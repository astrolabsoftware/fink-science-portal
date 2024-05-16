# Copyright 2024 AstroLab Software
# Author: Sergey Karpov
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import functools
import shlex

import numpy as np
import regex as re  # For partial matching

from apps.utils import request_api


@functools.lru_cache(maxsize=320)
def call_resolver(data, kind, reverse=False, **kwargs):
    """Call Fink resolver

    Parameters
    ----------
    data: str
        Query payload
    kind: str
        Resolver name: ssodnet, tns, simbad

    Returns
    -------
    payload: dict
        Payload returned by the /api/v1/resolver endpoint
    """
    if kind == "tns":
        # Normalize AT name to have whitespace before year
        m = re.match(r"^(AT|SN)\s*([12]\w+)$", str(data), re.IGNORECASE)
        if m:
            data = m[1].upper() + " " + m[2]
    elif kind == "ssodnet":
        data = str(data)

    try:
        if kind == "ztf":
            payload = request_api(
                "/api/v1/objects",
                json={
                    "objectId": data,
                    "columns": "i:ra,i:dec",
                },
                output="json",
            )
        else:
            params = {
                "resolver": kind,
                "name": str(data),
                "reverse": reverse,
            }
            params.update(kwargs)

            payload = request_api(
                "/api/v1/resolver",
                json=params,
                output="json",
            )
    except ValueError:
        payload = None

    return payload


name_patterns = [
    {
        "type": "ztf",
        "pattern": r"^ZTF[12]\d\w{7}$",
        "hint": "ZTF objectId (format ZTFyyccccccc)",
        "min": 3,
    },
    {
        "type": "tracklet",
        "pattern": r"^TRCK_\d{8}_\d{6}_\d{2}$",
        "hint": "tracklet (format TRCK_YYYYMMDD_HHMMSS_NN)",
        "min": 4,
    },
    # {
    #     'type': 'at',
    #     'pattern': '^AT[12]\d{3}\w{3}$',
    #     'hint': 'AT: ATyyyyccc',
    #     'min': 3
    # },
]


def parse_query(string, timeout=None):
    """Parse (probably incomplete) query

    Order is as follows:
    1. Extract object names (partially) matching some patterns
    2. Extract keyword parameters, either key:value or key=value
    3. Try to interpret the rest as coordinates as follows:
      - Pair of degrees
      - HH MM SS.S [+-]?DD MM SS.S
      - HH:MM:SS.S [+-]?DD:MM:SS.S
      - HHhMMhSS.Ss [+-]?DDhMMhSS.Ss
      - optionally, use one more number as a radius, in either arcseconds, minutes or degrees
    4. The rest is resolved through several Fink resolvers
    5. Finally, the action is suggested based on the parameters
      - for ZTF objectIds it is 'objectid' unless the radius `r` is explicitly given and the match is not partial (then it is 'conesearch')
      - for tracklets, it is always 'tracklet'
      - for resolved objects or coordinates, it is `conesearch` even if no radius is specified
      - for SSO objects it is always `sso`
      - if `after` keyword is specified it is `daterange`

    Parameters
    ----------
    string: str
        String to parse

    Returns
    -------
    Dictionary containing the following keys:
      - object: object name
      - type: object type derived from name parsing
      - hint: some human-readable description of what was parsed
      - action: suggested action for the query
      - params: dictionary with keyword parameters (ra, dec, r, ...)
      - string: original query string
    """
    # Results schema
    query = {
        "object": None,
        "type": None,
        "partial": False,
        "hint": None,
        "action": None,
        "params": {},
        "completions": [],
        "string": string,
    }

    if not string:
        return query

    string = string.replace(",", " ")  # TODO: preserve quoted commas?..

    # Sanitize the times to ISO format so that they parse as single tokens
    string = re.sub(
        r"\b([12]\d{3})[.-]([012]\d{1})[.-]([0123]\d{1})\s+([012]\d{1})[:]([012345]\d{1})[:]([012345]\d{1})(\.\d*)?\b",
        r"\1-\2-\3T\4:\5:\6\7",
        string,
    )

    # Split the string into tokens
    try:
        tokens = shlex.split(string, posix=True)  # It will also handle quoted strings
    except AttributeError:
        return query

    unparsed = []

    for token in tokens:
        is_parsed = False
        # Try to locate well-defined object name patterns
        for pattern in name_patterns:
            if pattern.get("min") and len(token) >= pattern.get("min"):
                m = re.match(pattern["pattern"], token, re.IGNORECASE, partial=True)
                if m:
                    query["object"] = token
                    query["type"] = pattern["type"]
                    query["hint"] = pattern["hint"]
                    query["partial"] = m.partial
                    is_parsed = True

                    if m.partial:
                        query["hint"] = query["hint"] + " (partial)"
                    break

        if is_parsed:
            continue

        # Try to parse keyword parameters, either as key:value or key=value
        m = re.match(r"^(\w+)[=:](.*?)$", token)
        if m:
            key = m[1].lower()
            value = m[2]
            # Special handling for numbers, possibly ending with d/m/s for degrees etc
            m = re.match(r'^([+-]?(\d+)(.\d+)?)([dms\'"]?)$', value)
            if m:
                value = float(m[1]) if "." in m[1] else int(m[1])
                if m[4] == "d":
                    value *= 3600
                elif m[4] == "m" or m[4] == "'":
                    value *= 60
                elif m[4] == "s" or m[4] == '"' or key == "r":
                    value *= 1

            query["params"][key] = value

        else:
            unparsed.append(token)

    string = " ".join(unparsed)

    # Parse the rest of the query string as coordinates, if any
    if len(string) and not query["object"]:
        # Pair of decimal degrees
        m = re.search(r"^(\d+\.?\d*)\s+([+-]?\d+\.?\d*)(\s+(\d+\.?\d*))?$", string)
        if m:
            query["params"]["ra"] = float(m[1])
            query["params"]["dec"] = float(m[2])
            if m[4] is not None:
                query["params"]["r"] = float(m[4])

            query["object"] = string
            query["type"] = "coordinates"
            query["hint"] = "Decimal coordinates"

            if m[4] is not None:
                query["hint"] += " with radius"

        else:
            # HMS DMS
            m = re.search(
                r"^(\d{1,2})\s+(\d{1,2})\s+(\d{1,2}\.?\d*)\s+([+-])?\s*(\d{1,3})\s+(\d{1,2})\s+(\d{1,2}\.?\d*)(\s+(\d+\.?\d*))?$",
                string,
            ) or re.search(
                r"^(\d{1,2})[:h](\d{1,2})[:m](\d{1,2}\.?\d*)[s]?\s+([+-])?\s*(\d{1,3})[d:](\d{1,2})[m:](\d{1,2}\.?\d*)[s]?(\s+(\d+\.?\d*))?$",
                string,
            )
            if m:
                query["params"]["ra"] = (
                    float(m[1]) + float(m[2]) / 60 + float(m[3]) / 3600
                ) * 15
                query["params"]["dec"] = (
                    float(m[5]) + float(m[6]) / 60 + float(m[7]) / 3600
                )

                if m[4] == "-":
                    query["params"]["dec"] *= -1

                if m[9] is not None:
                    query["params"]["r"] = float(m[9])

                query["object"] = string
                query["type"] = "coordinates"
                query["hint"] = "HMS DMS coordinates"

                if m[9] is not None:
                    query["hint"] += " with radius"

            else:
                query["object"] = string
                query["type"] = "unresolved"

    # Should we resolve object name?..
    if (
        query["object"]
        and query["type"] == "ztf"
        and not query["partial"]
        and "r" in query["params"]
    ):
        res = call_resolver(query["object"], "ztf")
        if res:
            query["params"]["ra"] = res[0]["i:ra"]
            query["params"]["dec"] = res[0]["i:dec"]

    if query["object"] and query["type"] not in [
        "ztf",
        "tracklet",
        "coordinates",
        None,
    ]:
        for reverse in [False, True]:
            if "ra" not in query["params"] and query["object"][0].isalpha():
                # TNS
                res = call_resolver(
                    query["object"], "tns", timeout=timeout, reverse=reverse
                )
                if res:
                    query["object"] = res[0]["d:fullname"]
                    query["type"] = "tns"
                    query["hint"] = "TNS object / {}".format(res[0]["d:internalname"])
                    query["params"]["ra"] = res[0]["d:ra"]
                    query["params"]["dec"] = res[0]["d:declination"]

                    if len(res) > 1:
                        # Make list of unique names not equal to the first one
                        query["completions"] = list(
                            np.unique(
                                [
                                    _["d:fullname"]
                                    for _ in res
                                    if _["d:fullname"] != res[0]["d:fullname"]
                                ],
                            ),
                        )

                    break

        if "ra" not in query["params"] and query["object"][0].isalpha():
            # Simbad
            res = call_resolver(query["object"], "simbad", timeout=timeout)
            if res:
                query["object"] = res[0]["oname"]
                query["type"] = "simbad"
                query["hint"] = "Simbad object / {}".format(res[0]["otype"])
                query["params"]["ra"] = res[0]["jradeg"]
                query["params"]["dec"] = res[0]["jdedeg"]

        if "ra" not in query["params"]:
            # SSO - final test
            res = call_resolver(query["object"], "ssodnet", timeout=timeout)
            if res:
                query["object"] = res[0]["i:name"]
                query["params"]["sso"] = res[0]["i:ssnamenr"]
                query["type"] = "sso"
                query["hint"] = "SSO object / {} {}".format(
                    res[0]["i:ssnamenr"], res[0]["i:name"]
                )

                if len(res) > 1:
                    query["completions"] = list(
                        dict.fromkeys(
                            [
                                (_["i:ssnamenr"], _["i:ssnamenr"] + " " + _["i:name"])
                                for _ in res
                                if _["i:ssnamenr"] != res[0]["i:ssnamenr"]
                            ],
                        ),
                    )

    # Handle aliases
    aliases = {"radius": "r"}
    for _ in aliases:
        if _ in query["params"]:
            query["params"][aliases[_]] = query["params"].pop(_)

    # Guess the kind of query
    if "ra" in query["params"] and "dec" in query["params"]:
        query["action"] = "conesearch"

    elif query["type"] == "ztf":
        query["action"] = "objectid"
        query["object"] = query["object"][:3].upper() + query["object"][3:]

    elif query["type"] == "tracklet":
        query["action"] = "tracklet"
        query["object"] = query["object"].upper()

    elif query["type"] == "sso" or "sso" in query["params"]:
        query["action"] = "sso"

    elif query["params"].get("class") == "Anomaly":
        query["action"] = "anomaly"
        query["hint"] = "Anomaly search"

    elif "random" in query["params"]:
        query["action"] = "random"
        query["hint"] = "Random search / {} objects".format(query["params"]["random"])

    elif "class" in query["params"]:
        query["action"] = "class"
        query["hint"] = "Class based search / {}".format(query["params"]["class"])

    elif "last" in query["params"]:
        query["action"] = "class"
        query["params"]["class"] = "All classes"
        query["hint"] = "Latest objects / {}, {} objects".format(
            query["params"]["class"], query["params"]["last"]
        )

    elif "after" in query["params"]:
        query["action"] = "daterange"
        query["hint"] = "Date range search"

    else:
        query["action"] = "unknown"

    return query

# Copyright 2023-2024 AstroLab Software
# Author: Julien Peloton
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
import requests
import datetime

import pandas as pd

import io
import sys

APIURL = sys.argv[1]


def ssoftsearch(
    version=None,
    flavor=None,
    sso_number=None,
    sso_name=None,
    schema=None,
    output_format="parquet",
):
    """Perform a sso search in the Science Portal using the Fink REST API"""
    payload = {"output-format": output_format}

    if version is not None:
        payload.update(
            {
                "version": version,
            }
        )

    if flavor is not None:
        payload.update(
            {
                "flavor": flavor,
            }
        )

    if sso_number is not None:
        payload.update(
            {
                "sso_number": sso_number,
            }
        )

    if sso_name is not None:
        payload.update(
            {
                "sso_name": sso_name,
            }
        )

    if schema is not None:
        payload.update(
            {
                "schema": True,
            }
        )

    r = requests.post("{}/api/v1/ssoft".format(APIURL), json=payload)

    assert r.status_code == 200, r.content

    if output_format == "json":
        # Format output in a DataFrame
        pdf = pd.read_json(io.BytesIO(r.content))
    elif output_format == "csv":
        pdf = pd.read_csv(io.BytesIO(r.content))
    elif output_format == "parquet":
        pdf = pd.read_parquet(io.BytesIO(r.content))

    return pdf


def default_ssoft() -> None:
    """
    Examples
    --------
    >>> default_ssoft()
    """
    pdf = ssoftsearch()

    assert not pdf.empty

    now = datetime.datetime.now()
    current_date = "{}.{:02d}".format(now.year, now.month)

    assert pdf["version"].to_numpy()[0] == current_date

    assert "alpha0" in pdf.columns


def previous_ssoft() -> None:
    """
    Examples
    --------
    >>> previous_ssoft()
    """
    pdf = ssoftsearch(version="2023.07")

    assert not pdf.empty


def test_ids() -> None:
    """
    Examples
    --------
    >>> test_ids()
    """
    pdf = ssoftsearch(sso_number="33803")

    assert len(pdf) == 1

    pdf = ssoftsearch(sso_name="Benoitcarry")

    assert len(pdf) == 1


def test_schema() -> None:
    """
    Examples
    --------
    >>> test_schema()
    """
    pdf = ssoftsearch(flavor="SHG1G2")

    schema = ssoftsearch(schema=True, flavor="SHG1G2", output_format="json")

    # check columns
    not_in_pdf = [i for i in set(schema["args"].keys()) if i not in set(pdf.columns)]
    not_in_schema = [i for i in set(pdf.columns) if i not in set(schema["args"].keys())]

    assert not_in_pdf == [], not_in_pdf
    assert not_in_schema == [], not_in_schema

    msg = "Found {} entries in the DataFrame and {} entries in the schema.".format(
        len(pdf.columns), len(schema)
    )
    assert set(schema["args"].keys()) == set(pdf.columns), msg


def compare_schema() -> None:
    """
    Examples
    --------
    >>> compare_schema()
    """
    schema1 = ssoftsearch(schema=True, flavor="SSHG1G2", output_format="json")

    # get the schema
    r = requests.get("{}/api/v1/ssoft?schema&flavor=SSHG1G2".format(APIURL))
    schema2 = r.json()

    keys1 = set(schema1["args"].keys())
    keys2 = set(schema2["args"].keys())
    assert keys1 == keys2, [keys1, keys2]


def check_sshg1g2() -> None:
    """
    Examples
    --------
    >>> check_sshg1g2()
    """
    pdf = ssoftsearch(flavor="SSHG1G2")

    assert "period" in pdf.columns
    assert "a_b_00" in pdf.columns


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

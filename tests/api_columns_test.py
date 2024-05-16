# Copyright 2024 AstroLab Software
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
import pandas as pd

import io
import sys

APIURL = sys.argv[1]


def get_fields_per_family():
    """Get fields exposed in /api/v1/columns"""
    r = requests.get("{}/api/v1/columns".format(APIURL))

    assert r.status_code == 200, r.content

    schema = r.json()

    categories = schema["fields"].keys()

    dic = {}
    for i in ["i:", "d:", "b:", "v:"]:
        for category in categories:
            if i in category:
                dic[i] = list(schema["fields"][category].keys())

    return dic


def check_recent_columns(columns, objectId):
    """Check the alert columns correspond to what is defined in /api/v1/columns"""
    fields_per_family = get_fields_per_family()

    for family in fields_per_family.keys():
        definition = fields_per_family[family]
        obtained = [
            i.split(family)[1]
            for i in columns
            if i.startswith(family) and ("t2_" not in i)
        ]

        outside_obtained = [i for i in definition if i not in obtained]
        assert len(outside_obtained) == 0, (
            "Not in obtained fields",
            family,
            outside_obtained,
            objectId,
        )

        # `spicy_name` was introduced by mistake instead of `spicy_class` for 2024/02/01
        outside_definition = [
            i for i in obtained if (i not in definition) and (i != "spicy_name")
        ]
        assert len(outside_definition) == 0, (
            "Not in defined fields",
            family,
            outside_definition,
            objectId,
        )


def check_old_columns(columns, objectId):
    """Check the alert columns correspond to what is defined in /api/v1/columns"""
    fields_per_family = get_fields_per_family()

    for family in fields_per_family.keys():
        definition = fields_per_family[family]
        obtained = [
            i.split(family)[1]
            for i in columns
            if i.startswith(family) and ("t2_" not in i)
        ]

        # Only d: has changed
        if family != "d:":
            outside_obtained = [i for i in definition if i not in obtained]
            assert len(outside_obtained) == 0, (
                "Not in obtained fields",
                family,
                outside_obtained,
                objectId,
            )

            # `spicy_name` was introduced by mistake instead of `spicy_class` for 2024/02/01
            outside_definition = [
                i for i in obtained if (i not in definition) and (i != "spicy_name")
            ]
            assert len(outside_definition) == 0, (
                "Not in defined fields",
                family,
                outside_definition,
                objectId,
            )
        else:
            recent_cols = [
                "DR3Name",
                "Plx",
                "anomaly_score",
                "delta_time",
                "e_Plx",
                "from_upper",
                "gcvs",
                "jd_first_real_det",
                "jdstarthist_dt",
                "lc_features_g",
                "lc_features_r",
                "lower_rate",
                "mag_rate",
                "mangrove_2MASS_name",
                "mangrove_HyperLEDA_name",
                "mangrove_ang_dist",
                "mangrove_lum_dist",
                "sigma_rate",
                "spicy_class",
                "spicy_id",
                "upper_rate",
                "vsx",
                "x3hsp",
                "x4lac",
            ]

            outside_obtained = [i for i in definition if i not in obtained]
            outside_obtained_ = [i for i in outside_obtained if i not in recent_cols]
            assert len(outside_obtained_) == 0, (
                "Not in obtained fields",
                family,
                outside_obtained_,
                objectId,
            )

            # `spicy_name` was introduced by mistake instead of `spicy_class` for 2024/02/01
            outside_definition = [
                i for i in obtained if (i not in definition) and (i != "spicy_name")
            ]
            assert len(outside_definition) == 0, (
                "Not in defined fields",
                family,
                outside_definition,
                objectId,
            )


def test_recent_object() -> None:
    """Supposed to fail if apps/api/api.py@columns_arguments is not updated correctly

    Examples
    --------
    >>> test_recent_object()
    """
    r = requests.post(
        "{}/api/v1/latests".format(APIURL),
        json={"class": "EB*", "n": 1, "columns": "i:objectId"},
    )

    assert r.status_code == 200, r.content

    objectId = r.json()[0]["i:objectId"]
    r2 = requests.post(
        "{}/api/v1/objects".format(APIURL),
        json={
            "objectId": objectId,
            "columns": "*",
            "output-format": "json",
            "withupperlim": True,
            "withcutouts": True,
        },
    )

    assert r2.status_code == 200, r2.content

    pdf = pd.read_json(io.BytesIO(r2.content))

    check_recent_columns(pdf.columns, objectId)


def test_old_object() -> None:
    """
    Examples
    --------
    >>> test_old_object()
    """
    objectId = "ZTF21abfmbix"
    r = requests.post(
        "{}/api/v1/objects".format(APIURL),
        json={
            "objectId": objectId,
            "columns": "*",
            "output-format": "json",
            "withupperlim": True,
            "withcutouts": True,
        },
    )

    assert r.status_code == 200, r.content

    pdf = pd.read_json(io.BytesIO(r.content))

    check_old_columns(pdf.columns, objectId)


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

# Copyright 2022 AstroLab Software
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


def statstest(date="2021", columns="*", output_format="json"):
    """Perform a stats search in the Science Portal using the Fink REST API"""
    payload = {
        "date": date,
        "columns": columns,
        "output-format": output_format,
    }

    r = requests.post("{}/api/v1/statistics".format(APIURL), json=payload)

    assert r.status_code == 200, r.content

    if output_format == "json":
        # Format output in a DataFrame
        pdf = pd.read_json(io.BytesIO(r.content))
    elif output_format == "csv":
        pdf = pd.read_csv(io.BytesIO(r.content))
    elif output_format == "parquet":
        pdf = pd.read_parquet(io.BytesIO(r.content))

    return pdf


def test_stats() -> None:
    """
    Examples
    --------
    >>> test_stats()
    """
    pdf = statstest()

    # Number of observation days in 2021
    assert len(pdf) == 254, len(pdf)


def test_a_day() -> None:
    """
    Examples
    --------
    >>> test_a_day()
    """
    pdf = statstest(date="20211103")

    assert len(pdf) == 1

    assert len(pdf.columns) == 131

    assert "basic:sci" in pdf.columns
    assert "basic:raw" in pdf.columns

    assert pdf["basic:raw"].to_numpy()[0] == 346644


def test_cols() -> None:
    """
    Examples
    --------
    >>> test_cols()
    """
    pdf = statstest(columns="basic:exposures,class:Solar System MPC")

    assert not pdf.empty

    assert len(pdf.columns) == 2 + 2, pdf.columns


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

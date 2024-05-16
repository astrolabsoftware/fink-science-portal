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
import numpy as np

from astropy.time import Time

import io
import sys

APIURL = sys.argv[1]


def trackletsearch(date="2021-08-10", columns="*", output_format="json"):
    """Perform a tracklet search in the Science Portal using the Fink REST API"""
    payload = {"date": date, "columns": columns, "output-format": output_format}

    r = requests.post("{}/api/v1/tracklet".format(APIURL), json=payload)

    assert r.status_code == 200, r.content

    if output_format == "json":
        # Format output in a DataFrame
        pdf = pd.read_json(io.BytesIO(r.content))
    elif output_format == "csv":
        pdf = pd.read_csv(io.BytesIO(r.content))
    elif output_format == "parquet":
        pdf = pd.read_parquet(io.BytesIO(r.content))

    return pdf


def test_simple_trackletsearch() -> None:
    """
    Examples
    --------
    >>> test_simple_trackletsearch()
    """
    pdf = trackletsearch()

    assert not pdf.empty

    assert np.all(pdf["d:tracklet"].to_numpy() != "")

    assert np.all([i.startswith("TRCK") for i in pdf["d:tracklet"].to_numpy()])


def test_fulldate() -> None:
    """
    Examples
    --------
    >>> test_fulldate()
    """
    pdf = trackletsearch(date="2021-10-22 09:19:49")
    jd0 = Time("2021-10-22 09:19:49").jd

    assert np.all(
        [np.round(i, 3) == np.round(jd0, 3) for i in pdf["i:jd"].to_numpy()]
    ), (jd0, pdf["i:jd"].to_numpy())


def test_single_tracklet() -> None:
    """
    Examples
    --------
    >>> test_single_tracklet()
    """
    pdf = trackletsearch(date="2021-10-22 09:19:49 00")

    assert np.all(pdf["d:tracklet"].to_numpy() == "TRCK_20211022_091949_00")


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

# Copyright 2023 AstroLab Software
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

from astropy.io import votable

import io
import sys
import json

APIURL = sys.argv[1]


def anomalysearch(
    n=10, start_date=None, stop_date=None, output_format="json", cols=None
):
    """Perform a search for anomaly"""
    payload = {"n": n, "output-format": output_format}

    if start_date is not None:
        payload.update({"start_date": start_date, "stop_date": stop_date})

    if cols is not None:
        payload.update({"columns": cols})

    r = requests.post("{}/api/v1/anomaly".format(APIURL), json=payload)

    assert r.status_code == 200, r.content

    if output_format == "json":
        # Format output in a DataFrame
        pdf = pd.read_json(io.BytesIO(r.content))
    elif output_format == "csv":
        pdf = pd.read_csv(io.BytesIO(r.content))
    elif output_format == "parquet":
        pdf = pd.read_parquet(io.BytesIO(r.content))
    elif output_format == "votable":
        vt = votable.parse(io.BytesIO(r.content))
        pdf = vt.get_first_table().to_table().to_pandas()

    return pdf


def test_simple_anomaly() -> None:
    """
    Examples
    --------
    >>> test_simple_anomaly()
    """
    pdf = anomalysearch()

    assert not pdf.empty

    assert len(pdf) == 10, len(pdf)

    assert np.all(pdf["d:anomaly_score"].to_numpy() < 0)


def test_anomaly_and_date() -> None:
    """
    Examples
    --------
    >>> test_anomaly_and_date()
    """
    pdf = anomalysearch(start_date="2023-01-25", stop_date="2023-01-25")

    assert not pdf.empty

    assert len(pdf) == 10, len(pdf)

    assert "ZTF23aaaatwl" in pdf["i:objectId"].to_numpy()


def test_anomaly_and_cols_with_sort() -> None:
    """
    Examples
    --------
    >>> test_anomaly_and_cols_with_sort()
    """
    pdf = anomalysearch(cols="i:jd,i:objectId")

    assert not pdf.empty

    assert len(pdf.columns) == 2, len(pdf.columns)

    assert "i:jd" in pdf.columns
    assert "i:objectId" in pdf.columns
    assert "v:classifation" not in pdf.columns


def test_query_url() -> None:
    """
    Examples
    --------
    >>> test_query_url()
    """
    pdf1 = anomalysearch()

    url = "{}/api/v1/anomaly?n=10&output-format=json".format(APIURL)
    r = requests.get(url)
    pdf2 = pd.read_json(io.BytesIO(r.content))

    # subset of cols to avoid type issues
    cols = ["d:anomaly_score"]

    isclose = np.isclose(pdf1[cols], pdf2[cols])
    assert np.all(isclose)


def test_various_outputs() -> None:
    """
    Examples
    --------
    >>> test_various_outputs()
    """
    pdf1 = anomalysearch(output_format="json")

    for fmt in ["csv", "parquet", "votable"]:
        pdf2 = anomalysearch(output_format=fmt)

        # subset of cols to avoid type issues
        cols1 = ["d:anomaly_score"]

        # https://docs.astropy.org/en/stable/io/votable/api_exceptions.html#w02-x-attribute-y-is-invalid-must-be-a-standard-xml-id
        cols2 = cols1 if fmt != "votable" else ["d_anomaly_score"]

        isclose = np.isclose(pdf1[cols1], pdf2[cols2])
        assert np.all(isclose), fmt


def test_feature_array() -> None:
    """
    Examples
    --------
    >>> test_feature_array()
    """
    pdf = anomalysearch()

    a_feature = pdf["d:lc_features_g"].to_numpy()[0]
    assert isinstance(a_feature, str), a_feature

    for col in ["d:lc_features_g", "d:lc_features_r"]:
        pdf[col] = pdf[col].apply(lambda x: json.loads(x))

    a_feature = pdf["d:lc_features_g"].to_numpy()[0]
    assert isinstance(a_feature, list), a_feature


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

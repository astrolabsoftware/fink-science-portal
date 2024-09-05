# Copyright 2022-2024 AstroLab Software
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

from astropy.coordinates import SkyCoord
from astropy.io import votable

import io
import sys

APIURL = sys.argv[1]


def conesearch(
    ra="193.8217409",
    dec="2.8973184",
    radius="5",
    startdate=None,
    window=None,
    output_format="json",
):
    """Perform a conesearch in the Science Portal using the Fink REST API"""
    payload = {"ra": ra, "dec": dec, "radius": radius, "output-format": output_format}

    if startdate is not None:
        payload.update({"startdate": startdate, "window": window})

    r = requests.post("{}/api/v1/conesearch".format(APIURL), json=payload)

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


def test_simple_conesearch() -> None:
    """
    Examples
    --------
    >>> test_simple_conesearch()
    """
    ra0 = 193.8217
    dec0 = 2.897
    radius = 5

    pdf = conesearch(ra=ra0, dec=dec0, radius=radius)

    # Not empty
    assert not pdf.empty

    # One object found
    assert len(pdf) == 1

    # Check the candidate is found no further away than the radius
    coord0 = SkyCoord(ra0, dec0, unit="deg")
    coord1 = SkyCoord(pdf["i:ra"].to_numpy()[0], pdf["i:dec"].to_numpy()[0], unit="deg")

    sep = coord0.separation(coord1).degree * 3600

    assert sep <= 5, sep


def test_conesearch_with_dates() -> None:
    """
    Examples
    --------
    >>> test_conesearch_with_dates()
    """
    # at this date, one object
    pdf1 = conesearch(
        ra="175.3242473",
        dec="36.5429392",
        radius="5",
        startdate="2021-11-03 10:00:00",
        window="1",
    )

    # at this date, a new object appeared
    pdf2 = conesearch(
        ra="175.3242473",
        dec="36.5429392",
        radius="5",
        startdate="2021-11-05 10:00:00",
        window="1",
    )

    assert pdf1.empty
    assert not pdf2.empty

    # One object found
    assert len(pdf2) == 1


def test_bad_radius_conesearch() -> None:
    """
    Examples
    --------
    >>> test_bad_radius_conesearch()
    """
    payload = {
        "ra": "175.3242473",
        "dec": "36.5429392",
        "radius": 36000,
        "output_format": "json",
    }

    r = requests.post("{}/api/v1/conesearch".format(APIURL), json=payload)

    msg = {
        "status": "error",
        "text": "`radius` cannot be bigger than 18,000 arcseconds (5 degrees).\n",
    }
    assert r.text == str(msg)


def test_empty_conesearch() -> None:
    """
    Examples
    --------
    >>> test_empty_conesearch()
    """
    pdf = conesearch(ra=0, dec=0, radius=1)

    assert pdf.empty


def test_coordinates() -> None:
    """
    Examples
    --------
    >>> test_coordinates()
    """
    pdf1 = conesearch(ra=193.822, dec=2.89732)
    pdf2 = conesearch(ra="193d49m18.267s", dec="2d53m50.35s")
    pdf3 = conesearch(ra="12h55m17.218s", dec="+02d53m50.35s")
    pdf4 = conesearch(ra="12 55 17.218", dec="+02 53 50.35")
    pdf5 = conesearch(ra="12:55:17.218", dec="02:53:50.35")

    magpsf = pdf1["i:magpsf"].to_numpy()
    for pdf in [pdf2, pdf3, pdf4, pdf5]:
        assert np.all(pdf["i:magpsf"].to_numpy() == magpsf)


def test_bad_request() -> None:
    """
    Examples
    --------
    >>> test_bad_request()
    """
    payload = {"ra": "kfdlkj", "dec": "lkfdjf", "radius": 5, "output_format": "json"}

    r = requests.post("{}/api/v1/conesearch".format(APIURL), json=payload)

    msg = {
        "status": "error",
        "text": ValueError("Invalid character at col 0 in angle 'kfdlkj'"),
    }
    assert r.text == str(msg), r.text


def test_various_outputs() -> None:
    """
    Examples
    --------
    >>> test_various_outputs()
    """
    pdf1 = conesearch(output_format="json")

    for fmt in ["csv", "parquet", "votable"]:
        pdf2 = conesearch(output_format=fmt)

        # subset of cols to avoid type issues
        cols1 = ["i:ra", "i:dec"]

        # https://docs.astropy.org/en/stable/io/votable/api_exceptions.html#w02-x-attribute-y-is-invalid-must-be-a-standard-xml-id
        cols2 = cols1 if fmt != "votable" else ["i_ra", "i_dec"]

        isclose = np.isclose(pdf1[cols1], pdf2[cols2])
        assert np.all(isclose), fmt


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

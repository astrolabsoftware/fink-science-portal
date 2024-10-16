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

import io
import sys

APIURL = sys.argv[1]


def ssosearch(
    n_or_d="8467",
    withEphem=False,
    withCutouts=False,
    withResiduals=False,
    cutout_kind=None,
    columns="*",
    output_format="json",
    expected_status=200,
):
    """Perform a sso search in the Science Portal using the Fink REST API"""
    payload = {
        "n_or_d": n_or_d,
        "withEphem": withEphem,
        "withcutouts": withCutouts,
        "withResiduals": withResiduals,
        "columns": columns,
        "output-format": output_format,
    }

    if cutout_kind is not None:
        payload.update({"cutout-kind": cutout_kind})

    r = requests.post("{}/api/v1/sso".format(APIURL), json=payload)

    assert r.status_code == expected_status, r.content

    if r.status_code == 200:
        if output_format == "json":
            # Format output in a DataFrame
            pdf = pd.read_json(io.BytesIO(r.content))
        elif output_format == "csv":
            pdf = pd.read_csv(io.BytesIO(r.content))
        elif output_format == "parquet":
            pdf = pd.read_parquet(io.BytesIO(r.content))
    else:
        pdf = pd.DataFrame()

    return pdf


def test_simple_ssosearch() -> None:
    """
    Examples
    --------
    >>> test_simple_ssosearch()
    """
    pdf = ssosearch()

    assert not pdf.empty

    assert np.all(pdf["i:ssnamenr"].to_numpy() > 0)

    assert np.all(pdf["d:roid"].to_numpy() == 3)

    assert len(pdf.groupby("i:ssnamenr").count()) == 1


def test_ephem() -> None:
    """
    Examples
    --------
    >>> test_ephem()
    """
    names = [
        "8467",
        "BenoitCarry",
        "JulienPeloton",
        "Phaethon",
        3200,
        "Lucretia",
        269,
        323137,
    ]
    for name in names:
        pdf = ssosearch(n_or_d=name, withEphem=True)

        assert not pdf.empty

        assert "Phase" in pdf.columns

        assert "SDSS:g" in pdf.columns


def test_residuals() -> None:
    """
    Examples
    --------
    >>> test_residuals()
    """
    pdf = ssosearch(withResiduals=True)

    assert not pdf.empty

    assert "residuals_shg1g2" in pdf.columns, list(pdf.columns)

    pdf = ssosearch("33803,8467", withResiduals=True, expected_status=400)

    assert pdf.empty

    pdf = ssosearch("323137", withResiduals=True)

    assert not pdf.empty

    assert np.isnan(pdf["residuals_shg1g2"].to_numpy()[0])


def test_comet() -> None:
    """
    Examples
    --------
    >>> test_comet()
    """
    pdf = ssosearch(n_or_d="10P", withEphem=True)

    assert not pdf.empty

    assert "Phase" in pdf.columns

    assert "SDSS:g" not in pdf.columns


def test_temp_designation() -> None:
    """
    Examples
    --------
    >>> test_temp_designation()
    """
    pdf_ephem = ssosearch(n_or_d="2010 JO69", withEphem=True)

    assert not pdf_ephem.empty

    assert "Phase" in pdf_ephem.columns

    assert "SDSS:g" in pdf_ephem.columns


def test_multiple_sso_names() -> None:
    """
    Examples
    --------
    >>> test_multiple_sso_names()
    """
    pdf = ssosearch(n_or_d="624188")

    assert len(pdf["sso_name"].unique()) == 1, pdf["sso_name"].unique()
    assert len(pdf["i:ssnamenr"].unique()) == 3, pdf["i:ssnamenr"].unique()

    # however we do not want Rubin & Rubincam
    pdf = ssosearch(n_or_d="Rubin")

    assert len(pdf["sso_name"].unique()) == 1, pdf["sso_name"].unique()
    assert len(pdf["i:ssnamenr"].unique()) == 1, pdf["i:ssnamenr"].unique()


def test_bad_request() -> None:
    """
    Examples
    --------
    >>> test_bad_request()
    """
    pdf = ssosearch(n_or_d="kdflsjffld", expected_status=400)

    assert pdf.empty


def test_multiple_ssosearch() -> None:
    """
    Examples
    --------
    >>> test_multiple_ssosearch()
    """
    pdf = ssosearch(n_or_d="8467,10P")

    assert not pdf.empty

    assert len(pdf.groupby("i:ssnamenr").count()) == 2

    assert len(pdf.groupby("sso_name").count()) == 2


def test_with_ephem_multiple_ssosearch() -> None:
    """
    Examples
    --------
    >>> test_with_ephem_multiple_ssosearch()
    """
    pdf = ssosearch(n_or_d="8467,1922", withEphem=True)

    assert len(pdf.groupby("i:ssnamenr").count()) == 2
    assert len(pdf.groupby("sso_name").count()) == 2
    assert len(pdf.groupby("sso_number").count()) == 2

    assert 8467 in np.unique(pdf["i:ssnamenr"].to_numpy())
    assert 1922 in np.unique(pdf["i:ssnamenr"].to_numpy())

    pdf1 = ssosearch(n_or_d="8467", withEphem=True)
    pdf2 = ssosearch(n_or_d="1922", withEphem=True)

    assert len(pdf) == len(pdf1) + len(pdf2)

    m1 = pdf["i:ssnamenr"] == 8467
    assert len(pdf[m1].to_numpy()) == len(pdf1.to_numpy()), (
        pdf[m1].to_numpy(),
        pdf1.to_numpy(),
    )

    m2 = pdf["i:ssnamenr"] == 1922
    assert len(pdf[m2].to_numpy()) == len(pdf2.to_numpy()), (
        pdf[m2].to_numpy(),
        pdf2.to_numpy(),
    )


def test_withcutouts() -> None:
    """
    Examples
    --------
    >>> test_withcutouts()
    """
    pdf = ssosearch(withCutouts=True)

    assert "b:cutoutScience_stampData" in pdf.columns
    assert isinstance(pdf["b:cutoutScience_stampData"].to_numpy()[0], list), pdf[
        "b:cutoutScience_stampData"
    ]

    pdf = ssosearch(withCutouts=True, cutout_kind="Template")

    assert "b:cutoutTemplate_stampData" in pdf.columns
    assert isinstance(pdf["b:cutoutTemplate_stampData"].to_numpy()[0], list)


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

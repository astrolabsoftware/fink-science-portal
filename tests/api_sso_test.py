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

def ssosearch(n_or_d='8467', withEphem=False, columns='*', output_format='json'):
    """ Perform a sso search in the Science Portal using the Fink REST API
    """
    payload = {
        'n_or_d': n_or_d,
        'withEphem': withEphem,
        'columns': columns,
        'output-format': output_format
    }

    r = requests.post(
        '{}/api/v1/sso'.format(APIURL),
        json=payload
    )

    if output_format == 'json':
        # Format output in a DataFrame
        pdf = pd.read_json(io.BytesIO(r.content))
    elif output_format == 'csv':
        pdf = pd.read_csv(io.BytesIO(r.content))
    elif output_format == 'parquet':
        pdf = pd.read_parquet(io.BytesIO(r.content))

    return pdf

def test_simple_ssosearch() -> None:
    """
    Examples
    ---------
    >>> test_simple_ssosearch()
    """
    pdf = ssosearch()

    assert not pdf.empty

    assert np.alltrue(pdf['i:ssnamenr'].values > 0)

    assert np.alltrue(pdf['d:roid'].values == 3)

    assert len(pdf.groupby('i:ssnamenr').count()) == 1

def test_ephem() -> None:
    """
    Examples
    ---------
    >>> test_ephem()
    """
    pdf = ssosearch(withEphem=True)

    assert not pdf.empty

    assert 'Phase' in pdf.columns

    assert 'SDSS:g' in pdf.columns

def test_comet() -> None:
    """
    Examples
    ---------
    >>> test_comet()
    """
    pdf = ssosearch(n_or_d='10P', withEphem=True)

    assert not pdf.empty

    assert 'Phase' in pdf.columns

    assert 'SDSS:g' not in pdf.columns

def test_temp_designation() -> None:
    """
    Examples
    ---------
    >>> test_temp_designation()
    """
    pdf_noephem = ssosearch(n_or_d='2010 JO69', withEphem=False)
    pdf_ephem = ssosearch(n_or_d='2010 JO69', withEphem=True)

    assert not pdf_noephem.empty
    assert not pdf_ephem.empty

    assert 'Phase' not in pdf_ephem.columns

    assert 'SDSS:g' not in pdf_ephem.columns

def test_bad_request() -> None:
    """
    Examples
    ---------
    >>> test_bad_request()
    """
    pdf = ssosearch(n_or_d='kdflsjffld')

    assert pdf.empty

def test_multiple_ssosearch() -> None:
    """
    Examples
    ---------
    >>> test_multiple_ssosearch()
    """
    pdf = ssosearch(n_or_d='8467,10P')

    assert not pdf.empty

    assert len(pdf.groupby('i:ssnamenr').count()) == 2

def test_with_ephem_multiple_ssosearch() -> None:
    """
    Examples
    ---------
    >>> test_with_ephem_multiple_ssosearch()
    """
    pdf = ssosearch(n_or_d='8467,1922', withEphem=True)

    assert len(pdf.groupby('i:ssnamenr').count()) == 2

    assert 8467 in np.unique(pdf['i:ssnamenr'].values)
    assert 1922 in np.unique(pdf['i:ssnamenr'].values)

    pdf1 = ssosearch(n_or_d='8467', withEphem=True)
    pdf2 = ssosearch(n_or_d='1922', withEphem=True)

    assert len(pdf) == len(pdf1) + len(pdf2)

    m1 = pdf['i:ssnamenr'] == 8467
    assert len(pdf[m1].values) == len(pdf1.values), (pdf[m1].values, pdf1.values)

    m2 = pdf['i:ssnamenr'] == 1922
    assert len(pdf[m2].values) == len(pdf2.values), (pdf[m2].values, pdf2.values)


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

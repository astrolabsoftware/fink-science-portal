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

def classsearch(myclass='Early SN Ia candidate', n=10, startdate=None, stopdate=None, output_format='json', cols=None):
    """ Perform a class search in the Science Portal using the Fink REST API
    """
    payload = {
        'class': myclass,
        'n': n,
        'output_format': output_format
    }

    if startdate is not None:
        payload.update(
            {
                'startdate': startdate,
                'stopdate': stopdate
            }
        )

    if cols is not None:
        payload.update({'columns': cols})

    r = requests.post(
        '{}/api/v1/latests'.format(APIURL),
        json=payload
    )

    if output_format == 'json':
        # Format output in a DataFrame
        pdf = pd.read_json(r.content)
    elif output_format == 'csv':
        pdf = pd.read_csv(io.BytesIO(r.content))
    elif output_format == 'parquet':
        pdf = pd.read_parquet(io.BytesIO(r.content))

    return pdf

def test_simple_classsearch() -> None:
    """
    Examples
    ---------
    >>> test_simple_classsearch()
    """
    pdf = classsearch()

    assert not pdf.empty

    assert len(pdf) == 10, len(pdf)

    assert np.alltrue(pdf['v:classification'].values == 'Early SN Ia candidate')

def test_simbad_classsearch() -> None:
    """
    Examples
    ---------
    >>> test_simbad_classsearch()
    """
    pdf = classsearch(myclass='(SIMBAD) QSO')

    assert not pdf.empty

    assert len(pdf) == 10, len(pdf)

    assert np.alltrue(pdf['v:classification'].values == 'QSO')

# def test_tns_classsearch() -> None:
#     """
#     Examples
#     ---------
#     >>> test_tns_classsearch()
#     """
#     pdf = classsearch(myclass='(TNS) SN Ia', n=100)
#
#     assert not pdf.empty
#
#     # 9 instead of 10 because we group by objectId,
#     # and among the 10 first alerts, there are 2 with the same objectId
#     assert len(pdf) == 9, len(pdf)
#
#     # print(pdf['i:fid'].values)
#     assert np.alltrue(pdf['i:fid'].values > 0)

def test_classsearch_and_date() -> None:
    """
    Examples
    ---------
    >>> test_classsearch_and_date()
    """
    pdf = classsearch(startdate='2021-11-01', stopdate='2021-12-01')

    assert not pdf.empty

    assert len(pdf) == 10, len(pdf)

    assert np.alltrue(pdf['v:classification'].values == 'Early SN Ia candidate')

    assert np.alltrue(pdf['v:lastdate'].values < '2021-12-01')

    assert np.alltrue(pdf['v:lastdate'].values >= '2021-11-01')

def test_classsearch_and_cols_with_sort() -> None:
    """
    Examples
    ---------
    >>> test_classsearch_and_cols_with_sort()
    """
    pdf = classsearch(cols='i:jd,i:objectId')

    assert not pdf.empty

    assert len(pdf.columns) == 2, len(pdf.columns)

    assert 'i:jd' in pdf.columns
    assert 'i:objectId' in pdf.columns
    assert 'v:classifation' not in pdf.columns

def test_classsearch_and_cols_without_sort() -> None:
    """
    Examples
    ---------
    >>> test_classsearch_and_cols_without_sort()
    """
    pdf = classsearch(cols='i:objectId')

    assert not pdf.empty

    assert len(pdf.columns) == 1, len(pdf.columns)

    assert 'i:objectId' in pdf.columns


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

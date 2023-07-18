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

APIURL = sys.argv[1]

def resolver(resolver='', name='', nmax=None, reverse=None, output_format='json'):
    """ Perform a conesearch in the Science Portal using the Fink REST API
    """
    payload = {
        'resolver': resolver,
        'name': name,
        'output-format': output_format
    }

    if reverse is not None:
        payload.update(
            {
                'reverse': True,
            }
        )

    if nmax is not None:
        payload.update(
            {
                'nmax': nmax,
            }
        )

    r = requests.post(
        '{}/api/v1/resolver'.format(APIURL),
        json=payload
    )

    if output_format == 'json':
        # Format output in a DataFrame
        pdf = pd.read_json(io.BytesIO(r.content))
    elif output_format == 'csv':
        pdf = pd.read_csv(io.BytesIO(r.content))
    elif output_format == 'parquet':
        pdf = pd.read_parquet(io.BytesIO(r.content))
    elif output_format == 'votable':
        vt = votable.parse(io.BytesIO(r.content))
        pdf = vt.get_first_table().to_table().to_pandas()

    return pdf

def test_tns_resolver() -> None:
    """
    Examples
    ---------
    >>> test_tns_resolver()
    """
    pdf = resolver(resolver='tns', name='SN 2023')

    # Not empty
    assert not pdf.empty

    # One object found
    assert len(pdf) == 10

    cols = ['d:declination', 'd:fullname', 'd:internalname', 'd:ra', 'd:type']
    for col in cols:
        assert col in pdf.columns, col

def test_reverse_tns_resolver() -> None:
    """
    Examples
    ---------
    >>> test_reverse_tns_resolver()
    """
    pdf = resolver(resolver='tns', name='ZTF23aaaahln', reverse=True)

    # Not empty
    assert not pdf.empty

    # One object found
    assert len(pdf) == 1

    assert pdf['d:fullname'].values[0] == 'SN 2023Q', pdf.columns

def test_nmax() -> None:
    """
    Examples
    ---------
    >>> test_nmax()
    """
    pdf = resolver(resolver='tns', name='SN 2023', nmax=20)

    # Not empty
    assert not pdf.empty

    # One object found
    assert len(pdf) == 20

def test_simbad_resolver() -> None:
    """
    Examples
    ---------
    >>> test_simbad_resolver()
    """
    pdf = resolver(resolver='simbad', name='Markarian 2')

    # Not empty
    assert not pdf.empty

    # One object found
    assert len(pdf) == 1

    assert pdf['oname'].values[0] == 'Mrk 2', pdf['oname']

    cols = [
        'name', 'oid', 'oname', 'otype',
        'jpos', 'jradeg', 'jdedeg',
        'refPos', 'Vel', 'MType', 'nrefs'
    ]
    for col in cols:
        assert col in pdf.columns, [col, pdf.columns]

def test_reverse_simbad_resolver() -> None:
    """
    Examples
    ---------
    >>> test_reverse_simbad_resolver()
    """
    pdf = resolver(resolver='simbad', name='ZTF18aabfjoi', reverse=True)

    # Not empty
    assert not pdf.empty

    # One object found
    assert len(pdf) == 5, len(pdf)

    assert pdf['d:cdsxmatch'].values[0] == 'GinGroup', pdf['d:cdsxmatch'].values

def test_ssodnet_resolver() -> None:
    """
    Examples
    ---------
    >>> test_ssodnet_resolver()
    """
    pdf = resolver(resolver='ssodnet', name='33803')

    # Not empty
    assert not pdf.empty

    # One object found
    assert len(pdf) == 10

    assert '1999 VK210' in pdf['name'].values, pdf['name'].values

    cols = [
        'type', 'system', 'class', 'updated',
        'ephemeris', 'physical-ephemeris',
        'aliases', 'links', 'id', 'name', 'parent'
    ]
    for col in cols:
        assert col in pdf.columns, [col, pdf.columns]

def test_reverse_ssodnet_resolver() -> None:
    """
    Examples
    ---------
    >>> test_reverse_ssodnet_resolver()
    """
    pdf = resolver(resolver='ssodnet', name='ZTF23aabccya', reverse=True)

    # Not empty
    assert not pdf.empty

    # One object found
    assert len(pdf) == 1, len(pdf)

    assert pdf['i:ssnamenr'].values[0] == 33803, pdf['i:ssnamenr'].values


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

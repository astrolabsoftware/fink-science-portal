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

from astropy.io import votable

import io
import sys

APIURL = sys.argv[1]

def push_euclid(fn='old_ssopipe.txt'):
    """ Push Euclid SSO data
    """
    data = open(fn, 'rb').read()

    r = requests.post(
        '{}/api/v1/euclidin'.format(APIURL),
        json={
            'EID': '6565656',
            'pipeline': 'ssopipe',
            'version': '1.0',
            'date': '19881103',
            'payload': str(data),
            'mode': 'sandbox'
        }
    )

    return r.content

def pull_euclid(pipeline='ssopipe', dates='20210101', columns='*', output_format='json'):
    """ Pull Euclid data
    """
    payload = {
        'pipeline': pipeline,
        'dates': dates,
        'columns': columns,
        'mode': 'sandbox',
        'output-format': output_format
    }

    r = requests.post(
        '{}/api/v1/eucliddata'.format(APIURL),
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

def test_euclid_push() -> None:
    """
    Examples
    ---------
    >>> test_euclid_push()
    """
    msg = push_euclid()

    # Not empty
    assert msg == b'6565656 - ssopipe - 1.0 - 19881103 - Uploaded!', msg


def test_euclid_single_date() -> None:
    """
    Examples
    ---------
    >>> test_euclid_single_date()
    """
    pdf = pull_euclid(dates='20210101')

    # Not empty
    assert not pdf.empty

    # One object found
    assert len(pdf) == 2798, len(pdf)

def test_euclid_range_date() -> None:
    """
    Examples
    ---------
    >>> test_euclid_range_date()
    """
    pdf = pull_euclid(dates='20210101:20210102')

    # Not empty
    assert not pdf.empty

    # One object found
    assert len(pdf) == 2798, len(pdf)

def test_euclid_all_date() -> None:
    """
    Examples
    ---------
    >>> test_euclid_all_date()
    """
    pdf = pull_euclid(dates='*')

    # Not empty
    assert not pdf.empty

    # One object found
    assert len(pdf) == 2798, len(pdf)

def test_euclid_columns() -> None:
    """
    Examples
    ---------
    >>> test_euclid_columns()
    """
    pdf = pull_euclid(dates='20210101', columns='d:INDEX')

    # Not empty
    assert not pdf.empty

    # One object found
    assert len(pdf.columns) == 1, pdf.columns


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

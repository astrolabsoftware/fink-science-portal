# Copyright 2023-2024 AstroLab Software
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
import datetime

import pandas as pd
import numpy as np

import io
import sys

APIURL = sys.argv[1]

def ssoftsearch(version=None, flavor=None, sso_number=None, sso_name=None, schema=None, output_format='parquet'):
    """ Perform a sso search in the Science Portal using the Fink REST API
    """
    payload = {
        'output-format': output_format
    }

    if version is not None:
        payload.update(
            {
                'version': version,
            }
        )

    if flavor is not None:
        payload.update(
            {
                'flavor': flavor,
            }
        )

    if sso_number is not None:
        payload.update(
            {
                'sso_number': sso_number,
            }
        )

    if sso_name is not None:
        payload.update(
            {
                'sso_name': sso_name,
            }
        )

    if schema is not None:
        payload.update(
            {
                'schema': True,
            }
        )

    r = requests.post(
        '{}/api/v1/ssoft'.format(APIURL),
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

def default_ssoft() -> None:
    """
    Examples
    ---------
    >>> default_ssoft()
    """
    pdf = ssoftsearch()

    assert not pdf.empty

    now = datetime.datetime.now()
    current_date = '{}.{:02d}'.format(now.year, now.month)

    assert pdf['version'].values[0] == current_date

    assert 'alpha0' in pdf.columns

def previous_ssoft() -> None:
    """
    Examples
    ---------
    >>> previous_ssoft()
    """
    pdf = ssoftsearch(version='2023.07')

    assert not pdf.empty

def test_ids() -> None:
    """
    Examples
    ---------
    >>> test_ids()
    """
    pdf = ssoftsearch(sso_number='33803')

    assert len(pdf) == 1

    pdf = ssoftsearch(sso_name='Benoitcarry')

    assert len(pdf) == 1

def test_schema() -> None:
    """
    Examples
    ---------
    >>> test_schema()
    """
    pdf = ssoftsearch(schema=True, output_format='json')

    assert len(pdf) == 55, 'Found {} entries'.format(len(pdf))


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

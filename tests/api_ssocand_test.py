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

def ssocandsearch(kind='orbParams', trajectory_id=None, start_date=None, stop_date=None, output_format='json'):
    """ Perform a sso candidate search in the Science Portal using the Fink REST API
    """
    payload = {
        'kind': kind,
        'output-format': output_format
    }

    if trajectory_id is not None:
        payload.update({'trajectory_id': trajectory_id})
    if start_date is not None:
        payload.update({'start_date': start_date})
    if stop_date is not None:
        payload.update({'stop_date': stop_date})

    r = requests.post(
        '{}/api/v1/ssocand'.format(APIURL),
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

def test_orbparam() -> None:
    """
    Examples
    ---------
    >>> test_orbparam()
    """
    pdf = ssocandsearch()

    assert not pdf.empty

    assert len(pdf) >= 580

    assert 'd:a' in pdf.columns

def test_lightcurves() -> None:
    """
    Examples
    ---------
    >>> test_lightcurves()
    """
    pdf = ssocandsearch(kind='lightcurves')

    assert not pdf.empty

    assert 'd:dcmag' in pdf.columns

def test_time_boundaries() -> None:
    """
    Examples
    ---------
    >>> test_time_boundaries()
    """
    pdf = ssocandsearch(
        kind='lightcurves', start_date='2020-01-01', stop_date='2020-12-31'
    )

    assert not pdf.empty

    assert np.alltrue(pdf['d:jd'].values >= Time('2020-01-01', format='iso').jd)
    assert np.alltrue(pdf['d:jd'].values <= Time('2020-12-31', format='iso').jd)


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

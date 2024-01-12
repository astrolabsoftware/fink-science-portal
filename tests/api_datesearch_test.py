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

def datesearch(startdate='2021-07-01 05:59:37.000', window=1/24/60, output_format='json'):
    """ Perform a date search in the Science Portal using the Fink REST API
    """
    payload = {
        'startdate': startdate,
        'window': window,
        'output-format': output_format
    }

    r = requests.post(
        '{}/api/v1/explorer'.format(APIURL),
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

def test_simple_datesearch() -> None:
    """
    Examples
    ---------
    >>> test_simple_datesearch()
    """
    pdf = datesearch()

    assert not pdf.empty

    assert len(pdf) == 407, len(pdf)

    assert (np.max(pdf['i:jd']) - np.min(pdf['i:jd'])) <= 1

def test_bad_datesearch() -> None:
    """
    Examples
    ---------
    >>> test_bad_datesearch()
    """

    pdf1 = datesearch('2021-07-01 05:59:37.000', window=3/24)

    # The window is rounded to 3 hours so results should be equal
    pdf2 = datesearch('2021-07-01 05:59:37.000', window=1)

    assert len(pdf1) == len(pdf2), '{} != {}'.format(len(pdf1), len(pdf2))


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

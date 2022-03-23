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
import time

import io
import sys

APIURL = sys.argv[1]

def classsearch(myclass='Solar System MPC', n=100000, startdate='2022-03-03', stopdate='2022-03-04', output_format='json'):
    """ Perform a heavy class search in the Science Portal using the Fink REST API
    """
    payload = {
        'class': myclass,
        'n': n,
        'output-format': output_format
    }

    if startdate is not None:
        payload.update(
            {
                'startdate': startdate,
                'stopdate': stopdate
            }
        )

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

def test_heavy_classsearch() -> None:
    """
    Examples
    ---------
    >>> test_heavy_classsearch()
    """
    t0 = time.time()
    pdf = classsearch()
    dt = time.time() - t0

    # less than 45 seconds to get 21,000 objects
    assert dt < 45, 'Spent {} seconds in querying for MPC objects -- too long!'.format(dt)


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

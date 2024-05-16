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

import io
import sys

APIURL = sys.argv[1]

def xmatchtest(catalog='mycatalog.csv', header='RA,Dec,ID,Time', radius=1.5, window=7):
    """Perform a xmatch search in the Science Portal using the Fink REST API
    """
    payload = {
        'catalog': open(catalog).read(),
        'header': header,
        'radius': radius, # in arcsecond
        'window': window # in days
    }

    r = requests.post(
        '{}/api/v1/xmatch'.format(APIURL),
        json=payload
    )

    assert r.status_code == 200, r.content

    pdf = pd.read_json(io.BytesIO(r.content))

    return pdf

def test_xmatch() -> None:
    """
    Examples
    --------
    >>> test_xmatch()
    """
    pdf = xmatchtest()

    assert len(pdf) == 1, len(pdf)

    assert pdf['ID'].to_numpy()[0] == 'AnObjectMatching'


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

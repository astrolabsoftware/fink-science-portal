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

def bayestartest(bayestar='bayestar.fits.gz', credible_level=0.1, output_format='json'):
    """ Perform a GW search in the Science Portal using the Fink REST API
    """
    data = open(bayestar, 'rb').read()
    payload = {
        'bayestar': str(data),
        'credible_level': credible_level,
        'output-format': output_format
    }

    r = requests.post(
        '{}/api/v1/bayestar'.format(APIURL),
        json=payload
    )

    pdf = pd.read_json(r.content)

    return pdf

def test_bayestar() -> None:
    """
    Examples
    ---------
    >>> test_bayestar()
    """
    pdf = bayestartest()

    assert len(pdf) == 49, len(pdf)

    a = pdf.groupby('v:classification').count()\
        .sort_values('i:objectId', ascending=False)['i:objectId']\
        .to_dict()

    assert a['QSO'] == 16, a


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

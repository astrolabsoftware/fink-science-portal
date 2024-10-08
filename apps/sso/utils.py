# Copyright 2024 AstroLab Software
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

import numpy as np
import rocks

def resolve_sso_name_to_ssnamenr(sso_name):
    """Find corresponding ZTF ssnamenr from user input

    Parameters
    ----------
    sso_name: str
        SSO name or number

    Returns
    ----------
    out: list of str
        List of corresponding ZTF ssnamenr
    """
    # search all ssnamenr corresponding quaero -> ssnamenr
    r = requests.post(
        'https://fink-portal.org/api/v1/resolver',
        json={
            'resolver': 'ssodnet',
            'name': sso_name
        }
    )
    if r.status_code != 200:
        return []

    ssnamenrs = np.unique([i["i:ssnamenr"] for i in r.json()])

    return ssnamenrs

def resolve_sso_name(sso_name):
    """Find corresponding UAI name and number using quaero

    Parameters
    ----------
    sso_name: str
        SSO name or number

    Returns
    ----------
    name: str
        UAI name. NaN if does not exist.
    number: str
        UAI number. NaN if does not exist.
    """
    sso_name, sso_number = rocks.identify(sso_name)
    return sso_name, sso_number

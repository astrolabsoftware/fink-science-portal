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

def get_an_object(number=1, output_format='json', columns='*', object_class="", seed=None):
    """ Query an object from the Science Portal using the Fink REST API
    """
    payload = {
        'n': number,
        'columns': columns,
        'output-format': output_format,
    }

    if object_class != "":
        payload.update({'class': object_class})

    if seed is not None:
        payload.update({'seed': int(seed)})

    r = requests.post(
        '{}/api/v1/random'.format(APIURL),
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

def test_single_object() -> None:
    """
    Examples
    ---------
    >>> test_single_object()
    """
    pdf = get_an_object(number=1)

    assert not pdf.empty

def test_multiple_objects() -> None:
    """
    Examples
    ---------
    >>> test_multiple_objects()
    """
    pdf = get_an_object(number=3)
    nobjects = len(pdf.groupby('i:objectId').count())

    assert nobjects == 3, nobjects

def test_seed() -> None:
    """
    Examples
    ---------
    >>> test_seed()
    """
    pdf1 = get_an_object(number=1, seed=54859)
    pdf2 = get_an_object(number=1, seed=54859)

    oid1 = np.unique(pdf1['i:objectId'].values)
    oid2 = np.unique(pdf2['i:objectId'].values)

    assert oid1 == oid2

    pdf1 = get_an_object(number=1)
    pdf2 = get_an_object(number=1)

    oid1 = np.unique(pdf1['i:objectId'].values)
    oid2 = np.unique(pdf2['i:objectId'].values)

    assert oid1 != oid2

def test_column_selection() -> None:
    """
    Examples
    ---------
    >>> test_column_selection()
    """
    pdf = get_an_object(number=1, columns='i:jd,i:magpsf')

    assert len(pdf.columns) == 2, 'I count {} columns'.format(len(pdf.columns))

def test_class() -> None:
    """
    Examples
    ---------
    >>> test_class()
    """
    pdf = get_an_object(number=3, object_class="Solar System MPC")

    assert np.all([i == 'Solar System MPC' for i in pdf['v:classification'].values])


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

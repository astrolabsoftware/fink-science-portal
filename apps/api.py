# Copyright 2020 AstroLab Software
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
from flask import request, abort, jsonify
from app import client

import io
import pandas as pd

from flask import Blueprint

PORTAL_URL = 'http://134.158.75.151:24000'

api_bp = Blueprint('', __name__)

args_objects = [
    {
        'name': 'objectId',
        'required': True,
        'description': 'ZTF Object ID'
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet'
    }
]

@api_bp.route('/api/v1/objects', methods=['GET'])
def return_object_arguments():
    """ Obtain information about retrieving object data
    """
    msg = """
    In python you would use
    ```python
    import requests
    import pandas as pd
    import io

    # get data for ZTF19acnjwgm as json
    r = requests.post(
      '{}/api/v1/objects',
      json={'objectId': 'ZTF19acnjwgm', 'output-format': 'json'}
    )

    pdf = pd.read_json(r.content)

    # get data for ZTF19acnjwgm as csv
    r = requests.post(
      '{}/api/v1/objects',
      json={'objectId': 'ZTF19acnjwgm', 'output-format': 'csv'}
    )

    pdf = pd.read_csv(io.BytesIO(r.content))
    ```

    In a unix shell, you would simply use
    ```sh
    curl -H "Content-Type: application/json" \
        -X POST -d '{"objectId":"ZTF19acnjwgm", "output-format":"csv"}' \
        {}/api/v1/objects \
        -o ZTF19acnjwgm.csv
    ```
    """.format(PORTAL_URL, PORTAL_URL, PORTAL_URL)
    args_objects.append(
        {
            'Usage': msg
        }
    )
    return jsonify({'args': args_objects})

@api_bp.route('/api/v1/objects', methods=['POST'])
def return_object():
    """ Retrieve object data from the Fink database
    """
    # Check all required args are here
    required_args = [i for i in args_objects if i['required'] is True]
    for required_arg in required_args:
        if required_arg not in request.json:
            rep = {
                'status': 'error',
                'text': "A value for `{}` is required. Use GET to check arguments.\n".format(required_arg)
            }
            return Response(str(rep), 400)

    to_evaluate = "key:key:{}".format(request.json['objectId'])
    results = client.scan(
        "",
        to_evaluate,
        "*",
        0, True, True
    )
    pdf = pd.DataFrame.from_dict(results, orient='index')
    if 'output-format' not in request.json or request.json['output-format'] == 'json':
        return pdf.to_json()
    elif request.json['output-format'] == 'csv':
        return pdf.to_csv(index=False)
    elif request.json['output-format'] == 'parquet':
        return pdf.parquet(io.BytesIO())

    rep = {
        'status': 'error',
        'text': "Output format `{}` is not supported. Choose among json, csv, or parquet\n".format(request.json['output-format'])
    }
    return Response(str(rep), 400)

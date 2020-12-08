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
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc

from flask import request, jsonify, Response
from app import client

import io
import pandas as pd

from flask import Blueprint

PORTAL_URL = 'http://134.158.75.151:24000'

api_bp = Blueprint('', __name__)

api_doc = """
# Fink API

## Summary of services

| HTTP Method | URI | Action |
|-------------|-----|--------|
| POST | http://134.158.75.151:24000/api/v1/objects| Retrieve object data from the Fink database |
| GET | http://134.158.75.151:24000/api/v1/objects | Obtain information about retrieving object data |
| POST | http://134.158.75.151:24000/api/v1/explorer | Query the Fink alert database |
| GET | http://134.158.75.151:24000/api/v1/explorer | Obtain information about querying the Fink alert database|
| POST | http://134.158.75.151:24000/api/v1/xmatch | Cross-match user-defined catalog with Fink alert data|
| GET | http://134.158.75.151:24000/api/v1/xmatch | Obtain information about catalog cross-match|

## Retrieve object data

The list of arguments for retrieving object data can be found at http://134.158.75.151:24000/api/v1/objects.
In a unix shell, you would simply use

```bash
# Get data for ZTF19acnjwgm and save it in a CSV file
curl -H "Content-Type: application/json" -X POST -d '{"objectId":"ZTF19acnjwgm", "output-format":"csv"}' http://134.158.75.151:24000/api/v1/objects -o ZTF19acnjwgm.csv
```

In python, you would use

```python
import requests
import pandas as pd

# get data for ZTF19acnjwgm
r = requests.post(
  'http://134.158.75.151:24000/api/v1/objects',
  json={
    'objectId': 'ZTF19acnjwgm',
    'output-format': 'json'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)
```

Note that for `csv` output, you need to use

```python
# get data for ZTF19acnjwgm in CSV format...
r = ...

pd.read_csv(io.BytesIO(r.content))
```
"""

layout = html.Div(
    [
        html.Br(),
        dbc.Container(
            [
                dbc.Row(
                    [
                        dbc.Card(
                            dbc.CardBody(
                                dcc.Markdown(api_doc)
                            ), style={
                                'backgroundColor': 'rgb(248, 248, 248, .7)'
                            }
                        )
                    ]
                ),
            ], className="mb-8", fluid=True, style={'width': '95%'}
        )
    ], className='home', style={
        'background-image': 'linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(/assets/background.png)',
        'background-size': 'contain'
    }
)

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
    return jsonify({'args': args_objects})

@api_bp.route('/api/v1/objects', methods=['POST'])
def return_object():
    """ Retrieve object data from the Fink database
    """
    # Check all required args are here
    required_args = [i['name'] for i in args_objects if i['required'] is True]
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
        f = io.BytesIO()
        pdf.to_parquet(f)
        f.seek(0)
        return f.read()

    rep = {
        'status': 'error',
        'text': "Output format `{}` is not supported. Choose among json, csv, or parquet\n".format(request.json['output-format'])
    }
    return Response(str(rep), 400)

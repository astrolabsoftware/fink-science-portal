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

from app import client, clientP, clientT, clientS, nlimit
from apps.utils import extract_fink_classification, convert_jd

import io
import healpy as hp
import pandas as pd
import numpy as np

import astropy.units as u
from astropy.time import Time, TimeDelta
from astropy.coordinates import SkyCoord

from flask import Blueprint

PORTAL_URL = 'http://134.158.75.151:24000'

api_bp = Blueprint('', __name__)

api_doc_summary = """
# Fink API

## Summary of services

| HTTP Method | URI | Action | Availability |
|-------------|-----|--------|--------------|
| POST/GET | http://134.158.75.151:24000/api/v1/objects| Retrieve single object data from the Fink database | &#x2611;&#xFE0F; |
| POST/GET | http://134.158.75.151:24000/api/v1/explorer | Query the Fink alert database | &#x2611;&#xFE0F; |
| POST/GET | http://134.158.75.151:24000/api/v1/latests | Get latest alerts by class | &#x2611;&#xFE0F; |
| POST/GET | http://134.158.75.151:24000/api/v1/xmatch | Cross-match user-defined catalog with Fink alert data| &#x274C; |
| GET  | http://134.158.75.151:24000/api/v1/classes  | Display all Fink derived classification | &#x2611;&#xFE0F; |
"""

api_doc_object = """
## Retrieve single object data

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

api_doc_explorer = """
## Query the Fink alert database

Currently, you cannot query using several conditions.
You must choose among `Search by Object ID` (group 0), `Conesearch` (group 1), or `Search by Date` (group 2).
In a future release, you will be able to combine searches.
The list of arguments for querying the Fink alert database can be found at http://134.158.75.151:24000/api/v1/explorer.

### Search by Object ID

Enter a valid object ID to access its data, e.g. try:

* ZTF19acmdpyr, ZTF19acnjwgm, ZTF17aaaabte, ZTF20abqehqf, ZTF18acuajcr

In a unix shell, you would simply use

```bash
# Get data for ZTF19acnjwgm and save it in a CSV file
curl -H "Content-Type: application/json" -X POST -d '{"objectId":"ZTF19acnjwgm"}' http://134.158.75.151:24000/api/v1/explorer -o search_ZTF19acnjwgm.json
```

In python, you would use

```python
import requests
import pandas as pd

# get data for ZTF19acnjwgm
r = requests.post(
  'http://134.158.75.151:24000/api/v1/explorer',
  json={
    'objectId': 'ZTF19acnjwgm',
  }
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)
```

### Conesearch

Perform a conesearch around a position on the sky given by (RA, Dec, radius).
The initializer for RA/Dec is very flexible and supports inputs provided in a number of convenient formats.
The following ways of initializing a conesearch are all equivalent (radius in arcsecond):

* 271.3914265, 45.2545134, 5
* 271d23m29.1354s, 45d15m16.2482s, 5
* 18h05m33.9424s, +45d15m16.2482s, 5
* 18 05 33.9424, +45 15 16.2482, 5
* 18:05:33.9424, 45:15:16.2482, 5

In a unix shell, you would simply use

```bash
# Get all objects falling within (center, radius) = ((ra, dec), radius)
curl -H "Content-Type: application/json" -X POST -d '{"ra":"271.3914265", "dec":"45.2545134", "radius":"5"}' http://134.158.75.151:24000/api/v1/explorer -o conesearch.json
```

In python, you would use

```python
import requests
import pandas as pd

# Get all objects falling within (center, radius) = ((ra, dec), radius)
r = requests.post(
  'http://134.158.75.151:24000/api/v1/explorer',
  json={
    'ra': '271.3914265',
    'dec': '45.2545134',
    'radius': '5'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)
```

### Search by Date

Choose a starting date and a time window to see all alerts in this period.
Dates are in UTC, and the time window in minutes.
Example of valid search:

* 2019-11-03 02:40:00

In a unix shell, you would simply use

```bash
# Get all objects between 2019-11-03 02:40:00 and 2019-11-03 02:50:00 UTC
curl -H "Content-Type: application/json" -X POST -d '{"startdate":"2019-11-03 02:40:00", "window":"10"}' http://134.158.75.151:24000/api/v1/explorer -o datesearch.json
```

In python, you would use

```python
import requests
import pandas as pd

# Get all objects between 2019-11-03 02:40:00 and 2019-11-03 02:50:00 UTC
r = requests.post(
  'http://134.158.75.151:24000/api/v1/explorer',
  json={
    'startdate': '2019-11-03 02:40:00',
    'window': '10'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)
```
"""

api_doc_latests = """
## Get latest alerts by class

The list of arguments for getting latest alerts by class can be found at http://134.158.75.151:24000/api/v1/latests.

The list of Fink class can be found at http://134.158.75.151:24000/api/v1/classes

```bash
# Get list of available class in Fink
curl -H "Content-Type: application/json" -X GET http://134.158.75.151:24000/api/v1/classes -o finkclass.json
```

In a unix shell, you would simply use

```bash
# Get latests 5 Early SN candidates
curl -H "Content-Type: application/json" -X POST -d '{"class":"Early SN candidate", "n":"5"}' http://134.158.75.151:24000/api/v1/latests -o latest_five_sn_candidates.json
```

In python, you would use

```python
import requests
import pandas as pd

# Get latests 5 Early SN candidates
r = requests.post(
  'http://134.158.75.151:24000/api/v1/latests',
  json={
    'class': 'Early SN candidate',
    'n': '5'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)
```

Note that for `csv` output, you need to use

```python
# get latests in CSV format...
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
                                dcc.Markdown(api_doc_summary)
                            ), style={
                                'backgroundColor': 'rgb(248, 248, 248, .7)'
                            }
                        ),
                    ]
                ),
                html.Br(),
                dbc.Tabs(
                    [
                        dbc.Tab(
                            [
                                dbc.Card(
                                    dbc.CardBody(
                                        dcc.Markdown(api_doc_object)
                                    ), style={
                                        'backgroundColor': 'rgb(248, 248, 248, .7)'
                                    }
                                ),
                            ], label="Retrieve object data"
                        ),
                        dbc.Tab(
                            [
                                dbc.Card(
                                    dbc.CardBody(
                                        dcc.Markdown(api_doc_explorer)
                                    ), style={
                                        'backgroundColor': 'rgb(248, 248, 248, .7)'
                                    }
                                ),
                            ], label="Query the database"
                        ),
                        dbc.Tab(
                            [
                                dbc.Card(
                                    dbc.CardBody(
                                        dcc.Markdown(api_doc_latests)
                                    ), style={
                                        'backgroundColor': 'rgb(248, 248, 248, .7)'
                                    }
                                ),
                            ], label="Get latest alerts"
                        ),
                        dbc.Tab(label="Xmatch", disabled=True),
                    ]
                )
            ], className="mb-8", fluid=True, style={'width': '80%'}
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
        'name': 'withcutouts',
        'required': False,
        'description': 'If True, retrieve also gzipped FITS cutouts.'
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet'
    }
]

args_explorer = [
    {
        'name': 'objectId',
        'required': False,
        'group': 0,
        'description': 'ZTF Object ID'
    },
    {
        'name': 'ra',
        'required': False,
        'group': 1,
        'description': 'Right Ascension'
    },
    {
        'name': 'dec',
        'required': False,
        'group': 1,
        'description': 'Declination'
    },
    {
        'name': 'radius',
        'required': False,
        'group': 1,
        'description': 'Conesearch radius in arcsec. Maximum is 60 arcseconds.'
    },
    {
        'name': 'startdate',
        'required': False,
        'group': 2,
        'description': 'Starting date in UTC'
    },
    {
        'name': 'window',
        'required': False,
        'group': 2,
        'description': 'Time window in minutes. Maximum is 180 minutes.'
    }
]

args_latest = [
    {
        'name': 'class',
        'required': True,
        'description': 'Fink derived class'
    },
    {
        'name': 'n',
        'required': False,
        'description': 'Last N alerts to transfer. Default is 10, max is 1000.'
    },
    {
        'name': 'columns',
        'required': False,
        'description': 'Data columns to transfer. '
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

    if 'withcutouts' in request.json and request.json['withcutouts'] == 'True':
        pdf['b:cutoutScience_stampData'] = pdf['b:cutoutScience_stampData'].apply(
            lambda x: str(client.repository().get(x))
        )
        pdf['b:cutoutTemplate_stampData'] = pdf['b:cutoutTemplate_stampData'].apply(
            lambda x: str(client.repository().get(x))
        )
        pdf['b:cutoutDifference_stampData'] = pdf['b:cutoutDifference_stampData'].apply(
            lambda x: str(client.repository().get(x))
        )

    if 'output-format' not in request.json or request.json['output-format'] == 'json':
        return pdf.to_json(orient='records')
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

@api_bp.route('/api/v1/explorer', methods=['GET'])
def query_db_arguments():
    """ Obtain information about querying the Fink database
    """
    return jsonify({'args': args_explorer})

@api_bp.route('/api/v1/explorer', methods=['POST'])
def query_db():
    """ Query the Fink database
    """
    # Check the user specifies only one group
    all_groups = [i['group'] for i in args_explorer if i['name'] in request.json]
    if len(np.unique(all_groups)) != 1:
        rep = {
            'status': 'error',
            'text': "You need to set parameters from the same group\n"
        }
        return Response(str(rep), 400)

    # Check the user specifies all parameters within a group
    user_group = np.unique(all_groups)[0]
    required_args = [i['name'] for i in args_explorer if i['group'] == user_group]
    for required_arg in required_args:
        if required_arg not in request.json:
            rep = {
                'status': 'error',
                'text': "A value for `{}` is required for group {}. Use GET to check arguments.\n".format(required_arg, user_group)
            }
            return Response(str(rep), 400)

    # Columns of interest
    colnames = [
        'i:objectId', 'i:ra', 'i:dec', 'i:jd', 'd:cdsxmatch', 'i:ndethist'
    ]

    colnames_added_values = [
        'd:cdsxmatch',
        'd:roid',
        'd:mulens_class_1',
        'd:mulens_class_2',
        'd:snn_snia_vs_nonia',
        'd:snn_sn_vs_all',
        'd:rfscore',
        'i:ndethist',
        'i:drb',
        'i:classtar'
    ]

    # Column name to display
    colnames_to_display = [
        'objectId', 'RA', 'Dec', 'last seen', 'classification', 'ndethist'
    ]

    # Types of columns
    dtypes_ = [
        np.str, np.float, np.float, np.float, np.str, np.int
    ]
    dtypes = {i: j for i, j in zip(colnames, dtypes_)}

    if user_group == 0:
        # objectId search
        to_evaluate = "key:key:{}".format(request.json['objectId'])

        results = client.scan(
            "",
            to_evaluate,
            ",".join(colnames + colnames_added_values),
            0, True, True
        )
    if user_group == 1:
        clientP.setLimit(1000)

        # Interpret user input
        ra, dec = request.json['ra'], request.json['dec']
        radius = request.json['radius']
        if int(radius) > 60:
            rep = {
                'status': 'error',
                'text': "`radius` cannot be bigger than 60 arcseconds.\n"
            }
            return Response(str(rep), 400)
        if 'h' in ra:
            coord = SkyCoord(ra, dec, frame='icrs')
        elif ':' in ra or ' ' in ra:
            coord = SkyCoord(ra, dec, frame='icrs', unit=(u.hourangle, u.deg))
        else:
            coord = SkyCoord(ra, dec, frame='icrs', unit='deg')

        ra = coord.ra.deg
        dec = coord.dec.deg
        radius = float(radius) / 3600.

        # angle to vec conversion
        vec = hp.ang2vec(np.pi / 2.0 - np.pi / 180.0 * dec, np.pi / 180.0 * ra)

        # list of neighbour pixels
        pixs = hp.query_disc(131072, vec, np.pi / 180 * radius, inclusive=True)

        # Send request
        to_evaluate = ",".join(['key:key:{}'.format(i) for i in pixs])
        results = clientP.scan(
            "",
            to_evaluate,
            ",".join(colnames + colnames_added_values),
            0, True, True
        )
    elif user_group == 2:
        if int(request.json['window']) > 180:
            rep = {
                'status': 'error',
                'text': "`window` cannot be bigger than 180 minutes.\n"
            }
            return Response(str(rep), 400)
        # Time to jd
        jd_start = Time(request.json['startdate']).jd
        jd_end = jd_start + TimeDelta(int(request.json['window']) * 60, format='sec').jd

        # Send the request. RangeScan.
        clientT.setRangeScan(True)
        to_evaluate = "key:key:{},key:key:{}".format(jd_start, jd_end)
        results = clientT.scan(
            "",
            to_evaluate,
            ",".join(colnames + colnames_added_values),
            0, True, True
        )

    # reset the limit in case it has been changed above
    client.setLimit(nlimit)

    if results.isEmpty():
        return pd.DataFrame({}).to_json()

    # Loop over results and construct the dataframe
    pdfs = pd.DataFrame.from_dict(results, orient='index')

    # Fink final classification
    classifications = extract_fink_classification(
        pdfs['d:cdsxmatch'],
        pdfs['d:roid'],
        pdfs['d:mulens_class_1'],
        pdfs['d:mulens_class_2'],
        pdfs['d:snn_snia_vs_nonia'],
        pdfs['d:snn_sn_vs_all'],
        pdfs['d:rfscore'],
        pdfs['i:ndethist'],
        pdfs['i:drb'],
        pdfs['i:classtar']
    )

    # inplace (booo)
    pdfs['d:cdsxmatch'] = classifications

    pdfs = pdfs[colnames]

    # Column values are string by default - convert them
    pdfs = pdfs.astype(dtype=dtypes)

    # Rename columns
    pdfs = pdfs.rename(
        columns={i: j for i, j in zip(colnames, colnames_to_display)}
    )

    # Display only the last alert
    pdfs = pdfs.loc[pdfs.groupby('objectId')['last seen'].idxmax()]
    pdfs['last seen'] = pdfs['last seen'].apply(convert_jd)

    return pdfs.to_json(orient='records')

@api_bp.route('/api/v1/latests', methods=['GET'])
def latest_objects_arguments():
    """ Obtain information about latest objects
    """
    return jsonify({'args': args_latest})

@api_bp.route('/api/v1/latests', methods=['POST'])
def latest_objects():
    """ Get latest objects by class
    """
    # Check all required args are here
    required_args = [i['name'] for i in args_latest if i['required'] is True]
    for required_arg in required_args:
        if required_arg not in request.json:
            rep = {
                'status': 'error',
                'text': "A value for `{}` is required. Use GET to check arguments.\n".format(required_arg)
            }
            return Response(str(rep), 400)

    if 'n' not in request.json:
        nalerts = 10
    else:
        nalerts = int(request.json['n'])

    # Columns of interest
    colnames = [
        'i:objectId', 'i:ra', 'i:dec', 'i:jd', 'd:cdsxmatch', 'i:ndethist'
    ]

    colnames_added_values = [
        'd:cdsxmatch',
        'd:roid',
        'd:mulens_class_1',
        'd:mulens_class_2',
        'd:snn_snia_vs_nonia',
        'd:snn_sn_vs_all',
        'd:rfscore',
        'i:ndethist',
        'i:drb',
        'i:classtar'
    ]

    # Column name to display
    colnames_to_display = [
        'objectId', 'RA', 'Dec', 'last seen', 'classification', 'ndethist'
    ]

    # Types of columns
    dtypes_ = [
        np.str, np.float, np.float, np.float, np.str, np.int
    ]
    dtypes = {i: j for i, j in zip(colnames, dtypes_)}

    # Search for latest alerts for a specific class
    if request.json['class'] != 'allclasses':
        clientS.setLimit(nalerts)
        clientS.setRangeScan(True)
        clientS.setReversed(True)

        # start of the Fink operations
        jd_start = Time('2019-11-01 00:00:00').jd
        jd_stop = Time.now().jd

        results = clientS.scan(
            "",
            "key:key:{}_{},key:key:{}_{}".format(
                request.json['class'],
                jd_start,
                request.json['class'],
                jd_stop
            ),
            ",".join(colnames + colnames_added_values), 0, False, False
        )
    elif request.json['class'] == 'allclasses':
        clientT.setLimit(nalerts)
        clientT.setRangeScan(True)
        clientT.setReversed(True)

        # start of the Fink operations
        jd_start = Time('2019-11-01 00:00:00').jd
        jd_stop = Time.now().jd

        to_evaluate = "key:key:{},key:key:{}".format(jd_start, jd_stop)
        results = clientT.scan(
            "",
            to_evaluate,
            ",".join(colnames + colnames_added_values),
            0, True, True
        )

    if results.isEmpty():
        return pd.DataFrame({}).to_json()

    # Loop over results and construct the dataframe
    pdfs = pd.DataFrame.from_dict(results, orient='index')

    # Fink final classification
    classifications = extract_fink_classification(
        pdfs['d:cdsxmatch'],
        pdfs['d:roid'],
        pdfs['d:mulens_class_1'],
        pdfs['d:mulens_class_2'],
        pdfs['d:snn_snia_vs_nonia'],
        pdfs['d:snn_sn_vs_all'],
        pdfs['d:rfscore'],
        pdfs['i:ndethist'],
        pdfs['i:drb'],
        pdfs['i:classtar']
    )

    # inplace (booo)
    pdfs['d:cdsxmatch'] = classifications

    pdfs = pdfs[colnames]

    # Column values are string by default - convert them
    pdfs = pdfs.astype(dtype=dtypes)

    # Rename columns
    pdfs = pdfs.rename(
        columns={i: j for i, j in zip(colnames, colnames_to_display)}
    )

    # Display only the last alert
    pdfs = pdfs.loc[pdfs.groupby('objectId')['last seen'].idxmax()]
    pdfs['last seen'] = pdfs['last seen'].apply(convert_jd)

    if 'output-format' not in request.json or request.json['output-format'] == 'json':
        return pdf.to_json(orient='records')
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

@api_bp.route('/api/v1/classes', methods=['GET'])
def class_arguments():
    """ Obtain all Fink derived class
    """
    # SIMBAD
    simbad_types = pd.read_csv('assets/simbad_types.csv', header=None)[0].values
    simbad_types = sorted(simbad_types, key=lambda s: s.lower())

    # Fink science modules
    fink_types = pd.read_csv('assets/fink_types.csv', header=None)[0].values
    fink_types = sorted(fink_types, key=lambda s: s.lower())

    types = {
        'Fink classifiers': fink_types,
        'Cross-match with SIMBAD': simbad_types
    }

    return jsonify({'classnames': types})

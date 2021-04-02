# Copyright 2020-2021 AstroLab Software
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
from flask import send_file

from PIL import Image as im
from matplotlib import cm

from app import client, clientP, clientT, clientS, clientSSO, clientTNS, nlimit
from apps.utils import format_hbase_output
from apps.utils import extract_cutouts
from apps.plotting import legacy_normalizer, convolve, sigmoid_normalizer

import io
import requests

import healpy as hp
import pandas as pd
import numpy as np

import astropy.units as u
from astropy.time import Time, TimeDelta
from astropy.coordinates import SkyCoord
from astropy.table import Table

from flask import Blueprint

APIURL = "http://134.158.75.151:24000"

api_bp = Blueprint('', __name__)

api_doc_summary = """
# Fink API

## Summary of services

| HTTP Method | URI | Action | Availability |
|-------------|-----|--------|--------------|
| POST/GET | {}/api/v1/objects| Retrieve single object data from the Fink database | &#x2611;&#xFE0F; |
| POST/GET | {}/api/v1/explorer | Query the Fink alert database | &#x2611;&#xFE0F; |
| POST/GET | {}/api/v1/latests | Get latest alerts by class | &#x2611;&#xFE0F; |
| POST/GET | {}/api/v1/sso | Get Solar System Object data | &#x2611;&#xFE0F; |
| POST/GET | {}/api/v1/cutouts | Retrieve cutout data from the Fink database| &#x2611;&#xFE0F; |
| POST/GET | {}/api/v1/xmatch | Cross-match user-defined catalog with Fink alert data| &#x274C; |
| GET  | {}/api/v1/classes  | Display all Fink derived classification | &#x2611;&#xFE0F; |
| GET  | {}/api/v1/columns  | Display all available alert fields and their type | &#x2611;&#xFE0F; |
""".format(APIURL, APIURL, APIURL, APIURL, APIURL, APIURL, APIURL, APIURL)

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

You can also get a votable using the json output format:

```python
from astropy.table import Table

# get data for ZTF19acnjwgm in JSON format...
r = ...

t = Table(r.json())
```

By default, we transfer all available data fields (original ZTF fields and Fink science module outputs).
But you can also choose to transfer only a subset of the fields:

```python
# select only jd, and magpsf
r = requests.post(
  'http://134.158.75.151:24000/api/v1/objects',
  json={
    'objectId': 'ZTF19acnjwgm',
    'columns': 'i:jd,i:magpsf'
  }
)
```

Note that the fields should be comma-separated. Unknown field names are ignored.

Finally, you can also request data from cutouts stored in alerts (science, template and difference).
Simply set `withcutouts` in the json payload (string):

```python
import requests
import pandas as pd
import matplotlib.pyplot as plt

# transfer cutout data
r = requests.post(
  'http://134.158.75.151:24000/api/v1/objects',
  json={
    'objectId': 'ZTF19acnjwgm',
    'withcutouts': 'True'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)

columns = [
    'b:cutoutScience_stampData',
    'b:cutoutTemplate_stampData',
    'b:cutoutDifference_stampData'
]

for col in columns:
    # 2D array
    data = pdf[col].values[0]

    # do whatever plotting

plt.show()
```

See [here](https://github.com/astrolabsoftware/fink-science-portal/blob/1dea22170449f120d92f404ac20bbb856e1e77fc/apps/plotting.py#L584-L593) how we do in the Science Portal to display cutouts.
Note that you need to flip the array to get the correct orientation on sky (`data[::-1]`).

"""

api_doc_explorer = """
## Query the Fink alert database

This service allows you to search matching objects in the database.
If several alerts from the same object match the query, we group information and
only display the data from the last alert. To get a full history about an object,
you should use the `Retrieve single object data` service instead.

Currently, you cannot query using several conditions.
You must choose among `Search by Object ID` (group 0), `Conesearch` (group 1), or `Search by Date` (group 2).
In a future release, you will be able to combine searches.
The list of arguments for querying the Fink alert database can be found at http://134.158.75.151:24000/api/v1/explorer.

### Search by Object ID

Enter a valid object ID to access its data, e.g. try:

* ZTF19acmdpyr, ZTF19acnjwgm, ZTF17aaaabte, ZTF20abqehqf, ZTF18acuajcr

In a unix shell, you would simply use

```bash
# Get data for ZTF19acnjwgm and save it in a JSON file
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
* 271d23m29.135s, 45d15m16.25s, 5
* 18h05m33.942s, +45d15m16.25s, 5
* 18 05 33.942, +45 15 16.25, 5
* 18:05:33.942, 45:15:16.25, 5

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

api_doc_sso = """
## Retrieve Solar System Object data

The list of arguments for retrieving SSO data can be found at http://134.158.75.151:24000/api/v1/sso.
The numbers or designations are taken from the MPC archive.
When searching for a particular asteroid or comet, it is best to use the IAU number,
as in 4209 for asteroid "4209 Briggs". You can also try for numbered comet (e.g. 10P),
or interstellar object (none so far...). If the number does not yet exist, you can search for designation.
Here are some examples of valid queries:

* Asteroids by number (default)
  * Asteroids (Main Belt): 4209, 1922
  * Asteroids (Hungarians): 18582, 77799
  * Asteroids (Jupiter Trojans): 4501, 1583
  * Asteroids (Mars Crossers): 302530
* Asteroids by designation (if number does not exist yet)
  * 2010JO69, 2017AD19, 2012XK111
* Comets by number (default)
  * 10P, 249P, 124P
* Comets by designation (if number does no exist yet)
  * C/2020V2, C/2020R2

Note for designation, you can also use space (2010 JO69 or C/2020 V2).

In a unix shell, you would simply use

```bash
# Get data for the asteroid 4209 and save it in a CSV file
curl -H "Content-Type: application/json" -X POST -d '{"n_or_d":"4209", "output-format":"csv"}' http://134.158.75.151:24000/api/v1/sso -o 4209.csv
```

In python, you would use

```python
import requests
import pandas as pd

# get data for ZTF19acnjwgm
r = requests.post(
  'http://134.158.75.151:24000/api/v1/sso',
  json={
    'n_or_d': '4209',
    'output-format': 'json'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)
```

Note that for `csv` output, you need to use

```python
# get data for asteroid 4209 in CSV format...
r = ...

pd.read_csv(io.BytesIO(r.content))
```

You can also get a votable using the json output format:

```python
from astropy.table import Table

# get data for asteroid 4209 in JSON format...
r = ...

t = Table(r.json())
```

By default, we transfer all available data fields (original ZTF fields and Fink science module outputs).
But you can also choose to transfer only a subset of the fields:

```python
# select only jd, and magpsf
r = requests.post(
  'http://134.158.75.151:24000/api/v1/sso',
  json={
    'n_or_d': '4209',
    'columns': 'i:jd,i:magpsf'
  }
)
```

Note that the fields should be comma-separated. Unknown field names are ignored.
"""

api_doc_cutout = """
## Retrieve cutout data from the Fink database

The list of arguments for retrieving cutout data can be found at http://134.158.75.151:24000/api/v1/cutouts.

### PNG

In a unix shell, you can retrieve the last cutout of an object by simply using

```bash
curl -H "Content-Type: application/json" \\
    -X POST -d \\
    '{"objectId":"ZTF19acnjwgm", "kind":"Science"}' \\
    http://134.158.75.151:24000/api/v1/cutouts -o cutoutScience.png
```

This will retrieve the `Science` image and save it on `cutoutScience.png`.
In Python, the equivalent script would be:

```python
import io
import requests
from PIL import Image as im

# get data for ZTF19acnjwgm
r = requests.post(
    'http://134.158.75.151:24000/api/v1/cutouts',
    json={
        'objectId': 'ZTF19acnjwgm',
        'kind': 'Science',
    }
)

image = im.open(io.BytesIO(r.content))
image.save('cutoutScience.png')
```

Note you can choose between the `Science`, `Template`, or `Difference` images.
You can also customise the image treatment by

```python
import io
import requests
from PIL import Image as im

# get data for ZTF19acnjwgm
r = requests.post(
    'http://134.158.75.151:24000/api/v1/cutouts',
    json={
        'objectId': 'ZTF19acnjwgm',
        'kind': 'Science', # Science, Template, Difference
        'stretch': 'sigmoid', # sigmoid[default], linear, sqrt, power, log, asinh
        'colormap': 'viridis', # Valid matplotlib colormap name (see matplotlib.cm). Default is grayscale.
        'pmin': 0.5, # The percentile value used to determine the pixel value of minimum cut level. Default is 0.5. No effect for sigmoid.
        'pmax': 99.5, # The percentile value used to determine the pixel value of maximum cut level. Default is 99.5. No effect for sigmoid.
        'convolution_kernel': 'gauss' # Convolve the image with a kernel (gauss or box). Default is None (not specified).
    }
)

image = im.open(io.BytesIO(r.content))
image.save('mysupercutout.png')
```

By default, you will retrieve the cutout of the last alert emitted for the object `objectId`.
You can also access cutouts of other alerts from this object by specifying their candidate ID:

```python
import io
import requests
import pandas as pd
from PIL import Image as im

# Get all candidate ID with JD for ZTF19acnjwgm
r = requests.post(
    'http://134.158.75.151:24000/api/v1/objects',
    json={
        'objectId': 'ZTF19acnjwgm',
        'columns': 'i:candid,i:jd'
    }
)

pdf_candid = pd.read_json(r.content)
# Get the first alert
first_alert = pdf_candid['i:candid'].values[-1]

# get data for ZTF19acnjwgm
r = requests.post(
    'http://134.158.75.151:24000/api/v1/cutouts',
    json={
        'objectId': 'ZTF19acnjwgm',
        'kind': 'Science',
        'candid': first_alert
    }
)

image = im.open(io.BytesIO(r.content))
image.save('mysupercutout_firstalert.png')
```

### FITS

You can also retrieve the original FITS file stored in the alert:

```bash
curl -H "Content-Type: application/json" \\
    -X POST -d \\
    '{"objectId":"ZTF19acnjwgm", "kind":"Science", "output-format": "FITS"}' \\
    http://134.158.75.151:24000/api/v1/cutouts -o cutoutScience.fits
```

or equivalently in Python:

```python
import io
from astropy.io import fits
import requests
import pandas as pd

# get data for ZTF19acnjwgm
r = requests.post(
    'http://134.158.75.151:24000/api/v1/cutouts',
    json={
        'objectId': 'ZTF19acnjwgm',
        'kind': 'Science',
        'output-format': 'FITS'
    }
)

data = fits.open(io.BytesIO(r.content))
data.writeto('cutoutScience.fits')
```

### Numpy array

You can also retrieve only the data block stored in the alert:

```python
import requests
import pandas as pd

# get data for ZTF19acnjwgm
r = requests.post(
    'http://134.158.75.151:24000/api/v1/cutouts',
    json={
        'objectId': 'ZTF19acnjwgm',
        'kind': 'Science',
        'output-format': 'array'
    }
)

pdf = pd.read_json(r.content)
array = pdf['b:cutoutScience_stampData'].values[0]
```

"""

layout = html.Div(
    [
        html.Br(),
        html.Br(),
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
                        dbc.Tab(
                            [
                                dbc.Card(
                                    dbc.CardBody(
                                        dcc.Markdown(api_doc_sso)
                                    ), style={
                                        'backgroundColor': 'rgb(248, 248, 248, .7)'
                                    }
                                ),
                            ], label="Get Solar System Objects"
                        ),
                        dbc.Tab(
                            [
                                dbc.Card(
                                    dbc.CardBody(
                                        dcc.Markdown(api_doc_cutout)
                                    ), style={
                                        'backgroundColor': 'rgb(248, 248, 248, .7)'
                                    }
                                ),
                            ], label="Get Image data"
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
        'description': 'If True, retrieve also uncompressed FITS cutout data (2D array).'
    },
    {
        'name': 'columns',
        'required': False,
        'description': 'Comma-separated data columns to transfer. Default is all columns. See {}/api/v1/columns for more information.'.format(APIURL)
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
    },
    {
        'name': 'output-format',
        'required': False,
        'group': None,
        'description': 'Output format among json[default], csv, parquet'
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
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet'
    }
]

args_sso = [
    {
        'name': 'n_or_d',
        'required': False,
        'description': 'IAU number of the object, or designation of the object IF the number does not exist yet. Example for numbers: 4209 (asteroid) or 10P (comet). Example for designations: 2010JO69 (asteroid) or C/2020V2 (comet).'
    },
    {
        'name': 'columns',
        'required': False,
        'description': 'Comma-separated data columns to transfer. Default is all columns. See {}/api/v1/columns for more information.'.format(APIURL)
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet'
    }
]

args_cutouts = [
    {
        'name': 'objectId',
        'required': True,
        'description': 'ZTF Object ID'
    },
    {
        'name': 'kind',
        'required': True,
        'description': 'Science, Template, or Difference'
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'PNG[default], FITS, array'
    },
    {
        'name': 'candid',
        'required': False,
        'description': 'Candidate ID of the alert belonging to the object with `objectId`. If not filled, the cutouts of the latest alert is returned'
    },
    {
        'name': 'stretch',
        'required': False,
        'description': 'Stretch function to be applied. Available: sigmoid[default], linear, sqrt, power, log, asinh.'
    },
    {
        'name': 'colormap',
        'required': False,
        'description': 'Valid matplotlib colormap name (see matplotlib.cm). Default is grayscale.'
    },
    {
        'name': 'pmin',
        'required': False,
        'description': 'The percentile value used to determine the pixel value of minimum cut level. Default is 0.5. No effect for sigmoid.'
    },
    {
        'name': 'pmax',
        'required': False,
        'description': 'The percentile value used to determine the pixel value of maximum cut level. Default is 99.5. No effect for sigmoid.'
    },
    {
        'name': 'convolution_kernel',
        'required': False,
        'description': 'Convolve the image with a kernel (gauss or box). Default is None (not specified).'
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
    if 'output-format' in request.json:
        output_format = request.json['output-format']
    else:
        output_format = 'json'

    # Check all required args are here
    required_args = [i['name'] for i in args_objects if i['required'] is True]
    for required_arg in required_args:
        if required_arg not in request.json:
            rep = {
                'status': 'error',
                'text': "A value for `{}` is required. Use GET to check arguments.\n".format(required_arg)
            }
            return Response(str(rep), 400)

    if 'columns' in request.json:
        cols = request.json['columns'].replace(" ", "")
        truncated = True
    else:
        cols = '*'
        truncated = False
    to_evaluate = "key:key:{}".format(request.json['objectId'])

    # We do not want to perform full scan if the objectid is a wildcard
    client.setLimit(1000)

    results = client.scan(
        "",
        to_evaluate,
        cols,
        0, True, True
    )

    schema_client = client.schema()

    # reset the limit in case it has been changed above
    client.setLimit(nlimit)

    pdf = format_hbase_output(
        results, schema_client, group_alerts=False, truncated=truncated
    )

    if 'withcutouts' in request.json and request.json['withcutouts'] == 'True':
        pdf = extract_cutouts(pdf, client)

    if output_format == 'json':
        return pdf.to_json(orient='records')
    elif output_format == 'csv':
        return pdf.to_csv(index=False)
    elif output_format == 'parquet':
        f = io.BytesIO()
        pdf.to_parquet(f)
        f.seek(0)
        return f.read()

    rep = {
        'status': 'error',
        'text': "Output format `{}` is not supported. Choose among json, csv, or parquet\n".format(output_format)
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
    if 'output-format' in request.json:
        output_format = request.json['output-format']
    else:
        output_format = 'json'

    # Check the user specifies only one group
    all_groups = [i['group'] for i in args_explorer if i['group'] is not None and i['name'] in request.json]
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

    if user_group == 0:
        # objectId search
        to_evaluate = "key:key:{}".format(request.json['objectId'])

        # Avoid a full scan
        client.setLimit(1000)

        results = client.scan(
            "",
            to_evaluate,
            "*",
            0, True, True
        )
        # reset the limit in case it has been changed above
        client.setLimit(nlimit)

        schema_client = client.schema()
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
            "*",
            0, True, True
        )
        schema_client = clientP.schema()
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
            "*",
            0, True, True
        )
        schema_client = clientT.schema()

    # reset the limit in case it has been changed above
    client.setLimit(nlimit)

    pdfs = format_hbase_output(results, schema_client, group_alerts=True)

    if output_format == 'json':
        return pdfs.to_json(orient='records')
    elif output_format == 'csv':
        return pdfs.to_csv(index=False)
    elif output_format == 'parquet':
        f = io.BytesIO()
        pdfs.to_parquet(f)
        f.seek(0)
        return f.read()

    rep = {
        'status': 'error',
        'text': "Output format `{}` is not supported. Choose among json, csv, or parquet\n".format(request.json['output-format'])
    }
    return Response(str(rep), 400)

@api_bp.route('/api/v1/latests', methods=['GET'])
def latest_objects_arguments():
    """ Obtain information about latest objects
    """
    return jsonify({'args': args_latest})

@api_bp.route('/api/v1/latests', methods=['POST'])
def latest_objects():
    """ Get latest objects by class
    """
    if 'output-format' in request.json:
        output_format = request.json['output-format']
    else:
        output_format = 'json'

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

    # Search for latest alerts for a specific class
    tns_classes = pd.read_csv('assets/tns_types.csv', header=None)[0].values
    is_tns = request.json['class'].startswith('TNS|') and (request.json['class'].split('|')[1] in tns_classes)
    if is_tns:
        classname = request.json['class'].split('|')[1]
        clientTNS.setLimit(nalerts)
        clientTNS.setRangeScan(True)
        clientTNS.setReversed(True)

        # start of the Fink operations
        jd_start = Time('2019-11-01 00:00:00').jd
        jd_stop = Time.now().jd

        results = clientTNS.scan(
            "",
            "key:key:{}_{},key:key:{}_{}".format(
                classname,
                jd_start,
                classname,
                jd_stop
            ),
            "*", 0, True, True
        )
        schema_client = clientTNS.schema()
        group_alerts = True
    elif request.json['class'] != 'allclasses':
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
            "*", 0, False, False
        )
        schema_client = clientS.schema()
        group_alerts = False
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
            "*",
            0, True, True
        )
        schema_client = clientT.schema()
        group_alerts = False

    # We want to return alerts
    pdfs = format_hbase_output(results, schema_client, group_alerts=group_alerts)

    if is_tns:
        pdfs['key:key'] = pdfs['key:key'].apply(lambda x: x.split('_')[0])
        pdf.rename(columns={'key:key': 'TNS'}, inplace=True)

    if output_format == 'json':
        return pdfs.to_json(orient='records')
    elif output_format == 'csv':
        return pdfs.to_csv(index=False)
    elif output_format == 'parquet':
        f = io.BytesIO()
        pdfs.to_parquet(f)
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
    # TNS
    tns_types = pd.read_csv('assets/tns_types.csv', header=None)[0].values
    tns_types = sorted(tns_types, key=lambda s: s.lower())

    # SIMBAD
    simbad_types = pd.read_csv('assets/simbad_types.csv', header=None)[0].values
    simbad_types = sorted(simbad_types, key=lambda s: s.lower())

    # Fink science modules
    fink_types = pd.read_csv('assets/fink_types.csv', header=None)[0].values
    fink_types = sorted(fink_types, key=lambda s: s.lower())

    types = {
        'Fink classifiers': fink_types,
        'TNS classified data': tns_types,
        'Cross-match with SIMBAD (see http://simbad.u-strasbg.fr/simbad/sim-display?data=otypes)': simbad_types
    }

    return jsonify({'classnames': types})

@api_bp.route('/api/v1/columns', methods=['GET'])
def columns_arguments():
    """ Obtain all alert fields available and their type
    """
    # ZTF candidate fields
    r = requests.get('https://raw.githubusercontent.com/ZwickyTransientFacility/ztf-avro-alert/master/schema/candidate.avsc')
    tmp = pd.DataFrame.from_dict(r.json())
    ztf_candidate = tmp['fields'].apply(pd.Series)
    ztf_candidate = ztf_candidate.append(
        {
            "name": "schemavsn",
            "type": "string",
            "doc": "schema version used"
        }, ignore_index=True
    )
    ztf_candidate = ztf_candidate.append(
        {
            "name": "publisher",
            "type": "string",
            "doc": "origin of alert packet"
        }, ignore_index=True
    )
    ztf_candidate = ztf_candidate.append(
        {
            "name": "objectId",
            "type": "string",
            "doc": "object identifier or name"
        }, ignore_index=True
    )

    ztf_cutouts = pd.DataFrame.from_dict(
        [
            {
                "name": "cutoutScience_stampData",
                "type": "array",
                "doc": "2D array from the Science cutout FITS"
            }
        ]
    )
    ztf_cutouts = ztf_cutouts.append(
        {
            "name": "cutoutTemplate_stampData",
            "type": "array",
            "doc": "2D array from the Template cutout FITS"
        }, ignore_index=True
    )
    ztf_cutouts = ztf_cutouts.append(
        {
            "name": "cutoutDifference_stampData",
            "type": "array",
            "doc": "2D array from the Difference cutout FITS"
        }, ignore_index=True
    )

    # Science modules
    fink_science = pd.DataFrame(
        [
            {'name': 'cdsxmatch', 'type': 'string', 'doc': 'SIMBAD closest counterpart, based on position. See http://134.158.75.151:24000/api/v1/classes'},
            {'name': 'mulens_class_1', 'type': ['string', 'null'], 'doc': 'Predicted class of an alert in band g using LIA (among microlensing ML, variable star VS, cataclysmic event CV, and constant event CONSTANT). Nothing if not classified.'},
            {'name': 'mulens_class_2', 'type': ['string', 'null'], 'doc': 'Predicted class of an alert in band r using LIA (among microlensing ML, variable star VS, cataclysmic event CV, and constant event CONSTANT). Nothing if not classified.'},
            {'name': 'rfscore', 'type': 'double', 'doc': 'Probability of an alert to be a SNe Ia using a Random Forest Classifier (binary classification). Higher is better.'},
            {'name': 'knscore', 'type': 'double', 'doc': 'Probability of an alert to be a Kilonova using a PCA & Random Forest Classifier (binary classification). Higher is better.'},
            {'name': 'roid', 'type': 'int', 'doc': 'Determine if the alert is a potential Solar System object (experimental). See https://github.com/astrolabsoftware/fink-science/blob/db57c40cd9be10502e34c5117c6bf3793eb34718/fink_science/asteroids/processor.py#L26'},
            {'name': 'snn_sn_vs_all', 'type': 'double', 'doc': 'The probability of an alert to be a SNe vs. anything else (variable stars and other categories in the training) using SuperNNova'},
            {'name': 'snn_snia_vs_nonia', 'type': 'double', 'doc': 'The probability of an alert to be a SN Ia vs. core-collapse SNe using SuperNNova'},
        ]
    )

    # Science modules
    fink_derived = pd.DataFrame(
        [
            {'name': 'classification', 'type': 'string', 'doc': 'Fink inferred classification. See http://134.158.75.151:24000/api/v1/classes'},
            {'name': 'r-g', 'type': 'double', 'doc': 'Last r-g measurement for this object.'},
            {'name': 'rate(r-g)', 'type': 'double', 'doc': 'r-g rate in mag/day (between last and first available r-g measurements).'},
            {'name': 'lastdate', 'type': 'string', 'doc': 'Datetime for the alert (from the i:jd field).'},
        ]
    )

    # Sort by name
    ztf_candidate = ztf_candidate.sort_values('name')
    fink_science = fink_science.sort_values('name')
    fink_derived = fink_derived.sort_values('name')

    types = {
        'ZTF original fields (i:)': {i: {'type': j, 'doc': k} for i, j, k in zip(ztf_candidate.name, ztf_candidate.type, ztf_candidate.doc)},
        'ZTF original cutouts (b:)': {i: {'type': j, 'doc': k} for i, j, k in zip(ztf_cutouts.name, ztf_cutouts.type, ztf_cutouts.doc)},
        'Fink science module outputs (d:)': {i: {'type': j, 'doc': k} for i, j, k in zip(fink_science.name, fink_science.type, fink_science.doc)},
        'Fink added values (v:)': {i: {'type': j, 'doc': k} for i, j, k in zip(fink_derived.name, fink_derived.type, fink_derived.doc)}
    }

    return jsonify({'fields': types})

@api_bp.route('/api/v1/sso', methods=['GET'])
def return_sso_arguments():
    """ Obtain information about retrieving Solar System Object data
    """
    return jsonify({'args': args_sso})

@api_bp.route('/api/v1/sso', methods=['POST'])
def return_sso():
    """ Retrieve Solar System Object data from the Fink database
    """
    if 'output-format' in request.json:
        output_format = request.json['output-format']
    else:
        output_format = 'json'

    if 'columns' in request.json:
        cols = request.json['columns'].replace(" ", "")
        truncated = True
    else:
        cols = '*'
        truncated = False

    payload = request.json['n_or_d'].replace(' ', '')

    # Note the trailing _ to avoid mixing e.g. 91 and 915 in the same query
    to_evaluate = "key:key:{}_".format(payload)

    # We do not want to perform full scan if the objectid is a wildcard
    clientSSO.setLimit(1000)

    results = clientSSO.scan(
        "",
        to_evaluate,
        cols,
        0, True, True
    )

    schema_client = clientSSO.schema()

    # reset the limit in case it has been changed above
    clientSSO.setLimit(nlimit)

    pdf = format_hbase_output(
        results, schema_client, group_alerts=False, truncated=truncated
    )

    if output_format == 'json':
        return pdf.to_json(orient='records')
    elif output_format == 'csv':
        return pdf.to_csv(index=False)
    elif output_format == 'parquet':
        f = io.BytesIO()
        pdf.to_parquet(f)
        f.seek(0)
        return f.read()

    rep = {
        'status': 'error',
        'text': "Output format `{}` is not supported. Choose among json, csv, or parquet\n".format(output_format)
    }
    return Response(str(rep), 400)

@api_bp.route('/api/v1/cutouts', methods=['GET'])
def cutouts_arguments():
    """ Obtain information about cutouts service
    """
    return jsonify({'args': args_cutouts})

@api_bp.route('/api/v1/cutouts', methods=['POST'])
def return_cutouts():
    """ Retrieve cutout data from the Fink database
    """
    assert request.json['kind'] in ['Science', 'Template', 'Difference']

    if 'output-format' in request.json:
        output_format = request.json['output-format']
    else:
        output_format = 'PNG'

    # default stretch is sigmoid
    if 'stretch' in request.json:
        stretch = request.json['stretch']
    else:
        stretch = 'sigmoid'

    # default name based on parameters
    filename = '{}_{}'.format(
        request.json['objectId'],
        request.json['kind']
    )

    if output_format == 'PNG':
        filename = filename + '.png'
    elif output_format == 'JPEG':
        filename = filename + '.jpg'
    elif output_format == 'FITS':
        filename = filename + '.fits'

    # Query the Database (object query)
    results = client.scan(
        "",
        "key:key:{}".format(request.json['objectId']),
        "b:cutout{}_stampData,i:jd,i:candid".format(request.json['kind']),
        0, True, True
    )
    truncated = True

    # Format the results
    schema_client = client.schema()
    pdf = format_hbase_output(
        results, schema_client, group_alerts=False, truncated=truncated
    )

    # Extract only the alert of interest
    if 'candid' in request.json:
        pdf = pdf[pdf['i:candid'].astype(str) == str(request.json['candid'])]
    else:
        # pdf has been sorted in `format_hbase_output`
        pdf = pdf.iloc[0:1]

    if pdf.empty:
        return send_file(
            io.BytesIO(),
            mimetype='image/png',
            as_attachment=True,
            attachment_filename=filename
        )
    # Extract cutouts
    if output_format == 'FITS':
        pdf = extract_cutouts(
            pdf,
            client,
            col='b:cutout{}_stampData'.format(request.json['kind']),
            return_type='FITS'
        )
    else:
        pdf = extract_cutouts(
            pdf,
            client,
            col='b:cutout{}_stampData'.format(request.json['kind']),
            return_type='array'
        )

    array = pdf['b:cutout{}_stampData'.format(request.json['kind'])].values[0]

    # send the FITS file
    if output_format == 'FITS':
        return send_file(
            array,
            mimetype='application/octet-stream',
            as_attachment=True,
            attachment_filename=filename
        )
    # send the array
    elif output_format == 'array':
        return pdf[['b:cutout{}_stampData'.format(request.json['kind'])]].to_json(orient='records')

    if stretch == 'sigmoid':
        array = sigmoid_normalizer(array, 0, 1)
    else:
        pmin = 0.5
        if 'pmin' in request.json:
            pmin = float(request.json['pmin'])
        pmax = 99.5
        if 'pmax' in request.json:
            pmax = float(request.json['pmax'])
        array = legacy_normalizer(array, stretch=stretch, pmin=pmin, pmax=pmax)

    if 'convolution_kernel' in request.json:
        assert request.json['convolution_kernel'] in ['gauss', 'box']
        array = convolve(array, smooth=1, kernel=request.json['convolution_kernel'])

    # colormap
    if "colormap" in request.json:
        colormap = getattr(cm, request.json['colormap'])
    else:
        colormap = lambda x: x
    array = np.uint8(colormap(array) * 255)

    # Convert to PNG
    data = im.fromarray(array)
    datab = io.BytesIO()
    data.save(datab, format='PNG')
    datab.seek(0)
    return send_file(
        datab,
        mimetype='image/png',
        as_attachment=True,
        attachment_filename=filename)

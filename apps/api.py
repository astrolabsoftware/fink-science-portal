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

from app import client
from app import clientP128, clientP4096, clientP131072
from app import clientT, clientS
from app import clientSSO, clientTNS
from app import clientU, clientUV, nlimit
from app import clientStats
from app import APIURL
from apps.utils import format_hbase_output
from apps.utils import extract_cutouts
from apps.utils import get_superpixels
from apps.plotting import legacy_normalizer, convolve, sigmoid_normalizer
from apps.statistics import dic_names

import io
import requests
import java
import gzip

import healpy as hp
import pandas as pd
import numpy as np

import astropy.units as u
from astropy.time import Time, TimeDelta
from astropy.coordinates import SkyCoord
from astropy.table import Table
from astropy.io import fits

from flask import Blueprint

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
| POST/GET | {}/api/v1/xmatch | Cross-match user-defined catalog with Fink alert data| &#x2611;&#xFE0F; |
| POST/GET | {}/api/v1/bayestar | Cross-match LIGO/Virgo sky map with Fink alert data| &#x2611;&#xFE0F; |
| POST/GET | {}/api/v1/statistics | Statistics concerning Fink alert data| &#x2611;&#xFE0F; |
| GET  | {}/api/v1/classes  | Display all Fink derived classification | &#x2611;&#xFE0F; |
| GET  | {}/api/v1/columns  | Display all available alert fields and their type | &#x2611;&#xFE0F; |
""".format(APIURL, APIURL, APIURL, APIURL, APIURL, APIURL, APIURL, APIURL, APIURL, APIURL)

api_doc_object = """
## Retrieve single object data

The list of arguments for retrieving object data can be found at https://fink-portal.org/api/v1/objects.

In a unix shell, you would simply use

```bash
# Get data for ZTF21aaxtctv and save it in a CSV file
curl -H "Content-Type: application/json" -X POST -d '{"objectId":"ZTF21aaxtctv", "output-format":"csv"}' https://fink-portal.org/api/v1/objects -o ZTF21aaxtctv.csv
```

In python, you would use

```python
import requests
import pandas as pd

# get data for ZTF21aaxtctv
r = requests.post(
  'https://fink-portal.org/api/v1/objects',
  json={
    'objectId': 'ZTF21aaxtctv',
    'output-format': 'json'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)
```

Note that for `csv` output, you need to use

```python
# get data for ZTF21aaxtctv in CSV format...
r = ...

pd.read_csv(io.BytesIO(r.content))
```

You can also get a votable using the json output format:

```python
from astropy.table import Table

# get data for ZTF21aaxtctv in JSON format...
r = ...

t = Table(r.json())
```

By default, we transfer all available data fields (original ZTF fields and Fink science module outputs).
But you can also choose to transfer only a subset of the fields:

```python
# select only jd, and magpsf
r = requests.post(
  'https://fink-portal.org/api/v1/objects',
  json={
    'objectId': 'ZTF21aaxtctv',
    'columns': 'i:jd,i:magpsf'
  }
)
```

Note that the fields should be comma-separated. Unknown field names are ignored.

### Upper limits and bad quality data

You can also retrieve upper limits and bad quality data (as defined by Fink quality cuts)
alongside valid measurements. For this you would use `withupperlim` (see usage below).
Note that the returned data will contained a new column, `d:tag`, to easily check data type:
`valid` (valid alert measurements), `upperlim` (upper limits), `badquality` (alert measurements that did not pass quality cuts).
Here is an example that query the data, and plot it:

```python
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
sns.set_context('talk')

# get data for ZTF21aaxtctv
r = requests.post(
  'https://fink-portal.org/api/v1/objects',
  json={
    'objectId': 'ZTF21aaxtctv',
    'withupperlim': 'True'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)

fig = plt.figure(figsize=(15, 6))

colordic = {1: 'C0', 2: 'C1'}

for filt in np.unique(pdf['i:fid']):
    maskFilt = pdf['i:fid'] == filt

    # The column `d:tag` is used to check data type
    maskValid = pdf['d:tag'] == 'valid'
    plt.errorbar(
        pdf[maskValid & maskFilt]['i:jd'].apply(lambda x: x - 2400000.5),
        pdf[maskValid & maskFilt]['i:magpsf'],
        pdf[maskValid & maskFilt]['i:sigmapsf'],
        ls = '', marker='o', color=colordic[filt]
    )

    maskUpper = pdf['d:tag'] == 'upperlim'
    plt.plot(
        pdf[maskUpper & maskFilt]['i:jd'].apply(lambda x: x - 2400000.5),
        pdf[maskUpper & maskFilt]['i:diffmaglim'],
        ls='', marker='^', color=colordic[filt], markerfacecolor='none'
    )

    maskBadquality = pdf['d:tag'] == 'badquality'
    plt.errorbar(
        pdf[maskBadquality & maskFilt]['i:jd'].apply(lambda x: x - 2400000.5),
        pdf[maskBadquality & maskFilt]['i:magpsf'],
        pdf[maskBadquality & maskFilt]['i:sigmapsf'],
        ls='', marker='v', color=colordic[filt]
    )

plt.gca().invert_yaxis()
plt.xlabel('Modified Julian Date')
plt.ylabel('Magnitude')
plt.show()
```

![sn_example](https://user-images.githubusercontent.com/20426972/113519225-2ba29480-958b-11eb-9452-15e84f0e5efc.png)

### Cutouts

Finally, you can also request data from cutouts stored in alerts (science, template and difference).
Simply set `withcutouts` in the json payload (string):

```python
import requests
import pandas as pd
import matplotlib.pyplot as plt

# transfer cutout data
r = requests.post(
  'https://fink-portal.org/api/v1/objects',
  json={
    'objectId': 'ZTF21aaxtctv',
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
The list of arguments for querying the Fink alert database can be found at https://fink-portal.org/api/v1/explorer.

### Search by Object ID

Enter a valid object ID to access its data, e.g. try:

* ZTF21abfmbix, ZTF21aaxtctv, ZTF21abfaohe, ZTF20aanxcpf, ZTF17aaaabte, ZTF18aafpcwm, ZTF21abujbqa, ZTF21abuipwb, ZTF18acuajcr

In a unix shell, you would simply use

```bash
# Get data for ZTF21aaxtctv and save it in a JSON file
curl -H "Content-Type: application/json" -X POST -d '{"objectId":"ZTF21aaxtctv"}' https://fink-portal.org/api/v1/explorer -o search_ZTF21aaxtctv.json
```

In python, you would use

```python
import requests
import pandas as pd

# get data for ZTF21aaxtctv
r = requests.post(
  'https://fink-portal.org/api/v1/explorer',
  json={
    'objectId': 'ZTF21aaxtctv',
  }
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)
```

### Conesearch

Perform a conesearch around a position on the sky given by (RA, Dec, radius).
The initializer for RA/Dec is very flexible and supports inputs provided in a number of convenient formats.
The following ways of initializing a conesearch are all equivalent (radius in arcsecond):

* 193.822, 2.89732, 5
* 193d49m18.267s, 2d53m50.35s, 5
* 12h55m17.218s, +02d53m50.35s, 5
* 12 55 17.218, +02 53 50.35, 5
* 12:55:17.218, 02:53:50.35, 5

In a unix shell, you would simply use

```bash
# Get all objects falling within (center, radius) = ((ra, dec), radius)
curl -H "Content-Type: application/json" -X POST -d '{"ra":"193.822", "dec":"2.89732", "radius":"5"}' https://fink-portal.org/api/v1/explorer -o conesearch.json
```

In python, you would use

```python
import requests
import pandas as pd

# Get all objects falling within (center, radius) = ((ra, dec), radius)
r = requests.post(
  'https://fink-portal.org/api/v1/explorer',
  json={
    'ra': '193.822',
    'dec': '2.89732',
    'radius': '5'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)
```

Maximum radius length is 18,000 arcseconds (5 degrees). Note that in case of
several objects matching, the results will be sorted according to the column
`v:separation_degree`, which is the angular separation in degree between
the input (ra, dec) and the objects found.

In addition, you can specify time boundaries:

```python
import requests
import pandas as pd

# Get all objects falling within (center, radius) = ((ra, dec), radius)
# between 2021-06-25 05:59:37.000 (included) and 2021-07-01 05:59:37.000 (excluded)
r = requests.post(
  'https://fink-portal.org/api/v1/explorer',
  json={
    'ra': '193.822',
    'dec': '2.89732',
    'radius': '5',
    'startdate_conesearch': '2021-06-25 05:59:37.000',
    'window_days_conesearch': 7
  }
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)
```

Here is the performance of the service for querying a
single object (database of 1.3TB, about 40 million alerts):

![conesearch](https://user-images.githubusercontent.com/20426972/123047697-e493a500-d3fd-11eb-9f30-216dce9cbf43.png)

_circle marks with dashed lines are results for a full scan search
(~2 years of data, 40 million alerts), while the upper triangles with
dotted lines are results when restraining to 7 days search.
The numbers close to markers show the number of objects returned by the conesearch._

### Search by Date

Choose a starting date and a time window to see all alerts in this period.
Dates are in UTC, and the time window in minutes.
Example of valid search:

* 2021-07-01 05:59:37.000

In a unix shell, you would simply use

```bash
# Get all objects between 2021-07-01 05:59:37.000 and 2021-07-01 06:09:37.000 UTC
curl -H "Content-Type: application/json" -X POST -d '{"startdate":"2021-07-01 05:59:37.000", "window":"10"}' https://fink-portal.org/api/v1/explorer -o datesearch.json
```

In python, you would use

```python
import requests
import pandas as pd

# Get all objects between 2021-07-01 05:59:37.000 and 2021-07-01 06:09:37.000 UTC
r = requests.post(
  'https://fink-portal.org/api/v1/explorer',
  json={
    'startdate': '2021-07-01 05:59:37.000',
    'window': '10'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)
```
"""

api_doc_latests = """
## Get latest alerts by class

The list of arguments for getting latest alerts by class can be found at https://fink-portal.org/api/v1/latests.

The list of Fink class can be found at https://fink-portal.org/api/v1/classes

```bash
# Get list of available class in Fink
curl -H "Content-Type: application/json" -X GET https://fink-portal.org/api/v1/classes -o finkclass.json
```

To get the last 5 candidates of the class `Early SN Ia candidate`, you would simply use in a unix shell:

```bash
# Get latests 5 Early SN Ia candidates
curl -H "Content-Type: application/json" -X POST -d '{"class":"Early SN Ia candidate", "n":"5"}' https://fink-portal.org/api/v1/latests -o latest_five_sn_candidates.json
```

In python, you would use

```python
import requests
import pandas as pd

# Get latests 5 Early SN Ia candidates
r = requests.post(
  'https://fink-portal.org/api/v1/latests',
  json={
    'class': 'Early SN Ia candidate',
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

You can also specify `startdate` and `stopdate` for your search:

```python
import requests
import pandas as pd

# Get all classified SN Ia from TNS between March 1st 2021 and March 5th 2021
r = requests.post(
  'https://fink-portal.org/api/v1/latests',
  json={
    'class': '(TNS) SN Ia',
    'n': '100',
    'startdate': '2021-03-01',
    'stopdate': '2021-03-05'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)
```
There is no limit of time, but you will be limited by the
number of alerts retrieve on the server side `n` (current max is 1000).
"""

api_doc_sso = """
## Retrieve Solar System Object data

The list of arguments for retrieving SSO data can be found at https://fink-portal.org/api/v1/sso.
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
curl -H "Content-Type: application/json" -X POST -d '{"n_or_d":"4209", "output-format":"csv"}' https://fink-portal.org/api/v1/sso -o 4209.csv
```

In python, you would use

```python
import requests
import pandas as pd

# get data for ZTF21aaxtctv
r = requests.post(
  'https://fink-portal.org/api/v1/sso',
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
  'https://fink-portal.org/api/v1/sso',
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

The list of arguments for retrieving cutout data can be found at https://fink-portal.org/api/v1/cutouts.

### PNG

In a unix shell, you can retrieve the last cutout of an object by simply using

```bash
curl -H "Content-Type: application/json" \\
    -X POST -d \\
    '{"objectId":"ZTF21aaxtctv", "kind":"Science"}' \\
    https://fink-portal.org/api/v1/cutouts -o cutoutScience.png
```

This will retrieve the `Science` image and save it on `cutoutScience.png`.
In Python, the equivalent script would be:

```python
import io
import requests
from PIL import Image as im

# get data for ZTF21aaxtctv
r = requests.post(
    'https://fink-portal.org/api/v1/cutouts',
    json={
        'objectId': 'ZTF21aaxtctv',
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

# get data for ZTF21aaxtctv
r = requests.post(
    'https://fink-portal.org/api/v1/cutouts',
    json={
        'objectId': 'ZTF21aaxtctv',
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

# Get all candidate ID with JD for ZTF21aaxtctv
r = requests.post(
    'https://fink-portal.org/api/v1/objects',
    json={
        'objectId': 'ZTF21aaxtctv',
        'columns': 'i:candid,i:jd'
    }
)

pdf_candid = pd.read_json(r.content)
# Get the first alert
first_alert = pdf_candid['i:candid'].values[-1]

# get data for ZTF21aaxtctv
r = requests.post(
    'https://fink-portal.org/api/v1/cutouts',
    json={
        'objectId': 'ZTF21aaxtctv',
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
    '{"objectId":"ZTF21aaxtctv", "kind":"Science", "output-format": "FITS"}' \\
    https://fink-portal.org/api/v1/cutouts -o cutoutScience.fits
```

or equivalently in Python:

```python
import io
from astropy.io import fits
import requests
import pandas as pd

# get data for ZTF21aaxtctv
r = requests.post(
    'https://fink-portal.org/api/v1/cutouts',
    json={
        'objectId': 'ZTF21aaxtctv',
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

# get data for ZTF21aaxtctv
r = requests.post(
    'https://fink-portal.org/api/v1/cutouts',
    json={
        'objectId': 'ZTF21aaxtctv',
        'kind': 'Science',
        'output-format': 'array'
    }
)

pdf = pd.read_json(r.content)
array = pdf['b:cutoutScience_stampData'].values[0]
```

"""

api_doc_xmatch = """
## Xmatch with catalogs

The list of arguments for retrieving object data can be found at https://fink-portal.org/api/v1/xmatch.

Let's assume you have a catalog on disk (CSV format), you would use:

```python
import requests
import pandas as pd

r = requests.post(
   'https://fink-portal.org/api/v1/xmatch',
   json={
       'catalog': open('mycatalog.csv').read(),
       'header': 'RA,Dec,ID',
       'radius': 1.5, # in arcsecond
       'window': 7 # in days
   }
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)
```

The crossmatch service is a wrapper around the conesearch service.
Here is the current performance of the service for querying a
single object (1.3TB, about 40 million alerts):

![conesearch](https://user-images.githubusercontent.com/20426972/123047697-e493a500-d3fd-11eb-9f30-216dce9cbf43.png)

_circle marks with dashed lines are results for a full scan search
(~2 years of data, 40 million alerts), while the upper triangles with
dotted lines are results when restraining to 7 days search.
The numbers close to markers show the number of objects returned by the conesearch._

The catalog format must be CSV, and it is assumed that the first line is the header,
and then each line is an object, e.g.

```
ID,Time,RA,Dec,otherproperty
210430A,2021-04-30 10:42:10,57.185,45.080,toto
210422A,2021-04-22 17:47:10,21.077,42.100,tutu
210421B,2021-04-21 10:54:44,270.817,56.828,tutu
210421A,2021-04-21 00:27:30,104.882,4.928,toto
210420B,2021-04-20 18:34:37,254.313,42.558,foo
210419C,2021-04-19 23:27:49,212.969,36.011,bar
AnObjectMatching,2019-11-02 02:51:12.001,271.3914265,45.2545134,foo
```

The argument `header` is the comma-separated names of the columns matching
RA, Dec, ID and Time (in this order). So if your catalog header is

```
aproperty,myID,detection time,RA(J2000),Dec(J2000),otherproperty
x,210430A,2021-04-30 10:42:10,57.185,45.080,toto
y,210422A,2021-04-22 17:47:10,21.077,42.100,tutu
```

You would specify:

```python
'header': 'RA(J2000),Dec(J2000),myID,detection time'
```

Note that the `Time` column is optional. You do not need to specify it,
in which case your header argument will be:

```python
'header': 'RA(J2000),Dec(J2000),myID'
```

Note that is is always better to specify the time column as it speeds-up
the computation (instead of performing a full-scan). If you specify the `Time`
column, you can specify the time `window` in days around which we should perform
the cross-match (default is 1 day starting from the time column).

Finally, you can specify the `radius` for the cross-match, in arcsecond. You can
specify any values, with a maximum of 18,000 arcseconds (5 degrees).
Note that in case of several objects matching, the results will be sorted
according to the column `v:separation_degree`, which is the angular separation
in degree between the input (ra, dec) and the objects found.

"""

api_doc_bayestar = """
## Cross-match with LIGO/Virgo sky maps

The list of arguments for retrieving object data can be found at https://fink-portal.org/api/v1/bayestar.

Let's assume you want get all alerts falling inside a given LIGO/Virgo credible region sky map
(retrieved from the GraceDB event page, or distributed via GCN). You would
simply upload the sky map with a threshold, and Fink returns all alerts emitted
within `[-1 day, +6 day]` from the GW event inside the chosen credible region.
Concretely on [S200219ac](https://gracedb.ligo.org/superevents/S200219ac/view/):

```python
# LIGO/Virgo probability sky maps, as gzipped FITS (bayestar.fits.gz)
# S200219ac on 2020-02-19T09:44:15.197173
fn = 'bayestar.fits.gz'

# GW credible region threshold to look for. Note that the values in the resulting
# credible level map vary inversely with probability density: the most probable pixel is
# assigned to the credible level 0.0, and the least likely pixel is assigned the credible level 1.0.
# Area of the 20% Credible Region:
credible_level = 0.2

# Query Fink
data = open(fn, 'rb').read()
r = requests.post(
    'https://fink-portal.org/api/v1/bayestar',
    json={
        'bayestar': str(data),
        'credible_level': credible_level,
        'output-format': 'json'
    }
)

pdf = pd.read_json(r.content)
```

You will get a Pandas DataFrame as usual, with all alerts inside the region (within `[-1 day, +6 day]`).
Here are some statistics on this specific event:

```markdown
| `credible_level` | Sky area | number of alerts returned | Execution time |
|-----------|----------|---------------------------|----------------------|
| 0.2 | 81 deg2 | 121 | 2 to 5 seconds |
| 0.5 | 317 deg2 | 1137 | 10 to 15 seconds|
| 0.9 | 1250 deg2 | 2515 | > 60 seconds |
```

Here is the details of alert classification for a credible level of 0.9:

```
5968 alerts found
v:classification
Unknown                   2122
Solar System candidate    2058
QSO                        703
SN candidate               259
RRLyr                      253
Solar System MPC           172
Seyfert_1                  118
EB*                        105
Ambiguous                   24
Blue                        19
Star                        18
Galaxy                      15
BLLac                       12
Radio                       10
Candidate_RRLyr             10
SN                           8
Seyfert_2                    6
PulsV*delSct                 5
BClG                         5
AGN                          5
LPV*                         4
EB*Algol                     4
RadioG                       3
CataclyV*                    3
QSO_Candidate                2
X                            2
BlueStraggler                2
Candidate_EB*                2
LINER                        2
GravLensSystem               2
PM*                          2
GinCl                        1
EllipVar                     1
AMHer                        1
Early SN Ia candidate        1
HB*                          1
DwarfNova                    1
Possible_G                   1
Candidate_CV*                1
Nova                         1
BYDra                        1
WD*                          1
Mira                         1
low-mass*                    1
```
Most of the alerts are actually catalogued. Finally, you can overplot alerts on the sky map:

```python
import healpy as hp
import matplotlib.pyplot as plt

hpx, header_ = hp.read_map(fn, h=True, field=0)
header = {i[0]: i[1] for i in header_}

title = 'Probability sky maps for {}'.format(header['OBJECT'])
hp.mollzoom(hpx, coord='G', title=title)

if len(pdf) > 0:
    hp.projscatter(
        pdf['i:ra'],
        pdf['i:dec'],
        lonlat=True,
        marker='x',
        color='C1',
        alpha=0.5
    )

hp.graticule()
plt.show()
```

![gw](https://user-images.githubusercontent.com/20426972/134175884-3b190fa9-8051-4a1d-8bf8-cc8b47252494.png)
"""

api_doc_stats = """
## Fink data statistics

The [statistics](https://fink-portal.org/stats) page makes use of the REST API.
If you want to further explore Fink statistics, or create your own dashboard based on Fink data,
you can do also all of these yourself using the REST API. Here is an example using Python:

```python
import requests
import pandas as pd

# get stats for all the year 2021
r = requests.post(
  'https://fink-portal.org/api/v1/statistics',
  json={{
    'date': '2021',
    'output-format': 'json'
  }}
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)
```

Note `date` can be either a given night (YYYYMMDD), month (YYYYMM), year (YYYY), or eveything (empty string).
The schema of the dataframe is the following:

{}

All other fields starting with `class:` are crossmatch from the SIMBAD database.
""".format(pd.DataFrame([dic_names]).T.rename(columns={0: 'description'}).to_markdown())

def layout(is_mobile):
    if is_mobile:
        width = '95%'
    else:
        width = '80%'
    layout_ = html.Div(
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
                            dbc.Tab(
                                [
                                    dbc.Card(
                                        dbc.CardBody(
                                            dcc.Markdown(api_doc_xmatch)
                                        ), style={
                                            'backgroundColor': 'rgb(248, 248, 248, .7)'
                                        }
                                    ),
                                ], label="Xmatch"
                            ),
                            dbc.Tab(
                                [
                                    dbc.Card(
                                        dbc.CardBody(
                                            dcc.Markdown(api_doc_bayestar)
                                        ), style={
                                            'backgroundColor': 'rgb(248, 248, 248, .7)'
                                        }
                                    ),
                                ], label="Gravitational Waves"
                            ),
                            dbc.Tab(
                                [
                                    dbc.Card(
                                        dbc.CardBody(
                                            dcc.Markdown(api_doc_stats)
                                        ), style={
                                            'backgroundColor': 'rgb(248, 248, 248, .7)'
                                        }
                                    ),
                                ], label="Statistics"
                            ),
                        ]
                    )
                ], className="mb-8", fluid=True, style={'width': width}
            )
        ], className='home', style={
            'background-image': 'linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(/assets/background.png)',
            'background-size': 'contain'
        }
    )
    return layout_


args_objects = [
    {
        'name': 'objectId',
        'required': True,
        'description': 'ZTF Object ID'
    },
    {
        'name': 'withupperlim',
        'required': False,
        'description': 'If True, retrieve also upper limit measurements, and bad quality measurements. Use the column `d:tag` in your results: valid, upperlim, badquality.'
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
        'required': True,
        'group': 0,
        'description': 'ZTF Object ID'
    },
    {
        'name': 'ra',
        'required': True,
        'group': 1,
        'description': 'Right Ascension'
    },
    {
        'name': 'dec',
        'required': True,
        'group': 1,
        'description': 'Declination'
    },
    {
        'name': 'radius',
        'required': True,
        'group': 1,
        'description': 'Conesearch radius in arcsec. Maximum is 36,000 arcseconds (10 degrees).'
    },
    {
        'name': 'startdate_conesearch',
        'required': False,
        'group': 1,
        'description': '[Optional] Starting date in UTC for the conesearch query.'
    },
    {
        'name': 'window_days_conesearch',
        'required': False,
        'group': 1,
        'description': '[Optional] Time window in days for the conesearch query.'
    },
    {
        'name': 'startdate',
        'required': True,
        'group': 2,
        'description': 'Starting date in UTC'
    },
    {
        'name': 'window',
        'required': True,
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
        'description': 'Last N alerts to transfer between stopping date and starting date. Default is 10, max is 1000.'
    },
    {
        'name': 'startdate',
        'required': False,
        'description': 'Starting date in UTC (iso, jd, or MJD). Default is 2019-11-01 00:00:00'
    },
    {
        'name': 'stopdate',
        'required': False,
        'description': 'Stopping date in UTC (iso, jd, or MJD). Default is now.'
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

args_xmatch = [
    {
        'name': 'catalog',
        'required': True,
        'description': 'External catalog as CSV'
    },
    {
        'name': 'header',
        'required': True,
        'description': 'Comma separated names of columns corresponding to RA, Dec, ID, Time[optional] in the input catalog.'
    },
    {
        'name': 'radius',
        'required': True,
        'description': 'Conesearch radius in arcsec. Maximum is 18,000 arcseconds (5 degrees).'
    },
    {
        'name': 'window',
        'required': False,
        'description': '[Optional] Time window in days.'
    },
]

args_bayestar = [
    {
        'name': 'bayestar',
        'required': True,
        'description': 'LIGO/Virgo probability sky maps, as gzipped FITS (bayestar.fits.gz)'
    },
    {
        'name': 'credible_level',
        'required': True,
        'description': 'GW credible region threshold to look for. Note that the values in the resulting credible level map vary inversely with probability density: the most probable pixel is assigned to the credible level 0.0, and the least likely pixel is assigned the credible level 1.0.'
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet'
    }
]

args_stats = [
    {
        'name': 'date',
        'required': True,
        'description': 'Observing date. This can be either a given night (YYYYMMDD), month (YYYYMM), year (YYYY), or eveything (empty string)'
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

    if 'withupperlim' in request.json and request.json['withupperlim'] == 'True':
        # upper limits
        resultsU = clientU.scan(
            "",
            "{}".format(to_evaluate),
            "*", 0, False, False
        )

        # bad quality
        resultsUP = clientUV.scan(
            "",
            "{}".format(to_evaluate),
            "*", 0, False, False
        )

        pdfU = pd.DataFrame.from_dict(resultsU, orient='index')
        pdfUP = pd.DataFrame.from_dict(resultsUP, orient='index')

        pdf['d:tag'] = 'valid'
        pdfU['d:tag'] = 'upperlim'
        pdfUP['d:tag'] = 'badquality'

        if 'i:jd' in pdfUP.columns:
            # workaround -- see https://github.com/astrolabsoftware/fink-science-portal/issues/216
            mask = np.array([False if float(i) in pdf['i:jd'].values else True for i in pdfUP['i:jd'].values])
            pdfUP = pdfUP[mask]

        pdf_ = pd.concat((pdf, pdfU, pdfUP), axis=0)
        pdf_['i:jd'] = pdf_['i:jd'].astype(float)

        # replace
        pdf = pdf_.sort_values('i:jd', ascending=False)

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
    required = [i['required'] for i in args_explorer if i['group'] == user_group]
    for required_arg, required_ in zip(required_args, required):
        if (required_arg not in request.json) and required_:
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
        # Interpret user input
        ra, dec = request.json['ra'], request.json['dec']
        radius = request.json['radius']

        if 'startdate_conesearch' in request.json:
            startdate = request.json['startdate_conesearch']
        else:
            startdate = None
        if 'window_days_conesearch' in request.json and request.json['window_days_conesearch'] is not None:
            window_days = float(request.json['window_days_conesearch'])
        else:
            window_days = 1.0

        if float(radius) > 18000.:
            rep = {
                'status': 'error',
                'text': "`radius` cannot be bigger than 18,000 arcseconds (5 degrees).\n"
            }
            return Response(str(rep), 400)

        if 'h' in str(ra):
            coord = SkyCoord(ra, dec, frame='icrs')
        elif ':' in str(ra) or ' ' in str(ra):
            coord = SkyCoord(ra, dec, frame='icrs', unit=(u.hourangle, u.deg))
        else:
            coord = SkyCoord(ra, dec, frame='icrs', unit='deg')

        ra = coord.ra.deg
        dec = coord.dec.deg
        radius_deg = float(radius) / 3600.

        # angle to vec conversion
        vec = hp.ang2vec(np.pi / 2.0 - np.pi / 180.0 * dec, np.pi / 180.0 * ra)

        # Send request
        if float(radius) <= 30.:
            nside = 131072
            clientP_ = clientP131072
        elif (float(radius) > 30.) & (float(radius) <= 1000.):
            nside = 4096
            clientP_ = clientP4096
        else:
            nside = 128
            clientP_ = clientP128

        pixs = hp.query_disc(
            nside,
            vec,
            np.pi / 180 * radius_deg,
            inclusive=True
        )

        # For the future: we could set clientP_.setRangeScan(True)
        # and pass directly the time boundaries here instead of
        # grouping by later.

        # Filter by time - logic to be improved...
        if startdate is not None:
            if ':' in str(startdate):
                jdstart = Time(startdate).jd
            elif str(startdate).startswith('24'):
                jdstart = Time(startdate, format='jd').jd
            else:
                jdstart = Time(startdate, format='mjd').jd
            jdend = jdstart + window_days

            clientP_.setRangeScan(True)
            results = java.util.TreeMap()
            for pix in pixs:
                to_search = "key:key:{}_{},key:key:{}_{}".format(pix, jdstart, pix, jdend)
                result = clientP_.scan(
                    "",
                    to_search,
                    "*",
                    0, True, True
                )
                results.putAll(result)
        else:
            to_evaluate = ",".join(
                [
                    'key:key:{}'.format(i) for i in pixs
                ]
            )
            # Get matches in the pixel index table
            results = clientP_.scan(
                "",
                to_evaluate,
                "*",
                0, True, True
            )

        # extract objectId and times
        objectids = [i[1]['i:objectId'] for i in results.items()]
        times = [float(i[1]['key:key'].split('_')[1]) for i in results.items()]
        pdf_ = pd.DataFrame({'oid': objectids, 'jd': times})

        # Filter by time - logic to be improved...
        if startdate is not None:
            pdf_ = pdf_[(pdf_['jd'] >= jdstart) & (pdf_['jd'] < jdstart + window_days)]

        # groupby and keep only the last alert per objectId
        pdf_ = pdf_.loc[pdf_.groupby('oid')['jd'].idxmax()]

        # Get data from the main table
        results = java.util.TreeMap()
        for oid, jd in zip(pdf_['oid'].values, pdf_['jd'].values):
            to_evaluate = "key:key:{}_{}".format(oid, jd)

            result = client.scan(
                "",
                to_evaluate,
                "*",
                0, True, True
            )
            results.putAll(result)
        schema_client = client.schema()
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

    pdfs = format_hbase_output(
        results,
        schema_client,
        group_alerts=True,
        extract_color=False
    )

    # For conesearch, sort by distance
    if (user_group == 1) and (len(pdfs) > 0):
        sep = coord.separation(
            SkyCoord(
                pdfs['i:ra'],
                pdfs['i:dec'],
                unit='deg'
            )
        ).deg

        pdfs['v:separation_degree'] = sep
        pdfs = pdfs.sort_values('v:separation_degree', ascending=True)

        mask = pdfs['v:separation_degree'] > radius_deg
        pdfs = pdfs[~mask]

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

    if 'startdate' not in request.json:
        # start of the Fink operations
        jd_start = Time('2019-11-01 00:00:00').jd
    else:
        jd_start = Time(request.json['startdate']).jd

    if 'stopdate' not in request.json:
        jd_stop = Time.now().jd
    else:
        jd_stop = Time(request.json['stopdate']).jd

    # Search for latest alerts for a specific class
    tns_classes = pd.read_csv('assets/tns_types.csv', header=None)[0].values
    is_tns = request.json['class'].startswith('(TNS)') and (request.json['class'].split('(TNS) ')[1] in tns_classes)
    if is_tns:
        classname = request.json['class'].split('(TNS) ')[1]
        clientTNS.setLimit(nalerts)
        clientTNS.setRangeScan(True)
        clientTNS.setReversed(True)

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
    elif request.json['class'].startswith('(SIMBAD)') or request.json['class'] != 'allclasses':
        if request.json['class'].startswith('(SIMBAD)'):
            classname = request.json['class'].split('(SIMBAD) ')[1]
        else:
            classname = request.json['class']

        if classname == 'Early SN Ia candidate':
            # ugly fix. In the database,
            # we made a typo that is not fixed.
            classname = 'Early SN candidate'
        clientS.setLimit(nalerts)
        clientS.setRangeScan(True)
        clientS.setReversed(True)

        results = clientS.scan(
            "",
            "key:key:{}_{},key:key:{}_{}".format(
                classname,
                jd_start,
                classname,
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
    tns_types = ['(TNS) ' + x for x in tns_types]

    # SIMBAD
    simbad_types = pd.read_csv('assets/simbad_types.csv', header=None)[0].values
    simbad_types = sorted(simbad_types, key=lambda s: s.lower())
    simbad_types = ['(SIMBAD) ' + x for x in simbad_types]

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
            {'name': 'cdsxmatch', 'type': 'string', 'doc': 'SIMBAD closest counterpart, based on position. See https://fink-portal.org/api/v1/classes'},
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
            {'name': 'constellation', 'type': 'string', 'doc': 'Name of the constellation an alert on the sky is in'},
            {'name': 'classification', 'type': 'string', 'doc': 'Fink inferred classification. See https://fink-portal.org/api/v1/classes'},
            {'name': 'g-r', 'type': 'double', 'doc': 'Last g-r measurement for this object.'},
            {'name': 'rate(g-r)', 'type': 'double', 'doc': 'g-r rate in mag/day (between last and first available g-r measurements).'},
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
        results,
        schema_client,
        group_alerts=False,
        truncated=truncated,
        extract_color=False
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

@api_bp.route('/api/v1/xmatch', methods=['GET'])
def xmatch_arguments():
    """ Obtain information about the xmatch service
    """
    return jsonify({'args': args_xmatch})

@api_bp.route('/api/v1/xmatch', methods=['POST'])
def xmatch_user():
    """ Xmatch with user uploaded catalog
    """
    df = pd.read_csv(io.StringIO(request.json['catalog']))

    radius = float(request.json['radius'])
    if radius > 18000.:
        rep = {
            'status': 'error',
            'text': "`radius` cannot be bigger than 18,000 arcseconds (5 degrees).\n"
        }
        return Response(str(rep), 400)

    header = request.json['header']

    header = [i.strip() for i in header.split(',')]
    if len(header) == 3:
        raname, decname, idname = header
    elif len(header) == 4:
        raname, decname, idname, timename = header
    else:
        rep = {
            'status': 'error',
            'text': "Header should contain 3 or 4 entries from your catalog. E.g. RA,DEC,ID or RA,DEC,ID,Time\n"
        }
        return Response(str(rep), 400)

    if 'window' in request.json:
        window_days = request.json['window']
    else:
        window_days = None

    # Fink columns of interest
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
        'i:classtar',
        'd:knscore',
        'i:jdstarthist'
    ]

    unique_cols = np.unique(colnames + colnames_added_values).tolist()

    # check units
    ra0 = df[raname].values[0]
    if 'h' in str(ra0):
        coords = [
            SkyCoord(ra, dec, frame='icrs')
            for ra, dec in zip(df[raname].values, df[decname].values)
        ]
    elif ':' in str(ra0) or ' ' in str(ra0):
        coords = [
            SkyCoord(ra, dec, frame='icrs', unit=(u.hourangle, u.deg))
            for ra, dec in zip(df[raname].values, df[decname].values)
        ]
    else:
        coords = [
            SkyCoord(ra, dec, frame='icrs', unit='deg')
            for ra, dec in zip(df[raname].values, df[decname].values)
        ]
    ras = [coord.ra.deg for coord in coords]
    decs = [coord.dec.deg for coord in coords]
    ids = df[idname].values

    if len(header) == 4:
        times = df[timename].values
    else:
        times = np.zeros_like(ras)

    pdfs = pd.DataFrame(columns=unique_cols + [idname] + ['v:classification'])
    for oid, ra, dec, time_start in zip(ids, ras, decs, times):
        if len(header) == 4:
            payload = {
                'ra': ra,
                'dec': dec,
                'radius': radius,
                'startdate_conesearch': time_start,
                'window_days_conesearch': window_days

            }
        else:
            payload = {
                'ra': ra,
                'dec': dec,
                'radius': radius
            }
        r = requests.post(
           '{}/api/v1/explorer'.format(APIURL),
           json=payload
        )
        pdf = pd.read_json(r.content)
        # Loop over results and construct the dataframe
        if not pdf.empty:
            pdf[idname] = [oid] * len(pdf)
            if 'd:knscore' not in pdf.columns:
                pdf['d:knscore'] = np.zeros(len(pdf), dtype=float)
            pdfs = pd.concat((pdfs, pdf), ignore_index=True)

    # Final join
    join_df = pd.merge(
        pdfs,
        df,
        on=idname
    )

    # reorganise columns order
    no_duplicate = np.where(pdfs.columns != idname)[0]
    cols = list(df.columns) + list(pdfs.columns[no_duplicate])
    join_df = join_df[cols]
    return join_df.to_json(orient='records')

@api_bp.route('/api/v1/bayestar', methods=['GET'])
def query_bayestar_arguments():
    """ Obtain information about inspecting a GW localization map
    """
    return jsonify({'args': args_bayestar})

@api_bp.route('/api/v1/bayestar', methods=['POST'])
def query_bayestar():
    """ Query the Fink database to find alerts inside a GW localization map
    """
    if 'output-format' in request.json:
        output_format = request.json['output-format']
    else:
        output_format = 'json'

    # Interpret user input
    bayestar_data = request.json['bayestar']
    credible_level_threshold = float(request.json['credible_level'])

    with gzip.open(io.BytesIO(eval(bayestar_data)), 'rb') as f:
        with fits.open(io.BytesIO(f.read())) as hdul:
            data = hdul[1].data
            header = hdul[1].header

    hpx = data['PROB']
    if header['ORDERING'] == 'NESTED':
        hpx = hp.reorder(hpx, n2r=True)

    i = np.flipud(np.argsort(hpx))
    sorted_credible_levels = np.cumsum(hpx[i])
    credible_levels = np.empty_like(sorted_credible_levels)
    credible_levels[i] = sorted_credible_levels

    # TODO: use that to define the max skyfrac (in conjunction with level)
    # npix = len(hpx)
    # nside = hp.npix2nside(npix)
    # skyfrac = np.sum(credible_levels <= 0.1) * hp.nside2pixarea(nside, degrees=True)

    credible_levels_128 = hp.ud_grade(credible_levels, 128)

    pixs = np.where(credible_levels_128 <= credible_level_threshold)[0]

    # make a condition as well on the number of pixels?
    # print(len(pixs), pixs)

    # For the future: we could set clientP128.setRangeScan(True)
    # and pass directly the time boundaries here instead of
    # grouping by later.

    # 1 day before the event, to 6 days after the event
    jdstart = Time(header['DATE-OBS']).jd - 1
    jdend = jdstart + 6

    clientP128.setRangeScan(True)
    results = java.util.TreeMap()
    for pix in pixs:
        to_search = "key:key:{}_{},key:key:{}_{}".format(pix, jdstart, pix, jdend)
        result = clientP128.scan(
            "",
            to_search,
            "*",
            0, True, True
        )
        results.putAll(result)

    # extract objectId and times
    objectids = [i[1]['i:objectId'] for i in results.items()]
    times = [float(i[1]['key:key'].split('_')[1]) for i in results.items()]
    pdf_ = pd.DataFrame({'oid': objectids, 'jd': times})

    # Filter by time - logic to be improved...
    pdf_ = pdf_[(pdf_['jd'] >= jdstart) & (pdf_['jd'] < jdend)]

    # groupby and keep only the last alert per objectId
    pdf_ = pdf_.loc[pdf_.groupby('oid')['jd'].idxmax()]

    # Get data from the main table
    results = java.util.TreeMap()
    for oid, jd in zip(pdf_['oid'].values, pdf_['jd'].values):
        to_evaluate = "key:key:{}_{}".format(oid, jd)

        result = client.scan(
            "",
            to_evaluate,
            "*",
            0, True, True
        )
        results.putAll(result)
    schema_client = client.schema()

    pdfs = format_hbase_output(
        results,
        schema_client,
        group_alerts=True,
        extract_color=False
    )

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

@api_bp.route('/api/v1/statistics', methods=['GET'])
def query_statistics_arguments():
    """ Obtain information about Fink statistics
    """
    return jsonify({'args': args_stats})

@api_bp.route('/api/v1/statistics', methods=['POST'])
def return_statistics():
    """ Retrieve statistics about Fink data
    """
    if 'output-format' in request.json:
        output_format = request.json['output-format']
    else:
        output_format = 'json'

    if 'columns' in request.json:
        cols = request.json['columns'].replace(" ", "")
    else:
        cols = '*'

    payload = request.json['date']

    to_evaluate = "key:key:ztf_{}".format(payload)

    results = clientStats.scan(
        "",
        to_evaluate,
        cols,
        0, True, True
    )

    pdf = pd.DataFrame.from_dict(results, orient='index')

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

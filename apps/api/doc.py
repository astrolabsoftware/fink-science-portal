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
import pandas as pd

from app import APIURL
from apps.statistics import dic_names

api_doc_summary = f"""
# Fink API

## Summary of services

| HTTP Method | URI | Action | Availability |
|-------------|-----|--------|--------------|
| POST/GET | {APIURL}/api/v1/objects| Retrieve single object data from the Fink database | &#x2611;&#xFE0F; |
| POST/GET | {APIURL}/api/v1/explorer | Query the Fink alert database | &#x2611;&#xFE0F; |
| POST/GET | {APIURL}/api/v1/latests | Get latest alerts by class | &#x2611;&#xFE0F; |
| POST/GET | {APIURL}/api/v1/sso | Get confirmed Solar System Object data | &#x2611;&#xFE0F; |
| POST/GET | {APIURL}/api/v1/ssocand | Get candidate Solar System Object data | &#x2611;&#xFE0F; |
| POST/GET | {APIURL}/api/v1/tracklet | Get tracklet data | &#x2611;&#xFE0F; |
| POST/GET | {APIURL}/api/v1/cutouts | Retrieve cutout data from the Fink database| &#x2611;&#xFE0F; |
| POST/GET | {APIURL}/api/v1/xmatch | Cross-match user-defined catalog with Fink alert data| &#x2611;&#xFE0F; |
| POST/GET | {APIURL}/api/v1/bayestar | Cross-match LIGO/Virgo sky map with Fink alert data| &#x2611;&#xFE0F; |
| POST/GET | {APIURL}/api/v1/statistics | Statistics concerning Fink alert data| &#x2611;&#xFE0F; |
| POST/GET | {APIURL}/api/v1/anomaly | Fink alerts with large anomaly score| &#x2611;&#xFE0F; |
| POST/GET | {APIURL}/api/v1/random | Draw random objects from the Fink database| &#x2611;&#xFE0F; |
| POST/GET  | {APIURL}/api/v1/ssoft  | Get the Fink Solar System table | &#x2611;&#xFE0F; |
| POST/GET  | {APIURL}/api/v1/resolver  | Resolve names | &#x2611;&#xFE0F; |
| GET  | {APIURL}/api/v1/classes  | Display all Fink derived classification | &#x2611;&#xFE0F; |
| GET  | {APIURL}/api/v1/columns  | Display all available alert fields and their type | &#x2611;&#xFE0F; |
"""

api_doc_object = """
## Retrieve object data

The list of arguments for retrieving object data can be found at https://fink-portal.org/api/v1/objects.

In a unix shell, you would simply use

```bash
# Get data for ZTF21aaxtctv and save it in a CSV file
curl -H "Content-Type: application/json" -X POST -d '{"objectId":"ZTF21aaxtctv", "output-format":"csv"}' https://fink-portal.org/api/v1/objects -o ZTF21aaxtctv.csv

# you can also specify parameters in the URL, e.g. with wget:
wget "https://fink-portal.org/api/v1/objects?objectId=ZTF21aaxtctv&output-format=json" -O ZTF21aaxtctv.json
```

In python, you would use

```python
import io
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
pdf = pd.read_json(io.BytesIO(r.content))
```

You can retrieve the data for several objects at once:

```python
mylist = ['ZTF21aaxtctv', 'ZTF21abfmbix', 'ZTF21abfaohe']

# get data for many objects
r = requests.post(
  'https://fink-portal.org/api/v1/objects',
  json={
    'objectId': ','.join(mylist),
    'output-format': 'json'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))
```

Note that for `csv` output, you need to use

```python
# get data for ZTF21aaxtctv in CSV format...
r = ...

pd.read_csv(io.BytesIO(r.content))
```

You can also get a votable:

```python
import io
from astropy.io import votable

# get data for ZTF21aaxtctv in JSON format...
r = ...

vt = votable.parse(io.BytesIO(r.content))
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
pdf = pd.read_json(io.BytesIO(r.content))

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
pdf = pd.read_json(io.BytesIO(r.content))

columns = [
    'b:cutoutScience_stampData',
    'b:cutoutTemplate_stampData',
    'b:cutoutDifference_stampData'
]

for col in columns:
    # 2D array
    data = pdf[col].to_numpy()[0]

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
You must choose among `Search by Object ID` and `Conesearch` / `Search by Date`.
In a future release, you will be able to combine searches.
The list of arguments for querying the Fink alert database can be found at https://fink-portal.org/api/v1/explorer.

### Search by Object ID

Enter a valid object ID to access its data, e.g. try:

* ZTF21abfmbix, ZTF21aaxtctv, ZTF21abfaohe, ZTF20aanxcpf, ZTF17aaaabte, ZTF18aafpcwm, ZTF21abujbqa, ZTF21abuipwb, ZTF18acuajcr

In a unix shell, you would simply use

```bash
# Get data for ZTF21aaxtctv and save it in a JSON file
curl -H "Content-Type: application/json" -X POST -d '{"objectId":"ZTF21aaxtctv"}' https://fink-portal.org/api/v1/explorer -o search_ZTF21aaxtctv.json

# you can also specify parameters in the URL, e.g. with wget:
wget "https://fink-portal.org/api/v1/explorer?objectId=ZTF21aaxtctv&output-format=json" -O ZTF21aaxtctv.json
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
pdf = pd.read_json(io.BytesIO(r.content))
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

# you can also specify parameters in the URL, e.g. with wget:
wget "https://fink-portal.org/api/v1/explorer?ra=193.822&dec=2.89732&radius=5&startdate_conesearch=2021-06-25 05:59:37.000&window_days_conesearch=7&output-format=json" -O conesearch.json
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
pdf = pd.read_json(io.BytesIO(r.content))
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
    'startdate': '2021-06-25 05:59:37.000',
    'window': 7
  }
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))
```

Here is the performance of the service for querying a
single object (database of 1.3TB, about 40 million alerts):

![conesearch](https://user-images.githubusercontent.com/20426972/123047697-e493a500-d3fd-11eb-9f30-216dce9cbf43.png)

_circle marks with dashed lines are results for a full scan search
(~2 years of data, 40 million alerts), while the upper triangles with
dotted lines are results when restraining to 7 days search.
The numbers close to markers show the number of objects returned by the conesearch._

### Search by Date

Choose a starting date and stopping date or a time window to see all alerts in this period.
Dates are in UTC, and the time window in days (but should not exceed 3 hours).
Example of valid search:

* 2021-07-01 05:59:37.000

In a unix shell, you would simply use

```bash
# Get all objects between 2021-07-01 05:59:37.000 and 2021-07-01 06:09:37.000 UTC
curl -H "Content-Type: application/json" -X POST -d '{"startdate":"2021-07-01 05:59:37.000", "window":"0.007"}' https://fink-portal.org/api/v1/explorer -o datesearch.json

# you can also specify parameters in the URL, e.g. with wget:
wget "https://fink-portal.org/api/v1/explorer?startdate=2021-07-01 05:59:37.000&window=0.007&output-format=json" -O datesearch.json
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
    'window': '0.007'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))
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

# you can also specify parameters in the URL, e.g. with wget:
wget "https://fink-portal.org/api/v1/latests?class=Early SN Ia candidate&n=5&output-format=json" -O latest_five_sn_candidates.json
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
pdf = pd.read_json(io.BytesIO(r.content))
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
pdf = pd.read_json(io.BytesIO(r.content))
```
There is no limit of time, but you will be limited by the
number of alerts retrieve on the server side `n` (current max is 1000).
"""

api_doc_sso = """
## Retrieve Solar System Object data

The list of arguments for retrieving SSO data can be found at https://fink-portal.org/api/v1/sso.
The numbers or designations are taken from the MPC archive.
When searching for a particular asteroid or comet, it is best to use the IAU number,
as in 8467 for asteroid "8467 Benoitcarry". You can also try for numbered comet (e.g. 10P),
or interstellar object (none so far...). If the number does not yet exist, you can search for designation.
Here are some examples of valid queries:

* Asteroids by number (default)
  * Asteroids (Main Belt): 8467, 1922
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
# Get data for the asteroid 8467 and save it in a CSV file
curl -H "Content-Type: application/json" -X POST -d '{"n_or_d":"8467", "output-format":"csv"}' https://fink-portal.org/api/v1/sso -o 8467.csv

# you can also specify parameters in the URL, e.g. with wget:
wget "https://fink-portal.org/api/v1/sso?n_or_d=8467&output-format=json" -O 8467.json
```

In python, you would use

```python
import requests
import pandas as pd

# get data for object 8467
r = requests.post(
  'https://fink-portal.org/api/v1/sso',
  json={
    'n_or_d': '8467',
    'output-format': 'json'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))
```

Note that for `csv` output, you need to use

```python
# get data for asteroid 8467 in CSV format...
r = ...

pd.read_csv(io.BytesIO(r.content))
```

You can also get a votable using the json output format:

```python
from astropy.table import Table

# get data for asteroid 8467 in JSON format...
r = ...

t = Table(r.json())
```

You can also attach the ephemerides provided by the [Miriade ephemeride service](https://ssp.imcce.fr/webservices/miriade/api/ephemcc/):

```python
import requests
import pandas as pd

# get data for object 8467
r = requests.post(
  'https://fink-portal.org/api/v1/sso',
  json={
    'n_or_d': '8467',
    'withEphem': True,
    'output-format': 'json'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))
print(pdf.columns)
Index(['index', 'Date', 'LAST', 'HA', 'Az', 'H', 'Dobs', 'Dhelio', 'VMag',
       'SDSS:g', 'SDSS:r', 'Phase', 'Elong.', 'AM', 'dRAcosDEC', 'dDEC', 'RV',
       'RA', 'Dec', 'Longitude', 'Latitude', 'd:cdsxmatch', 'd:mulens',
       'd:rf_kn_vs_nonkn', 'd:rf_snia_vs_nonia', 'd:roid', 'd:snn_sn_vs_all',
       'd:snn_snia_vs_nonia', 'i:candid', 'i:chipsf', 'i:classtar', 'i:dec',
       'i:diffmaglim', 'i:distnr', 'i:distpsnr1', 'i:drb', 'i:fid', 'i:field',
       'i:isdiffpos', 'i:jd', 'i:jdendhist', 'i:jdstarthist', 'i:maggaia',
       'i:magnr', 'i:magpsf', 'i:magzpsci', 'i:ndethist', 'i:neargaia',
       'i:nid', 'i:nmtchps', 'i:objectId', 'i:publisher', 'i:ra', 'i:rb',
       'i:rcid', 'i:sgscore1', 'i:sigmagnr', 'i:sigmapsf', 'i:ssdistnr',
       'i:ssmagnr', 'i:ssnamenr', 'i:tooflag', 'i:xpos', 'i:ypos',
       'd:tracklet', 'v:classification', 'v:lastdate', 'v:constellation',
       'i:magpsf_red'],
      dtype='object')
```

Where first columns are fields returned from Miriade (beware it adds few seconds delay).
There are some limitations:

    - Color ephemerides are returned only for asteroids
    - Temporary designations (C/... or YYYY...) do not have ephemerides available

You can also query several objects at the same time:

```python
import requests
import pandas as pd

# get data for object 8467 and 1922
r = requests.post(
  'https://fink-portal.org/api/v1/sso',
  json={
    'n_or_d': '8467,1922',
    'output-format': 'json'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))
```

Note that you can mix asteroid and comet names, unless you specify `withEphem=True`, in which
case you must give only a list of asteroid names or list of comet names (schemas for ephemerides are not the same).

By default, we transfer all available data fields (original ZTF fields and Fink science module outputs).
But you can also choose to transfer only a subset of the fields:

```python
# select only jd, and magpsf
r = requests.post(
  'https://fink-portal.org/api/v1/sso',
  json={
    'n_or_d': '8467',
    'columns': 'i:jd,i:magpsf'
  }
)
```

Note that the fields should be comma-separated. Unknown field names are ignored.
"""

api_doc_tracklets = """
## Retrieve tracklet data

The list of arguments for retrieving tracklet data can be found at https://fink-portal.org/api/v1/tracklet.

Each night there are a lot of fast moving objects seen in single exposures (or a few).
These objects usually leave discrete tracks (several connected dots), that we call tracklets.
The magnitude is rather low, and their magnitude can oscillate (e.g. rotating objects).
This is somehow similar to solar system object, expect that these objects
seem mainly man-made, they are fast moving, and they typically orbit around the Earth (this
is also tighted to the detection method we use).

In order to get tracklet data, you need to specify the date in the format `YYYY-MM-DD hh:mm:ss`.
Note you can also specify bigger interval, e.g. `YYYY-MM-DD` to get all tracklets for one day,
or `YYYY-MM-DD hh` to get all tracklets for one hour.

In a unix shell, you would simply use

```bash
# Get tracklet data for the night 2021-08-10
curl -H "Content-Type: application/json" -X POST -d '{"date":"2021-08-10", "output-format":"csv"}' https://fink-portal.org/api/v1/tracklet -o trck_20210810.csv

# you can also specify parameters in the URL, e.g. with wget:
wget "https://fink-portal.org/api/v1/tracklet?date=2021-08-10&output-format=json" -O trck_20210810.json
```

In python, you would use

```python
import requests
import pandas as pd

# Get all tracklet data for the night 2021-08-10
r = requests.post(
  'https://fink-portal.org/api/v1/tracklet',
  json={
    'date': '2021-08-10',
    'output-format': 'json'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))
```
You can also specify up to the second if you know the exposure time:

```python
# Get tracklet data TRCK_20211022_091949
r = requests.post(
  'https://fink-portal.org/api/v1/tracklet',
  json={
    'id': '2021-10-22 09:19:49',
    'output-format': 'json'
  }
)
```

Finally if there are several tracklets in one exposure, you can select the one you want:

```python
# Get first tracklet TRCK_20211022_091949_00
r = requests.post(
  'https://fink-portal.org/api/v1/tracklet',
  json={
    'id': '2021-10-22 09:19:49 00',
    'output-format': 'json'
  }
)
```

They are ordered by two digits 00, 01, 02, ...
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

# you can also specify parameters in the URL, e.g. with wget:
wget "https://fink-portal.org/api/v1/cutouts?objectId=ZTF21aaxtctv&kind=Science" -O ZTF21aaxtctv_Science.png
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
        'stretch': 'sigmoid', # sigmoid[default], linear, sqrt, power, log
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
first_alert = pdf_candid['i:candid'].to_numpy()[-1]

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

data = fits.open(io.BytesIO(r.content), ignore_missing_simple=True)
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

pdf = pd.read_json(io.BytesIO(r.content))
array = pdf['b:cutoutScience_stampData'].to_numpy()[0]
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
pdf = pd.read_json(io.BytesIO(r.content))
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

Let's assume you want get all alerts falling inside a given LIGO/Virgo/Kagra
credible region sky map, just use the event name:

```python
import io
import requests
import pandas as pd

# GW credible region threshold to look for. Note that the values in the resulting
# credible level map vary inversely with probability density: the most probable pixel is
# assigned to the credible level 0.0, and the least likely pixel is assigned the credible level 1.0.
# Area of the 20% Credible Region:
credible_level = 0.2

# Query Fink
r = requests.post(
    'https://fink-portal.org/api/v1/bayestar',
    json={
        'event_name': 'S230709bi',
        'credible_level': credible_level,
        'output-format': 'json'
    }
)

pdf = pd.read_json(io.BytesIO(r.content))
```
Fink returns all alerts emitted within `[-1 day, +6 day]` from the GW event inside the chosen credible region.
Alternatively, you can input a sky map retrieved from the GraceDB event page, or distributed via GCN.
Concretely on [S230709bi](https://gracedb.ligo.org/superevents/S230709bi/view/):

```python
import io
import requests
import pandas as pd

# LIGO/Virgo probability sky maps, as gzipped FITS (bayestar.fits.gz)
data = requests.get('https://gracedb.ligo.org/api/superevents/S230709bi/files/bayestar.fits.gz')

# Query Fink
r = requests.post(
    'https://fink-portal.org/api/v1/bayestar',
    json={
        'bayestar': str(data.content),
        'credible_level': 0.2,
        'output-format': 'json'
    }
)

pdf = pd.read_json(io.BytesIO(r.content))
```

You will get a Pandas DataFrame as usual, with all alerts inside the region (within `[-1 day, +6 day]`).
Here is the details of alert classification for a credible level of 0.4:

```
pdf.groupby('d:classification').size()
d:classification
SN candidate               2
Solar System MPC           2
Solar System candidate    42
Unknown                   35
```

You can safely ignore `Solar System MPC`, but `Solar System candidate` can also be genuine new extra-galactic transients that we misclassified. Finally, you can overplot alerts on the sky map:

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

![gw](/assets/gw.png)

You can also find this tutorial in the [fink-tutorials repository](https://github.com/astrolabsoftware/fink-tutorials/blob/main/MMA/gravitational_waves.ipynb).
Note that you can also use any map with the same structure than LVK skymaps:

```python
import io
import requests
import pandas as pd

fn = 'my.fits.gz'

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

pdf = pd.read_json(io.BytesIO(r.content))
```
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
pdf = pd.read_json(io.BytesIO(r.content))
```

Note `date` can be either a given night (YYYYMMDD), month (YYYYMM), year (YYYY), or eveything (empty string).
The schema of the dataframe is the following:

{}

All other fields starting with `class:` are crossmatch from the SIMBAD database.
""".format(
    pd.DataFrame([dic_names]).T.rename(columns={0: "description"}).to_markdown(),
)

api_doc_random = """
## Draw random objects

This service lets you draw random objects (full lightcurve) from the Fink database (120+ million alerts). This is still largely experimental.

The list of arguments for retrieving object data can be found at https://fink-portal.org/api/v1/random.

In a unix shell, you would simply use

```bash
# Get the data for 8 *objects* randomly drawn from the +120 million alerts in Fink
curl -H "Content-Type: application/json" -X POST -d '{"n":8, "output-format":"csv"}' https://fink-portal.org/api/v1/random -o random.csv

# you can also specify parameters in the URL, e.g. with wget:
wget "https://fink-portal.org/api/v1/random?n=8&output-format=json" -O random.json
```

In python, you would use

```python
import requests
import pandas as pd

r = requests.post(
  'https://fink-portal.org/api/v1/random',
  json={
    'n': integer, # Number of random objects to get. Maximum is 16.
    'class': classname, # Optional, specify a Fink class.
    'seed': integer, # Optional, the seed for reproducibility
    'columns': str, # Optional, comma-separated column names
    'output-format': output_format, # Optional [json[default], csv, parquet, votable]
  }
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))
```

As this service is experimental, the number of random objects returned for a single
call cannot be greater than 16. Concerning the classname, see https://fink-portal.org/api/v1/classes.
If you do not specify the parameter `class`, you will get random objects from all classes.
For better performances, we advice to choose a classname, and limit colunms to transfer, e.g.:

```
# random Early SN Ia candidate
r = requests.post(
  'https://fink-portal.org/api/v1/random',
  json={
    'n': 16, # Number of random objects to get
    'class': 'Early SN Ia candidate', # Optional, specify a Fink class.
    'seed': 0, # Optional, the seed for reproducibility
    'columns': 'i:objectId,i:jd,i:magpsf,i:fid', # Optional, comma-separated column names
  }
)
```

Note that this returns data for *objects* (and not just alerts).

Note also that the `seed` is used to fix the date boundaries, hence it is valid only over a small period of time as the database is updated everyday, and more dates are added...
So consider your seed valid over 24h (this might change in the future).

"""

api_doc_ssocand = """
## Explore Solar System object orbit candidates

This service lets you query the information about new Solar System objects found by [fink-fat](https://github.com/FusRoman/fink-fat).

The list of arguments for retrieving object data can be found at https://fink-portal.org/api/v1/ssocand.

In python, you would use

```python
import io
import requests
import pandas as pd

r = requests.post(
  'https://fink-portal.org/api/v1/ssocand',
  json={
    'kind': str, # Mandatory, `orbParams` or `lightcurves`
    'ssoCandId': int, # optional, if you know a trajectory ID. Otherwise returns all.
    'start_date': str, # optional. Only for lightcurves. Default is 2019-11-01
    'stop_date': str, # optional. Only for lightcurves. Default is today.
    'maxnumber': int, # optional. Max number of entries to retrieve. Default is 10,000.
    'output-format': str
  }
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))
```

Depending on `kind`, you would get information on:
- `lightcurves`: photometry of objects related to candidate orbits
- `orbParams`: orbital parameters for orbit candidates
"""

api_doc_anomaly = """
## Explore Anomaly detections

This service lets you query the information about anomalous objects in Fink. Each night, Fink selects and stores
the top 10 alerts with the most anomalous scores. The Science module was deployed and start producing scores on 2023-01-25.

The list of arguments for retrieving alert data can be found at https://fink-portal.org/api/v1/anomaly.

In python, you would use

```python
import io
import requests
import pandas as pd

r = requests.post(
  'https://fink-portal.org/api/v1/anomaly',
  json={
    'n': int, # Optional. Number of objects to retrieve between `stop_date` and `start_date`. Default is 10.
    'start_date': str, # Optional. YYYY-MM-DD. Default is 2023-01-25
    'stop_date': str, # Optional. YYYY-MM-DD. Default is today
    'columns': str, # Optional. Comma-separated column names to retrieve. Default is all columns.
    'output-format': str
  }
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))
```

This table has full _alert_ schema, and you can easily gets statistics, example:

```python
# retrieve all anomalies
import io
import requests
import pandas as pd

r = requests.post(
  'https://fink-portal.org/api/v1/anomaly',
  json={
    'n': 10000, # on purpose large
    'stop_date': '2023-05-22',
    'columns': 'i:objectId,d:cdsxmatch,i:magpsf'
  }
)
pdf = pd.read_json(io.BytesIO(r.content))

pdf.groupby('d:cdsxmatch').agg({'i:objectId': 'count'}).sort_values('i:objectId', ascending=False)

               i:objectId
d:cdsxmatch
CataclyV*             191
Unknown               170
Mira                   65
RRLyr                  63
LPV*                   52
EB*_Candidate          21
EB*                    20
Star                   14
CV*_Candidate          10
Fail 504               10
Blazar                  6
V*                      6
WD*_Candidate           4
YSO_Candidate           4
PulsV*                  3
Fail 500                3
YSO                     3
Fail 503                2
SN                      2
LP*_Candidate           1
BLLac                   1
QSO                     1
Radio                   1
Seyfert_1               1
TTau*                   1
Em*                     1
ClG                     1
V*?_Candidate           1
BlueStraggler           1
AGN                     1
```
Note the `Fail X` labels are when the CDS xmatch service fails with error code X (web service).
But because this table has full _alert_ schema, if you want full object data,
you need to call then the `/api/v1/object` service. Example:

```python
# retrieve last 10 anomaly objectIds
import io
import requests
import pandas as pd

r = requests.post(
  'https://fink-portal.org/api/v1/anomaly',
  json={
    'n': 10,
    'columns': 'i:objectId'
  }
)

# Format output in a DataFrame
oids = [i['i:objectId'] for i in r.json()]

# retrieve full objects data
r = requests.post(
  'https://fink-portal.org/api/v1/objects',
  json={
    'objectId': ','.join(oids),
    'columns': 'i:objectId,i:magpsf,i:sigmapsf,d:anomaly_score,d:cdsxmatch,d:lc_features_g,d:lc_features_r',
    'output-format': 'json'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))
```

Note the first time, the `/api/v1/object` query can be long (especially if
you are dealing with variable stars), but then data is cached on the server,
and subsequent queries are much faster. By default, `features` are string arrays. You can easily
cast them into proper arrays using the `json` package:

```python
import json

for col in ['d:lc_features_g', 'd:lc_features_r']:
  pdf[col] =  pdf[col].apply(lambda x: json.loads(x))
```

The anomaly header can be found [here](https://github.com/astrolabsoftware/fink-science/blob/master/fink_science/ad_features/processor.py#L74), and
programmatically accessed via:

```python
from fink_science.ad_features.processor import FEATURES_COLS
print(FEATURES_COLS)
[
  'mean', 'weighted_mean', 'standard_deviation', 'median', 'amplitude', 'beyond_1_std',
  'cusum', 'inter_percentile_range_10', 'kurtosis', 'linear_trend', 'linear_trend_sigma',
  'linear_trend_noise', 'linear_fit_slope', 'linear_fit_slope_sigma', 'linear_fit_reduced_chi2',
  'magnitude_percentage_ratio_40_5', 'magnitude_percentage_ratio_20_10', 'maximum_slope',
  'median_absolute_deviation', 'median_buffer_range_percentage_10', 'percent_amplitude',
  'mean_variance', 'anderson_darling_normal', 'chi2', 'skew', 'stetson_K'
]
```

"""

api_doc_ssoft = """
## Get the Fink Solar System Table

This service lets you query the table containing aggregated parameters for Solar System objects in Fink.
This table is updated once a month, with all data in Fink.

### Basic usage

The list of arguments for retrieving alert data can be found at https://fink-portal.org/api/v1/ssoft,
and the schema of the table (json) can be found at https://fink-portal.org/api/v1/ssoft?schema

In python, you would use

```python
import io
import requests
import pandas as pd

r = requests.post(
  'https://fink-portal.org/api/v1/ssoft',
  json={
    'output-format': 'parquet'
  }
)

# Format output in a DataFrame
pdf = pd.read_parquet(io.BytesIO(r.content))
```

or e.g. with curl:

```
curl -H "Content-Type: application/json" -X POST -d '{"output-format":"parquet"}' https://fink-portal.org/api/v1/ssoft -o ssoft.parquet
```

This table contains basic statistics (e.g. coverage in time for each object, name, number, ...),
fitted parameters (absolute magnitude, phase parameters, spin parameters, ...), quality statuses, and version number.

### Single object

You can also retrieve information about a single object, using its name or IAU number:

```
# using name
curl -H "Content-Type: application/json" -X POST -d '{"output-format":"json", "sso_name": "Autonoma"}' https://fink-portal.org/api/v1/ssoft

# using number
curl -H "Content-Type: application/json" -X POST -d '{"output-format":"json", "sso_number": "1465"}' https://fink-portal.org/api/v1/ssoft
```

You can retrieve the schema of the table using using the schema argument:

```python
import io
import requests
import pandas as pd

r = requests.post(
  'https://fink-portal.org/api/v1/ssoft',
  json={
    'schema': True
  }
)

schema = r.json()['args']
```

or view it in your browser:

```
https://fink-portal.org/api/v1/ssoft?schema
```

### Flavors

By default, we expose the parameters from the sHG1G2 model (paper coming!), that is HG1G2
augmented with shape and spin parameters. You can also choose standard `HG` or `HG1G2` models:

```python
import io
import requests
import pandas as pd

r = requests.post(
  'https://fink-portal.org/api/v1/ssoft',
  json={
    'flavor': 'HG',
    'output-format': 'parquet'
  }
)
```

Idem for the schema of the table:

```
https://fink-portal.org/api/v1/ssoft?flavor=HG&schema
```

### Version

The table is versioned (`YYYY.MM`), and you can access previous versions (starts at 2023.07):

```python
import io
import requests
import pandas as pd

r = requests.post(
  'https://fink-portal.org/api/v1/ssoft',
  json={
    'version': '2023.07',
    'output-format': 'parquet'
  }
)
```

By default (that is `version` unspecified), the service will return the latest one.
"""

api_doc_resolver = """
## Resolving names

Giving names is a complex process, and often objects end up with multiple names or designations.
At the era of big data, this is especially harder as the need to names million of
objects quickly lead to non-intuitive designation process.
We will not come up with a new naming scheme here, but rather offer a
new service to explore existing names for a given object.
Currently, you will be able to resolve ZTF object names in SIMBAD,
the Transient Name Server, and Solar System databases known by
the Quaero service from SSODNET -- and vice versa meaning given an object in
one of those 3 databases, you will know if there is a corresponding ZTF objects.
This service is expanding, and we will keep adding new source of information.

The list of arguments for retrieving alert data can be found at https://fink-portal.org/api/v1/resolver

### TNS to ZTF

I have a TNS identifier, are there ZTF objects corresponding?

```python
import io
import requests
import pandas as pd

r = requests.post(
  'https://fink-portal.org/api/v1/resolver',
  json={
    'resolver': 'tns',
    'name': 'SN 2023vwy'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))

   d:declination  d:fullname d:internalname       d:ra  d:redshift d:type       key:time
0      52.219894  SN 2023vwy     ATLAS23url  47.765951       0.031  SN Ia  1704445385951
1      52.219894  SN 2023vwy   ZTF23abmwsrw  47.765951       0.031  SN Ia  1704445385951
```

You can also download the full table by specifying an empty name:

```python
r = requests.post(
  'https://fink-portal.org/api/v1/resolver',
  json={
    'resolver': 'tns',
    'name': '',
    'nmax': 1000000
  }
)

         d:declination  d:fullname     d:internalname           d:ra d:redshift  d:type       key:time
0           -55.409677    AT 1976S  GSC2.3 SATX032616     286.245594        NaN     nan  1704445383818
1           -25.480611    AT 1978M  GSC2.3 S64P036598     122.320327        NaN     nan  1704445383818
2            47.530987   AT 1991bm  GSC2.3 N0ZY037003     273.810015        NaN     nan  1704445388697
3            14.414089   AT 1992bw  GSC2.3 NB6I007107       1.510637        NaN     nan  1704445388697
4            25.566352   AT 1993an  GSC2.3 NBIP012777      10.505964        NaN     nan  1704445383818
...                ...         ...                ...            ...        ...     ...            ...
174736      40.9886174  SN 2023zzk         ATLAS23xnr     54.7199172   0.020127   SN II  1704445385595
174737      40.9886174  SN 2023zzk       ZTF23abtycgb     54.7199172   0.020127   SN II  1704445385595
174738  -42.6586722222  SN 2023zzn         ATLAS23xjb  46.8617011111      0.094  SLSN-I  1704445385595
174739  -24.7868458611   SN 2024fa         ATLAS24adw   36.255712664       0.01   SN II  1704445385595
174740  -24.7868458611   SN 2024fa             PS24ca   36.255712664       0.01   SN II  1704445385595

[174741 rows x 7 columns]

```

### ZTF to TNS

I have a ZTF object name, are there counterparts in TNS?


```python
r = requests.post(
  'https://fink-portal.org/api/v1/resolver',
  json={
    'resolver': 'tns',
    'reverse': True,
    'name': 'ZTF23abmwsrw'
  }
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))

   d:declination  d:fullname d:internalname       d:ra d:type       key:time
0      52.219904  AT 2023vwy   ZTF23abmwsrw  47.765935    nan  1698788550829
1      52.219894  SN 2023vwy   ZTF23abmwsrw  47.765951  SN Ia  1702926332847
```

### SIMBAD to ZTF

I have an astronomical object name referenced in SIMBAD, are there counterparts in ZTF? As these objects can be extended, we typically provide coordinates, and then you need to run a conesearch:


```python
r = requests.post(
  'https://fink-portal.org/api/v1/resolver',
  json={
    'resolver': 'simbad',
    'name': 'Markarian 2'
  }
)

if r.json() != []:
    print('Object found!')
    print(r.json())
    print()

    r = requests.post(
      'https://fink-portal.org/api/v1/explorer',
      json={
        'ra': r.json()[0]['jradeg'],
        'dec': r.json()[0]['jdedeg'],
        'radius': 60
      }
    )

    # Format output in a DataFrame
    pdf = pd.read_json(io.BytesIO(r.content))
    print('Object(s) in ZTF: {}'.format(pdf['i:objectId'].to_numpy()))
else:
    print('No objects found')
```

Leading in this example to:

```
Object found!
[
  {
    'name': 'Si=Simbad, all IDs (via url)',
    'oid': 1579005,
    'oname': 'Mrk 2',
    'otype': 'GiG',
    'jpos': '01:54:53.80 +36:55:04.6',
    'jradeg': 28.7241958,
    'jdedeg': 36.9179556,
    'refPos': '2006AJ....131.1163S',
    'z': None,
    'MType': 'SBa',
    'nrefs': 138
  }
]

Object(s) in ZTF: ['ZTF18aabfjoi']
```

### ZTF to SIMBAD

I have a ZTF object name, are there counterparts in SIMBAD?


```python
r = requests.post(
  'https://fink-portal.org/api/v1/resolver',
  json={
    'resolver': 'simbad',
    'reverse': True,
    'name': 'ZTF18aabfjoi'
  }
)
pdf = pd.read_json(io.BytesIO(r.content))

  d:cdsxmatch             i:candid      i:dec          i:jd    i:objectId       i:ra
0    GinGroup  1045306711115010048  36.917909  2.458800e+06  ZTF18aabfjoi  28.724092
1    GinGroup  1400219061115010048  36.917912  2.459155e+06  ZTF18aabfjoi  28.724130
2    GinGroup  1626461821115010048  36.917924  2.459381e+06  ZTF18aabfjoi  28.724110
3    GinGroup  1977476361115010048  36.917913  2.459732e+06  ZTF18aabfjoi  28.724100
4    GinGroup  2119325081115010048  36.917892  2.459874e+06  ZTF18aabfjoi  28.724094
```

5 different alerts from the same object (`ZTF18aabfjoi`).

### SSO to ZTF

I have a SSO name or number, are there ZTF objects corresponding?
You first need to resolve the corresponding ZTF `ssnamenr`:

```python
r = requests.post(
  'https://fink-portal.org/api/v1/resolver',
  json={
    'resolver': 'ssodnet',
    'name': '624188'
  }
)

pdf = pd.read_json(io.BytesIO(r.content))

     i:name  i:number i:ssnamenr
0  2002 MA6    624188    2002MA6
1  2002 MA6    624188     624188
2  2002 MA6    624188   2002MA06
3  2002 MA6    624188     624188
```

and then search for corresponding alerts for all `ssnamenr`:

```python
r = requests.post(
  'https://fink-portal.org/api/v1/sso',
  json={
    'n_or_d': ','.join(pdf['i:ssnamenr'].to_numpy()),
    'columns': 'i:objectId,i:ra,i:dec,i:magpsf,i:sigmapsf,i:ssnamenr'
  }
)
sso = pd.read_json(io.BytesIO(r.content))

        i:dec   i:magpsf    i:objectId       i:ra  i:sigmapsf i:ssnamenr
0   38.761579  19.651100  ZTF19acrplsa  84.760898    0.201959   2002MA06
1   35.097359  19.678823  ZTF19adagirr  74.131671    0.154512   2002MA06
2   32.709072  20.320038  ZTF23aazubcu  38.761726    0.181345    2002MA6
3   36.039245  20.226397  ZTF23abcakzn  42.951283    0.208451    2002MA6
4   37.399041  20.620817  ZTF23abecthp  44.314170    0.181139    2002MA6
5   37.412476  19.931238  ZTF23abeeoen  44.324915    0.122155    2002MA6
6   38.092562  19.839323  ZTF23abfvtyr  44.875277    0.110749    2002MA6
7   38.102591  20.627150  ZTF23abfxptv  44.881451    0.182423    2002MA6
8   39.028132  19.811459  ZTF23abhahgo  45.412434    0.116035    2002MA6
9   40.087669  19.518000  ZTF23abidfxt  45.472807    0.134570     624188
10  40.253863  20.037786  ZTF23abilvaz  45.374426    0.172761     624188
11  40.263377  19.517801  ZTF23abiotst  45.365776    0.116226     624188
12  40.717564  19.452196  ZTF23abkempy  44.508594    0.087599     624188
13  40.718352  19.871597  ZTF23abkfquu  44.504111    0.144978     624188
14  40.760788  19.485823  ZTF23abkwjee  44.211183    0.093203     624188
15  40.777337  19.365993  ZTF23ablsjlg  43.858879    0.078582     624188
16  40.777324  19.830032  ZTF23ablthyz  43.850151    0.109873     624188
17  40.046433  19.359879  ZTF23abogmeh  40.809196    0.127990     624188
18  39.832539  19.788800  ZTF23aboqpks  40.349063    0.139298     624188
19  39.153497  19.270357  ZTF23abpqqiz  39.155381    0.140963     624188
20  39.134613  19.803095  ZTF23abpsedk  39.124796    0.165054     624188
21  38.846470  19.866776  ZTF23abqbtrv  38.709943    0.139531     624188
22  38.826889  19.179682  ZTF23abqdzil  38.680996    0.095241     624188
23  38.508815  19.166033  ZTF23abqphse  38.268334    0.072787     624188
24  33.059517  19.892330  ZTF23absmjqg  35.439591    0.186579     624188
25  32.477462  19.840815  ZTF23abtpaxv  35.544006    0.173815     624188
26  32.294998  19.863436  ZTF23abtxgba  35.595829    0.105220     624188
27  32.292988  19.976093  ZTF23abtxjux  35.596339    0.081324     624188
28  32.094647  20.584602  ZTF23abuivpe  35.662240    0.160992     624188
29  31.925860  20.086443  ZTF23abuppio  35.728953    0.138072     624188
30  31.916201  20.444067  ZTF23abuqdev  35.732460    0.172873     624188
```

### Exact/inexact searches

By default, the SSO resolver will perform an _inexact_ search, meaning it will return the exact search plus closest matches. The number of closest matches is controlled by the parameter `nmax`, with default `nmax=10`:

```python
r = requests.post(
  'https://fink-portal.org/api/v1/resolver',
  json={
    'resolver': 'ssodnet',
    'name': '33'
  }
)

pdf = pd.read_json(io.BytesIO(r.content))

          i:name  i:number  i:ssnamenr
0     Polyhymnia        33          33
1     Polyhymnia        33          33
2      Adalberta       330         330
3      Adalberta       330         330
4       3300 T-1     17325       17325
5       3300 T-2     69209       69209
6       3300 T-3     79071       79071
7      McGlasson      3300        3300
8      McGlasson      3300        3300
9  Chenjiansheng     33000       33000
```
Note that there are duplicates, as data is indexed by `name`, `number`, and `ssnamenr`.
If you want to perform an _exact_ search, just put `nmax=1`:

```python
r = requests.post(
  'https://fink-portal.org/api/v1/resolver',
  json={
    'resolver': 'ssodnet',
    'name': '33',
    'nmax': 1
  }
)

pdf = pd.read_json(io.BytesIO(r.content))

       i:name  i:number  i:ssnamenr
0  Polyhymnia        33          33
1  Polyhymnia        33          33
```

### ZTF to SSO

I have a ZTF object name, is there a counterpart in the SsODNet quaero database, and what are all the known aliases to Fink?

```python
r = requests.post(
  'https://fink-portal.org/api/v1/resolver',
  json={
    'resolver': 'ssodnet',
    'reverse': True,
    'name': 'ZTF23abidfxt'
  }
)

if r.json() != []:
    name = r.json()[0]['i:ssnamenr']
    print('Asteroid counterpart found with designation {}'.format(name))
    print()

    r2 = requests.post(
      'https://fink-portal.org/api/v1/resolver',
      json={
        'resolver': 'ssodnet',
        'name': name,
        'nmax': 1
      }
    )

    pdf = pd.read_json(io.BytesIO(r2.content))
    print('In the Fink database, {} also corresponds to: '.format(name))
    print(pdf)
```

Leading to:

```
Asteroid counterpart found with designation 624188

In the Fink database, 624188 also corresponds to:
  i:source i:ssnamenr
0    number   2002MA06
1    number    2002MA6
2    number     624188
3  ssnamenr     624188
```
"""

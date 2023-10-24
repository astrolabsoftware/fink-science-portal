# Copyright 2021-2023 AstroLab Software
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
import dash
import dash_bootstrap_components as dbc
from dash.long_callback import DiskcacheLongCallbackManager

# import jpype

import yaml
import diskcache

cache = diskcache.Cache("./cache")
long_callback_manager = DiskcacheLongCallbackManager(cache)

args = yaml.load(open('config.yml'), yaml.Loader)

APIURL = args['APIURL']

# bootstrap theme
external_stylesheets = [
    dbc.themes.SPACELAB,
    '//aladin.u-strasbg.fr/AladinLite/api/v2/latest/aladin.min.css',
    '//use.fontawesome.com/releases/v5.7.2/css/all.css',
]
external_scripts = [
    '//code.jquery.com/jquery-1.12.1.min.js',
    '//aladin.u-strasbg.fr/AladinLite/api/v2/latest/aladin.min.js',
    '//cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js',
]

app = dash.Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    external_scripts=external_scripts,
    meta_tags=[{
        "name": "viewport",
        "content": "width=device-width, initial-scale=1"
    }],
    long_callback_manager=long_callback_manager
)


app.title = 'Fink Science Portal'
nlimit = 10000

app.server.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
server = app.server

app.config.suppress_callback_exceptions = True

# if not jpype.isJVMStarted():
#     jarpath = "-Djava.class.path=bin/FinkBrowser.exe.jar"
#     jpype.startJVM(jpype.getDefaultJVMPath(), "-ea", jarpath, convertStrings=True)

# jpype.attachThreadToJVM()

# import com.Lomikel.HBaser
# from com.astrolabsoftware.FinkBrowser.Utils import Init

# Init.init()

# client = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
# client.connect(args['tablename'], args['SCHEMAVER'])
# client.setLimit(nlimit)

# clientT = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
# clientT.connect(args['tablename'] + ".jd", args['SCHEMAVER'])
# clientT.setLimit(nlimit)

# clientP128 = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
# clientP128.connect(args['tablename'] + ".pixel128", args['SCHEMAVER'])
# clientP128.setLimit(nlimit)

# clientS = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
# clientS.connect(args['tablename'] + ".class", args['SCHEMAVER'])
# clientS.setLimit(nlimit)

# clientU = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
# clientU.connect(args['tablename'] + ".upper", args['SCHEMAVER'])
# clientU.setLimit(nlimit)

# clientUV = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
# clientUV.connect(args['tablename'] + ".uppervalid", args['SCHEMAVER'])
# clientUV.setLimit(nlimit)

# clientSSO = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
# clientSSO.connect(args['tablename'] + ".ssnamenr", args['SCHEMAVER'])
# clientSSO.setLimit(nlimit)

# clientTRCK = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
# clientTRCK.connect(args['tablename'] + ".tracklet", args['SCHEMAVER'])
# clientTRCK.setLimit(nlimit)

# clientTNS = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
# clientTNS.connect(args['tablename'] + ".tns", args['SCHEMAVER'])
# clientTNS.setLimit(nlimit)

# clientStats = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
# clientStats.connect('statistics_class', args['SCHEMAVER'])
# clientStats.setLimit(nlimit)

# clientSSOCAND = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
# clientSSOCAND.connect(args['tablename'] + ".sso_cand", args['SCHEMAVER'])
# clientSSOCAND.setLimit(nlimit)

# clientSSOORB = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
# clientSSOORB.connect(args['tablename'] + ".orb_cand", args['SCHEMAVER'])
# clientSSOORB.setLimit(nlimit)

# clientANOMALY = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
# clientANOMALY.connect(args['tablename'] + ".anomaly", args['SCHEMAVER'])
# clientANOMALY.setLimit(nlimit)

# clientTNSRESOL = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
# clientTNSRESOL.connect(args['tablename'] + ".tns_resolver", args['SCHEMAVER'])
# clientTNSRESOL.setLimit(nlimit)

# clientMeta = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
# clientMeta.connect(args['tablename'] + ".metadata", 'schema')
# clientMeta.setLimit(nlimit)

import dash
import dash_bootstrap_components as dbc

import jpype
import jpype.imports
from jpype import JImplements, JOverride, JImplementationFor

APIURL = "http://localhost"

# bootstrap theme
# https://bootswatch.com/spacelab/
external_stylesheets = [
    dbc.themes.SPACELAB,
    '//aladin.u-strasbg.fr/AladinLite/api/v2/latest/aladin.min.css',
    '//use.fontawesome.com/releases/v5.7.2/css/all.css',
]
external_scripts = [
    '//code.jquery.com/jquery-1.9.1.min.js',
    '//aladin.u-strasbg.fr/AladinLite/api/v2/latest/aladin.min.js',
    '//cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.4/MathJax.js?config=TeX-MML-AM_CHTML',
]

app = dash.Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    external_scripts=external_scripts,
    meta_tags=[{
        "name": "viewport",
        "content": "width=device-width, initial-scale=1"
    }]
)


app.title = 'Fink Science Portal'
nlimit = 10000

app.server.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
server = app.server

app.config.suppress_callback_exceptions = True

if not jpype.isJVMStarted():
    jarpath = "-Djava.class.path=bin/FinkBrowser_05112020.exe.jar"
    jpype.startJVM(jpype.getDefaultJVMPath(), "-ea", jarpath, convertStrings=True)

jpype.attachThreadToJVM()

import com.Lomikel.HBaser
from com.astrolabsoftware.FinkBrowser.Utils import Init

Init.init()

IPADDR = "localhost"
ZOOPORT = 2181
SCHEMAVER = "schema_1.3_0.4.8"

# base
tablename = 'test_sp'

client = com.Lomikel.HBaser.HBaseClient(IPADDR, ZOOPORT);
client.connect(tablename, SCHEMAVER)

clientT = com.Lomikel.HBaser.HBaseClient(IPADDR, ZOOPORT);
clientT.connect(tablename + ".jd", SCHEMAVER)

clientP128 = com.Lomikel.HBaser.HBaseClient(IPADDR, ZOOPORT);
clientP128.connect(tablename + ".pixel128", SCHEMAVER)

clientP4096 = com.Lomikel.HBaser.HBaseClient(IPADDR, ZOOPORT);
clientP4096.connect(tablename + ".pixel4096", SCHEMAVER)

clientP131072 = com.Lomikel.HBaser.HBaseClient(IPADDR, ZOOPORT);
clientP131072.connect(tablename + ".pixel131072", SCHEMAVER)

clientS = com.Lomikel.HBaser.HBaseClient(IPADDR, ZOOPORT);
clientS.connect(tablename + ".class", SCHEMAVER)

clientU = com.Lomikel.HBaser.HBaseClient(IPADDR, ZOOPORT);
clientU.connect(tablename + ".upper", SCHEMAVER)

clientUV = com.Lomikel.HBaser.HBaseClient(IPADDR, ZOOPORT);
clientUV.connect(tablename + ".uppervalid", SCHEMAVER)

clientSSO = com.Lomikel.HBaser.HBaseClient(IPADDR, ZOOPORT);
clientSSO.connect(tablename + ".ssnamenr", SCHEMAVER)

clientTRCK = com.Lomikel.HBaser.HBaseClient(IPADDR, ZOOPORT);
clientTRCK.connect(tablename + ".tracklet", SCHEMAVER)

clientTNS = com.Lomikel.HBaser.HBaseClient(IPADDR, ZOOPORT);
clientTNS.connect(tablename + ".tns", SCHEMAVER)

clientStats = com.Lomikel.HBaser.HBaseClient(IPADDR, ZOOPORT);
clientStats.connect('statistics_class', SCHEMAVER)

clientSSOCAND = com.Lomikel.HBaser.HBaseClient(IPADDR, ZOOPORT);
clientSSOCAND.connect(tablename + ".orb_cand", SCHEMAVER)

clientSSOORB = com.Lomikel.HBaser.HBaseClient(IPADDR, ZOOPORT);
clientSSOORB.connect(tablename + ".sso_cand", SCHEMAVER)

client.setLimit(nlimit);

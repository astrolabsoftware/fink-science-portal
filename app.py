import dash
import dash_bootstrap_components as dbc

import jpype
import jpype.imports
from jpype import JImplements, JOverride, JImplementationFor

import yaml

args = yaml.load(open('config.yml'), yaml.Loader)

APIURL = args['APIURL']

# bootstrap theme
external_stylesheets = [
    dbc.themes.ZEPHYR,
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

client = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
client.connect(args['tablename'], args['SCHEMAVER'])

clientT = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
clientT.connect(args['tablename'] + ".jd", args['SCHEMAVER'])

clientP128 = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
clientP128.connect(args['tablename'] + ".pixel128", args['SCHEMAVER'])

clientP4096 = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
clientP4096.connect(args['tablename'] + ".pixel4096", args['SCHEMAVER'])

clientP131072 = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
clientP131072.connect(args['tablename'] + ".pixel131072", args['SCHEMAVER'])

clientS = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
clientS.connect(args['tablename'] + ".class", args['SCHEMAVER'])

clientU = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
clientU.connect(args['tablename'] + ".upper", args['SCHEMAVER'])

clientUV = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
clientUV.connect(args['tablename'] + ".uppervalid", args['SCHEMAVER'])

clientSSO = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
clientSSO.connect(args['tablename'] + ".ssnamenr", args['SCHEMAVER'])

clientTRCK = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
clientTRCK.connect(args['tablename'] + ".tracklet", args['SCHEMAVER'])

clientTNS = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
clientTNS.connect(args['tablename'] + ".tns", args['SCHEMAVER'])

clientStats = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
clientStats.connect('statistics_class', args['SCHEMAVER'])

clientSSOCAND = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
clientSSOCAND.connect(args['tablename'] + ".sso_cand", args['SCHEMAVER'])

clientSSOORB = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
clientSSOORB.connect(args['tablename'] + ".orb_cand", args['SCHEMAVER'])

client.setLimit(nlimit);

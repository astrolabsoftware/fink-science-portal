import dash
import dash_bootstrap_components as dbc

import jpype
import jpype.imports
from jpype import JImplements, JOverride, JImplementationFor

APIURL = "http://134.158.75.151:24000"

# bootstrap theme
# https://bootswatch.com/spacelab/
external_stylesheets = [
    dbc.themes.SPACELAB,
    'http://aladin.u-strasbg.fr/AladinLite/api/v2/latest/aladin.min.css'
]
external_scripts = [
    'http://code.jquery.com/jquery-1.9.1.min.js',
    'http://aladin.u-strasbg.fr/AladinLite/api/v2/latest/aladin.min.js'
]
# external_stylesheets = [dbc.themes.LUX]
# external_stylesheets = [dbc.themes.FLATLY]

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
server = app.server
app.config.suppress_callback_exceptions = True

if not jpype.isJVMStarted():
    jarpath = "-Djava.class.path=/Users/julien/Downloads/FinkBrowser.exe(1).jar"
    # jarpath = "-Djava.class.path=/Users/julien/Documents/workspace/myrepos/fink-science-portal/FinkBrowser.exe.jar"
    jpype.startJVM(jpype.getDefaultJVMPath(), "-ea", jarpath, convertStrings=True)

import com.Lomikel.HBaser

# client = com.Lomikel.HBaser.HBaseClient("134.158.74.54", 2181);
# client.connect("test_portal_tiny.1", "schema_v0");
# client.connect("test_portal_tiny.3", "schema_0.7.0_0.3.6");

client = com.Lomikel.HBaser.HBaseClient("localhost", 2181);
client.connect("test_sp", "schema_0.7.0_0.3.7");
client.setLimit(nlimit);

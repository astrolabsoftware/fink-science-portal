import dash
import dash_bootstrap_components as dbc

import jpype
import jpype.imports
from jpype import JImplements, JOverride, JImplementationFor

# bootstrap theme
# https://bootswatch.com/spacelab/
external_stylesheets = [dbc.themes.SPACELAB]
# external_stylesheets = [dbc.themes.LUX]
# external_stylesheets = [dbc.themes.FLATLY]

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

app.title = 'Fink Science Portal'
server = app.server
app.config.suppress_callback_exceptions = True

jarpath = "-Djava.class.path=/Users/julien/Downloads/FinkBrowser.exe.jar"
jpype.startJVM(jpype.getDefaultJVMPath(), "-ea", jarpath, convertStrings=True)

import com.Lomikel.HBaser

client = com.Lomikel.HBaser.HBaseClient("134.158.74.54", 2181);
client.connect("test_portal_tiny.1", "schema_v0");
# client.connect("test_portal_tiny.3", "schema_0.7.0_0.3.6");
client.setLimit(10);

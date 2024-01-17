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
from dash import DiskcacheManager

# import jpype

import os
import yaml
import diskcache

cache = diskcache.Cache("./cache")
long_callback_manager = DiskcacheLongCallbackManager(cache)
background_callback_manager = DiskcacheManager(cache)

args = yaml.load(open('config.yml'), yaml.Loader)

APIURL = args['APIURL']
LOCALAPI = args.get('LOCALAPI', False)

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

# Enable verbose logging on callbacks, if requested
if 'DASH_TELEMETRY' in os.environ:
    from telemetry import DashWithTelemetry
    factory = DashWithTelemetry
else:
    factory = dash.Dash

app = factory(
    __name__,
    external_stylesheets=external_stylesheets,
    external_scripts=external_scripts,
    meta_tags=[{
        "name": "viewport",
        "content": "width=device-width, initial-scale=1"
    }],
    long_callback_manager=long_callback_manager,
    background_callback_manager=background_callback_manager,
    update_title=None,
    title='Fink Science Portal'
)

nlimit = 10000

app.server.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
server = app.server

app.config.suppress_callback_exceptions = True

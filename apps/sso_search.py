# Copyright 2020-2022 AstroLab Software
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
from dash import html, dcc, Input, Output, State, dash_table, no_update
from dash.exceptions import PreventUpdate

import dash_bootstrap_components as dbc
import visdcc
import dash_trich_components as dtc

import dash_mantine_components as dmc
from dash_iconify import DashIconify

from app import server
from app import app
from app import client
from app import APIURL

from apps import summary, about, statistics
from apps.api import api
from apps import __version__ as portal_version

from apps.utils import markdownify_objectid, class_colors
from apps.utils import isoify_time, validate_query, extract_query_url
from apps.plotting import draw_cutouts_quickview, draw_lightcurve_preview

from fink_utils.xmatch.simbad import get_simbad_labels

import requests
import pandas as pd
import numpy as np
from astropy.time import Time, TimeDelta
from astropy.coordinates import name_resolve
import astropy.utils as autils

message_help = """
Search for Solar System Objects in the Fink database.
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

"""

modal = html.Div(
    [
        dbc.Button(
            "Help",
            id="open",
            color='light',
            outline=True,
            style={
                "border": "0px black solid",
                'background': 'rgba(255, 255, 255, 0.0)',
                'color': 'grey'
            }
        ),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Solar System Objects (SSO)"), close_button=True),
                dbc.ModalBody(dcc.Markdown(message_help)),
            ],
            id="modal2", scrollable=True
        ),
    ]
)

@app.callback(
    Output("modal2", "is_open"),
    [Input("open", "n_clicks")],
    [State("modal2", "is_open")],
)
def toggle_modal(n1, is_open):
    """ Callback for the modal (open/close)
    """
    if n1:
        return not is_open
    return is_open

@app.callback(
    Output('selectSSO', 'options'),
    Input('selectSSO', 'search_value'),
)
def autocomplete_sso(data):
    """ Search for SSO names matching in IMCCE database

    Return only the 10 first results
    """
    if not data:
        raise PreventUpdate

    if data is not None:
        r = requests.get('https://api.ssodnet.imcce.fr/quaero/1/sso/instant-search?q={}'.format(str(data)))
        total = r.json()['total']
        if total > 0:
            template = '{} ({} {})'
            names = []
            for i in r.json()['data']:
                if 'class' in i.keys():
                    txt = template.format(i['name'], i['type'], '>'.join(i['class']))
                else:
                    txt = template.format(i['name'], i['type'], '')
                names.append(txt)
            options = [{'label': name, 'value': name, 'search': str(data)} for name in names]
        else:
            options = []
    else:
        options = [{'label': str(data), 'value': str(data)}]

    return options

# embedding the navigation bar
fink_search_bar_sso = dbc.InputGroup(
    [
        dcc.Dropdown(
            id='selectSSO',
            options=[],
            placeholder='Enter first letters or numbers of a SSO (e.g. cer)',
            style={"border": "0px black solid", 'background': 'rgba(255, 255, 255, 0.0)', 'color': 'grey', 'width': '90%'},
        ),
        modal
    ], style={"border": "0.5px grey solid", 'background': 'rgba(255, 255, 255, .75)'}, className='rcorners2'
)

def layout(pathname, is_mobile):
    if is_mobile:
        width = '95%'
        style = {'background-image': 'linear-gradient(rgba(255,255,255,0.3), rgba(255,255,255,0.3)), url(/assets/background.png)'}
    else:
        width = '60%'
        style = {'background-image': 'linear-gradient(rgba(255,255,255,0.3), rgba(255,255,255,0.3)), url(/assets/background.png)', 'background-size': 'contain'}
    layout = html.Div(
        [
            html.Br(),
            html.Br(),
            dbc.Container(
                [
                    html.Br(),
                    dbc.Row(fink_search_bar_sso),
                    html.Br(),
                    html.Br(),
                ], id='trash3', fluid=True, style={'width': width}
            ),
            # dbc.Container(id='results'),
        ],
        className='home',
        style=style
    )

    return layout


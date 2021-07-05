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
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import visdcc
import plotly.graph_objects as go

import pandas as pd
import numpy as np
import requests

from app import app, client, clientU, clientUV, clientSSO

from apps.cards import card_cutouts, card_sn_scores
from apps.cards import card_id, card_sn_properties
from apps.cards import download_object_modal
from apps.cards import card_variable_plot, card_variable_button
from apps.cards import card_explanation_variable, card_explanation_mulens
from apps.cards import card_mulens_plot, card_mulens_button, card_mulens_param
from apps.cards import card_sso_lightcurve, card_sso_radec, card_sso_mpc_params
from apps.plotting import plot_classbar
from apps.plotting import all_radio_options

from apps.utils import format_hbase_output
from apps.api import APIURL

dcc.Location(id='url', refresh=False)

def tab1_content(pdf):
    """ Summary tab

    Parameters
    ----------
    pdf: pd.DataFrame
        Results from a HBase client query
    """
    tab1_content_ = html.Div([
        dbc.Row(
            [
                dbc.Col(
                    dcc.Graph(
                        figure=plot_classbar(pdf),
                        style={
                            'width': '100%',
                            'height': '4pc'
                        },
                        config={'displayModeBar': False},
                        id='classbar'
                    ),
                    width=12
                ),
            ], justify='around'
        ),
        dbc.Row([
            dbc.Col(card_cutouts(False), width=8),
            dbc.Col([
                card_id(pdf)
            ], width=4)
        ]),
    ])
    return tab1_content_

def tab2_content(pdf):
    """ Supernova tab
    """
    tab2_content_ = html.Div([
        dbc.Row([
            dbc.Col(card_sn_scores(), width=8),
            dbc.Col(id='card_sn_properties', width=4)
        ]),
    ])
    return tab2_content_

def tab3_content(pdf):
    """ Variable stars tab
    """
    tab3_content_ = html.Div([
        dbc.Row([
            dbc.Col([card_variable_plot(), html.Br(), card_explanation_variable()], width=8),
            dbc.Col([card_variable_button(pdf)], width=4)
        ]),
    ])
    return tab3_content_

def tab4_content(pdf):
    """ Microlensing tab
    """
    tab4_content_ = html.Div([
        dbc.Row([
            dbc.Col([card_mulens_plot(), html.Br(), card_explanation_mulens()], width=8),
            dbc.Col([card_mulens_button(pdf), card_mulens_param()], width=4)
        ]),
    ])
    return tab4_content_

def tab5_content(pdf):
    """ SSO tab
    """
    ssnamenr = pdf['i:ssnamenr'].values[0]
    tab5_content_ = html.Div([
        dbc.Row(
            [
                dbc.Col([card_sso_lightcurve(), card_sso_radec()]),
                dbc.Col([card_sso_mpc_params(ssnamenr)], width=4)
            ]
        ),
    ])
    return tab5_content_

def tab_mobile_content(pdf):
    """ Content for mobile application
    """
    content_ = html.Div([
        dbc.Row(
            [
                dbc.Col(
                    dcc.Graph(
                        figure=plot_classbar(pdf, is_mobile=True),
                        style={
                            'width': '100%',
                            'height': '4pc'
                        },
                        config={'displayModeBar': False},
                        id='classbar'
                    ),
                    width=12
                ),
            ], justify='around'
        ),
    ])
    return content_

def tabs(pdf, is_mobile):
    if is_mobile:
        tabs_ = tab_mobile_content(pdf)
    else:
        tabs_ = dbc.Tabs(
            [
                dbc.Tab(tab1_content(pdf), label="Summary", tab_style={"margin-left": "auto"}),
                dbc.Tab(tab2_content(pdf), label="Supernovae"),
                dbc.Tab(tab3_content(pdf), label="Variable stars"),
                dbc.Tab(tab4_content(pdf), label="Microlensing"),
                dbc.Tab(tab5_content(pdf), label="Solar System"),
                dbc.Tab(label="GRB", disabled=True)
            ]
        )
    return tabs_

def title(name, is_mobile):
    if is_mobile:
        header = [
            html.Hr(),
            dbc.Row(
                [
                    html.Img(src="/assets/Fink_SecondaryLogo_WEB.png", height='10%', width='10%'),
                    html.H5(children='{}'.format(name[1:]), id='name', style={'color': '#15284F'})
                ]
            ),
        ]
        title_ = html.Div(header)
    else:
        header = [html.Img(src="/assets/Fink_SecondaryLogo_WEB.png", height='10%', width='10%'), html.H1(children='{}'.format(name[1:]), id='name', style={'color': '#15284F'})]
        title_ = dbc.Card(
            dbc.CardHeader(
                [
                    dbc.Row(
                        header
                    )
                ]
            ),
        )
    return title_

@app.callback(
    Output('external_links', 'children'),
    Input('object-data', 'children')
)
def create_external_links(object_data):
    pdf = pd.read_json(object_data)
    ra0 = pdf['i:ra'].values[0]
    dec0 = pdf['i:dec'].values[0]
    buttons = [
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Button('TNS', id='TNS', target="_blank", href='https://www.wis-tns.org/search?ra={}&decl={}&radius=5&coords_unit=arcsec'.format(ra0, dec0), color='link'),
                        dbc.Button('OAC', id='OAC', target="_blank", href='https://api.astrocats.space/catalog?ra={}&dec={}&radius=2'.format(ra0, dec0), color='link'),
                    ], width=12
                )
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Button('SIMBAD', id='SIMBAD', target="_blank", href="http://simbad.u-strasbg.fr/simbad/sim-coo?Coord={}%20{}&Radius=0.08".format(ra0, dec0), color="link"),
                        dbc.Button('NED', id='NED', target="_blank", href="http://ned.ipac.caltech.edu/cgi-bin/objsearch?search_type=Near+Position+Search&in_csys=Equatorial&in_equinox=J2000.0&ra={}&dec={}&radius=1.0&obj_sort=Distance+to+search+center&img_stamp=Yes".format(ra0, dec0), color="link"),
                        dbc.Button('SDSS', id='SDSS', target="_blank", href="http://skyserver.sdss.org/dr13/en/tools/chart/navi.aspx?ra={}&dec={}".format(ra0, dec0), color="link"),
                    ], width=12
                )
            ]
        ),
    ]
    return buttons


def make_item(i):
    # we use this function to make the example items to avoid code duplication
    names = ["&#43; Lightcurve", '&#43; Last alert properties', '&#43; Aladin Lite', '&#43; External links']

    information = html.Div([], id='alert_table')
    lightcurve = html.Div(
        [
            dcc.Graph(
                id='lightcurve_cutouts',
                style={
                    'width': '100%',
                    'height': '15pc'
                },
                config={'displayModeBar': False}
            ),
            html.Div(
                dbc.RadioItems(
                    options=[{'label': k, 'value': k} for k in all_radio_options.keys()],
                    value="Difference magnitude",
                    id="switch-mag-flux",
                    inline=True
                ), style={'display': 'none'}
            )
        ]
    )
    aladin = html.Div(
        [dcc.Markdown('Hit full screen if the display does not work'), visdcc.Run_js(id='aladin-lite-div')],
        style={
            'width': '100%',
            'height': '25pc'
        }
    )
    external = dbc.CardBody(id='external_links')

    to_display = [lightcurve, information, aladin, external]

    header = html.H2(
        dbc.Button(
            html.H5(children=dcc.Markdown('{}'.format(names[i - 1])), style={'color': '#15284F'}),
            color='link',
            id=f"group-{i}-toggle",
            n_clicks=0,
        )
    )
    coll = dbc.Collapse(
        to_display[i - 1],
        id=f"collapse-{i}",
        is_open=False,
    )
    return html.Div([header, html.Hr(), coll])


accordion = html.Div(
    [make_item(1), make_item(2), make_item(3), make_item(4)], className="accordion"
)


@app.callback(
    [Output(f"collapse-{i}", "is_open") for i in range(1, 5)],
    [Input(f"group-{i}-toggle", "n_clicks") for i in range(1, 5)],
    [State(f"collapse-{i}", "is_open") for i in range(1, 5)],
)
def toggle_accordion(n1, n2, n3, n4, is_open1, is_open2, is_open3, is_open4):
    ctx = dash.callback_context

    if not ctx.triggered:
        return False, False, False, False
    else:
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "group-1-toggle" and n1:
        return not is_open1, False, False, False
    elif button_id == "group-2-toggle" and n2:
        return False, not is_open2, False, False
    elif button_id == "group-3-toggle" and n3:
        return False, False, not is_open3, False
    elif button_id == "group-4-toggle" and n4:
        return False, False, False, not is_open4
    return False, False, False, False

@app.callback(
    [
        Output('object-data', 'children'),
        Output('object-upper', 'children'),
        Output('object-uppervalid', 'children'),
        Output('object-sso', 'children'),
    ],
    [
        Input('url', 'pathname'),
    ])
def store_query(name):
    """ Cache query results (data and upper limits) for easy re-use

    https://dash.plotly.com/sharing-data-between-callbacks
    """
    results = client.scan("", "key:key:{}".format(name[1:]), "*", 0, True, True)
    schema_client = client.schema()
    pdfs = format_hbase_output(results, schema_client, group_alerts=False)

    uppers = clientU.scan("", "key:key:{}".format(name[1:]), "*", 0, True, True)
    pdfsU = pd.DataFrame.from_dict(uppers, orient='index')

    uppersV = clientUV.scan("", "key:key:{}".format(name[1:]), "*", 0, True, True)
    pdfsUV = pd.DataFrame.from_dict(uppersV, orient='index')

    payload = pdfs['i:ssnamenr'].values[0]
    results = clientSSO.scan(
        "",
        "key:key:{}_".format(payload),
        "*",
        0, True, True
    )
    schema_client_sso = clientSSO.schema()
    pdfsso = format_hbase_output(
        results, schema_client_sso,
        group_alerts=False, truncated=False, extract_color=False
    )
    return pdfs.to_json(), pdfsU.to_json(), pdfsUV.to_json(), pdfsso.to_json()

def layout(name, is_mobile):
    # even if there is one object ID, this returns  several alerts
    r = requests.post(
        '{}/api/v1/objects'.format(APIURL),
        json={
            'objectId': name[1:],
        }
    )
    pdf = pd.read_json(r.content)

    if is_mobile:
        layout_ = html.Div(
            [
                html.Br(),
                html.Br(),
                dbc.Container(
                    [
                        dbc.Row(
                            [
                                dbc.Col(title(name, is_mobile), width={"size": 12, "offset": 0},),
                            ]
                        ),
                        dbc.Row(
                            [
                                dbc.Col([html.Br(), card_cutouts(is_mobile)], width={"size": 12, "offset": 0},),
                            ]
                        ),
                        dbc.Row(
                            [
                                dbc.Col(tabs(pdf, is_mobile), width=12)
                            ]
                        ),
                        html.Br(),
                        dbc.Row(
                            [
                                dbc.Col(accordion, width=12)
                            ]
                        ),
                    ], id='webinprog', fluid=True, style={'width': '100%'}
                ),
            html.Div(id='object-data', style={'display': 'none'}),
            html.Div(id='object-upper', style={'display': 'none'}),
            html.Div(id='object-uppervalid', style={'display': 'none'}),
            html.Div(id='object-sso', style={'display': 'none'}),
            ],
            className='home',
            style={
                'background-image': 'linear-gradient(rgba(255,255,255,0.6), rgba(255,255,255,0.6)), url(/assets/background.png)',
                'background-size': 'contain'
            }
        )
    else:
        layout_ = html.Div(
            [
                html.Br(),
                html.Br(),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                title(name, is_mobile),
                                html.Br(),
                                html.Div(
                                    [visdcc.Run_js(id='aladin-lite-div')],
                                    style={
                                        'width': '100%',
                                        'height': '25pc'
                                    }
                                ),
                                html.Br(),
                                *download_object_modal(pdf['i:objectId'].values[0])
                            ], width={"size": 3},
                        ),
                        dbc.Col(tabs(pdf, is_mobile), width=8)
                    ],
                    justify="around", no_gutters=True
                ),
                html.Div(id='object-data', style={'display': 'none'}),
                html.Div(id='object-upper', style={'display': 'none'}),
                html.Div(id='object-uppervalid', style={'display': 'none'}),
                html.Div(id='object-sso', style={'display': 'none'}),
            ], className='home', style={'background-image': 'linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(/assets/background.png)', 'background-size': 'contain'}
        )

    return layout_

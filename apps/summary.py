# Copyright 2020 AstroLab Software
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
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import visdcc

import pandas as pd
import requests

from app import app, client, clientU

from apps.cards import card_cutouts, card_sn_scores
from apps.cards import card_id, card_sn_properties
from apps.cards import card_download
from apps.cards import card_variable_plot, card_variable_button
from apps.cards import card_explanation_variable, card_explanation_mulens
from apps.cards import card_mulens_plot, card_mulens_button, card_mulens_param
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
        dbc.Row([
            dbc.Col(card_cutouts(), width=8),
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
            dbc.Col([card_sn_properties(pdf)], width=4)
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

def tabs(pdf):
    tabs_ = dbc.Tabs(
        [
            dbc.Tab(tab1_content(pdf), label="Summary", tab_style={"margin-left": "auto"}),
            dbc.Tab(tab2_content(pdf), label="Supernovae"),
            dbc.Tab(tab3_content(pdf), label="Variable stars"),
            dbc.Tab(tab4_content(pdf), label="Microlensing"),
            dbc.Tab(label="Solar System", disabled=True),
            dbc.Tab(label="GRB", disabled=True)
        ]
    )
    return tabs_

def title(name):
    title_ = dbc.Card(
        dbc.CardHeader(
            [
                dbc.Row([
                    html.Img(src="/assets/Fink_SecondaryLogo_WEB.png", height='20%', width='20%'),
                    html.H1(children='{}'.format(name[1:]), id='name', style={'color': '#15284F'})
                ])
            ]
        ),
    )
    return title_


@app.callback(
    [
        Output('object-data', 'children'),
        Output('object-upper', 'children'),
    ],
    [
        Input('url', 'pathname'),
    ])
def store_query(name):
    """ Cache query results (data and upper limits) for easy re-use

    https://dash.plotly.com/sharing-data-between-callbacks
    """
    results = client.scan("", "key:key:{}".format(name[1:]), "*", 0, True, True)
    pdfs = pd.DataFrame.from_dict(results, orient='index')

    uppers = clientU.scan("", "key:key:{}".format(name[1:]), "*", 0, True, True)
    pdfsU = pd.DataFrame.from_dict(uppers, orient='index')
    return pdfs.to_json(), pdfsU.to_json()

def layout(name):
    # even if there is one object ID, this returns  several alerts
    results = client.scan("", "key:key:{}".format(name[1:]), "*", 0, True, True)
    r = requests.post(
        '{}/api/v1/explorer'.format(APIURL),
        json={
            'objectId': name[1:],
        }
    )
    pdf = pd.read_json(r.content)

    layout_ = html.Div(
        [
            html.Br(),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            title(name),
                            html.Br(),
                            html.Div(
                                [visdcc.Run_js(id='aladin-lite-div')],
                                style={
                                    'width': '100%',
                                    'height': '25pc'
                                }
                            ),
                            card_download(results)
                        ], width={"size": 3},
                    ),
                    dbc.Col(tabs(pdf), width=8)
                ],
                justify="around", no_gutters=True
            ),
            html.Div(id='object-data', style={'display': 'none'}),
            html.Div(id='object-upper', style={'display': 'none'})
        ], className='home', style={'background-image': 'linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(/assets/background.png)', 'background-size': 'contain'}
    )

    return layout_

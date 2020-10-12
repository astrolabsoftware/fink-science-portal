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
import dash_bootstrap_components as dbc
import visdcc

from app import app, client

from apps.cards import card_lightcurve, card_cutouts, card_sn_scores
from apps.cards import card_id, card_fink_added_values, card_sn_properties
from apps.cards import card_download, card_classification
from apps.cards import card_variable_plot, card_variable_button
from apps.cards import card_explanation_variable

dcc.Location(id='url', refresh=False)

def tab1_content(data):
    """ Summary tab

    Parameters
    ----------
    data: java.util.TreeMap
        Results from a HBase client query
    """
    tab1_content_ = html.Div([
        dbc.Row([
            dbc.Col(card_cutouts(data), width=8),
            dbc.Col([
                card_id(data),
                card_classification(data)
            ], width=4)
        ]),
    ])
    return tab1_content_

def tab2_content(data):
    """ Supernova tab
    """
    tab2_content_ = html.Div([
        dbc.Row([
            dbc.Col(card_sn_scores(data), width=8),
            dbc.Col([card_sn_properties(data)], width=4)
        ]),
    ])
    return tab2_content_

def tab3_content(data):
    """ Variable stars tab
    """
    tab3_content_ = html.Div([
        dbc.Row([
            dbc.Col([card_variable_plot(data), html.Br(), card_explanation_variable()], width=8),
            dbc.Col([card_variable_button(data)], width=4)
        ]),
    ])
    return tab3_content_

def tabs(data):
    tabs_ = dbc.Tabs(
        [
            dbc.Tab(tab1_content(data), label="Summary", tab_style={"margin-left": "auto"}),
            dbc.Tab(tab2_content(data), label="Supernovae"),
            dbc.Tab(tab3_content(data), label="Variable stars"),
            dbc.Tab(label="Microlensing", disabled=True),
            dbc.Tab(label="Solar System", disabled=True),
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

def layout(name):
    # even if there is one object ID, this returns  several alerts
    results = client.scan("", "key:key:{}".format(name[1:]), None, 0, True, True)

    layout_ = html.Div(
        [
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
                                    'height': '30pc'
                                }
                            ),
                            card_download(results)
                        ], width={"size": 3},
                    ),
                    dbc.Col(tabs(results), width=8)
                ],
                justify="around", no_gutters=True
            )
        ]
    )

    return layout_

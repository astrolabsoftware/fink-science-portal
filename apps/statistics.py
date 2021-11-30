# Copyright 2021 AstroLab Software
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
from dash.dependencies import Input, Output

from app import app, clientStats

import pandas as pd

dcc.Location(id='url', refresh=False)

@app.callback(
    Output('object-stats', 'children'),
    [
        Input('url', 'pathname'),
    ])
def store_stat_query(name):
    """ Cache query results (data and upper limits) for easy re-use

    https://dash.plotly.com/sharing-data-between-callbacks
    """
    # Query everything from this century
    name = 'ztf_20'

    results = clientStats.scan(
        "",
        "key:key:{}".format(name),
        "*",
        0,
        True,
        True
    )

    # Construct the dataframe
    pdf = pd.DataFrame.from_dict(results, orient='index')
    return pdf.to_json()

@app.callback(
    [Output('stat_row', 'children')],
    [Input('object-stats', 'children')]
)
def create_stat_row(object_stats):
    """ Create links to external website. Used in the mobile app.
    """
    pdf = pd.read_json(object_stats)
    c0 = stat_card(pdf['key:key'].values[0], 'Last night'),
    c1 = stat_card(pdf['basic:raw'].values[0], 'Alerts received'),
    c2 = stat_card(pdf['basic:sci'].values[0], 'Alerts processed'),
    c3 = stat_card(pdf['basic:fields'].values[0], 'Fields visited'),
    c4 = stat_card(pdf['basic:exposures'].values[0], 'Exposures taken')
    row = [
        dbc.Col(width=1), c0, c1, c2, c3, c4, dbc.Col(width=1)
    ]
    return html.Div(row)

def stat_card(value, title):
    """
    """
    col = dbc.Col(
        [
            html.Br(),
            html.H3(html.B(value)),
            html.P(title)
        ], width=2
    )

    return col

def heatmap_content():
    """
    """
    layout_ = html.Div(
        [
            html.Br(),
            dbc.Row(
                [
                    dbc.Col(id='heatmap_stat', width=10)
                ], justify="center", no_gutters=True
            ),
        ],
    )

    return layout_

def timelines():
    """
    """
    layout_ = html.Div(
        [
            html.Br(),
            dbc.Row(
                [
                    dbc.Col(id='evolution', width=10)
                ], justify="center", no_gutters=True
            ),
        ],
    )

    return layout_

def layout(is_mobile):
    """
    """
    if is_mobile:
        tabs_ = None
    else:
        label_style = {"color": "#000"}
        tabs_ = dbc.Tabs(
            [
                dbc.Tab(heatmap_content(), label="Heatmap", label_style=label_style),
                dbc.Tab(timelines(), label="Timelines", label_style=label_style),
                dbc.Tab(label="TNS", disabled=True),
            ]
        )

    if is_mobile:
        layout_ = None
    else:
        layout_ = html.Div(
            [
                html.Br(),
                html.Br(),
                dbc.Row(id='stat_row'),
                dbc.Row(
                    [
                        html.Br(),
                        dbc.Col(tabs_, width=10)
                    ],
                    justify="center", no_gutters=True
                ),
                html.Div(id='object-stats', style={'display': 'none'}),
            ],
            className='home',
            style={
                'background-image': 'linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(/assets/background.png)',
                'background-size': 'contain'
            }
        )

    return layout_

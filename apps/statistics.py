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

import numpy as np
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

    cols = 'basic:raw,basic:sci,basic:fields,basic:exposures,class:Unknown'
    results = clientStats.scan(
        "",
        "key:key:{}".format(name),
        cols,
        0,
        True,
        True
    )

    # Construct the dataframe
    pdf = pd.DataFrame.from_dict(results, orient='index')
    return pdf.to_json()

@app.callback(
    Output('stat_row', 'children'),
    Input('object-stats', 'children')
)
def create_stat_row(object_stats):
    """ Create links to external website. Used in the mobile app.
    """
    pdf = pd.read_json(object_stats)
    n_ = pdf['key:key'].values[-1]
    night = n_[4:8] + '-' + n_[8:10] + '-' + n_[10:12]
    c0 = dbc.Col(
        children=[
            html.Br(),
            html.H3(html.B(night)),
            html.P('Last observing night')
        ], width=2
    )
    c1 = dbc.Col(
        children=[
            html.Br(),
            html.H3(html.B('{:,}'.format(pdf['basic:sci'].values[-1]))),
            html.P('Alerts processed')
        ], width=2
    )
    c2 = dbc.Col(
        children=[
            html.Br(),
            html.H3(html.B('{:,}'.format(np.sum(pdf['basic:sci'].values)))),
            html.P('Since 2019/11/01')
        ], width=2
    )

    n_alert_unclassified = np.sum(pdf['class:Unknown'].values)
    n_alert_classified = np.sum(pdf['basic:sci'].values) - n_alert_unclassified

    c3 = dbc.Col(
        children=[
            html.Br(),
            html.H3(html.B('{:,}'.format(n_alert_classified))),
            html.P('With classification')
        ], width=2
    )

    c4 = dbc.Col(
        children=[
            html.Br(),
            html.H3(html.B('{:,}'.format(n_alert_unclassified))),
            html.P('Without classification')
        ], width=2
    )

    row = [
        dbc.Col(width=1), c0, c1, c2, c3, c4, dbc.Col(width=1)
    ]
    return row

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
    switch = html.Div(
        [
            dbc.Checklist(
                options=[
                    {"label": "Option 1", "value": 1},
                ],
                value=[],
                id="switch-cumulative",
                switch=True,
            ),
        ]
    )
    layout_ = html.Div(
        [
            html.Br(),
            dbc.Row(
                [
                    dbc.Col(generate_col_list(), width=10),
                    dbc.Col(switch, width=2)
                ], justify='around'
            ),
            dbc.Row(
                [
                    dbc.Col(id='evolution', width=10)
                ], justify="center", no_gutters=True
            ),
        ],
    )

    return layout_

def daily_stats():
    """
    """
    layout_ = html.Div(
        [
            html.Br(),
            dbc.Row(dbc.Col(generate_night_list())),
            dbc.Row(
                [
                    dbc.Col(id="hist_sci_raw", width=3),
                    dbc.Col(id="hist_classified", width=3),
                    dbc.Col(id="hist_catalogued", width=3),
                    dbc.Col(id="hist_candidates", width=3)
                ], justify='around'
            ),
            dbc.Row(
                [
                    dbc.Col(id="daily_classification", width=10)
                ], justify='around'
            )
        ],
    )

    return layout_

def generate_night_list():
    """ Generate the list of available nights (last night first)
    """
    results = clientStats.scan(
        "",
        "key:key:ztf_",
        '',
        0,
        True,
        True
    )

    # Construct the dataframe
    pdf = pd.DataFrame.from_dict(results, orient='index')

    labels = pdf['key:key'].apply(lambda x: x[4:8] + '-' + x[8:10] + '-' + x[10:12])

    dropdown = dcc.Dropdown(
        options=[
            *[
                {'label': label, 'value': value}
                for label, value in zip(labels[::-1], pdf['key:key'].values[::-1])
            ]
        ],
        id='dropdown_days',
        searchable=True,
        clearable=True,
        placeholder=labels[-1],
    )

    return dropdown

def generate_col_list():
    """ Generate the list of available columns
    """
    schema = clientStats.schema()
    schema_list = list(schema.columnNames())
    labels = [i.split(':')[1] for i in schema_list]

    dropdown = dcc.Dropdown(
        options=[
            *[
                {'label': label, 'value': value}
                for label, value in zip(labels, schema_list)]
        ],
        id='dropdown_params',
        searchable=True,
        clearable=True,
        placeholder="Choose a columns",
    )

    return dropdown

def get_data_one_night(night):
    """
    """
    cols = 'basic:raw,basic:sci,basic:fields,basic:exposures'
    results = clientStats.scan(
        "",
        "key:key:{}".format(night),
        "*",
        0,
        True,
        True
    )

    # Construct the dataframe
    pdf = pd.DataFrame.from_dict(results, orient='index')

    return pdf

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
                dbc.Tab(daily_stats(), label="Daily statistics", label_style=label_style),
                dbc.Tab(timelines(), label="Timelines", label_style=label_style),
                dbc.Tab(label="TNS", disabled=True),
                dbc.Tab(label="Help", disabled=True),
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

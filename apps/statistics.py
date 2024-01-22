# Copyright 2021-2022 AstroLab Software
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
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

from app import app
from apps.utils import loading
from apps.utils import request_api
from apps.utils import query_and_order_statistics

import numpy as np
import pandas as pd

dcc.Location(id='url', refresh=False)

dic_names = {
    'key:key': 'Observation date in the form ztf_YYYYMMDD',
    'basic:raw': 'Number of alerts received',
    'basic:sci': 'Number of alerts processed (passing quality cuts)',
    'basic:n_g': 'Number of measurements in the g band',
    'basic:n_r': 'Number of measurements in the r band',
    'basic:exposures': 'Number of exposures (30 seconds)',
    'basic:fields': 'Number of fields visited',
    'class:simbad_tot': 'Number of alerts with a counterpart in SIMBAD',
    'class:simbad_gal': 'Number of alerts with a close-by candidate host-galaxy in SIMBAD',
    'class:Solar System MPC': 'Number of alerts with a counterpart in MPC (SSO)',
    'class:SN candidate': 'Number of alerts classified as SN by Fink',
    'class:Early SN Ia candidate': 'Number of alerts classified as early SN Ia by Fink',
    'class:Kilonova candidate': 'Number of alerts classified as Kilonova by Fink',
    'class:Microlensing candidate': 'Number of alerts classified as Microlensing by Fink',
    'class:SN candidate': 'Number of alerts classified as SN by Fink',
    'class:Solar System candidate': 'Number of alerts classified as SSO candidates by Fink',
    'class:Tracklet': 'Number of alerts classified as satelitte glints or space debris by Fink',
    'class:Unknown': 'Number of alerts without classification'
}

stat_doc = """
This page shows various statistics concerning Fink processed data.
These statistics are updated once a day, after the ZTF observing night.
Click on the different tabs to explore data.

## Heatmap

The `Heatmap` tab shows the number of alerts processed by Fink for each night
since the beginning of our operations (2019/11/01). The graph is color coded,
dark cells represent a low number of processed alerts, while bright cells represent
a high number of processed alerts.

## Daily statistics

The `Daily statistics` tab shows various statistics for a given observing night. By default,
we show the last observing night. You can change the night by using the dropdown button.

The first row shows histograms for various indicators:
- Quality cuts: difference between number of received alerts versus number of processed alerts. The difference is simmply due to the quality cuts in Fink selecting only the best quality alerts.
- Classification: Number of alerts that receive a tag by Fink, either from the Machine Learning classifiers, or from a crossmatch with catalogs. The rest is "unclassified".
- External catalogs: Number of alerts that have a counterpart either in the MPC catalog or in the SIMBAD database.
- Selected candidates: Number of alerts for a subset of classes: early type Ia supernova (SN Ia), supernovae or core-collapse (SNe), Kilonova, or Solar System candidates.

The second row shows the number of alerts for all labels in Fink (from classifiers or crossmatch).
Since there are many labels available, do not hesitate to zoom in to see more details!

## Timelines

The `Timelines` tab shows the evolution of several parameters over time. By default, we show the number of
processed alerts per night, since the beginning of operations. You can change the parameter to
show by using the dropdown button. Fields starting with `SIMBAD:` are labels from the SIMBAD database.

Note that you can also show the cumulative number of alerts over time by switching the button on the top right :-)

## REST API

If you want to explore more statistics, or create your own dashboard based on Fink data,
you can do all of these yourself using the REST API. Here is an example using Python:

```python
import requests
import pandas as pd

# get stats for all the year 2021
r = requests.post(
  'https://fink-portal.org/api/v1/statistics',
  json={{
    'date': '2021',
    'output-format': 'json'
  }}
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)
```

Note `date` can be either a given night (YYYYMMDD), month (YYYYMM), year (YYYY), or eveything (empty string).
The schema of the dataframe is the following:

{}

All other fields starting with `class:` are crossmatch from the SIMBAD database.
""".format(pd.DataFrame([dic_names]).T.rename(columns={0: 'description'}).to_markdown())

@app.callback(
    Output('object-stats', 'data'),
    Input('url', 'pathname'),
)
def store_stat_query(name):
    """ Cache query results (data and upper limits) for easy re-use

    https://dash.plotly.com/sharing-data-between-callbacks
    """
    pdf = query_and_order_statistics(
        columns='basic:raw,basic:sci,basic:fields,basic:exposures,class:Unknown',
        drop=False
    )

    return pdf.to_json()

@app.callback(
    Output('stat_row', 'children'),
    Input('object-stats', 'data'),
    prevent_initial_call=True
)
def create_stat_row(object_stats):
    """ Show basic stats. Used in the desktop app.
    """
    pdf = pd.read_json(object_stats)
    c0_, c1_, c2_, c3_, c4_ = create_stat_generic(pdf)

    return [
        dbc.Col(
            dbc.Row(
                [
                    dbc.Col(c0_, md=6),
                    dbc.Col(c1_, md=6),
                ],
                style={
                    'border-left': '1px solid #c4c0c0',
                    'border-bottom': '1px solid #c4c0c0',
                    'border-right': '1px solid #c4c0c0',
                    'border-radius': '0px 0px 25px 25px',
                    "text-align": "center"
                }
            ),
            md=5,
        ),
        dbc.Col(c2_, md=3, style={'text-align': 'center'}),
        dbc.Col(c3_, md=2, style={'text-align': 'center'}),
        dbc.Col(c4_, md=2, style={'text-align': 'center'}),
    ]

@app.callback(
    Output('stat_row_mobile', 'children'),
    Input('object-stats', 'data'),
    prevent_initial_call=True
)
def create_stat_row(object_stats):
    """ Show basic stats. Used in the mobile app.
    """
    pdf = pd.read_json(object_stats)
    c0_, c1_, c2_, c3_, c4_ = create_stat_generic(pdf)

    rowify = lambda x: dbc.Row(
        children=[dbc.Col(children=x, width=10)],
        justify='center',
        style={
            "text-align": "center"
        }
    )

    row = [
        html.Br(), html.Br(),
        rowify(c0_),
        html.Br(),
        rowify(c1_),
        html.Br(),
        rowify(c2_),
        html.Br(),
        rowify(c3_),
        html.Br(),
        rowify(c4_),
        html.Br(), html.Br(),
        dbc.Card(
            dbc.CardBody(
                dcc.Markdown('_Connect with a bigger screen to explore more statistics_')
            )
        ),
    ]

    return row

def create_stat_generic(pdf):
    """ Show basic stats. Used in the mobile app.
    """
    n_ = pdf['key:key'].values[-1]
    night = n_[4:8] + '-' + n_[8:10] + '-' + n_[10:12]

    c0 = [
        html.H3(html.B(night)),
        html.P('Last ZTF observing night'),
    ]

    c1 = [
        html.H3(html.B('{:,}'.format(pdf['basic:sci'].values[-1]))),
        html.P('Alerts processed'),
    ]

    c2 = [
        html.H3(html.B('{:,}'.format(np.sum(pdf['basic:sci'].values)))),
        html.P('Since 2019/11/01')
    ]

    mask = ~np.isnan(pdf['class:Unknown'].values)
    n_alert_unclassified = np.sum(pdf['class:Unknown'].values[mask])
    n_alert_classified = np.sum(pdf['basic:sci'].values) - n_alert_unclassified

    c3 = [
        html.H3(html.B('{:,}'.format(n_alert_classified))),
        html.P('With classification')
    ]

    c4 = [
        html.H3(html.B('{:,}'.format(n_alert_unclassified))),
        html.P('Without classification')
    ]

    return c0, c1, c2, c3, c4

def heatmap_content():
    """
    """

    layout_ = html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        dmc.Skeleton(style={'width': '100%', 'height': '30pc'}, className="mt-3"),
                        id='heatmap_stat'
                    )
                ], justify="center", className="g-0"
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
                    {"label": "Cumulative", "value": 1},
                    {"label": "Percentage", "value": 2},
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
                    dbc.Col(generate_col_list(), md=10),
                    dbc.Col(switch, md=2)
                ], justify='around'
            ),
            loading(dbc.Row(
                [
                    dbc.Col(id='evolution')
                ], justify="center", className="g-0"
            )),
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
            loading(dbc.Row(
                [
                    dbc.Col(id="hist_sci_raw", md=3),
                    dbc.Col(id="hist_classified", md=3),
                    dbc.Col(id="hist_catalogued", md=3),
                    dbc.Col(id="hist_candidates", md=3)
                ], justify='around'
            )),
            loading(dbc.Row(
                [
                    dbc.Col(id="daily_classification")
                ], justify='around'
            ))
        ],
    )

    return layout_

def generate_night_list():
    """ Generate the list of available nights (last night first)
    """
    pdf = query_and_order_statistics(columns='', drop=False)

    labels = list(pdf['key:key'].apply(lambda x: x[4:8] + '-' + x[8:10] + '-' + x[10:12]))

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
    r = request_api(
        '/api/v1/statistics',
        json={
            'output-format': 'json',
            'schema': True
        }
    )
    pdf = pd.read_json(r)
    schema_list = list(pdf['schema'])

    labels = [
        i.replace('class', 'SIMBAD')
        if i not in dic_names
        else dic_names[i]
        for i in schema_list
    ]

    # Sort them for better readability
    idx = np.argsort(labels)
    labels = np.array(labels)[idx]
    schema_list = np.array(schema_list)[idx]

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
    """ Get the statistics for one night
    """
    cols = 'basic:raw,basic:sci,basic:fields,basic:exposures'

    r = request_api(
        '/api/v1/statistics',
        json={
            'date': night,
            'output-format': 'json',
            'columns': ''
        }
    )

    # Format output in a DataFrame
    pdf = pd.read_json(r)

    return pdf

def layout():
    """
    """
    label_style = {"color": "#000"}
    tabs_ = dbc.Tabs(
        [
            dbc.Tab(heatmap_content(), label="Heatmap", label_style=label_style),
            dbc.Tab(daily_stats(), label="Daily statistics", label_style=label_style),
            dbc.Tab(timelines(), label="Timelines", label_style=label_style),
            dbc.Tab(label="TNS", disabled=True),
            dbc.Tab(
                dbc.Card(
                    dbc.CardBody(
                        dcc.Markdown(stat_doc)
                    )
                ),
                label="Help",
                label_style=label_style
            ),
        ]
    )

    layout_ = dbc.Container(
        [
            dbc.Row(id='stat_row', className="mt-3", justify="center"),
            dbc.Row(
                [
                    dbc.Col(tabs_),
                ],
                justify="center", className="mt-3"
            ),
            dcc.Store(id='object-stats'),
        ],
        fluid='lg',
    )

    return layout_

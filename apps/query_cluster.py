# Copyright 2022 AstroLab Software
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
from dash import html, dcc, Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

from app import app

import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date

from fink_utils.xmatch.simbad import get_simbad_labels

simbad_types = get_simbad_labels('old_and_new')
simbad_types = sorted(simbad_types, key=lambda s: s.lower())

tns_types = pd.read_csv('assets/tns_types.csv', header=None)[0].values
tns_types = sorted(tns_types, key=lambda s: s.lower())

@app.callback(
    Output("timeline_data_transfer", "children"),
    [
        Input('trans_datasource', 'value'),
        # Input('trans_filters', 'value')
    ]
)
def timeline_data_transfer(trans_datasource):
    """
    """
    trans_filters, trans_content = None, None
    active_ = np.where(
        np.array([trans_datasource, trans_filters, trans_content]) != None
    )
    timeline = dmc.Timeline(
        active=len(active_[0]),
        bulletSize=15,
        lineWidth=2,
        children=[
            dmc.TimelineItem(
                title="Select data source",
                children=[
                    dmc.Text(
                        [
                            "Choose between ",
                            dmc.Anchor("ZTF", href="https://www.ztf.caltech.edu/", size="sm"),
                            " and",
                            dmc.Anchor(" DESC/Elasticc", href="https://portal.nersc.gov/cfs/lsst/DESC_TD_PUBLIC/ELASTICC/", size="sm"),
                        ],
                        color="dimmed",
                        size="sm",
                    ),
                ],
            ),
            dmc.TimelineItem(
                title="Filter alerts",
                children=[
                    dmc.Text(
                        [
                            "Select date range, alert classes, or more.",
                        ],
                        color="dimmed",
                        size="sm",
                    ),
                ],
            ),
            dmc.TimelineItem(
                title="Select content",
                lineVariant="dashed",
                children=[
                    dmc.Text(
                        [
                            "Complete alert packet, or a subset.",
                        ],
                        color="dimmed",
                        size="sm",
                    ),
                ],
            ),
            dmc.TimelineItem(
                [
                    dmc.Text(
                        [
                            "Review what you will get",
                        ],
                        color="dimmed",
                        size="sm",
                    ),
                ],
                title="Summary",
            ),
        ],
    )

    return timeline

@app.callback(
    Output("filter_tab", "children"),
    [
        Input('trans_datasource', 'value'),
    ]
)
def filter_tab(trans_datasource):
    """
    """
    if trans_datasource == 'ztf':
        datepicker = html.Div(
            [
                dmc.DateRangePicker(
                    id="date-range-picker",
                    label="Date Range",
                    description="Pick up start and stop dates (included), with a maximum of 2 weeks allowed.",
                    minDate=date(2019, 11, 1),
                    maxDate=date.today(),
                    value=[datetime.now().date() - timedelta(days=7), datetime.now().date()],
                    style={"width": 500},
                    hideOutsideDates=True,
                    amountOfMonths=2,
                    allowSingleDateInRange=True
                ),
                dmc.Space(h=10),
                dmc.MultiSelect(
                    label="Alert class",
                    placeholder="Select all you like!",
                    id="framework-multi-select",
                    value=None,
                    data = [
                        {'label': 'All classes', 'value': 'allclasses'},
                        {'label': 'Unknown', 'value': 'Unknown'},
                        {'label': '(Fink) Early Supernova Ia candidates', 'value': 'Early SN Ia candidate'},
                        {'label': '(Fink) Supernova candidates', 'value': 'SN candidate'},
                        {'label': '(Fink) Kilonova candidates', 'value': 'Kilonova candidate'},
                        {'label': '(Fink) Microlensing candidates', 'value': 'Microlensing candidate'},
                        {'label': '(Fink) Solar System (MPC)', 'value': 'Solar System MPC'},
                        {'label': '(Fink) Solar System (candidates)', 'value': 'Solar System candidate'},
                        {'label': '(Fink) Tracklet (space debris & satellite glints)', 'value': 'Tracklet'},
                        {'label': '(Fink) Ambiguous', 'value': 'Ambiguous'},
                        *[{'label': '(TNS) ' + simtype, 'value': '(TNS) ' + simtype} for simtype in tns_types],
                        *[{'label': '(SIMBAD) ' + simtype, 'value': '(SIMBAD) ' + simtype} for simtype in simbad_types]
                    ],
                    searchable=True,
                    style={"width": 500, "marginBottom": 10},
                ),
                dmc.Space(h=10),
                dmc.Textarea(
                    label="Extra conditions",
                    description=[
                        "One condition per line, ending with semi-colon. See ",
                        dmc.Anchor("here", href="https://fink-portal.org/api/v1/columns", size="sm"),
                        " for field description.",
                    ],
                    placeholder="e.g. magpsf > 19.5;",
                    style={"width": 500},
                    autosize=True,                ),
            ]
        )
        tab = html.Div(
            [
                html.Br(),
                html.Br(),
                dmc.Divider(variant="solid", label='Filters'),
                datepicker,
            ]
        )
        return tab
    elif trans_datasource == 'elasticc':
        return html.Div(trans_datasource)
    else:
        return html.Div()

def query_builder():
    """ Build iteratively the query based on user inputs.
    """
    tab1 = html.Div(
        [
            html.Br(),
            html.Br(),
            dmc.Divider(variant="solid", label='Data Source'),
            dmc.RadioGroup(
                id="trans_datasource",
                data=[
                    {"value": "ztf", "label": "ZTF"},
                    {"value": "elasticc", "label": "ELASTiCC"},
                ],
                value=None,
                label="Choose the type of alerts you want to retrieve",
                size="sm",
            ),
        ]
    )
    query = html.Div(
        [
            tab1,
            html.Div(id='filter_tab')
            # Filter: Div based on previous response
            # Content: Div based on previous response
            # Result: Div based on previous response. Should contain a
            # summary + instruction to get data via Kafka.
        ]
    )

    return query

def estimate_alert_number():
    """ Callback to estimate the number of alerts to be transfered
    """
    pass

def layout(is_mobile):
    """ Layout for the data transfer service
    """
    layout_ = html.Div(
        [
            html.Br(),
            html.Br(),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Br(),
                            html.Br(),
                            html.Div(id='timeline_data_transfer'),
                            html.Br(),
                        ], width={"size": 3},
                    ),
                    dbc.Col(query_builder(), width=8)
                ],
                justify="around", className="g-0"
            ),
        ], className='home', style={'background-image': 'linear-gradient(rgba(255,255,255,0.9), rgba(255,255,255,0.9)), url(/assets/background.png)', 'background-size': 'cover'}
    )

    return layout_
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
        Input('filter_tab', 'children'),
        Input('content_tab', 'children'),
        Input('summary_tab', 'children')
    ]
)
def timeline_data_transfer(trans_datasource, date_range_picker, trans_content, summary_content):
    """
    """
    active_ = np.where(
        np.array([trans_datasource, date_range_picker, trans_content, summary_content]) != None
    )[0]
    tmp = len(active_) - 1
    nsteps = 0 if tmp < 0 else tmp
    timeline = dmc.Timeline(
        active=nsteps,
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
    ], prevent_initial_call=True
)
def filter_tab(trans_datasource):
    """ Section containing filtering options
    """
    if trans_datasource == 'ztf':
        options = html.Div(
            [
                dmc.DateRangePicker(
                    id="date-range-picker",
                    label="Date Range",
                    description="Pick up start and stop dates (included), with a maximum of 14 nights allowed.",
                    minDate=date(2019, 11, 1),
                    maxDate=date.today(),
                    value=None,
                    style={"width": 500},
                    hideOutsideDates=True,
                    amountOfMonths=2,
                    allowSingleDateInRange=True,
                    required=True
                ),
                dmc.Space(h=10),
                dmc.MultiSelect(
                    label="Alert class",
                    description="Select all classes you like!",
                    placeholder="start typing...",
                    id="class_select",
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
                    style={"width": 500},
                ),
                dmc.Space(h=10),
                dmc.Textarea(
                    id="extra_cond",
                    label="Extra conditions",
                    description=[
                        "One condition per line (SQL syntax), ending with semi-colon. See ",
                        dmc.Anchor("here", href="https://fink-portal.org/api/v1/columns", size="xs"),
                        " for field description.",
                    ],
                    placeholder="e.g. magpsf > 19.5;",
                    style={"width": 500},
                    autosize=True,
                    minRows=2,              ),
            ]
        )
        tab = html.Div(
            [
                dmc.Space(h=10),
                dmc.Divider(variant="solid", label='Filters'),
                options,
            ]
        )
        return tab
    elif trans_datasource == 'elasticc':
        return html.Div("Under construction...")
    else:
        return html.Div()

@app.callback(
    Output("content_tab", "children"),
    [
        Input('date-range-picker', 'value')
    ], prevent_initial_call=True
)
def content_tab(date_range_picker):
    """ Section containing filtering options
    """
    if date_range_picker is not None:
        tab = html.Div(
            [
                dmc.Space(h=10),
                dmc.Divider(variant="solid", label='Alert content'),
                dmc.RadioGroup(
                    id="trans_content",
                    data=[
                        {"value": "Full packet", "label": "Full packet"},
                        {"value": "Lightcurve", "label": "Lightcurve"},
                        {"value": "Cutouts", "label": "Cutouts"},
                    ],
                    value=None,
                    label="Choose the content you want to retrieve",
                    size="sm",
                ),
            ]
        )
        return tab
    else:
        PreventUpdate

@app.callback(
    Output("summary_tab", "children"),
    [
        Input('trans_content', 'value'),
    ],
    [
        State('trans_datasource', 'value'),
        State('date-range-picker', 'value'),
        State('class_select', 'value'),
        State('extra_cond', 'value'),
    ],
    prevent_initial_call=True
)
def summary_tab(trans_content, trans_datasource, date_range_picker, class_select, extra_cond):
    """ Section containing summary
    """
    if trans_content is None:
        PreventUpdate

    tab = html.Div(
        [
            dmc.Text('Source: {}'.format(trans_datasource)),
            dmc.Text('Dates: {} - {}'.format(*date_range_picker)),
            dmc.Text('Classe(s): {}'.format(class_select)),
            dmc.Text('Conditions: {}'.format(extra_cond)),
            dmc.Text('Content: {}'.format(trans_content)),
        ]

    )
    return tab

def query_builder():
    """ Build iteratively the query based on user inputs.
    """
    tab = html.Div(
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
                size="md",
                color='orange'
            ),
        ]
    )
    return tab

def estimate_alert_number():
    """ Callback to estimate the number of alerts to be transfered
    """
    pass

def layout(is_mobile):
    """ Layout for the data transfer service
    """
    qb = query_builder()
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
                    dbc.Col(
                        [
                            qb,
                            html.Div(None, id='filter_tab'),
                            html.Div(None, id='content_tab'),
                            html.Div(None, id='summary_tab')
                        ],
                        width=8)
                ],
                justify="around", className="g-0"
            ),
        ], className='home', style={'background-image': 'linear-gradient(rgba(255,255,255,0.9), rgba(255,255,255,0.9)), url(/assets/background.png)', 'background-size': 'cover'}
    )

    return layout_
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

import numpy as np

def timeline_data_transfer(trans_datasource, trans_filters, trans_content):
    """
    """
    active_ = np.where(
        np.array([trans_datasource, trans_filters, trans_content]) != None
    )
    timeline = dmc.Timeline(
        active=len(active_),
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
                            dmc.Anchor("DESC/Elasticc", href="https://portal.nersc.gov/cfs/lsst/DESC_TD_PUBLIC/ELASTICC/", size="sm"),
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
                            "Full fledge packet, or a subset.",
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

def query_builder():
    """ Build iteratively the query based on user inputs.
    """
    query = html.Div(
        [
            # Data source
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
                            # html.Div(id="timeline_data_transfer"),
                            timeline_data_transfer(1, None, None),
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
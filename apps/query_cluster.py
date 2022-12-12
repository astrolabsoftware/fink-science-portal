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

def timeline_data_transfer(trans_datasource, trans_filters, trans_content):
    """
    """
    active = np.where(
        np.array([trans_datasource, trans_filters, trans_content]) != None
    )
    dmc.Timeline(
        active=active,
        bulletSize=15,
        lineWidth=2,
        children=[
            dmc.TimelineItem(
                title="New Branch",
                children=[
                    dmc.Text(
                        [
                            "You've created new branch ",
                            dmc.Anchor("fix-notification", href="#", size="sm"),
                            " from master",
                        ],
                        color="dimmed",
                        size="sm",
                    ),
                ],
            ),
            dmc.TimelineItem(
                title="Commits",
                children=[
                    dmc.Text(
                        [
                            "You've pushed 23 commits to ",
                            dmc.Anchor("fix-notification", href="#", size="sm"),
                        ],
                        color="dimmed",
                        size="sm",
                    ),
                ],
            ),
            dmc.TimelineItem(
                title="Pull Request",
                lineVariant="dashed",
                children=[
                    dmc.Text(
                        [
                            "You've submitted a pull request ",
                            dmc.Anchor(
                                "Fix incorrect notification message (#178)",
                                href="#",
                                size="sm",
                            ),
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
                            dmc.Anchor(
                                "Ann Marie Ward",
                                href="https://github.com/AnnMarieW",
                                size="sm",
                            ),
                            " left a comment on your pull request",
                        ],
                        color="dimmed",
                        size="sm",
                    ),
                ],
                title="Code Review",
            ),
        ],
    )

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
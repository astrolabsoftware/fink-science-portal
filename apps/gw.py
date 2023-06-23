# Copyright 2023 AstroLab Software
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
from dash import html, dcc, Input, Output, State, callback_context as ctx, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash_iconify import DashIconify

import io
import requests
import pandas as pd
from urllib.request import urlopen, URLError

from app import app, APIURL

@app.callback(
    Output("notify-container", "children"),
    [
        Input("gw-loading-button", "n_clicks"),
        Input('superevent_name', 'value'),
    ],
    prevent_initial_call=True,
)
def notify_load(nc1, superevent_name):
    """ Notify the user a query has been launched
    """
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if button_id != "gw-loading-button":
        raise PreventUpdate
    else:
        return dmc.Notification(
            id="my-notification",
            title=superevent_name,
            message="The process has started.",
            loading=True,
            color="orange",
            action="show",
            autoClose=False,
        )

@app.callback(
    [
        Output("gw-notification", "action"),
        Output("gw-notification", "color"),
        Output("gw-notification", "title"),
        Output("gw-notification", "message"),
        Output("gw-notification", "loading"),
        Output("gw-notification", "autoClose")
    ],
    [
        Input('superevent_name', 'value'),
        Input("request-status", "data"),
    ],
    prevent_initial_call=True,
)
def notify_results(superevent_name, status):
    if status == 'done':
        return "update", "green", superevent_name, "The process has completed", False, 5000
    elif status == 'error':
        return "show", "red", superevent_name, "Could not find an event named {} on GraceDB".format(superevent_name), False, False
    else:
        raise PreventUpdate

@app.callback(
    [
        Output("gw-data", "data"),
        Output("request-status", "data"),
    ],
    [
        Input('gw-loading-button', 'n_clicks'),
        Input('credible_level', 'value'),
        Input('superevent_name', 'value'),
    ],
    State("request-status", "data"),
    prevent_initial_call=True
)
def query_bayestar(submit, credible_level, superevent_name, status):
    """
    """
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if button_id != "gw-loading-button":
        return no_update, ''

    if superevent_name == '':
        raise PreventUpdate

    # Query Fink
    fn = 'https://gracedb.ligo.org/api/superevents/{}/files/bayestar.fits.gz'.format(superevent_name)
    try:
        data = urlopen(fn).read()
    except URLError:
        return pd.DataFrame().to_json(), 'error'

    r = requests.post(
        '{}/api/v1/bayestar'.format(APIURL),
        json={
            'bayestar': str(data),
            'credible_level': float(credible_level),
            'output-format': 'json'
        }
    )

    pdf = pd.read_json(io.BytesIO(r.content))

    return pdf.to_json(), "done"


def layout(is_mobile):
    """ Layout for the GW counterpart search
    """
    description = [
        "Enter an event ID from the ",
        dmc.Anchor("O3", href="https://gracedb.ligo.org/superevents/public/O3/", size="xs", target="_blank"),
        " or ",
        dmc.Anchor("O4", href="https://gracedb.ligo.org/superevents/public/O4/", size="xs", target="_blank"),
        " runs."
    ]
    supervent_name = html.Div(
        [
            dmc.Space(h=10),
            dmc.Divider(variant="solid", label='Superevent'),
            dmc.Space(h=10),
            dmc.TextInput(
                id="superevent_name",
                label=None,
                description=description,
                placeholder="e.g. S200219ac",
            ),
        ], id='superevent_name_selector'
    )

    credible_level = html.Div(
        [
            dmc.Space(h=10),
            dmc.Divider(variant="solid", label='Credible level'),
            dmc.Space(h=10),
            dmc.NumberInput(
                label=None,
                description="From 0 (most likely) to 1 (least likely)",
                value=0.2,
                precision=2,
                min=0.0,
                max=1.0,
                step=0.05,
                id='credible_level'
            ),
        ], id='credible_level_selector'
    )

    submit_gw = dmc.Center(
        [
            dmc.Button(
                "Search for alerts matching",
                id="gw-loading-button",
                leftIcon=DashIconify(icon="fluent:database-plug-connected-20-filled"),
                loaderProps={'variant': 'dots', 'color': 'orange'},
                variant="outline",
                color='indigo'
            ),
        ]
    )

    if is_mobile:
        # width_right = 10
        # title = dbc.Row(
        #     children=[
        #         dmc.Space(h=20),
        #         dmc.Stack(
        #             children=[
        #                 dmc.Title(
        #                     children='Fink Data Transfer',
        #                     style={'color': '#15284F'}
        #                 ),
        #                 dmc.Anchor(
        #                     dmc.ActionIcon(
        #                         DashIconify(icon="fluent:question-16-regular", width=20),
        #                         size=30,
        #                         radius="xl",
        #                         variant="light",
        #                         color='orange',
        #                     ),
        #                     href="https://fink-broker.org/2023-01-17-data-transfer",
        #                     target="_blank"
        #                 ),
        #             ],
        #             align="center",
        #             justify="center",
        #         )
        #     ]
        # )
        # left_side = html.Div(id='timeline_data_transfer', style={'display': 'none'})
        # style = {
        #     'background-image': 'linear-gradient(rgba(255,255,255,0.3), rgba(255,255,255,0.3)), url(/assets/background.png)'
        # }
        pass
    else:
        width_right = 8
        title = html.Div()
        left_side = dbc.Col(
            [
                html.Br(),
                html.Br(),
                supervent_name,
                html.Br(),
                credible_level,
                html.Br(),
                html.Br(),
                submit_gw,
                dcc.Store(id='gw-data'),
                dcc.Store(id='request-status', data='')
            ], width={"size": 3},
        )
        style={
            'background-image': 'linear-gradient(rgba(255,255,255,0.3), rgba(255,255,255,0.3)), url(/assets/background.png)',
            'background-size': 'cover'
        }

    layout_ = dmc.NotificationsProvider(
        html.Div(
            [
                html.Br(),
                html.Br(),
                title,
                dbc.Row(
                    [
                        left_side,
                        dbc.Col(
                            [
                                html.Br(),
                                html.Br(),
                            ],
                            width=width_right)
                    ],
                    justify="around", className="g-0"
                ),
                html.Br(),
                html.Div("notify-container"),
                dmc.Notification(
                    id="gw-notification",
                    title="Process initiated",
                    message="The process has started.",
                    loading=True,
                    color="orange",
                    action="hide",
                    autoClose=False,
                )
            ], className='home', style={'background-image': 'linear-gradient(rgba(255,255,255,0.9), rgba(255,255,255,0.9)), url(/assets/background.png)', 'background-size': 'cover'}
        )
    )

    return layout_
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
from dash import html, dcc, Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash_iconify import DashIconify


def layout(is_mobile):
    """ Layout for the GW counterpart search
    """
    description = [
        "Enter a event ID from the ",
        dmc.Anchor("O3", href="https://gracedb.ligo.org/superevents/public/O3/", size="xs", target="_blank"),
        " or ",
        dmc.Anchor("O4", href="https://gracedb.ligo.org/superevents/public/O4/", size="xs", target="_blank"),
        " runs."
    ]
    selector = html.Div(
        [
            dmc.Space(h=10),
            dmc.Divider(variant="solid", label='Superevents'),
            dmc.TextInput(
                id="superevent_name",
                label=None,
                description=description,
                placeholder="e.g. S200219ac",
            ),
        ], id='gw_selector'
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
                selector,
                html.Br(),
            ], width={"size": 3},
        )
        style={
            'background-image': 'linear-gradient(rgba(255,255,255,0.3), rgba(255,255,255,0.3)), url(/assets/background.png)',
            'background-size': 'cover'
        }

    layout_ = html.Div(
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
        ], className='home', style={'background-image': 'linear-gradient(rgba(255,255,255,0.9), rgba(255,255,255,0.9)), url(/assets/background.png)', 'background-size': 'cover'}
    )

    return layout_
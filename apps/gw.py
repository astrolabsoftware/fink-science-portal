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
from dash import html, dcc, Input, Output, State, callback_context as ctx, no_update, dash_table
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash_iconify import DashIconify

import io
import requests
import pandas as pd
from urllib.request import urlopen, URLError

from app import app, APIURL
from apps.utils import markdownify_objectid

# @app.callback(
#     [
#         Output("gw-notification", "action"),
#         Output("gw-notification", "color"),
#         Output("gw-notification", "title"),
#         Output("gw-notification", "message"),
#         Output("gw-notification", "loading"),
#         Output("gw-notification", "autoClose"),
#         Output("request-status", "data", allow_duplicate=True)
#     ],
#     [
#         Input('superevent_name', 'value'),
#         Input("request-status", "data"),
#     ],
#     prevent_initial_call=True,
# )
# def notify_results(superevent_name, status):
#     if status == 'done':
#         return "update", "green", superevent_name, "The process has completed", False, 5000, ''
#     elif status == 'error':
#         return "show", "red", superevent_name, "Could not find an event named {} on GraceDB".format(superevent_name), False, 5000, ''
#     else:
#         raise PreventUpdate

@app.callback(
    Output("gw-data", "children"),
    [
        Input('gw-loading-button', 'n_clicks'),
        Input('credible_level', 'value'),
        Input('superevent_name', 'value'),
    ],
    prevent_initial_call=True
)
def query_bayestar(submit, credible_level, superevent_name):
    """
    """
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if button_id != "gw-loading-button":
        # return no_update, ''
        return no_update

    if superevent_name == '':
        raise PreventUpdate

    # Query Fink
    fn = 'https://gracedb.ligo.org/api/superevents/{}/files/bayestar.fits.gz'.format(superevent_name)
    try:
        data = urlopen(fn).read()
    except URLError:
        return "error"

    r = requests.post(
        '{}/api/v1/bayestar'.format(APIURL),
        json={
            'bayestar': str(data),
            'credible_level': float(credible_level),
            'output-format': 'json'
        }
    )

    pdf = pd.read_json(io.BytesIO(r.content))

    # return pdf.to_json(), "done"
    return pdf.to_json()

def populate_result_table_gw(data, columns, is_mobile):
    """ Define options of the results table, and add data and columns
    """
    if is_mobile:
        page_size = 5
        markdown_options = {'link_target': '_self'}
    else:
        page_size = 10
        markdown_options = {'link_target': '_blank'}
    table = dash_table.DataTable(
        data=data,
        columns=columns,
        id='result_table_gw',
        page_size=page_size,
        style_as_list_view=True,
        sort_action="native",
        filter_action="native",
        markdown_options=markdown_options,
        fixed_columns={'headers': True, 'data': 1},
        style_data={
            'backgroundColor': 'rgb(248, 248, 248, .7)'
        },
        style_table={'maxWidth': '100%'},
        style_cell={'padding': '5px', 'textAlign': 'center', 'overflow': 'hidden'},
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(248, 248, 248, .7)'
            }
        ],
        style_header={
            'backgroundColor': 'rgb(230, 230, 230)',
            'fontWeight': 'bold'
        }
    )
    return table

@app.callback(
    [
        Output("gw-table", "children"),
        Output("gw-loading-button", "children"),
    ],
    [
        Input('gw-loading-button', 'n_clicks'),
        Input('gw-data', 'children'),
        Input('superevent_name', 'value'),
    ],
    prevent_initial_call=True
)
def show_table(nclick, gw_data, superevent_name):
    """
    """
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if button_id != "gw-loading-button":
        raise PreventUpdate

    if gw_data == "error":
        return dmc.Alert(
            "Could not find an event named {} on GraceDB".format(superevent_name),
            title='Oops!',
            color="red",
            withCloseButton=True
        ), no_update

    pdf = pd.read_json(gw_data)
    if pdf.empty:
        return dmc.Alert(
            "No counterparts found in Fink for the event named {}".format(superevent_name),
            title='Oops!',
            color="red",
            withCloseButton=True
        ), no_update
    else:
        colnames_to_display = {
            'i:objectId': 'objectId',
            'd:classification': 'Classification',
            'd:nalerthist': 'Number of measurements',
            'v:gw_lapse': 'Delay (day)',
        }
        pdf['v:gw_lapse'] = pdf['i:jdstarthist'] - pdf['v:jdstartgw']
        pdf['i:objectId'] = pdf['i:objectId'].apply(markdownify_objectid)
        data = pdf.sort_values('v:gw_lapse', ascending=True).to_dict('records')
        columns = [
            {
                'id': c,
                'name': colnames_to_display[c],
                'type': 'text',
                # 'hideable': True,
                'presentation': 'markdown',
            } for c in colnames_to_display.keys()
        ]

        table = populate_result_table_gw(data, columns, is_mobile=False)

        return table, no_update

def card_explanation():
    """ Explain what is used to fit for variable stars
    """
    msg = """
    Fill the fields on the right (or leave default), and press `Fit data` to
    perform a time series analysis of the data:

    - Number of base terms: number of frequency terms to use for the base model common to all bands (default=1)
    - Number of band terms: number of frequency terms to use for the residuals between the base model and each individual band (default=1)

    The fit is done using [gatspy](https://zenodo.org/record/47887)
    described in [VanderPlas & Ivezic (2015)](https://ui.adsabs.harvard.edu/abs/2015ApJ...812...18V/abstract).
    We use a multiband periodogram (LombScargleMultiband) to find the best period.
    Alternatively, you can manually set the period in days.

    The title of the plot will give you the fitted period, and a score for the fit.
    The score is between 0 (poor fit) and 1 (excellent fit).
    """
    card = dmc.Accordion(
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl("How to make a fit?"),
                    dmc.AccordionPanel(dcc.Markdown(msg)),
                ],
                value="info"
            ),
        ], value='info'
    )
    return card

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

    submit_gw = dmc.LoadingOverlay(
        dmc.Center(
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
        ),
        loaderProps={"variant": "dots", "color": "orange", "size": "xl"}
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
                # dcc.Store(id='gw-data'),
                html.Div(id='gw-data', style={'display': 'none'}),
                # dcc.Store(id='request-status', data='')
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
                        dmc.LoadingOverlay(
                            dmc.Paper(
                                [
                                    html.Br(),
                                    dbc.Container(id='gw-table'),
                                    html.Br(),
                                    card_explanation()
                                ], radius='xl', p='md', shadow='xl', withBorder=True
                            ), loaderProps={"variant": "dots", "color": "orange", "size": "xl"},
                        ),
                        width=width_right
                    )
                ],
                justify="around", className="g-0"
            ),
            html.Br()
        ], className='home', style={'background-image': 'linear-gradient(rgba(255,255,255,0.9), rgba(255,255,255,0.9)), url(/assets/background.png)', 'background-size': 'cover'}
    )

    return layout_
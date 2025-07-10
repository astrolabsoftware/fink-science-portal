# Copyright 2025 AstroLab Software
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
import dash_mantine_components as dmc
import textwrap
import base64
import datetime
import io

import numpy as np
import pandas as pd
import requests
import yaml
from dash import Input, Output, State, html, dcc, ctx, callback, no_update, dash_table
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from astropy.io import votable

from fink_utils.xmatch.simbad import get_simbad_labels

from app import app
from apps.mining.utils import (
    estimate_size_gb_elasticc,
    estimate_size_gb_ztf,
    submit_spark_job,
    upload_file_hdfs,
    estimate_alert_number_ztf,
    estimate_alert_number_elasticc,
)
from apps.utils import extract_configuration
from apps.utils import format_field_for_data_transfer
from apps.utils import create_datatransfer_schema_table
from apps.utils import create_datatransfer_livestream_table
from apps.utils import query_and_order_statistics
from apps.plotting import COLORS_ZTF

import pkgutil

import fink_filters.ztf.livestream as ffz

args = extract_configuration("config.yml")
APIURL = args["APIURL"]

min_step = 0
max_step = 4

MAX_ROW = 100000

def upload_catalog():
    """
    """
    return html.Div(
        children=[
            dcc.Upload(
                id='upload-data',
                children=html.Div([
                    'Drag and Drop or ',
                    html.A('Select Files '),
                    "(csv, parquet, or votable)"
                ]),
                style={
                    'width': '100%',
                    'height': '60px',
                    'lineHeight': '60px',
                    'borderWidth': '1px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center',
                    'margin': '10px'
                },
            ),
            html.Div(id='output-data-upload'),
            dmc.Space(h=10),
            html.Div(id="column-selector"),
        ]
    )

def date_tab():
    options = html.Div(
        [
            dmc.YearPickerInput(
                type="range",
                id="date-range-picker-xmatch",
                label="Date Range",
                description="Pick up one or several years of Fink/ZTF data to crossmatch against",
                hideOutsideDates=True,
                numberOfColumns=2,
                dropdownType="modal",
                modalProps={"centered": True},
                minDate="2019-11-02",
                maxDate=(datetime.datetime.now().date() - datetime.timedelta(days=1)),
                allowSingleDateInRange=True,
                required=True,
                clearable=True,
            ),
        ]
    )
    tab = html.Div(
        [
            dmc.Space(h=50),
            options,
        ],
        id="date_tab-xmatch",
    )
    return tab

def filter_content_tab():
    options = html.Div(
        [
            dmc.MultiSelect(
                label="Alert fields",
                description="Select all Fink/ZTF fields you would like to be added.",
                placeholder="start typing...",
                id="field_select_xmatch",
                searchable=True,
                clearable=True,
            ),
            dmc.Accordion(
                id="accordion-schema",
                children=[
                    dmc.AccordionItem(
                        [
                            dmc.AccordionControl(
                                "Alert schema",
                                icon=DashIconify(
                                    icon="tabler:help",
                                    color=dmc.DEFAULT_THEME["colors"]["blue"][6],
                                    width=20,
                                ),
                            ),
                            dmc.AccordionPanel(create_datatransfer_schema_table(cutouts_allowed=False)),
                        ],
                        value="info",
                    ),
                ],
            ),
            dmc.Space(h=10),
        ],
    )
    tab = html.Div(
        [
            dmc.Space(h=50),
            dmc.Divider(variant="solid", label="Filter alert content"),
            options,
        ],
        id="filter_content_tab_xmatch",
    )
    return tab


instructions = """
#### 1. Review

You are about to submit a job on the Fink Apache Spark & Kafka clusters.
Review your parameters, before hitting submission!

#### 2. Register

To retrieve the data, you need to get an account on the Fink Kafka cluster. See [fink-client](https://github.com/astrolabsoftware/fink-client) and
the [documentation](https://fink-broker.readthedocs.io/en/latest/services/data_transfer) for more information.

#### 3. Retrieve

Once data has started to flow in the topic, you can easily download your alerts using the [fink-client](https://github.com/astrolabsoftware/fink-client).
Install the latest version and use e.g.
"""


def layout():
    active = 0
    helper = """
    The Fink xmatch service allows you to upload a catalog of sources and crossmatch again Fink-processed alert data at scale.
    We provide access to alert data from ZTF (over 200 million alerts as of 2025), and soon from the Rubin Observatory.

    Follow these steps: (1) upload your catalog (100,000 rows maximum), (2) choose one or several years of data, and (3) select only the relevant alert fields to be added.

    The accepted formats for catalog are: csv, parquet, and votable.

    Once ready, submit your job on the Fink Apache Spark and Kafka clusters to retrieve your data wherever you like.
    To access the data, you need to create an account. See the [fink-client](https://github.com/astrolabsoftware/fink-client) and
    the [documentation](https://fink-broker.readthedocs.io/en/latest/services/data_transfer) for more information. The data is available
    for download for 7 days.
    """

    layout = dmc.Container(
        size="90%",
        children=[
            dmc.Space(h=20),
            dmc.Grid(
                justify="center",
                gutter={"base": 5, "xs": "md", "md": "xl", "xl": 50},
                grow=True,
                children=[
                    dmc.GridCol(
                        children=[
                            dmc.Stack(
                                [
                                    dmc.Space(h=20),
                                    dmc.Center(
                                        dmc.Title(
                                            children="Fink Xmatch",
                                            style={"color": "#15284F"},
                                        ),
                                    ),
                                    dmc.Space(h=20),
                                    dmc.SegmentedControl(
                                        id="trans_datasource-xmatch",
                                        value="ZTF",
                                        data=[
                                            {
                                                "value": "Rubin",
                                                "label": "Rubin",
                                                "disabled": True,
                                            },
                                            {"value": "ZTF", "label": "ZTF"},
                                        ],
                                        radius="lg",
                                        size="lg",
                                    ),
                                    dmc.RingProgress(
                                        roundCaps=True,
                                        sections=[{"value": 0, "color": "grey"}],
                                        size=250,
                                        thickness=20,
                                        label="",
                                        id="gauge_entry_number",
                                    ),
                                    dmc.Accordion(
                                        variant="separated",
                                        radius="xl",
                                        children=[
                                            dmc.AccordionItem(
                                                [
                                                    dmc.AccordionControl(
                                                        "Help",
                                                        icon=DashIconify(
                                                            icon="material-symbols:info-outline",
                                                            color="black",
                                                            width=30,
                                                        ),
                                                    ),
                                                    dmc.AccordionPanel(
                                                        dcc.Markdown(
                                                            helper, link_target="_blank"
                                                        ),
                                                    ),
                                                ],
                                                value="description",
                                            ),
                                        ],
                                        value=None,
                                    ),
                                ],
                                align="center",
                            )
                        ],
                        span=2,
                    ),
                    dmc.GridCol(
                        children=[
                            dmc.Space(h=40),
                            dmc.Space(h=40),
                            dmc.Stepper(
                                color="#15284F",
                                id="stepper-xmatch-usage",
                                active=active,
                                children=[
                                    dmc.StepperStep(
                                        label="Choose catalog",
                                        description="Upload your catalog of objects",
                                        children=upload_catalog(),
                                        id="stepper-catalog",
                                    ),
                                    dmc.StepperStep(
                                        label="Date Range",
                                        description="Choose your date range for Fink",
                                        children=date_tab(),
                                        id="stepper-date-xmatch",
                                    ),
                                    dmc.StepperStep(
                                        label="Choose content",
                                        description="Pick up only relevant fields",
                                        children=filter_content_tab(),
                                    ),
                                    dmc.StepperStep(
                                        label="Launch xmatch!",
                                        description="Get your data",
                                        children=dmc.Grid(
                                            justify="center",
                                            gutter={
                                                "base": 5,
                                                "xs": "md",
                                                "md": "xl",
                                                "xl": 50,
                                            },
                                            grow=True,
                                            children=[
                                                dmc.GridCol(
                                                    children=[
                                                        dmc.Stack(
                                                            children=[
                                                                dmc.Space(h=20),
                                                                dmc.Group(
                                                                    children=[
                                                                        dmc.Button(
                                                                            "Submit job",
                                                                            id="submit_xmatch",
                                                                            variant="outline",
                                                                            color=COLORS_ZTF[
                                                                                0
                                                                            ],
                                                                            leftSection=DashIconify(
                                                                                icon="fluent:database-plug-connected-20-filled"
                                                                            ),
                                                                        ),
                                                                        html.A(
                                                                            dmc.Button(
                                                                                "Clear and restart",
                                                                                id="refresh-xmatch",
                                                                                color="red",
                                                                            ),
                                                                            href="/xmatch",
                                                                        ),
                                                                    ]
                                                                ),
                                                                html.Div(
                                                                    id="notification-container"
                                                                ),
                                                                dmc.Group(children=[]),
                                                                dcc.Interval(
                                                                    id="interval-component-xmatch",
                                                                    interval=1 * 3000,
                                                                    n_intervals=0,
                                                                ),
                                                                html.Div(
                                                                    id="batch_log_xmatch"
                                                                ),
                                                            ],
                                                            align="center",
                                                        )
                                                    ],
                                                    span=6,
                                                ),
                                                dmc.GridCol(
                                                    dmc.Stack(
                                                        children=[
                                                            dmc.Space(h=20),
                                                            dcc.Markdown(instructions),
                                                            dmc.CodeHighlight(
                                                                code="# Submit to see code",
                                                                id="code_block_xmatch",
                                                                language="bash",
                                                            ),
                                                        ]
                                                    ),
                                                    span=6,
                                                ),
                                            ],
                                        ),
                                    ),
                                ],
                            ),
                            dmc.Space(h=40),
                            dmc.Group(
                                justify="center",
                                mt="xl",
                                children=[
                                    dmc.Button(
                                        "Back", id="back-xmatch-usage", variant="default"
                                    ),
                                    dmc.Button("Next step", id="next-xmatch-usage"),
                                ],
                            ),
                            dcc.Store(id="object-catalog"),
                            # dcc.Store(data="", id="log_progress"),
                            # html.Div("", id="batch_id", style={"display": "none"}),
                            # html.Div("", id="topic_name", style={"display": "none"}),
                        ],
                        span=9,
                    ),
                ],
            ),
        ],
    )

    return layout

@app.callback(
    Output("column-selector", "children"),
    Input("object-catalog", "data"),
    prevent_initial_call=True,
)
def select_columns(catalog):
    """
    """
    pdf = pd.read_json(io.StringIO(catalog))

    if pdf.empty:
        return no_update

    radius = dmc.NumberInput(
        placeholder="type value...",
        label="Crossmatch radius in arcsecond",
        variant="default",
        # size="sm",
        # radius="sm",
        hideControls=True,
        w=250,
        mb=10,
        id="radius_xmatch",
    )

    ra = dmc.Select(
        label="Select column for Right Ascension",
        placeholder="Select one",
        id="ra-column",
        data=[{"value": c, "label": c} for c in pdf.columns],
        w=250,
        mb=10,
    )
    dec = dmc.Select(
        label="Select column for Declination",
        placeholder="Select one",
        id="dec-column",
        data=[{"value": c, "label": c} for c in pdf.columns],
        w=250,
        mb=10,
    )
    identifier = dmc.Select(
        label="Select column for the identifier",
        placeholder="Select one",
        id="id-column",
        data=[{"value": c, "label": c} for c in pdf.columns],
        w=250,
        mb=10,
    )

    return dmc.Group([ra, dec, identifier, radius], justify="center")


@app.callback(
    [
        Output("date-range-picker-xmatch", "minDate"),
        Output("date-range-picker-xmatch", "maxDate"),
        Output("field_select_xmatch", "data"),
    ],
    [
        Input("trans_datasource-xmatch", "value"),
    ],
    # prevent_initial_call=True,
)
def display_filter_tab(trans_datasource):
    if trans_datasource is None:
        PreventUpdate  # noqa: B018
    else:
        # Available fields
        data_content_select = format_field_for_data_transfer(trans_datasource, with_predefined_options=False, cutouts_allowed=False)

        if trans_datasource == "ZTF":
            minDate = datetime.date(2019, 11, 1)
            maxDate = datetime.date.today()

        return (
            minDate,
            maxDate,
            data_content_select,
        )

@callback(
    Output("stepper-xmatch-usage", "active"),
    Input("back-xmatch-usage", "n_clicks"),
    Input("next-xmatch-usage", "n_clicks"),
    State("stepper-xmatch-usage", "active"),
    prevent_initial_call=True,
)
def update(back, next_, current):
    button_id = ctx.triggered_id
    step = current if current is not None else 0
    if button_id == "back-xmatch-usage":
        step = step - 1 if step > min_step else step
    else:
        step = step + 1 if step < max_step else step
    return step


@callback(
    Output("next-xmatch-usage", "style"),
    Input("next-xmatch-usage", "n_clicks"),
    Input("stepper-xmatch-usage", "active"),
    prevent_initial_call=True,
)
def last_step(next, current):
    if current == max_step - 1 or current == max_step:
        return {"display": "none"}
    return {}


@callback(
    Output("back-xmatch-usage", "style"),
    Input("back-xmatch-usage", "n_clicks"),
    Input("stepper-xmatch-usage", "active"),
)
def first_step(back, current):
    if current == 0 or current is None:
        return {"display": "none"}
    return {}

@callback(
    Output("stepper-catalog", "color"),
    Input("object-catalog", "data"),
    Input("back-xmatch-usage", "n_clicks"),
    Input("next-xmatch-usage", "n_clicks"),
)
def update_icon_date(catalog, back_, next_):
    button_id = ctx.triggered_id
    if button_id in ["back-xmatch-usage", "next-xmatch-usage"]:
        if catalog is None or catalog == {}:
            return "red"
        return "#15284F"
    return "#15284F"

@callback(
    Output("submit_xmatch", "disabled"),
    Input("object-catalog", "data"),
    Input("date-range-picker-xmatch", "value"),
)
def disable_button(catalog, date):
    f1 = date is None or date == ""
    f2 = catalog is None or catalog == {}
    if f1 or f2:
        return True
    return False

def parse_contents(catalog, filename, date):
    pdf = pd.read_json(io.StringIO(catalog))

    # Check header? Or ask the user to provide what is RA, DEC, OID?

    return html.Div([
        html.H5("{}".format(filename)),
        html.H6("Preview of the 10 first rows"),

        dash_table.DataTable(
            pdf.head(10).to_dict('records'),
            [{'name': i, 'id': i} for i in pdf.columns]
        ),
        # dmc.Space(h=10),
        # dmc.Text(
        #     [
        #         "Assuming Right Ascension is ",
        #         dmc.Text(pdf.columns[0], fw=700, span=True, c=COLORS_ZTF[1]),
        #         ", Declination is ",
        #         dmc.Text(pdf.columns[1], fw=700, span=True, c=COLORS_ZTF[1]),
        #         ", and Identifier is ",
        #         dmc.Text(pdf.columns[2], fw=700, span=True, c=COLORS_ZTF[1]),
        #         ". If this is not correct, re-order your columns and upload again."
        #     ]
        # )
    ])

@callback(Output('output-data-upload', 'children'),
              Input('object-catalog', 'data'),
              State('upload-data', 'filename'),
              State('upload-data', 'last_modified'))
def update_output(catalog, filename, date):
    if catalog is not None:
        children = parse_contents(catalog, filename, date)
        return children

@callback(
    [
        Output("object-catalog", "data"),
        Output("gauge_entry_number", "sections"),
        Output("gauge_entry_number", "label"),
    ],
    [
        Input('upload-data', 'contents'),
        State('upload-data', 'filename'),
    ],
    prevent_initial_call=True,
)
def store_catalog(content, filename):
    """Store data from user
    """
    if content is None:
        return no_update, no_update, no_update
    content_type, content_string = content.split(',')
    decoded = base64.b64decode(content_string)

    try:
        if '.csv' in filename:
            # Assume that the user uploaded a CSV file
            pdf = pd.read_csv(
                io.StringIO(decoded.decode('utf-8')))
        elif ".parquet" in filename:
            # Assume that the user uploaded a parquet file
            pdf = pd.read_parquet(io.BytesIO(decoded))
        elif ".xml" in filename:
            # Assume that the user uploaded a votable file
            table = votable.parse(io.BytesIO(decoded))
            pdf = table.get_first_table().to_table(use_names_over_ids=True).to_pandas()
    except Exception as e:
        return "{}", [{"value": 0, "color": "grey", "tooltip": "0%"}], dmc.Text(e, c="red", ta="center")

    if len(pdf) > MAX_ROW:
        msg = "{:,} is too many rows! Maximum is 100,000".format(len(pdf))
        return "{}", [{"value": 100, "color": "red", "tooltip": "100%"}], dmc.Text(msg, c="red", ta="center")


    sections = {"value": len(pdf) / MAX_ROW * 100, "color": "green", "tooltip": "{:.2f}%".format(len(pdf) / MAX_ROW * 100)}
    label = dmc.Text(
        "{:,} rows".format(len(pdf)), c=COLORS_ZTF[0], ta="center"
    )

    return pdf.to_json(), [sections], label


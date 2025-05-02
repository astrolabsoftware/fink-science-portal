# Copyright 2020-2024 AstroLab Software
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
import io
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import pandas as pd
from dash import Input, Output, dcc
from dash_iconify import DashIconify

from app import app
from apps.cards import card_neighbourhood
from apps.utils import create_button_for_external_conesearch


def card_explanation_blazar():
    """Explain what is used to fit for Blazars"""
    msg = """
    This light curve is obtained by dividing each band by a meaningful calculation of its median.
    Each median is calculated by selecting measurements in one band if and only if there is at least one other measurement in the other band less than 12 hours after the first.
    The sub-selections of measurements are then used to calculate the respective medians.

    Once these medians have been calculated, the entire light curve is divided by its overall median to make it equal to 1.

    The slider allows you to drag the lowest and highest percentile of your choice. When you are happy with the value for that percentile, click Update Plot.

    You can also add measurements from the Data Release by loading them using the Get DR Photometry button.
    """
    card = dmc.Accordion(
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "How to use this panel?",
                        icon=[
                            DashIconify(
                                icon="tabler:help-hexagon",
                                color="#3C8DFF",
                                width=20,
                            ),
                        ],
                    ),
                    dmc.AccordionPanel(dcc.Markdown(msg)),
                ],
                value="info",
            ),
        ],
        value="info",
        id="card_explanation_blazar",
    )
    return card


@app.callback(
    Output("card_blazar_button", "children"),
    [
        Input("object-data", "data"),
    ],
    prevent_initial_call=True,
)
def card_blazar_button(object_data):
    """Add a card containing button to fit for variable stars"""
    pdf = pd.read_json(io.StringIO(object_data))

    ra0 = pdf["i:ra"].to_numpy()[0]
    dec0 = pdf["i:dec"].to_numpy()[0]

    card1 = dmc.Accordion(
        disableChevronRotation=True,
        multiple=True,
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Neighbourhood",
                        icon=[
                            DashIconify(
                                icon="tabler:atom-2",
                                color=dmc.DEFAULT_THEME["colors"]["green"][6],
                                width=20,
                            ),
                        ],
                    ),
                    dmc.AccordionPanel(
                        dmc.Stack(
                            [
                                card_neighbourhood(pdf),
                                dbc.Row(
                                    [
                                        create_button_for_external_conesearch(
                                            kind="asas-sn-variable",
                                            ra0=ra0,
                                            dec0=dec0,
                                            radius=0.5,
                                        ),
                                        create_button_for_external_conesearch(
                                            kind="snad", ra0=ra0, dec0=dec0, radius=5
                                        ),
                                        create_button_for_external_conesearch(
                                            kind="vsx", ra0=ra0, dec0=dec0, radius=0.1
                                        ),
                                    ],
                                    justify="around",
                                    className="mb-2",
                                ),
                            ],
                            align="center",
                        ),
                    ),
                ],
                value="external",
            ),
        ],
        styles={"content": {"padding": "5px"}},
    )

    return card1

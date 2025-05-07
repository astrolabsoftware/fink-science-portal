# Copyright 2020-2024 AstroLab Software
# Authors: Julien Peloton, Julian Hamo
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


def card_explanation_observability():
    """Explain what is used to fit for Observability"""
    msg = """
    This plot is calculated using the Astropy library. It shows the altitude and corresponding airmass of a source along the night. The UTC time is given on the lower axis while the local time is given on the upper axis.

    The right panel allows you to select an observation date and an observatory. You can also choose to display the altitude of the moon during the night, as well as its phase. Once you have selected a date and an observatory, click on Update Plot.
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
        id="card_explanation_observability",
    )
    return card


@app.callback(
    Output("card_observability_button", "children"),
    [
        Input("object-data", "data"),
    ],
    prevent_initial_call=True,
)
def card_observability_button(object_data):
    """Add a card containing button to fit for observability of the source"""
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

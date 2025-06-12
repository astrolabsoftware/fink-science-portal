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
import dash_mantine_components as dmc
import pandas as pd
from dash import Input, Output, dcc
from dash_iconify import DashIconify

from app import app
from apps.cards import card_neighbourhood


def card_explanation_observability():
    """Explain what is used to fit for Observability"""
    msg = """
    This plot is calculated using the [Astropy](http://www.astropy.org/) library. It shows the altitude and corresponding airmass of a source along the night. The UTC time is given on the lower axis while the local time is given on the upper axis.

    The right panel allows you to select an observation date and an observatory. You can also choose to display the altitude of the moon during the night, as well as its phase and illumination. Once you have selected a date and an observatory, click on `Update Plot`.

    The plot also shows the different definitions of nights, which can be useful, from lighter to darker shades of blue. These are no-sun night (sun below the horizon), civil night (sun 6° below the horizon), nautical night (sun 12° below the horizon) and astronomical night (sun 18° below the horizon).

    If you cannot find your observatory of choice, you can enter its coordinates in the `Custom Observatory` field. Remember that both longitude and latitude must be written in decimal degrees. Note that longitudes are negative towards the west. You can omit the positive sign of the longitude and latitude. To use the existing list of observatories again, clear the `Longitude` and `Latitude` fields in the `Custom Observatory` section.

    In case your observatory is not listed here, you can also open a [ticket](https://github.com/astrolabsoftware/fink-science-portal/issues) with the coordinates.
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

    card1 = dmc.Accordion(
        disableChevronRotation=True,
        multiple=True,
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Custom Observatory",
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
                            card_neighbourhood(pdf),
                        ),
                    ),
                ],
                value="external",
            ),
        ],
        styles={"content": {"padding": "5px"}},
    )

    return card1

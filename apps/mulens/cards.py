# Copyright 2020-2022 AstroLab Software
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
from dash import html, dcc, dash_table, Input, Output, State
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from app import app
from apps.cards import card_neighbourhood

import pandas as pd

@app.callback(
    Output("card_mulens", "children"),
    [
        Input('object-data', 'data'),
    ],
    prevent_initial_call=True
)
def card_mulens(object_data):
    """ Add a card containing button to fit for microlensing events
    """
    pdf = pd.read_json(object_data)

    ra0 = pdf['i:ra'].values[0]
    dec0 = pdf['i:dec'].values[0]

    card1 = dmc.AccordionMultiple(
        disableChevronRotation=True,
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Neighbourhood",
                        icon=[
                            DashIconify(
                                icon="tabler:atom-2",
                                color=dmc.theme.DEFAULT_COLORS["green"][6],
                                width=20,
                            )
                        ],
                    ),
                    dmc.AccordionPanel(
                        [
                            card_neighbourhood(pdf),
                        ],
                    ),
                ],
                value='neighbourhood',
            ),
        ],
        # Show it open by default
        value='neighbourhood',
        styles={'content':{'padding':'5px'}}
    )

    return card1

def card_explanation_mulens():
    """ Explain what is used to fit for microlensing events
    """
    msg = """
    Press `Fit data` to perform a time series analysis of the data. Fitted parameters will be displayed alongside with the plot.

    The fit is done using [pyLIMA](https://github.com/ebachelet/pyLIMA)
    described in [Bachelet et al (2017)](https://ui.adsabs.harvard.edu/abs/2017AJ....154..203B/abstract).
    We use a simple PSPL model to fit the data.
    """
    card = dmc.Accordion(
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "How to make a fit?",
                        icon=[
                            DashIconify(
                                icon="tabler:help-hexagon",
                                color="#3C8DFF",
                                width=20,
                            )
                        ],
                    ),
                    dmc.AccordionPanel(dcc.Markdown(msg)),
                ],
                value='info'
            ),
        ],
        value='info',
        id='card_explanation_mulens'
    )
    return card

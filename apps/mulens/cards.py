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

import pandas as pd

def card_mulens_button(pdf):
    """ Add a card containing button to fit for microlensing events
    """
    distnr = pdf['i:distnr'].values[0]
    ssnamenr = pdf['i:ssnamenr'].values[0]
    distpsnr1 = pdf['i:distpsnr1'].values[0]
    neargaia = pdf['i:neargaia'].values[0]
    constellation = pdf['v:constellation'].values[0]
    if 'd:DR3Name' in pdf.columns:
        gaianame = pdf['d:DR3Name'].values[0]
    else:
        gaianame = None
    cdsxmatch = pdf['d:cdsxmatch'].values[0]

    ra0 = pdf['i:ra'].values[0]
    dec0 = pdf['i:dec'].values[0]

    card1 = dmc.Accordion(
        state={"0": False},
        multiple=True,
        offsetIcon=False,
        disableIconRotation=True,
        children=[
            dmc.AccordionItem(
                [
                    dmc.Paper(
                        [
                            dcc.Markdown(
                                """
                                ```python
                                Constellation: {}
                                Class (SIMBAD): {}
                                Name (MPC): {}
                                Name (Gaia): {}
                                Distance (Gaia): {:.2f} arcsec
                                Distance (PS1): {:.2f} arcsec
                                Distance (ZTF): {:.2f} arcsec
                                ```
                                ---
                                """.format(
                                    constellation,
                                    cdsxmatch, ssnamenr, gaianame,
                                    float(neargaia), float(distpsnr1), float(distnr)
                                )
                            ),
                        ],
                        radius='xl', p='md', shadow='xl', withBorder=True
                    ),
                ],
                label="Neighbourhood",
                icon=[
                    DashIconify(
                        icon="tabler:atom-2",
                        color=dmc.theme.DEFAULT_COLORS["green"][6],
                        width=20,
                    )
                ],
            )
        ]
    )

    submit_mulens_button = dmc.Button(
        'Fit data',
        id='submit_mulens',
        color='dark', variant="outline", fullWidth=True, radius='xl'
    )

    card2 = html.Div(id='mulens_params')
    card3 = submit_mulens_button

    return html.Div([card1, html.Br(), card2, html.Br(), card3])

def card_explanation_mulens():
    """ Explain what is used to fit for microlensing events
    """
    msg = """
    Press `Fit data` to perform a time series analysis of the data. Fitted parameters will be displayed on the right panel.

    The fit is done using [pyLIMA](https://github.com/ebachelet/pyLIMA)
    described in [Bachelet et al (2017)](https://ui.adsabs.harvard.edu/abs/2017AJ....154..203B/abstract).
    We use a simple PSPL model to fit the data.
    """
    card = dmc.Accordion(
        state={'0': True},
        children=[
            dmc.AccordionItem(
                dcc.Markdown(msg),
                label="How to make a fit?",
            ),
        ],
    )
    return card
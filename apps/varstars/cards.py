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
import numpy as np

def card_explanation_variable():
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
    The score is between 0 (poor fit) and 1 (excellent fitprevent_initial_call=True,).
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

@app.callback(
    Output("card_variable_button", "children"),
    [
        Input('object-data', 'children'),
    ],
    prevent_initial_call=True
)
def card_variable_button(object_data):
    """ Add a card containing button to fit for variable stars
    """
    pdf = pd.read_json(object_data)
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
                                """.format(
                                    constellation,
                                    cdsxmatch, ssnamenr, gaianame,
                                    float(neargaia), float(distpsnr1), float(distnr)
                                )
                            ),
                            html.Br(),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dbc.Button(
                                            className='btn btn-default zoom btn-circle btn-lg',
                                            style={'background-image': 'url(/assets/buttons/assassin_logo.png)', 'background-size': 'cover'},
                                            color='dark',
                                            outline=True,
                                            id='asas-sn',
                                            target="_blank",
                                            href='https://asas-sn.osu.edu/variables?ra={}&dec={}&radius=0.5&vmag_min=&vmag_max=&amplitude_min=&amplitude_max=&period_min=&period_max=&lksl_min=&lksl_max=&class_prob_min=&class_prob_max=&parallax_over_err_min=&parallax_over_err_max=&name=&references[]=I&references[]=II&references[]=III&references[]=IV&references[]=V&references[]=VI&sort_by=raj2000&sort_order=asc&show_non_periodic=true&show_without_class=true&asassn_discov_only=false&'.format(ra0, dec0)
                                        ), width=4),
                                    dbc.Col(
                                        dbc.Button(
                                            className='btn btn-default zoom btn-circle btn-lg',
                                            style={'background-image': 'url(/assets/buttons/snad.svg)', 'background-size': 'cover'},
                                            color='dark',
                                            outline=True,
                                            id='SNAD-var-star',
                                            target="_blank",
                                            href='https://ztf.snad.space/search/{} {}/{}'.format(ra0, dec0, 5)
                                        ), width=4),
                                ], justify='around'
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

    nterms_base = dbc.Row(
        [
            dbc.Label("Number of base terms"),
            dbc.Input(
                placeholder="1",
                value=1,
                type="number",
                id='nterms_base',
                debounce=True,
                min=0, max=4
            ),
            dbc.Label("Number of band terms"),
            dbc.Input(
                placeholder="1",
                value=1,
                type="number",
                id='nterms_band',
                debounce=True,
                min=0, max=4
            ),
            dbc.Label("Set manually the period (days)"),
            dbc.Input(
                placeholder="Optional",
                value=None,
                type="number",
                id='manual_period',
                debounce=True
            )
        ], className='mb-3', style={'width': '100%', 'display': 'inline-block'}
    )

    submit_varstar_button = dmc.Button(
        'Fit data',
        id='submit_variable',
        color='dark', variant="outline", fullWidth=True, radius='xl',
        loaderProps={'variant': 'dots'}
    )

    card2 = dmc.Paper(
        [
            nterms_base,
        ], radius='xl', p='md', shadow='xl', withBorder=True
    )
    card3 = submit_varstar_button

    return html.Div([card1, html.Br(), card2, html.Br(), card3])
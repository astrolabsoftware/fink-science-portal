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

from apps.utils import queryMPC, convert_mpc_type

from app import app, APIURL

import visdcc

def card_sso_left(ssnamenr):
    """
    """
    ssnamenr_ = str(ssnamenr)

    python_download = """import requests
import pandas as pd
import io

# get data for ZTF19acnjwgm
r = requests.post(
    '{}/api/v1/sso',
    json={{
        'n_or_d': '{}',
        'output-format': 'json'
    }}
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))""".format(
        APIURL,
        ssnamenr
    )

    curl_download = """
curl -H "Content-Type: application/json" -X POST \\
    -d '{{"n_or_d":"{}", "output-format":"csv"}}' \\
    {}/api/v1/sso -o {}.csv
    """.format(ssnamenr, APIURL, ssnamenr)

    download_tab = dmc.Tabs(
        color="red",
        children=[
            dmc.Tab(label="Python", children=dmc.Prism(children=python_download, language="python")),
            dmc.Tab(label="Curl", children=dmc.Prism(children=curl_download, language="bash")),
        ]
    )

    if ssnamenr_ != 'null':
        extra_items = [
            dmc.AccordionItem(
                [
                    dmc.Paper(
                        download_tab,
                        radius='xl', p='md', shadow='xl', withBorder=True
                    )
                ],
                label="Download data",
                icon=[
                    DashIconify(
                        icon="tabler:database-export",
                        color=dmc.theme.DEFAULT_COLORS["red"][6],
                        width=20,
                    )
                ],
            ),
            dmc.AccordionItem(
                [
                    dmc.Paper(
                        dbc.Row(
                            [
                                dbc.Col(
                                    dbc.Button(
                                        className='btn btn-default zoom btn-circle btn-lg',
                                        style={'background-image': 'url(/assets/buttons/mpc.jpg)', 'background-size': 'cover'},
                                        color='dark',
                                        outline=True,
                                        id='MPC',
                                        target="_blank",
                                        href='https://minorplanetcenter.net/db_search/show_object?utf8=%E2%9C%93&object_id={}'.format(ssnamenr_)
                                    ), width=4),
                                dbc.Col(
                                    dbc.Button(
                                        className='btn btn-default zoom btn-circle btn-lg',
                                        style={'background-image': 'url(/assets/buttons/nasa.png)', 'background-size': 'cover'},
                                        color='dark',
                                        outline=True,
                                        id='JPL',
                                        target="_blank",
                                        href='https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr={}'.format(ssnamenr_),
                                    ), width=4
                                ),
                            ], justify='around'
                        ),
                        radius='xl', p='md', shadow='xl', withBorder=True
                    )
                ],
                label="External links",
                icon=[
                    DashIconify(
                        icon="tabler:external-link",
                        color=dmc.theme.DEFAULT_COLORS["orange"][6],
                        width=20,
                    )
                ],
            ),
        ]
    else:
        extra_items = []

    card = dmc.Accordion(
        state={"0": True, **{"{}".format(i+1): False for i in range(4)}},
        multiple=True,
        offsetIcon=False,
        disableIconRotation=True,
        children=[
            dmc.AccordionItem(
                [
                    dmc.Paper(
                        card_sso_mpc_params(ssnamenr),
                        radius='xl', p='md', shadow='xl', withBorder=True
                    )
                ],
                label="SSO card",
                icon=[
                    DashIconify(
                        icon="majesticons:comet",
                        color=dmc.theme.DEFAULT_COLORS["dark"][6],
                        width=20,
                    )
                ],
            ),
            *extra_items
        ]
    )

    return card

def card_sso_mpc_params(ssnamenr):
    """ MPC parameters
    """
    template = """
    ```python
    # Properties from MPC
    number: {}
    period (year): {}
    a (AU): {}
    q (AU): {}
    e: {}
    inc (deg): {}
    Omega (deg): {}
    argPeri (deg): {}
    tPeri (MJD): {}
    meanAnomaly (deg): {}
    epoch (MJD): {}
    H: {}
    G: {}
    neo: {}
    ```
    """
    ssnamenr_ = str(ssnamenr)
    if ssnamenr_.startswith('C/'):
        kind = 'comet'
        ssnamenr_ = ssnamenr_[:-2] + ' ' + ssnamenr_[-2:]
        data = queryMPC(ssnamenr_, kind=kind)
    elif (ssnamenr_[-1] == 'P'):
        kind = 'comet'
        data = queryMPC(ssnamenr_, kind=kind)
    else:
        kind = 'asteroid'
        data = queryMPC(ssnamenr_, kind=kind)

    if data.empty:
        card = html.Div(
            [
                html.H5("Name: None", className="card-title"),
                html.H6("Orbit type: None", className="card-subtitle"),
            ],
        )
        return card
    if kind == 'comet':
        header = [
            html.H5("Name: {}".format(data['n_or_d']), className="card-title"),
            html.H6("Orbit type: Comet", className="card-subtitle"),
        ]
        abs_mag = None
        phase_slope = None
        neo = 0
    elif kind == 'asteroid':
        if data['name'] is None:
            name = ssnamenr
        else:
            name = data['name']
        orbit_type = convert_mpc_type(int(data['orbit_type']))
        header = [
            html.H5("Name: {}".format(name), className="card-title"),
            html.H6("Orbit type: {}".format(orbit_type), className="card-subtitle"),
        ]
        abs_mag = data['absolute_magnitude']
        phase_slope = data['phase_slope']
        neo = int(data['neo'])

    card = html.Div(
        [
            *header,
            dcc.Markdown(
                template.format(
                    data['number'],
                    data['period'],
                    data['semimajor_axis'],
                    data['perihelion_distance'],
                    data['eccentricity'],
                    data['inclination'],
                    data['ascending_node'],
                    data['argument_of_perihelion'],
                    float(data['perihelion_date_jd']) - 2400000.5,
                    data['mean_anomaly'],
                    float(data['epoch_jd']) - 2400000.5,
                    abs_mag,
                    phase_slope,
                    neo
                )
            ),
        ],
    )
    return card
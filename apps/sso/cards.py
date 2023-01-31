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

import rocks

import visdcc

def get_sso_data(ssnamenr):
    """
    """
    data = rocks.Rock(
        ssnamenr,
        datacloud=['phase_functions', 'spins'],
        skip_id_check=False
    )
    if data.id_ == '':
        if ssnamenr.startswith('C/'):
            kind = 'comet'
            ssnamenr = ssnamenr[:-2] + ' ' + ssnamenr[-2:]
            data = queryMPC(ssnamenr, kind=kind)
        elif (ssnamenr[-1] == 'P'):
            kind = 'comet'
            data = queryMPC(ssnamenr, kind=kind)
        else:
            kind = 'asteroid'
            data = queryMPC(ssnamenr, kind=kind)

        if data.empty:
            return None, None
        return data, kind
    else:
        return data, None

def card_sso_left(ssnamenr):
    """
    """
    ssnamenr_ = str(ssnamenr)

    python_download = """import requests
import pandas as pd
import io

# get data for {}
r = requests.post(
    '{}/api/v1/sso',
    json={{
        'n_or_d': '{}',
        'withEphem': True,
        'output-format': 'json'
    }}
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))""".format(
        ssnamenr,
        APIURL,
        ssnamenr
    )

    curl_download = """
curl -H "Content-Type: application/json" -X POST \\
    -d '{{"n_or_d":"{}", "output-format":"csv"}}' \\
    {}/api/v1/sso -o {}.csv
    """.format(ssnamenr, APIURL, ssnamenr)

    download_tab = dmc.Tabs(
        [
            dmc.TabsList(
                [
                    dmc.Tab("Python", value="Python"),
                    dmc.Tab("Curl", value="Curl")
                ],
            ),
            dmc.TabsPanel(children=dmc.Prism(children=python_download, language="python"), value="Python"),
            dmc.TabsPanel(children=dmc.Prism(children=curl_download, language="bash"), value="Curl")
        ], color="red", value="Python"
    )

    if ssnamenr_ != 'null':
        ssnamenr_ = str(ssnamenr)
        data, kind = get_sso_data(ssnamenr_)
        if kind is not None:
            # from MPC
            card_properties = card_sso_mpc_params(data, ssnamenr_, kind)
        else:
            card_properties = card_sso_rocks_params(data)

        extra_items = [
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Download data",
                        icon=[
                            DashIconify(
                                icon="tabler:database-export",
                                color=dmc.theme.DEFAULT_COLORS["red"][6],
                                width=20,
                            )
                        ],
                    ),
                    dmc.AccordionPanel(
                        [
                            dmc.Paper(
                                [
                                    download_tab,
                                    dcc.Markdown('See {}/api for more options'.format(APIURL)),
                                ],
                                radius='xl', p='md', shadow='xl', withBorder=True
                            )
                        ],
                    ),
                ],
                value='api'
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "External links",
                        icon=[
                            DashIconify(
                                icon="tabler:external-link",
                                color=dmc.theme.DEFAULT_COLORS["orange"][6],
                                width=20,
                            )
                        ],
                    ),
                    dmc.AccordionPanel(
                        [
                            dmc.Paper(
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            dbc.Button(
                                                className='btn btn-default zoom btn-circle btn-lg',
                                                style={'background-image': 'url(/assets/buttons/imcce.png)', 'background-size': 'cover'},
                                                color='light',
                                                outline=True,
                                                id='IMCCE',
                                                target="_blank",
                                                href='https://ssp.imcce.fr/webservices/ssodnet/api/ssocard.php?q={}'.format(data.name)
                                            ), width=4),
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
                    ),
                ],
                value='external'
            ),
        ]

        card = dmc.AccordionMultiple(
            disableChevronRotation=True,
            children=[
                dmc.AccordionItem(
                    [
                        dmc.AccordionControl(
                            "SsODNet - ssoCard",
                            icon=[
                                DashIconify(
                                    icon="majesticons:comet",
                                    color=dmc.theme.DEFAULT_COLORS["dark"][6],
                                    width=20,
                                )
                            ],
                        ),
                        dmc.AccordionPanel(
                            [
                                dmc.Paper(
                                    card_properties,
                                    radius='xl', p='md', shadow='xl', withBorder=True
                                )
                            ],
                        ),
                    ],
                    value='sso'
                ),
                *extra_items
            ], value='sso'
        )
    else:
        card = html.Div()

    return card

def card_sso_mpc_params(data, ssnamenr, kind):
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
    if data is None:
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

def card_sso_rocks_params(data):
    """ IMCCE parameters from Rocks
    """
    if data is None:
        card = html.Div(
            [
                html.H5("Name: None", className="card-title"),
                html.H6("Class: None", className="card-subtitle"),
                html.H6("Parent body: None", className="card-subtitle"),
                html.H6("Dynamical system: None", className="card-subtitle"),
                dmc.Divider(
                    label='Physical parameters',
                    variant="solid",
                    style={"marginTop": 20, "marginBottom": 20},
                ),
                html.H6("Taxonomical class: None", className="card-subtitle"),
                html.H6("Absolute magnitude (mag): None", className="card-subtitle"),
                html.H6("Diameter (km): None", className="card-subtitle"),
                dmc.Divider(
                    label='Dynamical parameters',
                    variant="solid",
                    style={"marginTop": 20, "marginBottom": 20},
                ),
                html.H6("a (AU): None", className="card-subtitle"),
                html.H6("e: None", className="card-subtitle"),
                html.H6("i (deg): None", className="card-subtitle"),
                html.H6("Omega (deg): None", className="card-subtitle"),
                html.H6("argPeri (deg): None", className="card-subtitle"),
                html.H6("Mean motion (deg/day): None", className="card-subtitle"),
                html.H6("Orbital period (day): None", className="card-subtitle"),
                html.H6("Tisserand parameter: None", className="card-subtitle"),
            ],
        )
        return card

    margin = 1
    header = [
        html.H5("Name: {} ({})".format(data.name, data.number), className="card-title"),
        html.H6("Class: {}".format(data.class_), className="card-subtitle", style={"marginTop": margin, "marginBottom": margin}),
        html.H6("Parent body: {}".format(data.parent), className="card-subtitle", style={"marginTop": margin, "marginBottom": margin}),
        html.H6("Dynamical system: {}".format(data.system), className="card-subtitle", style={"marginTop": margin, "marginBottom": margin}),
        dmc.Divider(
            label='Physical parameters',
            variant="solid",
            style={"marginTop": 20, "marginBottom": 10},
        ),
        html.H6("Taxonomical class: {}".format(data.parameters.physical.taxonomy.class_.value), className="card-subtitle", style={"marginTop": margin, "marginBottom": margin}),
        html.H6("Absolute magnitude (mag): {}".format(data.parameters.physical.phase_function.generic_johnson_V.H.value), className="card-subtitle", style={"marginTop": margin, "marginBottom": margin}),
        html.H6("Diameter (km): {}".format(data.parameters.physical.diameter.value), className="card-subtitle", style={"marginTop": margin, "marginBottom": margin}),
        dmc.Divider(
            label='Dynamical parameters',
            variant="solid",
            style={"marginTop": 20, "marginBottom": 10},
        ),
        html.H6("a (AU): {}".format(data.parameters.dynamical.orbital_elements.semi_major_axis.value,), className="card-subtitle", style={"marginTop": margin, "marginBottom": margin}),
        html.H6("e: {}".format(data.parameters.dynamical.orbital_elements.eccentricity.value,), className="card-subtitle", style={"marginTop": margin, "marginBottom": margin}),
        html.H6("i (deg): {}".format(data.parameters.dynamical.orbital_elements.inclination.value,), className="card-subtitle", style={"marginTop": margin, "marginBottom": margin}),
        html.H6("Omega (deg): {}".format(data.parameters.dynamical.orbital_elements.node_longitude.value,), className="card-subtitle", style={"marginTop": margin, "marginBottom": margin}),
        html.H6("argPeri (deg): {}".format(data.parameters.dynamical.orbital_elements.perihelion_argument.value,), className="card-subtitle", style={"marginTop": margin, "marginBottom": margin}),
        html.H6("Mean motion (deg/day): {}".format(data.parameters.dynamical.orbital_elements.mean_motion.value,), className="card-subtitle", style={"marginTop": margin, "marginBottom": margin}),
        html.H6("Orbital period (day): {}".format(data.parameters.dynamical.orbital_elements.orbital_period.value,), className="card-subtitle", style={"marginTop": margin, "marginBottom": margin}),
        html.H6("Tisserand parameter: {}".format(data.parameters.dynamical.tisserand_parameter.jupiter.value,), className="card-subtitle", style={"marginTop": margin, "marginBottom": margin}),
    ]

    if data.parameters.physical.spin is not None:
        header.append(
            dmc.Divider(
                label='Spin parameters',
                variant="solid",
                style={"marginTop": 20, "marginBottom": 10},
            ),
        )
        for index, avail_spin in enumerate(data.parameters.physical.spin):
            header.append(
                dmc.Divider(
                    label=avail_spin.method[0].shortbib,
                    variant="dashed",
                    style={"marginTop": 10, "marginBottom": 5},
                )
            )
            header.append(
                html.H6(
                    "RA0 (deg): {}".format(
                        avail_spin.RA0.value
                    ),
                    className="card-subtitle"
                )
            )
            header.append(
                html.H6(
                    "DEC0 (deg): {}".format(
                        avail_spin.DEC0.value
                    ),
                    className="card-subtitle"
                ),
            )

    card = html.Div(
        header
    )
    return card
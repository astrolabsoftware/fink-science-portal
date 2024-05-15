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
import textwrap

import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import rocks
from dash import Input, Output, dcc, html
from dash_iconify import DashIconify

from app import APIURL, app
from apps.utils import convert_mpc_type, help_popover, queryMPC

AU_TO_M=149597870700

def get_sso_data(ssnamenr):
    """Extract SSO data from various providers (SSODNET, MPC)
    """
    data = rocks.Rock(
        ssnamenr,
        skip_id_check=False,
    )
    if data.id_ == "":
        if ssnamenr.startswith("C/"):
            kind = "comet"
            ssnamenr = ssnamenr[:-2] + " " + ssnamenr[-2:]
            data = queryMPC(ssnamenr, kind=kind)
        elif (ssnamenr[-1] == "P"):
            kind = "comet"
            data = queryMPC(ssnamenr, kind=kind)
        else:
            kind = "asteroid"
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

    python_download = f"""import requests
import pandas as pd
import io

# get data for {ssnamenr}
r = requests.post(
    '{APIURL}/api/v1/sso',
    json={{
        'n_or_d': '{ssnamenr}',
        'withEphem': True,
        'output-format': 'json'
    }}
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))"""

    curl_download = f"""
curl -H "Content-Type: application/json" -X POST \\
    -d '{{"n_or_d":"{ssnamenr}", "output-format":"csv"}}' \\
    {APIURL}/api/v1/sso -o {ssnamenr}.csv
    """

    download_tab = dmc.Tabs(
        [
            dmc.TabsList(
                [
                    dmc.Tab("Python", value="Python"),
                    dmc.Tab("Curl", value="Curl"),
                ],
            ),
            dmc.TabsPanel(children=dmc.Prism(children=python_download, language="python"), value="Python"),
            dmc.TabsPanel(children=dmc.Prism(children=curl_download, language="bash"), value="Curl"),
        ], color="red", value="Python",
    )

    if ssnamenr_ != "null":
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
                            ),
                        ],
                    ),
                    dmc.AccordionPanel(
                        html.Div(
                            [
                                dmc.Group(
                                    [
                                        dmc.Button(
                                            "JSON",
                                            id="download_sso_json",
                                            variant="outline",
                                            color="indigo",
                                            compact=True,
                                            leftIcon=[DashIconify(icon="mdi:code-json")],
                                        ),
                                        dmc.Button(
                                            "CSV",
                                            id="download_sso_csv",
                                            variant="outline",
                                            color="indigo",
                                            compact=True,
                                            leftIcon=[DashIconify(icon="mdi:file-csv-outline")],
                                        ),
                                        dmc.Button(
                                            "VOTable",
                                            id="download_sso_votable",
                                            variant="outline",
                                            color="indigo",
                                            compact=True,
                                            leftIcon=[DashIconify(icon="mdi:xml")],
                                        ),
                                        help_popover(
                                            [
                                                dcc.Markdown("You may also download the data programmatically."),
                                                download_tab,
                                                dcc.Markdown(f"See {APIURL}/api for more options"),
                                            ],
                                            "help_download_sso",
                                            trigger=dmc.ActionIcon(
                                                    DashIconify(icon="mdi:help"),
                                                    id="help_download_sso",
                                                    variant="outline",
                                                    color="indigo",
                                            ),
                                        ),
                                        # FIXME: is it correct way to get ssnamenr field?..
                                        html.Div(str(data.number), id="download_sso_ssnamenr", className="d-none"),
                                        html.Div(APIURL, id="download_sso_apiurl", className="d-none"),
                                    ], position="center", spacing="xs",
                                ),
                            ],
                        ),

                    ),
                ],
                value="api",
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
                            ),
                        ],
                    ),
                    dmc.AccordionPanel(
                        [
                            dmc.Stack(
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            dbc.Button(
                                                className="btn btn-default zoom btn-circle btn-lg",
                                                style={"background-image": "url(/assets/buttons/imcce.png)", "background-size": "cover"},
                                                color="light",
                                                outline=True,
                                                id="IMCCE",
                                                target="_blank",
                                                href=f"https://ssp.imcce.fr/forms/ssocard/{data.id_}",
                                            ), width=4),
                                        dbc.Col(
                                            dbc.Button(
                                                className="btn btn-default zoom btn-circle btn-lg",
                                                style={"background-image": "url(/assets/buttons/mpc.jpg)", "background-size": "cover"},
                                                color="dark",
                                                outline=True,
                                                id="MPC",
                                                target="_blank",
                                                href=f"https://minorplanetcenter.net/db_search/show_object?utf8=%E2%9C%93&object_id={ssnamenr_}",
                                            ), width=4),
                                        dbc.Col(
                                            dbc.Button(
                                                className="btn btn-default zoom btn-circle btn-lg",
                                                style={"background-image": "url(/assets/buttons/nasa.png)", "background-size": "cover"},
                                                color="dark",
                                                outline=True,
                                                id="JPL",
                                                target="_blank",
                                                href=f"https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr={ssnamenr_}",
                                            ), width=4,
                                        ),
                                    ], justify="around",
                                ),
                                align="center",
                            ),
                        ],
                    ),
                ],
                value="external",
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
                                ),
                            ],
                        ),
                        dmc.AccordionPanel(
                            [
                                dmc.Paper(
                                    card_properties,
                                    radius="sm", p="xs", shadow="sm", withBorder=True, style={"width": "100%"},
                                ),
                            ],
                        ),
                    ],
                    value="sso",
                ),
                *extra_items,
            ], value="sso",
            styles={"content":{"padding":"5px"}},
        )
    else:
        card = html.Div()

    return card

# Downloads handling. Requires CORS to be enabled on the server.
# TODO: We are mostly using it like this until GET requests properly initiate
# downloads instead of just opening the file (so, Content-Disposition etc)
download_js = """
function(n_clicks, name, apiurl){
    if(n_clicks > 0){
        fetch(apiurl + '/api/v1/sso', {
            method: 'POST',
            body: JSON.stringify({
                 'n_or_d': name,
                 'withEphem': true,
                 'output-format': '$FORMAT'
            }),
            headers: {
                'Content-type': 'application/json'
            }
        }).then(function(response) {
            return response.blob();
        }).then(function(data) {
            window.saveAs(data, name + '.$EXTENSION');
        }).catch(error => console.error('Error:', error));
    };
    return true;
}
"""
app.clientside_callback(
    download_js.replace("$FORMAT", "json").replace("$EXTENSION", "json"),
    Output("download_sso_json", "n_clicks"),
    [
        Input("download_sso_json", "n_clicks"),
        Input("download_sso_ssnamenr", "children"),
        Input("download_sso_apiurl", "children"),
    ],
)
app.clientside_callback(
    download_js.replace("$FORMAT", "csv").replace("$EXTENSION", "csv"),
    Output("download_sso_csv", "n_clicks"),
    [
        Input("download_sso_csv", "n_clicks"),
        Input("download_sso_ssnamenr", "children"),
        Input("download_sso_apiurl", "children"),
    ],
)
app.clientside_callback(
    download_js.replace("$FORMAT", "votable").replace("$EXTENSION", "vot"),
    Output("download_sso_votable", "n_clicks"),
    [
        Input("download_sso_votable", "n_clicks"),
        Input("download_sso_ssnamenr", "children"),
        Input("download_sso_apiurl", "children"),
    ],
)

def card_sso_mpc_params(data, ssnamenr, kind):
    """MPC parameters
    """
    if data is None:
        card = html.Div(
            [
                dcc.Markdown(
                    r"""
                    ##### Name: `None`
                    Orbit type: `None`
                    """,
                    className="markdown markdown-pre",
                ),
            ],
        )
        return card
    if kind == "comet":
        name = data["n_or_d"]
        orbit_type = "Comet"
        abs_mag = None
        phase_slope = None
        neo = 0
    elif kind == "asteroid":
        if data["name"] is None:
            name = ssnamenr
        else:
            name = data["name"]
        orbit_type = convert_mpc_type(int(data["orbit_type"]))
        abs_mag = data["absolute_magnitude"]
        phase_slope = data["phase_slope"]
        neo = int(data["neo"])

    card = html.Div(
        [
            dcc.Markdown(
                r"""
                ##### Name: `{}`
                Orbit type: `{}`

                ###### Properties from MPC
                number: `{}`
                period (year): `{}`
                a (AU): `{}`
                q (AU): `{}`
                e: `{}`
                inc (deg): `{}`
                Omega (deg): `{}`
                argPeri (deg): `{}`
                tPeri (MJD): `{}`
                meanAnomaly (deg): `{}`
                epoch (MJD): `{}`
                H: `{}`
                G: `{}`
                neo: `{}`
                """.format(
                    name,
                    orbit_type,
                    data["number"],
                    data["period"],
                    data["semimajor_axis"],
                    data["perihelion_distance"],
                    data["eccentricity"],
                    data["inclination"],
                    data["ascending_node"],
                    data["argument_of_perihelion"],
                    float(data["perihelion_date_jd"]) - 2400000.5,
                    data["mean_anomaly"],
                    float(data["epoch_jd"]) - 2400000.5,
                    abs_mag,
                    phase_slope,
                    neo,
                ),
                className="markdown markdown-pre",
            ),
        ],
        className="ps-2 pe-2",
    )
    return card

def card_sso_rocks_params(data):
    """IMCCE parameters from Rocks
    """
    if data is None:
        card = html.Div(
            [
                html.H5("Name: None", className="card-title"),
                "Class: None", html.Br(),
                "Parent body: None", html.Br(),
                "Dynamical system: None", html.Br(),
                dmc.Divider(
                    label="Physical parameters",
                    variant="solid",
                    style={"marginTop": 20, "marginBottom": 20},
                ),
                "Taxonomical class: None", html.Br(),
                "Absolute magnitude (mag): None", html.Br(),
                "Diameter (km): None", html.Br(),
                dmc.Divider(
                    label="Dynamical parameters",
                    variant="solid",
                    style={"marginTop": 20, "marginBottom": 20},
                ),
                "a (AU): None", html.Br(),
                "e: None", html.Br(),
                "i (deg): None", html.Br(),
                "Omega (deg): None", html.Br(),
                "argPeri (deg): None", html.Br(),
                "Mean motion (deg/day): None", html.Br(),
                "Orbital period (day): None", html.Br(),
                "Tisserand parameter: None", html.Br(),
            ],
        )
        return card

    # Convert km in AU
    if data.parameters.dynamical.orbital_elements.semi_major_axis.unit == "km":
        semi_major_axis = data.parameters.dynamical.orbital_elements.semi_major_axis.value / AU_TO_M * 1000
    else:
        semi_major_axis = data.parameters.dynamical.orbital_elements.semi_major_axis.value

    text = rf"""
    ##### Name: `{data.name}` / `{data.number}`
    Class: `{data.class_}`
    Parent body: `{data.parent}`
    Dynamical system: `{data.system}`

    ###### Physical parameters
    Taxonomical class: `{data.parameters.physical.taxonomy.class_.value}`
    Absolute magnitude (mag): `{data.parameters.physical.absolute_magnitude.value}`
    Diameter (km): `{data.parameters.physical.diameter.value}`

    ###### Dynamical parameters
    a (AU): `{semi_major_axis}`
    e: `{data.parameters.dynamical.orbital_elements.eccentricity.value}`
    i (deg): `{data.parameters.dynamical.orbital_elements.inclination.value}`
    Omega (deg): `{data.parameters.dynamical.orbital_elements.node_longitude.value}`
    argPeri (deg): `{data.parameters.dynamical.orbital_elements.periapsis_distance.value}`
    Mean motion (deg/day): `{data.parameters.dynamical.orbital_elements.mean_motion.value}`
    Orbital period (day): `{data.parameters.dynamical.orbital_elements.orbital_period.value}`
    Tisserand parameter: `{data.parameters.dynamical.tisserand_parameters.jupiter.value}`
    """

    if data.parameters.physical.spin is not None:
        text = textwrap.dedent(text) # Remove indentation
        text += "\n"
        text += "###### Spin parameters\n"

        for _, avail_spin in enumerate(data.parameters.physical.spin):
            text += "\n"
            text += f"""<h6 children="{avail_spin.bibref.shortbib}" class="dashed" style="margin-top: 5px; margin-bottom: 0;"/>\n\n"""
            text += f"RA0 (deg): `{avail_spin.RA0.value}`\n"
            text += f"DEC0 (deg): `{avail_spin.DEC0.value}`\n"

    card = html.Div(
        dcc.Markdown(
            text,
            dangerously_allow_html=True,
            className="markdown markdown-pre",
        ),
        className="ps-2 pe-2",
    )
    return card

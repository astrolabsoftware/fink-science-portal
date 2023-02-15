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
import visdcc

from app import app, APIURL

from apps.plotting import all_radio_options
from apps.utils import pil_to_b64
from apps.utils import generate_qr
from apps.utils import class_colors

from fink_utils.xmatch.simbad import get_simbad_labels

import pandas as pd
import numpy as np
import urllib

def card_lightcurve_summary():
    """ Add a card containing the lightcurve

    Returns
    ----------
    card: dbc.Card
        Card with the cutouts drawn inside
    """
    card = dmc.Paper(
        [
            dcc.Graph(
                id='lightcurve_cutouts',
                style={
                    'width': '100%',
                    'height': '25pc'
                },
                config={'displayModeBar': False}
            ),
            dbc.Row(
                dbc.Col(
                    dmc.ChipGroup(
                        [
                            dmc.Chip(x, value=x, variant="outline", color="orange", radius="xl", size="sm")
                            for x in all_radio_options.keys()
                        ],
                        id="switch-mag-flux",
                        value="Difference magnitude",
                        spacing="xl",
                        position='center',
                        multiple=False,
                    )
                )
            ),
            dmc.Accordion(
                children=[
                    dmc.AccordionItem(
                        [
                            dmc.AccordionPanel("Information"),
                            dmc.AccordionControl(
                                dcc.Markdown(
                                    """
                                    Circles (&#9679;) with error bars show valid alerts that pass the Fink quality cuts.
                                    In addition, the _Difference magnitude_ view shows:
                                    - upper triangles with errors (&#9650;), representing alert measurements that do not satisfy Fink quality cuts, but are nevetheless contained in the history of valid alerts and used by classifiers.
                                    - lower triangles (&#9661;), representing 5-sigma mag limit in difference image based on PSF-fit photometry contained in the history of valid alerts.
                                    """
                                )
                            ),
                        ],
                        value='info'
                    ),
                ],
            )
        ], radius='xl', p='md', shadow='xl', withBorder=True
    )
    return card

def card_explanation_xmatch():
    """ Explain how xmatch works
    """
    msg = """
    The Fink Xmatch service allows you to cross-match your catalog data with
    all Fink alert data processed so far (more than 60 million alerts, from ZTF). Just drag and drop
    a csv file containing at least position columns named `RA` and `Dec`, and a
    column containing ids named `ID` (could be string, integer, ... anything to identify your objects). Required column names are case insensitive. The catalog can also contained
    other columns that will be displayed.

    The xmatch service will perform a conesearch around the positions with a fix radius of 1.5 arcseconds.
    The initializer for RA/Dec is very flexible and supports inputs provided in a number of convenient formats.
    The following ways of declaring positions are all equivalent:

    * 271.3914265, 45.2545134
    * 271d23m29.1354s, 45d15m16.2482s
    * 18h05m33.9424s, +45d15m16.2482s
    * 18 05 33.9424, +45 15 16.2482
    * 18:05:33.9424, 45:15:16.2482

    The final table will contain the original columns of your catalog for all rows matching a Fink object, with two new columns:

    * `objectId`: clickable ZTF objectId.
    * `classification`: the class of the last alert received for this object, inferred by Fink.

    This service is still experimental, and your feedback is welcome. Note that the system will limit to the first 1000 rows of your file (or 5MB max) for the moment.
    Contact us by opening an [issue](https://github.com/astrolabsoftware/fink-science-portal/issues) if you need other file formats or encounter problems.
    """
    card = dbc.Card(
        dbc.CardBody(
            dcc.Markdown(msg)
        ), style={
            'backgroundColor': 'rgb(248, 248, 248, .7)'
        }
    )
    return card

def create_external_links(ra0, dec0):
    """
    """
    buttons = [
        dbc.Row(
            [
                dbc.Col(
                    dbc.Button(
                        className='btn btn-default btn-circle btn-lg',
                        style={'background-image': 'url(/assets/buttons/tns_logo.png)', 'background-size': 'cover'},
                        color='dark',
                        outline=True,
                        id='TNS',
                        target="_blank",
                        href='https://www.wis-tns.org/search?ra={}&decl={}&radius=5&coords_unit=arcsec'.format(ra0, dec0)
                    )
                ),
                dbc.Col(
                    dbc.Button(
                        className='btn btn-default btn-circle btn-lg',
                        style={'background-image': 'url(/assets/buttons/simbad.png)', 'background-size': 'cover'},
                        color='dark',
                        outline=True,
                        id='SIMBAD',
                        target="_blank",
                        href="http://simbad.u-strasbg.fr/simbad/sim-coo?Coord={}%20{}&Radius=0.08".format(ra0, dec0)
                    )
                ),
                dbc.Col(
                    dbc.Button(
                        className='btn btn-default btn-circle btn-lg',
                        style={'background-image': 'url(/assets/buttons/snad.svg)', 'background-size': 'cover'},
                        color='dark',
                        outline=True,
                        id='SNAD',
                        target="_blank",
                        href='https://ztf.snad.space/search/{} {}/{}'.format(ra0, dec0, 5)
                    )
                ),
            ], justify='around'
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Button(
                        className='btn btn-default btn-circle btn-lg',
                        style={'background-image': 'url(/assets/buttons/NEDVectorLogo_WebBanner_100pxTall_2NoStars.png)', 'background-size': 'cover'},
                        color='dark',
                        outline=True,
                        id='NED',
                        target="_blank",
                        href="http://ned.ipac.caltech.edu/cgi-bin/objsearch?search_type=Near+Position+Search&in_csys=Equatorial&in_equinox=J2000.0&ra={}&dec={}&radius=1.0&obj_sort=Distance+to+search+center&img_stamp=Yes".format(ra0, dec0)
                    ),
                ),
                dbc.Col(
                    dbc.Button(
                        className='btn btn-default btn-circle btn-lg',
                        style={'background-image': 'url(/assets/buttons/sdssIVlogo.png)', 'background-size': 'cover'},
                        color='dark',
                        outline=True,
                        id='SDSS',
                        target="_blank",
                        href="http://skyserver.sdss.org/dr13/en/tools/chart/navi.aspx?ra={}&dec={}".format(ra0, dec0)
                    ),
                )
            ], justify='around'
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Button(
                        className='btn btn-default btn-circle btn-lg',
                        style={'background-image': 'url(/assets/buttons/asassn.png)', 'background-size': 'cover'},
                        color='dark',
                        outline=True,
                        id='ASAS-SN',
                        target="_blank",
                        href="https://asas-sn.osu.edu/?ra={}&dec={}".format(ra0, dec0)
                    ),
                )
            ], justify='around'
        ),
    ]
    return buttons

@app.callback(
    Output('card_id_col', 'children'),
    [
        Input('object-data', 'children'),
    ])
def card_id(object_data):
    """ Add a card containing basic alert data
    """
    pdf = pd.read_json(object_data)
    objectid = pdf['i:objectId'].values[0]
    ra0 = pdf['i:ra'].values[0]
    dec0 = pdf['i:dec'].values[0]

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

    python_download = """import requests
import pandas as pd
import io

# get data for ZTF19acnjwgm
r = requests.post(
    '{}/api/v1/objects',
    json={{
        'objectId': '{}',
        'output-format': 'json'
    }}
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))""".format(
        APIURL,
        objectid
    )

    curl_download = """
curl -H "Content-Type: application/json" -X POST \\
    -d '{{"objectId":"{}", "output-format":"csv"}}' \\
    {}/api/v1/objects \\
    -o {}.csv
    """.format(objectid, APIURL, objectid)

    download_tab = dmc.Tabs(
        [
            dmc.TabsList(
                [
                    dmc.Tab("Python", value="Python"),
                    dmc.Tab("Curl", value="Curl"),
                ],
            ),
            dmc.TabsPanel(dmc.Prism(children=python_download, language="python"), value="Python"),
            dmc.TabsPanel(children=dmc.Prism(children=curl_download, language="bash"), value="Curl"),
        ],
        color="red", value="Python"
    )

    qrdata = "https://fink-portal.org/{}".format(objectid)
    qrimg = generate_qr(qrdata)

    qrcode = html.Img(src="data:image/png;base64, " + pil_to_b64(qrimg), height='20%')

    card = dmc.AccordionMultiple(
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Last alert cutouts",
                        icon=[
                            DashIconify(
                                icon="tabler:flare",
                                color=dmc.theme.DEFAULT_COLORS["dark"][6],
                                width=20,
                            )
                        ],
                    ),
                    dmc.AccordionPanel(
                        [
                            dmc.Paper(
                                [
                                    dbc.Row(id='stamps', justify='around', className="g-0"),
                                    dbc.Modal(
                                        [
                                            dbc.ModalHeader(
                                                dmc.Select(
                                                    label="",
                                                    placeholder="Select a date",
                                                    searchable=True,
                                                    nothingFound="No options found",
                                                    id="date_modal_select",
                                                    value=None,
                                                    data=[
                                                        {"value": i, "label": i} for i in pdf['v:lastdate'].values
                                                    ],
                                                    style={"width": 200, "marginBottom": 10},
                                                    zIndex=10000000,
                                                ),
                                                close_button=True,
                                                style={
                                                    'background-image': 'linear-gradient(rgba(150, 150, 150,0.3), rgba(255,255,255,0.3))'
                                                }
                                            ),
                                            dbc.ModalBody(
                                                [
                                                    dmc.Group(
                                                        id="stamps_modal_content",
                                                        position='center',
                                                        spacing='xl'
                                                    ),
                                                ], style={
                                                    'background': 'rgba(255, 255, 255,0.0)',
                                                    'background-image': 'linear-gradient(rgba(255, 255, 255,0.0), rgba(255,255,255,0.0))'
                                                }
                                            ),
                                        ],
                                        id="stamps_modal",
                                        scrollable=True,
                                        centered=True,
                                        size='xl'
                                    ),
                                ],
                                radius='xl', p='md', shadow='xl', withBorder=True
                            ),
                            dmc.Space(h=4),
                            dmc.Center(
                                dmc.ActionIcon(
                                    DashIconify(icon="tabler:arrows-maximize"),
                                    id="maximise_stamps",
                                    n_clicks=0,
                                    variant="default",
                                    radius=30,
                                    size=36,
                                    color='gray'
                                ),
                            ),
                        ],
                    ),
                ],
                value='stamps'
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Coordinates",
                        icon=[
                            DashIconify(
                                icon="tabler:target",
                                color=dmc.theme.DEFAULT_COLORS["orange"][6],
                                width=20,
                            )
                        ],
                    ),
                    dmc.AccordionPanel(
                        [
                            html.Div(id='coordinates'),
                            dbc.Row(
                                dbc.Col(
                                    dmc.ChipGroup(
                                        [
                                            dmc.Chip(x, value=x, variant="outline", color="orange", radius="xl", size="sm")
                                            for x in ['EQU', 'GAL']
                                        ],
                                        id="coordinates_chips",
                                        value="EQU",
                                        spacing="xl",
                                        position='center',
                                        multiple=False,
                                    )
                                )
                            ),
                        ],
                    ),
                ],
                value='coordinates'
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Last alert content",
                        icon=[
                            DashIconify(
                                icon="tabler:file-description",
                                color=dmc.theme.DEFAULT_COLORS["blue"][6],
                                width=20,
                            )
                        ],
                    ),
                    dmc.AccordionPanel(
                        html.Div([], id='alert_table'),
                    ),
                ],
                value='last_alert'
            ),
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
                            download_tab,
                            dcc.Markdown('See {}/api for more options'.format(APIURL)),
                        ],
                    ),
                ],
                value='api'
            ),
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
                        dmc.Stack(
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
                                    ],
                                    radius='xl', p='md', shadow='xl', withBorder=True
                                ),
                                html.Br(),
                                *create_external_links(ra0, dec0)
                            ],
                            align='center'
                        )
                    ),
                ],
                value='external'
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Share",
                        icon=[
                            DashIconify(
                                icon="tabler:share",
                                color=dmc.theme.DEFAULT_COLORS["gray"][6],
                                width=20,
                            )
                        ],
                    ),
                    dmc.AccordionPanel(
                        [
                            dmc.Center(qrcode, style={'width': '100%', 'height': '200'})
                        ],
                    ),
                ],
                value='qr'
            ),
        ],
        value='stamps'
    )

    return card

@app.callback(
    Output("stamps_modal", "is_open"),
    Input("maximise_stamps", "n_clicks"),
    Input("maximise_stamps", "n_clicks"),
    Input("maximise_stamps", "n_clicks"),
    State("stamps_modal", "is_open"),
    prevent_initial_call=True,
)
def modal_stamps(nc1, nc2, nc3, opened):
    return not opened

@app.callback(
    Output('card_id_left', 'children'),
    [
        Input('object-data', 'children'),
        Input('object-uppervalid', 'children'),
        Input('object-upper', 'children')
    ])
def card_id1(object_data, object_uppervalid, object_upper):
    """ Add a card containing basic alert data
    """
    pdf = pd.read_json(object_data)

    objectid = pdf['i:objectId'].values[0]
    date_end = pdf['v:lastdate'].values[0]
    discovery_date = pdf['v:lastdate'].values[-1]
    jds = pdf['i:jd'].values
    ndet = len(pdf)

    pdf_upper_valid = pd.read_json(object_uppervalid)
    if not pdf_upper_valid.empty:
        mask = pdf_upper_valid['i:jd'].apply(lambda x: x not in jds)
        nupper_valid = len(pdf_upper_valid[mask])
    else:
        nupper_valid = 0

    pdf_upper = pd.read_json(object_upper)
    if not pdf_upper.empty:
        nupper = len(pdf_upper)
    else:
        nupper = 0

    simbad_types = get_simbad_labels('old_and_new')
    simbad_types = sorted(simbad_types, key=lambda s: s.lower())

    badges = []
    for c in np.unique(pdf['v:classification']):
        if c in simbad_types:
            color = class_colors['Simbad']
        elif c in class_colors.keys():
            color = class_colors[c]
        else:
            # Sometimes SIMBAD mess up names :-)
            color = class_colors['Simbad']

        badges.append(
            dmc.Badge(
                c,
                color=color,
                variant="dot",
            )
        )

    card = dmc.Paper(
        [
            dbc.Row(
                [
                    dbc.Col(dmc.Avatar(src="/assets/Fink_SecondaryLogo_WEB.png", size='lg'), width=2),
                    dbc.Col(dmc.Title(objectid, order=1, style={'color': '#15284F'}), width=10),
                ], justify='start', align="center"
            ),
            html.Div(badges),
            dcc.Markdown(
                """
                ```python
                Discovery date: {}
                Last detection: {}
                Number of detections: {}
                Number of low quality alerts: {}
                Number of upper limits: {}
                ```
                """.format(
                    discovery_date, date_end, ndet, nupper_valid, nupper)
            ),
        ], radius='xl', p='md', shadow='xl', withBorder=True
    )
    return card

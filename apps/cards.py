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
from apps.utils import queryMPC, convert_mpc_type
from apps.utils import pil_to_b64
from apps.utils import generate_qr
from apps.utils import class_colors

from fink_utils.xmatch.simbad import get_simbad_labels

from astropy.time import Time
import pandas as pd
import numpy as np
import urllib

def card_cutouts(is_mobile):
    """ Add a card containing cutouts

    Returns
    ----------
    card: dbc.Card
        Card with the cutouts drawn inside
    """
    if not is_mobile:
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
                        dmc.Chips(
                            data=[
                                {'label': k, 'value': k} for k in all_radio_options.keys()
                            ],
                            id="switch-mag-flux",
                            value="Difference magnitude",
                            color="orange",
                            radius="xl",
                            size="sm",
                            spacing="xl",
                            variant="outline",
                            position='center',
                            multiple=False,
                        )
                    )
                ),
                dmc.Accordion(
                    children=[
                        dmc.AccordionItem(
                            dcc.Markdown(
                                """
                                Circles (&#9679;) with error bars show valid alerts that pass the Fink quality cuts.
                                In addition, the _Difference magnitude_ view shows:
                                - upper triangles with errors (&#9650;), representing alert measurements that do not satisfy Fink quality cuts, but are nevetheless contained in the history of valid alerts and used by classifiers.
                                - lower triangles (&#9661;), representing 5-sigma mag limit in difference image based on PSF-fit photometry contained in the history of valid alerts.
                                """
                            ),
                            label="Information",
                        ),
                    ],
                    state={'0': True}
                )
            ], radius='xl', p='md', shadow='xl', withBorder=True
        )
    else:
        card = dbc.Row(id='stamps_mobile', justify='around')
    return card




def card_sso_lightcurve():
    """ Add a card to display SSO lightcurve

    Returns
    ----------
    card: dbc.Card
        Card with the SSO lightcurve
    """
    card = html.Div(id='sso_lightcurve')
    return card

def card_sso_radec():
    """ Add a card to display SSO radec

    Returns
    ----------
    card: dbc.Card
        Card with the SSO radec
    """
    card = html.Div(id='sso_radec')
    return card

def card_sso_residual():
    """ Add a card to display SSO residuals (observation - ephemerides)

    Returns
    ----------
    card: dbc.Card
        Card with the SSO residual
    """
    card = html.Div(id='sso_residual')
    return card

def card_sso_astrometry():
    """ Add a card to display SSO astrometry

    Returns
    ----------
    card: dbc.Card
        Card with the SSO astrometry
    """
    card = html.Div(id='sso_astrometry')
    return card

def card_sso_phasecurve():
    """ Add a card to display SSO phase curve

    Returns
    ----------
    card: dbc.Card
        Card with the SSO phase curve
    """
    card = html.Div(id='sso_phasecurve')
    return card

def card_tracklet_lightcurve():
    """ Add a card to display tracklet lightcurve
    Returns
    ----------
    card: dbc.Card
        Card with the tracklet lightcurve
    """
    card = html.Div(id='tracklet_lightcurve')
    return card

def card_tracklet_radec():
    """ Add a card to display tracklet radec
    Returns
    ----------
    card: dbc.Card
        Card with the tracklet radec
    """
    card = html.Div(id='tracklet_radec')

    return card

def card_sso_skymap():
    """ Display the sky map in the explorer tab results (Aladin lite)

    It uses `visdcc` to execute javascript directly.

    Returns
    ---------
    out: list of objects
    """
    return html.Div(
        [
            visdcc.Run_js(id='aladin-lite-div-skymap_sso'),
            dcc.Markdown('_Hit the Aladin Lite fullscreen button if the image is not displayed (we are working on it...)_'),
        ], style={
            'width': '100%',
            'height': '25pc'
        }
    )

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

# get data for ZTF19acnjwgm
r = requests.post(
    '{}/api/v1/objects',
    json={{
        'objectId': '{}',
        'output-format': 'json'
    }}
)

# Format output in a DataFrame
pdf = pd.read_json(r.content)""".format(
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
        color="red",
        children=[
            dmc.Tab(label="Python", children=dmc.Prism(children=python_download, language="python")),
            dmc.Tab(label="Curl", children=dmc.Prism(children=curl_download, language="bash")),
        ]
    )

    card = dmc.Accordion(
        state={"0": True, **{"{}".format(i+1): False for i in range(3)}},
        multiple=True,
        offsetIcon=False,
        disableIconRotation=True,
        children=[
            dmc.AccordionItem(
                [
                    dmc.Paper(
                        dbc.Row(id='stamps', justify='around', className="g-0"),
                        radius='xl', p='md', shadow='xl', withBorder=True
                    )
                ],
                label="Last alert cutouts",
                icon=[
                    DashIconify(
                        icon="tabler:flare",
                        color=dmc.theme.DEFAULT_COLORS["dark"][6],
                        width=20,
                    )
                ],
            ),
            dmc.AccordionItem(
                html.Div([], id='alert_table'),
                label="Last alert content",
                icon=[
                    DashIconify(
                        icon="tabler:file-description",
                        color=dmc.theme.DEFAULT_COLORS["blue"][6],
                        width=20,
                    )
                ],
            ),
            dmc.AccordionItem(
                [
                    download_tab,
                    dcc.Markdown('See {}/api for more options'.format(APIURL)),
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
                    html.Br(),
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Button(
                                    className='btn btn-default zoom btn-circle btn-lg',
                                    style={'background-image': 'url(/assets/buttons/tns_logo.png)', 'background-size': 'cover'},
                                    color='dark',
                                    outline=True,
                                    id='TNS',
                                    target="_blank",
                                    href='https://www.wis-tns.org/search?ra={}&decl={}&radius=5&coords_unit=arcsec'.format(ra0, dec0)
                                ), width=4),
                            dbc.Col(
                                dbc.Button(
                                    className='btn btn-default zoom btn-circle btn-lg',
                                    style={'background-image': 'url(/assets/buttons/simbad.png)', 'background-size': 'cover'},
                                    color='dark',
                                    outline=True,
                                    id='SIMBAD',
                                    target="_blank",
                                    href="http://simbad.u-strasbg.fr/simbad/sim-coo?Coord={}%20{}&Radius=0.08".format(ra0, dec0)
                                ), width=4
                            ),
                            dbc.Col(
                                dbc.Button(
                                    className='btn btn-default zoom btn-circle btn-lg',
                                    style={'background-image': 'url(/assets/buttons/snad.svg)', 'background-size': 'cover'},
                                    color='dark',
                                    outline=True,
                                    id='SNAD',
                                    target="_blank",
                                    href='https://ztf.snad.space/search/{} {}/{}'.format(ra0, dec0, 5)
                                ), width=4),
                        ], justify='around'
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Button(
                                    className='btn btn-default zoom btn-circle btn-lg',
                                    style={'background-image': 'url(/assets/buttons/NEDVectorLogo_WebBanner_100pxTall_2NoStars.png)', 'background-size': 'cover'},
                                    color='dark',
                                    outline=True,
                                    id='NED',
                                    target="_blank",
                                    href="http://ned.ipac.caltech.edu/cgi-bin/objsearch?search_type=Near+Position+Search&in_csys=Equatorial&in_equinox=J2000.0&ra={}&dec={}&radius=1.0&obj_sort=Distance+to+search+center&img_stamp=Yes".format(ra0, dec0)
                                ), width=4
                            ),
                            dbc.Col(
                                dbc.Button(
                                    className='btn btn-default zoom btn-circle btn-lg',
                                    style={'background-image': 'url(/assets/buttons/sdssIVlogo.png)', 'background-size': 'cover'},
                                    color='dark',
                                    outline=True,
                                    id='SDSS',
                                    target="_blank",
                                    href="http://skyserver.sdss.org/dr13/en/tools/chart/navi.aspx?ra={}&dec={}".format(ra0, dec0)
                                ), width=4
                            )
                        ], justify='center'
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
            ),
        ],
    )

    qrdata = "https://fink-portal.org/{}".format(objectid)
    qrimg = generate_qr(qrdata)

    qrcode = html.Img(src="data:image/png;base64, " + pil_to_b64(qrimg), height='20%')

    return html.Div([card, dmc.Center(qrcode, style={'width': '100%', 'height': '200'})])

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

def card_download(pdf):
    """ Card containing a button to download object data
    """
    objectid = pdf['i:objectId'].values[0]
    card = dbc.Card(
        [
            dbc.ButtonGroup([
                dbc.Button(
                    html.A(
                        'Download Object Data',
                        id="download-link",
                        download="{}.csv".format(objectid),
                        href=generate_download_link(pdf),
                        target="_blank", style={"color": "white"}),
                    id='download',
                    target="_blank",
                    href=""
                )
            ])
        ],
        className="mt-3", body=True
    )
    return card

def generate_download_link(pdf):
    """ Crappy way for downloading data as csv. The URL is modified on-the-fly.
    TODO: try https://github.com/thedirtyfew/dash-extensions/
    """
    if pdf.empty:
        return ""
    else:
        # drop cutouts from download for the moment
        pdf = pdf.drop(
            columns=[
                'b:cutoutDifference_stampData',
                'b:cutoutScience_stampData',
                'b:cutoutTemplate_stampData'
            ]
        )
        csv_string = pdf.to_csv(index=False, encoding='utf-8')
        csv_string = "data:text/csv;charset=utf-8," + urllib.parse.quote(csv_string)
        return csv_string

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
    ---
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
        card = dbc.Card(
            [
                html.H5("Name: None", className="card-title"),
                html.H6("Orbit type: None", className="card-subtitle"),
                dcc.Markdown(
                    template.format(*([None] * 14))
                )
            ],
            className="mt-3", body=True
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

    card = dbc.Card(
        [
            *download_sso_modal(ssnamenr),
            dcc.Markdown("""---"""),
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
        ],
        className="mt-3", body=True
    )
    return card

def download_sso_modal(ssnamenr):
    message_download_sso = """
    In a terminal, simply paste (CSV):

    ```bash
    curl -H "Content-Type: application/json" -X POST \\
        -d '{{"n_or_d":"{}", "output-format":"csv"}}' \\
        {}/api/v1/sso -o {}.csv
    ```

    Or in a python terminal, simply paste:

    ```python
    import requests
    import pandas as pd

    r = requests.post(
      '{}/api/v1/sso',
      json={{
        'n_or_d': '{}',
        'output-format': 'json'
      }}
    )

    # Format output in a DataFrame
    pdf = pd.read_json(r.content)
    ```

    See {}/api for more options.
    """.format(
        ssnamenr,
        APIURL,
        str(ssnamenr).replace('/', '_'),
        APIURL,
        ssnamenr,
        APIURL
    )
    modal = [
        dbc.Button(
            "Download {} data".format(ssnamenr),
            id="open-sso",
            color='dark', outline=True
        ),
        dbc.Modal(
            [
                dbc.ModalBody(
                    dcc.Markdown(message_download_sso),
                    style={
                        'background-image': 'linear-gradient(rgba(255,255,255,0.2), rgba(255,255,255,0.4)), url(/assets/background.png)'
                    }
                ),
                dbc.ModalFooter(
                    dbc.Button(
                        "Close",
                        id="close-sso",
                        className="ml-auto",
                        color='dark',
                        outline=True
                    )
                ),
            ],
            id="modal-sso", scrollable=True
        ),
    ]
    return modal

@app.callback(
    Output("modal-sso", "is_open"),
    [Input("open-sso", "n_clicks"), Input("close-sso", "n_clicks")],
    [State("modal-sso", "is_open")],
)
def toggle_modal_sso(n1, n2, is_open):
    """ Callback for the modal (open/close)
    """
    if n1 or n2:
        return not is_open
    return is_open

def download_object_modal(objectid):
    message_download = """
    ### {}
    In a terminal, simply paste (CSV):

    ```bash
    curl -H "Content-Type: application/json" -X POST \\
        -d '{{"objectId":"{}", "output-format":"csv"}}' \\
        {}/api/v1/objects \\
        -o {}.csv
    ```

    Or in a python terminal, simply paste:

    ```python
    import requests
    import pandas as pd

    # get data for ZTF19acnjwgm
    r = requests.post(
      '{}/api/v1/objects',
      json={{
        'objectId': '{}',
        'output-format': 'json'
      }}
    )

    # Format output in a DataFrame
    pdf = pd.read_json(r.content)
    ```

    See {}/api for more options.
    """.format(
        objectid,
        objectid,
        APIURL,
        str(objectid).replace('/', '_'),
        APIURL,
        objectid,
        APIURL
    )
    modal = [
        html.Div(
            dbc.Button(
                "Get object data",
                id="open-object",
                color='dark', outline=True,
                style={'width': '100%', 'display': 'inline-block'}
            ), className='d-grid gap-2', style={'width': '100%', 'display': 'inline-block'}
        ),
        dbc.Modal(
            [
                dbc.ModalBody(
                    dcc.Markdown(message_download),
                    style={
                        'background-image': 'linear-gradient(rgba(255,255,255,0.2), rgba(255,255,255,0.4)), url(/assets/background.png)'
                    }
                ),
                dbc.ModalFooter(
                    dbc.Button(
                        "Close",
                        color='dark', outline=True,
                        id="close-object", className="ml-auto"
                    )
                ),
            ],
            id="modal-object", scrollable=True
        ),
    ]
    return modal

def inspect_object_modal(objectid):
    message = """
    ### {}
    Here are the fields contained in the last alert for {}. Note you can filter the
    table results using the first row (enter text and hit enter).
    - Fields starting with `i:` are original fields from ZTF.
    - Fields starting with `d:` are live added values by Fink.
    - Fields starting with `v:` are added values by Fink (post-processing).

    See {}/api/v1/columns for more information.
    """.format(objectid, objectid, APIURL)
    modal = [
        html.Div(
            dbc.Button(
                "Inspect alert data",
                id="open-object-prop",
                color='dark', outline=True,
                style={'width': '100%', 'display': 'inline-block'}
            ), className='d-grid gap-2', style={'width': '100%', 'display': 'inline-block'}
        ),
        dbc.Modal(
            [
                dbc.ModalBody(
                    [
                        dcc.Markdown(message),
                        html.Div([], id='alert_table')
                    ], style={
                        'background-image': 'linear-gradient(rgba(255,255,255,0.4), rgba(255,255,255,0.6)), url(/assets/background.png)'
                    }
                ),
                dbc.ModalFooter(
                    dbc.Button(
                        "Close",
                        color='dark', outline=True,
                        id="close-object-prop",
                        className="ml-auto"
                    )
                ),
            ],
            id="modal-object-prop", scrollable=True
        ),
    ]
    return modal

@app.callback(
    Output("modal-object", "is_open"),
    [Input("open-object", "n_clicks"), Input("close-object", "n_clicks")],
    [State("modal-object", "is_open")],
)
def toggle_modal_object(n1, n2, is_open):
    """ Callback for the modal (open/close)
    """
    if n1 or n2:
        return not is_open
    return is_open

@app.callback(
    Output("modal-object-prop", "is_open"),
    [Input("open-object-prop", "n_clicks"), Input("close-object-prop", "n_clicks")],
    [State("modal-object-prop", "is_open")],
)
def toggle_modal_object_prop(n1, n2, is_open):
    """ Callback for the modal (open/close)
    """
    if n1 or n2:
        return not is_open
    return is_open

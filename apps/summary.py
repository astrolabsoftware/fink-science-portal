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
import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import visdcc
import plotly.graph_objects as go
import dash_mantine_components as dmc

import pandas as pd
import numpy as np
import requests

from app import app, client, clientU, clientUV, clientSSO, clientTRCK

from apps.supernovae.cards import card_sn_scores
from apps.varstars.cards import card_explanation_variable
from apps.mulens.cards import card_explanation_mulens
from apps.mulens.cards import card_mulens_button
from apps.sso.cards import card_sso_left

from apps.cards import card_lightcurve_summary
from apps.cards import card_id, card_id1

from apps.plotting import plot_classbar
from apps.plotting import all_radio_options

from apps.utils import format_hbase_output
from apps.utils import get_miriade_data
from apps.utils import pil_to_b64
from apps.utils import generate_qr

from app import APIURL

dcc.Location(id='url', refresh=False)

def tab1_content():
    """ Summary tab
    """
    tab1_content_ = html.Div([
        dbc.Row(
            [
                dbc.Col(
                    dcc.Graph(
                        style={
                            'width': '100%',
                            'height': '4pc'
                        },
                        config={'displayModeBar': False},
                        id='classbar'
                    ),
                    width=12
                ),
            ], justify='around'
        ),
        dbc.Row([
            dbc.Col(card_lightcurve_summary(is_mobile=False), width=8),
            dbc.Col(id="card_id_col", width=4)
        ]),
    ])

    out = dmc.LoadingOverlay(
        tab1_content_,
        loaderProps={"variant": "dots", "color": "orange", "size": "xl"}
    )
    return out

def tab2_content():
    """ Supernova tab
    """
    tab2_content_ = html.Div([
        dbc.Row([
            dbc.Col(card_sn_scores(), width=8),
            dbc.Col(id='card_sn_properties', width=4)
        ]),
    ])
    return tab2_content_

def tab3_content():
    """ Variable stars tab
    """
    tab3_content_ = html.Div([
        dbc.Row([
            dbc.Col(
                dmc.LoadingOverlay(
                    dmc.Paper(
                        [
                            html.Div(id='variable_plot'),
                            html.Br(),
                            card_explanation_variable()
                        ], radius='xl', p='md', shadow='xl', withBorder=True
                    ), loaderProps={"variant": "dots", "color": "orange", "size": "xl"},
                ), width=8
            ),
            dbc.Col(id="card_variable_button", width=4)
        ]),
    ])
    return tab3_content_

def tab4_content(pdf):
    """ Microlensing tab
    """
    tab4_content_ = html.Div([
        dbc.Row([
            dbc.Col(
                dmc.LoadingOverlay(
                    dmc.Paper(
                        [
                            html.Div(id='mulens_plot'),
                            html.Br(),
                            card_explanation_mulens()
                        ], radius='xl', p='md', shadow='xl', withBorder=True
                    ), loaderProps={"variant": "dots", "color": "orange", "size": "xl"},
                ), width=8
            ),
            dbc.Col([card_mulens_button(pdf)], width=4)
        ]),
    ])
    return tab4_content_

def tab5_content(pdf):
    """ SSO tab
    """
    ssnamenr = pdf['i:ssnamenr'].values[0]

    msg = """
    **Top:** lightcurve from ZTF, with ephemerides provided by the
    [Miriade ephemeride service](https://ssp.imcce.fr/webservices/miriade/api/ephemcc/).

    **Bottom:** (asteroids only) residuals between observed and predicted magnitude
    as a function of the ecliptic longitude. The variations are most-likely due
    to the difference of aspect angle: the object is not a perfect sphere, and we
    are seeing its oblateness here. The solid lines are sinusoidal fits to the residuals.
    """
    tab1 = dbc.Row(
        [
            dbc.Col(
                [
                    html.Div(id='sso_lightcurve'),
                    html.Br(),
                    html.Div(id='sso_residual'),
                    dmc.Accordion(
                        children=[
                            dmc.AccordionItem(
                                dcc.Markdown(msg),
                                label="Information",
                            ),
                        ],
                    )
                ]
            ),
        ]
    )

    tab2 = dbc.Row(
        [
            dbc.Col(
                [
                    html.Div(id='sso_astrometry'),
                    dmc.Accordion(
                        children=[
                            dmc.AccordionItem(
                                dcc.Markdown("The residuals are the difference between the alert positions and the positions returned by the [Miriade ephemeride service](https://ssp.imcce.fr/webservices/miriade/api/ephemcc/)."),
                                label="How are computed the residuals?",
                            ),
                        ],
                    )
                ]
            ),
        ]
    )

    msg_phase = """
    By default, the data is modeled after the three-parameter H, G1, G2 magnitude phase function for asteroids
    from [Muinonen et al. 2010](https://doi.org/10.1016/j.icarus.2010.04.003).
    We use the implementation in [sbpy](https://sbpy.readthedocs.io/en/latest/sbpy/photometry.html#disk-integrated-phase-function-models) to fit the data.

    We propose two cases, one fitting bands separately, and
    the other fitting both bands simultaneously (rescaled). We
    also propose different phase curve modeling using the HG12 and HG models.
    Hit buttons to see the fitted values!
    """

    tab3 = dbc.Row(
        [
            dbc.Col(
                [
                    html.Div(id='sso_phasecurve'),
                    html.Br(),
                    dbc.Row(
                        dbc.Col(
                            dmc.Chips(
                                data=[
                                    {'label': 'per-band', 'value': 'per-band'},
                                    {'label': 'combined', 'value': 'combined'}
                                ],
                                id="switch-phase-curve-band",
                                value="per-band",
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
                    dbc.Row(
                        dbc.Col(
                            dmc.Chips(
                                data=[
                                    {'label': 'HG1G2', 'value': 'HG1G2'},
                                    {'label': 'HG12', 'value': 'HG12'},
                                    {'label': 'HG', 'value': 'HG'},
                                ],
                                id="switch-phase-curve-func",
                                value="HG1G2",
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
                                dcc.Markdown(msg_phase),
                                label="How is modeled the phase curve?",
                            ),
                        ],
                    )
                ]
            ),
        ]
    )

    if ssnamenr != 'null':
        left_side = dbc.Col(
            dmc.Tabs(
                [
                    dmc.Tab(tab1, label="Lightcurve"),
                    dmc.Tab(tab2, label="Astrometry"),
                    dmc.Tab(tab3, label="Phase curve")
                ],
                variant="outline"
            ), width=8
        )
    else:
        msg = """
        Object not referenced in the Minor Planet Center
        """
        left_side = dbc.Col([html.Br(), dbc.Alert(msg, color="danger")], width=8)
    tab5_content_ = dbc.Row(
        [
            left_side,
            dbc.Col(
                [
                    card_sso_left(ssnamenr)
                ], width=4
            )
        ]
    )
    return tab5_content_

def tab6_content(pdf):
    """ Tracklet tab
    """
    tab6_content_ = html.Div([
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Div(id="tracklet_lightcurve"),
                        html.Br(),
                        html.Div(id="tracklet_radec")
                    ]
                ),
            ]
        ),
    ])
    return tab6_content_

def tab_mobile_content(pdf):
    """ Content for mobile application
    """
    content_ = html.Div([
        dbc.Row(
            [
                dbc.Col(
                    dcc.Graph(
                        style={
                            'width': '100%',
                            'height': '4pc'
                        },
                        config={'displayModeBar': False},
                        id='classbar'
                    ),
                    width=12
                ),
            ], justify='around'
        ),
    ])
    return content_

def tabs(pdf, is_mobile):
    if is_mobile:
        tabs_ = tab_mobile_content(pdf)
    else:
        tabs_ = dmc.Tabs(
            [
                dmc.Tab(tab1_content(), label="Summary"),
                dmc.Tab(tab2_content(), label="Supernovae"),
                dmc.Tab(tab3_content(), label="Variable stars"),
                dmc.Tab(tab4_content(pdf), label="Microlensing"),
                dmc.Tab(tab5_content(pdf), label="Solar System"),
                dmc.Tab(tab6_content(pdf), label="Tracklets"),
                dmc.Tab(label="GRB", disabled=True)
            ], position='right', variant='outline'
        )
    return tabs_

def title(name, is_mobile):
    if is_mobile:
        header = [
            html.Hr(),
            dbc.Row(
                [
                    html.Img(src="/assets/Fink_SecondaryLogo_WEB.png", height='10%', width='10%'),
                    html.H5(children='{}'.format(name[1:]), id='name', style={'color': '#15284F'})
                ]
            ),
        ]
        title_ = html.Div(header)
    else:
        qrdata = "https://fink-portal.org/{}".format(name[1:])
        qrimg = generate_qr(qrdata)
        header = [
            dbc.Col(html.Img(src="data:image/png;base64, " + pil_to_b64(qrimg), height='90%', style={'min-width': '50px'}), width=2),
            dbc.Col(html.H1(children='{}'.format(name[1:]), id='name', style={'color': '#15284F'}), width=10)
        ]
        title_ = dbc.Card(
            dbc.CardHeader(
                [
                    dbc.Row(
                        header, style={'white-space': 'nowrap'}
                    )
                ]
            ),
        )
    return title_

@app.callback(
    Output('external_links', 'children'),
    Input('object-data', 'children')
)
def create_external_links(object_data):
    """ Create links to external website. Used in the mobile app.
    """
    pdf = pd.read_json(object_data)
    ra0 = pdf['i:ra'].values[0]
    dec0 = pdf['i:dec'].values[0]
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
                    ), width=4),
                dbc.Col(
                    dbc.Button(
                        className='btn btn-default btn-circle btn-lg',
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
                        className='btn btn-default btn-circle btn-lg',
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
                        className='btn btn-default btn-circle btn-lg',
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
                        className='btn btn-default btn-circle btn-lg',
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
    ]
    return buttons


def make_item(i):
    # we use this function to make the example items to avoid code duplication
    names = ["&#43; Lightcurve", '&#43; Last alert properties', '&#43; Aladin Lite', '&#43; External links']

    message = """
    Here are the fields contained in the last alert. Note you can filter the
    table results using the first row (enter text and hit enter).
    - Fields starting with `i:` are original fields from ZTF.
    - Fields starting with `d:` are live added values by Fink.
    - Fields starting with `v:` are added values by Fink (post-processing).

    See {}/api/v1/columns for more information.
    """.format(APIURL)

    information = html.Div(
        [
            dcc.Markdown(message),
            html.Div([], id='alert_table')
        ]
    )
    lightcurve = html.Div(
        [
            dcc.Graph(
                id='lightcurve_cutouts',
                style={
                    'width': '100%',
                    'height': '15pc'
                },
                config={'displayModeBar': False}
            ),
            html.Div(
                dbc.RadioItems(
                    options=[{'label': k, 'value': k} for k in all_radio_options.keys()],
                    value="Difference magnitude",
                    id="switch-mag-flux",
                    inline=True
                ), style={'display': 'none'}
            )
        ]
    )
    aladin = html.Div(
        [dcc.Markdown('Hit full screen if the display does not work'), visdcc.Run_js(id='aladin-lite-div2')],
        style={
            'width': '100%',
            'height': '25pc'
        }
    )
    external = dbc.CardBody(id='external_links')

    to_display = [lightcurve, information, aladin, external]

    header = html.H2(
        dbc.Button(
            html.H5(children=dcc.Markdown('{}'.format(names[i - 1])), style={'color': '#15284F'}),
            color='link',
            id=f"group-{i}-toggle",
            n_clicks=0,
        )
    )
    coll = dbc.Collapse(
        to_display[i - 1],
        id=f"collapse-{i}",
        is_open=False,
    )
    return html.Div([header, html.Hr(), coll])


accordion = html.Div(
    [make_item(1), make_item(2), make_item(3), make_item(4)], className="accordion"
)


@app.callback(
    [Output(f"collapse-{i}", "is_open") for i in range(1, 5)],
    [Input(f"group-{i}-toggle", "n_clicks") for i in range(1, 5)],
    [State(f"collapse-{i}", "is_open") for i in range(1, 5)],
)
def toggle_accordion(n1, n2, n3, n4, is_open1, is_open2, is_open3, is_open4):
    ctx = dash.callback_context

    if not ctx.triggered:
        return False, False, False, False
    else:
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "group-1-toggle" and n1:
        return not is_open1, False, False, False
    elif button_id == "group-2-toggle" and n2:
        return False, not is_open2, False, False
    elif button_id == "group-3-toggle" and n3:
        return False, False, not is_open3, False
    elif button_id == "group-4-toggle" and n4:
        return False, False, False, not is_open4
    return False, False, False, False

@app.callback(
    [
        Output('object-data', 'children'),
        Output('object-upper', 'children'),
        Output('object-uppervalid', 'children'),
        Output('object-sso', 'children'),
        Output('object-tracklet', 'children'),
    ],
    [
        Input('url', 'pathname'),
    ])
def store_query(name):
    """ Cache query results (data and upper limits) for easy re-use

    https://dash.plotly.com/sharing-data-between-callbacks
    """
    results = client.scan("", "key:key:{}".format(name[1:]), "*", 0, True, True)
    schema_client = client.schema()
    pdfs = format_hbase_output(results, schema_client, group_alerts=False)

    uppers = clientU.scan("", "key:key:{}".format(name[1:]), "*", 0, True, True)
    pdfsU = pd.DataFrame.from_dict(uppers, orient='index')

    uppersV = clientUV.scan("", "key:key:{}".format(name[1:]), "*", 0, True, True)
    pdfsUV = pd.DataFrame.from_dict(uppersV, orient='index')

    payload = pdfs['i:ssnamenr'].values[0]
    is_sso = np.alltrue([i == payload for i in pdfs['i:ssnamenr'].values])
    if str(payload) != 'null' and is_sso:
        results = clientSSO.scan(
            "",
            "key:key:{}_".format(payload),
            "*",
            0, True, True
        )
        schema_client_sso = clientSSO.schema()
        pdfsso = format_hbase_output(
            results, schema_client_sso,
            group_alerts=False, truncated=False, extract_color=False
        )

        if pdfsso.empty:
            # This can happen for SSO candidate with a ssnamenr
            # e.g. ZTF21abatnkh
            pdfsso = pd.DataFrame()
        else:
            # Extract miriade information as well
            pdfsso = get_miriade_data(pdfsso)
    else:
        pdfsso = pd.DataFrame()

    payload = pdfs['d:tracklet'].values[0]

    if str(payload).startswith('TRCK'):
        results = clientTRCK.scan(
            "",
            "key:key:{}".format(payload),
            "*",
            0, True, True
        )
        schema_client_tracklet = clientTRCK.schema()
        pdftracklet = format_hbase_output(
            results, schema_client_tracklet,
            group_alerts=False, truncated=False, extract_color=False
        )
    else:
        pdftracklet = pd.DataFrame()
    return pdfs.to_json(), pdfsU.to_json(), pdfsUV.to_json(), pdfsso.to_json(), pdftracklet.to_json()

def layout(name, is_mobile):
    # even if there is one object ID, this returns  several alerts
    r = requests.post(
        '{}/api/v1/objects'.format(APIURL),
        json={
            'objectId': name[1:],
        }
    )
    pdf = pd.read_json(r.content)

    qrdata = "https://fink-portal.org/{}".format(name[1:])
    qrimg = generate_qr(qrdata)

    if is_mobile:
        layout_ = html.Div(
            [
                html.Br(),
                html.Br(),
                dbc.Container(
                    [
                        dbc.Row(
                            [
                                dbc.Col(title(name, is_mobile), width={"size": 12, "offset": 0},),
                            ]
                        ),
                        dbc.Row(
                            [
                                dbc.Col([html.Br(), card_lightcurve_summary(is_mobile)], width={"size": 12, "offset": 0},),
                            ]
                        ),
                        dbc.Row(
                            [
                                dbc.Col(tabs(pdf, is_mobile), width=12)
                            ]
                        ),
                        html.Br(),
                        dbc.Row(
                            [
                                dbc.Col(accordion, width=12)
                            ]
                        ),
                        html.Br(),
                        dbc.Row(
                            [
                                html.Img(src="data:image/png;base64, " + pil_to_b64(qrimg), height='50%', width='50%'),
                            ], justify="center"
                        ),
                    ], id='webinprog', fluid=True, style={'width': '100%'}
                ),
            html.Div(id='object-data', style={'display': 'none'}),
            html.Div(id='object-upper', style={'display': 'none'}),
            html.Div(id='object-uppervalid', style={'display': 'none'}),
            html.Div(id='object-sso', style={'display': 'none'}),
            html.Div(id='object-tracklet', style={'display': 'none'}),
            ],
            className='home',
            style={
                'background-image': 'linear-gradient(rgba(255,255,255,0.6), rgba(255,255,255,0.6)), url(/assets/background.png)'
            }
        )
    else:
        layout_ = html.Div(
            [
                html.Br(),
                html.Br(),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Br(),
                                html.Div(id="card_id_left"),
                                html.Br(),
                                html.Br(),
                                html.Div(
                                    [visdcc.Run_js(id='aladin-lite-div')],
                                    style={
                                        'width': '100%',
                                        'height': '25pc',
                                    }, className='roundimg nozoom'
                                ),
                                html.Br(),
                            ], width={"size": 3},
                        ),
                        dbc.Col(tabs(pdf, is_mobile), width=8)
                    ],
                    justify="around", className="g-0"
                ),
                html.Div(id='object-data', style={'display': 'none'}),
                html.Div(id='object-upper', style={'display': 'none'}),
                html.Div(id='object-uppervalid', style={'display': 'none'}),
                html.Div(id='object-sso', style={'display': 'none'}),
                html.Div(id='object-tracklet', style={'display': 'none'}),
            ], className='home', style={'background-image': 'linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(/assets/background.png)', 'background-size': 'contain'}
        )

    return layout_

@app.callback(
    Output('aladin-lite-div2', 'run'),
    [
        Input('object-data', 'children'),
        Input(f"group-3-toggle", "n_clicks")
    ],
    [
        State(f"collapse-3", "is_open")
    ]
)
def integrate_aladin_lite_mobile(object_data, n3, is_open3):
    """ Integrate aladin light in the mobile app.

    the default parameters are:
        * PanSTARRS colors
        * FoV = 0.02 deg
        * SIMBAD catalig overlayed.

    Callbacks
    ----------
    Input: takes the alert ID
    Output: Display a sky image around the alert position from aladin.

    Parameters
    ----------
    alert_id: str
        ID of the alert
    """
    if n3:
        pdf_ = pd.read_json(object_data)
        cols = ['i:jd', 'i:ra', 'i:dec']
        pdf = pdf_.loc[:, cols]
        pdf = pdf.sort_values('i:jd', ascending=False)

        # Coordinate of the current alert
        ra0 = pdf['i:ra'].values[0]
        dec0 = pdf['i:dec'].values[0]

        # Javascript. Note the use {{}} for dictionary
        img = """
        var aladin = A.aladin('#aladin-lite-div2',
                  {{
                    survey: 'P/PanSTARRS/DR1/color/z/zg/g',
                    fov: 0.025,
                    target: '{} {}',
                    reticleColor: '#ff89ff',
                    reticleSize: 32
        }});
        var cat = 'https://axel.u-strasbg.fr/HiPSCatService/Simbad';
        var hips = A.catalogHiPS(cat, {{onClick: 'showTable', name: 'Simbad'}});
        aladin.addCatalog(hips);
        """.format(ra0, dec0)

        # img cannot be executed directly because of formatting
        # We split line-by-line and remove comments
        img_to_show = [i for i in img.split('\n') if '// ' not in i]

        return " ".join(img_to_show)
    else:
        return ''

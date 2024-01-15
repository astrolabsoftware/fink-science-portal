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
from dash import html, dcc, dash_table, Input, Output, State, clientside_callback
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import visdcc

from app import app, APIURL

from apps.plotting import all_radio_options
from apps.utils import pil_to_b64
from apps.utils import generate_qr
from apps.utils import class_colors
from apps.utils import simbad_types
from apps.utils import loading, help_popover
from apps.utils import request_api

from fink_utils.xmatch.simbad import get_simbad_labels
from fink_utils.photometry.utils import is_source_behind

import pandas as pd
import numpy as np
import urllib
import textwrap

from astropy.time import Time
from astropy.coordinates import SkyCoord

lc_help = r"""
##### Difference magnitude

Circles (&#9679;) with error bars show valid alerts that pass the Fink quality cuts.
In addition, the _Difference magnitude_ view shows:
- upper triangles with errors (&#9650;), representing alert measurements that do not satisfy Fink quality cuts, but are nevetheless contained in the history of valid alerts and used by classifiers.
- lower triangles (&#9661;), representing 5-sigma magnitude limit in difference image based on PSF-fit photometry contained in the history of valid alerts.

If the `Color` switch is turned on, the view also shows the panel with `g - r` color, estimated by combining nearby (closer than 0.3 days) measurements in two filters.

##### DC magnitude
DC magnitude is computed by combining the nearest reference image catalog magnitude (`magnr`),
differential magnitude (`magpsf`), and `isdiffpos` (positive or negative difference image detection) as follows:
$$
m_{DC} = -2.5\log_{10}(10^{-0.4m_{magnr}} + \texttt{sign} 10^{-0.4m_{magpsf}})
$$

where `sign` = 1 if `isdiffpos` = 't' or `sign` = -1 if `isdiffpos` = 'f'.
Before using the nearest reference image source magnitude (`magnr`), you will need
to ensure the source is close enough to be considered an association
(e.g., `distnr` $\leq$ 1.5 arcsec). It is also advised you check the other associated metrics
(`chinr` and/or `sharpnr`) to ensure it is a point source. ZTF recommends
0.5 $\leq$ `chinr` $\leq$ 1.5 and/or -0.5 $\leq$ `sharpnr` $\leq$ 0.5.

The view also shows, with dashed horizontal lines, the levels corresponding to the magnitudes of the nearest reference image catalog entry (`magnr`) used in computing DC magnitudes.

This view may be augmented with the photometric points from [ZTF Data Releases](https://www.ztf.caltech.edu/ztf-public-releases.html) by clicking `Get DR photometry` button. The points will be shown with semi-transparent dots (&#8226;).

##### DC flux
DC flux (in Jansky) is constructed from DC magnitude by using the following:
$$
f_{DC} = 3631 \times 10^{-0.4m_{DC}}
$$

Note that we display the flux in milli-Jansky.
"""

def card_lightcurve_summary():
    """ Add a card containing the lightcurve

    Returns
    ----------
    card: dbc.Card
        Card with the lightcurve drawn inside
    """
    card = dmc.Paper(
        [
            loading(
                dcc.Graph(
                    id='lightcurve_cutouts',
                    style={
                        'width': '100%',
                        'height': '30pc'
                    },
                    config={'displayModeBar': False},
                    className="mb-2"
                )
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
            dmc.Group(
                [
                    dmc.Switch(
                        "Color",
                        id='lightcurve_show_color',
                        color='gray',
                        radius='xl',
                        size='sm',
                        persistence=True
                    ),
                    dmc.Button(
                        "Get DR photometry",
                        id='lightcurve_request_release',
                        variant="outline",
                        color='gray',
                        radius='xl', size='xs',
                        compact=False,
                    ),
                    help_popover(
                        dcc.Markdown(
                            lc_help, mathjax=True
                        ),
                        'help_lc',
                        trigger=dmc.ActionIcon(
                            DashIconify(icon="mdi:help"),
                            id='help_lc',
                            color='gray',
                            variant="outline",
                            radius='xl',
                            size='md',
                        )
                    ),
                ],
                position='center', align='center'
            )
        ]
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
        )
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
                        className='btn btn-default btn-circle btn-lg zoom btn-image',
                        style={'background-image': 'url(/assets/buttons/tns_logo.png)', 'background-size': 'auto 100%', 'background-position-x': 'left'},
                        color='dark',
                        outline=True,
                        id='TNS',
                        title='TNS',
                        target="_blank",
                        href='https://www.wis-tns.org/search?ra={}&decl={}&radius=5&coords_unit=arcsec'.format(ra0, dec0)
                    )
                ),
                dbc.Col(
                    dbc.Button(
                        className='btn btn-default btn-circle btn-lg zoom btn-image',
                        style={'background-image': 'url(/assets/buttons/simbad.png)'},
                        color='dark',
                        outline=True,
                        id='SIMBAD',
                        title='SIMBAD',
                        target="_blank",
                        href="http://simbad.u-strasbg.fr/simbad/sim-coo?Coord={}%20{}&Radius=0.08".format(ra0, dec0)
                    )
                ),
                dbc.Col(
                    dbc.Button(
                        className='btn btn-default btn-circle btn-lg zoom btn-image',
                        style={'background-image': 'url(/assets/buttons/snad.svg)'},
                        color='dark',
                        outline=True,
                        id='SNAD',
                        title='SNAD',
                        target="_blank",
                        href='https://ztf.snad.space/search/{} {}/{}'.format(ra0, dec0, 5)
                    )
                ),
                dbc.Col(
                    dbc.Button(
                        className='btn btn-default btn-circle btn-lg zoom btn-image',
                        style={'background-image': 'url(/assets/buttons/dclogo_small.png)'},
                        color='dark',
                        outline=True,
                        id='DataCentral',
                        title='DataCentral Data Aggregation Service',
                        target="_blank",
                        href='https://das.datacentral.org.au/open?RA={}&DEC={}&FOV={}&ERR={}'.format(ra0, dec0, 0.5, 2.0)
                    )
                ),
            ], justify='around'
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Button(
                        className='btn btn-default btn-circle btn-lg zoom btn-image',
                        style={'background-image': 'url(/assets/buttons/NEDVectorLogo_WebBanner_100pxTall_2NoStars.png)', 'background-color': 'black'},
                        color='dark',
                        outline=True,
                        id='NED',
                        title='NED',
                        target="_blank",
                        href="http://ned.ipac.caltech.edu/cgi-bin/objsearch?search_type=Near+Position+Search&in_csys=Equatorial&in_equinox=J2000.0&ra={}&dec={}&radius=1.0&obj_sort=Distance+to+search+center&img_stamp=Yes".format(ra0, dec0)
                    ),
                ),
                dbc.Col(
                    dbc.Button(
                        className='btn btn-default btn-circle btn-lg zoom btn-image',
                        style={'background-image': 'url(/assets/buttons/sdssIVlogo.png)'},
                        color='dark',
                        outline=True,
                        id='SDSS',
                        title='SDSS',
                        target="_blank",
                        href="http://skyserver.sdss.org/dr13/en/tools/chart/navi.aspx?ra={}&dec={}".format(ra0, dec0)
                    ),
                ),
                dbc.Col(
                    dbc.Button(
                        className='btn btn-default btn-circle btn-lg zoom btn-image',
                        style={'background-image': 'url(/assets/buttons/asassn.png)', 'background-color': 'black'},
                        color='white',
                        outline=True,
                        id='ASAS-SN',
                        title='ASAS-SN',
                        target="_blank",
                        href="https://asas-sn.osu.edu/?ra={}&dec={}".format(ra0, dec0)
                    ),
                ),
                dbc.Col(
                    dbc.Button(
                        className='btn btn-default btn-circle btn-lg zoom btn-image',
                        style={'background-image': 'url(/assets/buttons/vsx.png)'},
                        color='dark',
                        outline=True,
                        id='VSX',
                        title='AAVSO VSX',
                        target="_blank",
                        href="https://www.aavso.org/vsx/index.php?view=results.get&coords={}+{}&format=d&size=0.1".format(ra0, dec0)
                    ),
                )
            ], justify='around'
        ),
    ]
    return buttons

def create_external_links_brokers(objectId):
    """
    """
    buttons = dbc.Row(
        [
            dbc.Col(
                dbc.Button(
                    className='btn btn-default btn-circle btn-lg zoom btn-image',
                    style={'background-image': 'url(/assets/buttons/logo_alerce.png)'},
                    color='dark',
                    outline=True,
                    id='alerce',
                    title='ALeRCE',
                    target="_blank",
                    href='https://alerce.online/object/{}'.format(objectId)
                )
            ),
            dbc.Col(
                dbc.Button(
                    className='btn btn-default btn-circle btn-lg zoom btn-image',
                    style={'background-image': 'url(/assets/buttons/logo_antares.png)'},
                    color='dark',
                    outline=True,
                    id='antares',
                    title='ANTARES',
                    target="_blank",
                    href='https://antares.noirlab.edu/loci?query=%7B%22currentPage%22%3A1,%22filters%22%3A%5B%7B%22type%22%3A%22query_string%22,%22field%22%3A%7B%22query%22%3A%22%2a{}%2a%22,%22fields%22%3A%5B%22properties.ztf_object_id%22,%22locus_id%22%5D%7D,%22value%22%3Anull,%22text%22%3A%22ID%20Lookup%3A%20ZTF21abfmbix%22%7D%5D,%22sortBy%22%3A%22properties.newest_alert_observation_time%22,%22sortDesc%22%3Atrue,%22perPage%22%3A25%7D'.format(objectId)
                )
            ),
            dbc.Col(
                dbc.Button(
                    className='btn btn-default btn-circle btn-lg zoom btn-image',
                    style={'background-image': 'url(/assets/buttons/logo_lasair.png)'},
                    color='dark',
                    outline=True,
                    id='lasair',
                    title='Lasair',
                    target="_blank",
                    href='https://lasair-ztf.lsst.ac.uk/objects/{}'.format(objectId)
                )
            ),
        ], justify='around'
    )
    return buttons

def card_neighbourhood(pdf):
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
    vsx = pdf['d:vsx'].values[0]
    gcvs = pdf['d:gcvs'].values[0]

    card = dmc.Paper(
        [
            dcc.Markdown(
                """
                Constellation: `{}`
                Class (SIMBAD): `{}`
                Class (VSX/GCVS): `{}` / `{}`
                Name (MPC): `{}`
                Name (Gaia): `{}`
                Distance (Gaia): `{:.2f}` arcsec
                Distance (PS1): `{:.2f}` arcsec
                Distance (ZTF): `{:.2f}` arcsec
                """.format(
                    constellation,
                    cdsxmatch, vsx, gcvs, ssnamenr, gaianame,
                    float(neargaia), float(distpsnr1), float(distnr)
                ),
                className="markdown markdown-pre ps-2 pe-2"
            ),
        ],
        radius='sm', p='xs', shadow='sm', withBorder=True, style={'width': '100%'},
    )

    return card

def make_modal_stamps(pdf):
    return [
        dbc.Modal(
            [
                dbc.ModalHeader(
                    [
                        dmc.ActionIcon(
                            DashIconify(icon="tabler:chevron-left"),
                            id="stamps_prev",
                            title="Next alert",
                            n_clicks=0,
                            variant="default",
                            size=36,
                            color='gray',
                            className='me-1'
                        ),
                        dmc.Select(
                            label="",
                            placeholder="Select a date",
                            searchable=True,
                            nothingFound="No options found",
                            id="date_modal_select",
                            value=pdf['v:lastdate'].values[0],
                            data=[
                                {"value": i, "label": i} for i in pdf['v:lastdate'].values
                            ],
                            zIndex=10000000,
                        ),
                        dmc.ActionIcon(
                            DashIconify(icon="tabler:chevron-right"),
                            id="stamps_next",
                            title="Previous alert",
                            n_clicks=0,
                            variant="default",
                            size=36,
                            color='gray',
                            className='ms-1'
                        ),
                    ],
                    close_button=True,
                    className="p-2 pe-4"
                ),
                loading(dbc.ModalBody(
                    [
                        dbc.Row(
                            id='stamps_modal_content',
                            justify='around',
                            className='g-0 mx-auto',
                        ),
                    ]
                )),
            ],
            id="stamps_modal",
            scrollable=True,
            centered=True,
            size='xl',
            # style={'max-width': '800px'}
        ),
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
    ]

# Toggle stamps modal
clientside_callback(
    """
    function toggle_stamps_modal(n_clicks, is_open) {
        return !is_open;
    }
    """,
    Output("stamps_modal", "is_open"),
    Input("maximise_stamps", "n_clicks"),
    State("stamps_modal", "is_open"),
    prevent_initial_call=True,
)

# Prev/Next for stamps modal
clientside_callback(
    """
    function stamps_prev_next(n_clicks_prev, n_clicks_next, clickData, value, data) {
        let id = data.findIndex((x) => x.value === value);
        let step = 1;

        const triggered = dash_clientside.callback_context.triggered.map(t => t.prop_id);

        if (triggered == 'lightcurve_cutouts.clickData')
            return clickData.points[0].x;

        if (triggered == 'stamps_prev.n_clicks')
            step = -1;

        id += step;
        if (step > 0 && id >= data.length)
            id = 0;
        if (step < 0 && id < 0)
            id = data.length - 1;

        return data[id].value;
    }
    """,
    Output("date_modal_select", "value"),
    [
        Input("stamps_prev", "n_clicks"),
        Input("stamps_next", "n_clicks"),
        Input("lightcurve_cutouts", "clickData"),
    ],
    State("date_modal_select", "value"),
    State("date_modal_select", "data"),
    prevent_initial_call=True,
)

def card_id(pdf):
    """ Add a card containing basic alert data
    """
    # pdf = pd.read_json(object_data)
    objectid = pdf['i:objectId'].values[0]
    ra0 = pdf['i:ra'].values[0]
    dec0 = pdf['i:dec'].values[0]

    python_download = """import requests
import pandas as pd
import io

# get data for {}
r = requests.post(
    '{}/api/v1/objects',
    json={{
        'objectId': '{}',
        'output-format': 'json'
    }}
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))""".format(
        objectid,
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

    card = dmc.AccordionMultiple(
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Alert cutouts",
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
                            loading(
                                dmc.Paper(
                                    [
                                        dbc.Row(
                                            dmc.Skeleton(style={'width': '100%', 'aspect-ratio': '3/1'}),
                                            id='stamps', justify='around', className="g-0"
                                        ),
                                    ],
                                    radius='sm', p='xs', shadow='sm', withBorder=True, style={'padding':'5px'}
                                )
                            ),
                            dmc.Space(h=4),
                            *make_modal_stamps(pdf),
                        ]
                    ),
                ],
                value='stamps'
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Alert content",
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
                        html.Div(
                            [
                                dmc.Group(
                                    [
                                        dmc.Button(
                                            "JSON",
                                            id='download_json',
                                            variant="outline",
                                            color='indigo',
                                            compact=True,
                                            leftIcon=[DashIconify(icon="mdi:code-json")],
                                        ),
                                        dmc.Button(
                                            "CSV",
                                            id='download_csv',
                                            variant="outline",
                                            color='indigo',
                                            compact=True,
                                            leftIcon=[DashIconify(icon="mdi:file-csv-outline")],
                                        ),
                                        dmc.Button(
                                            "VOTable",
                                            id='download_votable',
                                            variant="outline",
                                            color='indigo',
                                            compact=True,
                                            leftIcon=[DashIconify(icon="mdi:xml")],
                                        ),
                                        help_popover(
                                            [
                                                dcc.Markdown('You may also download the data programmatically.'),
                                                download_tab,
                                                dcc.Markdown('See {}/api for more options'.format(APIURL)),
                                            ],
                                            'help_download',
                                            trigger=dmc.ActionIcon(
                                                    DashIconify(icon="mdi:help"),
                                                    id='help_download',
                                                    variant="outline",
                                                    color='indigo',
                                            ),
                                        ),
                                        html.Div(objectid, id='download_objectid', className='d-none'),
                                        html.Div(APIURL, id='download_apiurl', className='d-none'),
                                    ], position="center", spacing="xs"
                                )
                            ],
                        ),
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
                                icon="tabler:external-link",
                                color="#15284F",
                                width=20,
                            )
                        ],
                    ),
                    dmc.AccordionPanel(
                        dmc.Stack(
                            [
                                card_neighbourhood(pdf),
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
                        "Other brokers",
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
                                create_external_links_brokers(objectid)
                            ],
                            align='center'
                        )
                    ),
                ],
                value='external_brokers'
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
                            dmc.Center(html.Div(id='qrcode'), style={'width': '100%', 'height': '200'})
                        ],
                    ),
                ],
                value='qr'
            ),
        ],
        value=['stamps'],
        styles={'content':{'padding':'5px'}}
    )

    return card

# Downloads handling. Requires CORS to be enabled on the server.
# TODO: We are mostly using it like this until GET requests properly initiate
# downloads instead of just opening the file (so, Content-Disposition etc)
download_js = """
function(n_clicks, name, apiurl){
    if(n_clicks > 0){
        fetch(apiurl + '/api/v1/objects', {
            method: 'POST',
            body: JSON.stringify({
                 'objectId': name,
                 'withupperlim': true,
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
    download_js.replace('$FORMAT', 'json').replace('$EXTENSION', 'json'),
    Output('download_json', 'n_clicks'),
    [
        Input('download_json', 'n_clicks'),
        Input('download_objectid', 'children'),
        Input('download_apiurl', 'children'),
    ]
)
app.clientside_callback(
    download_js.replace('$FORMAT', 'csv').replace('$EXTENSION', 'csv'),
    Output('download_csv', 'n_clicks'),
    [
        Input('download_csv', 'n_clicks'),
        Input('download_objectid', 'children'),
        Input('download_apiurl', 'children'),
    ]
)
app.clientside_callback(
    download_js.replace('$FORMAT', 'votable').replace('$EXTENSION', 'vot'),
    Output('download_votable', 'n_clicks'),
    [
        Input('download_votable', 'n_clicks'),
        Input('download_objectid', 'children'),
        Input('download_apiurl', 'children'),
    ]
)

def generate_tns_badge(oid):
    """ Generate TNS badge

    Parameters
    ----------
    oid: str
        ZTF object ID

    Returns
    ----------
    badge: dmc.Badge or None
    """
    r = request_api(
        '/api/v1/resolver',
        json={
            'resolver': 'tns',
            'name': oid,
            'reverse': True
        },
        get_json=True
    )

    if r != []:
        payload = r[-1]

        if payload['d:type'] != 'nan':
            msg = 'TNS: {} ({})'.format(payload['d:fullname'], payload['d:type'])
        else:
            msg = 'TNS: {}'.format(payload['d:fullname'])
        badge = dmc.Badge(
            msg,
            color='red',
            variant='dot'
        )
    else:
        badge = None

    return badge

def generate_metadata_name(oid):
    """ Generate name from metadata

    Parameters
    ----------
    oid: str
        ZTF object ID

    Returns
    ----------
    name: str
    """
    r = request_api(
        '/api/v1/metadata',
        json={
            'objectId': oid,
        },
        get_json=True
    )

    if r != []:
        name = r[0]['d:internal_name']
    else:
        name = None

    return name

@app.callback(
    Output('card_id_left', 'children'),
    [
        Input('object-data', 'data'),
        Input('object-uppervalid', 'data'),
        Input('object-upper', 'data')
    ],
    prevent_initial_call=True
)
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

    tns_badge = generate_tns_badge(pdf['i:objectId'].values[0])
    if tns_badge is not None:
        badges.append(tns_badge)

    ssnamenr = pdf['i:ssnamenr'].values[0]
    if ssnamenr and ssnamenr != 'null':
        badges.append(
            dmc.Badge(
                "SSO: {}".format(ssnamenr),
                color='yellow',
                variant="dot",
            )
        )

    tracklet = pdf['d:tracklet'].values[0]
    if tracklet and tracklet != 'null':
        badges.append(
            dmc.Badge(
                "{}".format(tracklet),
                color='violet',
                variant="dot",
            )
        )

    gcvs = pdf['d:gcvs'].values[0]
    if gcvs and gcvs != 'Unknown':
        badges.append(
            dmc.Badge(
                "GCVS: {}".format(gcvs),
                variant='outline',
                color=class_colors['Simbad'],
                size='md'
            )
        )

    vsx = pdf['d:vsx'].values[0]
    if vsx and vsx != 'Unknown':
        badges.append(
            dmc.Badge(
                "VSX: {}".format(vsx),
                variant='outline',
                color=class_colors['Simbad'],
                size='md'
            )
        )

    distnr = pdf['i:distnr'].values[0]
    if distnr:
        if is_source_behind(distnr):
            ztf_badge = dmc.Tooltip(
                dmc.Badge(
                    "ZTF: {:.1f}\"".format(distnr),
                    color='cyan',
                    variant="dot",
                    style={'border-color': 'red'},
                ),
                label="There is a source behind in ZTF reference image. You might want to check the DC magnitude plot, and get DR photometry to see its long-term behaviour",
                color='red',
                className='d-inline',
                id='badge_ztf',
                multiline=True,
            )
        else:
            ztf_badge = dmc.Tooltip(
                dmc.Badge(
                    "ZTF: {:.1f}\"".format(distnr),
                    color='cyan',
                    variant="dot",
                ),
                label="Distance to closest object in ZTF reference image",
                color='cyan',
                className='d-inline',
                multiline=True,
            )

        badges.append(ztf_badge)

    distpsnr = pdf['i:distpsnr1'].values[0]
    if distpsnr:
        badges.append(
            dmc.Tooltip(
                dmc.Badge(
                    "PS1: {:.1f}\"".format(distpsnr),
                    color='teal',
                    variant="dot",
                ),
                label="Distance to closest object in Pan-STARRS DR1 catalogue",
                color='teal',
                className='d-inline',
                multiline=True,
            )
        )

    distgaia =  pdf['i:neargaia'].values[0]
    if distgaia:
        badges.append(
            dmc.Tooltip(
                dmc.Badge(
                    "Gaia: {:.1f}\"".format(distgaia),
                    color='teal',
                    variant="dot",
                ),
                label="Distance to closest object in Gaia DR3 catalogue",
                color='teal',
                className='d-inline',
                multiline=True,
            )
        )

    meta_name = generate_metadata_name(pdf['i:objectId'].values[0])
    if meta_name is not None:
        extra_div = dbc.Row(
            [
                dbc.Col(dmc.Title(meta_name, order=4, style={'color': '#15284F'}), width=10),
            ], justify='start', align="center"
        )
    else:
        extra_div = html.Div()

    coords = SkyCoord(pdf['i:ra'].values[0], pdf['i:dec'].values[0], unit='deg')

    card = dmc.Paper(
        [
            dbc.Row(
                [
                    dbc.Col(dmc.Avatar(src="/assets/Fink_SecondaryLogo_WEB.png", size='lg'), width=2),
                    dbc.Col(dmc.Title(objectid, order=1, style={'color': '#15284F'}), width=10),
                ], justify='start', align="center"
            ),
            extra_div,
            html.Div(badges),
            dcc.Markdown(
                """
                Discovery date: `{}`
                Last detection: `{}`
                Duration: `{:.2f}` / `{:.2f}` days
                Detections: `{}` good, `{}` bad, `{}` upper
                RA/Dec: `{} {}`
                """.format(
                    discovery_date[:19],
                    date_end[:19],
                    jds[0] - jds[-1],
                    pdf['i:jdendhist'][0] - pdf['i:jdstarthist'][0],
                    ndet, nupper_valid, nupper,
                    coords.ra.to_string(pad=True, unit='hour', precision=2, sep=' '),
                    coords.dec.to_string(pad=True, unit='deg', alwayssign=True, precision=1, sep=' '),
                ),
                className="markdown markdown-pre ps-2 pe-2 mt-2"
            ),
        ], radius='xl', p='md', shadow='xl', withBorder=True
    )
    return card

def card_search_result(row, i):
    """Display single item for search results
    """
    badges = []

    name = row['i:objectId']
    if name[0] == '[': # Markdownified
        name = row['i:objectId'].split('[')[1].split(']')[0]

    # Handle different variants for key names from different API entry points
    classification = None
    for key in ['v:classification', 'd:classification']:
        if key in row:
            # Classification
            classification = row.get(key)
            if classification in simbad_types:
                color = class_colors['Simbad']
            elif classification in class_colors.keys():
                color = class_colors[classification]
            else:
                # Sometimes SIMBAD mess up names :-)
                color = class_colors['Simbad']

            badges.append(
                dmc.Badge(
                    classification,
                    variant='outline',
                    color=color,
                    size='md'
                )
            )

    # SSO
    ssnamenr = row.get('i:ssnamenr')
    if ssnamenr and ssnamenr != 'null':
        badges.append(
            dmc.Badge(
                "SSO: {}".format(ssnamenr),
                variant='outline',
                color='yellow',
                size='md'
            )
        )

    tracklet = row.get('d:tracklet')
    if tracklet and tracklet != 'null':
        badges.append(
            dmc.Badge(
                "{}".format(tracklet),
                variant='outline',
                color='violet',
                size='md'
            )
        )

    cdsxmatch = row.get('d:cdsxmatch')
    if cdsxmatch and cdsxmatch != 'Unknown' and cdsxmatch != classification:
        badges.append(
            dmc.Badge(
                "SIMBAD: {}".format(cdsxmatch),
                variant='outline',
                color=class_colors['Simbad'],
                size='md'
            )
        )

    gcvs = row.get('d:gcvs')
    if gcvs and gcvs != 'Unknown':
        badges.append(
            dmc.Badge(
                "GCVS: {}".format(gcvs),
                variant='outline',
                color=class_colors['Simbad'],
                size='md'
            )
        )

    vsx = row.get('d:vsx')
    if vsx and vsx != 'Unknown':
        badges.append(
            dmc.Badge(
                "VSX: {}".format(vsx),
                variant='outline',
                color=class_colors['Simbad'],
                size='md'
            )
        )

    # Nearby objects
    distnr = row.get('i:distnr')
    if distnr:
        if is_source_behind(distnr):
            ztf_badge = dmc.Badge(
                "ZTF: {:.1f}\"".format(distnr),
                color='cyan',
                variant='outline',
                size='md',
                style={'border-color': 'red'},
            )
        else:
            ztf_badge = dmc.Badge(
                "ZTF: {:.1f}\"".format(distnr),
                color='cyan',
                variant='outline',
                size='md',
            )

        badges.append(ztf_badge)

    distpsnr = row.get('i:distpsnr1')
    if distpsnr:
        badges.append(
            dmc.Badge(
                "PS1: {:.1f}\"".format(distpsnr),
                color='teal',
                variant='outline',
                size='md',
            )
        )

    distgaia = row.get('i:neargaia')
    if distgaia:
        badges.append(
            dmc.Badge(
                "Gaia: {:.1f}\"".format(distgaia),
                color='teal',
                variant='outline',
                size='md',
            )
        )

    if 'i:ndethist' in row:
        ndethist = row.get('i:ndethist')
    elif 'd:nalerthist' in row:
        ndethist = row.get('d:nalerthist')
    else:
        ndethist = '?'

    jdend = row.get('i:jdendhist', row.get('i:jd'))
    jdstart = row.get('i:jdstarthist')
    lastdate = row.get('i:lastdate', Time(jdend, format='jd').iso)

    coords = SkyCoord(row['i:ra'], row['i:dec'], unit='deg')

    text = """
    `{}` detection(s) in `{:.1f}` days
    First: `{}`
    Last: `{}`
    Equ: `{} {}`
    Gal: `{}`
    """.format(
        ndethist,
        jdend - jdstart,
        Time(jdstart, format='jd').iso[:19],
        lastdate[:19],
        coords.ra.to_string(pad=True, unit='hour', precision=2, sep=' '),
        coords.dec.to_string(pad=True, unit='deg', alwayssign=True, precision=1, sep=' '),
        coords.galactic.to_string(style='decimal'),
    )

    text = textwrap.dedent(text)
    if 'i:rb' in row:
        text += "RealBogus: `{:.2f}`\n".format(row['i:rb'])
    if 'd:anomaly_score' in row:
        text += "Anomaly score: `{:.2f}`\n".format(row['d:anomaly_score'])

    if 'v:separation_degree' in row:
        corner_str = "{:.1f}''".format(row['v:separation_degree']*3600)
    else:
        corner_str = str(i)

    item = dbc.Card(
        [
            # dbc.CardHeader(
            dbc.CardBody(
                [
                    html.A(
                        dmc.Group(
                            [
                                dmc.Text("{}".format(name), weight=700, size=26),
                                dmc.Space(w='sm'),
                                *badges
                            ],
                            spacing=3,
                        ),
                        href='/{}'.format(name),
                        target='_blank',
                        className='text-decoration-none',
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                dmc.Skeleton(
                                    style={
                                        'width': '12pc',
                                        'height': '12pc',
                                    },
                                ),
                                id={'type': 'search_results_cutouts', 'objectId': name, 'index': i},
                                width='auto'
                            ),
                            dbc.Col(
                                dcc.Markdown(
                                    text,
                                    style={'white-space': 'pre-wrap'},
                                ),
                                width='auto',
                            ),
                            dbc.Col(
                                dmc.Skeleton(
                                    style={
                                        'width': '100%',
                                        'height': '15pc'
                                    },
                                ),
                                id={'type': 'search_results_lightcurve', 'objectId': name, 'index': i},
                                xs=12, md=True,
                            ),
                        ],
                        justify='start',
                        className='g-2',
                    ),
                    # Upper right corner badge
                    dbc.Badge(
                        corner_str,
                        color="light",
                        pill=True,
                        text_color="dark",
                        className="position-absolute top-0 start-100 translate-middle border",
                    ),
                ]
            )
        ],
        color='white',
        className='mb-2 shadow border-1'
    )

    return item

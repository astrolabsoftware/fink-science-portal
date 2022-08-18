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
from dash import html, dcc, Input, Output, State, dash_table, no_update
from dash.exceptions import PreventUpdate

import dash_bootstrap_components as dbc
import visdcc
import dash_trich_components as dtc

import dash_mantine_components as dmc
from dash_iconify import DashIconify

from app import server
from app import app
from app import client
from app import APIURL

from apps import summary, about, statistics
from apps.api import api
from apps import __version__ as portal_version

from apps.utils import markdownify_objectid, class_colors
from apps.utils import isoify_time, validate_query, extract_query_url
from apps.plotting import draw_cutouts_quickview, draw_lightcurve_preview

from fink_utils.xmatch.simbad import get_simbad_labels

import requests
import pandas as pd
import numpy as np
from astropy.time import Time, TimeDelta

simbad_types = get_simbad_labels('old_and_new')
simbad_types = sorted(simbad_types, key=lambda s: s.lower())

tns_types = pd.read_csv('assets/tns_types.csv', header=None)[0].values
tns_types = sorted(tns_types, key=lambda s: s.lower())

message_help = """
##### Object ID

Enter a valid object ID to access its data, e.g. try:

* ZTF21abfmbix, ZTF21aaxtctv, ZTF21abfaohe, ZTF20aanxcpf, ZTF17aaaabte, ZTF18aafpcwm, ZTF21abujbqa, ZTF21abuipwb, ZTF18acuajcr

##### Conesearch

Perform a conesearch around a position on the sky given by (RA, Dec, radius).
The initializer for RA/Dec is very flexible and supports inputs provided in a number of convenient formats.
The following ways of initializing a conesearch are all equivalent (radius in arcsecond):

* 193.822, 2.89732, 5
* 193d49m18.267s, 2d53m50.35s, 5
* 12h55m17.218s, +02d53m50.35s, 5
* 12 55 17.218, +02 53 50.35, 5
* 12:55:17.218, 02:53:50.35, 5

Maximum radius length is 18,000 arcseconds (5 degrees). Note that in case of
several objects matching, the results will be sorted according to the angular
separation in degree between the input (ra, dec) and the objects found.

In addition, you can specify a starting date (UTC) and a window (in days) to refine your search.
Example, to refine your search starting at 2021-06-25 05:59:37.000 for 7 days:

* 193.822, 2.89732, 5, 2021-06-25 05:59:37.000, 7
* 193.822, 2.89732, 5, 2459391.7497338, 7

We encourage you to use the `startdate` and `window`, as your query will run much faster.

##### Date search

Choose a starting date and a time window to see all processed alerts in this period.
Dates are in UTC, and the time window in minutes.
Among several, you can choose YYYY-MM-DD hh:mm:ss, Julian Date, or Modified Julian Date. Example of valid search:

* 2021-07-01 05:59:37.000
* 2459396.7497337963
* 59396.2497337963

##### Class

Choose a class of interest using the drop-down menu to see the 100 latest alerts processed by Fink.

##### Solar System Objects (SSO)

Search for Solar System Objects in the Fink database.
The numbers or designations are taken from the MPC archive.
When searching for a particular asteroid or comet, it is best to use the IAU number,
as in 8467 for asteroid "8467 Benoitcarry". You can also try for numbered comet (e.g. 10P),
or interstellar object (none so far...). If the number does not yet exist, you can search for designation.
Here are some examples of valid queries:

* Asteroids by number (default)
  * Asteroids (Main Belt): 8467, 1922
  * Asteroids (Hungarians): 18582, 77799
  * Asteroids (Jupiter Trojans): 4501, 1583
  * Asteroids (Mars Crossers): 302530
* Asteroids by designation (if number does not exist yet)
  * 2010JO69, 2017AD19, 2012XK111
* Comets by number (default)
  * 10P, 249P, 124P
* Comets by designation (if number does no exist yet)
  * C/2020V2, C/2020R2

Note for designation, you can also use space (2010 JO69 or C/2020 V2).


##### Tracklet data

Search for Tracklet Objects in the Fink database. Tracklets are fast
moving objects, typically orbiting around the Earth. They are most likely
produced by satellite glints or space debris.

You have the choice to specify the date in the format `YYYY-MM-DD hh:mm:ss` or
any short versions such as `YYY-MM-DD` or `YYYY-MM-DD hh`. E.g. try:

- 2020-08-10
- 2021-10-22 09:19
- 2020-07-16 04:58:48
"""

msg_info = """
![logoexp](/assets/Fink_PrimaryLogo_WEB.png)

Fill the search bar and hit the search button. You can access help by clicking on the Help button at the right of the bar.

By default, the table shows:

- i:objectId: Unique identifier for this object
- i:ra: Right Ascension of candidate; J2000 (deg)
- i:dec: Declination of candidate; J2000 (deg)
- v:lastdate: last date the object has been seen by Fink
- v:classification: Classification inferred by Fink (Supernova candidate, Microlensing candidate, Solar System, SIMBAD class, ...)
- i:ndethist: Number of spatially coincident detections falling within 1.5 arcsec going back to the beginning of the survey; only detections that fell on the same field and readout-channel ID where the input candidate was observed are counted. All raw detections down to a photometric S/N of ~ 3 are included.
- v:lapse: number of days between the first and last spatially coincident detections.

You can also add more columns using the dropdown button above the result table. Full documentation of all available fields can be found at {}/api/v1/columns.

Finally, you can hit the button `Preview`. This will show you more information
about the first 10 alerts (science cutout, and basic information). Note you can
swipe between alerts (or use arrows on a laptop).
""".format(APIURL)

modal = html.Div(
    [
        dbc.Button(
            "Help",
            id="open",
            color='light',
            outline=True,
            style={
                "border": "0px black solid",
                'background': 'rgba(255, 255, 255, 0.0)',
                'color': 'grey'
            }
        ),
        dbc.Modal(
            [
                dbc.ModalHeader("Fink Science Portal"),
                dbc.ModalBody(dcc.Markdown(message_help)),
                dbc.ModalFooter(
                    dbc.Button("Close", id="close", className="ml-auto")
                ),
            ],
            id="modal", scrollable=True
        ),
    ]
)

@app.callback(
    Output("modal", "is_open"),
    [Input("open", "n_clicks"), Input("close", "n_clicks")],
    [State("modal", "is_open")],
)
def toggle_modal(n1, n2, is_open):
    """ Callback for the modal (open/close)
    """
    if n1 or n2:
        return not is_open
    return is_open


fink_search_bar = dbc.InputGroup(
    [
        dbc.Input(
            id="search_bar_input",
            autoFocus=True,
            type='search',
            style={"border": "0px black solid", 'background': 'rgba(255, 255, 255, 0.0)', 'color': 'grey'},
            className='inputbar',
            debounce=True
        ),
        dmc.ActionIcon(
            DashIconify(icon="tabler:search", width=20),
            n_clicks=0,
            id="submit",
            color='gray',
            variant="transparent",
            radius='xl',
            size='lg',
            loaderProps={'variant': 'dots', 'color': 'orange'}
        ),
        modal
    ], style={"border": "0.5px grey solid", 'background': 'rgba(255, 255, 255, .75)'}, className='rcorners2'
)

def print_msg_info():
    """ Display the explorer info message
    """
    h = html.Div([
        dbc.Row([
            dcc.Markdown(msg_info)
        ]),
    ])
    return h

def simple_card(
        name, finkclass, lastdate, fid,
        mag, jd, jdstarthist, ndethist, constellation, is_mobile):
    """ Preview card

    The laptop version shows Science cutout + metadata + lightcurve
    The mobile version shows Science cutout + metadata
    """
    dic_band = {1: 'g', 2: 'r'}
    fontsize = '75%'

    l1 = html.P(
        [
            html.Strong("Last emission date: ", style={'font-size': fontsize}),
            html.P(lastdate)
        ]
    )
    l2 = html.P(
        [
            html.Strong("Last magnitude (band {}): ".format(dic_band[fid]), style={'font-size': fontsize}),
            html.P("{:.2f}".format(mag))
        ]
    )

    l3 = html.P(
        [
            html.Strong("Days since first detection: ", style={'font-size': fontsize}),
            html.P('{}'.format(int(jd - jdstarthist)))
        ]
    )

    l4 = html.P(
        [
            html.Strong("Total number of detections: ", style={'font-size': fontsize}),
            html.P('{}'.format(ndethist))
        ]
    )

    l5 = html.P(
        [
            html.Strong("Constellation: ", style={'font-size': fontsize}),
            html.P('{}'.format(constellation))
        ]
    )

    if is_mobile:
        cardbody = dbc.CardBody(
            [
                html.H4("{}".format(finkclass), className="card-title"),
                l1,
                l2,
                l3,
                l4,
                l5
            ]
        )
        header = dbc.CardHeader(
            dbc.Row(
                draw_cutouts_quickview(name),
                id='stamps_quickview',
                justify='around'
            )
        )
    else:
        cardbody = dbc.CardBody(
            [
                html.H4("{}".format(finkclass), className="card-title"),
                html.P("Constellation: {}".format(constellation), className="card-title"),
                dcc.Graph(
                    figure=draw_lightcurve_preview(name),
                    config={'displayModeBar': False},
                    style={
                        'width': '100%',
                        'height': '15pc'
                    }
                )
            ]
        )

        header = dbc.CardHeader(
            dbc.Row(
                [
                    dbc.Col(draw_cutouts_quickview(name), width=2),
                    dbc.Col([l1, l2], width=5),
                    dbc.Col([l3, l4], width=5)
                ],
                id='stamps_quickview',
                justify='around'
            )
        )


    simple_card_ = dbc.Card(
        [
            header,
            cardbody,
            dbc.CardFooter(
                dbc.Button(
                    "Go to {}".format(name),
                    color="primary",
                    outline=True,
                    href='{}/{}'.format(APIURL, name)
                )
            )
        ], style={'background': '#000', 'background-image': 'linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.9)), url(/assets/background.png)'}
    )
    return simple_card_

@app.callback(
    Output('carousel', 'children'),
    [
        Input("open_modal_quickview", "n_clicks"),
        Input("result_table", "data"),
        Input('is-mobile', 'children')
    ],
)
def carousel(nclick, data, is_mobile):
    """ Carousel that shows alert preview
    """
    if nclick > 0:
        pdf = pd.DataFrame(data)
        names = pdf['i:objectId'].apply(lambda x: x.split('[')[1].split(']')[0]).values[0:10]
        finkclasses = pdf['v:classification'].values[0:10]
        lastdates = pdf['v:lastdate'].values[0:10]
        fids = pdf['i:fid'].values[0:10]
        mags = pdf['i:magpsf'].values[0:10]
        jds = pdf['i:jd'].values[0:10]
        jdstarthists = pdf['i:jdstarthist'].values[0:10]
        ndethists = pdf['i:ndethist'].values[0:10]
        constellations = pdf['v:constellation'][0:10]
        is_mobiles = [is_mobile] * 10
        carousel = dtc.Carousel(
            [
                html.Div(dbc.Container(simple_card(*args))) for args in zip(names, finkclasses, lastdates, fids, mags, jds, jdstarthists, ndethists, constellations, is_mobiles)
            ],
            slides_to_scroll=1,
            slides_to_show=1,
            swipe_to_slide=True,
            autoplay=False,
            speed=800,
            variable_width=False,
            center_mode=False
        )
    else:
        carousel = html.Div("")
    return carousel


modal_quickview = html.Div(
    [
        dmc.Button(
            "Preview",
            id="open_modal_quickview",
            n_clicks=0,
            leftIcon=[DashIconify(icon="tabler:eye")],
            color="gray",
            fullWidth=True,
            variant='outline',
            size='xl',
            radius='xl'
        ),
        dbc.Modal(
            [
                dbc.ModalBody(
                    dbc.Container(
                        id='carousel',
                        fluid=True,
                        style={'width': '95%'}
                    ), style={
                        'background': '#000',
                        'background-image': 'linear-gradient(rgba(0,0,0,0.3), rgba(255,255,255,0.3)), url(/assets/background.png)'
                    }
                ),
                dbc.ModalFooter(
                    dbc.Button(
                        "Close", id="close_modal_quickview", className="ml-auto", n_clicks=0
                    ), style={'display': 'None'}
                ),
            ],
            id="modal_quickview",
            is_open=False,
            size="lg",
        ),
    ]
)

@app.callback(
    Output("modal_quickview", "is_open"),
    [
        Input("open_modal_quickview", "n_clicks"),
        Input("close_modal_quickview", "n_clicks")
    ],
    [State("modal_quickview", "is_open")],
)
def toggle_modal_preview(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open

def display_table_results(table, is_mobile):
    """ Display explorer results in the form of a table with a dropdown
    menu on top to insert more data columns.

    The dropdown menu options are taken from the client schema (ZTF & Fink). It also
    contains other derived fields from the portal (fink_additional_fields).

    Parameters
    ----------
    table: dash_table.DataTable
        Dash DataTable containing the results. Can be empty.

    Returns
    ----------
    out: list of objects
        The list of objects contain:
          1. A dropdown menu to add new columns in the table
          2. Table of results
        The dropdown is shown only if the table is non-empty.
    """
    schema = client.schema()
    schema_list = list(schema.columnNames())
    fink_fields = [i for i in schema_list if i.startswith('d:')]
    ztf_fields = [i for i in schema_list if i.startswith('i:')]
    fink_additional_fields = [
        'v:constellation', 'v:g-r', 'v:rate(g-r)',
        'v:classification',
        'v:lastdate', 'v:firstdate', 'v:lapse'
    ]

    dropdown = dcc.Dropdown(
        id='field-dropdown2',
        options=[
            {'label': 'Fink science module outputs', 'disabled': True, 'value': 'None'},
            *[{'label': field, 'value': field} for field in fink_fields],
            {'label': 'Fink additional values', 'disabled': True, 'value': 'None'},
            *[{'label': field, 'value': field} for field in fink_additional_fields],
            {'label': 'Original ZTF fields (subset)', 'disabled': True, 'value': 'None'},
            *[{'label': field, 'value': field} for field in ztf_fields]
        ],
        searchable=True,
        clearable=True,
        placeholder="Add more fields to the table",
    )

    switch = dmc.Switch(
        size="md",
        radius="xl",
        label="Unique objects",
        color="orange",
        checked=False,
        id="alert-object-switch"
    )
    switch_description = "Toggle the switch to list each object only once. Only the latest alert will be displayed."

    switch_sso = dmc.Switch(
        size="md",
        radius="xl",
        label="Unique Solar System objects",
        color="orange",
        checked=False,
        id="alert-sso-switch"
    )
    switch_sso_description = "Toggle the switch to list each Solar System Object only once. Only the latest alert will be displayed."

    switch_tracklet = dmc.Switch(
        size="md",
        radius="xl",
        label="Unique tracklets",
        color="orange",
        checked=False,
        id="alert-tracklet-switch"
    )
    switch_tracklet_description = "Toggle the switch to list each Tracklet only once (fast moving objects). Only the latest alert will be displayed."

    if is_mobile:
        width_dropdown = 8
        width_preview = 4
        width_button = 4
    else:
        width_dropdown = 10
        width_preview = 2
        width_button = 4

    return dbc.Container([
        html.Br(),
        dmc.Accordion(
            state={"0": False},
            offsetIcon=False,
            children=[
                dmc.AccordionItem(
                    children=[
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        dmc.Group(
                                            [
                                                dropdown,
                                                dmc.Paper(
                                                    [
                                                        dmc.Group(
                                                            [
                                                                switch,
                                                                    dbc.Popover(
                                                                        [dbc.PopoverBody(switch_description)],
                                                                        target="alert-object-switch",
                                                                        trigger="hover",
                                                                        placement="top"
                                                                    ),
                                                                    switch_sso,
                                                                    dbc.Popover(
                                                                        [dbc.PopoverBody(switch_sso_description)],
                                                                        target="alert-sso-switch",
                                                                        trigger="hover",
                                                                        placement="top"
                                                                    ),
                                                                    switch_tracklet,
                                                                    dbc.Popover(
                                                                        [dbc.PopoverBody(switch_tracklet_description)],
                                                                        target="alert-tracklet-switch",
                                                                        trigger="hover",
                                                                        placement="top"
                                                                    ),
                                                            ], position='center'
                                                        )
                                                    ],
                                                    radius='xl', p='md', shadow='xl', withBorder=True
                                                ),
                                            ], direction='column', grow=True
                                        )
                                    ], width=8
                                ),
                                dbc.Col(modal_quickview, width=4)
                            ]
                        )
                    ],
                    label="Table options",
                    icon=[
                        DashIconify(
                            icon="tabler:arrow-bar-to-down",
                            color=dmc.theme.DEFAULT_COLORS["dark"][6],
                            width=20,
                        )
                    ],
                )
            ]
        ),
        table
    ], fluid=True)

@app.callback(
    Output('aladin-lite-div-skymap', 'run'),
    [
        Input("result_table", "data"),
        Input("result_table", "columns"),
        Input('tabs', 'active_tab')
    ],
)
def display_skymap(data, columns, activetab):
    """ Display explorer result on a sky map (Aladin lite). Limited to 1000 sources total.

    TODO: image is not displayed correctly the first time

    the default parameters are:
        * PanSTARRS colors
        * FoV = 360 deg
        * Fink alerts overlayed

    Callbacks
    ----------
    Input: takes the validation flag (0: no results, 1: results) and table data
    Output: Display a sky image around the alert position from aladin.
    """
    ctx = dash.callback_context
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if len(data) > 1000:
        msg = '<b>We cannot display {} objects on the sky map (limit at 1000). Please refine your query.</b><br>'.format(len(data))
        return """var container = document.getElementById('aladin-lite-div-skymap');var txt = '{}'; container.innerHTML = txt;""".format(msg)
    if len(data) > 0 and (activetab == 't2'):
        pdf = pd.DataFrame(data)

        # Coordinate of the first alert
        ra0 = pdf['i:ra'].values[0]
        dec0 = pdf['i:dec'].values[0]

        # Javascript. Note the use {{}} for dictionary
        # Force redraw of the Aladin lite window
        img = """var container = document.getElementById('aladin-lite-div-skymap');var txt = ''; container.innerHTML = txt;"""

        # Aladin lite
        img += """var a = A.aladin('#aladin-lite-div-skymap', {{target: '{} {}', survey: 'P/PanSTARRS/DR1/color/z/zg/g', showReticle: true, allowFullZoomout: true, fov: 360}});""".format(ra0, dec0)

        ras = pdf['i:ra'].values
        decs = pdf['i:dec'].values
        filts = pdf['i:fid'].values
        filts_dic = {1: 'g', 2: 'r'}
        times = pdf['v:lastdate'].values
        link = '<a target="_blank" href="{}/{}">{}</a>'
        titles = [link.format(APIURL, i.split(']')[0].split('[')[1], i.split(']')[0].split('[')[1]) for i in pdf['i:objectId'].values]
        mags = pdf['i:magpsf'].values
        classes = pdf['v:classification'].values
        n_alert_per_class = pdf.groupby('v:classification').count().to_dict()['i:objectId']
        cats = []
        for ra, dec, fid, time_, title, mag, class_ in zip(ras, decs, filts, times, titles, mags, classes):
            if class_ in simbad_types:
                cat = 'cat_{}'.format(simbad_types.index(class_))
                color = class_colors['Simbad']
            elif class_ in class_colors.keys():
                cat = 'cat_{}'.format(class_.replace(' ', '_'))
                color = class_colors[class_]
            else:
                # Sometimes SIMBAD mess up names :-)
                cat = 'cat_{}'.format(class_)
                color = class_colors['Simbad']

            if cat not in cats:
                img += """var {} = A.catalog({{name: '{}', sourceSize: 15, shape: 'circle', color: '{}', onClick: 'showPopup', limit: 1000}});""".format(cat, class_ + ' ({})'.format(n_alert_per_class[class_]), color)
                cats.append(cat)
            img += """{}.addSources([A.source({}, {}, {{objectId: '{}', mag: {:.2f}, filter: '{}', time: '{}', Classification: '{}'}})]);""".format(cat, ra, dec, title, mag, filts_dic[fid], time_, class_)

        for cat in sorted(cats):
            img += """a.addCatalog({});""".format(cat)

        # img cannot be executed directly because of formatting
        # We split line-by-line and remove comments
        img_to_show = [i for i in img.split('\n') if '// ' not in i]

        return " ".join(img_to_show)
    else:
        return ""

def display_skymap():
    """ Display the sky map in the explorer tab results (Aladin lite)

    It uses `visdcc` to execute javascript directly.

    Returns
    ---------
    out: list of objects
    """
    return [
        dbc.Container(
            html.Div(
                [
                    visdcc.Run_js(id='aladin-lite-div-skymap'),
                    dcc.Markdown('_Hit the Aladin Lite fullscreen button if the image is not displayed (we are working on it...)_'),
                ], style={
                    'width': '100%',
                    'height': '25pc'
                }
            )
        )
    ]

@app.callback(
    [
        Output("select", "style"),
        Output("select", "options"),
        Output("select", "placeholder"),
    ],
    [
        Input("dropdown-query", "value"),
    ]
)
def input_type(chip_value):
    """ Decide if the dropdown below the search bar should be shown

    Only some query types need to have a dropdown (Date & Class search). In
    those cases, we show the dropdown, otherwise it is hidden.

    In the case of class search, the options are derived from the
    Fink classification, and the SIMBAD labels.
    """
    if chip_value == "Date Search":
        options = [
            {'label': '1 minute', 'value': 1},
            {'label': '10 minutes', 'value': 10},
            {'label': '60 minutes (can be long)', 'value': 60}
        ]
        placeholder = "Choose a time window (default is 1 minute)"
        return {}, options, placeholder
    elif chip_value == "Class Search":
        options = [
            {'label': 'All classes', 'value': 'allclasses'},
            {'label': 'Unknown', 'value': 'Unknown'},
            {'label': 'Fink derived classes', 'disabled': True, 'value': 'None'},
            {'label': 'Early Supernova Ia candidates', 'value': 'Early SN Ia candidate'},
            {'label': 'Supernova candidates', 'value': 'SN candidate'},
            {'label': 'Kilonova candidates', 'value': 'Kilonova candidate'},
            {'label': 'Microlensing candidates', 'value': 'Microlensing candidate'},
            {'label': 'Solar System (MPC)', 'value': 'Solar System MPC'},
            {'label': 'Solar System (candidates)', 'value': 'Solar System candidate'},
            {'label': 'Tracklet (space debris & satellite glints)', 'value': 'Tracklet'},
            {'label': 'Ambiguous', 'value': 'Ambiguous'},
            {'label': 'TNS classified data', 'disabled': True, 'value': 'None'},
            *[{'label': '(TNS) ' + simtype, 'value': '(TNS) ' + simtype} for simtype in tns_types],
            {'label': 'Simbad crossmatch', 'disabled': True, 'value': 'None'},
            *[{'label': '(SIMBAD) ' + simtype, 'value': '(SIMBAD) ' + simtype} for simtype in simbad_types]
        ]
        placeholder = "All classes"
        return {}, options, placeholder
    else:
        return {'display': 'none'}, [], ''

@app.callback(
    [
        Output("search_bar_input", "placeholder"),
        Output("search_bar_input", "value")
    ],
    [
        Input("dropdown-query", "value")
    ],
    State("search_bar_input", "value")
)
def chips_values(chip_value, val):
    """ Change the placeholder value of the search bar based on the query type
    """

    default = "    Enter a valid ZTF object ID or choose another query type"

    if chip_value == "objectId":
        return default, val
    elif chip_value == "Conesearch":
        return "    Conesearch around RA, Dec, radius(, startdate, window). See Help for the syntax", val
    elif chip_value == "Date Search":
        return "    Search alerts inside a time window. See Help for the syntax", val
    elif chip_value == "Class Search":
        return "    Choose a class below. We will display the last 100 alerts for this class.", val
    elif chip_value == "SSO":
        return "    Enter a valid IAU number. See Help for more information", val
    elif chip_value == "Tracklet":
        return "    Enter a date to get satellite glints or debris. See Help for more information", val
    else:
        return default, ""

@app.callback(
    Output("logo", "children"),
    [
        Input("submit", "n_clicks"),
        Input("search_bar_input", "n_submit"),
        Input("select", "options"),
        Input("url", "search")
    ],
)
def logo(ns, nss, options, searchurl):
    """ Show the logo in the start page (and hide it otherwise)
    """
    ctx = dash.callback_context

    logo = [
        html.Br(),
        html.Br(),
        dbc.Row(
            dbc.Col(
                html.Img(
                    src="/assets/Fink_PrimaryLogo_WEB.png",
                    height='100%',
                    width='60%'
                )
            ), style={'textAlign': 'center'}
        ),
        html.Br()
    ]
    if nss is None and (not ctx.triggered) and (searchurl == ''):
        return logo
    else:
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if (button_id in ["submit", "search_bar_input"]) or (searchurl != '') or (options != []):
        return []
    else:
        return logo

def construct_results_layout(table, is_mobile):
    """ Construct the tabs containing explorer query results
    """
    results_ = [
        dbc.Tabs(
            [
                dbc.Tab(print_msg_info(), label='Info', tab_id='t0', label_style = {"color": "#000"}),
                dbc.Tab(display_table_results(table, is_mobile), label="Table", tab_id='t1', label_style = {"color": "#000"}),
                dbc.Tab(display_skymap(), label="Sky map", tab_id='t2', label_style = {"color": "#000"}),
            ],
            id="tabs",
            active_tab="t1",
        )
    ]
    return results_

def populate_result_table(data, columns, is_mobile):
    """ Define options of the results table, and add data and columns
    """
    if is_mobile:
        page_size = 5
        markdown_options = {'link_target': '_self'}
    else:
        page_size = 10
        markdown_options = {'link_target': '_blank'}
    table = dash_table.DataTable(
        data=data,
        columns=columns,
        id='result_table',
        page_size=page_size,
        style_as_list_view=True,
        sort_action="native",
        filter_action="native",
        markdown_options=markdown_options,
        fixed_columns={'headers': True, 'data': 1},
        style_data={
            'backgroundColor': 'rgb(248, 248, 248, .7)'
        },
        style_table={'maxWidth': '100%'},
        style_cell={'padding': '5px', 'textAlign': 'center', 'overflow': 'hidden'},
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(248, 248, 248, .7)'
            }
        ],
        style_header={
            'backgroundColor': 'rgb(230, 230, 230)',
            'fontWeight': 'bold'
        }
    )
    return table

@app.callback(
    [
        Output("result_table", "data"),
        Output("result_table", "columns"),
    ],
    [
        Input('field-dropdown2', 'value'),
        Input('alert-object-switch', 'checked'),
        Input('alert-sso-switch', 'checked'),
        Input('alert-tracklet-switch', 'checked')
    ],
    [
        State("result_table", "data"),
        State("result_table", "columns"),
    ]
)
def update_table(field_dropdown, groupby1, groupby2, groupby3, data, columns):
    """ Update table by adding new columns (no server call)
    """
    changed_id = [p['prop_id'] for p in dash.callback_context.triggered][0]
    # Adding new columns (no client call)
    if 'field-dropdown2' in changed_id:
        if field_dropdown is None or len(columns) == 0:
            raise PreventUpdate

        incolumns = any(c.get('id') == field_dropdown for c in columns)

        if incolumns is True:
            raise PreventUpdate

        columns.append({
            'name': field_dropdown,
            'id': field_dropdown,
            'type': 'text',
            'presentation': 'markdown'
            # 'hideable': True,
        })

        return data, columns
    elif groupby1 is True:
        pdf = pd.DataFrame.from_dict(data)
        pdf = pdf.drop_duplicates(subset='i:objectId', keep="first")
        data = pdf.to_dict('records')
        return data, columns
    elif groupby2 is True:
        pdf = pd.DataFrame.from_dict(data)
        if not np.alltrue(pdf['i:ssnamenr'] == 'null'):
            mask = ~pdf.duplicated(subset='i:ssnamenr') | (pdf['i:ssnamenr'] == 'null')
            pdf = pdf[mask]
            data = pdf.to_dict('records')
        return data, columns
    elif groupby3 is True:
        pdf = pd.DataFrame.from_dict(data)
        if not np.alltrue(pdf['d:tracklet'] == ''):
            mask = ~pdf.duplicated(subset='d:tracklet') | (pdf['d:tracklet'] == '')
            pdf = pdf[mask]
            data = pdf.to_dict('records')
        return data, columns
    else:
        raise PreventUpdate

@app.callback(
    [
        Output("results", "children"),
        Output("submit", "children")
    ],
    [
        Input("search_bar_input", "value"),
        Input("dropdown-query", "value"),
        Input("select", "value"),
        Input("is-mobile", "children"),
        Input('url', 'search'),
        Input('submit', 'n_clicks')
    ],
    State("results", "children")
)
def results(query, query_type, dropdown_option, is_mobile, searchurl, results, n_clicks):
    """ Query the database from the search input

    Returns
    ---------
    out: list of Tabs
        Tabs containing info, table, and skymap with the results
    validation: int
        0: not results found, 1: results found
    """
    empty_query = (query is None) or (query == '')

    if empty_query and query_type != "Class Search":
        raise PreventUpdate

    colnames_to_display = [
        'i:objectId', 'i:ra', 'i:dec',
        'v:lastdate', 'v:classification', 'i:ndethist',
        'v:lapse'
    ]

    # catch parameters sent from URL
    # override any other options
    if searchurl != '':
        query, query_type, dropdown_option = extract_query_url(searchurl)

    validation = validate_query(query, query_type)
    if (not validation['flag']) and (not empty_query):
        return dmc.Alert(validation['text'], title=validation['header'], color='red', withCloseButton=True), no_update

    if query_type == 'objectId':
        r = requests.post(
            '{}/api/v1/explorer'.format(APIURL),
            json={
                'objectId': query,
            }
        )
    elif query_type == 'SSO':
        # strip from spaces
        query_ = str(query.replace(' ', ''))

        r = requests.post(
            '{}/api/v1/sso'.format(APIURL),
            json={
                'n_or_d': query_
            }
        )
    elif query_type == 'Tracklet':
        # strip from spaces
        payload = {
            'date': query
        }

        r = requests.post(
            '{}/api/v1/tracklet'.format(APIURL),
            json=payload
        )
    elif query_type == 'Conesearch':
        args = [i.strip() for i in query.split(',')]
        if len(args) == 3:
            ra, dec, radius = args
            startdate = None
            window = None
        elif len(args) == 5:
            ra, dec, radius, startdate, window = args
        r = requests.post(
            '{}/api/v1/explorer'.format(APIURL),
            json={
                'ra': ra,
                'dec': dec,
                'radius': float(radius),
                'startdate_conesearch': startdate,
                'window_days_conesearch': window
            }
        )
    elif query_type == 'Date Search':
        startdate = isoify_time(query)
        if dropdown_option is None:
            window = 1
        else:
            window = dropdown_option
        r = requests.post(
            '{}/api/v1/explorer'.format(APIURL),
            json={
                'startdate': startdate,
                'window': window
            }
        )
    elif query_type == 'Class Search':
        if dropdown_option is None:
            alert_class = 'allclasses'
        else:
            alert_class = dropdown_option
        r = requests.post(
            '{}/api/v1/latests'.format(APIURL),
            json={
                'class': alert_class,
                'n': '100'
            }
        )

    # Format output in a DataFrame
    pdf = pd.read_json(r.content)

    if pdf.empty:
        text, header = text_noresults(query, query_type, dropdown_option, searchurl)
        return dmc.Alert(
            text,
            title='Oops!',
            color="red",
            withCloseButton=True
        ), no_update
    else:
        # Make clickable objectId
        pdf['i:objectId'] = pdf['i:objectId'].apply(markdownify_objectid)

        if query_type == 'Conesearch':
            data = pdf.sort_values(
                'v:separation_degree', ascending=True
            ).to_dict('records')
        else:
            data = pdf.sort_values('i:jd', ascending=False).to_dict('records')

        columns = [
            {
                'id': c,
                'name': c,
                'type': 'text',
                # 'hideable': True,
                'presentation': 'markdown',
            } for c in colnames_to_display
        ]
        validation = 1

    table = populate_result_table(data, columns, is_mobile)
    return construct_results_layout(table, is_mobile), no_update

def text_noresults(query, query_type, dropdown_option, searchurl):
    """ Toast to warn the user about the fact that we found no results
    """
    # catch parameters sent from URL
    # override any other options
    if searchurl != '':
        query, query_type, dropdown_option = extract_query_url(searchurl)

    # Good query, but no results
    # ugly hack
    if query_type == 'objectId':
        header = "Search by Object ID"
        text = "{} not found".format(query)
    elif query_type == 'SSO':
        header = "Search by Solar System Object ID"
        text = "{} ({}) not found".format(query, str(query).replace(' ', ''))
    elif query_type == 'Tracklet':
        header = "Search by Tracklet ID"
        text = "{} not found".format(query)
    elif query_type == 'Conesearch':
        header = "Conesearch"
        text = "No alerts found for (RA, Dec, radius) = {}".format(
            query
        )
    elif query_type == 'Date Search':
        header = "Search by Date"
        if dropdown_option is None:
            window = 1
        else:
            window = dropdown_option
        jd_start = Time(query).jd
        jd_end = jd_start + TimeDelta(window * 60, format='sec').jd

        text = "No alerts found between {} and {}".format(
            Time(jd_start, format='jd').iso,
            Time(jd_end, format='jd').iso
        )
    elif query_type == 'Class Search':
        header = "Get latest 100 alerts by class"
        if dropdown_option is None:
            alert_class = 'allclasses'
        else:
            alert_class = dropdown_option
        # start of the Fink operations
        jd_start = Time('2019-11-01 00:00:00').jd
        jd_stop = Time.now().jd

        text = "No alerts for class {} in between {} and {}".format(
            alert_class,
            Time(jd_start, format='jd').iso,
            Time(jd_stop, format='jd').iso
        )
    return text, header

# building the navigation bar
dropdown = dbc.DropdownMenu(
    children=[
        dbc.DropdownMenuItem("About", href="/about"),
        dbc.DropdownMenuItem("Fink Website", href="https://fink-broker.org/"),
        dbc.DropdownMenuItem(
            "Science Portal GitHub",
            href="https://github.com/astrolabsoftware/fink-science-portal"
        ),
    ],
    nav=True,
    in_navbar=True,
    label="Info",
)

navbar = dbc.Navbar(
    [
        html.A(
            dbc.Row(
                [
                    dbc.Col(
                        dbc.NavbarBrand(
                            "Fink Science portal {}".format(portal_version),
                            className="ml-2"
                        )
                    ),
                ],
                justify="start",
                className="g-0",
            ),
            href="/",
        ),
        dbc.NavbarToggler(id="navbar-toggler2"),
        dbc.Collapse(
            dbc.Nav(
                # right align dropdown menu with ml-auto className
                [
                    dbc.NavItem(dbc.NavLink('Search', href="{}".format(APIURL))),
                    dbc.NavItem(dbc.NavLink('Statistics', href="{}/stats".format(APIURL))),
                    dbc.NavItem(dbc.NavLink('API', href="{}/api".format(APIURL))),
                    dbc.NavItem(dbc.NavLink('Tutorials', href="https://github.com/astrolabsoftware/fink-notebook-template")),
                    dropdown
                ],
                navbar=True
            ),
            id="navbar-collapse2",
            navbar=True,
            style={'background-color': 'rgb(255,250,250)'}
        ),
    ],
    color="rgba(255,255,255,0.9)",
    dark=False,
    className="finknav",
    fixed='top'
)

# add callback for toggling the collapse on small screens
@app.callback(
    Output("navbar-collapse2", "is_open"),
    [Input("navbar-toggler2", "n_clicks")],
    [State("navbar-collapse2", "is_open")],
)
def toggle_navbar_collapse(n, is_open):
    if n:
        return not is_open
    return is_open

# embedding the navigation bar
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    navbar,
    html.Div(id='page-content'),
    html.Div(children=False, id='is-mobile', hidden=True),
])

app.clientside_callback(
    """
    function(href) {
        var cond1 = ( ( window.innerWidth <= 820 ) && ( window.innerHeight <= 600 ) )
        var cond2 = ( ( window.innerWidth <= 600 ) && ( window.innerHeight <= 820 ) )
        return ( ( cond1 ) || ( cond2 ) );
    }
    """,
    Output('is-mobile', 'children'),
    Input('url', 'href')
)

@app.callback(
    Output('page-content', 'children'),
    [Input('url', 'pathname'), Input('is-mobile', 'children')]
)
def display_page(pathname, is_mobile):
    if is_mobile:
        width = '95%'
        style = {'background-image': 'linear-gradient(rgba(255,255,255,0.3), rgba(255,255,255,0.3)), url(/assets/background.png)'}
    else:
        width = '60%'
        style = {'background-image': 'linear-gradient(rgba(255,255,255,0.3), rgba(255,255,255,0.3)), url(/assets/background.png)', 'background-size': 'contain'}
    layout = html.Div(
        [
            html.Br(),
            html.Br(),
            dbc.Container(
                [
                    html.Div(id='logo'),
                    html.Br(),
                    dmc.Chips(
                        data=[
                            {"value": "objectId", "label": "objectId"},
                            {"value": "Conesearch", "label": "Conesearch"},
                            {"value": "Date Search", "label": "Date Search"},
                            {"value": "Class Search", "label": "Class Search"},
                            {"value": "SSO", "label": "SSO"},
                            {"value": "Tracklet", "label": "Tracklet"},
                        ],
                        id="dropdown-query",
                        value='objectId',
                        color="orange",
                        radius="xl",
                        size="sm",
                        spacing="xl",
                        variant="outline",
                        position='center',
                        multiple=False,
                    ),
                    html.Br(),
                    dbc.Row(fink_search_bar),
                    html.Br(),
                    dcc.Dropdown(
                        id='select',
                        searchable=True,
                        clearable=True,
                    ),
                    html.Br(),
                ], id='trash', fluid=True, style={'width': width}
            ),
            dbc.Container(id='results'),
        ],
        className='home',
        style=style
    )
    if pathname == '/about':
        return about.layout
    elif pathname == '/api':
        return api.layout(is_mobile)
    elif pathname == '/stats':
        return statistics.layout(is_mobile)
    elif 'ZTF' in pathname:
        return summary.layout(pathname, is_mobile)
    else:
        return layout


# register the API
try:
    from apps.api.api import api_bp
    server.register_blueprint(api_bp, url_prefix='/')
    server.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    server.config['JSON_SORT_KEYS'] = False
except ImportError as e:
    print('API not yet registered')


if __name__ == '__main__':
    import yaml
    input_args = yaml.load(open('config.yml'), yaml.Loader)
    app.run_server(input_args['IP'], debug=True, port=input_args['PORT'])

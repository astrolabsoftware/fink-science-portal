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
from dash import html, dcc, Input, Output, State, dash_table, no_update, clientside_callback, ALL, MATCH
from dash.exceptions import PreventUpdate

import dash_bootstrap_components as dbc
import visdcc
import dash_trich_components as dtc

import dash_mantine_components as dmc
from dash_iconify import DashIconify

from dash_autocomplete_input import AutocompleteInput
# from dash_lazy_load import LazyLoad
# from dash_grocery import LazyLoad

from app import server
from app import app
from app import APIURL

from apps import summary, about, statistics, query_cluster, gw
from apps.api import api
from apps import __version__ as portal_version

from apps.utils import markdownify_objectid, class_colors, simbad_types
from apps.utils import isoify_time
from apps.utils import convert_jd
from apps.utils import retrieve_oid_from_metaname
from apps.utils import loading, help_popover
from apps.utils import class_colors
from apps.plotting import draw_cutouts_quickview, draw_lightcurve_preview
from apps.cards import card_search_result
from apps.parse import parse_query

from fink_utils.photometry.utils import is_source_behind

import requests
import pandas as pd
import numpy as np
from astropy.time import Time, TimeDelta

import urllib

tns_types = pd.read_csv('assets/tns_types.csv', header=None)[0].values
tns_types = sorted(tns_types, key=lambda s: s.lower())

fink_classes = [
    'All classes',
    'Unknown',
    # Fink derived classes
    'Early SN Ia candidate',
    'SN candidate',
    'Kilonova candidate',
    'Microlensing candidate',
    'Solar System MPC',
    'Solar System candidate',
    'Tracklet',
    'Ambiguous',
    # TNS classified data
    *['(TNS) ' + t for t in tns_types],
    # Simbad crossmatch
    *['(SIMBAD) ' + t for t in simbad_types]
]

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
By default, the table shows:

- i:objectId: Unique identifier for this object
- i:ra: Right Ascension of candidate; J2000 (deg)
- i:dec: Declination of candidate; J2000 (deg)
- v:lastdate: last date the object has been seen by Fink
- v:classification: Classification inferred by Fink (Supernova candidate, Microlensing candidate, Solar System, SIMBAD class, ...)
- i:ndethist: Number of spatially coincident detections falling within 1.5 arcsec going back to the beginning of the survey; only detections that fell on the same field and readout-channel ID where the input candidate was observed are counted. All raw detections down to a photometric S/N of ~ 3 are included.
- v:lapse: number of days between the first and last spatially coincident detections.

You can also add more columns using the dropdown button above the result table. Full documentation of all available fields can be found at {}/api/v1/columns.

Moreover, you can hit the button `Preview`. This will show you more information
about the first 10 alerts (science cutout, and basic information). Note you can
swipe between alerts (or use arrows on a laptop).

Finally, the button `Sky Map` will open a popup with embedded Aladin sky map showing the positions of the search results on the sky.
""".format(APIURL)

# Smart search field
quick_fields = [
    ['class', 'Alert class\nSelect one of Fink supported classes from the menu'],
    ['last', 'Number of latest alerts to show'],
    ['r', 'Radius for cone search\nIn arcseconds by default, use `r=1m` or `r=2d` for arcminutes or degrees, correspondingly'],
    # ['before', 'Upper timit on alert time\nISO time, MJD or JD'],
    ['after', 'Lower timit on alert time\nISO time, MJD or JD'],
    ['before', 'Upper timit on alert time\nISO time, MJD or JD'],
    ['window', 'Time window length\nDays']
]

fink_search_bar = [
        html.Div(
            [
                html.Span('Quick fields:', className='text-secondary'),
            ] + [
                html.Span(
                    [
                        html.A(
                            __[0],
                            title=__[1],
                            id={'type': 'search_bar_quick_field', 'index': _},
                            n_clicks=0,
                            className='ms-2 link text-decoration-none'
                        ),
                        " "
                    ]
                ) for _,__ in enumerate(quick_fields)
            ] + [
                html.Span(
                    dmc.Switch(
                        radius="xl",
                        size='sm',
                        offLabel=DashIconify(icon="radix-icons:id-card", width=15),
                        onLabel=DashIconify(icon="radix-icons:table", width=15),
                        color="orange",
                        checked=False,
                        persistence=True,
                        id="results_table_switch"
                    ),
                    className='float-right',
                    title='Show results as cards or table'
                ),
            ],
            className="ps-4 pe-4 mb-0 mt-1"
        ),

] + [html.Div(
    # className='p-0 m-0 border shadow-sm rounded-3',
    className='p-0 m-0 rcorners2 shadow',
    id="search_bar",
    # className='rcorners2',
    children=[
        dbc.InputGroup(
            [
                AutocompleteInput(
                    id='search_bar_input',
                    placeholder='Search, and you will find',
                    component='input',
                    trigger=[
                        'class:', 'class=',
                    ],
                    options={
                        'class:':fink_classes, 'class=':fink_classes,
                    },
                    maxOptions=0,
                    className="inputbar form-control border-0",
                    quoteWhitespaces=True,
                    autoFocus=True,
                ),

                dbc.Spinner(
                    dmc.ActionIcon(
                        DashIconify(icon="tabler:search", width=20),
                        n_clicks=0,
                        id="search_bar_submit",
                        color='gray',
                        variant="transparent",
                        radius='xl',
                        size='lg',
                        loaderProps={'variant': 'dots', 'color': 'orange'},
                    ), size='sm', color='warning'
                ),
                # modal
                help_popover(
                    [
                        dcc.Markdown(message_help)
                    ],
                    'help_search',
                    trigger=dmc.ActionIcon(
                        DashIconify(icon="mdi:help"),
                        id='help_search',
                        color='gray',
                        variant="transparent",
                        radius='xl',
                        size='lg',
                        # className="d-none d-sm-flex"
                    ),
                ),
            ]
        ),
        # Search suggestions
        dbc.Collapse(
            dbc.ListGroup(
                id='search_bar_suggestions',
            ),
            id='search_bar_suggestions_collapser',
            is_open=False,
        ),
        # Debounce timer
        dcc.Interval(
            id="search_bar_timer",
            interval=2000,
            max_intervals=1,
            disabled=True
        )
    ],
)]

# Time-based debounce from https://joetatusko.com/2023/07/11/time-based-debouncing-with-plotly-dash/
clientside_callback(
    """
    function start_suggestion_debounce_timer(value, n_submit, n_clicks, n_intervals) {
        const triggered = dash_clientside.callback_context.triggered.map(t => t.prop_id);
        if (triggered == 'search_bar_input.n_submit' || triggered == 'search_bar_submit.n_clicks')
            return [dash_clientside.no_update, true];

        if (n_intervals > 0)
            return [0, false];
        else
            return [dash_clientside.no_update, false];
    }
    """,
    [
        Output('search_bar_timer', 'n_intervals'),
        Output('search_bar_timer', 'disabled')
    ],
    Input('search_bar_input', 'value'),
    Input('search_bar_input', 'n_submit'),
    Input('search_bar_submit', 'n_clicks'),
    State('search_bar_timer', 'n_intervals'),
    prevent_initial_call=True,
)

# Update suggestions on (debounced) input
@app.callback(
    Output('search_bar_suggestions', 'children'),
    Output('search_bar_submit', 'children'),
    Output('search_bar_suggestions_collapser', 'is_open'),
    Input('search_bar_timer', 'n_intervals'),
    Input('search_bar_input', 'n_submit'),
    Input('search_bar_submit', 'n_clicks'),
    State('search_bar_input', 'value'),
    prevent_initial_call=True,
)
def update_suggestions(n_intervals, n_submit, n_clicks, value):
    # Clear the suggestions on submit
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if triggered_id in ['search_bar_input', 'search_bar_submit']:
        return no_update, no_update, False

    # Did debounce trigger fire?..
    if n_intervals != 1:
        return no_update, no_update, no_update

    if not value:
        return None, no_update, False

    query = parse_query(value, timeout=5)
    suggestions = []

    params = query['params']

    if not query['action']:
        return None, no_update, False

    if query['action'] == 'unknown':
        content = [
            html.Em('Query not recognized', className='m-0')
        ]
    else:
        content = []

        if query['completions']:
            completions = []

            for i,item in enumerate(query['completions']):
                if isinstance(item, list) or isinstance(item, tuple):
                    # We expect it to be (name, ext)
                    name = item[0]
                    ext = item[1]
                else:
                    name = item
                    ext = item

                completions.append(
                    html.A(
                        ext,
                        id={'type': 'search_bar_completion', 'index': i},
                        title=name,
                        n_clicks=0,
                        className='ms-2 link text-decoration-none'
                    )
                )

            content += [
                html.Div(
                    [
                        html.Span('Did you mean:', className='text-secondary'),
                    ] + completions,
                    className="border-bottom p-1 mb-1 mt-1 small"
                )
            ]

        content += [
            dmc.Group([
                html.Strong(query['object']) if query['object'] else None,
                dmc.Badge(query['type'], variant="outline", color='blue') if query['type'] else None,
                dmc.Badge(query['action'], variant="outline", color='red'),
            ], noWrap=False, position='left'),
            html.P(query['hint'], className='m-0'),
        ]

    if len(params):
        content += [
            html.Small(" ".join(["{}={}".format(_,params[_]) for _ in params]))
        ]

    suggestion = dbc.ListGroupItem(
        content,
        action=True,
        className='border-0'
    )

    suggestions.append(suggestion)

    return suggestions, no_update, True

# Completion clicked
# TODO: convert to clientside callback, if pattern matching is supported for them
@app.callback(
    Output('search_bar_input', 'value'),
    Input({'type': 'search_bar_completion', 'index': ALL}, 'n_clicks'),
    State({'type': 'search_bar_completion', 'index': ALL}, 'title'),
    prevent_initial_call=True
)
def on_completion(n_clicks, values):
    ctx = dash.callback_context
    if ctx.triggered[0]['value']:
        return values[ctx.triggered_id['index']]

    return no_update

# Quick field clicked
# clientside_callback(
#     """
#     function on_quickfield(n_clicks, values, value) {
#         const ctx = dash_clientside.callback_context;
#         window['ctx'] = ctx;
#         return window.dash_clientside.callback_context.triggered[0].prop_id.split('.')[0];
#     }
#     """,
#     Output('search_bar_input', 'value'),
#     Input({'type': 'search_bar_quick_field', 'index': ALL}, 'n_clicks'),
#     State({'type': 'search_bar_quick_field', 'index': ALL}, 'children'),
#     State('search_bar_input', 'value'),
#     prevent_initial_call=True
# )

# TODO: convert to clientside callback, if pattern matching is supported for them
@app.callback(
    Output('search_bar_input', 'value', allow_duplicate=True),
    Input({'type': 'search_bar_quick_field', 'index': ALL}, 'n_clicks'),
    State({'type': 'search_bar_quick_field', 'index': ALL}, 'children'),
    State('search_bar_input', 'value'),
    prevent_initial_call=True
)
def on_quickfield(n_clicks, values, value):
    if not value:
        value = ''

    ctx = dash.callback_context
    if ctx.triggered[0]['value']:
        return value + ' ' + values[ctx.triggered_id['index']] + '='

    return no_update

def display_table_results(table):
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
    r = requests.get(
        '{}/api/v1/columns'.format(APIURL),
        )
    pdf = pd.read_json(r.content)

    fink_fields = ['d:' + i for i in pdf.loc['Fink science module outputs (d:)']['fields'].keys()]
    ztf_fields = ['i:' + i for i in pdf.loc['ZTF original fields (i:)']['fields'].keys()]
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
        size="xs",
        radius="xl",
        label="Unique objects",
        color="orange",
        checked=False,
        id="alert-object-switch"
    )
    switch_description = "Toggle the switch to list each object only once. Only the latest alert will be displayed."

    switch_sso = dmc.Switch(
        size="xs",
        radius="xl",
        label="Unique SSO",
        color="orange",
        checked=False,
        id="alert-sso-switch"
    )
    switch_sso_description = "Toggle the switch to list each Solar System Object only once. Only the latest alert will be displayed."

    switch_tracklet = dmc.Switch(
        size="xs",
        radius="xl",
        label="Unique tracklets",
        color="orange",
        checked=False,
        id="alert-tracklet-switch"
    )
    switch_tracklet_description = "Toggle the switch to list each Tracklet only once (fast moving objects). Only the latest alert will be displayed."

    return [
        dbc.Row(
            [
                dbc.Col(
                    dropdown,
                    lg=5, md=6
                ),
                dbc.Col(
                    dbc.Row(
                        [
                            dbc.Col(
                                modal_skymap(),
                                md='auto'
                            ),
                            dbc.Col(
                                help_popover(
                                    dcc.Markdown(msg_info),
                                    id='help_msg_info',
                                    trigger=dmc.ActionIcon(
                                        DashIconify(icon="mdi:help"),
                                        id='help_msg_info',
                                        color='gray',
                                        variant="default",
                                        radius='xl',
                                        size='lg',
                                    ),
                                ),
                                md='auto'
                            ),
                        ],
                        align='center', justify='end',
                    ),
                    md='auto',
                )
            ],
            align='center', justify='between',
            className='pt-1 pb-1 ps-2 pe-2'
        ),
        dbc.Row(
            [
                dbc.Col(
                    dmc.Tooltip(
                        children=switch,
                        width=220,
                        multiline=True,
                        withArrow=True,
                        transition="fade",
                        transitionDuration=200,
                        label=switch_description
                    ),
                    md='auto',
                ),
                dbc.Col(
                    dmc.Tooltip(
                        children=switch_sso,
                        width=220,
                        multiline=True,
                        withArrow=True,
                        transition="fade",
                        transitionDuration=200,
                        label=switch_sso_description
                    ),
                    md='auto'
                ),
                dbc.Col(
                    dmc.Tooltip(
                        children=switch_tracklet,
                        width=220,
                        multiline=True,
                        withArrow=True,
                        transition="fade",
                        transitionDuration=200,
                        label=switch_tracklet_description
                    ),
                    md='auto'
                ),
            ],
            align='center', justify='start',
            className='pt-1 pb-1 ps-2 pe-2',
        ),
        table
    ]

@app.callback(
    Output('aladin-lite-div-skymap', 'run'),
    [
        Input("result_table", "data"),
        Input("result_table", "columns"),
        Input("modal_skymap", "is_open"),
    ],
)
def display_skymap(data, columns, is_open):
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

    if not is_open:
        return no_update

    if len(data) > 0:
        if len(data) > 1000:
            # Silently limit the size of list we display
            data = data[:1000]

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

        if 'v:lastdate' not in pdf.columns:
            # conesearch does not expose v:lastdate
            pdf['v:lastdate'] = pdf['i:jd'].apply(convert_jd)
        times = pdf['v:lastdate'].values
        link = '<a target="_blank" href="{}/{}">{}</a>'
        titles = [link.format(APIURL, i.split(']')[0].split('[')[1], i.split(']')[0].split('[')[1]) for i in pdf['i:objectId'].values]
        mags = pdf['i:magpsf'].values

        if 'v:classification' not in pdf.columns:
            if 'd:classification' in pdf.columns:
                pdf['v:classification'] = pdf['d:classification']
            else:
                pdf['v:classification'] = 'Unknown'
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

def modal_skymap():
    button = dmc.Button(
        "Sky Map",
        id="open_modal_skymap",
        n_clicks=0,
        leftIcon=[DashIconify(icon="bi:stars")],
        color="gray",
        fullWidth=True,
        variant='default',
        radius='xl'
    )

    modal = html.Div(
        [
            button,
            dbc.Modal(
                [
                    loading(
                        dbc.ModalBody(
                            html.Div(
                                [
                                    visdcc.Run_js(id='aladin-lite-div-skymap', style={'border': '0'}),
                                    # dcc.Markdown('_Hit the Aladin Lite fullscreen button if the image is not displayed (we are working on it...)_'),
                                ], style={
                                    'width': '100%',
                                    'height': '100%',
                                }
                            ),
                            className="p-1",
                            style={'height': '30pc'},
                        )
                    ),
                    dbc.ModalFooter(
                        dmc.Button(
                            "Close", id="close_modal_skymap", className="ml-auto",
                            color="gray",
                            # fullWidth=True,
                            variant='default',
                            radius='xl'
                        ),
                    ),
                ],
                id="modal_skymap",
                is_open=False,
                size="lg",
                # fullscreen="lg-down",
            ),
        ]
    )

    return modal

clientside_callback(
    """
    function toggle_modal_skymap(n1, n2, is_open) {
        if (n1 || n2)
            return ~is_open;
        else
            return is_open;
    }
    """,
    Output("modal_skymap", "is_open"),
    [
        Input("open_modal_skymap", "n_clicks"),
        Input("close_modal_skymap", "n_clicks")
    ],
    [State("modal_skymap", "is_open")],
    prevent_initial_call=True,
)

# @app.callback(
#     Output("modal_skymap", "is_open"),
#     [
#         Input("open_modal_skymap", "n_clicks"),
#         Input("close_modal_skymap", "n_clicks")
#     ],
#     [State("modal_skymap", "is_open")],
# )
# def toggle_modal_preview(n1, n2, is_open):
#     if n1 or n2:
#         return not is_open
#     return is_open

def construct_results_layout(table, msg):
    """ Construct the tabs containing explorer query results
    """
    results_ = html.Div(
        className='bg-opaque-100 mb-2 shadow-sm border rounded-3',
        children=[
            html.P(
                msg,
                className='p-3 m-0'
            ),
        ] + display_table_results(table)
    )

    return results_

def populate_result_table(data, columns):
    """ Define options of the results table, and add data and columns
    """
    page_size = 100
    markdown_options = {'link_target': '_blank'}

    table = dash_table.DataTable(
        data=data,
        columns=columns,
        id='result_table',
        page_size=page_size,
        # page_action='none',
        style_as_list_view=True,
        sort_action="native",
        filter_action="native",
        markdown_options=markdown_options,
        # fixed_columns={'headers': True, 'data': 1},
        style_data={
            'backgroundColor': 'rgb(248, 248, 248, 1.0)',
        },
        style_table={'maxWidth': '100%', 'overflowX': 'scroll'},
        style_cell={
            'padding': '5px',
            'textAlign': 'right',
            'overflow': 'hidden',
            'font-family': 'sans-serif',
            'fontSize': 14},
        style_data_conditional=[
            {
                'if': {'column_id': 'i:objectId'},
                'backgroundColor': 'rgb(240, 240, 240, 1.0)',
            }
        ],
        style_header={
            'backgroundColor': 'rgb(230, 230, 230)',
            'fontWeight': 'bold', 'textAlign': 'center'
        },
        # Align the text in Markdown cells
        css=[dict(selector="p", rule="margin: 0; text-align: left")]
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
            'type': 'numeric', 'format': dash_table.Format.Format(precision=8),
            'presentation': 'markdown' if field_dropdown == 'i:objectId' else 'input',
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

# Prepare and display the results
@app.callback(
    [
        Output('results', 'children'),
        Output('logo', 'is_open'),
        Output('search_bar_submit', 'children', allow_duplicate=True),
    ],
    [
        Input('search_bar_input', 'n_submit'),
        Input('search_bar_submit', 'n_clicks'),
        Input('url', 'search'),
    ],
    State('search_bar_input', 'value'),
    State('results_table_switch', 'checked'),
    # prevent_initial_call=True
    prevent_initial_call='initial_duplicate',
)
def results(n_submit, n_clicks, searchurl, value, show_table):
    """ Parse the search string and query the database
    """
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if not triggered_id:
        # FIXME: ???
        triggered_id = 'url'

    if not n_submit and not n_clicks and not searchurl:
        raise PreventUpdate

    if not value and not searchurl:
        # TODO: show back the logo?..
        return None, no_update, no_update

    colnames_to_display = {
        'i:objectId': 'objectId',
        'i:ra': 'RA (deg)',
        'i:dec': 'Dec (deg)',
        'v:lastdate': 'Last alert',
        'v:classification': 'Classification',
        'i:ndethist': 'Number of measurements',
        'v:lapse': 'Time variation (day)'
    }

    if searchurl and triggered_id == 'url':
        # Parse GET parameters from url
        params = dict(
            urllib.parse.parse_qsl(
                urllib.parse.urlparse(searchurl).query
            )
        )
        # Construct the query from them
        query = {'action': params.pop('action')}
        query['params'] = params
    else:
        query = parse_query(value)

    if not query or not query['action']:
        return None, no_update, no_update

    if query['action'] == 'unknown':
        return dbc.Alert(
            'Query not recognized: {}'.format(value),
            color='danger',
            className='shadow-sm'
        ), no_update, no_update

    elif query['action'] == 'objectid':
        # Search objects by objectId
        msg = "ObjectId search with {} name {}".format('partial' if query['partial'] else 'exact', query['object'])
        r = requests.post(
            '{}/api/v1/explorer'.format(APIURL),
            json={
                'objectId': query['object'],
            }
        )

    elif query['action'] == 'sso':
        # Solar System Objects
        msg = "Solar System object search with ssnamenr {}".format(query['params']['sso'])
        r = requests.post(
            '{}/api/v1/sso'.format(APIURL),
            json={
                'n_or_d': query['params']['sso']
            }
        )

    elif query['action'] == 'tracklet':
        # Tracklet by (partial) name
        msg = "Tracklet search with {} name {}".format('partial' if query['partial'] else 'exact', query['object'])
        payload = {
            'id': query['object']
        }

        r = requests.post(
            '{}/api/v1/tracklet'.format(APIURL),
            json=payload
        )

    elif query['action'] == 'conesearch':
        # Conesearch
        ra = float(query['params'].get('ra'))
        dec = float(query['params'].get('dec'))
        # Default is 10 arcsec, max is 5 degrees
        sr = min(float(query['params'].get('r', 10)), 18000)

        msg = "Cone search with center at {:.4f} {:.3f} and radius {:.1f} arcsec".format(ra, dec, sr)

        payload = {
            'ra': ra,
            'dec': dec,
            'radius': sr,
        }

        if 'after' in query['params']:
            startdate = isoify_time(query['params']['after'])
            window = float(query['params'].get('window', 1.0))

            msg += ' within {} days after {}'.format(window, startdate)

            payload['startdate_conesearch'] = startdate
            payload['window_days_conesearch'] = window

        r = requests.post(
            '{}/api/v1/explorer'.format(APIURL),
            json=payload
        )

        colnames_to_display = {
            'i:objectId': 'objectId',
            'v:separation_degree': 'Separation (degree)',
            'd:classification': 'Classification',
            'd:nalerthist': 'Number of measurements',
            'v:lapse': 'Time variation (day)'
        }

    elif query['action'] == 'class':
        # Class-based search
        alert_class = query['params'].get('class')
        if not alert_class or alert_class == 'All classes':
            alert_class = 'allclasses'

        n_last = int(query['params'].get('last', 100))

        msg = "Last {} objects with class '{}'".format(n_last, alert_class)

        payload = {
            'class': alert_class,
            'n': n_last
        }

        if 'after' in query['params']:
            startdate = isoify_time(query['params']['after'])

            msg += ' after {}'.format(startdate)

            payload['startdate'] = startdate

        if 'before' in query['params']:
            stopdate = isoify_time(query['params']['before'])

            msg += ' before {}'.format(stopdate)

            payload['stopdate'] = stopdate

        r = requests.post(
            '{}/api/v1/latests'.format(APIURL),
            json=payload
        )

    else:
        return dbc.Alert(
            'Unhandled query: {}'.format(query),
            color='danger',
            className='shadow-sm'
        ), no_update, no_update

    # Format output in a DataFrame
    pdf = pd.read_json(r.content)

    msg = "{} - {} found".format(msg, 'nothing' if pdf.empty else str(len(pdf.index)) + ' objects')

    if pdf.empty:
        # text, header = text_noresults(query, query_type, dropdown_option, searchurl)
        return dbc.Alert(
            msg,
            color="warning",
            className='shadow-sm'
        ), no_update, no_update
    else:
        # Make clickable objectId
        pdf['i:objectId'] = pdf['i:objectId'].apply(markdownify_objectid)

        # Sort the results
        if query['action'] == 'conesearch':
            pdf['v:lapse'] = pdf['i:jd'] - pdf['i:jdstarthist']
            data = pdf.sort_values(
                'v:separation_degree', ascending=True
            )
        else:
            data = pdf.sort_values('i:jd', ascending=False)

        if show_table:
            data = data.to_dict('records')

            columns = [
                {
                    'id': c,
                    'name': colnames_to_display[c],
                    'type': 'numeric', 'format': dash_table.Format.Format(precision=8),
                    # 'hideable': True,
                    'presentation': 'markdown' if c == 'i:objectId' else 'input',
                } for c in colnames_to_display.keys()
            ]

            table = populate_result_table(data, columns)
            results = construct_results_layout(table, msg)
        else:
            results = construct_results_list(pdf, msg)

        return results, False, no_update

def construct_results_list(pdf, msg, page_size=10):
    results_ = [
        dbc.Row(
            [
                dbc.Col(
                    msg,
                    md='auto'
                ),
                dbc.Col(
                    modal_skymap(),
                    md='auto'
                ),
            ],
            align='end', justify='between',
            className='m-2 ms-4 me-4'
        ),
        # Data storage
        dcc.Store(
            id='results_store',
            storage_type='memory',
            data=pdf.to_json(),
        ),
        dcc.Store(
            id='results_page_size_store',
            storage_type='memory',
            data=str(page_size),
        ),
        # For Aladin
        dcc.Store(
            id='result_table',
            storage_type='memory',
            data=pdf.to_dict('records'),
        ),
        # Actual display of results
        html.Div(
            id='results_paginated'
        ),
    ]

    npages = int(np.ceil(len(pdf.index)/page_size))
    results_ += [
        dmc.Space(h=10),
        dmc.Group(
            dmc.Pagination(
                id='results_pagination',
                total=npages,
                siblings=1,
                withControls=True,
                withEdges=True,
            ),
            position='center',
            className='d-none' if npages == 1 else ''
        ),
        dmc.Space(h=20),
    ]

    return results_

@app.callback(
    Output('results_paginated', 'children'),
    Input('results_pagination', 'page'),
    State('results_store', 'data'),
    State('results_page_size_store', 'data'),
)
def on_paginate(page, data, page_size):
    pdf = pd.read_json(data)
    page_size = int(page_size)

    if not page:
        page = 1

    results = []

    # Slice to selected page
    pdf_ = pdf.iloc[(page-1)*page_size : min(page*page_size, len(pdf.index))]

    for i,row in pdf_.iterrows():
        results.append(card_search_result(row, i))

    return results

# Scroll to top on paginate
clientside_callback(
    """
    function scroll_top(value) {
        document.querySelector('#search_bar').scrollIntoView({behavior: "smooth"})
        return dash_clientside.no_update;
    }
    """,
    Output('results_pagination', 'page'), # Fake output!!!
    Input('results_pagination', 'page'),
    prevent_initial_call=True,
)

@app.callback(
    Output({'type': 'search_results_lightcurve', 'objectId': MATCH, 'index': MATCH}, 'children'),
    Input({'type': 'search_results_lightcurve', 'objectId': MATCH, 'index': MATCH}, 'id')
)
def on_load_lightcurve(lc_id):
    if lc_id:
        # print(lc_id['objectId'])
        fig = draw_lightcurve_preview(lc_id['objectId'])
        return dcc.Graph(
            figure=fig,
            config={'displayModeBar': False},
            style={
                'width': '100%',
                'height': '15pc'
            },
            responsive=True
        )

    return no_update

@app.callback(
    Output({'type': 'search_results_cutouts', 'objectId': MATCH, 'index': MATCH}, 'children'),
    Input({'type': 'search_results_cutouts', 'objectId': MATCH, 'index': MATCH}, 'id')
)
def on_load_cutouts(lc_id):
    if lc_id:
        return html.Div(
            draw_cutouts_quickview(lc_id['objectId']),
            style={'width': '12pc', 'height': '12pc'},
        )
        # figs = draw_cutouts_quickview(lc_id['objectId'], ['science', 'template', 'difference'])
        # return dbc.Row(
        #     [
        #         dbc.Col(_, xs=4, className='p-0') for _ in figs
        #     ],
        #     justify='center',
        #     className='p-0',
        # )

    return no_update

clientside_callback(
    """
    function drawer_switch(n_clicks, pathname) {
        const triggered = dash_clientside.callback_context.triggered.map(t => t.prop_id);
        if (triggered == 'drawer-button.n_clicks')
            return true;
        else
            return false;
    }
    """,
    Output("drawer", "opened"),
    Input("drawer-button", "n_clicks"),
    Input('url', 'pathname'),
    prevent_initial_call=True,
)

navbar = dmc.Header(
    id='navbar',
    height=55,
    fixed=True,
    zIndex=1000,
    p=0,
    m=0,
    className="shadow-sm",
    children=[
        dmc.Space(h=10),
        dmc.Container(
            fluid=True,
            children=dmc.Group(
                position="apart",
                align="flex-end",
                children=[
                    # Right menu
                    dmc.Group(
                        position="left",
                        align="flex-start",
                        children=[
                            # Burger
                            dmc.ActionIcon(
                                DashIconify(icon="dashicons:menu", width=30), id="drawer-button", n_clicks=0
                            ),
                            dmc.Anchor(
                                dmc.Group([
                                    dmc.ThemeIcon(
                                        DashIconify(
                                            icon="ion:search-outline",
                                            width=22,
                                        ),
                                        radius=30,
                                        size=32,
                                        variant="outline",
                                        color="gray",
                                    ),
                                    dmc.MediaQuery(
                                        "Search",
                                        smallerThan="sm",
                                        styles={"display": "none"},
                                    ),
                                ], spacing='xs'),
                                href='/',
                                variant='text',
                                style={"textTransform": "capitalize", "textDecoration": "none"},
                                color="gray",
                            ),
                            dmc.Anchor(
                                dmc.Group([
                                    dmc.ThemeIcon(
                                        DashIconify(
                                            icon="ion:cloud-download-outline",
                                            width=22,
                                        ),
                                        radius=30,
                                        size=32,
                                        variant="outline",
                                        color="gray",
                                    ),
                                    dmc.MediaQuery(
                                        "Data Transfer",
                                        smallerThan="sm",
                                        styles={"display": "none"},
                                    ),
                                ], spacing='xs'),
                                href='/download',
                                variant='text',
                                style={"textTransform": "capitalize", "textDecoration": "none"},
                                color="gray",
                            ),
                            dmc.Anchor(
                                dmc.Group([
                                    dmc.ThemeIcon(
                                        DashIconify(
                                            icon="ion:infinite-outline",
                                            width=22,
                                        ),
                                        radius=30,
                                        size=32,
                                        variant="outline",
                                        color="gray",
                                    ),
                                    dmc.MediaQuery(
                                        "Gravitational Waves",
                                        smallerThan="sm",
                                        styles={"display": "none"},
                                    ),
                                ], spacing='xs'),
                                href='/gw',
                                variant='text',
                                style={"textTransform": "capitalize", "textDecoration": "none"},
                                color="gray",
                            ),
                        ],
                    ),
                    # Left menu
                    dmc.Group(
                        position="right",
                        align="flex-end",
                        children=[
                            dmc.Anchor(
                                dmc.Group([
                                    dmc.ThemeIcon(
                                        DashIconify(
                                            icon="ion:stats-chart-outline",
                                            width=22,
                                        ),
                                        radius=30,
                                        size=32,
                                        variant="outline",
                                        color="gray",
                                    ),
                                    dmc.MediaQuery(
                                        "Statistics",
                                        smallerThan="sm",
                                        styles={"display": "none"},
                                    ),
                                ], spacing='xs'),
                                href='/stats',
                                variant='text',
                                style={"textTransform": "capitalize", "textDecoration": "none"},
                                color="gray",
                            ),
                        ]
                    ),
                    # Sidebar
                    dmc.Drawer(
                        children=[
                            dmc.Divider(
                                labelPosition="left",
                                label=[
                                    DashIconify(
                                        icon='tabler:search', width=15, style={"marginRight": 10}
                                    ),
                                    "Explore",
                                ],
                                style={"marginTop": 20, "marginBottom": 20},
                            ),
                            dmc.Stack(
                                [
                                    dmc.Anchor(
                                        'Search',
                                        style={"textTransform": "capitalize", "textDecoration": "none"},
                                        href='/',
                                        size="sm",
                                        color="gray",
                                    ),
                                    dmc.Anchor(
                                        'Data Transfer',
                                        style={"textTransform": "capitalize", "textDecoration": "none"},
                                        href='/download',
                                        size="sm",
                                        color="gray",
                                    ),
                                    dmc.Anchor(
                                        'Gravitational Waves',
                                        style={"textTransform": "capitalize", "textDecoration": "none"},
                                        href='/gw',
                                        size="sm",
                                        color="gray",
                                    ),
                                    dmc.Anchor(
                                        'Statistics',
                                        style={"textTransform": "capitalize", "textDecoration": "none"},
                                        href='/stats',
                                        size="sm",
                                        color="gray",
                                    ),
                                ],
                                align="left",
                                spacing="sm",
                                style={"paddingLeft": 30, "paddingRight": 20},
                            ),
                            dmc.Divider(
                                labelPosition="left",
                                label=[
                                    DashIconify(
                                        icon='carbon:api', width=15, style={"marginRight": 10}
                                    ),
                                    "Learn",
                                ],
                                style={"marginTop": 20, "marginBottom": 20},
                            ),
                            dmc.Stack(
                                [
                                    dmc.Anchor(
                                        '{ API }',
                                        style={"textTransform": "capitalize", "textDecoration": "none"},
                                        href='/api',
                                        size="sm",
                                        color="gray",
                                    ),
                                    dmc.Anchor(
                                        'Tutorials',
                                        style={"textTransform": "capitalize", "textDecoration": "none"},
                                        href='https://github.com/astrolabsoftware/fink-tutorials',
                                        size="sm",
                                        color="gray",
                                    ),
                                ],
                                align="left",
                                spacing="sm",
                                style={"paddingLeft": 30, "paddingRight": 20},
                            ),
                            dmc.Divider(
                                labelPosition="left",
                                label=[
                                    DashIconify(
                                        icon='tabler:external-link', width=15, style={"marginRight": 10}
                                    ),
                                    "External links",
                                ],
                                style={"marginTop": 20, "marginBottom": 20},
                            ),
                            dmc.Stack(
                                [
                                    dmc.Anchor(
                                        'Fink broker',
                                        style={"textTransform": "capitalize", "textDecoration": "none"},
                                        href='https://fink-broker.org',
                                        size="sm",
                                        color="gray",
                                    ),
                                    dmc.Anchor(
                                        'Portal bug tracker',
                                        style={"textTransform": "capitalize", "textDecoration": "none"},
                                        href='https://github.com/astrolabsoftware/fink-science-portal',
                                        size="sm",
                                        color="gray",
                                    )
                                ],
                                align="left",
                                spacing="sm",
                                style={"paddingLeft": 30, "paddingRight": 20},
                            ),
                        ],
                        title="Fink Science Portal",
                        id="drawer",
                        padding="md",
                        zIndex=1e7,
                        transition='pop-top-left',
                    ),
                    # dmc.ThemeSwitcher(
                    #     id="color-scheme-toggle",
                    #     style={"cursor": "pointer"},
                    # ),
                ],
            ),
        )
    ],
)

# embedding the navigation bar
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    navbar,
    html.Div(id='page-content', className='home', style={'padding-top': '55px'}),
])

@app.callback(
    Output('page-content', 'children'),
    [
        Input('url', 'pathname'),
        Input('url', 'search'),
    ]
)
def display_page(pathname, searchurl):
    layout = html.Div(
        [
            dbc.Container(
                [
                    # Logo shown by default
                    dbc.Collapse(
                        dmc.MediaQuery(
                            dbc.Row(
                                dbc.Col(
                                    html.Img(
                                        src="/assets/Fink_PrimaryLogo_WEB.png",
                                        height='100%',
                                        width='40%',
                                        style={'min-width': '250px'},
                                    )
                                ), style={'textAlign': 'center'}, className="mt-3",
                            ),
                            query="(max-height: 400px) or (max-width: 300px)",
                            styles={'display': 'none'},
                        ), is_open=True, id='logo',
                    ),
                    dbc.Row(
                        dbc.Col(
                            fink_search_bar,
                            lg={'size':8, 'offset':2},
                            md={'size':10, 'offset':1},
                        ), className="mt-3 mb-3"
                    ),
                ], fluid="lg"
            ),
            dbc.Container(id='results', fluid="xxl")
        ],
    )
    if pathname == '/about':
        return about.layout
    elif pathname == '/api':
        return api.layout()
    elif pathname == '/stats':
        return statistics.layout()
    elif pathname == '/download':
        return query_cluster.layout()
    elif pathname == '/gw':
        return gw.layout()
    elif pathname.startswith('/ZTF'):
        return summary.layout(pathname)
    else:
        if pathname[1:]:
            # check this is not a name generated by a user
            oid = retrieve_oid_from_metaname(pathname[1:])
            if oid is not None:
                return summary.layout('/' + oid)
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

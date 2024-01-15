# Copyright 2023 AstroLab Software
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
from dash import html, dcc, Input, Output, State, callback_context as ctx, no_update, dash_table
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import visdcc

import io
import gzip
import time
import pandas as pd
import healpy as hp
import numpy as np
from urllib.request import urlopen, URLError
from astropy.io import fits
from mocpy import MOC
import astropy_healpix as ah
import astropy.units as u

from app import app, APIURL
from apps.utils import markdownify_objectid, convert_jd, simbad_types, class_colors
from apps.utils import extract_bayestar_query_url
from apps.utils import request_api

def extract_moc(fn, credible_level):
    """
    """
    payload = urlopen(fn).read()
    with fits.open(io.BytesIO(payload)) as hdul:
        data = hdul[1].data
        header = hdul[1].header
        max_order = hdul[1].header["MOCORDER"]

    uniq = data["UNIQ"]
    probdensity = data["PROBDENSITY"]

    level, ipix = ah.uniq_to_level_ipix(uniq)
    area = ah.nside_to_pixel_area(ah.level_to_nside(level)).to_value(u.steradian)

    prob = probdensity * area


    cumul_to = np.linspace(0.5, 0.9, 5)[::-1]
    colors = ["blue", "green", "yellow", "orange", "red"]
    moc = MOC.from_valued_healpix_cells(uniq, prob, max_order, cumul_to=credible_level)

    return moc

def extract_skyfrac_degree(fn, credible_level):
    """
    """
    payload = urlopen(fn).read()
    with gzip.open(io.BytesIO(payload), 'rb') as f:
        with fits.open(io.BytesIO(f.read())) as hdul:
            data = hdul[1].data
            header = hdul[1].header

    hpx = data['PROB']
    if header['ORDERING'] == 'NESTED':
        hpx = hp.reorder(hpx, n2r=True)

    i = np.flipud(np.argsort(hpx))
    sorted_credible_levels = np.cumsum(hpx[i])
    credible_levels = np.empty_like(sorted_credible_levels)
    credible_levels[i] = sorted_credible_levels

    npix = len(hpx)
    nside = hp.npix2nside(npix)
    skyfrac = np.sum(credible_levels <= credible_level) * hp.nside2pixarea(nside, degrees=True)
    return skyfrac

@app.callback(
    Output("gw-data", "data"),
    [
        Input('gw-loading-button', 'n_clicks'),
        Input('credible_level', 'value'),
        Input('superevent_name', 'value'),
        Input('url', 'search'),
    ]
)
def query_bayestar(submit, credible_level, superevent_name, searchurl):
    """
    """
    if searchurl != '':
        credible_level, superevent_name = extract_bayestar_query_url(searchurl)
        empty_query = (superevent_name is None) or (superevent_name == '') or (credible_level is None) or (credible_level == '')
        if empty_query:
            raise PreventUpdate
    else:
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if button_id != "gw-loading-button":
            raise PreventUpdate

    if superevent_name == '':
        raise PreventUpdate

    # Query Fink
    fn = 'https://gracedb.ligo.org/api/superevents/{}/files/bayestar.fits.gz'.format(superevent_name)
    try:
        data = urlopen(fn).read()
    except URLError:
        return "error"

    r = request_api(
        '/api/v1/bayestar',
        json={
            'bayestar': str(data),
            'credible_level': float(credible_level),
            'output-format': 'json'
        }
    )

    pdf = pd.read_json(r)

    # return pdf.to_json(), "done"
    return pdf.to_json()

def populate_result_table_gw(data, columns):
    """ Define options of the results table, and add data and columns
    """
    page_size = 10
    markdown_options = {'link_target': '_blank'}

    table = dash_table.DataTable(
        data=data,
        columns=columns,
        id='result_table_gw',
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
        Output("gw-table", "children"),
        Output("card_explanation", "value"),
    ],
    [
        Input('gw-loading-button', 'n_clicks'),
        Input('gw-data', 'data'),
        Input('superevent_name', 'value'),
        Input('url', 'search'),
    ],
)
def show_table(nclick, gw_data, superevent_name, searchurl):
    """
    """
    if searchurl == '':
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if button_id != "gw-loading-button":
            raise PreventUpdate
    else:
        credible_level, superevent_name = extract_bayestar_query_url(searchurl)

    if gw_data == "":
        return dmc.Alert(
            "Enter a valid superevent name",
            title='Oops!',
            color="red",
            withCloseButton=True
        ), "info"

    if gw_data == "error":
        return dmc.Alert(
            "Could not find an event named {} on GraceDB".format(superevent_name),
            title='Oops!',
            color="red",
            withCloseButton=True
        ), "info"

    pdf = pd.read_json(gw_data)
    if pdf.empty:
        return dmc.Alert(
            "No counterparts found in Fink for the event named {}".format(superevent_name),
            title='Oops!',
            color="red",
            withCloseButton=True
        ), "info"
    else:
        colnames_to_display = {
            'i:objectId': 'objectId',
            'd:classification': 'Classification',
            'd:nalerthist': 'Number of measurements',
            'v:gw_lapse': 'Delay (day)',
        }
        pdf['v:gw_lapse'] = pdf['i:jdstarthist'] - pdf['v:jdstartgw']
        pdf['i:objectId'] = pdf['i:objectId'].apply(markdownify_objectid)
        data = pdf.sort_values('v:gw_lapse', ascending=True).to_dict('records')
        columns = [
            {
                'id': c,
                'name': colnames_to_display[c],
                'type': 'text',
                # 'hideable': True,
                'presentation': 'markdown',
            } for c in colnames_to_display.keys()
        ]

        table = populate_result_table_gw(data, columns)

        return table, None

def card_explanation():
    """ Explain what is used to fit for variable stars
    """
    msg = """
    Enter a superevent name on the left (check [O3](https://gracedb.ligo.org/superevents/public/O3/) or [O4](https://gracedb.ligo.org/superevents/public/O4/) runs if you are unsure),
    and enter a credible level. Note that the values in the resulting credible level map vary inversely with probability density: the most probable pixel is
    assigned to the credible level 0.0, and the least likely pixel is assigned the credible level 1.0.

    The alerts falling into the sky map are shown in the table, with the following columns:
    - objectId: ZTF object ID.
    - Classification: tag according to Fink, at the time of the match.
    - Number of measurements: Number of available measurements, at the time of the match.
    - Delay: time delay in days between the GW trigger time `t0` and the first alert emission time (`jdstarthist`).

    Note that only alerts that started varying within the time boundaries `[t0 - 1 day, t0 + 6 days]` are considered,
    where `t0` is the GW trigger time.

    Finally we provide a visualisation of the alerts on the sky using Aladin Lite,
    along with a Multi-Ordered Coverage ([MOC](https://arxiv.org/abs/2201.05191)) of the GW event.
    """
    card = dmc.Accordion(
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Information",
                        icon=[
                            DashIconify(
                                icon="tabler:help-hexagon",
                                color="#3C8DFF",
                                width=20,
                            )
                        ],
                    ),
                    dmc.AccordionPanel(dcc.Markdown(msg, link_target="_blank")),
                ],
                value="info"
            ),
        ],
        value="info",
        id="card_explanation"
    )
    return card

@app.callback(
    [
        Output('aladin-lite-div-skymap-gw', 'run'),
        Output('container_skymap', 'style'),
        Output("progress_bar", "style")
    ],
    [
        Input('gw-loading-button', 'n_clicks'),
        Input('gw-data', 'data'),
        Input('credible_level', 'value'),
        Input('superevent_name', 'value'),
        Input('url', 'search'),
    ],
)
def display_skymap_gw(nclick, gw_data, credible_level, superevent_name, searchurl):
    """ Display explorer result on a sky map (Aladin lite).

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
    if searchurl == '':
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if button_id != "gw-loading-button":
            raise PreventUpdate
    else:
        credible_level, superevent_name = extract_bayestar_query_url(searchurl)

    if gw_data == "":
        raise PreventUpdate

    if gw_data == "error":
        raise PreventUpdate

    hide_progress = {'display': 'none', 'width': '100%', 'height': '5pc'}

    pdf = pd.read_json(gw_data)
    if len(pdf) > 0:
        pdf['v:lastdate'] = convert_jd(pdf['i:jd'])
        pdf['i:objectId'] = pdf['i:objectId'].apply(markdownify_objectid)
        # Coordinate of the first alert
        ra0 = pdf['i:ra'].values[0]
        dec0 = pdf['i:dec'].values[0]

        # Javascript. Note the use {{}} for dictionary
        # Force redraw of the Aladin lite window
        img = """var container = document.getElementById('aladin-lite-div-skymap-gw');var txt = ''; container.innerHTML = txt;"""

        # Aladin lite
        img += """var a = A.aladin('#aladin-lite-div-skymap-gw', {{target: '{} {}', survey: 'P/PanSTARRS/DR1/color/z/zg/g', showReticle: true, allowFullZoomout: true, fov: 360}});""".format(ra0, dec0)

        ras = pdf['i:ra'].values
        decs = pdf['i:dec'].values
        filts = pdf['i:fid'].values
        filts_dic = {1: 'g', 2: 'r'}
        times = pdf['v:lastdate'].values
        link = '<a target="_blank" href="{}/{}">{}</a>'
        titles = [link.format(APIURL, i.split(']')[0].split('[')[1], i.split(']')[0].split('[')[1]) for i in pdf['i:objectId'].values]
        # mags = pdf['i:magpsf'].values
        classes = pdf['d:classification'].values
        n_alert_per_class = pdf.groupby('d:classification').count().to_dict()['i:objectId']
        cats = []
        for ra, dec, fid, time_, title, class_ in zip(ras, decs, filts, times, titles, classes):
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
            img += """{}.addSources([A.source({}, {}, {{objectId: '{}', filter: '{}', time: '{}', Classification: '{}'}})]);""".format(cat, ra, dec, title, filts_dic[fid], time_, class_)

        for cat in sorted(cats):
            img += """a.addCatalog({});""".format(cat)

        fn = 'https://gracedb.ligo.org/api/superevents/{}/files/bayestar.multiorder.fits'.format(superevent_name)
        mm = extract_moc(fn, credible_level)
        img += """var json = {};""".format(mm.to_string(format='json'))
        img += """var moc = A.MOCFromJSON(json, {opacity: 0.25, color: 'white', lineWidth: 1}); a.addMOC(moc);"""

        # img cannot be executed directly because of formatting
        # We split line-by-line and remove comments
        img_to_show = [i for i in img.split('\n') if '// ' not in i]

        return " ".join(img_to_show), {'width': '100%', 'height': '25pc'}, hide_progress
    else:
        return "", {'display': 'none'}, hide_progress

def display_skymap_gw():
    """ Display the sky map in the explorer tab results (Aladin lite)

    It uses `visdcc` to execute javascript directly.

    Returns
    ---------
    out: list of objects
    """
    return dbc.Container(
        html.Div(
            [
                visdcc.Run_js(id='aladin-lite-div-skymap-gw'),
            ],
            id='container_skymap',
            style={'display': 'none'}
        )
    )

@app.callback(
    output=Output("gw-trigger", "children"),
    inputs=[
        Input("gw-loading-button", "n_clicks"),
        Input('url', 'search'),
    ],
    running=[
        (
            Output("progress_bar", "style"),
            {"visibility": "visible", 'width': '100%', 'height': '5pc'},
            {'display': 'none', 'width': '100%', 'height': '5pc'},
        ),
    ],
    progress=[
        Output("progress_bar", "value"),
        Output("progress_bar", "max")
    ],
    state=[
        State("superevent_name", 'value'),
        State('credible_level', 'value')
    ],
    background=True,
)
def callback_progress_bar(set_progress, n_clicks, searchurl, superevent_name, credible_level):
    if searchurl == '':
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if button_id != "gw-loading-button":
            raise PreventUpdate
    else:
        credible_level, superevent_name = extract_bayestar_query_url(searchurl)

    fn = 'https://gracedb.ligo.org/api/superevents/{}/files/bayestar.fits.gz'.format(superevent_name)
    try:
        total = extract_skyfrac_degree(fn, credible_level)
    except URLError:
        return "Error"

    rate = 0.15 # second/deg2
    for i in range(int(total)):
        time.sleep(rate)
        set_progress((str(i + 1), str(int(total))))
    return "Loaded!"

def layout():
    """ Layout for the GW counterpart search
    """
    description = [
        "Enter an event name from the ",
        dmc.Anchor("O3", href="https://gracedb.ligo.org/superevents/public/O3/", size="xs", target="_blank"),
        " or ",
        dmc.Anchor("O4", href="https://gracedb.ligo.org/superevents/public/O4/", size="xs", target="_blank"),
        " runs (e.g. S230709bi)."
    ]
    supervent_name = html.Div(
        [
            dmc.Space(h=10),
            dmc.Divider(variant="solid", label='Superevent'),
            dmc.Space(h=10),
            dmc.TextInput(
                id="superevent_name",
                label=None,
                description=description,
                placeholder="e.g. S230709bi",
            ),
        ], id='superevent_name_selector',
        className='mb-2'
    )

    credible_level = html.Div(
        [
            dmc.Space(h=10),
            dmc.Divider(variant="solid", label='Credible level'),
            dmc.Space(h=10),
            dmc.NumberInput(
                label=None,
                description="From 0 (most likely) to 1 (least likely)",
                value=0.2,
                precision=2,
                min=0.0,
                max=1.0,
                step=0.05,
                id='credible_level'
            ),
        ], id='credible_level_selector',
        className='mb-4'
    )

    submit_gw = dmc.Center(
        [
            dmc.Button(
                "Search for alerts matching",
                id="gw-loading-button",
                leftIcon=DashIconify(icon="fluent:database-plug-connected-20-filled"),
                loaderProps={'variant': 'dots', 'color': 'orange'},
                variant="outline",
                color='indigo'
            ),
        ],
        className='mb-4'
    )

    title_div = dbc.Row(
        children=[
            dmc.Space(h=20),
            dmc.Stack(
                children=[
                    dmc.Title(
                        children='Gravitational Waves',
                        style={'color': '#15284F'},
                            order=2
                    ),
                ],
                align="center",
                justify="center",
            ),
            dbc.Alert(
                dcc.Markdown("This service is still experimental. Open an issue on [GH](https://github.com/astrolabsoftware/fink-science-portal/issues) if you experience problems or if you have suggestions.", link_target="_blank"),
                dismissable=True,
                is_open=True,
                color="light",
                className="d-none d-md-block"
            )
        ]
    )

    layout_ = dbc.Container(
        [
            title_div,
            dbc.Row(
                [
                    dbc.Col(
                        [
                            supervent_name,
                            credible_level,
                            submit_gw,
                            html.Div(id="gw-trigger", style={'display': 'none'}),
                            dcc.Store(data='', id='gw-data'),
                        ], md=3,
                        # className="d-none d-md-block"
                    ),
                    dbc.Col(
                        [
                            dmc.Space(h=10),
                            html.Progress(id="progress_bar", style={'display': 'none', 'width': '100%', 'height': '5pc'}),
                            display_skymap_gw(),
                            dmc.Space(h=10),
                            dmc.Paper(
                                [
                                    html.Div(id='gw-table'),
                                    card_explanation()
                                ]
                            ),
                        ], md=9
                    ),
                ],
                justify="around", className="g-2"
            ),
            html.Br()
        ], fluid='lg'
    )

    # Wrap it to re-define the background
    layout_ = html.Div(
        layout_,
        className="bg-opaque-90"
    )

    return layout_

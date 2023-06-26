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
import requests
import pandas as pd
import healpy as hp
import numpy as np
from urllib.request import urlopen, URLError
from astropy.io import fits

from app import app, APIURL
from apps.utils import markdownify_objectid, convert_jd, simbad_types, class_colors

def extract_skyfrac_degree(fn):
    """
    """
    with gzip.open(fn, 'rb') as f:
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
    ],
    prevent_initial_call=True
)
def query_bayestar(submit, credible_level, superevent_name):
    """
    """
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

    r = requests.post(
        '{}/api/v1/bayestar'.format(APIURL),
        json={
            'bayestar': str(data),
            'credible_level': float(credible_level),
            'output-format': 'json'
        }
    )

    pdf = pd.read_json(io.BytesIO(r.content))

    # return pdf.to_json(), "done"
    return pdf.to_json()

def populate_result_table_gw(data, columns, is_mobile):
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
        Output("gw-loading-button", "children"),
    ],
    [
        Input('gw-loading-button', 'n_clicks'),
        Input('gw-data', 'data'),
        Input('superevent_name', 'value'),
    ],
    prevent_initial_call=True
)
def show_table(nclick, gw_data, superevent_name):
    """
    """
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if button_id != "gw-loading-button":
        raise PreventUpdate

    if gw_data == "":
        return dmc.Alert(
            "Enter a valid superevent name",
            title='Oops!',
            color="red",
            withCloseButton=True
        ), no_update

    if gw_data == "error":
        return dmc.Alert(
            "Could not find an event named {} on GraceDB".format(superevent_name),
            title='Oops!',
            color="red",
            withCloseButton=True
        ), no_update

    pdf = pd.read_json(gw_data)
    if pdf.empty:
        return dmc.Alert(
            "No counterparts found in Fink for the event named {}".format(superevent_name),
            title='Oops!',
            color="red",
            withCloseButton=True
        ), no_update
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

        table = populate_result_table_gw(data, columns, is_mobile=False)

        return table, no_update

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
    """
    card = dmc.Accordion(
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl("Information"),
                    dmc.AccordionPanel(dcc.Markdown(msg)),
                ],
                value="info"
            ),
        ]
    )
    return card

@app.callback(
    [
        Output('aladin-lite-div-skymap-gw', 'run'),
        Output('container_skymap', 'style')
    ],
    [
        Input('gw-loading-button', 'n_clicks'),
        Input('gw-data', 'data'),
    ],
)
def display_skymap_gw(nclick, gw_data):
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
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if button_id != "gw-loading-button":
        raise PreventUpdate

    if gw_data == "":
        raise PreventUpdate

    if gw_data == "error":
        raise PreventUpdate

    pdf = pd.read_json(gw_data)
    pdf['v:lastdate'] = pdf['i:jd'].apply(convert_jd)
    pdf['i:objectId'] = pdf['i:objectId'].apply(markdownify_objectid)
    if len(pdf) > 0:
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

        # img cannot be executed directly because of formatting
        # We split line-by-line and remove comments
        img_to_show = [i for i in img.split('\n') if '// ' not in i]

        return " ".join(img_to_show), {'width': '100%', 'height': '25pc'}
    else:
        return "", {'display': 'none'}

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

@app.long_callback(
    output=Output("gw-trigger", "children"),
    inputs=[
        Input("gw-loading-button", "n_clicks"),
    ],
    running=[
        (Output("gw-loading-button", "disabled"), True, False),
        (
            Output("progress_bar", "style"),
            {"visibility": "visible", 'width': '100%', 'height': '5pc'},
            {"visibility": "hidden", 'width': '100%', 'height': '5pc'},
        ),
    ],
    progress=[Output("progress_bar", "value"), Output("progress_bar", "max")],
    states=State("superevent_name", 'value'),
    prevent_initial_call=True
)
def callback_progress_bar(set_progress, n_clicks, superevent_name):
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if button_id != "gw-loading-button":
        raise PreventUpdate

    fn = 'https://gracedb.ligo.org/api/superevents/{}/files/bayestar.fits.gz'.format(superevent_name)
    total = extract_skyfrac_degree(fn)
    rate = 0.5 # second/deg2
    for i in range(int(total)):
        time.sleep(rate)
        set_progress((str(i + 1), str(int(total))))
    return "Loaded!"

def layout(is_mobile):
    """ Layout for the GW counterpart search
    """
    description = [
        "Enter an event ID from the ",
        dmc.Anchor("O3", href="https://gracedb.ligo.org/superevents/public/O3/", size="xs", target="_blank"),
        " or ",
        dmc.Anchor("O4", href="https://gracedb.ligo.org/superevents/public/O4/", size="xs", target="_blank"),
        " runs."
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
                placeholder="e.g. S200219ac",
            ),
        ], id='superevent_name_selector'
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
        ], id='credible_level_selector'
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
        ]
    )

    if is_mobile:
        # width_right = 10
        # title = dbc.Row(
        #     children=[
        #         dmc.Space(h=20),
        #         dmc.Stack(
        #             children=[
        #                 dmc.Title(
        #                     children='Fink Data Transfer',
        #                     style={'color': '#15284F'}
        #                 ),
        #                 dmc.Anchor(
        #                     dmc.ActionIcon(
        #                         DashIconify(icon="fluent:question-16-regular", width=20),
        #                         size=30,
        #                         radius="xl",
        #                         variant="light",
        #                         color='orange',
        #                     ),
        #                     href="https://fink-broker.org/2023-01-17-data-transfer",
        #                     target="_blank"
        #                 ),
        #             ],
        #             align="center",
        #             justify="center",
        #         )
        #     ]
        # )
        # left_side = html.Div(id='timeline_data_transfer', style={'display': 'none'})
        # style = {
        #     'background-image': 'linear-gradient(rgba(255,255,255,0.3), rgba(255,255,255,0.3)), url(/assets/background.png)'
        # }
        pass
    else:
        width_right = 8
        title = html.Div()
        left_side = dbc.Col(
            [
                html.Br(),
                html.Br(),
                supervent_name,
                html.Br(),
                credible_level,
                html.Br(),
                html.Br(),
                submit_gw,
                html.Div(id="gw-trigger", style={'display': 'none'}),
                dcc.Store(data='', id='gw-data'),
                # dcc.Store(id='request-status', data='')
            ], width={"size": 3},
        )
        style={
            'background-image': 'linear-gradient(rgba(255,255,255,0.3), rgba(255,255,255,0.3)), url(/assets/background.png)',
            'background-size': 'cover'
        }

    layout_ = html.Div(
        [
            html.Br(),
            html.Br(),
            title,
            dbc.Row(
                [
                    left_side,
                    dbc.Col(
                        [
                            html.Progress(id="progress_bar", style={"visibility": "hidden", 'width': '100%', 'height': '5pc'}),
                            display_skymap_gw(),
                            dmc.Space(h=10),
                            dmc.Paper(
                                [
                                    html.Div(id='gw-table'),
                                    card_explanation()
                                ], radius='xl', p='md', shadow='xl', withBorder=True
                            ),
                        ], width=width_right
                    ),
                ],
                justify="around", className="g-0"
            ),
            html.Br()
        ], className='home', style={'background-image': 'linear-gradient(rgba(255,255,255,0.9), rgba(255,255,255,0.9)), url(/assets/background.png)', 'background-size': 'cover'}
    )

    return layout_
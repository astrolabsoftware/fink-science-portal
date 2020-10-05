# Copyright 2020 AstroLab Software
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
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import visdcc

from app import app, client

from apps.cards import card_lightcurve, card_cutouts
from apps.cards import card_id, card_fink_added_values

dcc.Location(id='url', refresh=False)

def tab1_content(data):
    tab1_content_ = html.Div([
        dbc.Row([
            dbc.Col(card_cutouts(data), width=8),
            dbc.Col([card_id(data)], width=4, align='center')
        ]),
        dbc.Row([
            dbc.Col(card_lightcurve(data), width=8),
            dbc.Col([card_fink_added_values(data)], width=4, align='center')
        ]),
    ])
    return tab1_content_

tab2_content = dbc.Card(
    dbc.CardBody(
        [
            html.P("This is tab 2!", className="card-text"),
            dbc.Button("Don't click here", color="danger"),
        ]
    ),
    className="mt-3",
)

def tabs(data):
    tabs_ = dbc.Tabs(
        [
            dbc.Tab(tab1_content(data), label="Summary", tab_style={"margin-left": "auto"}),
            dbc.Tab(tab2_content, label="Supernova", disabled=True),
            dbc.Tab(label="Microlensing", disabled=True),
            dbc.Tab(label="Variable stars", disabled=True),
            dbc.Tab(label="Solar System", disabled=True),
        ]
    )
    return tabs_

def title(name):
    title_ = dbc.Card(
        dbc.CardHeader(
            [
                dbc.Row([
                    html.Img(src="/assets/Fink_SecondaryLogo_WEB.png", height='20%', width='20%'),
                    html.H1(children='{}'.format(name[1:]), id='name', style={'color': '#15284F'})
                ])
            ]
        ),
    )
    return title_

def layout(name):
    # even if there is one object ID, this returns  several alerts
    results = client.scan("", "key:key:{}".format(name[1:]), None, 0, True, True)

    layout_ = html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        [
                            title(name),
                            html.Br(),
                            html.Div(
                                [visdcc.Run_js(id='aladin-lite-div')],
                                style={
                                    'width': '100%',
                                    'height': '30pc'
                                }
                            )
                        ], width={"size": 3},
                    ),
                    dbc.Col(tabs(results), width=8)
                ],
                justify="around", no_gutters=True
            )
        ]
    )

    return layout_

@app.callback(
    Output('aladin-lite-div', 'run'), Input('url', 'pathname'))
def integrate_aladin_lite(name):
    """ Integrate aladin light in the 2nd Tab of the dashboard.

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
    default_img = ""
    if name:
        results = client.scan("", "key:key:{}".format(name[1:]), None, 0, True, True)
        pdf = extract_properties(results, ['i:jd', 'i:ra', 'i:dec'])
        pdf = pdf.sort_values('i:jd', ascending=False)

        # Coordinate of the current alert
        ra0 = pdf['i:ra'].values[0]
        dec0 = pdf['i:dec'].values[0]

        # Javascript. Note the use {{}} for dictionary
        img = """
        var aladin = A.aladin('#aladin-lite-div',
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

    return default_img

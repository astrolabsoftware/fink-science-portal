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
import dash_bootstrap_components as dbc

from apps.utils import convert_jd, extract_properties
from apps.plotting import draw_cutout, extract_latest_cutouts
from apps.plotting import draw_lightcurve, draw_scores

import numpy as np

def card_lightcurve(data) -> dbc.Card:
    """ Card containing the lightcurve object

    Parameters
    ----------
    data: java.util.TreeMap
        Results from a HBase client query

    Returns
    ----------
    card: dbc.Card
        Card with the lightcurve drawn inside
    """
    graph = dcc.Graph(
        id='lightcurve',
        figure=draw_lightcurve(data),
        style={
            'width': '100%',
            'height': '15pc'
        },
        config={'displayModeBar': False}
    )
    card = dbc.Card(
        dbc.CardBody(
            [
                graph
            ]
        ),
        className="mt-3"
    )
    return card

def card_sn_scores(data) -> dbc.Card:
    """ Card containing the score evolution

    Parameters
    ----------
    data: java.util.TreeMap
        Results from a HBase client query

    Returns
    ----------
    card: dbc.Card
        Card with the scores drawn inside
    """
    graph = dcc.Graph(
        id='scores',
        figure=draw_scores(data),
        style={
            'width': '100%',
            'height': '15pc'
        },
        config={'displayModeBar': False}
    )
    card = dbc.Card(
        dbc.CardBody(
            [
                graph
            ]
        ),
        className="mt-3"
    )
    return card

def card_cutouts(data):
    """ Add a card containing cutouts

    Parameters
    ----------
    science: np.array
        2D array containing science data
    template: np.array
        2D array containing template data
    difference: np.array
        2D array containing difference data

    Returns
    ----------
    card: dbc.Card
        Card with the cutouts drawn inside
    """
    science, template, difference = extract_latest_cutouts(data)
    card = dbc.Card(
        dbc.CardBody(
            [
                dbc.Row([
                    dbc.Col(html.H5(children="Science", className="text-center")),
                    dbc.Col(html.H5(children="Template", className="text-center")),
                    dbc.Col(html.H5(children="Difference", className="text-center"))
                ]),
                dbc.Row([
                    dcc.Graph(
                        id='science-stamps',
                        figure=draw_cutout(science, 'science'),
                        style={
                            'display': 'inline-block',
                        },
                        config={'displayModeBar': False}
                    ),
                    dcc.Graph(
                        id='template-stamps',
                        figure=draw_cutout(template, 'template'),
                        style={
                            'display': 'inline-block',
                        },
                        config={'displayModeBar': False}
                    ),
                    dcc.Graph(
                        id='difference-stamps',
                        figure=draw_cutout(difference, 'difference'),
                        style={
                            'display': 'inline-block',
                        },
                        config={'displayModeBar': False}
                    ),
                ], justify='around', no_gutters=True)
            ]
        ),
        className="mt-3"
    )
    return card

def card_id(data):
    """ Add a card containing basic alert data
    """
    pdf = extract_properties(
        data, ['i:objectId', 'i:candid', 'i:jd', 'i:ra', 'i:dec'])
    pdf = pdf.sort_values('i:jd', ascending=False)

    id0 = pdf['i:objectId'].values[0]
    candid0 = pdf['i:candid'].values[0]
    ra0 = pdf['i:ra'].values[0]
    dec0 = pdf['i:dec'].values[0]
    date0 = convert_jd(float(pdf['i:jd'].values[0]))

    card = dbc.Card(
        [
            html.H5("ObjectID: {}".format(id0), className="card-title"),
            html.H6("Candid: {}".format(candid0), className="card-subtitle"),
            dcc.Markdown(
                """
                ---
                ```
                Date: {}
                RA: {} deg
                Dec: {} deg
                ```
                """.format(date0, ra0, dec0)
            )
        ],
        className="mt-3", body=True
    )
    return card

def card_sn_properties(data):
    """ Add a card containing SN alert data
    """
    pdf = extract_properties(
        data, [
            'i:objectId',
            'i:candid',
            'i:jd',
            'd:snn_snia_vs_nonia',
            'd:snn_sn_vs_all',
            'd:rfscore'
        ]
    )
    pdf = pdf.sort_values('i:jd', ascending=False)

    id0 = pdf['i:objectId'].values[0]
    candid0 = pdf['i:candid'].values[0]
    snn_snia_vs_nonia = pdf['d:snn_snia_vs_nonia'].values[0]
    snn_sn_vs_all = pdf['d:snn_sn_vs_all'].values[0]
    rfscore = pdf['d:rfscore'].values[0]

    card = dbc.Card(
        [
            html.H5("ObjectID: {}".format(id0), className="card-title"),
            html.H6("Candid: {}".format(candid0), className="card-subtitle"),
            dcc.Markdown(
                """
                ---
                ```
                [SNN] SN Ia score: {:.2f}
                [SNN] SNe score: {:.2f}
                RF score: {:.2f}
                ```
                """.format(
                    float(snn_snia_vs_nonia),
                    float(snn_sn_vs_all),
                    float(rfscore))
            )
        ],
        className="mt-3", body=True
    )
    return card

def card_fink_added_values(data):
    pdf = extract_properties(
        data,
        [
            'i:jd',
            'd:cdsxmatch',
            'd:mulens_class_1',
            'd:mulens_class_2',
            'd:nalerthist',
            'd:rfscore',
            'd:roid',
            'd:snn_sn_vs_all',
            'd:snn_snia_vs_nonia'
        ]
    )
    pdf = pdf.sort_values('i:jd', ascending=False)

    out = "---\n"
    out += "``` \n"
    for index, colname in enumerate(pdf.columns):
        if colname == 'i:jd':
            continue
        if 'snn_' in colname:
            value = np.round(float(pdf[colname].values[0]), 3)
        else:
            value = pdf[colname].values[0]

        out += "{}: {}\n".format(colname[2:], value)

    out += "```"
    card = dbc.Card(
        [

            html.H5("Fink added values", className="card-subtitle"),
            dcc.Markdown(out)
        ],
        className="mt-3", body=True
    )
    return card

def card_external_sn_data(data):
    pdf = extract_properties(
        data, ['i:objectId', 'i:jd', 'i:ra', 'i:dec'])
    pdf = pdf.sort_values('i:jd', ascending=False)

    id0 = pdf['i:objectId'].values[0]
    ra0 = pdf['i:ra'].values[0]
    dec0 = pdf['i:dec'].values[0]
    card = dbc.Card(
        [

            html.H5("External data", className="card-subtitle"),
            dbc.Row([
                dbc.Button('TNS', id='TNS', href='https://wis-tns.weizmann.ac.il/search?ra={}&decl={}&radius=5&coords_unit=arcsec'.format(ra0, dec0)),
                dbc.Button('SIMBAD', id='SIMBAD', href="http://simbad.u-strasbg.fr/simbad/sim-coo?Coord={}%20{}&Radius=0.08".format(ra0, dec0)),
            ])
        ],
        className="mt-3", body=True
    )
    return card

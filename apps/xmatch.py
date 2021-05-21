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
import base64
import io
import csv
import dash
from dash.dependencies import Input, Output, State
import dash_core_components as dcc
import dash_html_components as html
import dash_table
import dash_bootstrap_components as dbc

import pandas as pd
import healpy as hp
import numpy as np

import astropy.units as u
from astropy.coordinates import SkyCoord

from app import app
from app import clientP

from apps.utils import extract_fink_classification
from apps.utils import markdownify_objectid
from apps.utils import convert_jd
from apps.utils import get_superpixels
from apps.cards import card_explanation_xmatch

layout = html.Div(
    [
        html.Br(),
        html.Br(),
        html.Br(),
        dbc.Container(
            [
                dbc.Row([
                    dbc.Col([
                        card_explanation_xmatch(),
                        dcc.Upload(
                            id='datatable-upload',
                            children=html.Div([
                                'Drag and Drop or ',
                                html.A('Select Files')
                            ]),
                            max_size=5 * 1024 * 1024, # 5MB max
                            style={
                                'width': '100%', 'height': '60px', 'lineHeight': '60px',
                                'borderWidth': '1px', 'borderStyle': 'dashed',
                                'borderRadius': '5px', 'textAlign': 'center', 'margin': '10px'
                            },
                        ),
                        html.H6(id='xmatch-message'),
                        dash_table.DataTable(
                            id='datatable-upload-container',
                            page_size=10,
                            style_as_list_view=True,
                            sort_action="native",
                            filter_action="native",
                            markdown_options={'link_target': '_blank'},
                            style_data={
                                'backgroundColor': 'rgb(248, 248, 248, .7)'
                            },
                            style_cell={'padding': '5px', 'textAlign': 'center'},
                            style_data_conditional=[
                                {
                                    'if': {'row_index': 'odd'},
                                    'backgroundColor': 'rgb(248, 248, 248, .7)'
                                }
                            ],
                            style_header={
                                'backgroundColor': 'rgb(230, 230, 230)',
                                'fontWeight': 'bold'
                            },
                            export_format='csv',
                            export_headers='display'
                        )],
                    )
                ])
            ]
        )
    ],
    className='home',
    style={
        'background-image': 'linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(/assets/background.png)',
        'background-size': 'contain'
    }
)


def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        if 'csv' in filename:
            # Assume that the user uploaded a CSV file
            return pd.read_csv(
                io.StringIO(decoded.decode('utf-8')))
        elif 'xls' in filename:
            # Assume that the user uploaded an excel file
            return pd.read_excel(io.BytesIO(decoded))
    except Exception as e:
        print(e)
        return html.Div([
            'There was an error processing this file.'
        ])


@app.callback(
    [
        Output('datatable-upload-container', 'data'),
        Output('datatable-upload-container', 'columns'),
        Output('xmatch-message', 'children'),
    ],
    [
        Input('datatable-upload', 'contents'),
    ],
    State('datatable-upload', 'filename')
)
def update_output(contents, filename):
    if contents is None:
        return [{}], [], ""
    df = parse_contents(contents, filename)
    nrow = len(df)
    if nrow > 1000:
        df = df.head(1000)

    # Columns of interest
    colnames = [
        'i:objectId', 'i:ra', 'i:dec', 'i:jd', 'd:cdsxmatch', 'i:ndethist'
    ]

    colnames_added_values = [
        'd:cdsxmatch',
        'd:roid',
        'd:mulens_class_1',
        'd:mulens_class_2',
        'd:snn_snia_vs_nonia',
        'd:snn_sn_vs_all',
        'd:rfscore',
        'i:ndethist',
        'i:drb',
        'i:classtar',
        'd:knscore',
        'i:jdstarthist'
    ]

    # Column name to display
    colnames_to_display = [
        'objectId', 'RA', 'Dec', 'last seen', 'classification', 'ndethist'
    ]

    unique_cols = np.unique(colnames + colnames_added_values).tolist()

    # Types of columns
    dtypes_ = [
        np.str, np.float, np.float, np.float, np.str, np.int
    ]
    dtypes = {i: j for i, j in zip(colnames, dtypes_)}

    raname = [i for i in df.columns if i in ['i:ra', 'RA', 'ra', 'Ra']][0]
    decname = [i for i in df.columns if i in ['i:dec', 'DEC', 'dec', 'Dec']][0]
    idname = [i for i in df.columns if i in ['ID', 'id', 'Name', 'name', 'NAME']][0]
    # extract ra/dec
    ra0 = df[raname].values[0]
    if 'h' in str(ra0):
        coords = [
            SkyCoord(ra, dec, frame='icrs')
            for ra, dec in zip(df[raname].values, df[decname].values)
        ]
    elif ':' in str(ra0) or ' ' in str(ra0):
        coords = [
            SkyCoord(ra, dec, frame='icrs', unit=(u.hourangle, u.deg))
            for ra, dec in zip(df[raname].values, df[decname].values)
        ]
    else:
        coords = [
            SkyCoord(ra, dec, frame='icrs', unit='deg')
            for ra, dec in zip(df[raname].values, df[decname].values)
        ]
    ras = [coord.ra.deg for coord in coords]
    decs = [coord.dec.deg for coord in coords]
    ids = df[idname].values

    radius_deg = 1.5 / 3600.

    # loop over rows
    #clientP.setLimit(10)
    count = 0
    pdfs = pd.DataFrame(columns=unique_cols + [idname])
    for oid, ra, dec, coord in zip(ids, ras, decs, coords):
        # vec = hp.ang2vec(
        #     np.pi / 2.0 - np.pi / 180.0 * dec,
        #     np.pi / 180.0 * ra
        # )
        # pixs = hp.query_disc(
        #     131072,
        #     vec,
        #     np.pi / 180 * radius / 3600.,
        #     inclusive=True
        # )
        #
        # to_search = ",".join(['key:key:{}'.format(i) for i in pixs])
        #
        # results = clientP.scan(
        #     "",
        #     to_search,
        #     ",".join(unique_cols),
        #     0, True, True
        # )

        # angle to vec conversion
        vec = hp.ang2vec(np.pi / 2.0 - np.pi / 180.0 * dec, np.pi / 180.0 * ra)

        # Send request
        if int(radius) <= 30:
            # arcsecond scale
            # get arcmin scale pixels
            pixs_arcsec = hp.query_disc(
                131072,
                vec,
                np.pi / 180 * radius_deg,
                inclusive=True
            )
            pixs_am = get_superpixels(pixs_arcsec, 131072, 4096)
            pixs_degree = get_superpixels(pixs_arcsec, 131072, 128)

            # For each pixel, get its superpixel
            pixs = [
                '{}_{}_{}'.format(
                    p[0],
                    p[1],
                    p[2]
                ) for p in zip(pixs_degree, pixs_am, pixs_arcsec)
            ]
            to_evaluate = ",".join(
                [
                    'key:key:{}'.format(i) for i in pixs
                ]
            )
        elif (int(radius) > 30) & (int(radius) <= 1800):
            # arcmin scale
            # get arcmin scale pixels
            pixs_am = hp.query_disc(
                4096,
                vec,
                np.pi / 180 * radius_deg,
                inclusive=True
            )
            pixs_degree = get_superpixels(pixs_am, 4096, 128)

            # For each pixel, get its superpixel
            pixs = [
                '{}_{}'.format(
                    p[0],
                    p[1]
                ) for p in zip(pixs_degree, pixs_am)
            ]
            to_evaluate = ",".join(
                [
                    'key:key:{}'.format(i) for i in pixs
                ]
            )
        else:
            # degree scale
            pixs = hp.query_disc(
                128,
                vec,
                np.pi / 180 * radius_deg,
                inclusive=True
            )
            to_evaluate = ",".join(
                [
                    'key:key:{}'.format(i) for i in pixs
                ]
            )
        results = clientP.scan(
            "",
            to_evaluate,
            "*",
            0, True, True
        )

        # Loop over results and construct the dataframe
        if not results.isEmpty():
            pdf = pd.DataFrame.from_dict(results, orient='index')[unique_cols]
            pdf[idname] = [oid] * len(pdf)
            if 'd:knscore' not in pdf.columns:
                pdf['d:knscore'] = np.zeros(len(pdf), dtype=float)

            sep = coord.separation(
                SkyCoord(
                    pdf['i:ra'],
                    pdf['i:dec'],
                    unit='deg'
                )
            ).deg

            pdf['v:separation_degree'] = sep
            pdf = pdf.sort_values('v:separation_degree', ascending=True)

            pdfs = pd.concat((pdfs, pdf), ignore_index=True)

    if pdfs.empty:
        columns = [
            {
                'id': c,
                'name': c,
                'type': 'text',
                'presentation': 'markdown'
            } for c in df.columns
        ]
        data = pd.DataFrame(columns=df.columns).to_dict('records')
        return data, columns, "No match for {}".format(filename)

    # Fink final classification
    classifications = extract_fink_classification(
        pdfs['d:cdsxmatch'],
        pdfs['d:roid'],
        pdfs['d:mulens_class_1'],
        pdfs['d:mulens_class_2'],
        pdfs['d:snn_snia_vs_nonia'],
        pdfs['d:snn_sn_vs_all'],
        pdfs['d:rfscore'],
        pdfs['i:ndethist'],
        pdfs['i:drb'],
        pdfs['i:classtar'],
        pdfs['i:jd'],
        pdfs['i:jdstarthist'],
        pdfs['d:knscore']
    )

    # inplace (booo)
    pdfs['d:cdsxmatch'] = classifications

    colnames.append(idname)
    colnames_to_display.append(idname)
    dtypes.update({idname: type(df[idname].values[0])})

    pdfs_fink = pdfs[colnames]

    # Make clickable objectId
    pdfs_fink['i:objectId'] = pdfs_fink['i:objectId'].apply(markdownify_objectid)

    # Column values are string by default - convert them
    pdfs_fink = pdfs_fink.astype(dtype=dtypes)

    # Rename columns
    pdfs_fink = pdfs_fink.rename(
        columns={i: j for i, j in zip(colnames, colnames_to_display)}
    )

    # Display only the last alert
    pdfs_fink = pdfs_fink.loc[pdfs_fink.groupby('objectId')['last seen'].idxmax()]
    pdfs_fink['last seen'] = pdfs_fink['last seen'].apply(convert_jd)

    # round numeric values for better display
    pdfs_fink = pdfs_fink.round(2)

    # Final join
    join_df = pd.merge(
        pdfs_fink[['objectId', 'classification', idname]],
        df,
        on=idname
    )
    data = join_df.to_dict('records')
    columns = [
        {
            'id': c,
            'name': c,
            'type': 'text',
            'presentation': 'markdown'
        } for c in join_df.columns
    ]
    if len(join_df) == 1:
        msg = "1 object found in {}".format(filename)
    else:
        msg = "{} objects found in {}".format(len(join_df), filename)
    return data, columns, msg

def generate_csv(s: str, lists: list) -> str:
    """ Make a string (CSV formatted) given lists of data and header.
    Parameters
    ----------
    s: str
        String which will contain the data.
        Should initially contain the CSV header.
    lists: list of lists
        List containing data.
        Length of `lists` must correspond to the header.

    Returns
    ----------
    s: str
        Updated string with one row per line.

    Examples
    ----------
    >>> header = "toto,tata\\n"
    >>> lists = [[1, 2], ["cat", "dog"]]
    >>> table = generate_csv(header, lists)
    >>> print(table)
    toto,tata
    1,"cat"
    2,"dog"
    <BLANKLINE>
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC)
    _ = [writer.writerow(row) for row in zip(*lists)]
    return s + output.getvalue().replace('\r', '')

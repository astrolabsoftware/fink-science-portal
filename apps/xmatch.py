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
import dash
from dash.dependencies import Input, Output, State
import dash_core_components as dcc
import dash_html_components as html
import dash_table

import pandas as pd
import healpy as hp
import numpy as np

import astropy.units as u
from astropy.coordinates import SkyCoord

from app import app
from app import clientP

from apps.utils import extract_fink_classification
from apps.utils import markdownify_objectid

layout = html.Div([
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
    dash_table.DataTable(id='datatable-upload-container')
], className='home', style={
    'background-image': 'linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(/assets/background.png)',
    'background-size': 'contain'
})


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


@app.callback(Output('datatable-upload-container', 'data'),
              Output('datatable-upload-container', 'columns'),
              Input('datatable-upload', 'contents'),
              State('datatable-upload', 'filename'))
def update_output(contents, filename):
    if contents is None:
        return [{}], []
    df = parse_contents(contents, filename)

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
        'i:classtar'
    ]

    # Column name to display
    colnames_to_display = [
        'objectId', 'RA', 'Dec', 'last seen', 'classification', 'ndethist'
    ]

    # Types of columns
    dtypes_ = [
        np.str, np.float, np.float, np.float, np.str, np.int
    ]
    dtypes = {i: j for i, j in zip(colnames, dtypes_)}

    raname = [i for i in df.columns if i in ['i:ra', 'RA', 'ra', 'Ra']][0]
    decname = [i for i in df.columns if i in ['i:dec', 'DEC', 'dec', 'Dec']][0]
    # extract ra/dec
    if 'h' in ra:
        coords = [
            SkyCoord(ra, dec, frame='icrs')
            for ra, dec in zip(df[raname].values, df[decname].values)
        ]
    elif ':' in ra or ' ' in ra:
        coords = [
            SkyCoord(ra, dec, frame='icrs', unit=(u.hourangle, u.deg))
            for ra, dec in zip(df[raname].values, df[decname].values)
        ]
    else:
        coords = [
            SkyCoord(ra, dec, frame='icrs', unit='deg')
            for ra, dec in zip(df[raname].values, df[decname].values)
        ]
    ras = [coord.ra.deg for i in df[raname].values]
    decs = [coord.dec.deg for i in df[decname].values]

    nrow = len(ra)
    indices = [i for i in range(nrow)]

    radius = 1.5 # arcsec
    # loop over rows
    clientP.setLimit(10)
    for index, ra, dec in zip(indices, ras, decs):
        pix = hp.ang2pix(
            131072,
            np.pi / 2.0 - np.pi / 180.0 * dec,
            np.pi / 180.0 * ra
        )
        vec = hp.ang2vec(
            np.pi / 2.0 - np.pi / 180.0 * dec,
            np.pi / 180.0 * ra
        )
        pixs = hp.query_disc(
            131072,
            vec,
            np.pi / 180 * radius / 3600.,
            inclusive=True
        )

        to_search = ",".join(['key:key:{}'.format(i) for i in pixs])

        results = clientP.scan(
            "",
            to_search,
            ",".join(colnames + colnames_added_values),
            0, True, True
        )

        # Loop over results and construct the dataframe
        if not results.isEmpty():
            pdf = pd.DataFrame.from_dict(results, orient='index')
            if index == 0:
                pdfs = pdf
            else:
                pdfs = pd.concat((pdfs, pdf))

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
        pdfs['i:classtar']
    )

    # inplace (booo)
    pdfs['d:cdsxmatch'] = classifications

    pdfs = pdfs[colnames]

    # Make clickable objectId
    pdfs['i:objectId'] = pdfs['i:objectId'].apply(markdownify_objectid)

    # Column values are string by default - convert them
    pdfs = pdfs.astype(dtype=dtypes)

    # Rename columns
    pdfs = pdfs.rename(
        columns={i: j for i, j in zip(colnames, colnames_to_display)}
    )

    # Display only the last alert
    pdfs = pdfs.loc[pdfs.groupby('objectId')['last seen'].idxmax()]
    pdfs['last seen'] = pdfs['last seen'].apply(convert_jd)

    # round numeric values for better display
    pdfs = pdfs.round(2)

    table = dash_table.DataTable(
        data=pdfs.sort_values('last seen', ascending=False).to_dict('records'),
        columns=[
            {
                'id': c,
                'name': c,
                'type': 'text',
                'presentation': 'markdown'
            } for c in colnames_to_display
        ],
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
        }
    )
    return table#df.to_dict('records'), [{"name": i, "id": i} for i in df.columns]

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
import dash
from dash.exceptions import PreventUpdate
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import dash_table

import pandas as pd
import numpy as np
from astropy.time import Time, TimeDelta
import healpy as hp

from app import app
from app import client, clientT, clientP, nlimit
from apps.utils import extract_row
from apps.utils import convert_jd
from apps.utils import extract_fink_classification
from apps.utils import markdownify_objectid

msg = """
_Enter a valid object ID (e.g. ZTF19acmdpyr) or a prefix (e.g. ZTF19) on
the left panel, and press enter. Then click on an objectId to get more details.
The table shows:_

- _objectId: Unique identifier for this object_
- _RA: Right Ascension of candidate; J2000 (deg)_
- _Dec: Declination of candidate; J2000 (deg)_
- _last seen: last date the object has been seen_
- _classification: Classification inferred by Fink:_
  - _Supernova candidate_
  - _Microlensing candidate_
  - _Solar System Object_
  - _SIMBAD class_
- _#alerts: number of Fink alerts corresponding to this object._
"""

object_id = dbc.FormGroup(
    [
        dbc.Label("Search by Object ID"),
        dbc.Input(
            placeholder="e.g. ZTF19acmdpyr",
            type="text",
            id='objectid',
            debounce=True
        ),
        dbc.FormText("Enter an objectId beginning with 'ZTF'"),
    ], style={'width': '100%', 'display': 'inline-block'}
)

conesearch = dbc.FormGroup(
    [
        dbc.Label("Conesearch"),
        dbc.Input(
            placeholder="ra, dec, radius",
            type="text",
            id='conesearch',
            debounce=True
        ),
        dbc.FormText("RA/Dec in degrees, radius in arcsecond")
    ], style={'width': '100%', 'display': 'inline-block'}
)

date_range = dbc.FormGroup(
    [
        dbc.Label("Search by Date"),
        html.Br(),
        dbc.Input(
            placeholder="YYYY-MM-DD HH:mm:ss",
            type="text",
            id='startdate',
            debounce=True,
        ),
        dbc.Input(
            placeholder="window [min]",
            type="number",
            id='window',
            max=180,
            debounce=True,
        ),
    ], style={'width': '100%', 'display': 'inline-block'}
)

alert_category = dbc.FormGroup(
    [
        dbc.Label("Filter by class"),
        dcc.Dropdown(
            id="alerts-dropdown",
            options=[
                {'label': 'All', 'value': 'All'},
                {'label': 'SN candidate', 'value': 'SN candidate'},
                {'label': 'Microlensing candidate', 'value': 'Microlensing candidate'},
                {'label': 'SIMBAD', 'value': 'SIMBAD'},
                {'label': 'Solar System', 'value': 'Solar System'},
                {'label': 'Unknown', 'value': 'Unknown'},
            ],
            clearable=False,
            value='All',
            style={'width': '100%', 'display': 'inline-block'}
        )
    ], style={'width': '100%', 'display': 'inline-block'}
)

submit_button = dbc.Button(
    'Submit Query',
    id='submit_query',
    style={'width': '100%', 'display': 'inline-block'},
    block=True
)

layout = html.Div(
    [
        dbc.Container(
            [
                dbc.Row([
                    dbc.Col(
                        [
                            dbc.Row(
                                html.Img(
                                    src="/assets/Fink_PrimaryLogo_WEB.png",
                                    height="50px"
                                )
                            ),
                            html.Br(),
                            html.P("Search Options"),
                            dbc.Row(object_id),
                            dbc.Row(conesearch),
                            dbc.Row(date_range),
                            dbc.Row(submit_button),
                            # html.Br(),
                            # dbc.Row(latest_alerts),
                        ], width=3
                    ),
                    dbc.Col([
                        html.H6(id="table"),
                        dbc.Card(
                            dbc.CardBody(
                                dcc.Markdown(msg)
                            ), style={
                                'backgroundColor': 'rgb(248, 248, 248, .7)'
                            }
                        )
                    ], width=9)
                ]),
            ], className="mb-4"
        )
    ], style={
        'background-image': 'url(/assets/background.png)',
        'width': '100%',
        'height': '100%',
        'top': '0px',
        'left': '0px',
    }
)

@app.callback(
    Output("table", "children"),
    [
        Input("submit_query", "n_clicks"),
        Input("objectid", "value"),
        Input("conesearch", "value"),
        Input('startdate', 'value'),
        Input('window', 'value')
    ]
)
def construct_table(n_clicks, objectid, radecradius, startdate, window):
    """ Query the HBase database and format results into a DataFrame.

    Parameters
    ----------
    value: str
        Object ID (or prefix) from user input

    Returns
    ----------
    dash_table
        Dash table containing aggregated data by object ID.
    """
    changed_id = [p['prop_id'] for p in dash.callback_context.triggered][0]
    if 'submit_query' not in changed_id:
        raise PreventUpdate
    # wrong query
    wrong_id = (objectid is None) or (objectid == '')
    wrong_conesearch = (radecradius is None) or (radecradius == '')
    wrong_date = (startdate is None) or (startdate == '')

    if n_clicks is not None and wrong_id and wrong_conesearch and wrong_date:
        return html.Table()

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
        'd:snn_sn_vs_all'
    ]

    # Column name to display
    colnames_to_display = [
        'objectId', 'RA', 'Dec', 'last seen', 'classification', '# ZTF trigger'
    ]

    # Types of columns
    dtypes_ = [
        np.str, np.float, np.float, np.float, np.str, np.int
    ]
    dtypes = {i: j for i, j in zip(colnames, dtypes_)}

    # default table
    if n_clicks is None:
        # # TODO: change that to date search
        return html.Table()

    if radecradius is not None and radecradius != '':
        clientP.setLimit(1000)

        # Interpret user input.
        # TODO: unsafe method...
        ra, dec, radius = radecradius.split(',')
        ra, dec, radius = float(ra), float(dec), float(radius) / 3600.

        # angle to vec conversion
        vec = hp.ang2vec(np.pi / 2.0 - np.pi / 180.0 * dec, np.pi / 180.0 * ra)

        # list of neighbour pixels
        pixs = hp.query_disc(131072, vec, np.pi / 180 * radius, inclusive=True)

        # Send request
        to_evaluate = ",".join(['key:key:{}'.format(i) for i in pixs])
        results = clientP.scan(
            "",
            to_evaluate,
            ",".join(colnames + colnames_added_values),
            0, True, True
        )
    elif startdate is not None and window is not None and startdate != '':
        # Time to jd
        jd_start = Time(startdate).jd
        jd_end = jd_start + TimeDelta(window * 60, format='sec').jd

        # Send the request. RangeScan.
        clientT.setRangeScan(True)
        to_evaluate = "key:key:{},key:key:{}".format(jd_start, jd_end)
        results = clientT.scan(
            "",
            to_evaluate,
            ",".join(colnames + colnames_added_values),
            0, True, True
        )
    else:
        # objectId search
        # TODO: check input with a regex
        to_evaluate = "key:key:{}".format(objectid)

        results = client.scan(
            "",
            to_evaluate,
            ",".join(colnames + colnames_added_values),
            0, True, True
        )

    # reset the limit in case it has been changed above
    client.setLimit(nlimit)

    if results.isEmpty():
        return html.Table()

    # Loop over results and construct the dataframe
    pdfs = pd.DataFrame.from_dict(results, orient='index')

    classifications = extract_fink_classification(
        pdfs['d:cdsxmatch'],
        pdfs['d:roid'],
        pdfs['d:mulens_class_1'],
        pdfs['d:mulens_class_2'],
        pdfs['d:snn_snia_vs_nonia'],
        pdfs['d:snn_sn_vs_all']
    )

    pdfs['d:cdsxmatch'] = classifications

    pdfs = pdfs[colnames]

    pdfs['i:objectId'] = pdfs['i:objectId'].apply(markdownify_objectid)

    # Column values are string by default - convert them
    pdfs = pdfs.astype(dtype=dtypes)

    # Rename columns
    pdfs = pdfs.rename(
        columns={i: j for i, j in zip(colnames, colnames_to_display)}
    )

    # replace cross-match by full classification
    # pdfs['classification'] = classifications

    # mismatch between nalerthist and number of real alerts
    # TODO: solve this mismatch!
    #nalerts = pdfs.groupby('objectId').count()['#detections'].values

    # Display only the last alert
    pdfs = pdfs.loc[pdfs.groupby('objectId')['last seen'].idxmax()]

    #pdfs['#detections'] = nalerts

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
    return table

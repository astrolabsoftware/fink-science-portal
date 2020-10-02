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
import dash_table

import pandas as pd
import numpy as np
from astropy.time import Time

from app import app
from app import client
from apps.decoder import convert_hbase_string
from apps.utils import convert_jd

msg = """
_Enter a valid object ID (e.g. ZTF18acvqrrf) or a prefix (e.g. ZTF20) on
the left panel, and press enter. Then click on an objectId to get more details.
The table shows:_

- _objectId: Unique identifier for this object_
- _RA: Right Ascension of candidate; J2000 (deg)_
- _Dec: Declination of candidate; J2000 (deg)_
- _last seen: last date the object has been seen_
- _cross-match: CDS crossmatch. Unknown if there is no match_
- _SNN score: SN Ia score from SuperNNova (1 is SN Ia)_
- _SSO object: Solar System Object label_
  - _0: probably not a SSO, 1: first time ZTF sees this object, 2: flagged by Fink as new SSO, 3: flagged by ZTF as known SSO_
- _#alerts: number of alerts corresponding to this object._
"""

object_id = dbc.FormGroup(
    [
        dbc.Label("Search by Object ID"),
        dbc.Input(
            placeholder="e.g. ZTF18 or ZTF19aaaaoor",
            type="text",
            id='objectid',
            debounce=True
        ),
        dbc.FormText("Enter an objectId beginning with 'ZTF'"),
    ]
)

filter_property = dbc.FormGroup(
    [
        dbc.Label("Filter by property"),
        dbc.Input(
            placeholder="ra < 10",
            type="text",
            id='filter_property',
            debounce=True
        ),
        dcc.Markdown("Known [alert field](https://zwickytransientfacility.github.io/ztf-avro-alert/schema.html), \n or a Fink added value field.", style={'font-size': '9pt'}),
    ]
)

latest_alerts = dbc.FormGroup(
    [
        dbc.Label("Latest alerts by category"),
        dcc.Dropdown(
            id="alerts-dropdown",
            placeholder="Select a category",
            clearable=True,
            style={'width': '100%', 'display': 'inline-block'}
        )
    ]
)

submit_button = dbc.FormGroup(
    [
        dbc.Button('Submit Query', id='submit_query', style={'width': '100%', 'display': 'inline-block'})
    ]
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
                            dbc.Row(filter_property),
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

@app.callback(Output("table", "children"), [Input("submit_query", "n_clicks"), Input("objectid", "value"), Input("filter_property", "value")])
def construct_table(n_clicks, objectid, filter_property):
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
    if n_clicks is None:
        return html.Table()
    if objectid is None or objectid == '':
        return html.Table()
    if filter_property is not None and filter_property != '':
        client.setEvaluation(filter_property)
    data = client.scan("", "key:key:{}".format(objectid), "", "1000")
    # print(filter_property, objectid)
    # if filter_property is None:
    #     filter_property = ""
    # data = client.scan("", "key:key:{}".format(objectid), filter_property, "0")
    if data == '':
        return html.Table()

    # initialise the dataframe
    pdfs = pd.DataFrame()

    # Columns of interest
    colnames = [
        'i:objectId', 'i:ra', 'i:dec', 'i:jd', 'd:cdsxmatch',
        'd:snn_snia_vs_nonia', 'd:roid', 'd:nalerthist'
    ]

    # Column name to display
    colnames_to_display = [
        'objectId', 'RA', 'Dec', 'last seen', 'cross-match',
        'SNN score', 'SSO object', '#alerts'
    ]

    # Types of columns
    dtypes_ = [
        np.str, np.float, np.float, np.float, np.str,
        np.float, np.int, np.int
    ]
    dtypes = {i: j for i, j in zip(colnames, dtypes_)}

    # Loop over results and construct the dataframe
    for datum in data.split('\n'):
        if datum == '':
            continue
        name, properties = convert_hbase_string(datum)
        properties['i:objectId'] = '[{}](/{})'.format(
            properties['i:objectId'],
            properties['i:objectId']
        )

        pdf = pd.DataFrame.from_dict(
            properties,
            orient='index',
            columns=[name]
        ).T[colnames]

        pdfs = pd.concat((pdfs, pdf))

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

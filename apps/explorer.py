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
from dash.dependencies import Input, Output, State

import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
import dash_table

import healpy as hp
import pandas as pd
import numpy as np

import astropy.units as u
from astropy.time import Time, TimeDelta
from astropy.coordinates import SkyCoord

from app import app
from app import client, clientT, clientP, clientS, nlimit
from apps.utils import extract_row
from apps.utils import convert_jd
from apps.utils import extract_fink_classification
from apps.utils import markdownify_objectid

msg = """
![logoexp](/assets/Fink_PrimaryLogo_WEB.png)

Fill one of the fields on the left, and click on the _Submit Query_ button. You can access help by clicking on the buttons at the left of each field.

The table shows:

- objectId: Unique identifier for this object
- RA: Right Ascension of candidate; J2000 (deg)
- Dec: Declination of candidate; J2000 (deg)
- last seen: last date the object has been seen by Fink
- classification: Classification inferred by Fink (Supernova candidate, Microlensing candidate, Solar System Object, SIMBAD class, ...)
- ndethist: Number of spatially coincident detections falling within 1.5 arcsec going back to the beginning of the survey; only detections that fell on the same field and readout-channel ID where the input candidate was observed are counted. All raw detections down to a photometric S/N of ~ 3 are included.
"""

msg_conesearch = """
Perform a conesearch around a position on the sky given by (RA, Dec, radius).
The initializer for RA/Dec is very flexible and supports inputs provided in a number of convenient formats.
The following ways of initializing a conesearch are all equivalent (radius in arcsecond):

* 271.3914265, 45.2545134, 5
* 271d23m29.1354s, 45d15m16.2482s, 5
* 18h05m33.9424s, +45d15m16.2482s, 5
* 18 05 33.9424, +45 15 16.2482, 5
* 18:05:33.9424, 45:15:16.2482, 5
"""

msg_objectid = """
Enter a valid object ID to access its data, e.g. try:

* ZTF19acmdpyr, ZTF19acnjwgm, ZTF17aaaabte, ZTF20abqehqf, ZTF18acuajcr
"""

msg_date = """
Choose a starting date and a time window to see all alerts in this period.
Dates are in UTC, and the time window in minutes.
Example of valid search:

* 2019-11-03 02:40:00
"""

msg_latest_alerts = """
Choose a class of interest using the drop-down menu to see the 100 latest alerts processed by Fink.
"""

simbad_types = np.sort(pd.read_csv('assets/simbad_types.csv', header=None)[0].values)
simbad_types_display = [i.capitalize() for i in simbad_types]


@app.callback(
    [
        Output("objectid", "value"),
        Output("conesearch", "value"),
        Output('startdate', 'value'),
        Output('window', 'value'),
        Output('class-dropdown', 'value')
    ],
    [
        Input("reset_button", "n_clicks"),
    ]
)
def reset_button(n_clicks):
    # Trigger the query only if the reset button is pressed.
    changed_id = [p['prop_id'] for p in dash.callback_context.triggered][0]
    if 'reset_button' not in changed_id:
        raise PreventUpdate
    if n_clicks:
        return None, None, None, None, None

noresults_toast = dbc.Toast(
    "",
    header="",
    id="noresults-toast",
    icon="danger",
    dismissable=True,
    is_open=False,
    style={"position": "fixed", "top": 66, "right": 10, "width": 350},
)

@app.callback(
    [
        Output("noresults-toast", "is_open"),
        Output("noresults-toast", "children"),
        Output("noresults-toast", "header")
    ],
    [
        Input("submit_query", "n_clicks"),
        Input("table", "children"),
        Input("objectid", "value"),
        Input("conesearch", "value"),
        Input('startdate', 'value'),
        Input('window', 'value'),
        Input('class-dropdown', 'value')
    ]
)
def open_noresults(n, table, objectid, radecradius, startdate, window, alert_class):
    """ Toast to warn the user about the fact that we found no results
    """
    # Trigger the query only if the submit button is pressed.
    changed_id = [p['prop_id'] for p in dash.callback_context.triggered][0]
    if 'submit_query' not in changed_id:
        raise PreventUpdate

    id_click = (objectid is not None) and (objectid != '')
    conesearch_click = (radecradius is not None) and (radecradius != '')
    date_click = (startdate is not None) and (startdate != '')
    class_click = (alert_class is not None) and (alert_class != '')

    # multiple queries
    if np.sum([id_click, conesearch_click, date_click, class_click]) > 1:
        m = []
        for name, condition in zip(["Search by Object ID", "Conesearch", "Search by Date", "Get latest 100 alerts by class"], [id_click, conesearch_click, date_click, class_click]):
            if condition:
                m.append(name)
        header = "Multi index search"
        text = "Searching along multiple fields is not yet allowed. Keep only one among {}".format(m)
        return True, text, header

    # ugly hack on the type
    if n and (table['namespace'] == 'dash_html_components'):
        if id_click:
            header = "Search by Object ID"
            text = "{} not found".format(objectid)
        elif conesearch_click:
            header = "Conesearch"
            text = "No alerts found for (RA, Dec, radius) = {}".format(
                radecradius
            )
        elif date_click:
            header = "Search by Date"
            if window:
                jd_start = Time(startdate).jd
                jd_end = jd_start + TimeDelta(window * 60, format='sec').jd

                text = "No alerts found between {} and {}".format(
                    Time(jd_start, format='jd').iso,
                    Time(jd_end, format='jd').iso
                )
            else:
                text = "You need to set a window (in minutes)"
        elif class_click:
            header = "Get latest 100 alerts by class"
            # start of the Fink operations
            jd_start = Time('2019-11-01 00:00:00').jd
            jd_stop = Time.now().jd

            text = "No alerts for class {} in between {} and {}".format(
                alert_class,
                Time(jd_start, format='jd').iso,
                Time(jd_stop, format='jd').iso
            )
        return True, text, header
    return False, "", ""

object_id = dbc.FormGroup(
    [
        dbc.Label(
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button(
                            "",
                            color="secondary",
                            id='open-objectid',
                            outline=True,
                            size="sm",
                            style=dict(height='10%')
                        ), width=1),
                    dbc.Col("Search by Object ID"),
                ],
            )
        ),
        dbc.Toast(
            [dcc.Markdown(msg_objectid, className="mb-0")],
            id="objectid-toast",
            header="Help",
            icon="light",
            dismissable=True,
            is_open=False
        ),
        dbc.Input(
            placeholder="e.g. ZTF19acmdpyr",
            type="text",
            id='objectid',
            debounce=True
        ),
        dbc.FormText("Enter a ZTF objectId, e.g. ZTF19acnjwgm"),
    ], style={'width': '100%', 'display': 'inline-block'}
)

@app.callback(
    Output("objectid-toast", "is_open"),
    [Input("open-objectid", "n_clicks")],
    [State("objectid-toast", "is_open")],
)
def open_objectid(n, is_open):
    if n:
        return not is_open
    return is_open

conesearch = dbc.FormGroup(
    [
        dbc.Label(
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button(
                            "",
                            color="secondary",
                            id='open-conesearch',
                            outline=True,
                            size="sm",
                            style=dict(height='10%')
                        ), width=1
                    ),
                    dbc.Col("Conesearch", width=1),
                ],
            )
        ),
        dbc.Toast(
            [dcc.Markdown(msg_conesearch, className="mb-0")],
            id="conesearch-toast",
            header="Help",
            icon="light",
            dismissable=True,
            is_open=False
        ),
        dbc.Input(
            placeholder="ra, dec, radius",
            type="text",
            id='conesearch',
            debounce=True
        ),
        dbc.FormText("e.g. 271.3914265, 45.2545134, 5"),
    ], style={'width': '100%', 'display': 'inline-block'}
)

@app.callback(
    Output("conesearch-toast", "is_open"),
    [Input("open-conesearch", "n_clicks")],
    [State("conesearch-toast", "is_open")],
)
def open_conesearch(n, is_open):
    if n:
        return not is_open
    return is_open

date_range = dbc.FormGroup(
    [
        dbc.Label(
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button(
                            "",
                            color="secondary",
                            id='open-date',
                            outline=True,
                            size="sm",
                            style=dict(height='10%')
                        ), width=1
                    ),
                    dbc.Col("Search by Date", width=10),
                ],
            )
        ),
        dbc.Toast(
            [dcc.Markdown(msg_date, className="mb-0")],
            id="date-toast",
            header="Help",
            icon="light",
            dismissable=True,
            is_open=False
        ),
        html.Br(),
        dbc.Input(
            placeholder="YYYY-MM-DD HH:mm:ss",
            type="text",
            id='startdate',
            debounce=True,
        ),
        dbc.FormText("Start date in UTC, e.g. 2019-11-03 02:40:00"),
        dbc.Input(
            placeholder="window [min]",
            type="number",
            id='window',
            max=180,
            debounce=True,
        ),
        dbc.FormText("Time window in minutes"),
    ], style={'width': '100%', 'display': 'inline-block'}
)

@app.callback(
    Output("date-toast", "is_open"),
    [Input("open-date", "n_clicks")],
    [State("date-toast", "is_open")],
)
def open_date(n, is_open):
    if n:
        return not is_open
    return is_open

dropdown = dbc.FormGroup(
    [
        dbc.Label(
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button(
                            "",
                            color="secondary",
                            id='open-latest-alerts',
                            outline=True,
                            size="sm",
                            style=dict(height='10%')
                        ), width=1
                    ),
                    dbc.Col(dbc.Label("Get latest 100 alerts by class"), width=11),
                ], justify='start',
            ), style={'width': '100%', 'display': 'inline-block'}
        ),
        dbc.Toast(
            [dcc.Markdown(msg_latest_alerts, className="mb-0")],
            id="latest-alerts-toast",
            header="Help",
            icon="light",
            dismissable=True,
            is_open=False
        ),
        dcc.Dropdown(
            id='class-dropdown',
            options=[
                {'label': 'All classes', 'value': 'allclasses'},
                {'label': 'Fink derived classes', 'disabled': True, 'value': 'None'},
                {'label': 'Early Supernova candidates', 'value': 'Early SN candidate'},
                {'label': 'Supernova candidates', 'value': 'SN candidate'},
                {'label': 'Microlensing candidates', 'value': 'Microlensing candidate'},
                {'label': 'Solar System Object candidates', 'value': 'Solar System'},
                {'label': 'Ambiguous', 'value': 'Ambiguous'},
                {'label': 'Simbad crossmatch', 'disabled': True, 'value': 'None'},
                *[{'label': label, 'value': value} for label, values in zip(simbad_types_display, simbad_types)]
            ],
            searchable=True,
            clearable=True,
            placeholder="Start typing or choose a class",
        )
    ], style={'width': '100%', 'display': 'inline-block'}
)

@app.callback(
    Output("latest-alerts-toast", "is_open"),
    [Input("open-latest-alerts", "n_clicks")],
    [State("latest-alerts-toast", "is_open")],
)
def open_latest_alerts(n, is_open):
    if n:
        return not is_open
    return is_open

submit_button = dbc.Button(
    'Submit Query',
    id='submit_query',
)

reset_button = dbc.Button(
    'Reset',
    id='reset_button',
    outline=True,
    color='secondary',
)

advanced_search_button = dbc.Button(
    "Advanced Search",
    id="collapse-button",
    className="mb-3",
    color="primary",
)
advanced_search = html.Div(
    [
        dbc.Collapse(
            dbc.Card(dbc.CardBody([dropdown])),
            id="collapse"
        ),
        html.Br()
    ], style={'width': '100%', 'display': 'inline-block'}
)

@app.callback(
    Output("collapse", "is_open"),
    [Input("collapse-button", "n_clicks")],
    [State("collapse", "is_open")],
)
def toggle_collapse(n, is_open):
    if n:
        return not is_open
    return is_open


layout = html.Div(
    [
        dbc.Container(
            [
                html.Br(),
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
                            dbc.Row(object_id),
                            dbc.Row(conesearch),
                            dbc.Row(date_range),
                            #dbc.Row(advanced_search_button),
                            #dbc.Row(advanced_search),
                            dbc.Row(dropdown),
                            dbc.Row(dbc.ButtonGroup([submit_button, reset_button])),
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
                    ], width=9),
                ]),
            ], className="mb-8", fluid=True, style={'width': '95%'}
        ), noresults_toast
    ], className='home', style={
        'background-image': 'linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(/assets/background.png)',
        'background-size': 'contain'
    }
)

@app.callback(
    Output("table", "children"),
    [
        Input("submit_query", "n_clicks"),
        Input("reset_button", "n_clicks"),
        Input("objectid", "value"),
        Input("conesearch", "value"),
        Input('startdate', 'value'),
        Input('window', 'value'),
        Input('class-dropdown', 'value')
    ]
)
def construct_table(n_clicks, reset_button, objectid, radecradius, startdate, window, alert_class):
    """ Query the HBase database and format results into a DataFrame.

    Parameters
    ----------
    n_clicks: int
        Represents the number of times that the button has been clicked on.
    objectid: str
        ObjectId as given by the user
    radecradius: str
        stringified comma-separated conesearch query (RA, Dec, radius)
    startdate: str
        Start date in format YYYY/MM/DD HH:mm:ss (UTC)
    window: int
        Number minutes
    alert_class: str
        Class of the alert to search against

    Returns
    ----------
    dash_table
        Dash table containing aggregated data by object ID.
    """
    if reset_button:
        return html.Table()

    # Trigger the query only if the submit button is pressed.
    changed_id = [p['prop_id'] for p in dash.callback_context.triggered][0]
    if 'submit_query' not in changed_id:
        raise PreventUpdate

    id_click = (objectid is not None) and (objectid != '')
    conesearch_click = (radecradius is not None) and (radecradius != '')
    date_click = (startdate is not None) and (startdate != '')
    class_click = (alert_class is not None) and (alert_class != '')

    if np.sum([id_click, conesearch_click, date_click, class_click]) > 1:
        raise PreventUpdate

    # wrong query
    wrong_id = (objectid is None) or (objectid == '')
    wrong_conesearch = (radecradius is None) or (radecradius == '')
    wrong_date = (startdate is None) or (startdate == '')
    wrong_class = (alert_class is None) or (alert_class == '')

    # If nothing has been filled
    if n_clicks is not None and wrong_id and wrong_conesearch and wrong_date and wrong_class:
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

    # default table
    if n_clicks is None:
        # # TODO: change that to date search
        return html.Table()

    # Search for latest alerts for a specific class
    if alert_class is not None and alert_class != '' and alert_class != 'allclasses':
        clientS.setLimit(100)
        clientS.setRangeScan(True)
        clientS.setReversed(True)

        # start of the Fink operations
        jd_start = Time('2019-11-01 00:00:00').jd
        jd_stop = Time.now().jd

        results = clientS.scan(
            "",
            "key:key:{}_{},key:key:{}_{}".format(
                alert_class,
                jd_start,
                alert_class,
                jd_stop
            ),
            ",".join(colnames + colnames_added_values), 0, False, False
        )
    # Search for latest alerts (all classes)
    elif alert_class == 'allclasses':
        clientT.setLimit(100)
        clientT.setRangeScan(True)
        clientT.setReversed(True)

        # start of the Fink operations
        jd_start = Time('2019-11-01 00:00:00').jd
        jd_stop = Time.now().jd

        to_evaluate = "key:key:{},key:key:{}".format(jd_start, jd_stop)
        results = clientT.scan(
            "",
            to_evaluate,
            ",".join(colnames + colnames_added_values),
            0, True, True
        )
    elif radecradius is not None and radecradius != '':
        clientP.setLimit(1000)

        # Interpret user input
        ra, dec, radius = radecradius.split(',')
        if 'h' in ra:
            coord = SkyCoord(ra, dec, frame='icrs')
        elif ':' in ra or ' ' in ra:
            coord = SkyCoord(ra, dec, frame='icrs', unit=(u.hourangle, u.deg))
        else:
            coord = SkyCoord(ra, dec, frame='icrs', unit='deg')

        ra = coord.ra.deg
        dec = coord.dec.deg
        radius = float(radius) / 3600.

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
    return table

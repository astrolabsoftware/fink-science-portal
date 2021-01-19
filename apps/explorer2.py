import dash
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import dash_table
from dash.exceptions import PreventUpdate

from apps.utils import markdownify_objectid
from apps.api import APIURL

from app import app

import requests
import pandas as pd
import numpy as np
from astropy.time import Time, TimeDelta

simbad_types = pd.read_csv('assets/simbad_types.csv', header=None)[0].values
simbad_types = sorted(simbad_types, key=lambda s: s.lower())

message_help = """
##### Object ID

Enter a valid object ID to access its data, e.g. try:

* ZTF19acmdpyr, ZTF19acnjwgm, ZTF17aaaabte, ZTF20abqehqf, ZTF18acuajcr

##### Conesearch

Perform a conesearch around a position on the sky given by (RA, Dec, radius).
The initializer for RA/Dec is very flexible and supports inputs provided in a number of convenient formats.
The following ways of initializing a conesearch are all equivalent (radius in arcsecond):

* 271.3914265, 45.2545134, 5
* 271d23m29.135s, 45d15m16.25s, 5
* 18h05m33.942s, +45d15m16.25s, 5
* 18 05 33.942, +45 15 16.25, 5
* 18:05:33.942, 45:15:16.25, 5

##### Date search

Choose a starting date and a time window to see all alerts in this period.
Dates are in UTC, and the time window in minutes.
You can choose YYYY-MM-DD hh:mm:ss, Julian Date, or Modified Julian Date. Example of valid search:

* 2019-11-03 02:40:00
* 2458790.61111
* 58790.11111

##### Class

Choose a class of interest using the drop-down menu to see the 100 latest alerts processed by Fink.

"""

modal = html.Div(
    [
        dbc.Button(
            "Help",
            id="open",
            color='light',
            outline=True,
            style={
                "border":"0px black solid",
                'background': 'rgba(255, 255, 255, 0.0)',
                'color': 'grey'
            }
        ),
        dbc.Modal(
            [
                dbc.ModalHeader("Fink Science Portal"),
                dbc.ModalBody(dcc.Markdown(message_help)),
                dbc.ModalFooter(
                    dbc.Button("Close", id="close", className="ml-auto")
                ),
            ],
            id="modal", scrollable=True
        ),
    ]
)


@app.callback(
    Output("modal", "is_open"),
    [Input("open", "n_clicks"), Input("close", "n_clicks")],
    [State("modal", "is_open")],
)
def toggle_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open


dropdown_menu_items = [
    dbc.DropdownMenuItem("ZTF Object ID", id="dropdown-menu-item-1"),
    dbc.DropdownMenuItem("Conesearch", id="dropdown-menu-item-2"),
    dbc.DropdownMenuItem("Date Search", id="dropdown-menu-item-3"),
    dbc.DropdownMenuItem("Class search", id="dropdown-menu-item-4")
]


input_group = dbc.InputGroup(
    [
        dbc.DropdownMenu(
            dropdown_menu_items,
            addon_type="append",
            id='dropdown-query',
            label="objectID",
            color='light',
            className='rcorners3',
            toggle_style={"border":"0px black solid", 'background': 'rgba(255, 255, 255, 0.0)', 'color': 'grey'}
        ),
        dbc.Input(
            id="input-group-dropdown-input",
            autoFocus=True,
            style={"border":"0px black solid", 'background': 'rgba(255, 255, 255, 0.0)', 'color': 'grey'},
            className='inputbar'
        ),
        dbc.Button(
            "X", id="reset",
            style={"border":"0px black solid", 'background': 'rgba(255, 255, 255, 0.0)', 'color': 'grey'}
        ),
        dbc.Button(
            "Go", id="submit",
            href="/explorer2",
            style={"border":"0px black solid", 'background': 'rgba(255, 255, 255, 0.0)', 'color': 'grey'}
        ),
        modal
    ], style={"border": "0.5px grey solid", 'background': 'rgba(255, 255, 255, .75)'}, className='rcorners2'
)
msg = """
![logoexp](/assets/Fink_PrimaryLogo_WEB.png)

Fill one of the fields on the left, and click on the _Submit Query_ button. You can access help by clicking on the buttons at the left of each field.

By default, the table shows:

- i:objectId: Unique identifier for this object
- i:ra: Right Ascension of candidate; J2000 (deg)
- i:dec: Declination of candidate; J2000 (deg)
- v:lastdate: last date the object has been seen by Fink
- v:classification: Classification inferred by Fink (Supernova candidate, Microlensing candidate, Solar System Object, SIMBAD class, ...)
- i:ndethist: Number of spatially coincident detections falling within 1.5 arcsec going back to the beginning of the survey; only detections that fell on the same field and readout-channel ID where the input candidate was observed are counted. All raw detections down to a photometric S/N of ~ 3 are included.

Users can also add more columns using the dropdown button above. Full documentation of all available fields can be found at http://134.158.75.151:24000/api/v1/columns.
"""

def tab1():
    h = html.Div([
        dbc.Row([
            dcc.Markdown(msg)
        ]),
    ])
    return h

def tab2(table):
    return [html.Br(), table]

@app.callback(
    [
        Output("select", "style"),
        Output("select", "options"),
        Output("select", "placeholder"),
    ],
    [
        Input("dropdown-menu-item-1", "n_clicks"),
        Input("dropdown-menu-item-2", "n_clicks"),
        Input("dropdown-menu-item-3", "n_clicks"),
        Input("dropdown-menu-item-4", "n_clicks"),
        Input("reset", "n_clicks"),
    ]
)
def input_type(n1, n2, n3, n4, n_reset):
    ctx = dash.callback_context

    if not ctx.triggered:
        return {'display': 'none'}, [], ''
    else:
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "dropdown-menu-item-3":
        options = [
            {'label': '1 minute', 'value': 1},
            {'label': '10 minutes', 'value': 10},
            {'label': '60 minutes (can be long)', 'value': 60}
        ]
        placeholder = "Choose a time window (default is 1 minute)"
        return {}, options, placeholder
    elif button_id == "dropdown-menu-item-4":
        options = [
            {'label': 'All classes', 'value': 'allclasses'},
            {'label': 'Fink derived classes', 'disabled': True, 'value': 'None'},
            {'label': 'Early Supernova candidates', 'value': 'Early SN candidate'},
            {'label': 'Supernova candidates', 'value': 'SN candidate'},
            {'label': 'Microlensing candidates', 'value': 'Microlensing candidate'},
            {'label': 'Solar System Object candidates', 'value': 'Solar System'},
            {'label': 'Ambiguous', 'value': 'Ambiguous'},
            {'label': 'Simbad crossmatch', 'disabled': True, 'value': 'None'},
            *[{'label': simtype, 'value': simtype} for simtype in simbad_types]
        ]
        placeholder = "Start typing or choose a class (default is last 100 alerts)"
        return {}, options, placeholder
    elif button_id == "reset":
        return {'display': 'none'}, [], ''
    else:
        return {'display': 'none'}, [], ''

@app.callback(
    [
        Output("input-group-dropdown-input", "placeholder"),
        Output("dropdown-query", "label"),
        Output("input-group-dropdown-input", "value")
    ],
    [
        Input("dropdown-menu-item-1", "n_clicks"),
        Input("dropdown-menu-item-2", "n_clicks"),
        Input("dropdown-menu-item-3", "n_clicks"),
        Input("dropdown-menu-item-4", "n_clicks"),
        Input("reset", "n_clicks"),
    ],
    State("input-group-dropdown-input", "value")
)
def on_button_click(n1, n2, n3, n4, n_reset, val):
    ctx = dash.callback_context

    default = "Enter a valid object ID or choose another query type"
    if not ctx.triggered:
        return default, "objectID", ""
    else:
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "reset":
        return default, 'objectID', ""
    elif button_id == "dropdown-menu-item-1":
        return "Enter a valid ZTF object ID", "objectID", val
    elif button_id == "dropdown-menu-item-2":
        return "Perform a conesearch around RA, Dec, radius. See Help for the syntax", "Conesearch", val
    elif button_id == "dropdown-menu-item-3":
        return "Search alerts inside a time window. See Help for the syntax", "Date", val
    elif button_id == "dropdown-menu-item-4":
        return "Show last 100 alerts for a particular class", "Class", val
    else:
        return "Valid object ID", "objectID", ""

@app.callback(
    Output("logo", "children"),
    [
        Input("submit", "n_clicks"),
        Input("reset", "n_clicks"),
    ],
)
def logo(ns, nr):
    """
    """
    ctx = dash.callback_context

    logo = [
        html.Br(),
        html.Br(),
        dbc.Row(dbc.Col(html.Img(src="/assets/Fink_PrimaryLogo_WEB.png", height='100%', width='60%')), style={'textAlign': 'center'}),
        html.Br()
    ]
    if not ctx.triggered:
        return logo
    else:
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "submit":
        return []
    elif button_id == "reset":
        return logo
    else:
        return logo

@app.callback(
    [
        Output("results", "children"),
        Output("validate_results", "value"),
    ],
    [
        Input("submit", "n_clicks"),
        Input("reset", "n_clicks"),
        Input("input-group-dropdown-input", "value"),
        Input("dropdown-query", "label"),
        Input("select", "value"),
    ],
    State("results", "children"),
)
def results(ns, nr, query, query_type, dropdown_option, results):
    colnames_to_display = [
        'i:objectId', 'i:ra', 'i:dec', 'v:lastdate', 'v:classification', 'i:ndethist'
    ]

    ctx = dash.callback_context

    if not ctx.triggered:
        return results
    else:
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "reset":
        return dash_table.DataTable(
            data=[],
            columns=[],
            id='result_table'
        ), 0
    elif button_id != "submit":
        raise PreventUpdate

    if (query_type in ['objectID', 'Conesearch', 'Date']) and ((query == '') or (query is None)):
        return dash_table.DataTable(
            data=[],
            columns=[],
            id='result_table'
        ), 0

    if query_type == 'objectID':
        r = requests.post(
            '{}/api/v1/explorer'.format(APIURL),
            json={
                'objectId': query,
            }
        )
    elif query_type == 'Conesearch':
        ra, dec, radius = query.split(',')
        r = requests.post(
            '{}/api/v1/explorer'.format(APIURL),
            json={
                'ra': ra,
                'dec': dec,
                'radius': float(radius)
            }
        )
    elif query_type == 'Date':
        if dropdown_option is None:
            window = 1
        else:
            window = dropdown_option
        r = requests.post(
            '{}/api/v1/explorer'.format(APIURL),
            json={
                'startdate': query,
                'window': window
            }
        )
    elif query_type == 'Class':
        if dropdown_option is None:
            alert_class = 'allclasses'
        else:
            alert_class = dropdown_option
        r = requests.post(
            '{}/api/v1/latests'.format(APIURL),
            json={
                'class': alert_class,
                'n': '100'
            }
        )

    # Format output in a DataFrame
    pdf = pd.read_json(r.content)

    if pdf.empty:
        data, columns = [], []
        validation = 0
    else:
        # Make clickable objectId
        pdf['i:objectId'] = pdf['i:objectId'].apply(markdownify_objectid)

        data = pdf.sort_values('i:jd', ascending=False).to_dict('records')

        columns = [
            {
                'id': c,
                'name': c,
                'type': 'text',
                # 'hideable': True,
                'presentation': 'markdown',
            } for c in colnames_to_display
        ]
        validation = 1
    table = dash_table.DataTable(
        data=data,
        columns=columns,
        id='result_table',
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
    results_ = [
        dbc.Tabs(
            [
                dbc.Tab(tab1(), label='Info', tab_id='t0'),
                dbc.Tab(tab2(table), label="Table", tab_id='t1'),
                dbc.Tab(label="Sky map", tab_id='t2', disabled=True),
            ],
            id="tabs",
            active_tab="t1",
        )
    ]
    return results_, validation


noresults_toast = dbc.Toast(
    "",
    header="",
    id="noresults-toast2",
    icon="danger",
    dismissable=True,
    is_open=False,
    style={"position": "fixed", "top": 66, "right": 10, "width": 350},
)

@app.callback(
    [
        Output("noresults-toast2", "is_open"),
        Output("noresults-toast2", "children"),
        Output("noresults-toast2", "header")
    ],
    [
        Input("submit", "n_clicks"),
        Input("validate_results", "value"),
        Input("input-group-dropdown-input", "value"),
        Input("dropdown-query", "label"),
        Input("select", "value"),
    ]
)
def open_noresults(n, results, query, query_type, dropdown_option):
    """ Toast to warn the user about the fact that we found no results
    """
    # Trigger the query only if the submit button is pressed.
    changed_id = [p['prop_id'] for p in dash.callback_context.triggered][0]
    if 'submit' not in changed_id:
        raise PreventUpdate

    good_query = (query is not None) or (query != '')

    good_objectid = (query.startswith('ZTF')) and (query_type == 'objectID')
    good_conesearch = (len(query.split(',')) == 3) and (query_type == 'Conesearch')
    good_datesearch = (query != '') and (query_type == 'Date')
    good_class = query_type == 'Class'

    # no queries
    if np.sum([good_objectid, good_conesearch, good_datesearch, good_class]) == 0:
        header = "No fields"
        text = "You need to define your query"
        return True, text, header

    bad_objectid = (query_type == 'objectID') and not (query.startswith('ZTF'))
    bad_conesearch = (query_type == 'Conesearch') and not (len(query.split(',')) == 3)
    if query_type == 'Date':
        try:
            _ = Time(query)
        except (ValueError, TypeError) as e:
            header = 'Bad start time'
            return True, e, header

    # ugly hack
    if n and int(results) == 0:
        if good_objectid:
            header = "Search by Object ID"
            text = "{} not found".format(query)
        elif good_conesearch:
            header = "Conesearch"
            text = "No alerts found for (RA, Dec, radius) = {}".format(
                query
            )
        elif good_datesearch:
            header = "Search by Date"
            if dropdown_option is None:
                window = 1
            else:
                window = dropdown_option
            jd_start = Time(query).jd
            jd_end = jd_start + TimeDelta(window * 60, format='sec').jd

            text = "No alerts found between {} and {}".format(
                Time(jd_start, format='jd').iso,
                Time(jd_end, format='jd').iso
            )
        elif good_class:
            header = "Get latest 100 alerts by class"
            if dropdown_option is None:
                alert_class = 'allclasses'
            else:
                alert_class = dropdown_option
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


layout = html.Div(
    [
        html.Br(),
        html.Br(),
        dbc.Container(
            [
                html.Div(id='logo'),
                html.Br(),
                dbc.Row(input_group),
                html.Br(),
                dcc.Dropdown(
                    id='select',
                    searchable=True,
                    clearable=True,
                ),
            ], id='trash', fluid=True, style={'width': '60%'}
        ),
        dbc.Container(id='results'),
        dbc.Input(id='validate_results', style={'display': 'none'}),
        noresults_toast
    ],
    className='home',
    style={
        'background-image': 'linear-gradient(rgba(255,255,255,0.6), rgba(255,255,255,0.6)), url(/assets/background.png)',
        'background-size': 'contain'
    }
)

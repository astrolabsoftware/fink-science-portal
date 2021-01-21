import dash
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import dash_table
from dash.exceptions import PreventUpdate
import visdcc

from apps.utils import markdownify_objectid
from apps.api import APIURL
from apps.utils import isoify_time, validate_query

from app import app
from app import clientP

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

Choose a starting date and a time window to see all processed alerts in this period.
Dates are in UTC, and the time window in minutes.
Among several, you can choose YYYY-MM-DD hh:mm:ss, Julian Date, or Modified Julian Date. Example of valid search:

* 2019-11-03 02:40:00
* 2458790.61111
* 58790.11111

##### Class

Choose a class of interest using the drop-down menu to see the 100 latest alerts processed by Fink.

"""

msg_info = """
![logoexp](/assets/Fink_PrimaryLogo_WEB.png)

Fill the search bar and hit the search button. You can access help by clicking on the Help button at the right of the bar.

By default, the table shows:

- i:objectId: Unique identifier for this object
- i:ra: Right Ascension of candidate; J2000 (deg)
- i:dec: Declination of candidate; J2000 (deg)
- v:lastdate: last date the object has been seen by Fink
- v:classification: Classification inferred by Fink (Supernova candidate, Microlensing candidate, Solar System Object, SIMBAD class, ...)
- i:ndethist: Number of spatially coincident detections falling within 1.5 arcsec going back to the beginning of the survey; only detections that fell on the same field and readout-channel ID where the input candidate was observed are counted. All raw detections down to a photometric S/N of ~ 3 are included.

You can also add more columns using the dropdown button above the result table. Full documentation of all available fields can be found at https://fink-portal.ijclab.in2p3.fr:24000/api/v1/columns.
"""

modal = html.Div(
    [
        dbc.Button(
            "Help",
            id="open",
            color='light',
            outline=True,
            style={
                "border": "0px black solid",
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
    """ Callback for the modal (open/close)
    """
    if n1 or n2:
        return not is_open
    return is_open


dropdown_menu_items = [
    dbc.DropdownMenuItem("ZTF Object ID", id="dropdown-menu-item-1"),
    dbc.DropdownMenuItem("Conesearch", id="dropdown-menu-item-2"),
    dbc.DropdownMenuItem("Date Search", id="dropdown-menu-item-3"),
    dbc.DropdownMenuItem("Class search", id="dropdown-menu-item-4")
]


fink_search_bar = dbc.InputGroup(
    [
        dbc.DropdownMenu(
            dropdown_menu_items,
            addon_type="append",
            id='dropdown-query',
            label="objectID",
            color='light',
            className='rcorners3',
            toggle_style={"border": "0px black solid", 'background': 'rgba(255, 255, 255, 0.0)', 'color': 'grey'}
        ),
        dbc.Input(
            id="search_bar_input",
            autoFocus=True,
            type='search',
            style={"border": "0px black solid", 'background': 'rgba(255, 255, 255, 0.0)', 'color': 'grey'},
            className='inputbar'
        ),
        dbc.Button(
            html.I(className="fas fa-search fa-1x"),
            id="submit",
            href="/explorer2",
            style={"border": "0px black solid", 'background': 'rgba(255, 255, 255, 0.0)', 'color': '#15284F90'}
        ),
        modal
    ], style={"border": "0.5px grey solid", 'background': 'rgba(255, 255, 255, .75)'}, className='rcorners2'
)

def print_msg_info():
    """ Display the explorer info message
    """
    h = html.Div([
        dbc.Row([
            dcc.Markdown(msg_info)
        ]),
    ])
    return h

def display_table_results(table):
    """ Display explorer results in the form of a table with a dropdown
    menu on top to insert more data columns.

    The dropdown menu options are taken from the client schema (ZTF & Fink). It also
    contains other derived fields from the portal (fink_additional_fields).

    Parameters
    ----------
    table: dash_table.DataTable
        Dash DataTable containing the results. Can be empty.

    Returns
    ----------
    out: list of objects
        The list of objects contain:
          1. A dropdown menu to add new columns in the table
          2. Table of results
        The dropdown is shown only if the table is non-empty.
    """
    schema = clientP.schema()
    schema_list = list(schema.columnNames())
    fink_fields = [i for i in schema_list if i.startswith('d:')]
    ztf_fields = [i for i in schema_list if i.startswith('i:')]
    fink_additional_fields = ['v:r-g', 'v:rate(r-g)', 'v:classification', 'v:lastdate']

    return [
        html.Br(),
        dcc.Dropdown(
            id='field-dropdown2',
            options=[
                {'label': 'Fink science module outputs', 'disabled': True, 'value': 'None'},
                *[{'label': field, 'value': field} for field in fink_fields],
                {'label': 'Fink additional values', 'disabled': True, 'value': 'None'},
                *[{'label': field, 'value': field} for field in fink_additional_fields],
                {'label': 'Original ZTF fields (subset)', 'disabled': True, 'value': 'None'},
                *[{'label': field, 'value': field} for field in ztf_fields]
            ],
            searchable=True,
            clearable=True,
            placeholder="Add more fields to the table",
        ),
        html.Br(),
        table
    ]

@app.callback(
    Output('aladin-lite-div-skymap', 'run'),
    [
        Input("validate_results", "value"),
        Input("result_table", "data"),
        Input("result_table", "columns")
    ],
)
def display_skymap(validation, data, columns):
    """ Display explorer result on a sky map (Aladin lite)

    TODO: image is not displayed correctly the first time
    TODO: for several search, images are superimposed... we need to find a way to clear the prevous view

    the default parameters are:
        * PanSTARRS colors
        * FoV = 360 deg
        * Fink alerts overlayed

    Callbacks
    ----------
    Input: takes the validation flag (0: no results, 1: results) and table data
    Output: Display a sky image around the alert position from aladin.
    """
    ctx = dash.callback_context
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if validation and (button_id == "validate_results"):
        pdf = pd.DataFrame(data)
        # Coordinate of the first alert
        ra0 = pdf['i:ra'].values[0]
        dec0 = pdf['i:dec'].values[0]

        # Javascript. Note the use {{}} for dictionary
        img = """
        var a = A.aladin('#aladin-lite-div-skymap', {{target: '{} {}', survey: 'P/PanSTARRS/DR1/color/z/zg/g', showReticle: true, allowFullZoomout: true, fov: 360}});
        var cat = A.catalog({{name: 'Fink alerts', sourceSize: 18, shape: 'cross', color: 'orange'}});
        a.addCatalog(cat);
        """.format(ra0, dec0)

        ras = pdf['i:ra'].values
        decs = pdf['i:dec'].values
        link = '<a target="_blank" href="{}/{}">{}</a>'
        titles = [link.format(APIURL, i.split(']')[0].split('[')[1], i.split(']')[0].split('[')[1]) for i in pdf['i:objectId'].values]
        mags = pdf['i:magpsf'].values
        classes = pdf['v:classification'].values
        for ra, dec, title, mag, class_ in zip(ras, decs, titles, mags, classes):
            img += """cat.addSources([A.marker({}, {}, {{popupTitle: '{}', popupDesc: '<em>mag:</em> {:.2f}<br/><em>Classification:</em> {}<br/>'}})]);""".format(ra, dec, title, mag, class_)

        # img cannot be executed directly because of formatting
        # We split line-by-line and remove comments
        img_to_show = [i for i in img.split('\n') if '// ' not in i]
        print(" ".join(img_to_show))

        return " ".join(img_to_show)
    else:
        return ""

def display_skymap():
    """ Display the sky map in the explorer tab results (Aladin lite)

    It uses `visdcc` to execute javascript directly.

    Returns
    ---------
    out: list of objects
    """
    return [
        dbc.Container(
            html.Div(
                [
                    visdcc.Run_js(id='aladin-lite-div-skymap'),
                    dcc.Markdown('_Hit the fullscreen button if the image is not displayed (we are working on it...)_')
                ], style={
                    'width': '100%',
                    'height': '25pc'
                }
            )
        )
    ]

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
    ]
)
def input_type(n1, n2, n3, n4):
    """ Decide if the dropdown below the search bar should be shown

    Only some query types need to have a dropdown (Date & Class search). In
    those cases, we show the dropdown, otherwise it is hidden.

    In the case of class search, the options are derived from the
    Fink classification, and the SIMBAD labels.
    """
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
    else:
        return {'display': 'none'}, [], ''

@app.callback(
    [
        Output("search_bar_input", "placeholder"),
        Output("dropdown-query", "label"),
        Output("search_bar_input", "value")
    ],
    [
        Input("dropdown-menu-item-1", "n_clicks"),
        Input("dropdown-menu-item-2", "n_clicks"),
        Input("dropdown-menu-item-3", "n_clicks"),
        Input("dropdown-menu-item-4", "n_clicks"),
    ],
    State("search_bar_input", "value")
)
def on_button_click(n1, n2, n3, n4, val):
    """ Change the placeholder value of the search bar based on the query type
    """
    ctx = dash.callback_context

    default = "Enter a valid object ID or choose another query type"
    if not ctx.triggered:
        return default, "objectID", ""
    else:
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "dropdown-menu-item-1":
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
        Input("submit", "n_clicks")
    ],
)
def logo(ns):
    """ Show the logo in the start page (and hide it otherwise)
    """
    ctx = dash.callback_context

    logo = [
        html.Br(),
        html.Br(),
        dbc.Row(
            dbc.Col(
                html.Img(
                    src="/assets/Fink_PrimaryLogo_WEB.png",
                    height='100%',
                    width='60%'
                )
            ), style={'textAlign': 'center'}
        ),
        html.Br()
    ]
    if not ctx.triggered:
        return logo
    else:
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "submit":
        return []
    else:
        return logo

def construct_results_layout(table):
    """ Construct the tabs containing explorer query results
    """
    results_ = [
        dbc.Tabs(
            [
                dbc.Tab(print_msg_info(), label='Info', tab_id='t0'),
                dbc.Tab(display_table_results(table), label="Table", tab_id='t1'),
                dbc.Tab(display_skymap(), label="Sky map", tab_id='t2'),
            ],
            id="tabs",
            active_tab="t1",
        )
    ]
    return results_

def populate_result_table(data, columns):
    """ Define options of the results table, and add data and columns
    """
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
    return table

@app.callback(
    [
        Output("result_table", "data"),
        Output("result_table", "columns"),
    ],
    [
        Input('field-dropdown2', 'value')
    ],
    [
        State("result_table", "data"),
        State("result_table", "columns"),
    ]
)
def update_table(field_dropdown, data, columns):
    """ Update table by adding new columns (no server call)
    """
    changed_id = [p['prop_id'] for p in dash.callback_context.triggered][0]
    # Adding new columns (no client call)
    if 'field-dropdown2' in changed_id:
        if field_dropdown is None or len(columns) == 0:
            raise PreventUpdate

        incolumns = any(c.get('id') == field_dropdown for c in columns)

        if incolumns is True:
            raise PreventUpdate

        columns.append({
            'name': field_dropdown,
            'id': field_dropdown,
            'type': 'text',
            'presentation': 'markdown'
            # 'hideable': True,
        })

        return data, columns
    else:
        raise PreventUpdate

@app.callback(
    [
        Output("results", "children"),
        Output("validate_results", "value"),
    ],
    [
        Input("submit", "n_clicks"),
        Input("search_bar_input", "value"),
        Input("dropdown-query", "label"),
        Input("select", "value"),
    ],
    State("results", "children")
)
def results(ns, query, query_type, dropdown_option, results):
    """ Query the database from the search input

    Returns
    ---------
    out: list of Tabs
        Tabs containing info, table, and skymap with the results
    validation: int
        0: not results found, 1: results found
    """
    colnames_to_display = [
        'i:objectId', 'i:ra', 'i:dec', 'v:lastdate', 'v:classification', 'i:ndethist'
    ]

    ctx = dash.callback_context
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id != "submit":
        raise PreventUpdate

    is_ok = validate_query(query, query_type)
    if not is_ok['flag']:
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
        startdate = isoify_time(query)
        if dropdown_option is None:
            window = 1
        else:
            window = dropdown_option
        r = requests.post(
            '{}/api/v1/explorer'.format(APIURL),
            json={
                'startdate': startdate,
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

    table = populate_result_table(data, columns)
    return construct_results_layout(table), validation


noresults_toast = html.Div(
    [
        dbc.Toast(
            "",
            header="",
            id="noresults-toast2",
            icon="danger",
            dismissable=True,
            is_open=False
        ),
        html.Br()
    ]
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
        Input("search_bar_input", "value"),
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

    validation = validate_query(query, query_type)
    if not validation['flag']:
        return (not validation['flag']), validation['header'], validation['text']

    # Good query, but no results
    # ugly hack
    if n and int(results) == 0:
        if query_type == 'objectID':
            header = "Search by Object ID"
            text = "{} not found".format(query)
        elif query_type == 'Conesearch':
            header = "Conesearch"
            text = "No alerts found for (RA, Dec, radius) = {}".format(
                query
            )
        elif query_type == 'Date':
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
        elif query_type == 'Class':
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
                dbc.Row(fink_search_bar),
                html.Br(),
                dcc.Dropdown(
                    id='select',
                    searchable=True,
                    clearable=True,
                ),
                html.Br(),
                noresults_toast
            ], id='trash', fluid=True, style={'width': '60%'}
        ),
        dbc.Container(id='results'),
        dbc.Input(id='validate_results', style={'display': 'none'}),
    ],
    className='home',
    style={
        'background-image': 'linear-gradient(rgba(255,255,255,0.6), rgba(255,255,255,0.6)), url(/assets/background.png)',
        'background-size': 'contain'
    }
)

import dash
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import dash_table
from dash.exceptions import PreventUpdate

import pandas as pd

# bootstrap theme
# https://bootswatch.com/spacelab/
external_stylesheets = [
    dbc.themes.SPACELAB,
    'http://aladin.u-strasbg.fr/AladinLite/api/v2/latest/aladin.min.css'
]
external_scripts = [
    'http://code.jquery.com/jquery-1.9.1.min.js',
    'http://aladin.u-strasbg.fr/AladinLite/api/v2/latest/aladin.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.4/MathJax.js?config=TeX-MML-AM_CHTML',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css',
    'https://use.fontawesome.com/releases/v5.7.2/css/all.css'
]
# external_stylesheets = [dbc.themes.LUX]
# external_stylesheets = [dbc.themes.FLATLY]

app = dash.Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    external_scripts=external_scripts,
    meta_tags=[{
        "name": "viewport",
        "content": "width=device-width, initial-scale=1"
    }]
)

app.title = 'Fink Science Portal'
server = app.server
app.config.suppress_callback_exceptions = True

msg_conesearch = """
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
Example of valid search:

* 2019-11-03 02:40:00

##### Class

Choose a class of interest using the drop-down menu to see the 100 latest alerts processed by Fink.

"""

modal = html.Div(
    [
        dbc.Button("Help", id="open", color='light', outline=True, style={"border":"0px black solid", 'background': 'rgba(255, 255, 255, 0.0)', 'color': 'grey'}),
        dbc.Modal(
            [
                dbc.ModalHeader("Fink Science Portal"),
                dbc.ModalBody(dcc.Markdown(msg_conesearch)),
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
            toggle_style={"border":"0px black solid", 'background': 'rgba(255, 255, 255, 0.0)', 'color': 'grey'}
        ),
        dbc.Input(
            id="input-group-dropdown-input",
            autoFocus=True,
            type='search',
            style={"border":"0px black solid", 'background': 'rgba(255, 255, 255, .75)', 'color': 'grey'},
            className='inputbar'
        ),
        dbc.Button(
            "X", id="reset",
            # outline=True, color='light',
            style={"border":"0px black solid", 'background': 'rgba(255, 255, 255, .75)', 'color': 'grey'}
        ),
        dbc.Button(
            "Go", id="submit", #outline=True, color='light',
            href="/",
            style={"border":"0px black solid", 'background': 'rgba(255, 255, 255, .75)', 'color': 'grey'}
        ),
        modal
    ], style={"border":"0.5px black solid"}, className='rcorners2'
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

# @app.callback(
#     Output("content", "children"),
#     [Input("tabs", "active_tab")]
# )
# def switch_tab(at):
#     if at == "t1":
#         return tab2()
#     elif at == "t2":
#         return html.Div([])
#     elif at == "t0":
#         return tab1()
#     return html.P("This shouldn't ever be displayed...")

@app.callback(
    Output("container", "children"),
    [
        Input("dropdown-menu-item-1", "n_clicks"),
        Input("dropdown-menu-item-2", "n_clicks"),
        Input("dropdown-menu-item-3", "n_clicks"),
        Input("dropdown-menu-item-4", "n_clicks"),
        Input("reset", "n_clicks"),
    ],
    State("container", "children"),
)
def input_type(n1, n2, n3, n4, n_reset, container):
    ctx = dash.callback_context

    if not ctx.triggered:
        return container
    else:
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "dropdown-menu-item-4":
        elem = [
            dcc.Dropdown(id="select", options=[
                {"label": "Option 1", "value": "1"},
                {"label": "Option 2", "value": "2"},
                {"label": "Disabled option", "value": "3", "disabled": True},
            ]),
            html.Br()
        ]
        return elem
    elif button_id == "reset":
        return []
    else:
        return container

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
        return "Valid object ID", "objectID", val
    elif button_id == "dropdown-menu-item-2":
        return "Conesearch", "Conesearch", val
    elif button_id == "dropdown-menu-item-3":
        return "Date search", "Date", val
    elif button_id == "dropdown-menu-item-4":
        return "Class search", "Class", val
    else:
        return "Valid object ID", "objectID", ""

@app.callback(
    [
        Output("table", "data"),
        Output("table", "columns")
    ],
    [
        Input("submit", "n_clicks"),
        Input("reset", "n_clicks")
    ],
    [
        State('table', 'data'),
        State('table', 'columns')
    ]
)
def table(n_submit, n_reset, data, columns):
    # if n_submit is None:
        # return [], []
    ctx = dash.callback_context
    # pdf = pd.DataFrame({'a': range(int(n_submit))})
    # columns = [
    #     {
    #         'id': c,
    #         'name': c,
    #         'type': 'text',
    #         # 'hideable': True,
    #         'presentation': 'markdown',
    #     } for c in pdf.columns
    # ]
    # return pdf.to_dict('records'), columns

    # changed_id = [p['prop_id'] for p in dash.callback_context.triggered][0]
    # # Trigger the query only if the submit button is pressed.
    # if 'submit' not in changed_id:
    #     raise PreventUpdate
    #
    # # Trigger the query only if the reset button is not pressed.
    # if n_reset and 'reset' in changed_id:
    #     return [], []
    # elif n_submit and 'submit' in changed_id:
    #     button_id = 'submit'
    # else:
    #     return [], []

    if not ctx.triggered:
        return data, columns
    else:
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "submit":
        pdf = pd.DataFrame({'a': range(int(n_submit))})
        columns = [
            {
                'id': c,
                'name': c,
                'type': 'text',
                # 'hideable': True,
                'presentation': 'markdown',
            } for c in pdf.columns
        ]
        return pdf.to_dict('records'), columns
    elif button_id == "reset":
        return [], []
    else:
        return data, columns

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
    Output("results", "children"),
    [
        Input("submit", "n_clicks"),
        Input("reset", "n_clicks"),
        Input("input-group-dropdown-input", "value"),
    ],
    State("results", "children"),
)
def results(ns, nr, query, results):
    ctx = dash.callback_context

    if not ctx.triggered:
        return results
    else:
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "submit":
        pdf = pd.DataFrame({'a': [query]*ns})
        columns = [
            {
                'id': c,
                'name': c,
                'type': 'text',
                # 'hideable': True,
                'presentation': 'markdown',
            } for c in pdf.columns
        ]
        table = dash_table.DataTable(
            data=pdf.to_dict('records'),
            columns=columns,
            id="table",
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
        return results_
    elif button_id == "reset":
        return html.Div([])
    else:
        return results

    # results_ = [
    #     dbc.Tabs(
    #         [
    #             dbc.Tab(label='Info', tab_id='t0'),
    #             dbc.Tab(label="Table", tab_id='t1'),
    #             dbc.Tab(label="Sky map", tab_id='t2'),
    #         ],
    #         id="tabs",
    #         active_tab="t1",
    #     ),
    #     html.Div(id="content", style={'width': '85%'}),
    # ]
    # if not ctx.triggered:
    #     return []
    # else:
    #     button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    #
    #
    # if button_id == "submit":
    #     return results_
    # elif button_id == "reset":
    #     return []
    # else:
    #     return []

# building the navigation bar
dropdown = dbc.DropdownMenu(
    children=[
        dbc.DropdownMenuItem("About", href="/about"),
        dbc.DropdownMenuItem("Fink Website", href="https://fink-broker.org/"),
        dbc.DropdownMenuItem(
            "Science Portal GitHub",
            href="https://github.com/astrolabsoftware/fink-science-portal"
        ),
    ],
    nav=True,
    in_navbar=True,
    label="Info",
)

navbar = dbc.Navbar(
    [
        html.A(
            dbc.Row(
                [
                    dbc.Col(
                        dbc.NavbarBrand(
                            "Fink Science portal {}".format(0.3),
                            className="ml-2"
                        )
                    ),
                ],
                justify="start",
                no_gutters=True,
            ),
            href="/home",
        ),
        dbc.NavbarToggler(id="navbar-toggler2"),
        dbc.Collapse(
            dbc.Nav(
                # right align dropdown menu with ml-auto className
                [
                    dbc.NavItem(dbc.NavLink('Explorer', href="http://134.158.75.151:24000/explorer")),
                    dbc.NavItem(dbc.NavLink('Xmatch', href="http://134.158.75.151:24000/xmatch")),
                    dbc.NavItem(dbc.NavLink('API', href="http://134.158.75.151:24000/api")),
                    dropdown
                ],
                navbar=True
            ),
            id="navbar-collapse2",
            navbar=True,
        )
    ],
    color="light",
    dark=False,
    className="finknav",
)

app.layout = html.Div(
    [
        navbar,
        # dbc.Container(
        #     [
        #         html.Div(id='logo')
        #     ], className='mb-1', fluid=True, style={'width': '50%'}
        # ),
        dbc.Container(
            [
                html.Div(id='logo'),
                html.Br(),
                dbc.Row(input_group, justify='left'),
                html.Br(),
                html.Div(id='container'),
            ], fluid=True, style={'width': '50%'}
        ),
        dbc.Container(id='results')
    ],
    className='home',
    style={
        'background-image': 'linear-gradient(rgba(255,255,255,0.6), rgba(255,255,255,0.6)), url(/assets/background.png)',
        'background-size': 'contain'
    }
)


if __name__ == '__main__':
    app.run_server(debug=True)

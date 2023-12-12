import dash
from dash import html, dcc, Input, Output, State, dash_table, no_update, ctx, clientside_callback, ALL
import requests
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import json

from dash_autocomplete_input import AutocompleteInput

from fink_utils.xmatch.simbad import get_simbad_labels
import pandas as pd

simbad_types = get_simbad_labels('old_and_new')
simbad_types = sorted(simbad_types, key=lambda s: s.lower())

tns_types = pd.read_csv('../assets/tns_types.csv', header=None)[0].values
tns_types = sorted(tns_types, key=lambda s: s.lower())

finkclasses = [
    'Unknown',
    'Early Supernova Ia candidates',
    'Supernova candidates',
    'Kilonova candidates',
    'Microlensing candidates',
    'Solar System (MPC)',
    'Solar System (candidates)',
    'Tracklet (space debris & satellite glints)',
    'Ambiguous',
    *['(TNS) ' + t for t in tns_types],
    *['(SIMBAD) ' + t for t in simbad_types]
]

# bootstrap theme
external_stylesheets = [
    dbc.themes.SPACELAB,
    '//aladin.u-strasbg.fr/AladinLite/api/v2/latest/aladin.min.css',
    '//use.fontawesome.com/releases/v5.7.2/css/all.css',
]
external_scripts = [
    '//code.jquery.com/jquery-1.12.1.min.js',
    '//aladin.u-strasbg.fr/AladinLite/api/v2/latest/aladin.min.js',
    '//cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.4/MathJax.js?config=TeX-MML-AM_CHTML',
]

from telemetry import DashWithTelemetry
app = DashWithTelemetry(
# app = dash.Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    external_scripts=external_scripts,
    meta_tags=[{
        "name": "viewport",
        "content": "width=device-width, initial-scale=1"
    }]
)

####################################
# Smart search bar

fink_search_bar = dbc.Row(dbc.Col(
    className='p-0 m-0 border border-dark rounded-3',
    children=[
        dbc.InputGroup(
            [
                # dcc.Input(
                #     id='magic_search',
                #     value='',
                #     autoFocus=True,
                #     type='text',
                #     className='inputbar form-control border-0',
                # ),
                AutocompleteInput(
                    id='magic_search',
                    component='input',
                    trigger=[
                        'class:', 'class=',
                    ],
                    options={
                        'class:':finkclasses, 'class=':finkclasses,
                    },
                    maxOptions=0,
                    className="inputbar form-control border-0",
                    quoteWhitespaces=True,
                    regex='^([a-zA-Z0-9_\-()]+|"[a-zA-Z0-9_\- ]*|\'[a-zA-Z0-9_\- ]*)$',
                    autoFocus=True,
                ),

                dbc.Spinner([
                    dmc.ActionIcon(
                        DashIconify(icon="tabler:search", width=20),
                        n_clicks=0,
                        id="submit",
                        color='gray',
                        variant="transparent",
                        radius='xl',
                        size='lg',
                        loaderProps={'variant': 'dots', 'color': 'orange'},
                        # Hide on screen sizes smaller than sm
                        className="d-none d-sm-flex"
                    ),
                ], size='sm',),
            ],
        ),
        dbc.ListGroup(
            id='magic_suggest',
        ),
        dcc.Interval(id="magic_timer", interval=2000, max_intervals=1, disabled=True)
    ]
))

from parse import parse_query

# Time-based debounce from https://joetatusko.com/2023/07/11/time-based-debouncing-with-plotly-dash/
# @app.callback(
#     Output('magic_timer', 'n_intervals'),
#     Output('magic_timer', 'disabled'),
#     Input('magic_search', 'value'),
#     Input('magic_search', 'n_submit'),
#     prevent_initial_call=True,
# )
# def start_suggestion_debounce_timer(value, n_submit):
#     if ctx.triggered[0]['prop_id'].split('.')[1] == 'n_submit':
#         # Stop timer on submit
#         return no_update, True
#     else:
#         # Start timer on normal input
#         return 0, False

clientside_callback(
    """
    function start_suggestion_debounce_timer(value, n_submit, n_intervals) {
        const triggered = dash_clientside.callback_context.triggered.map(t => t.prop_id);
        if (triggered == 'magic_search.n_submit')
            return [dash_clientside.no_update, true];

        if (n_intervals > 0)
            return [0, false];
        else
            return [dash_clientside.no_update, false];
    }
    """,
    [
        Output('magic_timer', 'n_intervals'),
        Output('magic_timer', 'disabled')
    ],
    Input('magic_search', 'value'),
    Input('magic_search', 'n_submit'),
    State('magic_timer', 'n_intervals'),
    prevent_initial_call=True,
)


# Update suggestions
@app.callback(
    Output('magic_suggest', 'children'),
    Output('submit', 'children'),
    Input('magic_timer', 'n_intervals'),
    State('magic_search', 'value'),
    prevent_initial_call=True,
)
def update_suggestions(n_intervals, value):
    if n_intervals == 1:
        if not value:
            return None, no_update
        query = parse_query(value, timeout=5)
        suggestions = []

        params = query['params']

        if not query['action']:
            return None, no_update

        content = []

        if query['completions']:
            content += [
                html.Div(
                    [
                        html.Span('Did you mean:', className='text-secondary'),
                    ] + [
                        dmc.Button(
                            __,
                            id={'type': 'magic_completion', 'index': _},
                            variant='subtle',
                            size='sm',
                            compact=True,
                            n_clicks=0
                        ) for _,__ in enumerate(query['completions'])
                    ],
                    className="border-bottom mb-1"
                )
            ]

        content += [
            dmc.Group([
                html.Strong(query['object']) if query['object'] else None,
                dmc.Badge(query['type'], variant="outline", color='blue') if query['type'] else None,
                dmc.Badge(query['action'], variant="outline", color='red'),
            ], noWrap=False, position='left'),
            html.P(query['hint'], className='m-0'),
        ]

        if len(params):
            content += [
                html.Small(" ".join(["{}={}".format(_,params[_]) for _ in params]))
            ]

        suggestion = dbc.ListGroupItem(
            content,
            action=True,
            className='border-0'
        )

        suggestions.append(suggestion)

        return suggestions, no_update
    else:
        return no_update, no_update

# Completion clicked
@app.callback(
    Output('magic_search', 'value'),
    Input({'type': 'magic_completion', 'index': ALL}, 'n_clicks'),
    State({'type': 'magic_completion', 'index': ALL}, 'children'),
    prevent_initial_call=True
)
def on_completion(n_clicks, values):
    if ctx.triggered[0]['value']:
        # print(ctx.triggered_id)
        # print(values[ctx.triggered_id['index']])
        return values[ctx.triggered_id['index']]

    return no_update

# Submit the results
@app.callback(
    Output('check', 'children'),
    Input('magic_search', 'n_submit'),
    State('magic_search', 'value'),
)
def on_submit(n_submit, value):
    if not n_submit:
        raise PreventUpdate
    else:
        print('query:', value)

        if value:
            query = parse_query(value)
            return html.Span(str(query), className='text-danger')
        else:
            return no_update

#############################################

# Main app
app.layout = html.Div(
    [
        dbc.Container(
            [
                html.Br(),
                dbc.Row(dbc.Col(fink_search_bar, width=12)),
                html.Div(id='check'),
                dmc.Space(h=20),
                html.Pre(parse_query.__doc__),
            ]
        )
    ]
)

# app.run_server('159.69.107.239', debug=True)
app.run_server(debug=True)

# Copyright 2020-2022 AstroLab Software
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
from dash import html, dcc, Input, Output, State, dash_table, no_update
from dash.exceptions import PreventUpdate

import dash_bootstrap_components as dbc
import visdcc
import dash_trich_components as dtc

import dash_mantine_components as dmc
from dash_iconify import DashIconify

from app import server
from app import app
from app import client
from app import APIURL

from apps import summary, about, statistics, search, sso_search
from apps.api import api
from apps import __version__ as portal_version

from apps.utils import markdownify_objectid, class_colors
from apps.utils import isoify_time, validate_query, extract_query_url
from apps.plotting import draw_cutouts_quickview, draw_lightcurve_preview

from fink_utils.xmatch.simbad import get_simbad_labels

import requests
import pandas as pd
import numpy as np
from astropy.time import Time, TimeDelta
from astropy.coordinates import name_resolve
import astropy.utils as autils

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

def create_home_link(label):
    return dmc.Text(
        label,
        size="xl",
        color="gray"
    )

@app.callback(
    Output("drawer", "opened"),
    Input("drawer-demo-button", "n_clicks"),
    prevent_initial_call=True,
)
def drawer_demo(n_clicks):
    return True

app.clientside_callback(
    """function(colorScheme) {
        return {
            colorScheme,
            fontFamily: "'Inter', sans-serif",
            primaryColor: "indigo"
        }
    }""",
    Output("theme-provider", "theme"),
    Input("color-scheme-toggle", "value"),
    prevent_initial_callback=True,
)

navbar = dmc.Header(
    height=55,
    fixed=True,
    p=0,
    m=0,
    style={'background-image': 'linear-gradient(rgba(255,255,255,0.3), rgba(255,255,255,0.3)), url(/assets/background.png)', 'background-size': 'cover'},
    children=[
        dmc.Space(h=10),
        dmc.Container(
            fluid=True,
            children=dmc.Group(
                position="apart",
                align="flex-start",
                children=[
                    dmc.ActionIcon(
                        DashIconify(icon="dashicons:menu", width=30), id="drawer-demo-button", n_clicks=0
                    ),
                    dmc.Drawer(
                        children=[
                            dmc.Divider(
                                labelPosition="left",
                                label=[
                                    DashIconify(
                                        icon='tabler:home', width=15, style={"marginRight": 10}
                                    ),
                                    "Home",
                                ],
                                style={"marginTop": 20, "marginBottom": 20},
                            ),
                            dmc.Group(
                                [
                                    dmc.Anchor(
                                        'Home',
                                        style={"textTransform": "capitalize", "textDecoration": "none"},
                                        href='/',
                                        size="sm",
                                        color="gray",
                                    ),
                                    dmc.Anchor(
                                        'Fink broker',
                                        style={"textTransform": "capitalize", "textDecoration": "none"},
                                        href='https://fink-broker.org',
                                        size="sm",
                                        color="gray",
                                    ),
                                ],
                                grow=True,
                                position="left",
                                spacing="sm",
                                direction="column",
                                style={"paddingLeft": 30, "paddingRight": 20},
                            ),
                            dmc.Divider(
                                labelPosition="left",
                                label=[
                                    DashIconify(
                                        icon='tabler:search', width=15, style={"marginRight": 10}
                                    ),
                                    "Search",
                                ],
                                style={"marginTop": 20, "marginBottom": 20},
                            ),
                            dmc.Group(
                                [
                                    dmc.Anchor(
                                        'Basic search',
                                        style={"textTransform": "capitalize", "textDecoration": "none"},
                                        href='/search',
                                        size="sm",
                                        color="gray",
                                    ),
                                    dmc.Anchor(
                                        'Solar System search',
                                        style={"textTransform": "capitalize", "textDecoration": "none"},
                                        href='/sso',
                                        size="sm",
                                        color="gray",
                                    ),
                                    dmc.Anchor(
                                        'Statistics',
                                        style={"textTransform": "capitalize", "textDecoration": "none"},
                                        href='/stats',
                                        size="sm",
                                        color="gray",
                                    ),
                                ],
                                grow=True,
                                position="left",
                                spacing="sm",
                                direction="column",
                                style={"paddingLeft": 30, "paddingRight": 20},
                            ),
                            dmc.Divider(
                                labelPosition="left",
                                label=[
                                    DashIconify(
                                        icon='carbon:api', width=15, style={"marginRight": 10}
                                    ),
                                    "Learn",
                                ],
                                style={"marginTop": 20, "marginBottom": 20},
                            ),
                            dmc.Group(
                                [
                                    dmc.Anchor(
                                        '{ API }',
                                        style={"textTransform": "capitalize", "textDecoration": "none"},
                                        href='/api',
                                        size="sm",
                                        color="gray",
                                    ),
                                    dmc.Anchor(
                                        'Tutorials',
                                        style={"textTransform": "capitalize", "textDecoration": "none"},
                                        href='https://github.com/astrolabsoftware/fink-tutorials',
                                        size="sm",
                                        color="gray",
                                    ),
                                    dmc.Anchor(
                                        'Bug tracker',
                                        style={"textTransform": "capitalize", "textDecoration": "none"},
                                        href='https://github.com/astrolabsoftware/fink-science-portal',
                                        size="sm",
                                        color="gray",
                                    )
                                ],
                                grow=True,
                                position="left",
                                spacing="sm",
                                direction="column",
                                style={"paddingLeft": 30, "paddingRight": 20},
                            ),
                        ],
                        title="Fink Science Portal",
                        id="drawer",
                        padding="md",
                        zIndex=1e7,
                        transition='pop-top-left',
                    ),
                    dmc.ThemeSwitcher(
                        id="color-scheme-toggle",
                        style={"cursor": "pointer"},
                    ),
                ],
            ),
        )
    ],
)

def Tile(icon, heading, description, href, class_name=None):
    return dcc.Link(
        dmc.Paper(
            p="lg",
            withBorder=True,
            radius='xl',
            shadow='xl',
            children=dmc.Group(
                direction="column",
                spacing=0,
                align="center",
                children=[
                    dmc.ThemeIcon(
                        DashIconify(icon=icon, height=20),
                        size=40,
                        radius=40,
                        variant="light",
                        color='orange'
                    ),
                    dmc.Text(
                        heading,
                        style={"marginTop": 20, "marginBottom": 10},
                    ),
                    dmc.Text(
                        description,
                        color="dimmed",
                        align="center",
                        size="sm",
                        style={"lineHeight": 1.6, "marginBottom": 10},
                    ),
                ]
            ),
            style={"marginBottom": 30},
            class_name=class_name
        ),
        href=href,
        style={"textDecoration": "none"},
    )

# add callback for toggling the collapse on small screens
@app.callback(
    Output("navbar-collapse2", "is_open"),
    [Input("navbar-toggler2", "n_clicks")],
    [State("navbar-collapse2", "is_open")],
)
def toggle_navbar_collapse(n, is_open):
    if n:
        return not is_open
    return is_open

def create_appshell(nav_data):
    return dmc.MantineProvider(
        id="theme-provider",
        theme={
            "colorScheme": "light",
            "fontFamily": "'Inter', sans-serif",
        },
        styles={
            "Button": {"root": {"fontWeight": 400}},
            "Alert": {"title": {"fontWeight": 500}},
            "AvatarsGroup": {"truncated": {"fontWeight": 500}},
        },
        withGlobalStyles=True,
        withNormalizeCSS=True,
        children=[
            dmc.NotificationsProvider(
                [
                    dcc.Location(id='url', refresh=False),
                    navbar,
                    html.Div(id='page-content'),
                    html.Div(children=False, id='is-mobile', hidden=True),
                ]
            ),
        ],
    )

app.layout = create_appshell(dash.page_registry.values())
# # embedding the navigation bar
# app.layout = html.Div([
#     dcc.Location(id='url', refresh=False),
#     navbar,
#     html.Div(id='page-content'),
#     html.Div(children=False, id='is-mobile', hidden=True),
# ])

app.clientside_callback(
    """
    function(href) {
        var cond1 = ( ( window.innerWidth <= 820 ) && ( window.innerHeight <= 600 ) )
        var cond2 = ( ( window.innerWidth <= 600 ) && ( window.innerHeight <= 820 ) )
        return ( ( cond1 ) || ( cond2 ) );
    }
    """,
    Output('is-mobile', 'children'),
    Input('url', 'href')
)

def make_logo():
    """ Show the logo in the start page (and hide it otherwise)
    """
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

    return logo

@app.callback(
    Output('page-content', 'children'),
    [Input('url', 'pathname'), Input('is-mobile', 'children')]
)
def display_page(pathname, is_mobile):
    if is_mobile:
        width = '95%'
        style = {'background-image': 'linear-gradient(rgba(255,255,255,0.3), rgba(255,255,255,0.3)), url(/assets/background.png)', 'background-size': 'cover'}
    else:
        width = '60%'
        style = {'background-image': 'linear-gradient(rgba(255,255,255,0.3), rgba(255,255,255,0.3)), url(/assets/background.png)', 'background-size': 'cover'}
    layout = html.Div(
        [
            html.Br(),
            html.Br(),
            dbc.Container(
                [
                    html.Div(make_logo()),
                    html.Br(),
                    dmc.SimpleGrid(
                        cols=3,
                        breakpoints=[
                            {"maxWidth": "xs", "cols": 1},
                            {"maxWidth": "sm", "cols": 2},
                        ],
                        children=[
                            Tile(
                                icon="majesticons:comet",
                                heading="Solar System search",
                                description="Inspect data from the Solar System",
                                href="/sso",
                                class_name=None
                            ),
                            Tile(
                                icon="tabler:search",
                                heading="Explore Fink alert data",
                                description="Search by name, coordinates, or class",
                                href="/search",
                                class_name='zoomed'
                            ),
                            Tile(
                                icon="carbon:api",
                                heading="{ API }",
                                description="Learn how to integrate Fink services",
                                href="/api",
                                class_name=None
                            ),
                        ]
                    ),
                ], id='trash', fluid=True, style={'width': width}
            ),
        ],
        className='home',
        style=style
    )
    if pathname == '/about':
        return about.layout
    elif pathname == '/search':
        return search.layout(pathname, is_mobile)
    elif pathname == '/sso':
        return sso_search.layout(pathname, is_mobile)
    elif pathname == '/api':
        return api.layout(is_mobile)
    elif pathname == '/stats':
        return statistics.layout(is_mobile)
    elif 'ZTF' in pathname:
        return summary.layout(pathname, is_mobile)
    else:
        return layout


# register the API
try:
    from apps.api.api import api_bp
    server.register_blueprint(api_bp, url_prefix='/')
    server.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    server.config['JSON_SORT_KEYS'] = False
except ImportError as e:
    print('API not yet registered')


if __name__ == '__main__':
    import yaml
    input_args = yaml.load(open('config.yml'), yaml.Loader)
    app.run_server(input_args['IP'], debug=True, port=input_args['PORT'])

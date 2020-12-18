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
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc

from app import server
from app import app

# import all pages in the app
from apps import home, explorer, grafink, summary, about, xmatch, api
from apps import __version__ as portal_version

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
    label="Explore",
)

navbar = dbc.Navbar(
    [
        html.A(
            dbc.Row(
                [
                    dbc.Col(
                        dbc.NavbarBrand(
                            "Fink Science portal - {}".format(portal_version),
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
                [dropdown],
                dbc.Button('API', href="http://134.158.75.151:24000/api"),
                navbar=True,
                vertical=True
            ),
            id="navbar-collapse2",
            navbar=True,
        )
    ],
    color="light",
    dark=False,
    className="finknav",
)

# embedding the navigation bar
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    navbar,
    html.Div(id='page-content')
])


@app.callback(Output('page-content', 'children'),
              [Input('url', 'pathname')])
def display_page(pathname):
    if pathname == '/explorer':
        return explorer.layout
    elif pathname == '/about':
        return about.layout
    elif pathname == '/grafink':
        return grafink.layout
    elif pathname == '/xmatch':
        return xmatch.layout
    elif pathname == '/api':
        return api.layout
    elif 'ZTF' in pathname:
        return summary.layout(pathname)
    else:
        return home.layout


# register the API
try:
    from apps.api import api_bp
    server.register_blueprint(api_bp, url_prefix='/')
    server.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    server.config['JSON_SORT_KEYS'] = False
except ImportError as e:
    print('API not yet registered')


if __name__ == '__main__':
    app.run_server(debug=True)

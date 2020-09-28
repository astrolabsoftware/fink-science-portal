import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc

from app import app

def layout(name):
    layout_ = html.Div([
        dbc.Container([
            dbc.Row([
                dbc.Col(html.H1(children='COVID-19 Worldwide at a glance {}'.format(name)), className="mb-2")
            ]),
            dbc.Row([
                dbc.Col(html.H6(children='Visualising trends across the world'), className="mb-4")
            ]),
            ])
        ])
    return layout_

import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc

import pandas as pd

from app import app
from app import client
from apps.decoder import convert_hbase_string

object_id = dbc.FormGroup(
    [
        dbc.Label("Search by Object ID"),
        dbc.Input(placeholder="Object ID", type="text", id='objectid', debounce=True),
        dbc.FormText("Enter an objectId beginning with 'ZTF'"),
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
        ),
        dbc.FormText("Enter valid category"),
    ]
)

layout = html.Div(
    [
        dbc.Container(
            [
                dbc.Row([dbc.Col(
                    [
                        dbc.Row(html.Img(src="/assets/Fink_PrimaryLogo_WEB.png", height="50px")),
                        html.Br(),
                        html.P("Search Options"),
                        dbc.Row(object_id),
                        html.Br(),
                        dbc.Row(latest_alerts),
                    ]
                ),
                dbc.Col(html.H6(id="table") #, style={'font-size': 10}
                )])
            ], className="mb-4"
        )
    ]
)

@app.callback(Output("table", "children"), [Input("objectid", "value")])
def construct_table(value):
    if value is None or value == '':
        return html.Table()
    data = client.scan("", "key:key:{}".format(value), "", "10000")
    names = []
    pdfs = pd.DataFrame()
    values = ['i:objectId', 'i:jd', 'd:cdsxmatch', 'i:fid']
    for datum in data.split('\n'):
        if datum == '':
            continue
        name, properties = convert_hbase_string(datum)
        names.append(name)
        properties['i:objectId'] = html.A(href='/{}'.format(properties['i:objectId']), children=properties['i:objectId'])
        pdf = pd.DataFrame.from_dict(properties, orient='index', columns=[name]).T[values]
        pdfs = pd.concat((pdfs, pdf))

    # print(pdfs)
    return dbc.Table.from_dataframe(pdfs, striped=True, bordered=True, hover=True)

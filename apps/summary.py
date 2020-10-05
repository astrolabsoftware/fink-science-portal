import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import visdcc
import plotly.graph_objects as go
import dash_table

from app import app, client

import gzip
import io
from astropy.io import fits
import numpy as np
import pandas as pd
import urllib

from apps.explorer import object_id, latest_alerts
from apps.utils import convolve, _data_stretch, convert_jd
from apps.decoder import extract_row

dcc.Location(id='url', refresh=False)

layout_lightcurve = dict(
    autosize=True,
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    legend=dict(font=dict(size=10), orientation="h"),
    xaxis={
        'title': 'Observation date'
    },
    yaxis={
        'autorange': 'reversed',
        'title': 'Magnitude'
    }
)

@app.callback(
    Output('table2', 'children'), Input('url', 'pathname'))
def card_properties(name):
    if name is None or name == '':
        return html.Table()
    results = client.scan("", "key:key:{}".format(name[1:]), None, 0, True, True)
    if results.isEmpty():
        return html.Table()

    pdf = extract_properties(data, None)
    pdf = pdf.sort_values('i:jd', ascending=False).head(1).T
    pdf = pdf.drop(['b:cutoutScience_stampData', 'b:cutoutTemplate_stampData', 'b:cutoutDifference_stampData'])
    pdf['field'] = pdf.index

    table = dash_table.DataTable(
        data=pdf.to_dict('records'), # return last one
        columns=[
            {
                'id': c,
                'name': c,
                'type': 'text',
                'presentation': 'markdown'
            } for c in pdf.columns
        ],
        page_size=5,  # we have less data in this example, so setting to 20
        style_as_list_view=True,
        sort_action="native",
        markdown_options={'link_target': '_blank'},
        style_data={
            'backgroundColor': 'rgb(248, 248, 248, .7)'
        },
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(248, 248, 248, .7)'
            }
        ],
        style_header={
            'backgroundColor': 'rgb(230, 230, 230)',
            'fontWeight': 'bold',
            'textAlign': 'left'
        }
    )
    return table

def draw_lightcurve(data):
    pdf = extract_lightcurve(data)

    jd = pdf['i:jd']
    jd = jd.apply(lambda x: convert_jd(float(x), to='iso'))
    figure = {
        'data': [
            {
                'x': jd[pdf['i:fid'] == '1'],
                'y': pdf['i:magpsf'][pdf['i:fid'] == '1'],
                'error_y': {
                    'type': 'data',
                    'array': pdf['i:sigmapsf'][pdf['i:fid'] == '1'],
                    'visible': True,
                    'color': '#1f77b4'
                },
                'mode': 'markers',
                'name': 'g band',
                'text': jd[pdf['i:fid'] == '1'],
                'marker': {
                    'size': 12,
                    'color': '#1f77b4',
                    'symbol': 'o'}
            },
            {
                'x': jd[pdf['i:fid'] == '2'],
                'y': pdf['i:magpsf'][pdf['i:fid'] == '2'],
                'error_y': {
                    'type': 'data',
                    'array': pdf['i:sigmapsf'][pdf['i:fid'] == '2'],
                    'visible': True,
                    'color': '#ff7f0e'
                },
                'mode': 'markers',
                'name': 'r band',
                'text': jd[pdf['i:fid'] == '2'],
                'marker': {
                    'size': 12,
                    'color': '#ff7f0e',
                    'symbol': 'o'}
            }
        ],
        "layout": layout_lightcurve
    }
    return figure


def card_lightcurve(data):
    graph = dcc.Graph(
        id='lightcurve',
        figure=draw_lightcurve(data),
        style={
            'width': '100%',
            'height': '15pc'
        },
        config={'displayModeBar': False}
    )
    card = dbc.Card(
        dbc.CardBody(
            [
                graph
            ]
        ),
        className="mt-3"#, color='primary', outline=True
    )
    return card

def card_cutouts(science, template, difference):
    card = dbc.Card(
        dbc.CardBody(
            [
                dbc.Row([
                    dbc.Col(html.H5(children="Science", className="text-center")),
                    dbc.Col(html.H5(children="Template", className="text-center")),
                    dbc.Col(html.H5(children="Difference", className="text-center"))
                ]),
                dbc.Row([
                    dcc.Graph(
                        id='science-stamps',
                        figure=draw_cutout(science, 'science'),
                        style={
                            'display': 'inline-block',
                        },
                        config={'displayModeBar': False}
                    ),
                    dcc.Graph(
                        id='template-stamps',
                        figure=draw_cutout(template, 'template'),
                        style={
                            'display': 'inline-block',
                        },
                        config={'displayModeBar': False}
                    ),
                    dcc.Graph(
                        id='difference-stamps',
                        figure=draw_cutout(difference, 'difference'),
                        style={
                            'display': 'inline-block',
                        },
                        config={'displayModeBar': False}
                    ),
                ], justify='around', no_gutters=True)
            ]
        ),
        className="mt-3"#, color='primary', outline=True
    )
    return card

def card_id(data):
    pdf = extract_properties(data, ['i:objectId', 'i:candid', 'i:jd', 'i:ra', 'i:dec'])
    pdf = pdf.sort_values('i:jd', ascending=False)

    id0 = pdf['i:objectId'].values[0]
    candid0 = pdf['i:candid'].values[0]
    ra0 = pdf['i:ra'].values[0]
    dec0 = pdf['i:dec'].values[0]
    date0 = convert_jd(float(pdf['i:jd'].values[0]))

    card = dbc.Card(
        [
            html.H5("ObjectID: {}".format(id0), className="card-title"),
            html.H6("Candid: {}".format(candid0), className="card-subtitle"),
            dcc.Markdown(
                """
                ---
                ```
                Date: {}
                RA: {} deg
                Dec: {} deg
                ```
                """.format(date0, ra0, dec0)
            )
        ],
        className="mt-3", body=True, #color='primary', outline=True
    )
    return card

def card_fink_added_values(data):
    pdf = extract_properties(
        data,
        [
            'i:jd',
            'd:cdsxmatch',
            'd:mulens_class_1',
            'd:mulens_class_2',
            'd:nalerthist',
            'd:rfscore',
            'd:roid',
            'd:snn_sn_vs_all',
            'd:snn_snia_vs_nonia'
        ]
    )
    pdf = pdf.sort_values('i:jd', ascending=False)

    out = "---\n"
    out += "``` \n"
    for index, colname in enumerate(pdf.columns):
        if colname == 'i:jd':
            continue
        if 'snn_' in colname:
            value = np.round(float(pdf[colname].values[0]), 3)
        else:
            value = pdf[colname].values[0]

        out += "{}: {}\n".format(colname[2:], value)

    out += "```"
    card = dbc.Card(
        [

            html.H5("Fink added values", className="card-subtitle"),
            dcc.Markdown(out)
        ],
        className="mt-3", body=True#, color='danger', outline=True
    )
    return card

def tab1_content(data):
    science, template, difference = extract_latest_cutouts(data)
    tab1_content_ = html.Div([
        dbc.Row([
            dbc.Col(card_cutouts(science, template, difference), width=8),
            dbc.Col([card_id(data)], width=4, align='center')
        ]),
        dbc.Row([
            dbc.Col(card_lightcurve(data), width=8),
            dbc.Col([card_fink_added_values(data)], width=4, align='center')
        ]),
    ])
    return tab1_content_

tab2_content = dbc.Card(
    dbc.CardBody(
        [
            html.P("This is tab 2!", className="card-text"),
            dbc.Button("Don't click here", color="danger"),
        ]
    ),
    className="mt-3",
)

def tabs(data):
    tabs_ = dbc.Tabs(
        [
            dbc.Tab(tab1_content(data), label="Summary", tab_style={"margin-left": "auto"}),
            dbc.Tab(tab2_content, label="Supernova", disabled=True),
            dbc.Tab(label="Microlensing", disabled=True),
            dbc.Tab(label="Variable stars", disabled=True),
            dbc.Tab(label="Solar System", disabled=True),
        ]
    )
    return tabs_

def title(name):
    title_ = dbc.Card(
        dbc.CardHeader(
            [
                dbc.Row([
                    html.Img(src="/assets/Fink_SecondaryLogo_WEB.png", height='20%', width='20%'),
                    html.H1(children='{}'.format(name[1:]), id='name', style={'color': '#15284F'})
                ])
            ]
        ),
        #color='primary', outline=True
    )
    return title_

def layout(name):
    # even if there is one object ID, this returns  several alerts
    results = client.scan("", "key:key:{}".format(name[1:]), None, 0, True, True)

    layout_ = html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        [
                            title(name),
                            html.Br(),
                            html.Div(
                                [visdcc.Run_js(id='aladin-lite-div')],
                                style={
                                    'width': '100%',
                                    'height': '30pc'
                                }
                            )
                        ], width={"size": 3},
                    ),
                    dbc.Col(tabs(results), width=8)
                ],
                justify="around", no_gutters=True
            )
        ]
    )

    return layout_

def draw_cutout(data, title):
    """ Display alert data and stamps based on its ID.

    By default, the data curve is the light curve (magpsd vs jd).

    Callbacks
    ----------
    Input: alert_id coming from the `alerts-dropdown` menu
    Input: field_name coming from the `field-dropdown` menu
    Output: Graph to display the historical light curve data of the alert.
    Output: stamps (Science, Template, Difference)

    Parameters
    ----------
    alert_id: str
        ID of the alerts (must be unique and saved on disk).
    field_name: str
        Name of the alert field to plot (default is None).

    Returns
    ----------
    html.div: Graph data and layout based on incoming alert data.
    """
    # Update graph data for stamps
    data = _data_stretch(data, stretch='linear')
    data = data[::-1]
    # data = convolve(data)

    fig = go.Figure(
        data=go.Heatmap(
            z=data, showscale=False, colorscale='greys'
        )
    )

    axis_template = dict(
        autorange=True,
        showgrid=False, zeroline=False,
        linecolor='black', showticklabels=False,
        ticks='')

    fig.update_layout(
        title=title,
        margin=dict(t=0, r=0, b=0, l=0),
        xaxis=axis_template,
        yaxis=axis_template,
        showlegend=True,
        width=150, height=150,
        autosize=False)

    return fig

def readstamp(stamp: str) -> np.array:
    """ Read the stamp data inside an alert.

    Parameters
    ----------
    alert: dictionary
        dictionary containing alert data
    field: string
        Name of the stamps: cutoutScience, cutoutTemplate, cutoutDifference

    Returns
    ----------
    data: np.array
        2D array containing image data
    """
    with gzip.open(io.BytesIO(stamp), 'rb') as f:
        with fits.open(io.BytesIO(f.read())) as hdul:
            data = hdul[0].data
    return data

def extract_properties(data: str, fieldnames: list):
    """
    """
    pdfs = pd.DataFrame()
    out = []
    for rowkey in data:
        if rowkey == '':
            continue
        properties = extract_row(rowkey, data)
        if fieldnames is not None:
            pdf = pd.DataFrame.from_dict(properties, orient='index', columns=[rowkey]).T[fieldnames]
        else:
            pdf = pd.DataFrame.from_dict(properties, orient='index', columns=[rowkey]).T
        pdfs = pd.concat((pdfs, pdf))
    return pdfs

def extract_lightcurve(data):
    """
    """
    pdfs = pd.DataFrame()
    values = ['i:jd', 'i:magpsf', 'i:sigmapsf', 'i:fid']
    for rowkey in data:
        if rowkey == '':
            continue
        properties = extract_row(rowkey, data)
        pdf = pd.DataFrame.from_dict(properties, orient='index', columns=[rowkey]).T[values]
        pdfs = pd.concat((pdfs, pdf))
    return pdfs

def extract_latest_cutouts(data):
    """
    """
    pdfs = pd.DataFrame()
    values = ['i:jd', 'b:cutoutScience_stampData', 'b:cutoutTemplate_stampData', 'b:cutoutDifference_stampData']
    for rowkey in data:
        if rowkey == '':
            continue
        properties = extract_row(rowkey, data)
        pdf = pd.DataFrame.from_dict(properties, orient='index', columns=[rowkey]).T[values]
        pdfs = pd.concat((pdfs, pdf))
    pdfs.sort_values('i:jd', ascending=False)
    diff = readstamp(client.repository().get(pdfs['b:cutoutDifference_stampData'].values[0]))
    science = readstamp(client.repository().get(pdfs['b:cutoutScience_stampData'].values[0]))
    template = readstamp(client.repository().get(pdfs['b:cutoutTemplate_stampData'].values[0]))
    return science, template, diff



@app.callback(
    Output('aladin-lite-div', 'run'), Input('url', 'pathname'))
def integrate_aladin_lite(name):
    """ Integrate aladin light in the 2nd Tab of the dashboard.

    the default parameters are:
        * PanSTARRS colors
        * FoV = 0.02 deg
        * SIMBAD catalig overlayed.

    Callbacks
    ----------
    Input: takes the alert ID
    Output: Display a sky image around the alert position from aladin.

    Parameters
    ----------
    alert_id: str
        ID of the alert
    """
    default_img = ""
    if name:
        results = client.scan("", "key:key:{}".format(name[1:]), None, 0, True, True)
        pdf = extract_properties(results, ['i:jd', 'i:ra', 'i:dec'])
        pdf = pdf.sort_values('i:jd', ascending=False)

        # Coordinate of the current alert
        ra0 = pdf['i:ra'].values[0]
        dec0 = pdf['i:dec'].values[0]

        # Javascript. Note the use {{}} for dictionary
        img = """
        var aladin = A.aladin('#aladin-lite-div',
                  {{
                    survey: 'P/PanSTARRS/DR1/color/z/zg/g',
                    fov: 0.025,
                    target: '{} {}',
                    reticleColor: '#ff89ff',
                    reticleSize: 32
        }});
        var cat = 'https://axel.u-strasbg.fr/HiPSCatService/Simbad';
        var hips = A.catalogHiPS(cat, {{onClick: 'showTable', name: 'Simbad'}});
        aladin.addCatalog(hips);
        """.format(ra0, dec0)

        # img cannot be executed directly because of formatting
        # We split line-by-line and remove comments
        img_to_show = [i for i in img.split('\n') if '// ' not in i]

        return " ".join(img_to_show)

    return default_img

from app import app, APIURL
import pandas as pd
import requests
import io
import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as u
from astropy.time import Time

from dash import html, dcc, Input, Output, dash_table, State
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify
from dash.exceptions import PreventUpdate

import visdcc

from apps.utils import class_colors, isoify_time, convert_jd, readstamp
from apps.plotting import (
    COLORS_ZTF,
    layout_sso_lightcurve,
    colors_,
    layout_ssocand_speed,
    layout_ssocand_acceleration,
)

import plotly.graph_objs as go

from poliastro.twobody import Orbit
from poliastro.plotting.misc import plot_solar_system
from poliastro.bodies import Sun


@app.callback(
    [Output("traj_lc", "data"), Output("traj_orb", "data")], [Input("url", "pathname")]
)
def store_traj_data(pathname):
    traj_id = pathname.split("_")[-1]
    r_lc = requests.post(
        "https://fink-portal.org/api/v1/ssocand",
        json={
            "kind": "lightcurves",  # Mandatory, `orbParams` or `lightcurves`
            # "ssoCandId": traj_id,
        },
    )

    # Format output in a DataFrame
    pdf_lc = pd.read_json(io.BytesIO(r_lc.content))
    pdf_lc = pdf_lc[pdf_lc["d:ssoCandId"] == traj_id]

    r_orb = requests.post(
        "https://fink-portal.org/api/v1/ssocand",
        json={
            "kind": "orbParams",  # Mandatory, `orbParams` or `lightcurves`
        },
    )

    # Format output in a DataFrame
    pdf_orb = pd.read_json(io.BytesIO(r_orb.content))
    pdf_orb = pdf_orb[pdf_orb["d:ssoCandId"] == traj_id]

    return pdf_lc.to_json(), pdf_orb.to_json()


@app.callback(
    Output("card_traj_left", "children"),
    [Input("url", "pathname"), Input("traj_lc", "data"), Input("traj_orb", "data")],
)
def construct_card_title(pathname, json_lc, json_orb):

    traj_lc = pd.read_json(json_lc)
    traj_orb = pd.read_json(json_orb)

    traj_id = pathname.split("_")[-1]
    discovery_date = isoify_time(traj_orb["d:ref_epoch"].values[0])
    date_end = isoify_time(traj_lc["d:jd"].values[-1])
    ndet = len(traj_lc)

    classification = "Solar System trajectory"
    card = dmc.Paper(
        [
            dbc.Row(
                [
                    dbc.Col(
                        dmc.Avatar(src="/assets/Fink_SecondaryLogo_WEB.png", size="lg"),
                        width=2,
                    ),
                    dbc.Col(
                        dmc.Title(
                            "{}".format(traj_id),
                            order=1,
                            style={"color": "#15284F"},
                        ),
                        width=10,
                    ),
                ],
                justify="start",
                align="center",
            ),
            html.Div(
                dmc.Badge(
                    classification,
                    color=class_colors[classification],
                    variant="dot",
                )
            ),
            dcc.Markdown(
                """
                ```python
                Discovery date: {}
                Last detection: {}
                Number of detections: {}
                ```
                """.format(
                    discovery_date, date_end, ndet
                )
            ),
        ],
        radius="xl",
        p="md",
        shadow="xl",
        withBorder=True,
    )

    return [card, html.Div(id="ssotraj_card")]



def get_cutout(objId_list):

    print(objId_list)

    # get data for many objects
    r = requests.post(
        'https://fink-portal.org/api/v1/objects',
        json={
            'objectId': ','.join(objId_list),
            'output-format': 'json',
            'columns': "i:objectId,b:cutoutScience_stampData,b:cutoutTemplate_stampData,b:cutoutDifference_stampData"
        }
    )

    print(r.content)

    # Format output in a DataFrame
    pdf = pd.read_json(r.content)

    print(pdf)

    return pdf


def lc_tab_content(pdf_lc):
    hovertemplate = r"""
    <b>%{yaxis.title.text}</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
    <b>mjd</b>: %{customdata}
    <extra></extra>
    """

    to_plot = []

    label_band = ["g band", "r band"]
    def data_band(band):
        cond = pdf_lc["d:fid"] == band

        date = pdf_lc[cond]["d:jd"].apply(lambda x: convert_jd(float(x), to="iso"))
        mag = pdf_lc[cond]["d:dcmag"]
        err = pdf_lc[cond]["d:dcmag_err"]

        obs = {
            "x": date,
            "y": mag,
            "error_y": {
                "type": "data",
                "array": err,
                "visible": True,
                "color": COLORS_ZTF[band - 1],
            },
            "mode": "markers",
            "name": label_band[band - 1],
            "customdata": pdf_lc[cond]["d:jd"].apply(lambda x: float(x) - 2400000.5),
            "hovertemplate": hovertemplate,
            "marker": {"size": 6, "color": COLORS_ZTF[band - 1], "symbol": "o"},
        }

        to_plot.append(obs)

    data_band(1)
    data_band(2)

    figure = {"data": to_plot, "layout": layout_sso_lightcurve}
    graph = dcc.Graph(
        figure=figure,
        style={"width": "100%", "height": "25pc"},
        config={"displayModeBar": False},
    )
    card = dmc.Paper(graph, radius="xl", p="md", shadow="xl", withBorder=True)

    # objId_list = ",".join(pdf_lc["d:objectId"].values)
    # cutout_pdf = get_cutout(objId_list)

    # cols = ['b:cutoutScience_stampData', 'b:cutoutTemplate_stampData', 'b:cutoutDifference_stampData']

    # items = [
    #     {
    #         "key": str(id), 
    #         "src": readstamp(cutout_pdf[col].values[0])
    #     }
    #     for id, col in zip(cols, np.arange(len(cols)))
    # ]

    # traj_summary_layout = html.Div([
    #     dbc.Row([
    #         dbc.Col([
    #             card,
    #             html.Br(),
    #             dbc.Carousel(
    #             items=[
    #                 {"key": "1", "src": "/static/images/slide1.svg"},
    #                 {"key": "2", "src": "/static/images/slide2.svg"},
    #                 {"key": "3", "src": "/static/images/slide3.svg"},
    #             ],
    #             controls=False,
    #             indicators=False,
    #             interval=2000,
    #             ride="carousel",
    #         )
    #         ])
    #     ])
    # ])


    return card


def astr_tab_content(pdf_lc):
    hovertemplate = r"""
    <b>Observation date</b>: %{customdata}<br>
    <extra></extra>
    """

    ra = pdf_lc["d:ra"]
    dec = pdf_lc["d:dec"]
    date = pdf_lc["d:jd"].apply(lambda x: convert_jd(float(x), to="iso"))

    layout_sso_radec = dict(
        margin=dict(l=50, r=30, b=0, t=0),
        hovermode="closest",
        hoverlabel={"align": "left"},
        legend=dict(
            font=dict(size=10),
            orientation="h",
            xanchor="right",
            x=1,
            y=1.2,
            bgcolor="rgba(218, 223, 225, 0.3)",
        ),
        yaxis={"title": "Declination", "automargin": True},
        xaxis={"autorange": "reversed", "title": "Right Ascension", "automargin": True},
    )

    fig = go.Figure(
        data=[
            go.Scatter(
                x=ra.values,
                y=dec.values,
                mode="markers",
                customdata=date.values,
                hovertemplate=hovertemplate,
                marker={"size": 6, "color": colors_[0], "symbol": "circle"},
            )
        ],
        layout=layout_sso_radec,
    )

    def makeArrow(x_start, y_start, x_end, y_end):
        return go.layout.Annotation(
            dict(
                x=x_end,
                y=y_end,
                xref="x",
                yref="y",
                text="",
                showarrow=True,
                axref="x",
                ayref="y",
                ax=x_start,
                ay=y_start,
                arrowhead=5,
                arrowwidth=1.5,
                arrowcolor="rgb(255,51,0)",
            )
        )

    annotations = [
        makeArrow(ra_s, dec_s, ra_e, dec_e)
        for ra_s, dec_s, ra_e, dec_e in zip(ra[:-1], dec[:-1], ra[1:], dec[1:])
    ]

    fig.update_layout(
        annotations=annotations,
    )

    graph = dcc.Graph(
        figure=fig,
        style={"width": "100%", "height": "25pc"},
        config={"displayModeBar": False},
    )

    card = dmc.Paper(graph, radius="xl", p="md", shadow="xl", withBorder=True)

    astr_layout = html.Div(
        [dbc.Row(
            [
                dbc.Col(
                    [
                        card,
                        html.Br(),
                        html.Div(
                            [visdcc.Run_js(id='aladin-sso-lite')],
                            style={
                                'width': '100%',
                                'height': '50pc',
                            }
                        ),
                        html.Br(),
                        html.Br(),
                        html.Br(),
                    ]
                )
            ]
        )]
    )

    return astr_layout


@app.callback(
    Output("dynamic_graph", "children"),
    [Input("dynamic_radio", "value"), Input("traj_lc", "data")],
)
def dyn_tab_content(v_radio, json_lc):
    hovertemplate = r"""
    <b>%{yaxis.title.text}</b>: %{y:.2f}<br>
    <extra></extra>
    """

    pdf_lc = pd.read_json(json_lc)

    ra, dec, jd = (
        pdf_lc["d:ra"].values,
        pdf_lc["d:dec"].values,
        (pdf_lc["d:jd"].values * 24),
    )
    coord = SkyCoord(ra, dec, unit=u.degree)

    ast_speed = coord[:-1:].separation(coord[1::]).arcminute / np.diff(jd)

    if v_radio == "speed":
        mean_speed = np.round(np.mean(ast_speed), 3)
        obs = {
            "x": np.arange(len(ast_speed)),
            "y": ast_speed,
            "hovertemplate": hovertemplate,
        }
        dyn_layout = layout_ssocand_speed
    elif v_radio == "acceleration":
        ast_acc = np.diff(ast_speed) / np.diff(np.diff(jd))
        mean_acc = np.round(np.mean(ast_acc), 3)
        obs = {
            "x": np.arange(len(ast_acc)),
            "y": ast_acc,
            "hovertemplate": hovertemplate,
        }
        dyn_layout = layout_ssocand_acceleration
    else:
        raise PreventUpdate

    figure = {"data": [obs], "layout": dyn_layout}

    graph = dcc.Graph(
        figure=figure,
        style={"width": "100%", "height": "25pc"},
        config={"displayModeBar": False},
    )

    card = dmc.Paper(graph, radius="xl", p="md", shadow="xl", withBorder=True)

    return card


def orb_tab_content(pdf_orb):

    a = pdf_orb["d:a"].values[0] << u.AU
    ecc = pdf_orb["d:e"].values[0] << u.one
    inc = pdf_orb["d:i"].values[0] << u.deg
    raan = pdf_orb["d:long_node"].values[0] << u.deg
    argp = pdf_orb["d:arg_peric"].values[0] << u.deg
    nu = pdf_orb["d:mean_anomaly"].values[0] << u.deg

    orb = Orbit.from_classical(Sun, a, ecc, inc, raan, argp, nu)

    jupyter_distance = 5.4570 << u.AU

    frame = plot_solar_system(
        outer=a > jupyter_distance,
        # epoch=Time(pdf_orb["d:ref_epoch"].values[0], format="jd"), # not working
        use_3d=True,
        interactive=True,
    )

    frame.plot(
        orb,
        label="{}".format(pdf_orb["d:ssoCandId"].values[0]),
        color="red",
    )

    graph = dcc.Graph(
        figure=frame._figure,
        style={"width": "100%", "height": "25pc"},
        config={"displayModeBar": False},
    )
    card = dmc.Paper(graph, radius="xs", p="md", shadow="xl", withBorder=True, style={"height":"30pc"})

    return card


@app.callback(
    Output("sso_tabs", "children"),
    [Input("traj_lc", "data"), Input("traj_orb", "data")],
)
def tabs(json_lc, json_orb):

    pdf_lc = pd.read_json(json_lc)
    pdf_orb = pd.read_json(json_orb)

    dynamic_tab = [
        dcc.RadioItems(["speed", "acceleration"], "speed", id="dynamic_radio"),
        html.Div(id="dynamic_graph"),
    ]

    tabs_ = dmc.Tabs(
        [
            dmc.Tab(lc_tab_content(pdf_lc), label="Lightcurve"),
            dmc.Tab(astr_tab_content(pdf_lc), label="Astrometry"),
            dmc.Tab(dynamic_tab, label="Dynamics"),
            dmc.Tab(orb_tab_content(pdf_orb), label="Orbit"),
        ],
        position="right",
        variant="outline",
    )
    return tabs_


def card_ssotraj_params(pdf_orb):

    """Orbit parameters"""
    template = """
    ```python
    # Properties computed by OrbFit
    a (AU): {}
    rms_a: {}
    e: {}
    rms_e: {}
    inc (deg): {}
    rms_inc: {}
    Omega (deg): {}
    rms_Omega: {}
    argPeri (deg): {}
    rms_argPeri: {}
    meanAnomaly (deg): {}
    rms_meanAnomaly: {}
    ```
    """

    header = [
        html.H5(
            "Id: {}".format(pdf_orb["d:ssoCandId"].values[0]),
            className="card-title",
        ),
        html.H6(
            "epoch (JD): {}".format(isoify_time(pdf_orb["d:ref_epoch"].values[0])),
            className="card-subtitle",
        ),
    ]

    card = html.Div(
        [
            *header,
            dcc.Markdown(
                template.format(
                    pdf_orb["d:a"].values[0],
                    pdf_orb["d:rms_a"].values[0],
                    pdf_orb["d:e"].values[0],
                    pdf_orb["d:rms_e"].values[0],
                    pdf_orb["d:i"].values[0],
                    pdf_orb["d:rms_i"].values[0],
                    pdf_orb["d:long_node"].values[0],
                    pdf_orb["d:rms_long_node"].values[0],
                    pdf_orb["d:arg_peric"].values[0],
                    pdf_orb["d:rms_arg_peric"].values[0],
                    pdf_orb["d:mean_anomaly"].values[0],
                    pdf_orb["d:rms_mean_anomaly"].values[0],
                )
            ),
        ],
    )

    return card


@app.callback(Output("ssotraj_card", "children"), [Input("traj_orb", "data")])
def construct_ssotraj_card(json_orb):
    pdf_orb = pd.read_json(json_orb)

    python_download = """
import requests
import pandas as pd
import io

# get data for ZTF19acnjwgm
r = requests.post(
        '{}/api/v1/ssocand',
        json={{
            'kind': 'lightcurves', # Mandatory, `orbParams` or `lightcurves`
            'ssoCandId': {},
            'output-format': 'json'
        }}
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))""".format(
        APIURL, pdf_orb["d:ssoCandId"].values[0]
    )

    curl_download = """Not available"""

    download_tab = dmc.Tabs(
        color="red",
        children=[
            dmc.Tab(
                label="Python",
                children=dmc.Prism(children=python_download, language="python"),
            ),
            dmc.Tab(
                label="Curl",
                children=dmc.Prism(children=curl_download, language="bash"),
            ),
        ],
    )

    extra_items = [
        dmc.AccordionItem(
            [
                dmc.Paper(
                    download_tab, radius="xl", p="md", shadow="xl", withBorder=True
                )
            ],
            label="Download data",
            icon=[
                DashIconify(
                    icon="tabler:database-export",
                    color=dmc.theme.DEFAULT_COLORS["red"][6],
                    width=20,
                )
            ],
        )
    ]

    card = dmc.Accordion(
        state={"0": True, **{"{}".format(i + 1): False for i in range(4)}},
        multiple=True,
        offsetIcon=False,
        disableIconRotation=True,
        children=[
            dmc.AccordionItem(
                [
                    dmc.Paper(
                        children=card_ssotraj_params(pdf_orb),
                        id="ssotraj_params",
                        radius="xl",
                        p="md",
                        shadow="xl",
                        withBorder=True,
                    )
                ],
                label="SSO card",
                icon=[
                    DashIconify(
                        icon="majesticons:comet",
                        color=dmc.theme.DEFAULT_COLORS["dark"][6],
                        width=20,
                    )
                ],
            ),
            *extra_items,
        ],
    )

    return card


def layout(is_mobile):
    """ """

    if is_mobile:
        layout_ = html.Div(
            [
                html.Br(),
                html.Br(),
                dbc.Container(id="stat_row_mobile"),
                html.Br(),
                html.Div(id="object-stats", style={"display": "none"}),
            ],
            className="home",
            style={
                "background-image": "linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(/assets/background.png)",
                "background-size": "contain",
            },
        )
    else:
        layout_ = html.Div(
            [
                html.Br(),
                html.Br(),
                html.Br(),
                html.Br(),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Br(),
                                html.Div(id="card_traj_left"),
                                html.Br(),
                                html.Br(),
                                html.Br(),
                            ],
                            width={"size": 3},
                        ),
                        dbc.Col(id="sso_tabs", width=8),
                    ],
                    justify="around",
                    className="g-0",
                ),
                dcc.Store("traj_lc"),
                dcc.Store("traj_orb"),
            ],
            className="home",
            style={
                "background-image": "linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(/assets/background.png)",
                "background-size": "contain",
            },
        )

    return layout_

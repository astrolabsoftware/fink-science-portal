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
import base64

from apps.utils import class_colors, isoify_time, convert_jd, readstamp
from apps.plotting import (
    COLORS_ZTF,
    layout_sso_lightcurve,
    colors_,
    layout_ssocand_speed,
    layout_ssocand_acceleration,
    sigmoid_normalizer,
    convolve,
)

import plotly.graph_objs as go

from poliastro.twobody import Orbit
from poliastro.plotting.misc import plot_solar_system
from poliastro.bodies import Sun

from PIL import Image


def get_cutout(objId_list):

    # get data for many objects
    r = requests.post(
        "https://fink-portal.org/api/v1/objects",
        json={
            "objectId": ",".join(objId_list),
            "output-format": "json",
            "withcutouts": "True",
            # "columns": "i:objectId,i:jd,b:cutoutScience_stampData,b:cutoutTemplate_stampData,b:cutoutDifference_stampData",
        },
    )

    # Format output in a DataFrame
    pdf = pd.read_json(r.content)

    return pdf


@app.callback(
    [Output("traj_lc", "data"), Output("traj_orb", "data"), Output("traj_img", "data")],
    [Input("url", "pathname")],
)
def store_traj_data(pathname):
    traj_id = pathname.split("_")[-1]

    r_lc = requests.post(
        "https://fink-portal.org/api/v1/ssocand",
        json={
            "kind": "lightcurves",  # Mandatory, `orbParams` or `lightcurves`
            "ssoCandId": traj_id,
        },
    )

    # Format output in a DataFrame
    pdf_lc = pd.read_json(io.BytesIO(r_lc.content))

    r_orb = requests.post(
        "https://fink-portal.org/api/v1/ssocand",
        json={
            "kind": "orbParams",  # Mandatory, `orbParams` or `lightcurves`
            "ssoCandId": traj_id,
        },
    )

    # Format output in a DataFrame
    pdf_orb = pd.read_json(io.BytesIO(r_orb.content))

    pdf_cutout = get_cutout(pdf_lc["d:objectId"].values)

    return pdf_lc.to_json(), pdf_orb.to_json(), pdf_cutout.to_json()


@app.callback(
    Output("drawer_objectId", "opened"),
    Input("open_objectId_drawer", "n_clicks"),
    prevent_initial_call=True,
)
def drawer_objectId_open(n_clicks):
    return True


def plot_sso_timeline_classbar(pdf, is_mobile):
    """Display a bar chart with individual alert classifications for the objectId timeline

    Parameters
    ----------
    pdf: pandas data
        cached alert data
    is_mobile: bool
        True if mobile plateform, False otherwise.
    """
    grouped = pdf.groupby("v:classification").count()
    alert_per_class = grouped["i:objectId"].to_dict()

    # descending date values
    top_labels = pdf["v:classification"].values# [::-1]
    customdata = (
        pdf["i:jd"].apply(lambda x: convert_jd(float(x), to="iso")).values# [::-1]
    )
    x_data = [[1] * len(top_labels)]
    y_data = top_labels

    palette = dmc.theme.DEFAULT_COLORS

    colors = [
        palette[class_colors["Simbad"]][6]
        if j not in class_colors.keys()
        else palette[class_colors[j]][6]
        for j in top_labels
    ]

    fig = go.Figure()

    is_seen = []
    for i in range(0, len(x_data[0])):
        for xd, yd, label in zip(x_data, y_data, top_labels):
            if top_labels[i] in is_seen:
                showlegend = False
            else:
                showlegend = True
            is_seen.append(top_labels[i])

            percent = np.round(alert_per_class[top_labels[i]] / len(pdf) * 100).astype(
                int
            )
            if is_mobile:
                name_legend = top_labels[i]
            else:
                name_legend = top_labels[i] + ": {}%".format(percent)
            fig.add_trace(
                go.Bar(
                    x=[xd[i]],
                    y=[yd],
                    orientation="h",
                    width=0.3,
                    showlegend=showlegend,
                    legendgroup=top_labels[i],
                    name=name_legend,
                    marker=dict(
                        color=colors[i],
                    ),
                    customdata=[customdata[i]],
                    hovertemplate="<b>Date</b>: %{customdata}",
                )
            )

    if is_mobile:
        legend_shift = 0.0
    else:
        legend_shift = 0.2
    fig.update_layout(
        xaxis=dict(
            showgrid=False,
            showline=False,
            showticklabels=False,
            zeroline=False,
        ),
        yaxis=dict(
            showgrid=False,
            showline=False,
            showticklabels=False,
            zeroline=False,
        ),
        legend=dict(
            bgcolor="rgba(255, 255, 255, 0)",
            bordercolor="rgba(255, 255, 255, 0)",
            orientation="h",
            traceorder="reversed",
            yanchor="bottom",
            itemclick=False,
            itemdoubleclick=False,
            x=legend_shift,
        ),
        barmode="stack",
        dragmode=False,
        paper_bgcolor="rgb(248, 248, 255, 0.0)",
        plot_bgcolor="rgb(248, 248, 255, 0.0)",
        margin=dict(l=0, r=0, b=0, t=0),
    )
    if not is_mobile:
        fig.update_layout(title_text="Alert classification")
        fig.update_layout(title_y=0.15)
        fig.update_layout(title_x=0.0)
        fig.update_layout(title_font_size=12)
    if is_mobile:
        fig.update_layout(legend=dict(font=dict(size=10)))
    return fig


@app.callback(Output("drawer_objectId", "children"), Input("traj_img", "data"))
def construct_objectId_drawer(cutout_json):

    pdf_cutout = pd.read_json(cutout_json).sort_values("i:jd")

    all_timeline_items = [
        dmc.TimelineItem(
            title=objId,
            children=[
                dmc.Text(
                    [
                        "{}".format(Time(pdf_cutout[(pdf_cutout["i:objectId"] == objId) & (pdf_cutout["v:classification"] == "Solar System candidate")]["i:jd"].values[0], format="jd").iso)
                    ],
                    color="dimmed",
                    size="sm",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            dcc.Graph(
                                figure=plot_sso_timeline_classbar(pdf_cutout[pdf_cutout["i:objectId"] == objId], False),
                                style={"width": "100%", "height": "4pc"},
                                config={"displayModeBar": False},
                            ),
                            width=12,
                        ),
                    ],
                    justify="around",
                ),
                dmc.Text(
                    [
                        "View in ",
                        dmc.Anchor(
                            "Fink",
                            href="https://fink-portal.org/{}".format(objId),
                            size="sm",
                        ),
                    ],
                    color="dimmed",
                    size="sm",
                ),
            ],
        )
        for objId in pdf_cutout["i:objectId"].unique()
    ]

    return html.Div(
        [
            dmc.Timeline(
                active=1, bulletSize=15, lineWidth=2, children=all_timeline_items
            ),
            html.Br(),
            html.Br(),
            html.Br(),
        ],
        style={"overflow": "scroll", "height": "100%"}
    )


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
            dmc.Button("ObjectId Timeline", id="open_objectId_drawer"),
            dmc.Drawer(
                title="ObjectId Trajectory Timeline",
                id="drawer_objectId",
                lockScroll = False,
                padding="md",
                size="40%"
            ),
        ],
        radius="xl",
        p="md",
        shadow="xl",
        withBorder=True
    )

    return [card, html.Div(id="ssotraj_card")]


def convert_img_to_base64(img):
    """

    Parameters
    ----------
    img : numpy array
        image
    """

    if img.dtype == object:
        img = img.astype(float)

    img = np.nan_to_num(img)
    img_type = img.dtype
    img[img == None] = 0
    img = img.astype(img_type)

    data = sigmoid_normalizer(img, 0, 255)

    data = data[::-1]
    data = convolve(data, smooth=1, kernel="gauss")

    im = Image.fromarray(data)
    im = im.convert("L")

    in_mem_file = io.BytesIO()
    im.save(in_mem_file, format="PNG")

    in_mem_file.seek(0)
    img_bytes = in_mem_file.read()

    return base64.b64encode(img_bytes)


def build_carousel(pdf_cutout, kind):

    pdf_cutout = pdf_cutout.sort_values("i:jd")

    get_col_name = {
        "Science": "b:cutoutScience_stampData",
        "Template": "b:cutoutTemplate_stampData",
        "Difference": "b:cutoutDifference_stampData",
    }

    base64_imgs = [
        convert_img_to_base64(np.array(pdf_cutout[get_col_name[kind]].values[idx]))
        for idx in np.arange(len(pdf_cutout))
    ]

    items = [
        {"key": str(id), "src": "data:image/jpg;base64,{}".format(b64_img.decode())}
        for b64_img in base64_imgs
    ]

    carousel = html.Div(
        [
            dbc.Col(
                [
                    html.H4(html.B(kind)),
                    dbc.Carousel(
                        id="carousel_{}".format(kind),
                        items=items,
                        controls=True,
                        indicators=True,
                        slide=False,
                    ),
                ]
            )
        ],
        style={
            "width": "20pc",
            "height": "20pc",
        },
    )

    return carousel


@app.callback(
    [
        Output("carousel_Science", "active_index"),
        Output("carousel_Template", "active_index"),
        Output("carousel_Difference", "active_index"),
    ],
    Input("drop_jd", "value"),
)
def select_slide(idx):
    return int(idx), int(idx), int(idx)


def build_img_drop(pdf_cutout):

    pdf_cutout = pdf_cutout.sort_values("i:jd")

    dropdown = dmc.Select(
        id="drop_jd",
        label="Menu",
        value="0",
        data=[
            {"value": "{}".format(idx), "label": "{}".format(Time(jd, format="jd").iso)}
            for idx, jd in zip(np.arange(len(pdf_cutout)), pdf_cutout["i:jd"].values)
        ],
        style={"width": "15pc"},
    )
    return dropdown


def lc_tab_content(pdf_lc, pdf_cutout):
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

    traj_summary_layout = html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        [
                            card,
                            html.Br(),
                            dbc.Row(
                                [
                                    build_carousel(pdf_cutout, "Science"),
                                    build_carousel(pdf_cutout, "Template"),
                                    build_carousel(pdf_cutout, "Difference"),
                                    build_img_drop(pdf_cutout),
                                ]
                            ),
                            html.Br(),
                            html.Br(),
                            html.Br(),
                        ]
                    )
                ]
            )
        ]
    )

    return traj_summary_layout


@app.callback(
    Output('aladin-sso-lite', 'run'), 
    [
        Input('traj_lc', 'data'), 
        Input("sso_summary_tabs", "active-tab")
    ]
)
def integrate_sso_aladin(lc_json, active_tab):
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

    if len(lc_json) > 0:
        pdf_lc = pd.read_json(lc_json)

        # Coordinate of the current alert
        ra0 = pdf_lc['d:ra'].values[0]
        dec0 = pdf_lc['d:dec'].values[0]

        ssocand_markers = """
            var sso_cat = A.catalog({{name: 'ssoCand markers', sourceSize: 18, onClick: 'showPopup', color: '{}'}});\n
            aladin.addCatalog(sso_cat);\n
            """.format(class_colors['Solar System trajectory'])

        for ra, dec, jd, objectId in zip(pdf_lc['d:ra'], pdf_lc['d:dec'], pdf_lc["d:jd"], pdf_lc["d:objectId"]):

            ssocand_markers += """
            sso_cat.addSources(
                [A.marker({}, {}, 
                {{
                    popupTitle: '{}', 
                    popupDesc: 'More info in <a target="_blank" href="https://fink-portal.org/{}"> Fink</a>'
                }})]);\n
            """.format(ra, dec, objectId, objectId)

            ssocand_markers += """aladin.addCatalog(A.catalogFromSkyBot({}, {}, {}, {}, {{"-loc": 'I41'}}, {{sourceSize: 10, onClick: "showTable", shape: "plus", displayLabel: true, labelColumn: 'Name', labelColor: '#ae4', labelFont: '12px sans-serif'}}));\n""".format(ra, dec, 1/60, jd)


        # Javascript. Note the use {{}} for dictionary
        img = """
        var container = document.getElementById('aladin-sso-lite');
        var txt = '';
        container.innerHTML = txt;

        var aladin = A.aladin(
            '#aladin-sso-lite',
            {{
                survey: 'P/PanSTARRS/DR1/color/z/zg/g',
                fov: 0.025,
                target: '{} {}',
                reticleColor: '#ff89ff',
                reticleSize: 32
            }}
        );""".format(ra0, dec0)

        img += ssocand_markers

        # img cannot be executed directly because of formatting
        # We split line-by-line and remove comments
        img_to_show = [i for i in img.split('\n') if '// ' not in i]

        return " ".join(img_to_show)
    else:
        return ""


def display_sso_skymap():

    return dbc.Container(html.Div(
        [visdcc.Run_js(id="aladin-sso-lite")],
        style={
            "width": "100%",
            "height": "50pc",
        },
    ))


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
        [
            dbc.Row(
                [
                    dbc.Col(
                        [
                            card,
                            html.Br(),
                            display_sso_skymap(),
                            html.Br(),
                            html.Br(),
                            html.Br(),
                        ]
                    )
                ]
            )
        ]
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

    orb = Orbit.from_classical(
        Sun,
        a,
        ecc,
        inc,
        raan,
        argp,
        nu,
        epoch=Time(pdf_orb["d:ref_epoch"].values[0], format="jd"),
    )

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

    orbit_figure = frame._figure

    astro_unit = 149597870.700

    if a > jupyter_distance:
        tick_vals = [i * astro_unit for i in np.arange(-100, 100, 10)]
        tick_texts = ["{:.3f}".format(i) for i in np.arange(-100, 100, 10)]
    else:
        tick_vals = [i * astro_unit for i in np.arange(-10, 10, 0.4)]
        tick_texts = ["{:.3f}".format(i) for i in np.arange(-10, 10, 0.4)]

    orbit_figure.update_layout(
        margin=dict(l=5, r=5, t=5, b=5),
        paper_bgcolor="LightSteelBlue",
        legend=dict(
            title="Solar System legend",
            title_font_family="Times New Roman",
            font=dict(family="Courier", size=16, color="black"),
            bgcolor="LightSteelBlue",
            bordercolor="Black",
            borderwidth=2,
        ),
        scene=dict(
            xaxis_title="x (AU)",
            yaxis_title="y (AU)",
            zaxis_title="z (AU)",
            xaxis=dict(tickmode="array", tickvals=tick_vals, ticktext=tick_texts),
            yaxis=dict(tickmode="array", tickvals=tick_vals, ticktext=tick_texts),
            zaxis=dict(tickmode="array", tickvals=tick_vals, ticktext=tick_texts),
        ),
    )

    graph = dcc.Graph(
        figure=orbit_figure,
        style={"height": "100%"},
        config={"displayModeBar": False},
    )
    card = dmc.Paper(
        graph,
        radius="xs",
        p="md",
        shadow="xl",
        withBorder=True,
        style={"height": "50pc"},
    )

    return card


@app.callback(
    Output("sso_tabs", "children"),
    [Input("traj_lc", "data"), Input("traj_orb", "data"), Input("traj_img", "data")],
)
def tabs(json_lc, json_orb, json_cutout):

    pdf_lc = pd.read_json(json_lc)
    pdf_orb = pd.read_json(json_orb)
    pdf_cutout = pd.read_json(json_cutout)

    dynamic_tab = [
        dcc.RadioItems(["speed", "acceleration"], "speed", id="dynamic_radio"),
        html.Div(id="dynamic_graph"),
    ]

    tabs_ = dbc.Tabs(
        [
            dbc.Tab(lc_tab_content(pdf_lc, pdf_cutout), label="Lightcurve", tab_id='t0'),
            dbc.Tab(astr_tab_content(pdf_lc), label="Astrometry", tab_id='t1'),
            dbc.Tab(dynamic_tab, label="Dynamics", tab_id='t2'),
            dbc.Tab(orb_tab_content(pdf_orb), label="Orbit", tab_id='t3'),
        ],
        id="sso_summary_tabs",
        # position="right",
        # variant="outline",
        active_tab='t0'
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
        'ssoCandId': "{}",
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
                html.Br(),
                dcc.Store("traj_lc"),
                dcc.Store("traj_orb"),
                dcc.Store("traj_img"),
            ],
            className="home",
            style={
                "background-image": "linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(/assets/background.png)",
                "background-size": "contain",
            },
        )

    return layout_

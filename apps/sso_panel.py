from cProfile import label
import pandas as pd
import numpy as np
import io
import requests
import random
import math

from app import app, clientStats
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, dash_table, State
import dash_mantine_components as dmc

from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from apps.utils import markdownify_objectid, random_color, class_colors

import plotly.graph_objs as go
import plotly.express as px

from astropy.time import Time
from astroquery.imcce import Skybot
from astropy.coordinates import SkyCoord
from astropy.time import Time
import astropy.units as u


@app.callback(Output("pdf_lc", "data"), [Input("url", "pathname")])
def store_lighcurves_query(name):
    """Cache query results (sso trajectories and lightcurves) for easy re-use

    https://dash.plotly.com/sharing-data-between-callbacks
    """

    r_lc = requests.post(
        "https://fink-portal.org/api/v1/ssocand",
        json={
            "kind": "lightcurves",  # Mandatory, `orbParams` or `lightcurves`
        },
    )

    # Format output in a DataFrame
    pdf_lc = pd.read_json(io.BytesIO(r_lc.content)).drop_duplicates("d:candid")

    return pdf_lc.to_json()


@app.callback(Output("pdf_orb", "data"), [Input("url", "pathname")])
def store_orbit_query(url):
    """Cache query results (sso trajectories and lightcurves) for easy re-use

    https://dash.plotly.com/sharing-data-between-callbacks
    """

    # pdf_lc = pd.read_json(json_lc)

    r_orb = requests.post(
        "https://fink-portal.org/api/v1/ssocand",
        json={
            "kind": "orbParams",  # Mandatory, `orbParams` or `lightcurves`
        },
    )

    # Format output in a DataFrame
    pdf_orb = pd.read_json(io.BytesIO(r_orb.content)).drop_duplicates(
        ["d:a", "d:e", "d:i"]
    )
    # pdf_orb = pdf_orb[pdf_orb["d:trajectory_id"].isin(pdf_lc["d:trajectory_id"])]

    return pdf_orb.to_json()


@app.callback(Output("mpc_data", "data"), [Input("url", "pathname")])
def load_mpc(url):

    mpc_ae = pd.read_parquet("data/ae_mpc.parquet")
    return mpc_ae.to_json()


def populate_sso_table(data, columns):
    """Define options of the results table, and add data and columns"""

    page_size = 10
    markdown_options = {"link_target": "_blank"}

    table = dash_table.DataTable(
        data=data,
        columns=columns,
        id="sso_lc_table",
        page_size=page_size,
        style_as_list_view=True,
        sort_action="native",
        filter_action="native",
        markdown_options=markdown_options,
        fixed_columns={"headers": True, "data": 1},
        style_data={"backgroundColor": "rgb(248, 248, 248, .7)"},
        style_table={"maxWidth": "100%"},
        style_cell={"padding": "5px", "textAlign": "center", "overflow": "hidden"},
        style_data_conditional=[
            {
                "if": 
                    {"row_index": "odd"}, 
                "backgroundColor": "rgb(248, 248, 248, .7)"
            }
        ],
        style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"},
    )
    return table


def display_table_results(table):

    return dbc.Container(
        [
            dcc.RadioItems(["Trajectory", "Orbit"], "Trajectory", id="sso-orb-radio"),
            table,
        ]
    )


@app.callback(
    [Output("sso_lc_table", "data"), Output("sso_lc_table", "columns")],
    [
        Input("sso-orb-radio", "value"),
        Input("pdf_orb", "data"),
        Input("pdf_lc", "data"),
    ],
    [State("sso_lc_table", "data"), State("sso_lc_table", "columns")],
)
def update_sso_table(orb_v_radio, json_orb, json_lc, data, columns):

    markdown_trajid = lambda traj_id: markdownify_objectid(
        traj_id, "trajid_{}".format(traj_id)
    )
    if orb_v_radio == "Orbit":
        pdf_orb = pd.read_json(json_orb).sort_values(["d:ssoCandId", "d:ref_epoch"])
        pdf_orb["d:ssoCandId"] = pdf_orb["d:ssoCandId"].apply(markdown_trajid)
        pdf_orb = pdf_orb.to_dict("records")

        colnames_to_display = [
            "d:ssoCandId",
            "d:ref_epoch",
            "d:a",
            "d:rms_a",
            "d:e",
            "d:rms_e",
            "d:i",
            "d:rms_i",
        ]

        columns = [
            {
                "id": c,
                "name": c,
                "type": "text",
                # 'hideable': True,
                "presentation": "markdown",
            }
            for c in colnames_to_display
        ]

        return pdf_orb, columns

    elif orb_v_radio == "Trajectory":
        original_pdf = pd.DataFrame.from_dict(data)
        if "d:jd" in original_pdf:
            raise PreventUpdate

        pdf_lc = pd.read_json(json_lc).sort_values(["d:ssoCandId", "d:jd"])
        pdf_lc["d:ssoCandId"] = pdf_lc["d:ssoCandId"].apply(markdown_trajid)
        pdf_lc = pdf_lc.to_dict("records")

        colnames_to_display = ["d:ssoCandId", "d:jd", "d:candid", "d:ra", "d:dec"]

        columns = [
            {
                "id": c,
                "name": c,
                "type": "text",
                # 'hideable': True,
                "presentation": "markdown",
            }
            for c in colnames_to_display
        ]

        return pdf_lc, columns

    else:
        raise PreventUpdate


@app.callback(
    Output("table_lc_res", "children"),
    [Input("pdf_lc", "data")],
)
def results(json_lc):

    pdf_lc = pd.read_json(json_lc).sort_values(["d:ssoCandId", "d:jd"])
    pdf_lc["d:ssoCandId"] = pdf_lc["d:ssoCandId"].apply(
        lambda traj_id: markdownify_objectid(traj_id, "trajid_{}".format(traj_id))
    )
    pdf_lc = pdf_lc.to_dict("records")
    colnames_to_display = ["d:ssoCandId", "d:jd", "d:candid", "d:ra", "d:dec"]

    columns = [
        {
            "id": c,
            "name": c,
            "type": "text",
            # 'hideable': True,
            "presentation": "markdown",
        }
        for c in colnames_to_display
    ]

    table = populate_sso_table(pdf_lc, columns)
    return dbc.Container([html.Br(), display_table_results(table)])


def construct_sso_stat_figure(pdf_orb, mpc_ae, xdata, ydata):

    xcand_data = pdf_orb["d:{}".format(xdata)].values
    ycand_data = pdf_orb["d:{}".format(ydata)].values

    is_distant = mpc_ae["Orbit_type"] == "Distant Object"

    no_distant = mpc_ae[~is_distant]
    distant = mpc_ae[is_distant]

    data = []
    for orb_type in mpc_ae["Orbit_type"].unique():
        tmp_df = no_distant[no_distant["Orbit_type"] == orb_type]
        x = tmp_df[xdata]
        y = tmp_df[ydata]
        data.append(
            go.Scattergl(
                x=x,
                y=y,
                mode="markers",
                name=orb_type,
                opacity=0.5
                # marker=dict(color=random_color()[2])
            )
        )

    data.append(
        go.Scattergl(
            x=distant[xdata],
            y=distant[ydata],
            mode="markers",
            name=distant["Orbit_type"].values[0],
            visible="legendonly",
            opacity=0.5,
            marker=dict(color="rgba(152, 0, 0, .5)"),
        )
    )

    data.append(
        go.Scattergl(
            x=xcand_data,
            y=ycand_data,
            mode="markers",
            name="Fink SSO candidates",
            marker=dict(
                size=10,
                line=dict(color="rgba(70, 138, 94, 0.5)", width=2),
                color="rgba(111, 235, 154, 0.5)",
            ),
        )
    )

    custom_title = {
        "a": "semi major axis (AU)",
        "e": "eccentricity",
        "i": "inclination (degree)",
    }

    layout_sso_ae = dict(
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
        yaxis={"title": custom_title[ydata], "automargin": True},
        xaxis={"title": custom_title[xdata], "automargin": True},
    )

    return {"data": data, "layout": layout_sso_ae}


@app.callback(
    Output("ae_distrib", "children"),
    [Input("pdf_orb", "data"), Input("mpc_data", "data")],
)
def construct_ae_distrib(json_orb, json_mpc):

    pdf_orb = pd.read_json(json_orb)
    mpc_ae = pd.read_json(json_mpc)

    fig = construct_sso_stat_figure(pdf_orb, mpc_ae, "a", "e")

    graph = dcc.Graph(figure=fig, config={"displayModeBar": False}, id="stats_sso")
    card = dmc.Paper(graph, radius="xl", p="md", shadow="xl", withBorder=True)

    xaxis_drop = dcc.Dropdown(["a", "e", "i"], id="xaxis_data")

    yaxis_drop = dcc.Dropdown(["a", "e", "i"], id="yaxis_data")

    # add a time slider to filter the SSO trajectories by date in the a/e plot.

    div = html.Div([card, xaxis_drop, yaxis_drop])
    return div


@app.callback(
    Output("stats_sso", "figure"),
    [
        Input("xaxis_data", "value"),
        Input("yaxis_data", "value"),
        Input("pdf_orb", "data"),
        Input("mpc_data", "data"),
    ],
)
def change_axis(xaxis_value, yaxis_value, json_orb, json_mpc):

    if xaxis_value != None and yaxis_value != None:
        app.logger.info(xaxis_value)
        app.logger.info(yaxis_value)

        pdf_orb = pd.read_json(json_orb)
        mpc_ae = pd.read_json(json_mpc)

        fig = construct_sso_stat_figure(pdf_orb, mpc_ae, xaxis_value, yaxis_value)

        return fig
    else:
        raise PreventUpdate


def query_stats():
    name = "ztf_"

    cols = "basic:raw,basic:sci,basic:fields,basic:exposures,class:Unknown"
    results = clientStats.scan("", "key:key:{}".format(name), cols, 0, True, True)

    # Construct the dataframe
    pdf = pd.DataFrame.from_dict(results, orient="index")
    return pdf


def create_sso_stat_generic(pdf_lc):
    """Show basic stats. Used in the mobile app."""

    pdf_stats = query_stats()
    n_ = pdf_stats["key:key"].values[-1]
    night = n_[4:8] + "-" + n_[8:10] + "-" + n_[10:12]
    last_night_jd = Time(night).jd

    last_traj = pdf_lc["d:ssoCandId"].values[-1]
    last_date = Time(pdf_lc["d:jd"].values[-1], format="jd").iso.split(" ")[0]

    nb_traj = len(pdf_lc["d:ssoCandId"].unique())

    nb_traj_last_obs = len(
        pdf_lc[pdf_lc["d:jd"] >= last_night_jd]["d:ssoCandId"].unique()
    )

    c0 = [
        html.H3(html.B(night)),
        html.P("Last ZTF observing night"),
    ]

    c1 = [
        html.H3(html.B(nb_traj_last_obs)),
        html.P("Number of SSOCAND"),
        html.P("Last observing night"),
    ]

    c2 = [
        html.H3(html.B(nb_traj)),
        html.P("Number of SSOCAND trajectories"),
        html.P("since 2019/11/01 ({} observation nights)".format(len(pdf_stats))),
    ]

    return c0, c1, c2


@app.callback(Output("sso_stat_row", "children"), Input("pdf_lc", "data"))
def create_stat_row(orb_json):
    """Show basic stats. Used in the desktop app."""
    pdf = pd.read_json(orb_json)
    c0_, c1_, c2_ = create_sso_stat_generic(pdf)

    c0 = dbc.Col(
        children=c0_,
        width=2,
        style={
            "border-left": "1px solid #c4c0c0",
            "border-bottom": "1px solid #c4c0c0",
            "border-radius": "0px 0px 0px 25px",
            "text-align": "center",
        },
    )

    c1 = dbc.Col(
        children=c1_,
        width=2,
        style={
            "border-bottom": "1px solid #c4c0c0",
            # 'border-right': '1px solid #c4c0c0',
            # 'border-radius': '0px 0px 25px 0px',
            "text-align": "center",
        },
    )

    c2 = dbc.Col(
        children=c2_,
        width=2,
        style={
            "border-bottom": "1px solid #c4c0c0",
            "border-right": "1px solid #c4c0c0",
            "border-radius": "0px 0px 25px 0px",
            "text-align": "center",
        },
    )

    row = [dbc.Col(width=1), c0, c1, c2, dbc.Col(width=1)]
    return row


def sso_identify(pdf_lc):
    def skybot_request(ra, dec, jd):
        try:
            return Skybot.cone_search(
                SkyCoord(ra * u.deg, dec * u.deg), 1 * u.arcmin, jd
            ).to_pandas()
        except RuntimeError:
            return pd.DataFrame()

    skybot_result = pd.concat(
        [
            skybot_request(ra, dec, jd)
            for ra, dec, jd in zip(pdf_lc["d:ra"], pdf_lc["d:dec"], pdf_lc["d:jd"])
        ]
    )

    if len(skybot_result) > 0:

        gb_skybot = (
            skybot_result.groupby("Name")
            .agg({"RA": len, "centerdist": np.mean})
            .sort_values(["RA", "centerdist"], ascending=[False, True])
            .reset_index()
        )

        assoc_str = ""
        for ast_name, nb_assoc, dist in zip(
            gb_skybot["Name"], gb_skybot["RA"], gb_skybot["centerdist"]
        ):

            assoc_str += """
            1. Object name: {}
                - number of associated alerts: {}
                - mean distance: {} arcsecond
            """.format(
                ast_name, math.ceil(nb_assoc), np.round_(dist, decimals=2)
            )

        return dcc.Markdown(
            """
            #### Most probable association (IMCCE/SkyBot)
            """
            + assoc_str
        )
    else:
        return dcc.Markdown(
            """
            #### No credible associations (IMCCE/SkyBot)
            """
        )


def draw_new_ssocard(
    ssoCandId, ref_epoch, semi_major, semi_maj_error, ecc, ecc_error, incl, incl_error
):

    r_lc = requests.post(
        "https://fink-portal.org/api/v1/ssocand",
        json={
            "kind": "lightcurves",  # Mandatory, `orbParams` or `lightcurves`
            "ssoCandId": ssoCandId,
        },
    )

    # Format output in a DataFrame
    pdf_lc = (
        pd.read_json(io.BytesIO(r_lc.content))
        .drop_duplicates("d:candid")
        .reset_index(drop=True)
        .sort_values("d:jd")
    )

    new_detection_badge = dmc.Badge(
        "New detection",
        color=class_colors["Solar System trajectory"],
        variant="dot",
    )

    first_det_date = Time(pdf_lc.iloc[0]["d:jd"], format="jd").iso
    last_det_date = Time(pdf_lc.iloc[-1]["d:jd"], format="jd").iso

    obs_window = np.round_(pdf_lc.iloc[-1]["d:jd"] - pdf_lc.loc[0]["d:jd"], decimals=2)

    date_info = dcc.Markdown(
        """
        ```python
        Last detection: {},
        First detection: {},
        Number of detections: {},
        Observation window: {} days 
        ```
        """.format(
            first_det_date, last_det_date, len(pdf_lc), obs_window
        )
    )

    orbit_info = dcc.Markdown(
        """
        ```python
        Orbit reference epoch: {}
        semi_major axis (a): {} ± {},
        eccentricity (e): {} ± {},
        inclination (i): {} ± {}
        ```
        """.format(
            ref_epoch, semi_major, semi_maj_error, ecc, ecc_error, incl, incl_error
        )
    )

    mag_info = dict()

    for filter in pdf_lc["d:fid"].unique():
        current_fid = pdf_lc[pdf_lc["d:fid"] == filter]
        min_mag = current_fid.iloc[current_fid["d:magpsf"].argmin()][
            ["d:magpsf", "d:sigmapsf"]
        ]
        max_mag = current_fid.iloc[current_fid["d:magpsf"].argmax()][
            ["d:magpsf", "d:sigmapsf"]
        ]
        mag_info[filter] = [min_mag, max_mag]

    def return_mag_info(filter):
        if filter in mag_info:
            return "(min={} ± {}, max={} ± {})".format(
                mag_info[filter][0]["d:magpsf"],
                np.round_(mag_info[filter][0]["d:sigmapsf"], decimals=8),
                mag_info[filter][1]["d:magpsf"],
                np.round_(mag_info[filter][1]["d:sigmapsf"], decimals=8),
            )
        else:
            return "no available data"

    mag_info = dcc.Markdown(
        """
        ```python
        g band: {},
        r band: {}
        ```
        """.format(
            return_mag_info(1), return_mag_info(2)
        )
    )

    # identification_info = sso_identify(pdf_lc)

    return dmc.Paper(
        [
            dbc.Row(
                [
                    dbc.Col(
                        dmc.Avatar(src="/assets/Fink_SecondaryLogo_WEB.png", size="lg"),
                        width=1,
                    ),
                    dbc.Col(
                        dmc.Title(
                            "{}".format(ssoCandId),
                            order=1,
                            style={"color": "#15284F"},
                        ),
                        width=1,
                    ),
                ],
                justify="start",
                align="center",
            ),
            html.Div(new_detection_badge),
            dmc.Accordion(
                state={"0": True, "1": False, "2": False},
                children=[
                    dmc.AccordionItem(date_info, label="Date"),
                    dmc.AccordionItem(orbit_info, label="Orbit"),
                    dmc.AccordionItem(mag_info, label="Magnitude"),
                    #dmc.AccordionItem(identification_info, label="Identification"),
                ],
            ),
        ],
        radius="xl",
        p="md",
        shadow="xl",
        withBorder=True,
    )


@app.callback(Output("last_sso_list", "children"), Input("pdf_orb", "data"))
def last_sso_list_component(orb_json):
    orb_data = pd.read_json(orb_json)
    orb_data = orb_data.sort_values("d:ref_epoch")

    last_sso_orb = orb_data.tail().sort_values("d:ref_epoch", ascending=False)

    list_sso_paper = [
        html.Div(
            [
                html.Br(),
                draw_new_ssocard(ssoId, ref_epoch, a, a_err, e, e_err, i, i_err),
            ]
        )
        for ssoId, ref_epoch, a, a_err, e, e_err, i, i_err in zip(
            last_sso_orb["d:ssoCandId"],
            last_sso_orb["d:ref_epoch"],
            last_sso_orb["d:a"],
            last_sso_orb["d:rms_a"],
            last_sso_orb["d:e"],
            last_sso_orb["d:rms_e"],
            last_sso_orb["d:i"],
            last_sso_orb["d:rms_i"],
        )
    ]

    list_sso_paper += [html.Br()]

    sso_news_component = dbc.Container(
        [
            dmc.Title("Solar System news", order=2, align="center"),
            dbc.Container(
                list_sso_paper,
                style={"overflow": "scroll", "maxHeight": "600px", "maxWidth": "70%"},
            ),
        ]
    )

    return sso_news_component


@app.callback(Output("main_sso_panel", "children"), Input("pdf_orb", "data"))
def main_tab_layout(fake):

    return dbc.Row([dbc.Col(id="last_sso_list"), dbc.Col(id="search_sso_cand")])


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
        label_style = {"color": "#000"}
        tabs_ = dbc.Tabs(
            [
                dbc.Tab(
                    html.Div(id="main_sso_panel"),
                    label="Solar System Candidate table",
                    label_style=label_style,
                ),
                dbc.Tab(
                    html.Div(id="ae_distrib"),  # edit props
                    label="a/e distribution",
                    label_style=label_style,
                ),
            ]
        )

        layout_ = html.Div(
            [
                html.Br(),
                html.Br(),
                html.Br(),
                dbc.Row(id="sso_stat_row"),
                html.Br(),
                dbc.Row([dbc.Col(tabs_)]),
                dcc.Store(id="pdf_lc"),
                dcc.Store(id="pdf_orb"),
                dcc.Store(id="mpc_data"),
            ],
            className="home",
            style={
                "background-image": "linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(/assets/background.png)",
                "background-size": "contain",
            },
        )

    return layout_

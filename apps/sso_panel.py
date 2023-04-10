import pandas as pd
import numpy as np
import io
import requests
import math
from datetime import timedelta

from app import app, clientStats
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, dash_table, State, ctx
import dash_mantine_components as dmc

from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from apps.utils import markdownify_objectid, class_colors

import plotly.graph_objs as go

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
    pdf_lc = pd.read_json(io.BytesIO(r_lc.content))  # .drop_duplicates("d:candid")

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
    pdf_orb = pd.read_json(io.BytesIO(r_orb.content))  # .drop_duplicates(
    #     ["d:a", "d:e", "d:i"]
    # )
    # pdf_orb = pdf_orb[pdf_orb["d:trajectory_id"].isin(pdf_lc["d:trajectory_id"])]

    return pdf_orb.to_json()


@app.callback(
    Output("pdf_orb_ext", "data"), [Input("pdf_orb", "data"), Input("pdf_lc", "data")]
)
def store_orbit_extend(orb_json, lc_json):

    pdf_orb = pd.read_json(orb_json)
    pdf_lc = pd.read_json(lc_json)

    ext_values = (
        pdf_lc.sort_values("d:jd")
        .groupby("d:ssoCandId")
        .apply(
            lambda x: pd.DataFrame(
                [
                    [
                        len(x["d:ra"]),
                        x["d:jd"].values[-1] - x["d:jd"].values[0],
                        np.min(np.where(x["d:fid"] == 1, x["d:magpsf"], 50)),
                        np.max(np.where(x["d:fid"] == 1, x["d:magpsf"], -1)),
                        np.min(np.where(x["d:fid"] == 2, x["d:magpsf"], 50)),
                        np.max(np.where(x["d:fid"] == 2, x["d:magpsf"], -1)),
                    ]
                ],
                columns=["nb_det", "obs_win", "g_min", "g_max", "r_min", "r_max"],
            )
        )
    )

    ext_values = pdf_orb.merge(ext_values, on="d:ssoCandId")

    markdown_trajid = lambda traj_id: markdownify_objectid(
        traj_id, "trajid_{}".format(traj_id)
    )
    ext_values["d:ssoCandId"] = ext_values["d:ssoCandId"].apply(markdown_trajid)

    ext_values["d:isoTime"] = Time(ext_values["d:ref_epoch"], format="jd").iso

    return ext_values.to_json()


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
            {"if": {"row_index": "odd"}, "backgroundColor": "rgb(248, 248, 248, .7)"}
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

    hovertemplate = r"""
    <b>%{xaxis.title.text}</b>: %{x:.2f}<br>
    <b>%{yaxis.title.text}</b>: %{y:.2f}<br>
    <b>ssoCandId</b>: %{customdata}
    <extra></extra>
    """

    with_error = pdf_orb[pdf_orb["d:rms_a"] != -1.0]
    without_error = pdf_orb[pdf_orb["d:rms_a"] == -1.0]

    # is_distant = mpc_ae["Orbit_type"] == "Distant Object"

    # no_distant = mpc_ae[~is_distant]
    # distant = mpc_ae[is_distant]

    data = []
    for orb_type in mpc_ae["Orbit_type"].unique():
        tmp_df = mpc_ae[mpc_ae["Orbit_type"] == orb_type]
        x = tmp_df[xdata]
        y = tmp_df[ydata]
        data.append(
            go.Scattergl(
                x=x,
                y=y,
                mode="markers",
                name=orb_type,
                opacity=0.5,
                hoverinfo="skip"
                # marker=dict(color=random_color()[2])
            )
        )

    data.append(
        go.Scattergl(
            x=with_error["d:{}".format(xdata)].values,
            y=with_error["d:{}".format(ydata)].values,
            mode="markers",
            name="Fink SSO candidates (with orbit errors)",
            marker=dict(
                size=10,
                line=dict(color="rgba(70, 138, 94, 0.5)", width=2),
                color="rgba(111, 235, 154, 0.5)",
            ),
            hovertemplate=hovertemplate,
            customdata=with_error["d:ssoCandId"].values
        )
    )

    data.append(
        go.Scattergl(
            x=without_error["d:{}".format(xdata)].values,
            y=without_error["d:{}".format(ydata)].values,
            mode="markers",
            name="Fink SSO candidates (without orbit errors)",
            marker=dict(
                size=10,
                line=dict(color="rgba(70, 138, 94, 0.5)", width=2),
                color="rgba(194, 14, 29, 0.8)",
            ),
            hovertemplate=hovertemplate,
            customdata=without_error["d:ssoCandId"].values
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

    fig = go.Figure(data=data, layout=layout_sso_ae)

    if xdata == "a" or xdata == "i":
        fig.update_xaxes(type="log")
    if ydata == "a" or ydata == "i":
        fig.update_yaxes(type="log")

    return fig


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

    xaxis_drop = dcc.Dropdown(["a", "e", "i"], id="xaxis_data", searchable=False)

    yaxis_drop = dcc.Dropdown(["a", "e", "i"], id="yaxis_data", searchable=False)

    # add a time slider to filter the SSO trajectories by date in the a/e plot.

    div = dbc.Row([dbc.Col(card, width=15), dbc.Col([xaxis_drop, yaxis_drop], width=1)], className="g-9")
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
            1. Object name: [{}](https://minorplanetcenter.net/db_search/show_object?utf8=%E2%9C%93&object_id={})
                - number of associated alerts: {}
                - mean distance: {} arcsecond
            """.format(
                ast_name,
                ast_name.replace(" ", "+"),
                math.ceil(nb_assoc),
                np.round_(dist, decimals=2),
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
    pdf_lc,
    ssoCandId,
    ref_epoch,
    semi_major,
    semi_maj_error,
    ecc,
    ecc_error,
    incl,
    incl_error,
):

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
        First detection: {},
        Last detection: {},
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

    identification_info = sso_identify(pdf_lc)

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
                            dcc.Markdown(
                                markdownify_objectid(
                                    ssoCandId, "trajid_{}".format(ssoCandId)
                                )
                            ),
                            order=1,
                            style={"color": "#15284F"},
                        ),
                        # width=1,
                    ),
                ],
                justify="start",
                align="center",
            ),
            html.Div(new_detection_badge),
            dmc.Accordion(
                value="Date",
                children=[
                    dmc.AccordionItem(
                        [dmc.AccordionControl("Date"), dmc.AccordionPanel(date_info)],
                        value="Date",
                    ),
                    dmc.AccordionItem(
                        [dmc.AccordionControl("Orbit"), dmc.AccordionPanel(orbit_info)],
                        value="Orbit",
                    ),
                    dmc.AccordionItem(
                        [
                            dmc.AccordionControl("Magnitude"),
                            dmc.AccordionPanel(mag_info),
                        ],
                        value="Magnitude",
                    ),
                    dmc.AccordionItem(
                        [
                            dmc.AccordionControl("Identification"),
                            dmc.AccordionPanel(identification_info),
                        ],
                        value="Identification",
                    ),
                ],
            ),
        ],
        radius="xl",
        p="md",
        shadow="xl",
        withBorder=True,
    )


@app.callback(
    Output("last_sso_list", "children"),
    [Input("pdf_orb", "data"), Input("pdf_lc", "data")],
)
def last_sso_list_component(orb_json, lc_json):

    orb_data = pd.read_json(orb_json)
    orb_data = orb_data.sort_values("d:ref_epoch")

    lc_data = pd.read_json(lc_json)

    last_sso_orb = orb_data.tail().sort_values("d:ref_epoch", ascending=False)

    list_sso_paper = [
        html.Div(
            [
                html.Br(),
                draw_new_ssocard(
                    lc_data[lc_data["d:ssoCandId"] == ssoId]
                    .drop_duplicates("d:candid")
                    .reset_index(drop=True)
                    .sort_values("d:jd"),
                    ssoId,
                    ref_epoch,
                    a,
                    a_err,
                    e,
                    e_err,
                    i,
                    i_err,
                ),
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

    sso_news_component = dbc.Card(
        [
            dbc.CardHeader(
                "Solar System news",
                style={
                    "text-align": "center",
                    "font-weight": "bold",
                    "font-size": "2vw",
                },
            ),
            dbc.Container(
                list_sso_paper,
                style={
                    "overflow": "scroll",
                    "maxHeight": "700px",
                    # "maxWidth": "70%"
                },
            ),
        ],
        style={"padding": 1},
    )

    return sso_news_component


def search_ssocand_component():

    sso_search_bar = dbc.InputGroup(
        [
            dbc.Input(
                id="ssocand_bar_input",
                placeholder="Enter a valid SSOCandId, Example : FF2022aaaaaxl",
                autoFocus=True,
                type="search",
                style={
                    "border": "0px black solid",
                    "background": "rgba(255, 255, 255, 0.0)",
                    "color": "grey",
                },
                className="inputbar",
                debounce=True,
            ),
            dmc.ActionIcon(
                DashIconify(icon="tabler:search", width=20),
                n_clicks=0,
                id="ssocand_submit",
                color="gray",
                variant="transparent",
                radius="xl",
                size="lg",
                loaderProps={"variant": "dots", "color": "orange"},
            ),
        ],
        style={"border": "0.5px grey solid", "background": "rgba(255, 255, 255, .75)"},
        className="rcorners2",
    )
    return sso_search_bar


def search_sso_by_date_component(pdf_orb):

    min_dateorb = Time(pdf_orb["d:ref_epoch"].min(), format="jd").to_datetime()
    max_dateorb = Time(pdf_orb["d:ref_epoch"].max(), format="jd").to_datetime()

    sso_datepicker = dmc.DateRangePicker(
        id="search_sso_date_comp",
        label="Search SSOCand by date",
        description="Select a min and max date",
        minDate=min_dateorb,
        maxDate=max_dateorb,
        value=[max_dateorb - timedelta(days=5), max_dateorb],
    )

    return sso_datepicker


def active_filter_component():

    active_filter_comp = dbc.InputGroup(
        [
            dmc.MultiSelect(
                id="filter_list_comp",
                # data=["React", "Angular", "Svelte", "Vue"],
                searchable=True,
                nothingFound="No filters found",
                style={"width": 400},
            ),
            dmc.Checkbox(
                checked=False,
                id="boolean_error_checkbox",
                label="show only orbits with error",
            ),
        ]
    )

    return active_filter_comp


def search_orbit_component():

    orbit_input_group = dbc.InputGroup(
        [
            dmc.Select(
                data=[
                    {"value": "d:a", "label": "a: semi major axis (AU)"},
                    {"value": "d:e", "label": "e: eccentricity"},
                    {"value": "d:i", "label": "i: inclination (degree)"},
                    {"value": "obs_win", "label": "observation window"},
                    {"value": "nb_det", "label": "number of detection"},
                    {"value": "g", "label": "magnitude in g"},
                    {"value": "r", "label": "magnitude in r"},
                ],
                id="select_range_filter",
            ),
            dcc.RangeSlider(
                0,
                40,
                value=[5, 15],
                id="orbit_prop_slider",
                # dots=False,
                tooltip={"placement": "bottom", "always_visible": True},
            ),
        ],
        style={"width": "100%", "display": "inline-block"},
    )

    return orbit_input_group


def column_orbit_component(pdf_orb):

    orb_cols = pdf_orb.columns

    orb_cols_group = dmc.ChipGroup(
        [
            dmc.Chip(
                x, color="orange", value=x, radius="xl", variant="outline", size="xs"
            )
            for x in orb_cols
        ],
        id="orbit_columns_chips",
        value=["d:ssoCandId", "d:isoTime"],
        position="center",
        spacing="xs",
        multiple=True,
    )
    return orb_cols_group


@app.callback(
    [Output("orbit_prop_slider", "min"), Output("orbit_prop_slider", "max")],
    [Input("pdf_orb_ext", "data"), Input("select_range_filter", "value")],
)
def change_orb_props_filter(orb_json, select_value):

    if select_value == "" or select_value is None:
        raise PreventUpdate
    else:
        pdf_ext = pd.read_json(orb_json)

        if select_value == "g":
            prop_min, prop_max = pdf_ext["g_min"].min(), pdf_ext["g_max"].max()
        elif select_value == "r":
            prop_min, prop_max = pdf_ext["r_min"].min(), pdf_ext["r_max"].max()
        else:
            prop_min, prop_max = (
                pdf_ext[select_value].min(),
                pdf_ext[select_value].max(),
            )
        return prop_min, prop_max


filter_list_data = []
filter_list_value = []


@app.callback(
    [Output("filter_list_comp", "data"), Output("filter_list_comp", "value")],
    [
        Input("pdf_orb_ext", "data"),
        Input("ssocand_bar_input", "value"),
        Input("search_sso_date_comp", "value"),
        Input("select_range_filter", "value"),
        Input("orbit_prop_slider", "value"),
    ],
)
def search_ssocand_filter(orb_json, ssocandid, date_range, select_range, value_range):

    comp_id = ctx.triggered_id
    if comp_id is None:
        raise PreventUpdate

    if comp_id == "ssocand_bar_input":
        if ssocandid == "" or ssocandid == None:
            raise PreventUpdate
        else:
            value = "`d:ssoCandId`.str.contains('{}')".format(ssocandid)
            label = "{}".format(ssocandid)
            filter_list_data.append({"value": value, "label": label})
            filter_list_value.append(value)

    elif comp_id == "search_sso_date_comp":

        if date_range is None:
            raise PreventUpdate
        else:
            start_jd = Time(date_range[0], format="isot").jd
            end_jd = Time(date_range[1], format="isot").jd

            value = "`d:ref_epoch` < {} and `d:ref_epoch` > {}".format(end_jd, start_jd)
            label = "ref_epoch < {} and ref_epoch > {}".format(
                date_range[0], date_range[1]
            )
            filter_list_data.append({"value": value, "label": label})
            filter_list_value.append(value)

    elif comp_id == "orbit_prop_slider":

        if value_range is None or select_range is None:
            raise PreventUpdate

        min_value, max_value = value_range[0], value_range[1]

        if select_range == "g":
            value = "`{}` < {} and `{}` > {}".format(
                "g_max", max_value, "g_min", min_value
            )
            label = "g mag > {} and g mag < {}".format(min_value, max_value)
        elif select_range == "r":
            value = "`{}` < {} and `{}` > {}".format(
                "r_max", max_value, "r_min", min_value
            )
            label = "r mag > {} and r mag < {}".format(min_value, max_value)
        else:
            value = "`{}` < {} and `{}` > {}".format(
                select_range, max_value, select_range, min_value
            )
            if select_range.startswith("d:"):
                label = "{} > {} and {} < {}".format(
                    select_range[2:], min_value, select_range[2:], max_value
                )
            else:
                label = "{} > {} and {} < {}".format(
                    select_range, min_value, select_range, max_value
                )
            filter_list_data.append({"value": value, "label": label})
            filter_list_value.append(value)

    return filter_list_data, filter_list_value


@app.callback(
    Output("ssocand_table", "data"),
    [
        Input("pdf_orb_ext", "data"),
        Input("filter_list_comp", "value"),
        Input("boolean_error_checkbox", "checked"),
    ],
)
def apply_filter_to_table(orb_json, filter_list_v_comp, with_error):

    pdf_ext = pd.read_json(orb_json)

    if with_error and with_error is not None:
        pdf_ext = pdf_ext[pdf_ext["d:rms_a"] != -1.0]

    if filter_list_v_comp is not None:
        global filter_list_value
        filter_list_value = filter_list_v_comp

    if filter_list_v_comp == [] or filter_list_v_comp is None:
        return pdf_ext.to_dict("records")
    else:
        return pdf_ext.query(" and ".join(filter_list_v_comp), engine="python").to_dict(
            "records"
        )


@app.callback(Output("ssocand_table", "columns"), Input("orbit_columns_chips", "value"))
def apply_columns_filter(selected_columns):

    new_columns = [
        {"name": cols, "id": cols, "presentation": "markdown"}
        if cols == "d:ssoCandId"
        else {"name": cols, "id": cols}
        for cols in selected_columns
    ]

    return new_columns


@app.callback(
    Output("search_sso_cand", "children"),
    [
        Input("pdf_orb_ext", "data"),
    ],
)
def build_filter_and_search(orb_json):

    pdf_orb = pd.read_json(orb_json)

    filter_tabs = dbc.Tabs(
        [
            dbc.Tab(search_ssocand_component(), label="Id filter"),
            dbc.Tab(search_sso_by_date_component(pdf_orb), label="Date filter"),
            dbc.Tab(search_orbit_component(), label="Property filter"),
            dbc.Tab(column_orbit_component(pdf_orb), label="Column filter"),
        ]
    )

    return html.Div(
        [
            filter_tabs,
            active_filter_component(),
            html.Div(id="sso_table_results"),
        ]
    )


@app.callback(Output("sso_table_results", "children"), Input("pdf_orb_ext", "data"))
def build_sso_table_results(orb_json):

    pdf_ext = pd.read_json(orb_json)

    markdown_options = {"link_target": "_blank"}
    return dash_table.DataTable(
        pdf_ext.to_dict("records"),
        columns=[
            {"name": i, "id": i, "presentation": "markdown"}
            if i == "d:ssoCandId"
            else {"name": i, "id": i}
            for i in ["d:ssoCandId", "d:a", "d:e", "d:i"]
        ],
        id="ssocand_table",
        page_size=13,
        sort_action="native",
        style_as_list_view=True,
        markdown_options=markdown_options,
        # fixed_columns={"headers": True, "data": 1},
        style_data={"backgroundColor": "rgb(248, 248, 248, .7)"},
        style_table={"maxWidth": "100%"},
        style_cell={"padding": "5px", "textAlign": "center", "overflow": "hidden"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "rgb(248, 248, 248, .7)"}
        ],
        style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"},
    )


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
                    label="SSOCands Explorer",
                    label_style=label_style,
                ),
                dbc.Tab(
                    html.Div(id="ae_distrib"),  # edit props
                    label="Distribution Explorer",
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
                dcc.Store(id="pdf_orb_ext"),
                dcc.Store(id="mpc_data"),
            ],
            className="home",
            style={
                "background-image": "linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(/assets/background.png)",
                "background-size": "contain",
            },
        )

    return layout_

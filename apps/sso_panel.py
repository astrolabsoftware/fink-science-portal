import pandas as pd
import io
import requests

from app import app
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, dash_table, State
import dash_mantine_components as dmc

from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from apps.utils import markdownify_objectid

@app.callback(
    Output("pdf_lc", "data"),
    [Input('url', 'pathname')]
)
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


@app.callback(
    Output("pdf_orb", "data"),
    [Input("pdf_lc", "data")]
)
def store_orbit_query(json_lc):
    """Cache query results (sso trajectories and lightcurves) for easy re-use

    https://dash.plotly.com/sharing-data-between-callbacks
    """

    pdf_lc = pd.read_json(json_lc)

    r_orb = requests.post(
        "https://fink-portal.org/api/v1/ssocand",
        json={
            "kind": "orbParams",  # Mandatory, `orbParams` or `lightcurves`
        },
    )

    # Format output in a DataFrame
    pdf_orb = pd.read_json(io.BytesIO(r_orb.content)).drop_duplicates(["d:a", "d:e", "d:i"])
    pdf_orb = pdf_orb[pdf_orb["d:trajectory_id"].isin(pdf_lc["d:trajectory_id"])]

    return pdf_orb.to_json()


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

    switch_lc_orb = dmc.Switch(
        size="md",
        radius="xl",
        label="orb_switch",
        color="orange",
        checked=False,
        id="sso-orb-switch",
    )
    switch_orb_description = (
        "Toggle the switch to list the orbital element of each trajectories."
    )

    return dbc.Container(
        [
            dmc.Accordion(
                state={"0": False},
                offsetIcon=False,
                children=[
                    dmc.AccordionItem(
                        children=[
                            dmc.Paper(
                                [
                                    dmc.Tooltip(
                                        children=switch_lc_orb,
                                        wrapLines=True,
                                        width=220,
                                        withArrow=True,
                                        transition="fade",
                                        transitionDuration=200,
                                        label=switch_orb_description,
                                    )
                                ]
                            )
                        ],
                        label="Trajectory Table options",
                        icon=[
                            DashIconify(
                                icon="tabler:arrow-bar-to-down",
                                color=dmc.theme.DEFAULT_COLORS["dark"][6],
                                width=20,
                            )
                        ],
                    )
                ],
            ),
            table,
        ]
    )


@app.callback(
    [Output("sso_lc_table", "data"), Output("sso_lc_table", "columns")],
    [Input("sso-orb-switch", "checked"), Input("pdf_orb", "data"), Input("pdf_lc", "data")],
    [State("sso_lc_table", "data"), State("sso_lc_table", "columns")],
)
def update_sso_table(orb_checked, json_orb, json_lc, data, columns):

    markdown_trajid = lambda traj_id: markdownify_objectid(traj_id, "trajid_{}".format(traj_id))
    if orb_checked is True:
        pdf_orb = (
            pd.read_json(json_orb)
            .sort_values(["d:trajectory_id", "d:ref_epoch"])
        )
        pdf_orb['d:trajectory_id'] = pdf_orb['d:trajectory_id'].apply(markdown_trajid)
        pdf_orb = pdf_orb.to_dict("records")

        colnames_to_display = [
            "d:trajectory_id",
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
    
    else:
        original_pdf = pd.DataFrame.from_dict(data)
        if "d:jd" in original_pdf:
            raise PreventUpdate
        
        pdf_lc = (
            pd.read_json(json_lc)
            .sort_values(["d:trajectory_id", "d:jd"])
        )
        pdf_lc['d:trajectory_id'] = pdf_lc['d:trajectory_id'].apply(markdown_trajid)
        pdf_lc = pdf_lc.to_dict("records")

        colnames_to_display = ["d:trajectory_id", "d:jd", "d:candid", "d:ra", "d:dec"]

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


@app.callback(
    Output("table_lc_res", "children"),
    [Input("pdf_lc", "data")],
)
def results(json_lc):

    pdf_lc = (
        pd.read_json(json_lc)
        .sort_values(["d:trajectory_id", "d:jd"])
    )
    pdf_lc['d:trajectory_id'] = pdf_lc['d:trajectory_id'].apply(
        lambda traj_id: markdownify_objectid(traj_id, "trajid_{}".format(traj_id)))
    pdf_lc = pdf_lc.to_dict("records")
    colnames_to_display = ["d:trajectory_id", "d:jd", "d:candid", "d:ra", "d:dec"]

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
                    dbc.Container(id="table_lc_res"),
                    label="Solar System Candidate table",
                    label_style=label_style,
                ),
                dbc.Tab(
                    dbc.Card(
                        dbc.CardBody(dcc.Markdown("je sais pas quoi mettre ici")),
                        style={"backgroundColor": "rgb(248, 248, 248, .7)"},
                    ),
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
                html.Br(),
                dbc.Row(
                    [html.Br(), dbc.Col(tabs_, width=10)],
                    justify="center",
                    className="g-0",
                ),
                dcc.Store(id="pdf_lc"),
                dcc.Store(id="pdf_orb"),
            ],
            className="home",
            style={
                "background-image": "linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(/assets/background.png)",
                "background-size": "contain",
            },
        )

    return layout_

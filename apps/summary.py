# Copyright 2020-2024 AstroLab Software
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
from urllib.error import URLError
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import numpy as np
import pandas as pd
import rocks
import visdcc
from dash import Input, Output, State, dcc, html, no_update
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from app import app
from apps.cards import card_id, card_lightcurve_summary
from apps.mulens.cards import card_explanation_mulens
from apps.plotting import (
    draw_sso_astrometry,
    draw_sso_lightcurve,
    draw_tracklet_lightcurve,
    draw_tracklet_radec,
)
from apps.sso.cards import card_sso_left
from apps.supernovae.cards import card_sn_scores
from fink_utils.sso.utils import get_miriade_data
from apps.utils import (
    generate_qr,
    loading,
    pil_to_b64,
    request_api,
    retrieve_oid_from_metaname,
)
from apps.varstars.cards import card_explanation_variable

dcc.Location(id="url", refresh=False)


def tab1_content(pdf):
    """Summary tab"""
    tab1_content_ = html.Div(
        [
            dmc.Space(h=10),
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Graph(
                            style={
                                "width": "100%",
                                "height": "4pc",
                            },
                            config={"displayModeBar": False},
                            id="classbar",
                        ),
                        width=12,
                    ),
                ],
                justify="around",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        children=[card_lightcurve_summary()],
                        md=8,
                    ),
                    dbc.Col(
                        children=[card_id(pdf)],
                        md=4,
                    ),
                ],
                className="g-1",
            ),
        ]
    )

    return tab1_content_


def tab2_content():
    """Supernova tab"""
    tab2_content_ = html.Div(
        [
            dmc.Space(h=10),
            dbc.Row(
                [
                    dbc.Col(card_sn_scores(), md=8),
                    dbc.Col(id="card_sn_properties", md=4),
                ],
                className="g-1",
            ),
        ]
    )
    return [tab2_content_]


def tab3_content():
    """Variable stars tab"""
    nterms_base = dmc.Container(
        [
            dbc.Label("Number of base terms"),
            dbc.Input(
                placeholder="1",
                value=1,
                type="number",
                id="nterms_base",
                debounce=True,
                min=0,
                max=4,
            ),
            dbc.Label("Number of band terms"),
            dbc.Input(
                placeholder="1",
                value=1,
                type="number",
                id="nterms_band",
                debounce=True,
                min=0,
                max=4,
            ),
            dbc.Label("Set manually the period (days)"),
            dbc.Input(
                placeholder="Optional",
                value=None,
                type="number",
                id="manual_period",
                debounce=True,
            ),
            dbc.Label("Range of periods (days)"),
            dbc.InputGroup(
                [
                    dbc.Input(
                        value=0.1,
                        type="number",
                        id="period_min",
                        debounce=True,
                    ),
                    dbc.InputGroupText(" < P < "),
                    dbc.Input(
                        value=1.2,
                        type="number",
                        id="period_max",
                        debounce=True,
                    ),
                ],
            ),
        ],
        className="mb-3",  # , style={'width': '100%', 'display': 'inline-block'}
    )

    submit_varstar_button = dmc.Button(
        "Fit data",
        id="submit_variable",
        color="dark",
        variant="outline",
        fullWidth=True,
        radius="xl",
    )

    card2 = dmc.Paper(
        [
            nterms_base,
        ],
        radius="sm",
        p="xs",
        shadow="sm",
        withBorder=True,
    )

    tab3_content_ = html.Div(
        [
            dmc.Space(h=10),
            dbc.Row(
                [
                    dbc.Col(
                        loading(
                            dmc.Paper(
                                [
                                    html.Div(id="variable_plot"),
                                    card_explanation_variable(),
                                ],
                            ),
                        ),
                        md=8,
                    ),
                    dbc.Col(
                        [
                            html.Div(id="card_variable_button"),
                            html.Br(),
                            card2,
                            html.Br(),
                            submit_varstar_button,
                        ],
                        md=4,
                    ),
                ],
                className="g-1",
            ),
        ]
    )
    return [tab3_content_]


def tab4_content():
    """Microlensing tab"""
    submit_mulens_button = dmc.Button(
        "Fit data",
        id="submit_mulens",
        color="dark",
        variant="outline",
        fullWidth=True,
        radius="xl",
    )

    tab4_content_ = html.Div(
        [
            dmc.Space(h=10),
            dbc.Row(
                [
                    dbc.Col(
                        loading(
                            dmc.Paper(
                                [
                                    html.Div(id="mulens_plot"),
                                    card_explanation_mulens(),
                                ],
                            ),
                        ),
                        md=8,
                    ),
                    dbc.Col(
                        [
                            html.Div(id="card_mulens"),
                            html.Br(),
                            submit_mulens_button,
                        ],
                        md=4,
                    ),
                ],
                className="g-1",
            ),
        ]
    )
    return [tab4_content_]


@app.callback(
    Output("tab_sso", "children"),
    [
        Input("object-sso", "data"),
    ],
    prevent_initial_call=True,
)
def tab5_content(object_soo):
    """SSO tab"""
    pdf = pd.read_json(object_soo)
    if pdf.empty:
        ssnamenr = "null"
        has_phase_curve_model = "false"
    else:
        ssnamenr = pdf["i:ssnamenr"].to_numpy()[0]
        # for JSON, CSV, VOTable javascript download
        has_phase_curve_model = str("residuals_shg1g2").lower()

    msg = """
    Alert data from ZTF, with ephemerides provided by the
    [Miriade ephemeride service](https://ssp.imcce.fr/webservices/miriade/api/ephemcc/).
    """
    tab1 = dbc.Row(
        [
            dbc.Col(
                [
                    dmc.Space(h=10),
                    draw_sso_lightcurve(pdf),
                    html.Br(),
                    dmc.Accordion(
                        children=[
                            dmc.AccordionItem(
                                [
                                    dmc.AccordionControl(
                                        "Information",
                                        icon=[
                                            DashIconify(
                                                icon="tabler:help-hexagon",
                                                color="#3C8DFF",
                                                width=20,
                                            ),
                                        ],
                                    ),
                                    dmc.AccordionPanel(dcc.Markdown(msg)),
                                ],
                                value="info",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    tab2 = dbc.Row(
        [
            dbc.Col(
                [
                    dmc.Space(h=10),
                    draw_sso_astrometry(pdf),
                    dmc.Accordion(
                        children=[
                            dmc.AccordionItem(
                                [
                                    dmc.AccordionControl(
                                        "How the residuals are computed?",
                                        icon=[
                                            DashIconify(
                                                icon="tabler:help-hexagon",
                                                color="#3C8DFF",
                                                width=20,
                                            ),
                                        ],
                                    ),
                                    dmc.AccordionPanel(
                                        dcc.Markdown(
                                            "The residuals are the difference between the alert positions and the positions returned by the [Miriade ephemeride service](https://ssp.imcce.fr/webservices/miriade/api/ephemcc/)."
                                        )
                                    ),
                                ],
                                value="residuals",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    msg_phase = r"""
    By default, the data is modeled after the three-parameter H, G1, G2 magnitude phase function for asteroids
    from [Muinonen et al. 2010](https://doi.org/10.1016/j.icarus.2010.04.003).
    We use the implementation in [sbpy](https://sbpy.readthedocs.io/en/latest/sbpy/photometry.html#disk-integrated-phase-function-models) to fit the data.

    We propose two cases, one fitting bands separately, and
    the other combining into a common V band before fitting. We
    also propose different phase curve modeling using the HG, HG12 and HG1G2 models.
    In addition, you can fit for spin values on top of the HG1G2 model (SHG1G2, paper in prep!).
    Note that in the spin case, H, $G_1$, and $G_2$ are fitted per band, but the spin parameters
    (R, $\alpha_0$, $\beta_0$) are fitted on all bands simultaneously.
    The title displays the value for the reduced $\chi^2$ of the fit.
    Hit buttons to see the fitted values!
    """

    tab3 = dbc.Row(
        [
            dbc.Col(
                [
                    dmc.Space(h=10),
                    html.Div(id="sso_phasecurve"),
                    html.Br(),
                    dmc.Stack(
                        [
                            dmc.RadioGroup(
                                children=dmc.Group(
                                    [
                                        dmc.Radio(k, value=k, color="orange")
                                        for k in ["per-band", "combined"]
                                    ]
                                ),
                                id="switch-phase-curve-band",
                                value="per-band",
                                size="sm",
                            ),
                            dmc.RadioGroup(
                                children=dmc.Group(
                                    [
                                        dmc.Radio(k, value=k, color="orange")
                                        for k in ["SHG1G2", "HG1G2", "HG12", "HG"]
                                    ]
                                ),
                                id="switch-phase-curve-func",
                                value="HG1G2",
                                size="sm",
                            ),
                        ],
                        align="center",
                        justify="center",
                    ),
                    dmc.Accordion(
                        children=[
                            dmc.AccordionItem(
                                [
                                    dmc.AccordionControl(
                                        "How the phase curve is modeled?",
                                        icon=[
                                            DashIconify(
                                                icon="tabler:help-hexagon",
                                                color="#3C8DFF",
                                                width=20,
                                            ),
                                        ],
                                    ),
                                    dmc.AccordionPanel(
                                        dcc.Markdown(msg_phase, mathjax=True)
                                    ),
                                ],
                                value="phase_curve",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    if ssnamenr != "null":
        left_side = dmc.Tabs(
            [
                dmc.TabsList(
                    [
                        dmc.TabsTab("Lightcurve", value="Lightcurve"),
                        dmc.TabsTab("Astrometry", value="Astrometry"),
                        dmc.TabsTab("Phase curve", value="Phase curve"),
                    ],
                ),
                dmc.TabsPanel(tab1, value="Lightcurve"),
                dmc.TabsPanel(tab2, value="Astrometry"),
                dmc.TabsPanel(tab3, value="Phase curve"),
            ],
            value="Lightcurve",
        )
    else:
        msg = """
        Object not referenced in the Minor Planet Center
        """
        left_side = [
            html.Br(),
            dmc.Alert(children="", title=msg, radius="md", color="red"),
        ]

    tab5_content_ = dbc.Row(
        [
            dmc.Space(h=10),
            dbc.Col(
                left_side,
                md=8,
            ),
            dbc.Col(
                [
                    card_sso_left(ssnamenr, has_phase_curve_model),
                ],
                md=4,
            ),
        ],
        className="g-1",
    )
    return tab5_content_


@app.callback(
    Output("tab_tracklet", "children"),
    [
        Input("object-tracklet", "data"),
    ],
    prevent_initial_call=True,
)
def tab6_content(object_tracklet):
    """Tracklet tab"""
    pdf = pd.read_json(object_tracklet)
    tab6_content_ = html.Div(
        [
            dmc.Space(h=10),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            draw_tracklet_lightcurve(pdf),
                            html.Br(),
                            draw_tracklet_radec(pdf),
                        ],
                    ),
                ],
            ),
        ]
    )
    return tab6_content_


def tabs(pdf):
    tabs_ = dmc.Tabs(
        [
            dmc.TabsList(
                [
                    dmc.TabsTab("Summary", value="Summary"),
                    dmc.TabsTab(
                        "Supernovae", value="Supernovae", disabled=len(pdf.index) == 1
                    ),
                    dmc.TabsTab(
                        "Variable stars",
                        value="Variable stars",
                        disabled=len(pdf.index) == 1,
                    ),
                    dmc.TabsTab(
                        "Microlensing",
                        value="Microlensing",
                        disabled=len(pdf.index) == 1,
                    ),
                    dmc.TabsTab(
                        "Solar System", value="Solar System", disabled=not is_sso(pdf)
                    ),
                    dmc.TabsTab(
                        "Tracklets", value="Tracklets", disabled=not is_tracklet(pdf)
                    ),
                    dmc.TabsTab("GRB", value="GRB", disabled=True),
                ],
                justify="flex-end",
            ),
            dmc.TabsPanel(children=[tab1_content(pdf)], value="Summary"),
            dmc.TabsPanel(tab2_content(), value="Supernovae"),
            dmc.TabsPanel(tab3_content(), value="Variable stars"),
            dmc.TabsPanel(tab4_content(), value="Microlensing"),
            dmc.TabsPanel(children=[], id="tab_sso", value="Solar System"),
            dmc.TabsPanel(children=[], id="tab_tracklet", value="Tracklets"),
        ],
        value="Summary",
    )

    return tabs_


def is_sso(pdfs):
    """Auxiliary function to check whether the object is a SSO"""
    payload = pdfs["i:ssnamenr"].to_numpy()[0]
    if str(payload) == "null" or str(payload) == "None":
        return False

    if np.all([i == payload for i in pdfs["i:ssnamenr"].to_numpy()]):
        return True

    return False


def is_tracklet(pdfs):
    """Auxiliary function to check whether the object is a tracklet"""
    payload = pdfs["d:tracklet"].to_numpy()[0]

    if str(payload).startswith("TRCK"):
        return True

    return False


@app.callback(
    [
        Output("object-data", "data"),
        Output("object-upper", "data"),
        Output("object-uppervalid", "data"),
        Output("object-sso", "data"),
        Output("object-tracklet", "data"),
    ],
    [
        Input("url", "pathname"),
    ],
)
def store_query(name):
    """Cache query results (data and upper limits) for easy re-use

    https://dash.plotly.com/sharing-data-between-callbacks
    """
    if not name[1:].startswith("ZTF"):
        # check this is not a name generated by a user
        oid = retrieve_oid_from_metaname(name[1:])
        if oid is None:
            raise PreventUpdate
    else:
        oid = name[1:]

    pdf = request_api(
        "/api/v1/objects",
        json={
            "objectId": oid,
            "withupperlim": True,
            "withcutouts": False,
        },
        dtype={"i:ssnamenr": str},  # Force reading this field as string
    )

    pdf["i:ssnamenr"] = pdf["i:ssnamenr"].replace(
        "None", "null"
    )  # For backwards compatibility

    pdfs = pdf[pdf["d:tag"] == "valid"]
    pdfsU = pdf[pdf["d:tag"] == "upperlim"]
    pdfsUV = pdf[pdf["d:tag"] == "badquality"]

    payload = pdfs["i:ssnamenr"].to_numpy()[0]
    is_sso = np.all([i == payload for i in pdfs["i:ssnamenr"].to_numpy()])
    if str(payload) != "null" and is_sso:
        pdfsso = request_api(
            "/api/v1/sso",
            json={
                "n_or_d": payload,
            },
        )

        if pdfsso.empty:
            # This can happen for SSO candidate with a ssnamenr
            # e.g. ZTF21abatnkh
            pdfsso = pd.DataFrame()
        else:
            # Extract miriade information as well
            name = rocks.id(payload)[0]
            if name:
                pdfsso["sso_name"] = name

            pdfsso = get_miriade_data(pdfsso, sso_colname="sso_name", withecl=False)
    else:
        pdfsso = pd.DataFrame()

    payload = pdfs["d:tracklet"].to_numpy()[0]

    if str(payload).startswith("TRCK"):
        pdftracklet = request_api(
            "/api/v1/tracklet",
            json={
                "id": payload,
            },
        )

    else:
        pdftracklet = pd.DataFrame()

    return (
        pdfs.to_json(),
        pdfsU.to_json(),
        pdfsUV.to_json(),
        pdfsso.to_json(),
        pdftracklet.to_json(),
    )


@app.callback(
    [
        Output("object-release", "data"),
        Output("lightcurve_request_release", "children"),
        Output("switch-mag-flux", "value"),
    ],
    Input("lightcurve_request_release", "n_clicks"),
    State("object-data", "data"),
    prevent_initial_call=True,
    background=True,
    running=[
        (Output("lightcurve_request_release", "disabled"), True, True),
        (Output("lightcurve_request_release", "loading"), True, False),
    ],
)
def store_release_photometry(n_clicks, object_data):
    if not n_clicks or not object_data:
        raise PreventUpdate

    pdf = pd.read_json(object_data)

    mean_ra = np.mean(pdf["i:ra"])
    mean_dec = np.mean(pdf["i:dec"])

    try:
        pdf_release = pd.read_csv(
            f"https://irsa.ipac.caltech.edu/cgi-bin/ZTF/nph_light_curves?POS=CIRCLE%20{mean_ra}%20{mean_dec}%20{2.0/3600}&BAD_CATFLAGS_MASK=32768&FORMAT=CSV",
        )

        if not pdf_release.empty:
            pdf_release = pdf_release[["mjd", "mag", "magerr", "filtercode"]]

            return (
                pdf_release.to_json(),
                f"DR photometry: {len(pdf_release.index)} points",
                "DC magnitude",
            )

    except URLError:
        import traceback

        traceback.print_exc()

    return no_update, "No DR photometry", no_update


@app.callback(
    Output("qrcode", "children"),
    [
        Input("url", "pathname"),
    ],
)
def make_qrcode(path):
    qrdata = f"https://fink-portal.org/{path[1:]}"
    qrimg = generate_qr(qrdata)

    return html.Img(src="data:image/png;base64, " + pil_to_b64(qrimg))


def layout(name):
    # even if there is one object ID, this returns  several alerts
    pdf = request_api(
        "/api/v1/objects",
        json={
            "objectId": name[1:],
        },
    )

    if pdf.empty:
        inner = html.Div(
            children=dmc.Container(
                dmc.Center(
                    style={"height": "100%", "width": "100%"},
                    children=[
                        dmc.Alert(
                            title=f"{name[1:]} not found",
                            children="Either the object name does not exist, or it has not yet been injected in our database (nightly data appears at the end of the night).",
                            color="gray",
                            radius="md",
                        ),
                    ],
                ),
                fluid=True,
                className="home",
            )
        )
        layout_ = dmc.MantineProvider(
            [inner],
        )
        return layout_
    else:
        col1 = dmc.GridCol(
            dmc.Skeleton(style={"width": "100%", "height": "15pc"}),
            id="card_id_left",
            className="p-1",
            span=12,
            # lg=12,
            # md=6,
            # sm=12,
        )
        col2 = dmc.GridCol(
            html.Div(
                [
                    visdcc.Run_js(id="aladin-lite-runner"),
                    html.Div(
                        dmc.Skeleton(
                            style={
                                "width": "100%",
                                "height": "100%",
                            },
                        ),
                        id="aladin-lite-div",
                        style={
                            "width": "100%",
                            "height": "27pc",
                        },
                    ),
                ],
                className="p-1",
            ),
            # lg=12,
            # md=6,
            # sm=12,
            span=12,
        )
        struct_left = dmc.Grid([col1, col2], gutter=0, className="g-0")
        struct = dmc.Grid(
            [
                dmc.GridCol(struct_left, span=3, className="p-1"),
                dmc.GridCol(
                    [
                        dmc.Space(h=10),
                        tabs(pdf),
                    ],
                    span=9,
                    className="p-1",
                ),
                dcc.Store(id="object-data"),
                dcc.Store(id="object-upper"),
                dcc.Store(id="object-uppervalid"),
                dcc.Store(id="object-sso"),
                dcc.Store(id="object-tracklet"),
                dcc.Store(id="object-release"),
            ],
            gutter="xl",
        )
        # I do not know why I have to pad here...
        return dmc.MantineProvider(
            dmc.Container(struct, fluid="xxl", style={"padding-top": "20px"})
        )

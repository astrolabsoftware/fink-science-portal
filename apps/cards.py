# Copyright 2020-2021 AstroLab Software
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
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import dash_table
import visdcc

from app import app

from apps.plotting import all_radio_options
from apps.utils import queryMPC, convert_mpc_type

from astropy.time import Time
import pandas as pd
import numpy as np
import urllib

def card_sn_scores() -> dbc.Card:
    """ Card containing the score evolution

    Returns
    ----------
    card: dbc.Card
        Card with the scores drawn inside
    """
    graph_lc = dcc.Graph(
        id='lightcurve_scores',
        style={
            'width': '100%',
            'height': '15pc'
        },
        config={'displayModeBar': False}
    )
    graph_scores = dcc.Graph(
        id='scores',
        style={
            'width': '100%',
            'height': '15pc'
        },
        config={'displayModeBar': False}
    )
    graph_color = dcc.Graph(
        id='colors',
        style={
            'width': '100%',
            'height': '15pc'
        },
        config={'displayModeBar': False}
    )
    graph_color_rate = dcc.Graph(
        id='colors_rate',
        style={
            'width': '100%',
            'height': '15pc'
        },
        config={'displayModeBar': False}
    )
    color_explanation = dcc.Markdown(
        """
        We show the last color evolution in 3 ways:
        - `delta(g-r)`: `(g-r)(i) - (g-r)(i-1)`, where `i` and `i-1` are the last two nights where both `g` and `r` measurements are available
        - `delta(g)`: `g(i) - g(i-1)`, where `g(i)` and `g(i-1)` are the last two measurements in the `g` band
        - `delta(r)`: `r(i) - r(i-1)`, where `r(i)` and `r(i-1)` are the last two measurements in the `r` band
        """
    )
    color_rate_explanation = dcc.Markdown(
        """
        We show:
        - `rate g-r`: color increase rate per day.
        - `rate g`: magnitude increase rate per day for the `g` band.
        - `rate r`: magnitude increase rate per day for the `r` band.
        """
    )
    msg = dcc.Markdown(
        """
        Fink's machine learning classification scores for Supernovae are derived from:
        - [SuperNNova](https://github.com/supernnova/SuperNNova) ([Möller & de Boissière 2019](https://academic.oup.com/mnras/article-abstract/491/3/4277/5651173)) to classify SNe at all light-curve epochs (`SN Ia score` & `SNe score`)
        - Random Forest (Leoni et al. in prep) and ([Ishida et al. 2019b](https://ui.adsabs.harvard.edu/abs/2019MNRAS.483....2I/abstract)) to classify early (pre-max) SN candidates (`Early SN Ia score`)

        Note that we then combine these scores, with other criteria,
        to give a final classification to the alert. An `SN candidate` requires that:
        - the alert passes the Fink quality cuts
        - the alert has no known transient association (from catalogues)
        - the alert has at least one of a SuperNNova model trained to identify SNe Ia or SNe (`SN Ia score` or `SNe score`) with a probability higher than 50% of this alert being a SN.

        In addition, the alert is considered as `Early SN Ia candidate` if it also satisfies:
        - the alert is relatively new (number of previous detections < 20)
        - the alert has the Random Forest model trained to select early supernovae Ia (`Early SN Ia score`) with a probability higher than 50% of this alert being a SN.
        """
    )
    card = dbc.Card(
        dbc.CardBody(
            [
                graph_lc,
                html.Br(),
                dbc.Tabs(
                    [
                        dbc.Tab(graph_scores, label='ML scores', tab_id='snt0'),
                        dbc.Tab([graph_color, html.Br(), color_explanation], label='Color and mag evolution', tab_id='snt1'),
                        dbc.Tab([graph_color_rate, html.Br(), color_rate_explanation], label='Color and mag rate', tab_id='snt2'),
                        dbc.Tab(msg, label='Info', tab_id='snt3'),
                    ]
                ),
            ]
        ),
        className="mt-3"
    )
    return card

def card_cutouts(is_mobile):
    """ Add a card containing cutouts

    Returns
    ----------
    card: dbc.Card
        Card with the cutouts drawn inside
    """
    if not is_mobile:
        card = dbc.Card(
            dbc.CardBody(
                [
                    dbc.Row([
                        dbc.Col(html.H5(children="Science", className="text-center")),
                        dbc.Col(html.H5(children="Template", className="text-center")),
                        dbc.Col(html.H5(children="Difference", className="text-center"))
                    ]),
                    dbc.Row(id='stamps', justify='around', no_gutters=True),
                    html.Br(),
                    html.Br(),
                    dcc.Graph(
                        id='lightcurve_cutouts',
                        style={
                            'width': '100%',
                            'height': '15pc'
                        },
                        config={'displayModeBar': False}
                    ),
                    dbc.Row(
                        dbc.RadioItems(
                            options=[{'label': k, 'value': k} for k in all_radio_options.keys()],
                            value="Difference magnitude",
                            id="switch-mag-flux",
                            inline=True
                        )
                    ),
                    html.Br(),
                    dcc.Markdown(
                        """
                        Circles (&#9679;) with error bars show valid alerts that pass the Fink quality cuts.
                        In addition, the _Difference magnitude_ view shows:
                        - upper triangles with errors (&#9650;), representing alert measurements that do not satisfy Fink quality cuts, but are nevetheless contained in the history of valid alerts and used by classifiers.
                        - lower triangles (&#9661;), representing 5-sigma mag limit in difference image based on PSF-fit photometry contained in the history of valid alerts.
                        """
                    ),
                ]
            ),
            className="mt-3"
        )
    else:
        card = dbc.Card(
            dbc.CardBody(
                [
                    dbc.Row(id='stamps_mobile', justify='around', no_gutters=True),
                ]
            ),
            className="mt-3"
        )
    return card

def card_variable_plot():
    """ Add a card to fit for variable stars

    Returns
    ----------
    card: dbc.Card
        Card with the variable drawn inside
    """
    card = dbc.Card(
        dbc.CardBody(id='variable_plot'),
        className="mt-3"
    )
    return card


nterms_base = dbc.FormGroup(
    [
        dbc.Label("Number of base terms"),
        dbc.Input(
            placeholder="1",
            value=1,
            type="number",
            id='nterms_base',
            debounce=True,
            min=0, max=4
        ),
        dbc.Label("Number of band terms"),
        dbc.Input(
            placeholder="1",
            value=1,
            type="number",
            id='nterms_band',
            debounce=True,
            min=0, max=4
        ),
        dbc.Label("Set manually the period (days)"),
        dbc.Input(
            placeholder="Optional",
            value=None,
            type="number",
            id='manual_period',
            debounce=True
        )
    ], style={'width': '100%', 'display': 'inline-block'}
)

submit_varstar_button = dbc.Button(
    'Fit data',
    id='submit_variable',
    style={'width': '100%', 'display': 'inline-block'},
    block=True
)

def card_variable_button(pdf):
    """ Add a card containing button to fit for variable stars
    """
    id0 = pdf['i:objectId'].values[0]
    cdsxmatch = pdf['d:cdsxmatch'].values[0]

    distnr = pdf['i:distnr'].values[0]
    objectidps1 = pdf['i:objectidps1'].values[0]
    distpsnr1 = pdf['i:distpsnr1'].values[0]
    neargaia = pdf['i:neargaia'].values[0]

    ra0 = pdf['i:ra'].values[0]
    dec0 = pdf['i:dec'].values[0]

    classification = pdf['v:classification'].values[0]

    card = dbc.Card(
        [
            html.H5("ObjectID: {}".format(id0), className="card-title"),
            html.H6(
                "Fink class: {}".format(classification),
                className="card-subtitle"
            ),
            dcc.Markdown(
                """
                ---
                ```python
                # Neighbourhood
                SIMBAD: {}
                PS1: {}
                Distance (PS1): {:.2f} arcsec
                Distance (Gaia): {:.2f} arcsec
                Distance (ZTF): {:.2f} arcsec
                ```
                """.format(
                    cdsxmatch, objectidps1, float(distpsnr1),
                    float(neargaia), float(distnr))
            ),
            dbc.Row(nterms_base),
            dbc.Row(submit_varstar_button),
            dbc.Row(
                dbc.Button(
                    'Search in ASAS-SN Var. Stars',
                    id='asas-sn',
                    style={'width': '100%', 'display': 'inline-block'},
                    block=True,
                    target="_blank",
                    href='https://asas-sn.osu.edu/variables?ra={}&dec={}&radius=0.5&vmag_min=&vmag_max=&amplitude_min=&amplitude_max=&period_min=&period_max=&lksl_min=&lksl_max=&class_prob_min=&class_prob_max=&parallax_over_err_min=&parallax_over_err_max=&name=&references[]=I&references[]=II&references[]=III&references[]=IV&references[]=V&references[]=VI&sort_by=raj2000&sort_order=asc&show_non_periodic=true&show_without_class=true&asassn_discov_only=false&'.format(ra0, dec0)
                )
            )
        ],
        className="mt-3", body=True
    )
    return card


submit_mulens_button = dbc.Button(
    'Fit data',
    id='submit_mulens',
    style={'width': '100%', 'display': 'inline-block'},
    block=True
)

def card_mulens_button(pdf):
    """ Add a card containing button to fit for microlensing events
    """
    id0 = pdf['i:objectId'].values[0]
    cdsxmatch = pdf['d:cdsxmatch'].values[0]

    distnr = pdf['i:distnr'].values[0]
    objectidps1 = pdf['i:objectidps1'].values[0]
    distpsnr1 = pdf['i:distpsnr1'].values[0]
    neargaia = pdf['i:neargaia'].values[0]

    classification = pdf['v:classification'].values[0]

    card = dbc.Card(
        [
            html.H5("ObjectID: {}".format(id0), className="card-title"),
            html.H6(
                "Fink class: {}".format(classification),
                className="card-subtitle"
            ),
            dcc.Markdown(
                """
                ---
                ```python
                # Neighbourhood
                SIMBAD: {}
                PS1: {}
                Distance (PS1): {:.2f} arcsec
                Distance (Gaia): {:.2f} arcsec
                Distance (ZTF): {:.2f} arcsec
                ```
                """.format(
                    cdsxmatch, objectidps1, float(distpsnr1),
                    float(neargaia), float(distnr))
            ),
            dbc.Row(submit_mulens_button)
        ],
        className="mt-3", body=True
    )
    return card

def card_mulens_plot():
    """ Add a card to fit for microlensing events

    Returns
    ----------
    card: dbc.Card
        Card with the microlensing fit drawn inside
    """
    card = dbc.Card(
        dbc.CardBody(id='mulens_plot'),
        className="mt-3"
    )
    return card

def card_explanation_variable():
    """ Explain what is used to fit for variable stars
    """
    msg = """
    Fill the fields on the right, and press `Fit data` to
    perform a time series analysis of the data:

    - Number of base terms: number of frequency terms to use for the base model common to all bands (default=1)
    - Number of band terms: number of frequency terms to use for the residuals between the base model and each individual band (default=1)

    The fit is done using [gatspy](https://zenodo.org/record/47887)
    described in [VanderPlas & Ivezic (2015)](https://ui.adsabs.harvard.edu/abs/2015ApJ...812...18V/abstract).
    We use a multiband periodogram (LombScargleMultiband) to find the best period.
    Alternatively, you can manually set the period in days.

    The title of the plot will give you the fitted period, and a score for the fit.
    The score is between 0 (poor fit) and 1 (excellent fit).
    """
    card = dbc.Card(
        dbc.CardBody(
            dcc.Markdown(msg)
        ), style={
            'backgroundColor': 'rgb(248, 248, 248, .7)'
        }
    )
    return card

def card_explanation_mulens():
    """ Explain what is used to fit for microlensing events
    """
    msg = """
    Press `Fit data` to perform a time series analysis of the data. Fitted parameters will be displayed on the right panel.

    The fit is done using [pyLIMA](https://github.com/ebachelet/pyLIMA)
    described in [Bachelet et al (2017)](https://ui.adsabs.harvard.edu/abs/2017AJ....154..203B/abstract).
    We use a simple PSPL model to fit the data.
    """
    card = dbc.Card(
        dbc.CardBody(
            dcc.Markdown(msg)
        ), style={
            'backgroundColor': 'rgb(248, 248, 248, .7)'
        }
    )
    return card

def card_sso_lightcurve():
    """ Add a card to display SSO lightcurve

    Returns
    ----------
    card: dbc.Card
        Card with the SSO lightcurve
    """
    card = dbc.Card(
        dbc.CardBody(id='sso_lightcurve'),
        className="mt-3"
    )
    return card

def card_sso_radec():
    """ Add a card to display SSO radec

    Returns
    ----------
    card: dbc.Card
        Card with the SSO radec
    """
    card = dbc.Card(
        dbc.CardBody(id='sso_radec'),
        className="mt-3"
    )
    return card

def card_sso_skymap():
    """ Display the sky map in the explorer tab results (Aladin lite)

    It uses `visdcc` to execute javascript directly.

    Returns
    ---------
    out: list of objects
    """
    return html.Div(
        [
            visdcc.Run_js(id='aladin-lite-div-skymap_sso'),
            dcc.Markdown('_Hit the Aladin Lite fullscreen button if the image is not displayed (we are working on it...)_'),
        ], style={
            'width': '100%',
            'height': '25pc'
        }
    )

def card_explanation_xmatch():
    """ Explain how xmatch works
    """
    msg = """
    The Fink Xmatch service allows you to cross-match your catalog data with
    all Fink alert data processed so far (more than 60 million alerts, from ZTF). Just drag and drop
    a csv file containing at least position columns named `RA` and `Dec`, and a
    column containing ids named `ID` (could be string, integer, ... anything to identify your objects). Required column names are case insensitive. The catalog can also contained
    other columns that will be displayed.

    The xmatch service will perform a conesearch around the positions with a fix radius of 1.5 arcseconds.
    The initializer for RA/Dec is very flexible and supports inputs provided in a number of convenient formats.
    The following ways of declaring positions are all equivalent:

    * 271.3914265, 45.2545134
    * 271d23m29.1354s, 45d15m16.2482s
    * 18h05m33.9424s, +45d15m16.2482s
    * 18 05 33.9424, +45 15 16.2482
    * 18:05:33.9424, 45:15:16.2482

    The final table will contain the original columns of your catalog for all rows matching a Fink object, with two new columns:

    * `objectId`: clickable ZTF objectId.
    * `classification`: the class of the last alert received for this object, inferred by Fink.

    This service is still experimental, and your feedback is welcome. Note that the system will limit to the first 1000 rows of your file (or 5MB max) for the moment.
    Contact us by opening an [issue](https://github.com/astrolabsoftware/fink-science-portal/issues) if you need other file formats or encounter problems.
    """
    card = dbc.Card(
        dbc.CardBody(
            dcc.Markdown(msg)
        ), style={
            'backgroundColor': 'rgb(248, 248, 248, .7)'
        }
    )
    return card

def card_id(pdf):
    """ Add a card containing basic alert data
    """
    id0 = pdf['i:objectId'].values[0]
    ra0 = pdf['i:ra'].values[0]
    dec0 = pdf['i:dec'].values[0]
    date0 = pdf['v:lastdate'].values[0]
    cdsxmatch = pdf['d:cdsxmatch'].values[0]

    distnr = pdf['i:distnr'].values[0]
    # objectidps1 = pdf['i:objectidps1'].values[0]
    ssnamenr = pdf['i:ssnamenr'].values[0]
    distpsnr1 = pdf['i:distpsnr1'].values[0]
    neargaia = pdf['i:neargaia'].values[0]

    try:
        rate_g = pdf['v:rate(dg)'][pdf['i:fid'] == 1].values[0]
    except IndexError:
        rate_g = 0.0
    try:
        rate_r = pdf['v:rate(dr)'][pdf['i:fid'] == 2].values[0]
    except IndexError:
        rate_r = 0.0

    classification = pdf['v:classification'].values[0]

    card = dbc.Card(
        [
            html.H5("ObjectID: {}".format(id0), className="card-title"),
            html.H6("Last class: {}".format(classification), className="card-subtitle"),
            dcc.Markdown(
                """
                ```python
                # General properties
                Date: {}
                RA: {} deg
                Dec: {} deg
                ```
                ---
                ```python
                # Variability (DC magnitude)
                Rate g (last): {:.2f} mag/day
                Rate r (last): {:.2f} mag/day
                ```
                ---
                ```python
                # Neighbourhood
                SIMBAD: {}
                MPC: {}
                Distance (PS1): {:.2f} arcsec
                Distance (Gaia): {:.2f} arcsec
                Distance (ZTF): {:.2f} arcsec
                ```
                ---
                """.format(
                    date0, ra0, dec0,
                    rate_g, rate_r,
                    cdsxmatch, ssnamenr, float(distpsnr1),
                    float(neargaia), float(distnr))
            ),
            dbc.ButtonGroup([
                dbc.Button('TNS', id='TNS', target="_blank", href='https://www.wis-tns.org/search?ra={}&decl={}&radius=5&coords_unit=arcsec'.format(ra0, dec0), color='light'),
                dbc.Button('OAC', id='OAC', target="_blank", href='https://api.astrocats.space/catalog?ra={}&dec={}&radius=2'.format(ra0, dec0), color='light'),
            ]),
            dbc.ButtonGroup([
                dbc.Button('SIMBAD', id='SIMBAD', target="_blank", href="http://simbad.u-strasbg.fr/simbad/sim-coo?Coord={}%20{}&Radius=0.08".format(ra0, dec0), color="light"),
                dbc.Button('NED', id='NED', target="_blank", href="http://ned.ipac.caltech.edu/cgi-bin/objsearch?search_type=Near+Position+Search&in_csys=Equatorial&in_equinox=J2000.0&ra={}&dec={}&radius=1.0&obj_sort=Distance+to+search+center&img_stamp=Yes".format(ra0, dec0), color="light"),
                dbc.Button('SDSS', id='SDSS', target="_blank", href="http://skyserver.sdss.org/dr13/en/tools/chart/navi.aspx?ra={}&dec={}".format(ra0, dec0), color="light"),
            ]),
        ],
        className="mt-3", body=True
    )
    return card

@app.callback(
    Output("card_sn_properties", "children"),
    [
        Input('lightcurve_scores', 'clickData'),
        Input('object-data', 'children'),
    ])
def card_sn_properties(clickData, object_data):
    """ Add a card containing SN alert data
    """
    pdf = pd.read_json(object_data)
    pdf = pdf.sort_values('i:jd', ascending=False)

    if clickData is not None:
        time0 = clickData['points'][0]['x']
        # Round to avoid numerical precision issues
        jds = pdf['i:jd'].apply(lambda x: np.round(x, 3)).values
        jd0 = np.round(Time(time0, format='iso').jd, 3)
        position = np.where(jds == jd0)[0][0]
    else:
        position = 0

    id0 = pdf['i:objectId'].values[position]
    snn_snia_vs_nonia = pdf['d:snn_snia_vs_nonia'].values[position]
    snn_sn_vs_all = pdf['d:snn_sn_vs_all'].values[position]
    rfscore = pdf['d:rfscore'].values[position]
    classtar = pdf['i:classtar'].values[position]
    ndethist = pdf['i:ndethist'].values[position]
    drb = pdf['i:drb'].values[position]

    ra0 = pdf['i:ra'].values[position]
    dec0 = pdf['i:dec'].values[position]

    try:
        g_minus_r = pdf['v:rate(g-r)'].values[0]
    except IndexError:
        g_minus_r = 0.0
    try:
        rate_g = pdf['v:rate(dg)'][pdf['i:fid'] == 1].values[0]
    except IndexError:
        rate_g = 0.0
    try:
        rate_r = pdf['v:rate(dr)'][pdf['i:fid'] == 2].values[0]
    except IndexError:
        rate_r = 0.0

    classification = pdf['v:classification'].values[position]

    card = dbc.Card(
        [
            html.H5("ObjectID: {}".format(id0), className="card-title"),
            html.H6(
                "Fink class: {}".format(classification),
                className="card-subtitle"
            ),
            dcc.Markdown(
                """
                ```python
                # SuperNNova classifiers
                SN Ia score: {:.2f}
                SNe score: {:.2f}
                # Early SN Ia classifier
                RF score: {:.2f}
                ```
                ---
                ```python
                # Variability (DC magnitude)
                Rate g-r (last): {:.2f} mag/day
                Rate g (last): {:.2f} mag/day
                Rate r (last): {:.2f} mag/day
                ```
                ---
                ```python
                # Extra properties
                Classtar: {:.2f}
                Detection in the survey: {}
                DL Real bogus: {:.2f}
                ```
                ---
                """.format(
                    float(snn_snia_vs_nonia),
                    float(snn_sn_vs_all),
                    float(rfscore),
                    g_minus_r,
                    rate_g,
                    rate_r,
                    float(classtar),
                    ndethist,
                    float(drb)
                )
            ),
            html.Br(),
            dbc.ButtonGroup([
                dbc.Button('TNS', id='TNS', target="_blank", href='https://www.wis-tns.org/search?ra={}&decl={}&radius=5&coords_unit=arcsec'.format(ra0, dec0), color='light'),
                dbc.Button('OAC', id='OAC', target="_blank", href='https://api.astrocats.space/catalog?ra={}&dec={}&radius=2'.format(ra0, dec0), color='light'),
            ]),
            dbc.ButtonGroup([
                dbc.Button('SIMBAD', id='SIMBAD', target="_blank", href="http://simbad.u-strasbg.fr/simbad/sim-coo?Coord={}%20{}&Radius=0.08".format(ra0, dec0), color="light"),
                dbc.Button('NED', id='NED', target="_blank", href="http://ned.ipac.caltech.edu/cgi-bin/objsearch?search_type=Near+Position+Search&in_csys=Equatorial&in_equinox=J2000.0&ra={}&dec={}&radius=1.0&obj_sort=Distance+to+search+center&img_stamp=Yes".format(ra0, dec0), color="light"),
                dbc.Button('SDSS', id='SDSS', target="_blank", href="http://skyserver.sdss.org/dr13/en/tools/chart/navi.aspx?ra={}&dec={}".format(ra0, dec0), color="light"),
            ]),
        ],
        className="mt-3", body=True
    )
    return card

def card_download(pdf):
    """ Card containing a button to download object data
    """
    objectid = pdf['i:objectId'].values[0]
    card = dbc.Card(
        [
            dbc.ButtonGroup([
                dbc.Button(
                    html.A(
                        'Download Object Data',
                        id="download-link",
                        download="{}.csv".format(objectid),
                        href=generate_download_link(pdf),
                        target="_blank", style={"color": "white"}),
                    id='download',
                    target="_blank",
                    href=""
                )
            ])
        ],
        className="mt-3", body=True
    )
    return card

def card_mulens_param():
    """ Add a card containing mulens fitted parameters
    """
    card = dbc.Card(
        [
            dcc.Markdown(id='mulens_params'),
        ], className="mt-3", body=True
    )
    return card

def generate_download_link(pdf):
    """ Crappy way for downloading data as csv. The URL is modified on-the-fly.
    TODO: try https://github.com/thedirtyfew/dash-extensions/
    """
    if pdf.empty:
        return ""
    else:
        # drop cutouts from download for the moment
        pdf = pdf.drop(
            columns=[
                'b:cutoutDifference_stampData',
                'b:cutoutScience_stampData',
                'b:cutoutTemplate_stampData'
            ]
        )
        csv_string = pdf.to_csv(index=False, encoding='utf-8')
        csv_string = "data:text/csv;charset=utf-8," + urllib.parse.quote(csv_string)
        return csv_string

def card_sso_mpc_params(ssnamenr):
    """ MPC parameters
    """
    template = """
    ```python
    # Properties from MPC
    number: {}
    period (year): {}
    a (AU): {}
    q (AU): {}
    e: {}
    inc (deg): {}
    Omega (deg): {}
    argPeri (deg): {}
    tPeri (MJD): {}
    meanAnomaly (deg): {}
    epoch (MJD): {}
    g: {}
    neo: {}
    ```
    ---
    """
    ssnamenr_ = str(ssnamenr)
    if ssnamenr_.startswith('C/'):
        kind = 'comet'
        ssnamenr_ = ssnamenr_[:-2] + ' ' + ssnamenr_[-2:]
        data = queryMPC(ssnamenr_, kind=kind)
    elif (ssnamenr_[-1] == 'P'):
        kind = 'comet'
        data = queryMPC(ssnamenr_, kind=kind)
    else:
        kind = 'asteroid'
        data = queryMPC(ssnamenr_, kind=kind)

    if data.empty:
        card = dbc.Card(
            [
                html.H5("Name: None", className="card-title"),
                html.H6("Orbit type: None", className="card-subtitle"),
                dcc.Markdown(
                    template.format(*([None] * 13))
                )
            ],
            className="mt-3", body=True
        )
        return card
    if kind == 'comet':
        header = [
            html.H5("Name: {}".format(data['n_or_d']), className="card-title"),
            html.H6("Orbit type: Comet", className="card-subtitle"),
        ]
        phase_slope = None
        neo = 0
    elif kind == 'asteroid':
        if data['name'] is None:
            name = ssnamenr
        else:
            name = data['name']
        orbit_type = convert_mpc_type(int(data['orbit_type']))
        header = [
            html.H5("Name: {}".format(name), className="card-title"),
            html.H6("Orbit type: {}".format(orbit_type), className="card-subtitle"),
        ]
        phase_slope = data['phase_slope']
        neo = int(data['neo'])

    card = dbc.Card(
        [
            *download_sso_modal(ssnamenr),
            dcc.Markdown("""---"""),
            *header,
            dcc.Markdown(
                template.format(
                    data['number'],
                    data['period'],
                    data['semimajor_axis'],
                    data['perihelion_distance'],
                    data['eccentricity'],
                    data['inclination'],
                    data['ascending_node'],
                    data['argument_of_perihelion'],
                    float(data['perihelion_date_jd']) - 2400000.5,
                    data['mean_anomaly'],
                    float(data['epoch_jd']) - 2400000.5,
                    phase_slope,
                    neo
                )
            ),
            dbc.ButtonGroup([
                dbc.Button('MPC', id='MPC', target="_blank", href='https://minorplanetcenter.net/db_search/show_object?utf8=%E2%9C%93&object_id={}'.format(ssnamenr_), color='light'),
                dbc.Button('JPL', id='JPL', target="_blank", href='https://ssd.jpl.nasa.gov/sbdb.cgi', color='light'),
            ]),
        ],
        className="mt-3", body=True
    )
    return card

def download_sso_modal(ssnamenr):
    message_download_sso = """
    In a terminal, simply paste (CSV):

    ```bash
    curl -H "Content-Type: application/json" -X POST \\
        -d '{{"n_or_d":"{}", "output-format":"csv"}}' \\
        http://134.158.75.151:24000/api/v1/sso -o {}.csv
    ```

    Or in a python terminal, simply paste:

    ```python
    import requests
    import pandas as pd

    r = requests.post(
      'http://134.158.75.151:24000/api/v1/sso',
      json={{
        'n_or_d': '{}',
        'output-format': 'json'
      }}
    )

    # Format output in a DataFrame
    pdf = pd.read_json(r.content)
    ```

    See http://134.158.75.151:24000/api for more options.
    """.format(ssnamenr, str(ssnamenr).replace('/', '_'), ssnamenr)
    modal = [
        dbc.Button(
            "Download {} data".format(ssnamenr),
            id="open-sso",
            color='secondary',
        ),
        dbc.Modal(
            [
                dbc.ModalHeader("Download {} data".format(ssnamenr)),
                dbc.ModalBody(dcc.Markdown(message_download_sso)),
                dbc.ModalFooter(
                    dbc.Button("Close", id="close-sso", className="ml-auto")
                ),
            ],
            id="modal-sso", scrollable=True
        ),
    ]
    return modal

@app.callback(
    Output("modal-sso", "is_open"),
    [Input("open-sso", "n_clicks"), Input("close-sso", "n_clicks")],
    [State("modal-sso", "is_open")],
)
def toggle_modal_sso(n1, n2, is_open):
    """ Callback for the modal (open/close)
    """
    if n1 or n2:
        return not is_open
    return is_open

def download_object_modal(objectid):
    message_download = """
    In a terminal, simply paste (CSV):

    ```bash
    curl -H "Content-Type: application/json" -X POST \\
        -d '{{"objectId":"{}", "output-format":"csv"}}' \\
        http://134.158.75.151:24000/api/v1/objects \\
        -o {}.csv
    ```

    Or in a python terminal, simply paste:

    ```python
    import requests
    import pandas as pd

    # get data for ZTF19acnjwgm
    r = requests.post(
      'http://134.158.75.151:24000/api/v1/objects',
      json={{
        'objectId': '{}',
        'output-format': 'json'
      }}
    )

    # Format output in a DataFrame
    pdf = pd.read_json(r.content)
    ```

    See http://134.158.75.151:24000/api for more options.
    """.format(objectid, str(objectid).replace('/', '_'), objectid)
    modal = [
        dbc.Button(
            "Download {} data".format(objectid),
            id="open-object",
            color='secondary',
            size="lg", block=True
        ),
        dbc.Modal(
            [
                dbc.ModalHeader("Download {} data".format(objectid)),
                dbc.ModalBody(dcc.Markdown(message_download)),
                dbc.ModalFooter(
                    dbc.Button("Close", id="close-object", className="ml-auto")
                ),
            ],
            id="modal-object", scrollable=True
        ),
    ]
    return modal

@app.callback(
    Output("modal-object", "is_open"),
    [Input("open-object", "n_clicks"), Input("close-object", "n_clicks")],
    [State("modal-object", "is_open")],
)
def toggle_modal_object(n1, n2, is_open):
    """ Callback for the modal (open/close)
    """
    if n1 or n2:
        return not is_open
    return is_open

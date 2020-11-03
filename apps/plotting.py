# Copyright 2020 AstroLab Software
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
import pandas as pd
import numpy as np
from gatspy import periodic

import java
import copy

from dash.dependencies import Input, Output
import plotly.graph_objects as go

from apps.utils import convert_jd, readstamp, _data_stretch
from apps.utils import extract_row, extract_properties
from apps.utils import apparent_flux, dc_mag
from apps.mulens_helper import fit_ml_de_simple, mulens_simple

from app import client, app

colors_ = [
    '#1f77b4',  # muted blue
    '#ff7f0e',  # safety orange
    '#2ca02c',  # cooked asparagus green
    '#d62728',  # brick red
    '#9467bd',  # muted purple
    '#8c564b',  # chestnut brown
    '#e377c2',  # raspberry yogurt pink
    '#7f7f7f',  # middle gray
    '#bcbd22',  # curry yellow-green
    '#17becf'   # blue-teal
]

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

layout_phase = dict(
    autosize=True,
    automargin=True,
    margin=dict(l=50, r=30, b=40, t=25),
    hovermode="closest",
    legend=dict(
        font=dict(size=10),
        orientation="h",
        yanchor="bottom",
        y=0.02,
        xanchor="right",
        x=1,
        bgcolor='rgba(0,0,0,0)'
    ),
    xaxis={
        'title': 'Phase'
    },
    yaxis={
        'autorange': 'reversed',
        'title': 'Magnitude'
    },
    title={
        "text": "Phased data",
        "y" : 1.01,
        "yanchor" : "bottom"
    }
)

layout_mulens = dict(
    autosize=True,
    automargin=True,
    margin=dict(l=50, r=30, b=40, t=25),
    hovermode="closest",
    legend=dict(
        font=dict(size=10),
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        bgcolor='rgba(0,0,0,0)'
    ),
    xaxis={
        'title': 'Observation date'
    },
    yaxis={
        'autorange': 'reversed',
        'title': 'DC magnitude'
    },
    title={
        "text": "Fit",
        "y" : 1.01,
        "yanchor" : "bottom"
    }
)

layout_scores = dict(
    autosize=True,
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    legend=dict(font=dict(size=10), orientation="h"),
    xaxis={
        'title': 'Observation date'
    },
    yaxis={
        'title': 'Score',
        'range': [0, 1]
    }
)

def extract_lightcurve(data: java.util.TreeMap) -> pd.DataFrame:
    """
    """
    values = ['i:jd', 'i:magpsf', 'i:sigmapsf', 'i:fid']
    pdfs = pd.DataFrame.from_dict(data, orient='index')
    if pdfs.empty:
        return pdfs
    return pdfs[values]

def extract_scores(data: java.util.TreeMap) -> pd.DataFrame:
    """
    """
    values = ['i:jd', 'd:snn_snia_vs_nonia', 'd:snn_sn_vs_all', 'd:rfscore']
    pdfs = pd.DataFrame.from_dict(data, orient='index')
    if pdfs.empty:
        return pdfs
    return pdfs[values]

@app.callback(
    [
        Output('lightcurve_cutouts', 'figure'),
        Output('lightcurve_scores', 'figure')
    ],
    [
        Input('switch-mag-flux', 'value'),
        Input('url', 'pathname'),
    ])
def draw_lightcurve(switch: int, pathname: str) -> dict:
    """ Draw object lightcurve with errorbars

    Parameters
    ----------
    switch: int
        Choose:
          - 0 to display difference magnitude
          - 1 to display dc magnitude
          - 2 to display flux
    pathname: str
        Pathname of the current webpage (should be /ZTF19...).

    Returns
    ----------
    figure: dict
    """
    data = client.scan(
        "",
        "key:key:{}".format(pathname[1:]),
        None, 0, True, True
    )
    pdf = extract_properties(
        data,
        [
            'i:jd', 'i:magpsf', 'i:sigmapsf', 'i:fid',
            'i:magnr', 'i:sigmagnr', 'i:magzpsci', 'i:isdiffpos'
        ]
    )

    jd = pdf['i:jd']
    jd = jd.apply(lambda x: convert_jd(float(x), to='iso'))

    mag = pdf['i:magpsf']
    err = pdf['i:sigmapsf']
    if switch == 0:
        layout_lightcurve['yaxis']['title'] = 'Difference magnitude'
        layout_lightcurve['yaxis']['autorange'] = 'reversed'
    elif switch == 1:
        # inplace replacement
        mag, err = np.transpose(
            [
                dc_mag(*args) for args in zip(
                    pdf['i:fid'].astype(int).values,
                    mag.astype(float).values,
                    err.astype(float).values,
                    pdf['i:magnr'].astype(float).values,
                    pdf['i:sigmagnr'].astype(float).values,
                    pdf['i:magzpsci'].astype(float).values,
                    pdf['i:isdiffpos'].values
                )
            ]
        )
        layout_lightcurve['yaxis']['title'] = 'Apparent DC magnitude'
        layout_lightcurve['yaxis']['autorange'] = 'reversed'
    elif switch == 2:
        # inplace replacement
        mag, err = np.transpose(
            [
                apparent_flux(*args) for args in zip(
                    pdf['i:fid'].astype(int).values,
                    mag.astype(float).values,
                    err.astype(float).values,
                    pdf['i:magnr'].astype(float).values,
                    pdf['i:sigmagnr'].astype(float).values,
                    pdf['i:magzpsci'].astype(float).values,
                    pdf['i:isdiffpos'].values
                )
            ]
        )
        layout_lightcurve['yaxis']['title'] = 'Apparent DC flux'
        layout_lightcurve['yaxis']['autorange'] = True

    figure = {
        'data': [
            {
                'x': jd[pdf['i:fid'] == '1'],
                'y': mag[pdf['i:fid'] == '1'],
                'error_y': {
                    'type': 'data',
                    'array': err[pdf['i:fid'] == '1'],
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
                'y': mag[pdf['i:fid'] == '2'],
                'error_y': {
                    'type': 'data',
                    'array': err[pdf['i:fid'] == '2'],
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
    return figure, figure

def draw_scores(data: java.util.TreeMap) -> dict:
    """ Draw scores from SNN module

    Parameters
    ----------
    data: java.util.TreeMap
        Results from a HBase client query

    Returns
    ----------
    figure: dict
    """
    pdf = extract_scores(data)

    jd = pdf['i:jd']
    jd = jd.apply(lambda x: convert_jd(float(x), to='iso'))
    figure = {
        'data': [
            {
                'x': jd,
                'y': [0.5] * len(jd),
                'mode': 'lines',
                'showlegend': False,
                'line': {
                    'color': 'black',
                    'width': 2.5,
                    'dash': 'dash'
                }
            },
            {
                'x': jd,
                'y': pdf['d:snn_snia_vs_nonia'],
                'mode': 'markers',
                'name': 'SN Ia score',
                'text': jd,
                'marker': {
                    'size': 10,
                    'color': '#2ca02c',
                    'symbol': 'circle'}
            },
            {
                'x': jd,
                'y': pdf['d:snn_sn_vs_all'],
                'mode': 'markers',
                'name': 'SNe score',
                'text': jd,
                'marker': {
                    'size': 10,
                    'color': '#d62728',
                    'symbol': 'square'}
            },
            {
                'x': jd,
                'y': pdf['d:rfscore'],
                'mode': 'markers',
                'name': 'Random Forest',
                'text': jd,
                'marker': {
                    'size': 10,
                    'color': '#9467bd',
                    'symbol': 'diamond'}
            }
        ],
        "layout": layout_scores
    }
    return figure

def extract_latest_cutouts(data: java.util.TreeMap):
    """ Extract cutout data from the alert

    Parameters
    ----------
    data: java.util.TreeMap
        Results from a HBase client query

    Returns
    ----------
    science: np.array
        2D array containing science data
    template: np.array
        2D array containing template data
    difference: np.array
        2D array containing difference data
    """
    values = [
        'i:jd',
        'b:cutoutScience_stampData',
        'b:cutoutTemplate_stampData',
        'b:cutoutDifference_stampData'
    ]
    pdfs = pd.DataFrame.from_dict(data, orient='index')[values]
    pdfs.sort_values('i:jd', ascending=False)
    diff = readstamp(
        client.repository().get(pdfs['b:cutoutDifference_stampData'].values[0]))
    science = readstamp(
        client.repository().get(pdfs['b:cutoutScience_stampData'].values[0]))
    template = readstamp(
        client.repository().get(pdfs['b:cutoutTemplate_stampData'].values[0]))
    return science, template, diff

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

@app.callback(
    Output('variable_plot', 'figure'),
    [
        Input('nterms_base', 'value'),
        Input('nterms_band', 'value'),
        Input('manual_period', 'value'),
        Input('url', 'pathname'),
        Input('submit_variable', 'n_clicks')
    ])
def plot_variable_star(nterms_base, nterms_band, manual_period, name, n_clicks):
    """
    """
    if type(nterms_base) not in [int]:
        return {'data': [], "layout": layout_phase}
    if type(nterms_band) not in [int]:
        return {'data': [], "layout": layout_phase}
    if manual_period is not None and type(manual_period) not in [int, float]:
        return {'data': [], "layout": layout_phase}

    if n_clicks is not None:
        results = client.scan("", "key:key:{}".format(name[1:]), None, 0, True, True)
        pdf = extract_properties(results, ['i:jd', 'i:magpsf', 'i:sigmapsf', 'i:fid'])
        pdf = pdf.sort_values('i:jd', ascending=False)

        jd = pdf['i:jd']
        fit_period = False if manual_period is not None else True
        model = periodic.LombScargleMultiband(
            Nterms_base=int(nterms_base),
            Nterms_band=int(nterms_band),
            fit_period=fit_period
        )
        model.optimizer.period_range = (0.1, 1.2)
        model.optimizer.quiet = True

        model.fit(
            jd.astype(float),
            pdf['i:magpsf'].astype(float),
            pdf['i:sigmapsf'].astype(float),
            pdf['i:fid'].astype(int)
        )

        if fit_period:
            period = model.best_period
        else:
            period = manual_period

        phase = jd.astype(float).values % period
        tfit = np.linspace(0, period, 100)

        layout_phase_ = copy.deepcopy(layout_phase)
        layout_phase_['title']['text'] = 'Period: {} days'.format(period)

        if '1' in np.unique(pdf['i:fid'].values):
            plot_filt1 = {
                'x': phase[pdf['i:fid'] == '1'],
                'y': pdf['i:magpsf'][pdf['i:fid'] == '1'],
                'error_y': {
                    'type': 'data',
                    'array': pdf['i:sigmapsf'][pdf['i:fid'] == '1'],
                    'visible': True,
                    'color': '#1f77b4'
                },
                'mode': 'markers',
                'name': 'g band',
                'text': phase[pdf['i:fid'] == '1'],
                'marker': {
                    'size': 12,
                    'color': '#1f77b4',
                    'symbol': 'o'}
            }
            fit_filt1 = {
                'x': tfit,
                'y': model.predict(tfit, period=period, filts=1),
                'mode': 'lines',
                'name': 'fit g band',
                'showlegend': False,
                'line': {
                    'color': '#1f77b4',
                }
            }
        else:
            plot_filt1 = {}
            fit_filt1 = {}

        if '2' in np.unique(pdf['i:fid'].values):
            plot_filt2 = {
                'x': phase[pdf['i:fid'] == '2'],
                'y': pdf['i:magpsf'][pdf['i:fid'] == '2'],
                'error_y': {
                    'type': 'data',
                    'array': pdf['i:sigmapsf'][pdf['i:fid'] == '2'],
                    'visible': True,
                    'color': '#ff7f0e'
                },
                'mode': 'markers',
                'name': 'r band',
                'text': phase[pdf['i:fid'] == '2'],
                'marker': {
                    'size': 12,
                    'color': '#ff7f0e',
                    'symbol': 'o'}
            }
            fit_filt2 = {
                'x': tfit,
                'y': model.predict(tfit, period=period, filts=2),
                'mode': 'lines',
                'name': 'fit r band',
                'showlegend': False,
                'line': {
                    'color': '#ff7f0e',
                }
            }
        else:
            plot_filt2 = {}
            fit_filt2 = {}

        figure = {
            'data': [
                plot_filt1,
                fit_filt1,
                plot_filt2,
                fit_filt2
            ],
            "layout": layout_phase_
        }
        return figure
    return {'data': [], "layout": layout_phase}

@app.callback(
    [
        Output('mulens_plot', 'figure'),
        Output('mulens_params', 'children'),
    ],
    [
        Input('url', 'pathname'),
        Input('submit_mulens', 'n_clicks')
    ])
def plot_mulens(name, n_clicks):
    """
    """
    if n_clicks is not None:
        results = client.scan("", "key:key:{}".format(name[1:]), None, 0, True, True)
        pdf = extract_properties(
            results,
            [
                'i:jd', 'i:magpsf', 'i:sigmapsf', 'i:fid',
                'i:magnr', 'i:sigmagnr', 'i:magzpsci', 'i:isdiffpos', 'i:objectId'
            ]
        )
        pdf = pdf.sort_values('i:jd', ascending=False)

        mag_dc, err_dc = np.transpose(
            [
                dc_mag(*args) for args in zip(
                    pdf['i:fid'].astype(int).values,
                    pdf['i:magpsf'].astype(float).values,
                    pdf['i:sigmapsf'].astype(float).values,
                    pdf['i:magnr'].astype(float).values,
                    pdf['i:sigmagnr'].astype(float).values,
                    pdf['i:magzpsci'].astype(float).values,
                    pdf['i:isdiffpos'].values
                )
            ]
        )

        # Container for measurements
        subpdf = pd.DataFrame({
            'filtercode': [],
            'mag_g': [],
            'magerr_g': [],
            'mag_r': [],
            'magerr_r': [],
            'time': [],
            'name': []
        })

        # Loop over filters
        conversiondict = {1.0: 'g', 2.0: 'r'}
        fids = pdf['i:fid'].astype(int).values
        jds = pdf['i:jd'].astype(float)
        jds_ = jds.values
        magpsf = pdf['i:magpsf'].astype(float).values
        sigmapsf = pdf['i:sigmapsf'].astype(float).values

        # extract historical and current measurements
        subpdf['time'] = jds_
        subpdf['name'] = pdf['i:objectId']

        masks = {'1': [], '2': []}
        for fid in np.unique(fids):
            # Select filter
            mask_fid = fids == fid

            # Remove upper limits
            maskNone = np.array(magpsf) == np.array(magpsf)

            # Remove outliers
            maskOutlier = np.array(mag_dc) < 22

            # Total mask
            mask = mask_fid * maskNone * maskOutlier
            masks[str(fid)] = mask

            # mot enough points for the fit
            if np.sum(mask) < 4:
                continue

            # Gather data for the fitter
            subpdf['filtercode'] = pd.Series(fids).replace(to_replace=conversiondict)
            subpdf[f'mag_{conversiondict[fid]}'] = mag_dc
            subpdf[f'magerr_{conversiondict[fid]}'] = err_dc

            # Nullify data which is not this filter
            subpdf[f'magerr_{conversiondict[fid]}'][~mask] = None
            subpdf[f'mag_{conversiondict[fid]}'][~mask] = None

        results_ml = fit_ml_de_simple(subpdf)

        # Compute chi2
        nfitted_param = 4. # u0, t0, tE, magstar
        time = np.arange(np.min(jds_), np.max(jds_), 1)

        if '1' in np.unique(pdf['i:fid'].values):
            plot_filt1 = {
                'x': jds[pdf['i:fid'] == '1'].apply(lambda x: convert_jd(float(x), to='iso')),
                'y': mag_dc[pdf['i:fid'] == '1'],
                'error_y': {
                    'type': 'data',
                    'array': err_dc[pdf['i:fid'] == '1'],
                    'visible': True,
                    'color': '#1f77b4'
                },
                'mode': 'markers',
                'name': 'g band',
                'text': jds_[pdf['i:fid'] == '1'],
                'marker': {
                    'size': 12,
                    'color': '#1f77b4',
                    'symbol': 'o'}
            }
            fit_filt1 = {
                'x': [convert_jd(float(t), to='iso') for t in time],
                'y': mulens_simple(time, results_ml.u0, results_ml.t0, results_ml.tE, results_ml.magStar_g),
                'mode': 'lines',
                'name': 'fit g band',
                'showlegend': False,
                'line': {
                    'color': '#1f77b4',
                }
            }

            # chi2
            observed = mag_dc[masks['1']]
            expected = mulens_simple(jds_, results_ml.u0, results_ml.t0, results_ml.tE, results_ml.magStar_g)[masks['1']]
            err = err_dc[masks['1']]
            chi2_g = 1. / (len(observed) - nfitted_param) * np.sum((observed - expected)**2/err**2)
        else:
            plot_filt1 = {}
            fit_filt1 = {}
            chi2_g = None

        if '2' in np.unique(pdf['i:fid'].values):
            plot_filt2 = {
                'x': jds[pdf['i:fid'] == '2'].apply(lambda x: convert_jd(float(x), to='iso')),
                'y': mag_dc[pdf['i:fid'] == '2'],
                'error_y': {
                    'type': 'data',
                    'array': err_dc[pdf['i:fid'] == '2'],
                    'visible': True,
                    'color': '#ff7f0e'
                },
                'mode': 'markers',
                'name': 'r band',
                'text': jds_[pdf['i:fid'] == '2'],
                'marker': {
                    'size': 12,
                    'color': '#ff7f0e',
                    'symbol': 'o'}
            }
            fit_filt2 = {
                'x': [convert_jd(float(t), to='iso') for t in time],
                'y': mulens_simple(time, results_ml.u0, results_ml.t0, results_ml.tE, results_ml.magStar_r),
                'mode': 'lines',
                'name': 'fit r band',
                'showlegend': False,
                'line': {
                    'color': '#ff7f0e',
                }
            }

            observed = mag_dc[masks['2']]
            expected = mulens_simple(jds_, results_ml.u0, results_ml.t0, results_ml.tE, results_ml.magStar_r)[masks['2']]
            err = err_dc[masks['2']]
            chi2_r = 1. / (len(observed) - nfitted_param) * np.sum((observed - expected)**2/err**2)
        else:
            plot_filt2 = {}
            fit_filt2 = {}
            chi2_r = None

        figure = {
            'data': [
                plot_filt1,
                fit_filt1,
                plot_filt2,
                fit_filt2
            ],
            "layout": layout_mulens
        }

        mulens_params = """
        ```python
        # Fitted parameters
        t0: {} (jd)
        tE: {} (days)
        u0: {}
        chi2_g/dof: {}
        chi2_r/dof: {}
        ```
        ---
        """.format(results_ml.t0, results_ml.tE, results_ml.u0, chi2_g, chi2_r)
        return figure, mulens_params

    mulens_params = """
    ```python
    # Fitted parameters
    t0:
    tE:
    u0:
    chi2_g/dof:
    chi2_r/dof:
    ```
    ---
    """
    return {'data': [], "layout": layout_mulens}, mulens_params

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

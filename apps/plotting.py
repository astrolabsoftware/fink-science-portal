# Copyright 2020-2023 AstroLab Software
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
import io
import pandas as pd
import numpy as np
from gatspy import periodic
from scipy.optimize import curve_fit

import datetime
import copy
from astropy.time import Time
from astropy.coordinates import SkyCoord
import requests

from dash import html, dcc, dash_table, Input, Output, State, no_update, ALL
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash_iconify import DashIconify
from dash.exceptions import PreventUpdate

from apps.utils import convert_jd, readstamp, _data_stretch, convolve
from fink_utils.photometry.conversion import apparent_flux, dc_mag
from fink_utils.photometry.utils import is_source_behind
from apps.utils import sine_fit
from apps.utils import class_colors
from apps.statistics import dic_names

from app import APIURL

from fink_utils.sso.spins import func_hg, func_hg12, func_hg1g2, func_hg1g2_with_spin
from fink_utils.sso.spins import estimate_sso_params, compute_color_correction

from pyLIMA import event
from pyLIMA import telescopes
from pyLIMA import microlmodels, microltoolbox
from pyLIMA.microloutputs import create_the_fake_telescopes

from astropy.modeling.fitting import LevMarLSQFitter
import astropy.units as u
from sbpy.data import Obs

from app import app

COLORS_ZTF = ['#15284F', '#F5622E']
COLORS_ZTF_RGB = ['rgba(21, 40, 79, 1, 0.2)', 'rgba(245, 98, 46, 1, 0.2)']

colors_ = [
    "rgb(165,0,38)",
    "rgb(215,48,39)",
    "rgb(244,109,67)",
    "rgb(253,174,97)",
    "rgb(254,224,144)",
    "rgb(224,243,248)",
    "rgb(171,217,233)",
    "rgb(116,173,209)",
    "rgb(69,117,180)",
    "rgb(49,54,149)"
]

all_radio_options = {
    "Difference magnitude": ["Difference magnitude", "DC magnitude", "DC flux"],
    "DC magnitude": ["Difference magnitude", "DC magnitude", "DC flux"],
    "DC flux": ["Difference magnitude", "DC magnitude", "DC flux"]
}

layout_lightcurve = dict(
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        'align': "left"
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        y=1.2,
        bgcolor='rgba(218, 223, 225, 0.3)'
    ),
    xaxis={
        'title': 'Observation date',
        'automargin': True
    },
    yaxis={
        'autorange': 'reversed',
        'title': 'Magnitude',
        'automargin': True
    }
)

layout_lightcurve_preview = dict(
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        'align': "left"
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        y=1.2,
        bgcolor='rgba(218, 223, 225, 0.3)'
    ),
    xaxis={
        'title': 'Observation date',
        'automargin': True
    },
    yaxis={
        'autorange': 'reversed',
        'title': 'Magnitude',
        'automargin': True
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
        bgcolor='rgba(218, 223, 225, 0.3)'
    ),
    xaxis={
        'title': 'Phase'
    },
    yaxis={
        'autorange': 'reversed',
        'title': 'Apparent DC Magnitude'
    },
    title={
        "text": "Phased data",
        "y": 1.01,
        "yanchor": "bottom"
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
        bgcolor='rgba(218, 223, 225, 0.3)'
    ),
    xaxis={
        'title': 'Observation date'
    },
    yaxis={
        'autorange': 'reversed',
        'title': 'DC magnitude'
    },
    title={
        "text": "pyLIMA Fit (PSPL model)",
        "y": 1.01,
        "yanchor": "bottom"
    }
)

layout_scores = dict(
    autosize=True,
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        y=1.2,
        bgcolor='rgba(218, 223, 225, 0.3)'
    ),
    hoverlabel={
        'align': "left"
    },
    xaxis={
        'title': 'Observation date',
        'automargin': True
    },
    yaxis={
        'title': 'Score',
        'range': [0, 1]
    }
)

layout_colors = dict(
    autosize=True,
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        y=1.2,
        bgcolor='rgba(218, 223, 225, 0.3)'
    ),
    hoverlabel={
        'align': "left"
    },
    xaxis={
        'automargin': True
    },
    yaxis={
        'title': 'Delta magnitude'
    }
)

layout_colors_rate = dict(
    autosize=True,
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        y=1.2,
        bgcolor='rgba(218, 223, 225, 0.3)'
    ),
    hoverlabel={
        'align': "left"
    },
    xaxis={
        'automargin': True
    },
    yaxis={
        'title': 'Rate (mag/day)'
    }
)

layout_sso_lightcurve = dict(
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        'align': "left"
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        y=1.2,
        bgcolor='rgba(218, 223, 225, 0.3)'
    ),
    xaxis={
        'title': 'Observation date',
        'automargin': True
    },
    yaxis={
        'autorange': 'reversed',
        'title': 'Magnitude',
        'automargin': True
    }
)

layout_sso_astrometry = dict(
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        'align': "left"
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        y=1.2,
        bgcolor='rgba(218, 223, 225, 0.3)'
    ),
    xaxis={
        'title': '&#916;RA cos(Dec) (\'\')',
        'automargin': True
    },
    yaxis={
        'title': '&#916;Dec (\'\')',
        'automargin': True,
        'scaleanchor': "x",
        'scaleratio': 1,
    }
)

layout_sso_phasecurve = dict(
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        'align': "left"
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        y=1.2,
        bgcolor='rgba(218, 223, 225, 0.3)'
    ),
    xaxis={
        'title': 'Phase angle [degree]',
        'automargin': True
    },
    yaxis={
        'autorange': 'reversed',
        'title': 'Observed magnitude [mag]',
        'automargin': True
    },
    title={
        "text": r"Reduced $\chi^2$",
        "y": 1.01,
        "yanchor": "bottom"
    }
)

layout_sso_phasecurve_residual = dict(
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        'align': "left"
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        y=1.2,
        bgcolor='rgba(218, 223, 225, 0.3)'
    ),
    xaxis={
        'title': 'Phase angle [degree]',
        'automargin': True
    },
    yaxis={
        'range': [-1, 1],
        'title': 'Residual [mag]',
        'automargin': True
    },
)

layout_sso_radec = dict(
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        'align': "left"
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        y=1.2,
        bgcolor='rgba(218, 223, 225, 0.3)'
    ),
    yaxis={
        'title': 'Declination',
        'automargin': True
    },
    xaxis={
        'autorange': 'reversed',
        'title': 'Right Ascension',
        'automargin': True
    }
)

layout_tracklet_lightcurve = dict(
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        'align': "left"
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        y=1.2,
        bgcolor='rgba(218, 223, 225, 0.3)'
    ),
    yaxis={
        'autorange': 'reversed',
        'title': 'Magnitude',
        'automargin': True
    },
    xaxis={
        'autorange': 'reversed',
        'title': 'Right Ascension',
        'automargin': True
    }
)

@app.callback(
    [
        Output('variable_plot', 'children'),
        Output("submit_variable", "children"),
    ],
    [
        Input('nterms_base', 'value'),
        Input('nterms_band', 'value'),
        Input('manual_period', 'value'),
        Input('submit_variable', 'n_clicks'),
        Input('object-data', 'children'),
    ],
    prevent_initial_call=True
)
def plot_variable_star(nterms_base, nterms_band, manual_period, n_clicks, object_data):
    """ Fit for the period of a star using gatspy

    See https://zenodo.org/record/47887
    See https://ui.adsabs.harvard.edu/abs/2015ApJ...812...18V/abstract

    TODO: clean me
    """
    if type(nterms_base) not in [int]:
        return {'data': [], "layout": layout_phase}
    if type(nterms_band) not in [int]:
        return {'data': [], "layout": layout_phase}
    if manual_period is not None and type(manual_period) not in [int, float]:
        return {'data': [], "layout": layout_phase}

    if n_clicks is not None:
        pdf_ = pd.read_json(object_data)
        cols = [
            'i:jd', 'i:magpsf', 'i:sigmapsf', 'i:fid',
            'i:magnr', 'i:sigmagnr', 'i:magzpsci', 'i:isdiffpos', 'i:objectId'
        ]
        pdf = pdf_.loc[:, cols]
        pdf['i:fid'] = pdf['i:fid'].astype(str)
        pdf = pdf.sort_values('i:jd', ascending=False)

        mag_dc, err_dc = np.transpose(
            [
                dc_mag(*args) for args in zip(
                    pdf['i:magpsf'].astype(float).values,
                    pdf['i:sigmapsf'].astype(float).values,
                    pdf['i:magnr'].astype(float).values,
                    pdf['i:sigmagnr'].astype(float).values,
                    pdf['i:isdiffpos'].values
                )
            ]
        )

        jd = pdf['i:jd']
        fit_period = False if manual_period is not None else True
        model = periodic.LombScargleMultiband(
            Nterms_base=int(nterms_base),
            Nterms_band=int(nterms_band),
            fit_period=fit_period
        )

        # Not sure about that...
        model.optimizer.period_range = (0.1, 1.2)
        model.optimizer.quiet = True

        model.fit(
            jd.astype(float),
            mag_dc,
            err_dc,
            pdf['i:fid'].astype(int)
        )

        if fit_period:
            period = model.best_period
        else:
            period = manual_period

        phase = jd.astype(float).values % period
        tfit = np.linspace(0, period, 100)

        layout_phase_ = copy.deepcopy(layout_phase)
        layout_phase_['title']['text'] = 'Period: {} days - score: {:.2f}'.format(period, model.score(period))

        if '1' in np.unique(pdf['i:fid'].values):
            plot_filt1 = {
                'x': phase[pdf['i:fid'] == '1'],
                'y': mag_dc[pdf['i:fid'] == '1'],
                'error_y': {
                    'type': 'data',
                    'array': err_dc[pdf['i:fid'] == '1'],
                    'visible': True,
                    'color': COLORS_ZTF[0]
                },
                'mode': 'markers',
                'name': 'g band',
                'text': phase[pdf['i:fid'] == '1'],
                'marker': {
                    'size': 12,
                    'color': COLORS_ZTF[0],
                    'symbol': 'o'}
            }
            fit_filt1 = {
                'x': tfit,
                'y': model.predict(tfit, period=period, filts=1),
                'mode': 'lines',
                'name': 'fit g band',
                'showlegend': False,
                'line': {
                    'color': COLORS_ZTF[0],
                }
            }
        else:
            plot_filt1 = {}
            fit_filt1 = {}

        if '2' in np.unique(pdf['i:fid'].values):
            plot_filt2 = {
                'x': phase[pdf['i:fid'] == '2'],
                'y': mag_dc[pdf['i:fid'] == '2'],
                'error_y': {
                    'type': 'data',
                    'array': err_dc[pdf['i:fid'] == '2'],
                    'visible': True,
                    'color': COLORS_ZTF[1]
                },
                'mode': 'markers',
                'name': 'r band',
                'text': phase[pdf['i:fid'] == '2'],
                'marker': {
                    'size': 12,
                    'color': COLORS_ZTF[1],
                    'symbol': 'o'}
            }
            fit_filt2 = {
                'x': tfit,
                'y': model.predict(tfit, period=period, filts=2),
                'mode': 'lines',
                'name': 'fit r band',
                'showlegend': False,
                'line': {
                    'color': COLORS_ZTF[1],
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
        graph = dcc.Graph(
            figure=figure,
            style={
                'width': '100%',
                'height': '25pc'
            },
            config={'displayModeBar': False}
        )

        return graph, no_update

    # quite referentially opaque...
    return "", no_update

@app.callback(
    Output('classbar', 'figure'),
    [
        Input('object-data', 'children'),
    ])
def plot_classbar(object_data):
    """ Display a bar chart with individual alert classifications

    Parameters
    ----------
    object_data: json data
        cached alert data
    """
    pdf = pd.read_json(object_data)
    grouped = pdf.groupby('v:classification').count()
    alert_per_class = grouped['i:objectId'].to_dict()

    # descending date values
    top_labels = pdf['v:classification'].values[::-1]
    customdata = pdf['i:jd'].apply(lambda x: convert_jd(float(x), to='iso')).values[::-1]
    x_data = [[1] * len(top_labels)]
    y_data = top_labels

    palette = dmc.theme.DEFAULT_COLORS

    colors = [palette[class_colors['Simbad']][6] if j not in class_colors.keys() else palette[class_colors[j]][6] for j in top_labels]

    fig = go.Figure()

    is_seen = []
    for i in range(0, len(x_data[0])):
        for xd, yd, label in zip(x_data, y_data, top_labels):
            if top_labels[i] in is_seen:
                showlegend = False
            else:
                showlegend = True
            is_seen.append(top_labels[i])

            percent = np.round(alert_per_class[top_labels[i]] / len(pdf) * 100).astype(int)
            name_legend = top_labels[i] + ': {}%'.format(percent)
            fig.add_trace(
                go.Bar(
                    x=[xd[i]], y=[yd],
                    orientation='h',
                    width=0.3,
                    showlegend=showlegend,
                    legendgroup=top_labels[i],
                    name=name_legend,
                    marker=dict(
                        color=colors[i],
                    ),
                    customdata=[customdata[i]],
                    hovertemplate='<b>Date</b>: %{customdata}'
                )
            )

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
            bgcolor='rgba(255, 255, 255, 0)',
            bordercolor='rgba(255, 255, 255, 0)',
            orientation="h",
            traceorder="reversed",
            yanchor='bottom',
            itemclick=False,
            itemdoubleclick=False,
            x=legend_shift
        ),
        barmode='stack',
        dragmode=False,
        paper_bgcolor='rgb(248, 248, 255, 0.0)',
        plot_bgcolor='rgb(248, 248, 255, 0.0)',
        margin=dict(l=0, r=0, b=0, t=0)
    )
    fig.update_layout(title_text='Individual alert classification')
    fig.update_layout(title_y=0.15)
    fig.update_layout(title_x=0.0)
    fig.update_layout(title_font_size=12)

    return fig

@app.callback(
    Output('lightcurve_cutouts', 'figure'),
    [
        Input('switch-mag-flux', 'value'),
        Input('url', 'pathname'),
        Input('object-data', 'children'),
        Input('object-upper', 'children'),
        Input('object-uppervalid', 'children'),
        Input('object-release', 'children')
    ])
def draw_lightcurve(switch: int, pathname: str, object_data, object_upper, object_uppervalid, object_release) -> dict:
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
    # Primary high-quality data points
    pdf_ = pd.read_json(object_data)
    cols = [
        'i:jd', 'i:magpsf', 'i:sigmapsf', 'i:fid', 'i:distnr',
        'i:magnr', 'i:sigmagnr', 'i:magzpsci', 'i:isdiffpos', 'i:candid'
    ]
    pdf = pdf_.loc[:, cols]

    # Upper limits
    pdf_upper = pd.read_json(object_upper)

    # Lower-quality data points
    pdf_upperv = pd.read_json(object_uppervalid)

    # type conversion
    dates = pdf['i:jd'].apply(lambda x: convert_jd(float(x), to='iso'))
    dates_upper = pdf_upper['i:jd'].apply(lambda x: convert_jd(float(x), to='iso'))
    dates_upperv = pdf_upperv['i:jd'].apply(lambda x: convert_jd(float(x), to='iso'))

    if object_release:
        # Data release photometry
        pdf_release = pd.read_json(object_release)
        dates_release = pdf_release['mjd'].apply(lambda x: convert_jd(float(x)+2400000.5, to='iso'))
    else:
        pdf_release = pd.DataFrame()

    # Exclude lower-quality points overlapping higher-quality ones
    mask = np.in1d(pdf_upperv['i:jd'].values, pdf['i:jd'].values)
    pdf_upperv,dates_upperv = [_[~mask] for _ in (pdf_upperv,dates_upperv)]

    # shortcuts
    mag = pdf['i:magpsf']
    err = pdf['i:sigmapsf']

    # Should we correct DC magnitudes for the nearby source?..
    is_dc_corrected = is_source_behind(pdf['i:distnr'].values[0])

    if switch == "Difference magnitude":
        layout_lightcurve['yaxis']['title'] = 'Difference magnitude'
        layout_lightcurve['yaxis']['autorange'] = 'reversed'
        scale = 1.0
    elif switch == "DC magnitude":
        if is_dc_corrected:
            # inplace replacement for DC corrected flux
            mag, err = np.transpose(
                [
                    dc_mag(*args) for args in zip(
                        mag.astype(float).values,
                        err.astype(float).values,
                        pdf['i:magnr'].astype(float).values,
                        pdf['i:sigmagnr'].astype(float).values,
                        pdf['i:isdiffpos'].values
                    )
                ]
            )
            # Keep only "good" measurements
            idx = err < 1
            pdf, dates, mag, err = [_[idx] for _ in [pdf, dates, mag, err]]

        layout_lightcurve['yaxis']['title'] = 'Apparent DC magnitude'
        layout_lightcurve['yaxis']['autorange'] = 'reversed'
        scale = 1.0
    elif switch == "DC flux":
        # inplace replacement
        mag, err = np.transpose(
            [
                apparent_flux(*args) for args in zip(
                    mag.astype(float).values,
                    err.astype(float).values,
                    pdf['i:magnr'].astype(float).values if is_dc_corrected else 99.0,
                    pdf['i:sigmagnr'].astype(float).values,
                    pdf['i:isdiffpos'].values
                )
            ]
        )

        layout_lightcurve['yaxis']['title'] = 'Apparent DC flux (milliJansky)'
        layout_lightcurve['yaxis']['autorange'] = True
        scale = 1e3

    layout_lightcurve['shapes'] = []

    figure = {
        'data': [],
        "layout": layout_lightcurve
    }

    for fid,fname,color in (
            (1, "g", COLORS_ZTF[0]),
            (2, "r", COLORS_ZTF[1])
    ):
        # High-quality measurements
        hovertemplate = r"""
        <b>%{yaxis.title.text}</b>: %{customdata[1]}%{y:.2f} &plusmn; %{error_y.array:.2f}<br>
        <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
        <b>mjd</b>: %{customdata[0]}
        <extra></extra>
        """
        idx = pdf['i:fid'] == fid
        figure['data'].append(
            {
                'x': dates[idx],
                'y': mag[idx] * scale,
                'error_y': {
                    'type': 'data',
                    'array': err[idx] * scale,
                    'visible': True,
                    'width': 0,
                    'opacity': 0.5,
                    'color': color
                },
                'mode': 'markers',
                'name': '{} band'.format(fname),
                'customdata': np.stack(
                    (
                        pdf['i:jd'].apply(lambda x: x - 2400000.5)[idx],
                        pdf['i:isdiffpos'].apply(lambda x: '(-) ' if x == 'f' else '')[idx],
                    ), axis=-1
                ),
                'hovertemplate': hovertemplate,
                "legendgroup": "{} band".format(fname),
                'legendrank': 100 + 10*fid,
                'marker': {
                    'size': 12,
                    'color': color,
                    'symbol': 'o'}
            }
        )

        if switch == "Difference magnitude":
            # Upper limits
            if not pdf_upper.empty:
                # <b>candid</b>: %{customdata[0]}<br> not available in index tables...
                hovertemplate_upper = r"""
                <b>Upper limit</b>: %{y:.2f}<br>
                <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
                <b>mjd</b>: %{customdata}
                <extra></extra>
                """
                idx = pdf_upper['i:fid'] == fid
                figure['data'].append(
                    {
                        'x': dates_upper[idx],
                        'y': pdf_upper['i:diffmaglim'][idx],
                        'mode': 'markers',
                        'name': '',
                        'customdata': pdf_upper['i:jd'].apply(lambda x: x - 2400000.5)[idx],
                        'hovertemplate': hovertemplate_upper,
                        "legendgroup": "{} band upper".format(fname),
                        'legendrank': 101 + 10*fid,
                        'marker': {
                            'color': color,
                            'symbol': 'triangle-down-open'
                        },
                        # 'showlegend': False
                    }
                )

            # Lower-quality data points
            if not pdf_upperv.empty:
                # <b>candid</b>: %{customdata[0]}<br> not available in index tables...
                hovertemplate_upperv = r"""
                <b>%{yaxis.title.text} (low quality)</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
                <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
                <b>mjd</b>: %{customdata}
                <extra></extra>
                """
                idx = pdf_upperv['i:fid'] == fid
                figure['data'].append(
                    {
                        'x': dates_upperv[idx],
                        'y': pdf_upperv['i:magpsf'][idx],
                        'error_y': {
                            'type': 'data',
                            'array': pdf_upperv['i:sigmapsf'][idx],
                            'visible': True,
                            'width': 0,
                            'opacity': 0.5,
                            'color': color
                        },
                        'mode': 'markers',
                        'customdata': pdf_upperv['i:jd'].apply(lambda x: x - 2400000.5)[idx],
                        'hovertemplate': hovertemplate_upperv,
                        "legendgroup": "{} band".format(fname),
                        'marker': {
                            'color': color,
                            'symbol': 'triangle-up'
                        },
                        'showlegend': False
                    }
                )

        elif switch == "DC magnitude":
            if is_dc_corrected:
                # Overplot the levels of nearby source magnitudes
                idx = pdf['i:fid'] == fid
                if np.sum(idx):
                    ref = np.mean(pdf['i:magnr'][idx])

                    figure['layout']['shapes'].append(
                        {
                            'type': 'line',
                            'yref': 'y',
                            'y0': ref, 'y1': ref,   # adding a horizontal line
                            'xref': 'paper', 'x0': 0, 'x1': 1,
                            'line': {'color': color, 'dash': 'dash', 'width': 1},
                            'legendgroup': '{} band'.format(fname),
                            'opacity': 0.3,
                        }
                    )

            # Data release photometry
            if not pdf_release.empty:
                hovertemplate_release = r"""
                <b>Data release magnitude</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
                <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
                <b>mjd</b>: %{customdata}
                <extra></extra>
                """
                idx = pdf_release['filtercode'] == 'z' + fname
                figure['data'].append(
                    {
                        'x': dates_release[idx],
                        'y': pdf_release['mag'][idx],
                        'error_y': {
                            'type': 'data',
                            'array': pdf_release['magerr'][idx],
                            'visible': True,
                            'width': 0,
                            'opacity': 0.5,
                            'color': color
                        },
                        'mode': 'markers',
                        'name': '',
                        'customdata': pdf_release['mjd'][idx],
                        'hovertemplate': hovertemplate_release,
                        "legendgroup": "{} band release".format(fname),
                        'legendrank': 102 + 10*fid,
                        'marker': {
                            'color': color,
                            'symbol': '.'
                        },
                        'opacity': 0.5,
                        # 'showlegend': False
                    }
                )

    return figure

@app.callback(
    Output('lightcurve_scores', 'figure'),
    [
        Input('url', 'pathname'),
        Input('object-data', 'children'),
        Input('object-upper', 'children'),
        Input('object-uppervalid', 'children')
    ])
def draw_lightcurve_sn(pathname: str, object_data, object_upper, object_uppervalid) -> dict:
    """ Draw object lightcurve with errorbars (SM view - DC mag fixed)

    Parameters
    ----------
    pathname: str
        Pathname of the current webpage (should be /ZTF19...).

    Returns
    ----------
    figure: dict
    """
    pdf_ = pd.read_json(object_data)
    cols = [
        'i:jd', 'i:magpsf', 'i:sigmapsf', 'i:fid',
        'i:magnr', 'i:sigmagnr', 'i:magzpsci', 'i:isdiffpos', 'i:candid'
    ]
    pdf = pdf_.loc[:, cols]

    # type conversion
    dates = pdf['i:jd'].apply(lambda x: convert_jd(float(x), to='iso'))

    # shortcuts
    mag = pdf['i:magpsf']
    err = pdf['i:sigmapsf']
    layout_lightcurve['yaxis']['title'] = 'Difference magnitude'
    layout_lightcurve['yaxis']['autorange'] = 'reversed'

    hovertemplate = r"""
    <b>%{yaxis.title.text}</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
    <b>mjd</b>: %{customdata}
    <extra></extra>
    """
    figure = {
        'data': [
            {
                'x': dates[pdf['i:fid'] == 1],
                'y': mag[pdf['i:fid'] == 1],
                'error_y': {
                    'type': 'data',
                    'array': err[pdf['i:fid'] == 1],
                    'visible': True,
                    'color': COLORS_ZTF[0]
                },
                'mode': 'markers',
                'name': 'g band',
                'customdata': pdf['i:jd'].apply(lambda x: x - 2400000.5)[pdf['i:fid'] == 1],
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 12,
                    'color': COLORS_ZTF[0],
                    'symbol': 'o'}
            },
            {
                'x': dates[pdf['i:fid'] == 2],
                'y': mag[pdf['i:fid'] == 2],
                'error_y': {
                    'type': 'data',
                    'array': err[pdf['i:fid'] == 2],
                    'visible': True,
                    'color': COLORS_ZTF[1]
                },
                'mode': 'markers',
                'name': 'r band',
                'customdata': pdf['i:jd'].apply(lambda x: x - 2400000.5)[pdf['i:fid'] == 2],
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 12,
                    'color': COLORS_ZTF[1],
                    'symbol': 'o'}
            }
        ],
        "layout": layout_lightcurve
    }
    return figure

def draw_lightcurve_preview(name) -> dict:
    """ Draw object lightcurve with errorbars (SM view - DC mag fixed)

    Parameters
    ----------
    pathname: str
        Pathname of the current webpage (should be /ZTF19...).

    Returns
    ----------
    figure: dict
    """
    cols = [
        'i:jd', 'i:magpsf', 'i:sigmapsf', 'i:fid',
    ]
    r = requests.post(
      '{}/api/v1/objects'.format(APIURL),
      json={
        'objectId': name,
        'withupperlim': 'True',
        'columns': ",".join(cols),
        'output-format': 'json'
      }
    )
    pdf = pd.read_json(r.content)

    # Mask upper-limits (but keep measurements with bad quality)
    mag_ = pdf['i:magpsf']
    mask = ~np.isnan(mag_)
    pdf = pdf[mask]

    # type conversion
    dates = pdf['i:jd'].apply(lambda x: convert_jd(float(x), to='iso'))

    # shortcuts
    mag = pdf['i:magpsf']
    err = pdf['i:sigmapsf']

    layout_lightcurve_preview['yaxis']['title'] = 'Difference magnitude'
    layout_lightcurve_preview['yaxis']['autorange'] = 'reversed'
    layout_lightcurve_preview['paper_bgcolor'] = 'rgba(0,0,0,0.0)'
    layout_lightcurve_preview['plot_bgcolor'] = 'rgba(0,0,0,0.2)'

    hovertemplate = r"""
    <b>%{yaxis.title.text}</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
    <b>mjd</b>: %{customdata}
    <extra></extra>
    """
    figure = {
        'data': [
            {
                'x': dates[pdf['i:fid'] == 1],
                'y': mag[pdf['i:fid'] == 1],
                'error_y': {
                    'type': 'data',
                    'array': err[pdf['i:fid'] == 1],
                    'visible': True,
                    'color': COLORS_ZTF[0]
                },
                'mode': 'markers',
                'name': 'g band',
                'customdata': pdf['i:jd'].apply(lambda x: x - 2400000.5)[pdf['i:fid'] == 1],
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 12,
                    'color': COLORS_ZTF[0],
                    'symbol': 'o'}
            },
            {
                'x': dates[pdf['i:fid'] == 2],
                'y': mag[pdf['i:fid'] == 2],
                'error_y': {
                    'type': 'data',
                    'array': err[pdf['i:fid'] == 2],
                    'visible': True,
                    'color': COLORS_ZTF[1]
                },
                'mode': 'markers',
                'name': 'r band',
                'customdata': pdf['i:jd'].apply(lambda x: x - 2400000.5)[pdf['i:fid'] == 2],
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 12,
                    'color': COLORS_ZTF[1],
                    'symbol': 'o'}
            }
        ],
        "layout": layout_lightcurve_preview
    }
    return figure

@app.callback(
    Output('scores', 'figure'),
    [
        Input('object-data', 'children'),
    ])
def draw_scores(object_data) -> dict:
    """ Draw scores from SNN module

    Parameters
    ----------
    pdf: pd.DataFrame
        Results from a HBase client query

    Returns
    ----------
    figure: dict

    TODO: memoise me
    """
    pdf = pd.read_json(object_data)

    # type conversion
    dates = pdf['i:jd'].apply(lambda x: convert_jd(float(x), to='iso'))

    hovertemplate = """
    <b>%{customdata[0]}</b>: %{y:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
    <b>mjd</b>: %{customdata[1]}
    <extra></extra>
    """
    figure = {
        'data': [
            {
                'x': dates,
                'y': [0.5] * len(dates),
                'mode': 'lines',
                'showlegend': False,
                'hoverinfo': 'skip',
                'line': {
                    'color': 'black',
                    'width': 2.5,
                    'dash': 'dash'
                }
            },
            {
                'x': dates,
                'y': pdf['d:snn_snia_vs_nonia'],
                'mode': 'markers',
                'name': 'SN Ia score',
                'customdata': list(
                    zip(
                        ['SN Ia score'] * len(pdf),
                        pdf['i:jd'].apply(lambda x: float(x) - 2400000.5),
                    )
                ),
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 10,
                    'color': '#15284F',
                    'symbol': 'circle'}
            },
            {
                'x': dates,
                'y': pdf['d:snn_sn_vs_all'],
                'mode': 'markers',
                'name': 'SNe score',
                'customdata': list(
                    zip(
                        ['SNe score'] * len(pdf),
                        pdf['i:jd'].apply(lambda x: float(x) - 2400000.5),
                    )
                ),
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 10,
                    'color': '#F5622E',
                    'symbol': 'square'}
            },
            {
                'x': dates,
                'y': pdf['d:rf_snia_vs_nonia'],
                'mode': 'markers',
                'name': 'Early SN Ia score',
                'customdata': list(
                    zip(
                        ['Early SN Ia score'] * len(pdf),
                        pdf['i:jd'].apply(lambda x: float(x) - 2400000.5),
                    )
                ),
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 10,
                    'color': '#3C8DFF',
                    'symbol': 'diamond'}
            }
        ],
        "layout": layout_scores
    }
    return figure

def extract_max_t2(pdf):
    """
    """
    cols = [i for i in pdf.columns if i.startswith('d:t2')]

    if cols == []:
        return pd.DataFrame()

    filt = pdf[cols].apply(lambda x: np.sum(x) > 0, axis=1)

    if pdf[filt].empty:
        return pd.DataFrame()

    series = pdf[cols][filt].apply(lambda x: np.array(x) == np.max(x), axis=1)
    df_tmp = pd.DataFrame(list(series.values), columns=pdf[cols].columns).T.sum(axis=1)
    df = pd.DataFrame(
        {
            'r': df_tmp.values,
            'theta': df_tmp.index
        },
        columns=['r', 'theta']
    )

    return df

@app.callback(
    Output('t2', 'children'),
    [
        Input('object-data', 'children'),
    ])
def draw_t2(object_data) -> dict:
    """ Draw scores from SNN module

    Parameters
    ----------
    pdf: pd.DataFrame
        Results from a HBase client query

    Returns
    ----------
    figure: dict

    TODO: memoise me
    """
    pdf = pd.read_json(object_data)

    df = extract_max_t2(pdf)

    if df.empty:
        msg = """
        No classification from T2 yet
        """
        out = dbc.Alert(msg, color="danger")
    else:
        figure = go.Figure(
            data=go.Scatterpolar(
                r=df.r,
                theta=[i.split('_')[-1] for i in df.theta],
                fill='toself',
                line=dict(color="#F5622E")
            ),
        )
        # figure = px.line_polar(df, r='r', theta='theta', line_close=True)
        # figure.update_traces(fill='toself')
        figure.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True
                ),
            ),
            showlegend=False,
            margin=dict(l=10, r=10, b=20, t=10),
        )

        graph = dcc.Graph(
            id='t2',
            figure=figure,
            style={
                'width': '100%',
                'height': '20pc'
            },
            config={'displayModeBar': False}
        )
        msg = """
        The radius gives the number of times a label was assigned the highest score from the T2 layer, among all alerts.
        T2 was deployed in 2023/01/25, and previous alerts do not contained scores.
        """
        button = dmc.ActionIcon(
            DashIconify(icon="fluent:question-16-regular", width=20),
            size="lg",
            variant="outline",
            id="action-icon",
            n_clicks=0,
            mb=10,
        )
        tooltip = dmc.Tooltip(
            button,
            width=220,
            withArrow=True,
            multiline=True,
            transition="fade",
            transitionDuration=100,
            label=msg
        )
        out = dmc.Center(
            children=[
                dmc.Group(
                    [
                        tooltip,
                        graph
                    ], position='center'
                )
            ],
        )

    return out

@app.callback(
    Output('colors', 'figure'),
    [
        Input('object-data', 'children'),
    ])
def draw_color(object_data) -> dict:
    """ Draw color evolution

    Parameters
    ----------
    pdf: pd.DataFrame
        Results from a HBase client query

    Returns
    ----------
    figure: dict

    TODO: memoise me
    """
    pdf = pd.read_json(object_data)

    # type conversion
    dates = pdf['i:jd'].apply(lambda x: convert_jd(float(x), to='iso'))

    hovertemplate = """
    <b>%{customdata[0]}</b>: %{y:.3f}<br>
    <b>mjd</b>: %{customdata[1]}
    <extra></extra>
    """
    m1 = pdf['i:fid'] == 1
    m2 = pdf['i:fid'] == 2
    figure = {
        'data': [
            {
                'x': dates,
                'y': pdf['v:g-r'],
                'mode': 'markers',
                'name': 'delta g-r (mag)',
                'customdata': list(
                    zip(
                        ['delta g-r'] * len(pdf['i:jd']),
                        pdf['i:jd'].apply(lambda x: float(x) - 2400000.5),
                    )
                ),
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 10,
                    'color': '#15284F',
                    'symbol': 'circle'
                }
            },
            {
                'x': dates[m1],
                'y': pdf['v:dg'][m1],
                'mode': 'markers',
                'name': 'delta g (mag)',
                'customdata': list(
                    zip(
                        ['delta g'] * len(pdf['i:jd'][m1]),
                        pdf['i:jd'].apply(lambda x: float(x) - 2400000.5)[m1],
                    )
                ),
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 10,
                    'color': '#F5622E',
                    'symbol': 'square'
                }
            },
            {
                'x': dates[m2],
                'y': pdf['v:dr'][m2],
                'mode': 'markers',
                'name': 'delta r (mag)',
                'customdata': list(
                    zip(
                        ['delta r'] * len(pdf['i:jd'][m2]),
                        pdf['i:jd'].apply(lambda x: float(x) - 2400000.5)[m2],
                    )
                ),
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 10,
                    'color': '#3C8DFF',
                    'symbol': 'diamond'
                }
            }
        ],
        "layout": layout_colors
    }
    return figure

@app.callback(
    Output('colors_rate', 'figure'),
    [
        Input('object-data', 'children'),
    ])
def draw_color_rate(object_data) -> dict:
    """ Draw color rate

    Parameters
    ----------
    pdf: pd.DataFrame
        Results from a HBase client query

    Returns
    ----------
    figure: dict

    TODO: memoise me
    """
    pdf = pd.read_json(object_data)

    # type conversion
    dates = pdf['i:jd'].apply(lambda x: convert_jd(float(x), to='iso'))

    hovertemplate_rate = """
    <b>%{customdata[0]} in mag/day</b>: %{y:.3f}<br>
    <b>mjd</b>: %{customdata[1]}
    <extra></extra>
    """
    m1 = pdf['i:fid'] == 1
    m2 = pdf['i:fid'] == 2
    figure = {
        'data': [
            {
                'x': dates,
                'y': pdf['v:rate(g-r)'],
                'mode': 'markers',
                'name': 'rate g-r (mag/day)',
                'customdata': list(
                    zip(
                        ['rate(delta g)'] * len(pdf['i:jd']),
                        pdf['i:jd'].apply(lambda x: float(x) - 2400000.5),
                    )
                ),
                'hovertemplate': hovertemplate_rate,
                'marker': {
                    'size': 10,
                    'color': '#15284F',
                    'symbol': 'circle'
                }
            },
            {
                'x': dates[m1],
                'y': pdf['v:rate(dg)'][m1],
                'mode': 'markers',
                'name': 'rate g (mag/day)',
                'customdata': list(
                    zip(
                        ['rate(delta g)'] * len(pdf['i:jd'][m1]),
                        pdf['i:jd'].apply(lambda x: float(x) - 2400000.5)[m1],
                    )
                ),
                'hovertemplate': hovertemplate_rate,
                'marker': {
                    'size': 10,
                    'color': '#F5622E',
                    'symbol': 'square'
                }
            },
            {
                'x': dates[m2],
                'y': pdf['v:rate(dr)'][m2],
                'mode': 'markers',
                'name': 'rate r (mag/day)',
                'customdata': list(
                    zip(
                        ['rate(delta r)'] * len(pdf['i:jd'][m2]),
                        pdf['i:jd'].apply(lambda x: float(x) - 2400000.5)[m2],
                    )
                ),
                'hovertemplate': hovertemplate_rate,
                'marker': {
                    'size': 10,
                    'color': '#3C8DFF',
                    'symbol': 'diamond'
                }
            },
        ],
        "layout": layout_colors_rate
    }
    return figure

def extract_cutout(object_data, time0, kind):
    """ Extract cutout data from the alert

    Parameters
    ----------
    object_data: json
        Jsonified pandas DataFrame
    time0: str
        ISO time of the cutout to extract
    kind: str
        science, template, or difference

    Returns
    ----------
    data: np.array
        2D array containing cutout data
    """
    values = [
        'i:jd',
        'b:cutout{}_stampData'.format(kind.capitalize()),
    ]
    pdf_ = pd.read_json(object_data)
    pdfs = pdf_.loc[:, values]
    pdfs = pdfs.sort_values('i:jd', ascending=False)

    if time0 is None:
        position = 0
    else:
        # Round to avoid numerical precision issues
        jds = pdfs['i:jd'].apply(lambda x: np.round(x, 3)).values
        jd0 = np.round(Time(time0, format='iso').jd, 3)
        if jd0 in jds:
            position = np.where(jds == jd0)[0][0]
        else:
            return None

    # Extract the cutout data
    r = requests.post(
        '{}/api/v1/cutouts'.format(APIURL),
        json={
            'objectId': pdf_['i:objectId'].values[0],
            'candid': str(pdf_['i:candid'].values[position]),
            'kind': kind.capitalize(),
            'output-format': 'FITS',
        }
    )

    cutout = readstamp(r.content, gzipped=False)

    if pdf_['i:isdiffpos'].values[position] == 'f' and kind == 'difference':
        # Negative event, let's invert the diff cutout
        cutout *= -1

    return cutout

@app.callback(
    Output("stamps", "children"),
    [
        Input('lightcurve_cutouts', 'clickData'),
        Input('object-data', 'children'),
    ]
)
def draw_cutouts(clickData, object_data):
    """ Draw cutouts data based on lightcurve data
    """
    if clickData is not None:
        jd0 = clickData['points'][0]['x']
    else:
        jd0 = None

    figs = []
    for kind in ['science', 'template', 'difference']:
        try:
            cutout = extract_cutout(object_data, jd0, kind=kind)
            if cutout is None:
                return no_update

            data = draw_cutout(cutout, kind)
        except OSError:
            data = dcc.Markdown("Load fail, refresh the page")

        figs.append(
            dbc.Col(
                data,
                xs=4,
                className="p-0",
            )
        )

    return figs

@app.callback(
    Output("stamps_modal_content", "children"),
    [
        Input('object-data', 'children'),
        Input('date_modal_select', 'value'),
        Input("stamps_modal", "is_open")
    ],
)
def draw_cutouts_modal(object_data, date_modal_select, is_open):
    """ Draw cutouts data based on lightcurve data
    """
    if not is_open:
        raise PreventUpdate

    figs = []
    for kind in ['science', 'template', 'difference']:
        try:
            data = extract_cutout(object_data, date_modal_select, kind=kind)
            figs.append(
                dmc.Tooltip(
                    children=draw_cutout(data, kind, modal=True),
                    radius='xl',
                    position='top',
                    multiline=True,
                    transition="fade",
                    transitionDuration=200,
                    label=kind,
                    zIndex=10000001
                )
            )
        except OSError:
            data = dcc.Markdown("Load fail, refresh the page")
            figs.append(data)
    return figs

def draw_cutouts_quickview(name):
    """ Draw Science cutout data for the preview service
    """
    figs = []
    for kind in ['science']:
        try:
            # transfer only necessary columns
            cols = [
                'i:objectId',
                'i:candid',
                'i:jd',
                'i:isdiffpos',
                'b:cutout{}_stampData'.format(kind.capitalize()),
            ]
            # Transfer cutout name data
            r = requests.post(
                '{}/api/v1/objects'.format(APIURL),
                json={
                    'objectId': name,
                    'columns': ','.join(cols)
                }
            )
            object_data = r.content
            data = extract_cutout(object_data, None, kind=kind)
            figs.append(draw_cutout(data, kind))
        except OSError:
            data = dcc.Markdown("Load fail, refresh the page")
            figs.append(data)
    return figs

def create_circular_mask(h, w, center=None, radius=None):

    if center is None: # use the middle of the image
        center = (int(w / 2), int(h / 2))
    if radius is None: # use the smallest distance between the center and image walls
        radius = min(center[0], center[1], w - center[0], h - center[1])

    Y, X = np.ogrid[:h, :w]
    dist_from_center = np.sqrt((X - center[0])**2 + (Y - center[1])**2)

    mask = dist_from_center <= radius
    return mask

def sigmoid(img: list) -> list:

    """ Sigmoid function used for img_normalizer

    Parameters
    -----------
    img: float array
        a float array representing a non-normalized image

    Returns
    -----------
    out: float array
    """

    # Compute mean and std of the image
    img_mean, img_std = img.mean(), img.std()
    # restore img to normal mean and std
    img_normalize = (img - img_mean) / img_std
    # image inversion
    inv_norm = -img_normalize
    # compute exponential of inv img
    exp_norm = np.exp(inv_norm)
    # perform sigmoid calculation and return it
    return 1 / (1 + exp_norm)

def sigmoid_normalizer(img: list, vmin: float, vmax: float) -> list:
    """ Image normalisation between vmin and vmax using Sigmoid function

    Parameters
    -----------
    img: float array
        a float array representing a non-normalized image

    Returns
    -----------
    out: float array where data are bounded between vmin and vmax
    """
    return (vmax - vmin) * sigmoid(img) + vmin

def legacy_normalizer(data: list, stretch='asinh', pmin=0.5, pmax=99.5) -> list:
    """ Old cutout normalizer which use the central pixel

    Parameters
    -----------
    data: float array
        a float array representing a non-normalized image

    Returns
    -----------
    out: float array where data are bouded between vmin and vmax
    """
    size = len(data)
    vmax = data[int(size / 2), int(size / 2)]
    vmin = np.min(data) + 0.2 * np.median(np.abs(data - np.median(data)))
    return _data_stretch(data, vmin=vmin, vmax=vmax, pmin=pmin, pmax=pmax, stretch=stretch)

def plain_normalizer(img: list, vmin: float, vmax: float, stretch='linear', pmin=0.5, pmax=99.5) -> list:
    """ Image normalisation between vmin and vmax

    Parameters
    -----------
    img: float array
        a float array representing a non-normalized image

    Returns
    -----------
    out: float array where data are bounded between vmin and vmax
    """
    limits = np.percentile(img, [pmin, pmax])
    data = _data_stretch(img, vmin=limits[0], vmax=limits[1], stretch=stretch, vmid=0.1, exponent=2)
    data = (vmax - vmin) * data + vmin

    return data

def draw_cutout(data, title, lower_bound=0, upper_bound=1, modal=False):
    """ Draw a cutout data
    """
    # Update graph data for stamps
    data = np.nan_to_num(data)

    # data = sigmoid_normalizer(data, lower_bound, upper_bound)
    data = plain_normalizer(data, lower_bound, upper_bound,
                            stretch='linear' if title in ['difference'] else 'asinh',
                            pmin=0.5, pmax=99.95)

    data = data[::-1]
    # data = convolve(data, smooth=1, kernel='gauss')
    shape = data.shape

    zsmooth = False

    fig = go.Figure(
        data=go.Heatmap(
            z=data, showscale=False, hoverinfo='skip', colorscale='Blues_r', zsmooth=zsmooth
        )
    )
    # Greys_r

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
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    fig.update_layout(width=shape[1], height=shape[0])
    fig.update_layout(yaxis={'scaleanchor':'x', 'scaleratio':1})

    if not modal:
        style = {'display':'block', 'aspect-ratio': '1', 'margin': '1px'}
        classname = 'zoom'
        classname = ''

        graph = dcc.Graph(
            id={'type':'stamp', 'id':title},
            figure=fig,
            style=style,
            config={'displayModeBar': False},
            className=classname,
            responsive=True
        )
    else:
        style = {'display': 'inline-block', 'height': '15pc', 'width': '15pc'}
        graph = dcc.Graph(
            id={'type':'stamp_modal', 'id':title},
            figure=fig,
            style=style,
            config={'displayModeBar': False},
            responsive=True
        )

    return graph

def zoom_cutouts(relayout_data, figure_states):
    # Code from https://stackoverflow.com/a/70405707
    unique_data = None
    for data in relayout_data:
        if relayout_data.count(data) == 1:
            unique_data = data

    if unique_data:
        for figure_state in figure_states:
            if unique_data.get('xaxis.autorange'):
                figure_state['layout']['xaxis']['autorange'] = True
                figure_state['layout']['yaxis']['autorange'] = True
            else:
                figure_state['layout']['xaxis']['range'] = [
                    unique_data['xaxis.range[0]'], unique_data['xaxis.range[1]']]
                figure_state['layout']['xaxis']['autorange'] = False
                figure_state['layout']['yaxis']['range'] = [
                    unique_data['yaxis.range[0]'], unique_data['yaxis.range[1]']]
                figure_state['layout']['yaxis']['autorange'] = False
        return [unique_data] * len(relayout_data), figure_states

    return relayout_data, figure_states

app.callback([
        Output({'type': 'stamp', 'id': ALL}, 'relayoutData'),
        Output({'type': 'stamp', 'id': ALL}, 'figure'),
    ],
    [
        Input({'type': 'stamp', 'id': ALL}, 'relayoutData'),
    ],
    State({'type': 'stamp', 'id': ALL}, 'figure'),
    prevent_initial_call=True
)(zoom_cutouts)

app.callback([
        Output({'type': 'stamp_modal', 'id': ALL}, 'relayoutData'),
        Output({'type': 'stamp_modal', 'id': ALL}, 'figure'),
    ],
    [
        Input({'type': 'stamp_modal', 'id': ALL}, 'relayoutData'),
    ],
    State({'type': 'stamp_modal', 'id': ALL}, 'figure'),
    prevent_initial_call=True
)(zoom_cutouts)

@app.callback(
    [
        Output('mulens_plot', 'children'),
        Output('mulens_params', 'children'),
        Output('submit_mulens', 'children'),
    ],
    [
        Input('submit_mulens', 'n_clicks'),
        Input('object-data', 'children')
    ])
def plot_mulens(n_clicks, object_data):
    """ Fit for microlensing event

    TODO: implement a fit using pyLIMA
    """
    if n_clicks is not None:
        pdf_ = pd.read_json(object_data)
        cols = [
            'i:jd', 'i:magpsf', 'i:sigmapsf', 'i:fid', 'i:ra', 'i:dec',
            'i:magnr', 'i:sigmagnr', 'i:magzpsci', 'i:isdiffpos', 'i:objectId'
        ]
        pdf = pdf_.loc[:, cols]
        pdf['i:fid'] = pdf['i:fid'].astype(str)
        pdf = pdf.sort_values('i:jd', ascending=False)

        mag_dc, err_dc = np.transpose(
            [
                dc_mag(*args) for args in zip(
                    pdf['i:magpsf'].astype(float).values,
                    pdf['i:sigmapsf'].astype(float).values,
                    pdf['i:magnr'].astype(float).values,
                    pdf['i:sigmagnr'].astype(float).values,
                    pdf['i:isdiffpos'].values
                )
            ]
        )

        current_event = event.Event()
        current_event.name = pdf['i:objectId'].values[0]

        current_event.ra = pdf['i:ra'].values[0]
        current_event.dec = pdf['i:dec'].values[0]

        filts = {'1': 'g', '2': 'r'}
        for fid in np.unique(pdf['i:fid'].values):
            mask = pdf['i:fid'].values == fid
            telescope = telescopes.Telescope(
                name='ztf_{}'.format(filts[fid]),
                camera_filter=format(filts[fid]),
                light_curve_magnitude=np.transpose(
                    [
                        pdf['i:jd'].values[mask],
                        mag_dc[mask],
                        err_dc[mask]
                    ]
                ),
                light_curve_magnitude_dictionnary={
                    'time': 0,
                    'mag': 1,
                    'err_mag': 2
                }
            )

            current_event.telescopes.append(telescope)

        # Le modele le plus simple
        mulens_model = microlmodels.create_model('PSPL', current_event)

        current_event.fit(mulens_model, 'DE')

        # 4 parameters
        dof = len(pdf) - 4 - 1

        results = current_event.fits[0]

        normalised_lightcurves = microltoolbox.align_the_data_to_the_reference_telescope(results, 0, results.fit_results)

        # Model
        create_the_fake_telescopes(results, results.fit_results)

        telescope_ = results.event.fake_telescopes[0]

        flux_model = mulens_model.compute_the_microlensing_model(telescope_, results.model.compute_pyLIMA_parameters(results.fit_results))[0]

        time = telescope_.lightcurve_flux[:, 0]
        magnitude = microltoolbox.flux_to_magnitude(flux_model)

        if '1' in np.unique(pdf['i:fid'].values):
            plot_filt1 = {
                'x': [convert_jd(t, to='iso') for t in normalised_lightcurves[0][:, 0]],
                'y': normalised_lightcurves[0][:, 1],
                'error_y': {
                    'type': 'data',
                    'array': normalised_lightcurves[0][:, 2],
                    'visible': True,
                    'color': COLORS_ZTF[0]
                },
                'mode': 'markers',
                'name': 'g band',
                'text': [convert_jd(t, to='iso') for t in normalised_lightcurves[0][:, 0]],
                'marker': {
                    'size': 12,
                    'color': COLORS_ZTF[0],
                    'symbol': 'o'}
            }
        else:
            plot_filt1 = {}

        if '2' in np.unique(pdf['i:fid'].values):
            # only filter r
            if len(np.unique(pdf['i:fid'].values)) == 1:
                index = 0
            else:
                index = 1
            plot_filt2 = {
                'x': [convert_jd(t, to='iso') for t in normalised_lightcurves[index][:, 0]],
                'y': normalised_lightcurves[index][:, 1],
                'error_y': {
                    'type': 'data',
                    'array': normalised_lightcurves[index][:, 2],
                    'visible': True,
                    'color': COLORS_ZTF[1]
                },
                'mode': 'markers',
                'name': 'r band',
                'text': [convert_jd(t, to='iso') for t in normalised_lightcurves[index][:, 0]],
                'marker': {
                    'size': 12,
                    'color': COLORS_ZTF[1],
                    'symbol': 'o'}
            }
        else:
            plot_filt2 = {}

        fit_filt = {
            'x': [convert_jd(float(t), to='iso') for t in time],
            'y': magnitude,
            'mode': 'lines',
            'name': 'fit',
            'showlegend': False,
            'line': {
                'color': '#7f7f7f',
            }
        }

        figure = {
            'data': [
                fit_filt,
                plot_filt1,
                plot_filt2
            ],
            "layout": layout_mulens
        }

        if sum([len(i) for i in figure['data']]) > 0:
            graph = dcc.Graph(
                figure=figure,
                style={
                    'width': '100%',
                    'height': '25pc'
                },
                config={'displayModeBar': False}
            )
        else:
            graph = ""

        # fitted parameters
        names = results.model.model_dictionnary
        params = results.fit_results
        err = np.diag(np.sqrt(results.fit_covariance))

        mulens_params = """
        ```python
        # Fitted parameters
        t0: {} +/- {} (jd)
        tE: {} +/- {} (days)
        u0: {} +/- {}
        chi2/dof: {}
        ```
        """.format(
            params[names['to']],
            err[names['to']],
            params[names['tE']],
            err[names['tE']],
            params[names['uo']],
            err[names['uo']],
            params[-1] / dof
        )

        mulens_params = dmc.Paper(
            [
                dcc.Markdown(mulens_params),
            ], radius='sm', p='xs', shadow='sm', withBorder=True
        )

        return graph, mulens_params, no_update

    mulens_params = ""
    return "", mulens_params, no_update

@app.callback(
    Output('aladin-lite-div', 'run'), Input('object-data', 'children'))
def integrate_aladin_lite(object_data):
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
    pdf_ = pd.read_json(object_data)
    cols = ['i:jd', 'i:ra', 'i:dec']
    pdf = pdf_.loc[:, cols]
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

def draw_sso_lightcurve(pdf) -> dict:
    """ Draw SSO object lightcurve with errorbars, and ephemerides on top
    from the miriade IMCCE service.

    Parameters
    ----------
    pathname: str
        Pathname of the current webpage (should be /ZTF19...).

    Returns
    ----------
    figure: dict
    """
    if pdf.empty:
        return html.Div()

    # type conversion
    dates = pdf['i:jd'].apply(lambda x: convert_jd(float(x), to='iso'))
    pdf['i:fid'] = pdf['i:fid'].apply(lambda x: int(x))

    # shortcuts
    mag = pdf['i:magpsf']
    err = pdf['i:sigmapsf']

    layout_sso_lightcurve['yaxis']['title'] = 'Difference magnitude'
    layout_sso_lightcurve['yaxis']['autorange'] = 'reversed'

    hovertemplate = r"""
    <b>%{yaxis.title.text}</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
    <b>mjd</b>: %{customdata}
    <extra></extra>
    """
    hovertemplate_ephem = r"""
    <b>%{yaxis.title.text}</b>: %{y:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x:.2f<br>
    <b>mjd</b>: %{customdata}
    <extra></extra>
    """

    to_plot = []

    gobs = {
        'x': dates[pdf['i:fid'] == 1],
        'y': mag[pdf['i:fid'] == 1],
        'error_y': {
            'type': 'data',
            'array': err[pdf['i:fid'] == 1],
            'visible': True,
            'color': COLORS_ZTF[0]
        },
        'mode': 'markers',
        'name': 'g band',
        'customdata': pdf['i:jd'].apply(lambda x: float(x) - 2400000.5)[pdf['i:fid'] == 1],
        'hovertemplate': hovertemplate,
        'marker': {
            'size': 6,
            'color': COLORS_ZTF[0],
            'symbol': 'o'}
    }
    to_plot.append(gobs)

    if 'SDSS:g' in pdf.columns:
        gephem = {
            'x': dates[pdf['i:fid'] == 1],
            'y': pdf['SDSS:g'][pdf['i:fid'] == 1],
            'mode': 'markers',
            'name': 'g (ephem)',
            'customdata': pdf['i:jd'].apply(lambda x: float(x) - 2400000.5)[pdf['i:fid'] == 1],
            'hovertemplate': hovertemplate_ephem,
            'marker': {
                'size': 6,
                'color': COLORS_ZTF[0],
                'symbol': 'o',
                'opacity': 0.5}
        }
        to_plot.append(gephem)

    robs = {
        'x': dates[pdf['i:fid'] == 2],
        'y': mag[pdf['i:fid'] == 2],
        'error_y': {
            'type': 'data',
            'array': err[pdf['i:fid'] == 2],
            'visible': True,
            'color': COLORS_ZTF[1]
        },
        'mode': 'markers',
        'name': 'r band',
        'customdata': pdf['i:jd'].apply(lambda x: float(x) - 2400000.5)[pdf['i:fid'] == 2],
        'hovertemplate': hovertemplate,
        'marker': {
            'size': 6,
            'color': COLORS_ZTF[1],
            'symbol': 'o'}
    }
    to_plot.append(robs)

    if 'SDSS:r' in pdf.columns:
        rephem = {
            'x': dates[pdf['i:fid'] == 2],
            'y': pdf['SDSS:r'][pdf['i:fid'] == 2],
            'mode': 'markers',
            'name': 'r (ephem)',
            'customdata': pdf['i:jd'].apply(lambda x: float(x) - 2400000.5)[pdf['i:fid'] == 2],
            'hovertemplate': hovertemplate_ephem,
            'marker': {
                'size': 6,
                'color': COLORS_ZTF[1],
                'symbol': 'o',
                'opacity': 0.5}
        }
        to_plot.append(rephem)

    figure = {
        'data': to_plot,
        "layout": layout_sso_lightcurve
    }
    graph = dcc.Graph(
        figure=figure,
        style={
            'width': '100%',
            'height': '30pc'
        },
        config={'displayModeBar': False}
    )
    card = dmc.Paper(graph, radius='xl', p='md', shadow='xl', withBorder=True)
    return card

def draw_sso_residual(pdf) -> dict:
    """ Draw SSO residuals (observation - ephemerides)

    Parameters
    ----------
    pathname: str
        Pathname of the current webpage (should be /ZTF19...).

    Returns
    ----------
    figure: dict
    """
    if pdf.empty:
        return html.Div()

    if 'SDSS:g' not in pdf.columns:
        return dbc.Alert(
            'No colors available from ephemerides for {}'.format(pdf['i:ssnamenr'].values[0]),
            color='danger'
        )

    # type conversion
    pdf['i:fid'] = pdf['i:fid'].apply(lambda x: int(x))

    # shortcuts
    mag = pdf['i:magpsf']
    err = pdf['i:sigmapsf']

    layout_sso_residual = copy.deepcopy(layout_sso_lightcurve)
    layout_sso_residual['yaxis']['title'] = 'Residuals [mag]'
    layout_sso_residual['xaxis']['title'] = 'Ecliptic longitude [deg]'

    diff1 = mag[pdf['i:fid'] == 1] - pdf['SDSS:g'][pdf['i:fid'] == 1]
    diff2 = mag[pdf['i:fid'] == 2] - pdf['SDSS:r'][pdf['i:fid'] == 2]

    popt1, pcov1 = curve_fit(sine_fit, pdf['Longitude'][pdf['i:fid'] == 1], diff1)
    popt2, pcov2 = curve_fit(sine_fit, pdf['Longitude'][pdf['i:fid'] == 2], diff2)

    hovertemplate = r"""
    <b>objectId</b>: %{customdata[0]}<br>
    <b>%{yaxis.title.text}</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x:.2f}<br>
    <b>date</b>: %{customdata[1]}
    <extra></extra>
    """
    gresiduals = {
        'x': pdf['Longitude'][pdf['i:fid'] == 1],
        'y': diff1,
        'error_y': {
            'type': 'data',
            'array': err[pdf['i:fid'] == 1],
            'visible': True,
            'color': COLORS_ZTF[0]
        },
        'mode': 'markers',
        'name': 'g band',
        'customdata': list(
            zip(
                pdf['i:objectId'][pdf['i:fid'] == 1],
                pdf['i:jd'].apply(lambda x: convert_jd(float(x), to='iso'))[pdf['i:fid'] == 1],
            )
        ),
        'hovertemplate': hovertemplate,
        'marker': {
            'size': 6,
            'color': COLORS_ZTF[0],
            'symbol': 'o'}
    }

    rresiduals = {
        'x': pdf['Longitude'][pdf['i:fid'] == 2],
        'y': diff2,
        'error_y': {
            'type': 'data',
            'array': err[pdf['i:fid'] == 2],
            'visible': True,
            'color': COLORS_ZTF[1]
        },
        'mode': 'markers',
        'name': 'r band',
        'customdata': list(
            zip(
                pdf['i:objectId'][pdf['i:fid'] == 2],
                pdf['i:jd'].apply(lambda x: convert_jd(float(x), to='iso'))[pdf['i:fid'] == 2],
            )
        ),
        'hovertemplate': hovertemplate,
        'marker': {
            'size': 6,
            'color': COLORS_ZTF[1],
            'symbol': 'o'}
    }

    longitude_arr = np.linspace(0,360,num=100)
    gfit = {
        'x': longitude_arr,
        'y': sine_fit(longitude_arr, *popt1),
        'mode': 'lines',
        'name': 'fit',
        'showlegend': False,
        'line': {
            'color': COLORS_ZTF[0],
        }
    }

    rfit = {
        'x': longitude_arr,
        'y': sine_fit(longitude_arr, *popt2),
        'mode': 'lines',
        'name': 'fit',
        'showlegend': False,
        'line': {
            'color': COLORS_ZTF[1],
        }
    }

    figure = {
        'data': [
            gresiduals,
            gfit,
            rresiduals,
            rfit
        ],
        "layout": layout_sso_residual
    }
    graph = dcc.Graph(
        figure=figure,
        style={
            'width': '100%',
            'height': '15pc'
        },
        config={'displayModeBar': False}
    )
    card = dmc.Paper(graph, radius='xl', p='md', shadow='xl', withBorder=True)
    return card

def draw_sso_astrometry(pdf) -> dict:
    """ Draw SSO object astrometry, that is difference position wrt ephemerides
    from the miriade IMCCE service.

    Parameters
    ----------
    pathname: str
        Pathname of the current webpage (should be /ZTF19...).

    Returns
    ----------
    figure: dict
    """
    if pdf.empty:
        msg = """
        Object not referenced in the Minor Planet Center
        """
        return html.Div([html.Br(), dbc.Alert(msg, color="danger")])

    if 'RA' not in pdf.columns:
        return dbc.Alert(
            'No ephemerides available for {}'.format(pdf['i:ssnamenr'].values[0]),
            color='danger'
        )

    # type conversion
    pdf['i:fid'] = pdf['i:fid'].apply(lambda x: int(x))

    deltaRAcosDEC = (pdf['i:ra'] - pdf.RA) * np.cos(np.radians(pdf['i:dec'])) * 3600
    deltaDEC = (pdf['i:dec'] - pdf.Dec) * 3600

    hovertemplate = r"""
    <b>objectId</b>: %{customdata[0]}<br>
    <b>%{yaxis.title.text}</b>: %{y:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x:.2f}<br>
    <b>mjd</b>: %{customdata[1]}
    <extra></extra>
    """
    diff_g = {
        'x': deltaRAcosDEC[pdf['i:fid'] == 1],
        'y': deltaDEC[pdf['i:fid'] == 1],
        'mode': 'markers',
        'name': 'g band',
        'customdata': list(
            zip(
                pdf['i:objectId'][pdf['i:fid'] == 1],
                pdf['i:jd'][pdf['i:fid'] == 1].apply(lambda x: float(x) - 2400000.5),
            )
        ),
        'hovertemplate': hovertemplate,
        'marker': {
            'size': 6,
            'color': COLORS_ZTF[0],
            'symbol': 'o'}
    }

    diff_r = {
        'x': deltaRAcosDEC[pdf['i:fid'] == 2],
        'y': deltaDEC[pdf['i:fid'] == 2],
        'mode': 'markers',
        'name': 'r band',
        'customdata': list(
            zip(
                pdf['i:objectId'][pdf['i:fid'] == 2],
                pdf['i:jd'][pdf['i:fid'] == 2].apply(lambda x: float(x) - 2400000.5),
            )
        ),
        'hovertemplate': hovertemplate,
        'marker': {
            'size': 6,
            'color': COLORS_ZTF[1],
            'symbol': 'o'}
    }

    figure = {
        'data': [
            diff_g,
            diff_r,
        ],
        "layout": layout_sso_astrometry
    }
    graph = dcc.Graph(
        figure=figure,
        style={
            'width': '100%',
            'height': '30pc'
        },
        config={'displayModeBar': False}
    )
    card = dmc.Paper(graph, radius='xl', p='md', shadow='xl', withBorder=True)
    return card

@app.callback(
    Output('sso_phasecurve', 'children'),
    [
        Input('url', 'pathname'),
        Input("switch-phase-curve-band", "value"),
        Input("switch-phase-curve-func", "value"),
        Input('object-sso', 'children')
    ])
def draw_sso_phasecurve(pathname: str, switch_band: str, switch_func: str, object_sso) -> dict:
    """ Draw SSO object phase curve

    Parameters
    ----------
    pathname: str
        Pathname of the current webpage (should be /ZTF19...).

    Returns
    ----------
    figure: dict
    """
    pdf = pd.read_json(object_sso)
    if pdf.empty:
        msg = """
        Object not referenced in the Minor Planet Center, or name not found in Fink.
        It may be a SSO candidate.
        """
        return html.Div([html.Br(), dbc.Alert(msg, color="danger")])

    if 'i:magpsf_red' not in pdf.columns:
        return dbc.Alert(
            'No ephemerides available for {}'.format(pdf['i:ssnamenr'].values[0]),
            color='danger'
        )

    pdf = pdf.sort_values('Phase')

    # type conversion
    pdf['i:fid'] = pdf['i:fid'].apply(lambda x: int(x))

    # Disctionary for filters
    filters = {1: 'g', 2: 'r', 3: 'i'}
    filts = np.unique(pdf['i:fid'].values)

    figs = []
    residual_figs = []

    hovertemplate = r"""
    <b>objectId</b>: %{customdata[0]}<br>
    <b>%{yaxis.title.text}</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x:.2f}<br>
    <b>mjd</b>: %{customdata[1]}
    <extra></extra>
    """

    if switch_func == 'HG1G2':
        fitfunc = func_hg1g2
        params = ['H', 'G1', 'G2']
        bounds = (
            [0, 0, 0],
            [30, 1, 1]
        )
        p0 = [15.0, 0.15, 0.15]
        x = np.deg2rad(pdf['Phase'].values)
    elif switch_func == 'HG12':
        fitfunc = func_hg12
        params = ['H', 'G12']
        bounds = (
            [0, 0],
            [30, 1]
        )
        p0 = [15.0, 0.15]
        x = np.deg2rad(pdf['Phase'].values)
    elif switch_func == 'HG':
        fitfunc = func_hg
        params = ['H', 'G']
        bounds = (
            [0, 0],
            [30, 1]
        )
        p0 = [15.0, 0.15]
        x = np.deg2rad(pdf['Phase'].values)
    elif switch_func == 'SHG1G2':
        fitfunc = func_hg1g2_with_spin
        params = ['H', 'G1', 'G2', 'R', 'alpha0', 'delta0']
        bounds = (
            [0, 0, 0, 1e-1, 0, -np.pi/2],
            [30, 1, 1, 1, 2*np.pi, np.pi/2]
        )
        p0 = [15.0, 0.15, 0.15, 0.8, np.pi, 0.0]
        x = [
            np.deg2rad(pdf['Phase'].values),
            np.deg2rad(pdf['i:ra'].values),
            np.deg2rad(pdf['i:dec'].values)
        ]

    layout_sso_phasecurve['title']['text'] = 'Reduced &#967;<sup>2</sup>: '
    if switch_band == 'per-band':
        dd = {'': [filters[f] + ' band' for f in filts]}
        dd.update({i: [''] * len(filts) for i in params})
        df_table = pd.DataFrame(
            dd,
            index=[filters[f] for f in filts]
        )

        # Multi-band fit
        outdic = estimate_sso_params(
            magpsf_red=pdf['i:magpsf_red'].values,
            sigmapsf=pdf['i:sigmapsf'].values,
            phase=np.deg2rad(pdf['Phase'].values),
            filters=pdf['i:fid'].values,
            ra=np.deg2rad(pdf['i:ra'].values),
            dec=np.deg2rad(pdf['i:dec'].values),
            p0=p0,
            bounds=bounds,
            model=switch_func,
            normalise_to_V=False
        )
        if outdic['fit'] != 0:
            return dbc.Alert("The fitting procedure could not converge.", color='danger')

        for i, f in enumerate(filts):
            cond = pdf['i:fid'] == f
            popt = []
            for pindex, param in enumerate(params):
                # rad2deg
                if pindex >= 3:
                    suffix = ''
                else:
                    suffix = '_{}'.format(f)

                loc = df_table[param].index == filters[f]
                df_table[param][loc] = '{:.2f} &plusmn; {:.2f}'.format(
                    outdic[param + suffix],
                    outdic['err_' + param + suffix]
                )

                if pindex <= 3:
                    popt.append(outdic[param + suffix])
                else:
                    popt.append(np.deg2rad(outdic[param + suffix]))

            ydata = pdf.loc[cond, 'i:magpsf_red']

            figs.append(
                {
                    'x': pdf.loc[cond, 'Phase'].values,
                    'y': ydata.values,
                    'error_y': {
                        'type': 'data',
                        'array': pdf.loc[cond, 'i:sigmapsf'].values,
                        'visible': True,
                        'color': COLORS_ZTF[i]
                    },
                    'mode': 'markers',
                    'name': '{:}'.format(filters[f]),
                    'customdata': list(
                        zip(
                            pdf.loc[cond, 'i:objectId'],
                            pdf.loc[cond, 'i:jd'].apply(lambda x: float(x) - 2400000.5),
                        )
                    ),
                    'hovertemplate': hovertemplate,
                    'marker': {
                        'size': 6,
                        'color': COLORS_ZTF[i],
                        'symbol': 'o'}
                }
            )

            if switch_func == 'SHG1G2':
                xx = np.array(x)[:, cond]
            else:
                xx = x[cond]

            figs.append(
                {
                    'x': pdf.loc[cond, 'Phase'].values,
                    'y': fitfunc(xx, *popt),
                    'mode': 'markers',
                    'name': 'fit {:}'.format(filters[f]),
                    'marker': {
                        'size': 6,
                        'color': COLORS_ZTF[i],
                        'symbol': 'x',
                        'opacity': 0.5
                    }
                }
            )

            residual_figs.append(
                {
                    'x': pdf.loc[cond, 'Phase'].values,
                    'y': ydata.values - fitfunc(xx, *popt),
                    'error_y': {
                        'type': 'data',
                        'array': pdf.loc[cond, 'i:sigmapsf'].values,
                        'visible': True,
                        'color': COLORS_ZTF[i]
                    },
                    'mode': 'markers',
                    'name': 'Residual {:}'.format(filters[f]),
                    'showlegend': False,
                    'marker': {
                        'color': COLORS_ZTF[i],
                    }
                }
            )
    elif switch_band == 'combined':
        dd = {'': ['V band']}
        dd.update({i: [''] for i in params})
        df_table = pd.DataFrame(
            dd,
            index=['V band']
        )

        outdic = estimate_sso_params(
            magpsf_red=pdf['i:magpsf_red'].values,
            sigmapsf=pdf['i:sigmapsf'].values,
            phase=np.deg2rad(pdf['Phase'].values),
            filters=pdf['i:fid'].values,
            ra=np.deg2rad(pdf['i:ra'].values),
            dec=np.deg2rad(pdf['i:dec'].values),
            p0=p0,
            bounds=bounds,
            model=switch_func,
            normalise_to_V=True
        )
        if outdic['fit'] != 0:
            return dbc.Alert("The fitting procedure could not converge.", color='danger')

        popt = []
        for pindex, param in enumerate(params):
            # rad2deg
            if pindex >= 3:
                suffix = ''
            else:
                suffix = '_V'

            df_table[param] = '{:.2f} &plusmn; {:.2f}'.format(
                outdic[param + suffix],
                outdic['err_' + param + suffix]
            )

            if pindex <= 3:
                popt.append(outdic[param + suffix])
            else:
                popt.append(np.deg2rad(outdic[param + suffix]))

        color = compute_color_correction(pdf['i:fid'].values)
        ydata = pdf['i:magpsf_red'].values + color

        figs.append(
            {
                'x': pdf['Phase'].values,
                'y': ydata,
                'error_y': {
                    'type': 'data',
                    'array': pdf['i:sigmapsf'].values,
                    'visible': True,
                    'color': COLORS_ZTF[0]
                },
                'mode': 'markers',
                'name': 'V band',
                'customdata': list(
                    zip(
                        pdf['i:objectId'],
                        pdf['i:jd'].apply(lambda x: float(x) - 2400000.5),
                    )
                ),
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 6,
                    'color': COLORS_ZTF[0],
                    'symbol': 'o'}
            }
        )

        figs.append(
            {
                'x': pdf['Phase'].values,
                'y': fitfunc(x, *popt),
                'mode': 'markers',
                'name': 'fit combined',
                'marker': {
                    'size': 6,
                    'color': COLORS_ZTF[0],
                    'symbol': 'x',
                    'opacity': 0.5
                }
            }
        )

        residual_figs.append(
            {
                'x': pdf['Phase'].values,
                'y': ydata - fitfunc(x, *popt),
                'error_y': {
                    'type': 'data',
                    'array': pdf['i:sigmapsf'].values,
                    'visible': True,
                    'color': COLORS_ZTF[0]
                },
                'mode': 'markers',
                'name': 'Residual',
                'showlegend': False,
                'marker': {
                    'color': COLORS_ZTF[0],
                }
            }
        )
    layout_sso_phasecurve['title']['text'] += '  {:.2f}  '.format(outdic['chi2red'])

    residual_figure = {
        'data': residual_figs,
        "layout": layout_sso_phasecurve_residual
    }

    figure = {
        'data': figs,
        "layout": layout_sso_phasecurve
    }

    columns = [
        {
            'id': c,
            'name': c,
            'type': 'text',
            # 'hideable': True,
            'presentation': 'markdown',
        } for c in df_table.columns
    ]

    table = dash_table.DataTable(
        id='phasecurve_table',
        columns=columns,
        data=df_table.to_dict('records'),
        style_as_list_view=True,
        style_data={
            'backgroundColor': 'rgb(248, 248, 248, .7)'
        },
        style_table={'maxWidth': '100%'},
        style_cell={
            'padding': '5px',
            'textAlign': 'left',
            'border': '0.5px solid grey'
        },
        style_filter={'backgroundColor': 'rgb(238, 238, 238, .7)'},
        style_header={
            'backgroundColor': 'rgb(230, 230, 230)',
            'fontWeight': 'bold'
        }
    )

    graph1 = dcc.Graph(
        figure=figure,
        style={
            'width': '100%',
            'height': '25pc'
        },
        config={'displayModeBar': False}
    )

    graph2 = dcc.Graph(
        figure=residual_figure,
        style={
            'width': '100%',
            'height': '15pc'
        },
        config={'displayModeBar': False}
    )
    card = dmc.Paper(
        [
            graph1,
            html.Br(),
            graph2,
            html.Br(),
            table
        ], radius='xl', p='md', shadow='xl', withBorder=True
    )
    return card

def draw_tracklet_lightcurve(pdf) -> dict:
    """ Draw tracklet object lightcurve with errorbars

    Parameters
    ----------
    pathname: str
        Pathname of the current webpage (should be /ZTF19...).

    Returns
    ----------
    figure: dict

    """
    if pdf.empty:
        msg = """
        Object not associated to a tracklet
        """
        return html.Div([html.Br(), dbc.Alert(msg, color="danger")])

    # type conversion
    pdf['i:fid'] = pdf['i:fid'].apply(lambda x: int(x))

    # shortcuts
    mag = pdf['i:magpsf']
    err = pdf['i:sigmapsf']

    layout_tracklet_lightcurve['yaxis']['title'] = 'Difference magnitude'
    layout_tracklet_lightcurve['yaxis']['autorange'] = 'reversed'

    hovertemplate = r"""
    <b>objectId</b>: %{customdata[0]}<br>
    <b>%{yaxis.title.text}</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x:.2f}<br>
    <b>Date</b>: %{customdata[1]}
    <extra></extra>
    """

    def generate_plot(filt, marker, color, showlegend):
        if filt == 1:
            name = 'g band'
        else:
            name = 'r band'
        dic = {
            'x': pdf['i:ra'][pdf['i:fid'] == filt],
            'y': mag[pdf['i:fid'] == filt],
            'error_y': {
                'type': 'data',
                'array': err[pdf['i:fid'] == filt],
                'visible': True,
                'color': color
            },
            'mode': 'markers',
            'name': name,
            'showlegend': showlegend,
            'customdata': list(
                zip(
                    pdf['i:objectId'][pdf['i:fid'] == filt],
                    pdf['v:lastdate'][pdf['i:fid'] == filt]
                )
            ),
            'hovertemplate': hovertemplate,
            'marker': {
                'size': 12,
                'color': color,
                'symbol': marker}
        }
        return dic

    data_ = []
    for filt in np.unique(pdf['i:fid']):
        if filt == 1:
            data_.append(generate_plot(1, marker='o', color=COLORS_ZTF[0], showlegend=True))
        elif filt == 2:
            data_.append(generate_plot(2, marker='o', color=COLORS_ZTF[1], showlegend=True))

    figure = {
        'data': data_,
        "layout": layout_tracklet_lightcurve
    }

    graph = dcc.Graph(
        figure=figure,
        style={
            'width': '100%',
            'height': '25pc'
        },
        config={'displayModeBar': False}
    )

    alert = dbc.Alert(
        "Tracklet ID: {}".format(
            pdf['d:tracklet'].values[0],
        ),
        color="info"
    )

    card = html.Div(
        [
            alert,
            dmc.Paper(
                graph,
                radius='xl', p='md', shadow='xl', withBorder=True
            )
        ]
    )
    return card

def draw_tracklet_radec(pdf) -> dict:
    """ Draw tracklet object radec
    Parameters
    ----------
    pathname: str
        Pathname of the current webpage (should be /ZTF19...).
    Returns
    ----------
    figure: dict
    """
    if pdf.empty:
        msg = ""
        return msg

    # shortcuts
    ra = pdf['i:ra'].apply(lambda x: float(x))
    dec = pdf['i:dec'].apply(lambda x: float(x))

    hovertemplate = r"""
    <b>objectId</b>: %{customdata[0]}<br>
    <b>%{yaxis.title.text}</b>: %{y:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x:.2f}<br>
    <b>Date</b>: %{customdata[1]}
    <extra></extra>
    """
    figure = {
        'data': [
            {
                'x': ra,
                'y': dec,
                'mode': 'markers',
                'name': 'Observations',
                'customdata': list(
                    zip(
                        pdf['i:objectId'],
                        pdf['v:lastdate']
                    )
                ),
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 12,
                    'color': '#d62728',
                    'symbol': 'circle-open-dot'}
            }
        ],
        "layout": layout_sso_radec
    }
    graph = dcc.Graph(
        figure=figure,
        style={
            'width': '100%',
            'height': '15pc'
        },
        config={'displayModeBar': False}
    )
    card = html.Div(
        [
            dmc.Paper(
                graph,
                radius='xl', p='md', shadow='xl', withBorder=True
            )
        ]
    )
    return card

@app.callback(
    Output('alert_table', 'children'),
    [
        Input('object-data', 'children'),
        Input('lightcurve_cutouts', 'clickData')
    ])
def alert_properties(object_data, clickData):
    pdf_ = pd.read_json(object_data)

    if clickData is not None:
        time0 = clickData['points'][0]['x']
        # Round to avoid numerical precision issues
        jds = pdf_['i:jd'].apply(lambda x: np.round(x, 3)).values
        jd0 = np.round(Time(time0, format='iso').jd, 3)
        if jd0 in jds:
            pdf_ = pdf_[jds == jd0]
        else:
            return no_update

    pdf = pdf_.head(1)
    pdf = pdf.drop(
        columns=[
            'b:cutoutDifference_stampData',
            'b:cutoutScience_stampData',
            'b:cutoutTemplate_stampData'
        ]
    )
    pdf = pd.DataFrame({'Name': pdf.columns, 'Value': pdf.values[0]})
    columns = [
        {
            'id': c,
            'name': c,
            # 'hideable': True,
            'presentation': 'input',
            'type': 'text' if c == 'Name' else 'numeric', 'format': dash_table.Format.Format(precision=8),
        } for c in pdf.columns
    ]
    data = pdf.to_dict('records')
    table = dash_table.DataTable(
        data=data,
        columns=columns,
        id='result_table_alert',
        # page_size=10,
        page_action='none',
        style_as_list_view=True,
        filter_action="native",
        markdown_options={'link_target': '_blank'},
        # fixed_columns={'headers': True},#, 'data': 1},
        persistence=True,
        style_data={
            'backgroundColor': 'rgb(248, 248, 248, 1.0)',
        },
        style_table={'maxWidth': '100%', 'maxHeight': '300px', 'overflow': 'auto'},
        style_cell={
            'padding': '5px',
            'textAlign': 'left',
            'overflow': 'hidden',
            'overflow-wrap': 'anywhere',
            'max-width': '100%',
            'font-family': 'sans-serif',
            'fontSize': 14},
        style_filter={'backgroundColor': 'rgb(238, 238, 238, 1.0)'},
        style_filter_conditional=[
            {
                'if': {'column_id': 'Value'},
                'textAlign': 'left',
            }
        ],
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(248, 248, 248, 1.0)'
            },
            {
                'if': {'column_id': 'Name'},
                'backgroundColor': 'rgb(240, 240, 240, 1.0)',
                'white-space': 'normal',
                'min-width': '8pc',
            },
            {
                'if': {'column_id': 'Value'},
                'white-space': 'normal',
                'min-width': '8pc',
            }
        ],
        style_header={
            'backgroundColor': 'rgb(230, 230, 230, 1.0)',
            'fontWeight': 'bold', 'textAlign': 'center'
        },
        # Align the text in Markdown cells
        css=[dict(selector="p", rule="margin: 0; text-align: left")]
    )
    return table

@app.callback(
    Output('heatmap_stat', 'children'),
    [
        Input('url', 'pathname'),
        Input('object-stats', 'children')
    ]
)
def plot_heatmap(pathname, object_stats):
    """ Plot heatmap
    """
    pdf = pd.read_json(object_stats)
    pdf['date'] = [
        Time(x[4:8] + '-' + x[8:10] + '-' + x[10:12]).datetime
        for x in pdf.index.values
    ]
    years = np.unique(pdf['date'].apply(lambda x: x.year)).tolist()

    idx = pd.date_range(
        Time('{}-01-01'.format(np.min(years))).datetime,
        Time('{}-12-31'.format(np.max(years))).datetime
    )
    pdf.index = pd.DatetimeIndex(pdf.date)
    pdf = pdf.drop(columns='date')
    pdf = pdf.reindex(idx, fill_value=0)
    pdf['date'] = pdf.index.values

    fig = display_years(pdf, years)

    graph = dcc.Graph(
        figure=fig,
        config={'displayModeBar': False},
        style={
            'width': '100%',
        },
    )

    card = dbc.Card(
        dbc.CardBody(graph, className="m-0 p-0"),
        className="mt-3"
    )
    return card

@app.callback(
    Output('evolution', 'children'),
    [
        Input('url', 'pathname'),
        Input('dropdown_params', 'value'),
        Input('switch-cumulative', 'value'),
    ]
)
def plot_stat_evolution(pathname, param_name, switch):
    """ Plot evolution of parameters as a function of time

    TODO: connect the callback to a dropdown button to choose the parameter
    """
    if param_name is None or param_name == '':
        param_name = 'basic:sci'

    if param_name != 'basic:sci':
        param_name_ = param_name + ',basic:sci'
    else:
        param_name_ = param_name

    r = requests.post(
        '{}/api/v1/statistics'.format(APIURL),
        json={
            'date': '',
            'output-format': 'json',
            'columns': param_name_
        }
    )

    # Format output in a DataFrame
    pdf = pd.read_json(io.BytesIO(r.content))
    pdf = pdf.set_index('key:key')
    pdf = pdf.fillna(0)

    pdf['date'] = [
        Time(x[4:8] + '-' + x[8:10] + '-' + x[10:12]).datetime
        for x in pdf.index.values
    ]

    if param_name in dic_names:
        newcol = dic_names[param_name]
    else:
        newcol = param_name.replace('class', 'SIMBAD')

    if 1 in switch:
        pdf[param_name] = pdf[param_name].astype(int).cumsum()
        if param_name != 'basic:sci':
            pdf['basic:sci'] = pdf['basic:sci'].astype(int).cumsum()
    if 2 in switch:
        pdf[param_name] = pdf[param_name].astype(int) / pdf['basic:sci'].astype(int) * 100

    pdf = pdf.rename(columns={param_name: newcol})

    fig = px.bar(
        pdf,
        y=newcol,
        x='date',
        text=newcol,
    )
    fig.update_traces(
        textposition='outside',
        marker_color='rgb(21, 40, 79)'
    )
    fig.update_layout(
        uniformtext_minsize=8,
        uniformtext_mode='hide',
        showlegend=True
    )
    fig.update_layout(
        title='',
        margin=dict(t=0, r=0, b=0, l=0),
        showlegend=True,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    graph = dcc.Graph(
        figure=fig,
        style={
            'width': '100%',
            'height': '35pc'
        },
        config={'displayModeBar': False}
    )
    card = dbc.Card(
        dbc.CardBody(graph),
        className="mt-3",
    )
    return card

def display_year(data, year: int = None, month_lines: bool = True, fig=None, row: int = None):
    """ Display one year as heatmap

    help from https://community.plotly.com/t/colored-calendar-heatmap-in-dash/10907/17

    Parameters
    ----------
    data: np.array
        Number of alerts per day, for ALL days of the year.
        Should be 0 if no observations
    year: int
        Year to plot
    month_lines: bool
        If true, make lines to mark months
    fig: plotly object
    row: int
        Number of the row (position) in the final plot
    """
    if year is None:
        year = datetime.datetime.now().year

    # First and last day
    d1 = datetime.date(year, 1, 1)
    d2 = datetime.date(year, 12, 31)

    delta = d2 - d1

    # should be put elsewhere as constants?
    month_names = [
        'Jan', 'Feb', 'Mar',
        'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep',
        'Oct', 'Nov', 'Dec'
    ]
    month_days = [
        31, 28, 31,
        30, 31, 30,
        31, 31, 30,
        31, 30, 31
    ]

    # annees bisextiles
    if year in [2020, 2024, 2028, 2032, 2036]:
        month_days[1] = 29

    # black magic
    month_positions = (np.cumsum(month_days) - 15) / 7

    # Gives a list with datetimes for each day a year
    dates_in_year = [d1 + datetime.timedelta(i) for i in range(delta.days + 1)]

    # gives [0,1,2,3,4,5,6,0,1,2,3,4,5,6,…]
    # ticktext in xaxis dict translates this to weekdays
    weekdays_in_year = [i.weekday() for i in dates_in_year]

    # gives [1,1,1,1,1,1,1,2,2,2,2,2,2,2,…]
    weeknumber_of_dates = [
        int(i.strftime("%V"))
        if not (int(i.strftime("%V")) == 1 and i.month == 12)
        else 53 for i in dates_in_year
    ]

    # Careful, first days of January can belong to week 53...
    # so to avoid messing up, we set them to 1, and shift all
    # other weeks by one
    if weeknumber_of_dates[0] == 53:
        weeknumber_of_dates = [i + 1 for i in weeknumber_of_dates]
        weeknumber_of_dates = [
            1 if (j.month == 1 and i == 54)
            else i
            for i, j in zip(weeknumber_of_dates, dates_in_year)
        ]

    # Gives something like list of strings like ‘2018-01-25’
    # for each date. Used in data trace to make good hovertext.
    # text = [str(i) for i in dates_in_year]
    text = ['{:,} alerts processed in {}'.format(int(i), j) for i, j in zip(data, dates_in_year)]

    # Some examples
    colorscale = [[False, '#eeeeee'], [True, '#76cf63']]
    colorscale = [[False, '#495a7c'], [True, '#F5622E']]
    colorscale = [[False, '#15284F'], [True, '#3C8DFF']]
    colorscale = [[False, '#3C8DFF'], [True, '#15284F']]
    colorscale = [[False, '#4563a0'], [True, '#F5622E']]
    colorscale = [[False, '#eeeeee'], [True, '#F5622E']]

    # handle end of year
    data = [
        go.Heatmap(
            x=weeknumber_of_dates,
            y=weekdays_in_year,
            z=data,
            text=text,
            hoverinfo='text',
            xgap=3, # this
            ygap=3, # and this is used to make the grid-like apperance
            showscale=False,
            colorscale=colorscale
        )
    ]

    if month_lines:
        kwargs = dict(
            mode='lines',
            line=dict(
                color='#9e9e9e',
                width=1
            ),
            hoverinfo='skip'

        )
        for date, dow, wkn in zip(
                dates_in_year,
                weekdays_in_year,
                weeknumber_of_dates):
            if date.day == 1:
                data += [
                    go.Scatter(
                        x=[wkn - 0.5, wkn - 0.5],
                        y=[dow - 0.5, 6.5],
                        **kwargs
                    )
                ]
                if dow:
                    data += [
                        go.Scatter(
                            x=[wkn - 0.5, wkn + 0.5],
                            y=[dow - 0.5, dow - 0.5],
                            **kwargs
                        ),
                        go.Scatter(
                            x=[wkn + 0.5, wkn + 0.5],
                            y=[dow - 0.5, -0.5],
                            **kwargs
                        )
                    ]

    layout = go.Layout(
        title='Fink activity chart: number of ZTF alerts processed per night\n',
        height=150,
        yaxis=dict(
            showline=False, showgrid=False, zeroline=False,
            tickmode='array',
            ticktext=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            tickvals=[0, 1, 2, 3, 4, 5, 6],
            autorange="reversed"
        ),
        xaxis=dict(
            showline=False, showgrid=False, zeroline=False,
            tickmode='array',
            ticktext=month_names,
            tickvals=month_positions
        ),
        font={'size': 10, 'color': '#9e9e9e'},
        plot_bgcolor=('#fff'),
        margin=dict(t=40),
        showlegend=False
    )

    if fig is None:
        fig = go.Figure(data=data, layout=layout)
    else:
        fig.add_traces(data, rows=[(row + 1)] * len(data), cols=[1] * len(data))
        fig.update_layout(layout)
        fig.update_xaxes(layout['xaxis'])
        fig.update_yaxes(layout['yaxis'])
        fig.update_layout(
            title={
                'y': 0.995,
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            }
        )

    return fig


def display_years(pdf, years):
    """ Display all heatmaps stacked

    Parameters
    ----------
    pdf: pd.DataFrame
        DataFrame from the REST API
    years: list or tuple of int
        years to display

    Returns
    ----------
    fig: plotly figure object
    """
    fig = make_subplots(rows=len(years), cols=1, subplot_titles=years)
    for i, year in enumerate(years):
        # select the data for the year
        data = pdf[
            pdf['date'].apply(lambda x: x.year == year)
        ]['basic:sci'].values

        # Display year
        display_year(data, year=year, fig=fig, row=i, month_lines=True)

        # Fix the height
        fig.update_layout(height=200 * len(years))
    return fig

def make_daily_card(pdf, color, linecolor, title, description, height='12pc', scale='lin', withpercent=True, norm=None):
    """
    """
    if withpercent and norm != 0:
        text = ['{:.0f}%'.format(int(i) / norm * 100) for i in pdf.values[0]]
    else:
        text = pdf.values[0]

    pdf = pdf.replace('', 0)
    pdf = pdf.fillna(0).astype(int)
    fig = go.Figure(
        [
            go.Bar(x=pdf.columns, y=pdf.values[0], text=text, textposition='auto')
        ]
    )

    fig.update_layout(
        title='',
        margin=dict(t=0, r=0, b=0, l=0),
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    fig.update_traces(
        marker_color=color,
        marker_line_color=linecolor,
        marker_line_width=1.5, opacity=0.6
    )

    if scale == 'log':
        fig.update_yaxes(type='log')

    graph = dcc.Graph(
        figure=fig,
        style={
            'width': '100%',
            'height': height
        },
        config={'displayModeBar': False}
    )
    myid = '{}_stat'.format(title.split(' ')[0])
    card = dbc.Card(
        [
            dbc.CardBody(
                [
                    html.H6(
                        [
                            title,
                            html.I(
                                className="fa fa-question-circle fa-1x",
                                style={"border": "0px black solid", 'background': 'rgba(255, 255, 255, 0.0)', 'color': '#15284F90', 'float': 'right'},
                                id=myid
                            )
                        ],
                        className="card-subtitle"
                    ),
                    graph
                ]
            ),
            dbc.Popover(
                [dbc.PopoverBody(description)],
                target=myid,
                trigger="hover",
            ),
        ],
        className="mt-3",
    )
    return card

@app.callback(
    Output('hist_sci_raw', 'children'),
    [
        Input('url', 'pathname'),
        Input('dropdown_days', 'value'),
    ]
)
def hist_sci_raw(pathname, dropdown_days):
    """ Make an histogram
    """
    r = requests.post(
        '{}/api/v1/statistics'.format(APIURL),
        json={
            'date': '',
            'output-format': 'json',
            'columns': 'basic:raw,basic:sci'
        }
    )

    # Format output in a DataFrame
    pdf = pd.read_json(r.content)
    pdf = pdf.set_index('key:key')
    # Remove hbase specific fields
    if 'key:time' in pdf.columns:
        pdf = pdf.drop(columns=['key:time'])

    if dropdown_days is None or dropdown_days == '':
        dropdown_days = pdf.index[-1]
    pdf = pdf[pdf.index == dropdown_days]

    pdf = pdf.rename(columns={'basic:raw': 'Received', 'basic:sci': 'Processed'})
    norm = int(pdf['Received'].values[0])

    description = """
    Received alerts go through a series of quality cuts defined by Fink.
    Only alerts passing quality cuts are then further processed by the science pipelines.
    """

    card = make_daily_card(
        pdf, color='rgb(158,202,225)', linecolor='rgb(8,48,107)', title='Quality cuts', description=description, norm=norm
    )

    return card

@app.callback(
    Output('hist_catalogued', 'children'),
    [
        Input('url', 'pathname'),
        Input('dropdown_days', 'value'),
    ]
)
def hist_catalogued(pathname, dropdown_days):
    """ Make an histogram
    """
    r = requests.post(
        '{}/api/v1/statistics'.format(APIURL),
        json={
            'date': '',
            'output-format': 'json',
            'columns': 'class:Solar System MPC,class:simbad_tot,basic:sci'
        }
    )

    # Format output in a DataFrame
    pdf = pd.read_json(r.content)
    pdf = pdf.set_index('key:key')
    # Remove hbase specific fields
    if 'key:time' in pdf.columns:
        pdf = pdf.drop(columns=['key:time'])

    pdf = pdf.rename(columns={'class:Solar System MPC': 'MPC', 'class:simbad_tot': 'SIMBAD'})

    if dropdown_days is None or dropdown_days == '':
        dropdown_days = pdf.index[-1]
    pdf = pdf[pdf.index == dropdown_days]

    norm = int(pdf['basic:sci'].values[0])
    pdf = pdf.drop(columns=['basic:sci'])

    description = """
    All alerts passing quality cuts are matched against the SIMBAD database and the Minor Planet Center catalog.
    Percentages are given with respect to the number of processed alerts (i.e. the ones that pass quality cuts).
    """

    card = make_daily_card(
        pdf, color='rgb(21, 40, 79)', linecolor='rgb(4, 14, 33)', title='Crossmatch to', description=description, norm=norm
    )

    return card

@app.callback(
    Output('hist_classified', 'children'),
    [
        Input('url', 'pathname'),
        Input('dropdown_days', 'value'),
    ]
)
def hist_classified(pathname, dropdown_days):
    """ Make an histogram
    """
    r = requests.post(
        '{}/api/v1/statistics'.format(APIURL),
        json={
            'date': '',
            'output-format': 'json',
            'columns': 'basic:sci,class:Unknown'
        }
    )

    # Format output in a DataFrame
    pdf = pd.read_json(r.content)
    pdf = pdf.set_index('key:key')
    # Remove hbase specific fields
    if 'key:time' in pdf.columns:
        pdf = pdf.drop(columns=['key:time'])

    # In case class:unknown contains NaN (see https://github.com/astrolabsoftware/fink-utils/issues/25)
    pdf['class:Unknown'] = pdf['class:Unknown'].replace(np.nan, 0)
    pdf['Classified'] = pdf['basic:sci'].astype(int) - pdf['class:Unknown'].astype(int)
    pdf = pdf.rename(columns={'class:Unknown': 'Unclassified'})

    if dropdown_days is None or dropdown_days == '':
        dropdown_days = pdf.index[-1]
    pdf = pdf[pdf.index == dropdown_days]

    norm = int(pdf['basic:sci'].values[0])
    pdf = pdf.drop(columns=['basic:sci'])

    description = """
    Each alert goes through the Fink science modules, and eventually gets a classification label, either from machine learning based modules or from crossmatch.
    Percentages are given with respect to the number of processed alerts (i.e. the ones that pass quality cuts).
    """

    card = make_daily_card(
        pdf, color='rgb(245, 98, 46)', linecolor='rgb(135, 86, 69)', title='Classification', description=description, norm=norm
    )

    return card

@app.callback(
    Output('hist_candidates', 'children'),
    [
        Input('url', 'pathname'),
        Input('dropdown_days', 'value'),
    ]
)
def hist_candidates(pathname, dropdown_days):
    """ Make an histogram
    """
    r = requests.post(
        '{}/api/v1/statistics'.format(APIURL),
        json={
            'date': '',
            'output-format': 'json',
            'columns': 'class:Solar System candidate,class:SN candidate,class:Early SN Ia candidate,class:Kilonova candidate'
        }
    )

    # Format output in a DataFrame
    pdf = pd.read_json(r.content)
    pdf = pdf.set_index('key:key')
    # Remove hbase specific fields
    if 'key:time' in pdf.columns:
        pdf = pdf.drop(columns=['key:time'])

    pdf = pdf.rename(
        columns={
            'class:Solar System candidate': 'SSO',
            'class:SN candidate': 'SNe',
            'class:Early SN Ia candidate': 'SN Ia',
            'class:Kilonova candidate': 'Kilonova'
        }
    )

    if dropdown_days is None or dropdown_days == '':
        dropdown_days = pdf.index[-1]
    pdf = pdf[pdf.index == dropdown_days]

    description = """
    Number of alerts for a subset of classes: early type Ia supernova (SN Ia), supernovae or core-collapse (SNe), Kilonova, or Solar System candidates (SSO).
    """

    card = make_daily_card(
        pdf, color='rgb(213, 213, 211)', linecolor='rgb(138, 138, 132)', title='Selected Fink candidates', description=description, withpercent=False
    )

    return card

@app.callback(
    Output('daily_classification', 'children'),
    [
        Input('url', 'pathname'),
        Input('dropdown_days', 'value'),
    ]
)
def fields_exposures(pathname, dropdown_days):
    """ Make an histogram
    """
    r = requests.post(
        '{}/api/v1/statistics'.format(APIURL),
        json={
            'date': '',
            'output-format': 'json',
            'columns': '*'
        }
    )

    # Format output in a DataFrame
    pdf = pd.read_json(r.content)
    pdf = pdf.set_index('key:key')
    # Remove hbase specific fields
    if 'key:time' in pdf.columns:
        pdf = pdf.drop(columns=['key:time'])

    to_drop = [i for i in pdf.columns if i.startswith('basic:')]
    pdf = pdf.drop(columns=to_drop)

    pdf = pdf.rename(columns={i: i.split(':')[1] for i in pdf.columns})

    if dropdown_days is None or dropdown_days == '':
        dropdown_days = pdf.index[-1]
    pdf = pdf[pdf.index == dropdown_days]

    description = "Histogram of Fink labels for all processed alerts during the night. For readability the plot displays only a few labels on the x-axis. Select a region to zoom in and discover more labels (alphabetical sort)."

    card = make_daily_card(
        pdf,
        color='rgb(21, 40, 79)', linecolor='rgb(4, 14, 33)',
        title='Individual Fink classifications',
        description=description,
        height='20pc', scale='log', withpercent=False
    )

    return card

@app.callback(
    Output('coordinates', 'children'),
    [
        Input('object-data', 'children'),
        Input('coordinates_chips', 'value')
    ])
def draw_alert_astrometry(object_data, kind) -> dict:
    """ Draw SSO object astrometry, that is difference position wrt ephemerides
    from the miriade IMCCE service.

    Parameters
    ----------
    pathname: str
        Pathname of the current webpage (should be /ZTF19...).

    Returns
    ----------
    figure: dict
    """
    pdf = pd.read_json(object_data)

    mean_ra = np.mean(pdf['i:ra'])
    mean_dec = np.mean(pdf['i:dec'])

    deltaRAcosDEC = (pdf['i:ra'] - mean_ra) * np.cos(np.radians(pdf['i:dec'])) * 3600
    deltaDEC = (pdf['i:dec'] - mean_dec) * 3600

    hovertemplate = r"""
    <b>%{yaxis.title.text}</b>: %{y:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x:.2f}<br>
    <b>mjd</b>: %{customdata}
    <extra></extra>
    """
    diff_g = {
        'x': deltaRAcosDEC[pdf['i:fid'] == 1],
        'y': deltaDEC[pdf['i:fid'] == 1],
        'mode': 'markers',
        'name': 'g band',
        'customdata': pdf['i:jd'][pdf['i:fid'] == 1].apply(lambda x: float(x) - 2400000.5),
        'hovertemplate': hovertemplate,
        'marker': {
            'size': 6,
            'color': COLORS_ZTF[0],
            'symbol': 'o'}
    }

    diff_r = {
        'x': deltaRAcosDEC[pdf['i:fid'] == 2],
        'y': deltaDEC[pdf['i:fid'] == 2],
        'mode': 'markers',
        'name': 'r band',
        'customdata': pdf['i:jd'][pdf['i:fid'] == 2].apply(lambda x: float(x) - 2400000.5),
        'hovertemplate': hovertemplate,
        'marker': {
            'size': 6,
            'color': COLORS_ZTF[1],
            'symbol': 'o'}
    }

    figure = {
        'data': [
            diff_g,
            diff_r,
        ],
        "layout": layout_sso_astrometry
    }
    # Force equal aspect ratio
    figure['layout']['yaxis']['scaleanchor'] = 'x'
    # figure['layout']['yaxis']['scaleratio'] = 1

    graph = dcc.Graph(
        figure=figure,
        style={
            'width': '100%',
            'height': '20pc',
            # Prevent occupying more than 60% of the screen height
            'max-height': '60vh',
            # Force equal aspect
            # 'display':'block',
            # 'aspect-ratio': '1',
            # 'margin': '1px'
        },
        config={'displayModeBar': False},
        responsive=True
    )
    card1 = dmc.Paper(graph, radius='sm', p='xs', shadow='sm', withBorder=True, className="mb-1")

    coord = SkyCoord(mean_ra, mean_dec, unit='deg')

    # degrees
    if kind == 'GAL':
        coords_deg = coord.galactic.to_string('decimal', precision=6)
    else:
        coords_deg = coord.to_string('decimal', precision=6)

    # hmsdms
    if kind == 'GAL':
        # Galactic coordinates are in DMS only
        coords_hms = coord.galactic.to_string('dms', precision=2)
    else:
        coords_hms = coord.to_string('hmsdms', precision=2)

    card2 = dmc.Center(
        dmc.Prism(children=coords_deg, language="python", style={'width': '80%'})
    )

    card3 = dmc.Center(
        dmc.Prism(children=coords_hms, language="python", style={'width': '80%'})
    )

    return html.Div([card1, card2, card3])

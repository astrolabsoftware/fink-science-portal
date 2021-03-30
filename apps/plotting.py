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
import pandas as pd
import numpy as np
from gatspy import periodic

import java
import copy
from astropy.time import Time

import dash
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import dash_core_components as dcc

from apps.utils import convert_jd, readstamp, _data_stretch, convolve
from apps.utils import apparent_flux, dc_mag

from pyLIMA import event
from pyLIMA import telescopes
from pyLIMA import microlmodels, microltoolbox
from pyLIMA.microloutputs import create_the_fake_telescopes

from app import client, app, clientSSO

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

all_radio_options = {
    "Difference magnitude": ["Difference magnitude", "DC magnitude", "DC apparent flux"],
    "DC magnitude": ["Difference magnitude", "DC magnitude", "DC apparent flux"],
    "DC apparent flux": ["Difference magnitude", "DC magnitude", "DC apparent flux"]
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

def extract_scores(data: java.util.TreeMap) -> pd.DataFrame:
    """ Extract SN scores from the data
    """
    values = ['i:jd', 'd:snn_snia_vs_nonia', 'd:snn_sn_vs_all', 'd:rfscore']
    pdfs = pd.DataFrame.from_dict(data, orient='index')
    if pdfs.empty:
        return pdfs
    return pdfs[values]

@app.callback(
    Output('switch-mag-flux-score', 'options'),
    [Input('switch-mag-flux', 'value')])
def set_radio2_options(selected_radio):
    return [{'label': i, 'value': i} for i in all_radio_options[selected_radio]]


@app.callback(
    Output('switch-mag-flux-score', 'value'),
    [Input('switch-mag-flux-score', 'options'), Input('switch-mag-flux', 'value')])
def set_radio1_value(available_options, value):
    index = [available_options.index(i) for i in available_options if i['label'] == value][0]
    return available_options[index]['value']

@app.callback(
    [
        Output('lightcurve_cutouts', 'figure'),
        Output('lightcurve_scores', 'figure')
    ],
    [
        Input('switch-mag-flux', 'value'),
        Input('switch-mag-flux-score', 'value'),
        Input('url', 'pathname'),
        Input('object-data', 'children'),
        Input('object-upper', 'children'),
        Input('object-uppervalid', 'children')
    ])
def draw_lightcurve(switch1: int, switch2: int, pathname: str, object_data, object_upper, object_uppervalid) -> dict:
    """ Draw object lightcurve with errorbars

    Parameters
    ----------
    switch{i}: int
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
    changed_id = [p['prop_id'] for p in dash.callback_context.triggered][0]
    if 'switch-mag-flux-score' in changed_id:
        switch = switch2
    else:
        switch = switch1

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
    if switch == "Difference magnitude":
        layout_lightcurve['yaxis']['title'] = 'Difference magnitude'
        layout_lightcurve['yaxis']['autorange'] = 'reversed'
    elif switch == "DC magnitude":
        # inplace replacement
        mag, err = np.transpose(
            [
                dc_mag(*args) for args in zip(
                    pdf['i:fid'].values,
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
    elif switch == "DC apparent flux":
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
                    'color': '#1f77b4'
                },
                'mode': 'markers',
                'name': 'g band',
                'customdata': pdf['i:jd'].apply(lambda x: x - 2400000.5)[pdf['i:fid'] == 1],
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 12,
                    'color': '#1f77b4',
                    'symbol': 'o'}
            },
            {
                'x': dates[pdf['i:fid'] == 2],
                'y': mag[pdf['i:fid'] == 2],
                'error_y': {
                    'type': 'data',
                    'array': err[pdf['i:fid'] == 2],
                    'visible': True,
                    'color': '#ff7f0e'
                },
                'mode': 'markers',
                'name': 'r band',
                'customdata': pdf['i:jd'].apply(lambda x: x - 2400000.5)[pdf['i:fid'] == 2],
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 12,
                    'color': '#ff7f0e',
                    'symbol': 'o'}
            }
        ],
        "layout": layout_lightcurve
    }

    if switch == "Difference magnitude":
        pdf_upper = pd.read_json(object_upper)
        # <b>candid</b>: %{customdata[0]}<br> not available in index tables...
        hovertemplate_upper = r"""
        <b>diffmaglim</b>: %{y:.2f}<br>
        <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
        <b>mjd</b>: %{customdata}
        <extra></extra>
        """
        if not pdf_upper.empty:
            dates2 = pdf_upper['i:jd'].apply(lambda x: convert_jd(float(x), to='iso'))
            figure['data'].append(
                {
                    'x': dates2[pdf_upper['i:fid'] == 1],
                    'y': pdf_upper['i:diffmaglim'][pdf_upper['i:fid'] == 1],
                    'mode': 'markers',
                    'customdata': pdf_upper['i:jd'].apply(lambda x: x - 2400000.5)[pdf_upper['i:fid'] == 1],
                    'hovertemplate': hovertemplate_upper,
                    'marker': {
                        'color': '#1f77b4',
                        'symbol': 'triangle-down-open'
                    },
                    'showlegend': False
                }
            )
            figure['data'].append(
                {
                    'x': dates2[pdf_upper['i:fid'] == 2],
                    'y': pdf_upper['i:diffmaglim'][pdf_upper['i:fid'] == 2],
                    'mode': 'markers',
                    'customdata': pdf_upper['i:jd'].apply(lambda x: x - 2400000.5)[pdf_upper['i:fid'] == 2],
                    'hovertemplate': hovertemplate_upper,
                    'marker': {
                        'color': '#ff7f0e',
                        'symbol': 'triangle-down-open'
                    },
                    'showlegend': False
                }
            )
        pdf_upperv = pd.read_json(object_uppervalid)
        # <b>candid</b>: %{customdata[0]}<br> not available in index tables...
        hovertemplate_upperv = r"""
        <b>%{yaxis.title.text}</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
        <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
        <b>mjd</b>: %{customdata}
        <extra></extra>
        """
        if not pdf_upperv.empty:
            dates2 = pdf_upperv['i:jd'].apply(lambda x: convert_jd(float(x), to='iso'))
            mask = np.array([False if i in pdf['i:jd'].values else True for i in pdf_upperv['i:jd'].values])
            dates2 = dates2[mask]
            pdf_upperv = pdf_upperv[mask]
            figure['data'].append(
                {
                    'x': dates2[pdf_upperv['i:fid'] == 1],
                    'y': pdf_upperv['i:magpsf'][pdf_upperv['i:fid'] == 1],
                    'error_y': {
                        'type': 'data',
                        'array': pdf_upperv['i:sigmapsf'][pdf_upperv['i:fid'] == 1],
                        'visible': True,
                        'color': '#1f77b4'
                    },
                    'mode': 'markers',
                    'customdata': pdf_upperv['i:jd'].apply(lambda x: x - 2400000.5)[pdf_upperv['i:fid'] == 1],
                    'hovertemplate': hovertemplate_upperv,
                    'marker': {
                        'color': '#1f77b4',
                        'symbol': 'triangle-up'
                    },
                    'showlegend': False
                }
            )
            figure['data'].append(
                {
                    'x': dates2[pdf_upperv['i:fid'] == 2],
                    'y': pdf_upperv['i:magpsf'][pdf_upperv['i:fid'] == 2],
                    'error_y': {
                        'type': 'data',
                        'array': pdf_upperv['i:sigmapsf'][pdf_upperv['i:fid'] == 2],
                        'visible': True,
                        'color': '#ff7f0e'
                    },
                    'mode': 'markers',
                    'customdata': pdf_upperv['i:jd'].apply(lambda x: x - 2400000.5)[pdf_upperv['i:fid'] == 2],
                    'hovertemplate': hovertemplate_upperv,
                    'marker': {
                        'color': '#ff7f0e',
                        'symbol': 'triangle-up'
                    },
                    'showlegend': False
                }
            )
    return figure, figure

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
                    'color': '#2ca02c',
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
                    'color': '#d62728',
                    'symbol': 'square'}
            },
            {
                'x': dates,
                'y': pdf['d:rfscore'],
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
                    'color': '#9467bd',
                    'symbol': 'diamond'}
            }
        ],
        "layout": layout_scores
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
        'i:fid',
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
        position = np.where(jds == jd0)[0][0]

    # Grab the cutout data
    cutout = readstamp(
        client.repository().get(
            pdfs['b:cutout{}_stampData'.format(kind.capitalize())].values[position]
        )
    )
    return cutout

@app.callback(
    Output("stamps", "children"),
    [
        Input('lightcurve_cutouts', 'clickData'),
        Input('object-data', 'children'),
    ])
def draw_cutouts(clickData, object_data):
    """ Draw difference cutout data based on lightcurve data
    """
    if clickData is not None:
        jd0 = clickData['points'][0]['x']
    else:
        jd0 = None
    figs = []
    for kind in ['science', 'template', 'difference']:
        try:
            data = extract_cutout(object_data, jd0, kind=kind)
            figs.append(draw_cutout(data, kind))
        except OSError:
            data = dcc.Markdown("Load fail, refresh the page")
            figs.append(data)
    return figs

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

def draw_cutout(data, title, lower_bound=0, upper_bound=1):
    """ Draw a cutout data
    """
    # Update graph data for stamps
    data = np.nan_to_num(data)

    data = sigmoid_normalizer(data, lower_bound, upper_bound)

    data = data[::-1]
    data = convolve(data, smooth=1, kernel='gauss')

    fig = go.Figure(
        data=go.Heatmap(
            z=data, showscale=False, colorscale='Greys_r'
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
        width=150, height=150,
        autosize=False)

    graph = dcc.Graph(
        id='{}-stamps'.format(title),
        figure=fig,
        style={
            'display': 'inline-block',
        },
        config={'displayModeBar': False}
    )
    return graph

@app.callback(
    Output('variable_plot', 'children'),
    [
        Input('nterms_base', 'value'),
        Input('nterms_band', 'value'),
        Input('manual_period', 'value'),
        Input('submit_variable', 'n_clicks'),
        Input('object-data', 'children')
    ])
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
        layout_phase_['title']['text'] = 'Period: {} days'.format(period)

        if '1' in np.unique(pdf['i:fid'].values):
            plot_filt1 = {
                'x': phase[pdf['i:fid'] == '1'],
                'y': mag_dc[pdf['i:fid'] == '1'],
                'error_y': {
                    'type': 'data',
                    'array': err_dc[pdf['i:fid'] == '1'],
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
                'y': mag_dc[pdf['i:fid'] == '2'],
                'error_y': {
                    'type': 'data',
                    'array': err_dc[pdf['i:fid'] == '2'],
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
        graph = dcc.Graph(
            figure=figure,
            style={
                'width': '100%',
                'height': '25pc'
            },
            config={'displayModeBar': False}
        )
        return graph

    # quite referentially opaque...
    return ""

@app.callback(
    [
        Output('mulens_plot', 'children'),
        Output('mulens_params', 'children'),
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
                    'color': '#1f77b4'
                },
                'mode': 'markers',
                'name': 'g band',
                'text': [convert_jd(t, to='iso') for t in normalised_lightcurves[0][:, 0]],
                'marker': {
                    'size': 12,
                    'color': '#1f77b4',
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
                    'color': '#ff7f0e'
                },
                'mode': 'markers',
                'name': 'r band',
                'text': [convert_jd(t, to='iso') for t in normalised_lightcurves[index][:, 0]],
                'marker': {
                    'size': 12,
                    'color': '#ff7f0e',
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
        ---
        """.format(
            params[names['to']],
            err[names['to']],
            params[names['tE']],
            err[names['tE']],
            params[names['uo']],
            err[names['uo']],
            params[-1] / dof
        )
        return graph, mulens_params

    mulens_params = """
    ```python
    # Fitted parameters
    t0: None
    tE: None
    u0: None
    chi2: None
    ```
    ---
    """
    return "", mulens_params

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

@app.callback(
    Output('sso_lightcurve', 'children'),
    [
        Input('url', 'pathname'),
        Input('object-sso', 'children')
    ])
def draw_sso_lightcurve(pathname: str, object_sso) -> dict:
    """ Draw SSO object lightcurve with errorbars

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
        ### Not referenced in the Minor Planet Center
        """
        return dcc.Markdown(msg)

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
    figure = {
        'data': [
            {
                'x': dates[pdf['i:fid'] == 1],
                'y': mag[pdf['i:fid'] == 1],
                'error_y': {
                    'type': 'data',
                    'array': err[pdf['i:fid'] == 1],
                    'visible': True,
                    'color': '#1f77b4'
                },
                'mode': 'markers',
                'name': 'g band',
                'customdata': pdf['i:jd'].apply(lambda x: float(x) - 2400000.5)[pdf['i:fid'] == 1],
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 12,
                    'color': '#1f77b4',
                    'symbol': 'o'}
            },
            {
                'x': dates[pdf['i:fid'] == 2],
                'y': mag[pdf['i:fid'] == 2],
                'error_y': {
                    'type': 'data',
                    'array': err[pdf['i:fid'] == 2],
                    'visible': True,
                    'color': '#ff7f0e'
                },
                'mode': 'markers',
                'name': 'r band',
                'customdata': pdf['i:jd'].apply(lambda x: float(x) - 2400000.5)[pdf['i:fid'] == 2],
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 12,
                    'color': '#ff7f0e',
                    'symbol': 'o'}
            }
        ],
        "layout": layout_sso_lightcurve
    }
    graph = dcc.Graph(
        figure=figure,
        style={
            'width': '100%',
            'height': '15pc'
        },
        config={'displayModeBar': False}
    )
    return graph

@app.callback(
    Output('sso_radec', 'children'),
    [
        Input('url', 'pathname'),
        Input('object-sso', 'children')
    ])
def draw_sso_radec(pathname: str, object_sso) -> dict:
    """ Draw SSO object radec

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
        msg = ""
        return dcc.Markdown(msg)

    # shortcuts
    ra = pdf['i:ra'].apply(lambda x: float(x))
    dec = pdf['i:dec'].apply(lambda x: float(x))

    hovertemplate = r"""
    <b>objectId</b>: %{customdata[0]}<br>
    <b>%{yaxis.title.text}</b>: %{y:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x:.2f}<br>
    <b>mjd</b>: %{customdata[1]}
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
                        pdf['i:jd'].apply(lambda x: float(x) - 2400000.5),
                    )
                ),
                'hovertemplate': hovertemplate,
                'marker': {
                    'size': 12,
                    'color': 'rgba(135, 206, 250, 0.85)',
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
    return graph

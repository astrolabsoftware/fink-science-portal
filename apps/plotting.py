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
# import os
import io
import copy
import base64
import datetime
from copy import deepcopy

import dash
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from astropy.coordinates import SkyCoord
import astropy.units as u
from astropy.time import Time
from dash import (
    ALL,
    Input,
    Output,
    State,
    clientside_callback,
    dash_table,
    dcc,
    html,
    no_update,
)
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify
from fink_utils.photometry.conversion import apparent_flux, dc_mag
from fink_utils.photometry.utils import is_source_behind
from fink_utils.sso.spins import (
    compute_color_correction,
    estimate_sso_params,
    func_hg,
    func_hg1g2,
    func_hg1g2_with_spin,
    func_hg12,
)
from gatspy import periodic
from plotly.subplots import make_subplots

from scipy.optimize import curve_fit

from app import app

# from apps import __file__
from apps.statistics import dic_names
from apps.utils import (
    _data_stretch,
    class_colors,
    convert_jd,
    extract_color,
    query_and_order_statistics,
    readstamp,
    request_api,
    sine_fit,
    apparent_flux_dr,
)
import apps.observability.utils as observability

COLORS_ZTF = ["#15284F", "#F5622E"]
COLORS_ZTF_NEGATIVE = ["#274667", "#F57A2E"]

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
    "rgb(49,54,149)",
]

all_radio_options = {
    "Difference magnitude": ["Difference magnitude", "DC magnitude", "DC flux"],
    "DC magnitude": ["Difference magnitude", "DC magnitude", "DC flux"],
    "DC flux": ["Difference magnitude", "DC magnitude", "DC flux"],
}

layout_lightcurve = dict(
    autosize=True,
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        "align": "left",
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        yanchor="bottom",
        y=1.02,
        bgcolor="rgba(218, 223, 225, 0.3)",
    ),
    xaxis={
        "title": "Observation date",
        "automargin": True,
        "zeroline": False,
    },
    yaxis={
        "autorange": "reversed",
        "title": "Magnitude",
        "automargin": True,
        "zeroline": False,
    },
)

layout_lightcurve_preview = dict(
    automargin=True,
    margin=dict(l=50, r=0, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        "align": "left",
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        y=1.2,
        bgcolor="rgba(218, 223, 225, 0.3)",
    ),
    xaxis={
        "title": "Observation date",
        "automargin": True,
    },
    yaxis={
        "autorange": "reversed",
        "title": "Magnitude",
        "automargin": True,
    },
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
        y=1.02,
        xanchor="right",
        x=1,
        bgcolor="rgba(218, 223, 225, 0.3)",
    ),
    xaxis={
        "title": "Phase",
        "zeroline": False,
    },
    yaxis={
        "autorange": "reversed",
        "title": "Apparent DC Magnitude",
        "zeroline": False,
    },
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
        bgcolor="rgba(218, 223, 225, 0.3)",
    ),
    hoverlabel={
        "align": "left",
    },
    xaxis={
        "title": "Observation date",
        "automargin": True,
    },
    yaxis={
        "title": "Score",
        "range": [0, 1],
    },
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
        bgcolor="rgba(218, 223, 225, 0.3)",
    ),
    hoverlabel={
        "align": "left",
    },
    xaxis={
        "automargin": True,
        "title": "Observation date",
    },
    yaxis={
        "title": "g - r",
    },
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
        bgcolor="rgba(218, 223, 225, 0.3)",
    ),
    hoverlabel={
        "align": "left",
    },
    xaxis={
        "automargin": True,
        "title": "Observation date",
    },
    yaxis={
        "title": "Rate (mag/day)",
    },
)

layout_sso_lightcurve = dict(
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        "align": "left",
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        yanchor="bottom",
        y=1.02,
        bgcolor="rgba(218, 223, 225, 0.3)",
    ),
    xaxis={
        "title": "Observation date",
        "automargin": True,
    },
    yaxis={
        "autorange": "reversed",
        "title": "Magnitude",
        "automargin": True,
    },
)

layout_sso_astrometry = dict(
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        "align": "left",
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        yanchor="bottom",
        y=1.02,
        bgcolor="rgba(218, 223, 225, 0.3)",
    ),
    xaxis={
        "title": "&#916;RA cos(Dec) ('')",
        "automargin": True,
    },
    yaxis={
        "title": "&#916;Dec ('')",
        "automargin": True,
        "scaleanchor": "x",
        "scaleratio": 1,
    },
)

layout_sso_phasecurve = dict(
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        "align": "left",
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        yanchor="bottom",
        y=1.02,
        bgcolor="rgba(218, 223, 225, 0.3)",
    ),
    xaxis={
        "title": "Phase angle [degree]",
        "automargin": True,
    },
    yaxis={
        "autorange": "reversed",
        "title": "Observed magnitude [mag]",
        "automargin": True,
    },
    title={
        "text": r"Reduced $\chi^2$",
        "y": 1.01,
        "yanchor": "bottom",
    },
)

layout_sso_phasecurve_residual = dict(
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        "align": "left",
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        yanchor="bottom",
        y=1.02,
        bgcolor="rgba(218, 223, 225, 0.3)",
    ),
    xaxis={
        "title": "Phase angle [degree]",
        "automargin": True,
    },
    yaxis={
        "range": [-1, 1],
        "title": "Residual [mag]",
        "automargin": True,
    },
)

layout_sso_radec = dict(
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        "align": "left",
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        yanchor="bottom",
        y=1.02,
        bgcolor="rgba(218, 223, 225, 0.3)",
    ),
    yaxis={
        "title": "Declination",
        "automargin": True,
    },
    xaxis={
        "autorange": "reversed",
        "title": "Right Ascension",
        "automargin": True,
    },
)

layout_tracklet_lightcurve = dict(
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        "align": "left",
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        yanchor="bottom",
        y=1.02,
        bgcolor="rgba(218, 223, 225, 0.3)",
    ),
    yaxis={
        "autorange": "reversed",
        "title": "Magnitude",
        "automargin": True,
    },
    xaxis={
        "autorange": "reversed",
        "title": "Right Ascension",
        "automargin": True,
    },
)

layout_blazar = dict(
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
        bgcolor="rgba(218, 223, 225, 0.3)",
    ),
    xaxis={
        "title": "Observation date",
        "zeroline": False,
    },
    yaxis={
        "title": r"Standardized flux &#981;/&#981;<sub>median</sub>",
        "zeroline": False,
    },
)

layout_observability = dict(
    automargin=True,
    margin=dict(l=50, r=30, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        "align": "left",
        "namelength": -1,
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        yanchor="bottom",
        y=1.02,
        bgcolor="rgba(218, 223, 225, 0.3)",
    ),
    yaxis={
        "range":[0,90],
        "title": "Elevation (&deg;)",
        "automargin": True,
    },
    yaxis2={
        "title": "Relative airmass",
        "overlaying": "y",
        "side": "right",
        "tickvals": 90 - np.degrees(np.arccos(1/np.array([1,2,3]))),
        "ticktext": [1,2,3],
        "showgrid": False,
        "showticklabels": True,
        "matches": "y",
        "anchor": "x"
    },
)

"""
def plot_altitude(target, observatory, astro_time, UTC=0, ax=None, show_moon_elevation=False):
    import matplotlib.pyplot as plt
    from matplotlib import dates
    from astroplan import Observer

    observer = Observer.at_site(observatory)

    fig = plt.figure()

    if ax is None:
        ax = plt.gca()

    time = Time(astro_time) + np.linspace(0, 24, 100)*u.hour
    altitude = observer.altaz(time, target).alt

    if show_moon_elevation:
        moon_altitude = observer.moon_altaz(time).alt
        ax.plot(time.plot_date, moon_altitude, color='black', label='Moon')

    ax.plot(time.plot_date, altitude, color='r', label='Target')
    #num_ticks = 9

    # Format the time axis (UTC time)
    ax.set_xlim([time[0].plot_date, time[-1].plot_date])
    ax.set_xticks(np.linspace(time[0].plot_date, time[-1].plot_date, 9))
    date_formatter = dates.DateFormatter('%H:%M')
    ax.xaxis.set_major_formatter(date_formatter)
    plt.setp(ax.get_xticklabels(), rotation=30, ha='right')

    # Format of the secondary time axis (local time)
    def UTC_to_local(x, UTC=UTC):
        return x + UTC / 24

    def local_to_UTC(x, UTC=UTC):
        return x - UTC / 24

    secax = ax.secondary_xaxis('top', functions=(UTC_to_local, local_to_UTC))
    secax.set_xlim([time[0].plot_date, time[-1].plot_date])
    secax.set_xticks(np.linspace(UTC_to_local(time[0].plot_date), UTC_to_local(time[-1].plot_date), 9))
    secax.set_xlabel('Local Time [hours]')
    date_formatter = dates.DateFormatter('%H:%M')
    secax.xaxis.set_major_formatter(date_formatter)
    plt.setp(secax.get_xticklabels(), rotation=-30, ha='right')

    # Shade background during night time
    start = time[0].datetime

        # Calculate and order twilights and set plotting alpha for each
    twilights = [
        (observer.sun_set_time(Time(start), which='next').datetime, 'white', 'Day'),
        (observer.twilight_evening_civil(Time(start), which='next').datetime, 'lightsteelblue', 'No Sun'),
        (observer.twilight_evening_nautical(Time(start), which='next').datetime, 'royalblue', 'Civil night'),
        (observer.twilight_evening_astronomical(Time(start), which='next').datetime, 'blue', 'Nautical night'),
        (observer.twilight_morning_astronomical(Time(start), which='next').datetime, 'midnightblue', 'Astronomical night'),
        (observer.twilight_morning_nautical(Time(start), which='next').datetime, 'blue', 'Astronomical morning'),
        (observer.twilight_morning_civil(Time(start), which='next').datetime, 'royalblue', 'Nautical morning'),
        (observer.sun_rise_time(Time(start), which='next').datetime, 'lightsteelblue', 'Civil morning'),
    ]

    #twilights.sort(key=operator.itemgetter(0))
    for i in range(1, 5):
        ax.axvspan(
            twilights[i - 1][0], twilights[i][0],
            ymin=0, ymax=1,
            facecolor=twilights[i][1], edgecolor='none', alpha=0.5,
            label=twilights[i][2]
        )
    for i in range(5, len(twilights)):
        ax.axvspan(
            twilights[i - 1][0], twilights[i][0],
            ymin=0, ymax=1,
            facecolor=twilights[i][1], edgecolor='none', alpha=0.5,
        )

    # unicde_Moon_phases = [
    #     '\U0001F311', '\U0001F312',
    #     '\U0001F313', '\U0001F314',
    #     '\U0001F315', '\U0001F316',
    #     '\U0001F317', '\U0001F318'
    # ]
    # unicode_Moon = unicde_Moon_phases[moon_phase(observer, time[0]) - 1]
    # ax.text(
    #     time[0].plot_date + 0.01 * (time[-1].plot_date - time[0].plot_date),
    #     0.01 * 90,
    #     unicode_Moon,
    #     fontsize=15, fontname='Segoe UI Emoji',
    #     ha='left', va='bottom'
    # )

    ax.set_ylim(0, 90)
    ax.tick_params(right=True)

    airmass_ticks = np.array([1, 2, 3])
    #ax.set_yticks([20, 30, 40, 50, 60, 90])
    altitude_ticks = 90 - np.degrees(np.arccos(1/airmass_ticks))

    ax2 = ax.twinx()
    # ax2.invert_yaxis()
    ax2.set_yticks(altitude_ticks)
    ax2.set_yticklabels(airmass_ticks)
    ax2.set_ylim(ax.get_ylim())
    ax2.set_ylabel('Relative airmass')

    # Set labels.
    ax.set_ylabel("Elevation [degrees]")
    ax.set_xlabel("UTC Time [hours]")
    ax.set_title(time[0].value[:10] + ' / MJD' + str(int(time[0].mjd)) + ' at ' + observer.name)
    ax.legend(ncol=2, loc='best')
    plt.tight_layout()

    return fig

@app.callback(
    Output("observability_plot", "src"),
    [
        Input("summary_tabs", "value"),
        Input("submit_observability", "n_clicks"),
        Input("object-data", "data"),
    ],
    [
        State("observatory", "value"),
        State("dateobs", "value"),
        State("moon_elevation", "checked"),
        State("moon_phase", "checked"),
        State("moon_illumination", "checked")
    ],
    prevent_initial_call=True,
    background=True,
    running=[
        (Output("submit_observability", "disabled"), True, False),
        (Output("submit_observability", "loading"), True, False),
    ],
)
def plot_observability(
    summary_tab,
    nclick,
    object_data,
    observatory,
    dateobs,
    moon_elevation,
    moon_phase,
    moon_illumination
):
    if summary_tab != "Observability":
        raise PreventUpdate

    pdf = pd.read_json(io.StringIO(object_data))
    ra0 = np.mean(pdf["i:ra"].to_numpy())
    dec0 = np.mean(pdf["i:dec"].to_numpy())
    target = SkyCoord(ra=ra0, dec=dec0, unit=(u.deg, u.deg))
    fig = plot_altitude(
        target,
        observatory,
        dateobs,
        UTC=0,
        ax=None,
        show_moon_elevation=moon_elevation
    )
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    # Embed the result in the html output.
    fig_data = base64.b64encode(buf.getbuffer()).decode("ascii")
    fig_bar_matplotlib = f'data:image/png;base64,{fig_data}'

    return fig_bar_matplotlib
"""

@app.callback(
    Output("observability_plot_test", "children"),
    [
        Input("summary_tabs", "value"),
        Input("submit_observability", "n_clicks"),
        Input("object-data", "data"),
    ],
    [
        State("observatory", "value"),
        State("dateobs", "value"),
        State("moon_elevation", "checked"),
        State("moon_phase", "checked"),
        State("moon_illumination", "checked")
    ],
    prevent_initial_call=True,
    background=True,
    running=[
        (Output("submit_observability", "disabled"), True, False),
        (Output("submit_observability", "loading"), True, False),
    ],
)
def plot_observability_test(
    summary_tab,
    nclick,
    object_data,
    observatory,
    dateobs,
    moon_elevation,
    moon_phase,
    moon_illumination
):
    if summary_tab != "Observability":
        raise PreventUpdate

    pdf = pd.read_json(io.StringIO(object_data))
    ra0 = np.mean(pdf["i:ra"].to_numpy())
    dec0 = np.mean(pdf["i:dec"].to_numpy())
    local_time = observability.observation_time(dateobs, delta_points=1/60)
    UTC_time = local_time - observability.observation_time_to_utc_offset(observatory) * u.hour
    UTC_axis = observability.from_time_to_axis(UTC_time)
    local_axis = observability.from_time_to_axis(local_time)
    mask_axis = [True if t[-2:] == "00" and int(t[:2]) % 2 == 0 else False for t in UTC_axis]
    idx_axis = np.where(mask_axis)[0]
    target_coordinates = observability.target_coordinates(ra0, dec0, observatory, UTC_time)
    airmass = observability.from_elevation_to_airmass(target_coordinates.alt.value)
    twilights = observability.utc_night_hours(
        observatory, 
        dateobs,
        observability.observation_time_to_utc_offset(observatory),
        UTC=True
    )
    twilights_list = observability.from_time_to_axis(list(twilights.values()))

    # Initialize figure
    figure = {
        "data": [],
        "layout": copy.deepcopy(layout_observability)
    }
 
    # Add UTC time in the layout
    figure["layout"]["xaxis"] = {
        "title": "UTC time",
        "automargin": True,
        "tickvals": UTC_axis[idx_axis],
        "showgrid": True
    }

    # Target plot
    hovertemplate_elevation = r"""
    <b>UTC time</b>:%{x}<br>
    <b>Elevation</b>: %{y:.0f} &deg;<br>
    <b>Azimut</b>: %{customdata[0]:.0f} &deg;<br>
    <b>Relative airmass</b>: %{customdata[1]:.2f}
    <extra></extra>
    """

    figure["data"].append(
            {
                "x": UTC_axis,
                "y": target_coordinates.alt.value,
                "mode": "lines",
                "name": "Target elevation",
                "legendgroup": "Elevation",
                "customdata": np.stack(
                    [
                        target_coordinates.az.value,
                        airmass,
                    ],
                    axis=-1,
                ),
                "hovertemplate": hovertemplate_elevation,
                "line": {"color": "black"},
            }
        )

    # Moon target
    if moon_elevation:
        moon_coordinates = observability.moon_coordinates(observatory, UTC_time)
        moon_airmass = observability.from_elevation_to_airmass(moon_coordinates.alt.value)

        hovertemplate_moon = r"""
        <b>UTC time</b>:%{x}<br>
        <b>Elevation</b>: %{y:.0f} &deg;<br>
        <b>Azimut</b>: %{customdata[0]:.0f} &deg;<br>
        <b>Relative airmass</b>: %{customdata[1]:.2f}
        <extra></extra>
        """

        figure["data"].append(
            {
                "x": UTC_axis,
                "y": moon_coordinates.alt.value,
                "mode": "lines",
                "name": "Moon elevation",
                "legendgroup": "Elevation",
                "customdata": np.stack(
                    [
                        moon_coordinates.az.value,
                        moon_airmass,
                    ],
                    axis=-1,
                ),
                "hovertemplate": hovertemplate_moon,
                "line": {"color": observability.moon_color},
            }
        )

    # For relative airmass
    figure["data"].append(
        {
            "x": ["00:00", "00:00", "00:00"],
            "y": list(90 - np.degrees(np.arccos(1/np.array([1, 2, 3])))),
            "yaxis": "y2",
            "mode": "markers",
            "marker": {"opacity":0},
            "showlegend": False,
            "hoverinfo": "skip"
        }
    )

    # Layout modification for local time
    figure["layout"]["xaxis2"] = {
        "title": "Local time",
        "overlaying": "x",
        "side": "top",
        "tickvals": UTC_axis[idx_axis],
        "ticktext": local_axis[idx_axis],
        "showgrid": False,
        "showticklabels": True,
        "matches": "x",
        "anchor": "y"
    }

    # For local time
    figure["data"].append(
        {
            "x": local_axis,
            "y": 45 * np.ones(len(local_axis)),
            "xaxis": "x2",
            "mode": "markers",
            "marker": {"opacity":0},
            "showlegend": False,
            "hoverinfo": "skip"
        }
    )

    # Twilights
    figure["layout"]["shapes"] = []
    for dummy in range(len(twilights_list)-1):
        figure["layout"]["shapes"].append(
            {
                "type":"rect",
                "xref":"x",
                "yref":"paper",
                "x0":twilights_list[dummy],
                "x1":twilights_list[dummy+1],
                "y0":0,
                "y1":1,
                "fillcolor":observability.night_colors[dummy],
                "layer":"below",
                "line_width":0,
                "line":dict(width=0)
            }
        )

    # Graphs
    graph = dcc.Graph(
        figure=figure,
        style={
            "width": "90%",
            "height": "25pc",
            "marginLeft": "auto",
            "marginRight": "auto"
        },
        config={"displayModeBar": False},
        responsive=True,
    )

    return graph


@app.callback(
    Output("moon_data", "children"),
    [
        Input("summary_tabs", "value"),
        Input("submit_observability", "n_clicks"),
        Input("object-data", "data"),
    ],
    [
        State("dateobs", "value"),
        State("moon_phase", "checked"),
        State("moon_illumination", "checked")
    ],
    prevent_initial_call=True,
    background=True,
    running=[
        (Output("submit_observability", "disabled"), True, False),
        (Output("submit_observability", "loading"), True, False),
    ],
)
def show_moon_data(
    summary_tab,
    nclick,
    object_data,
    dateobs,
    moon_phase,
    moon_illumination
):
    if summary_tab != "Observability":
        raise PreventUpdate

    date_time = Time(dateobs, scale="utc")
    msg = None
    if moon_phase and not moon_illumination:
        msg = f"Moon phase: {observability.get_moon_phase(date_time)}"
    elif not moon_phase and moon_illumination:
        msg = f"Moon illumination: {int(100 * observability.get_moon_illumination(date_time))}%"
    elif moon_phase and moon_illumination:
        msg = f"moon phase: `{observability.get_moon_phase(date_time)}`, moon illumination: `{int(100 * observability.get_moon_illumination(date_time))}%`"
    return msg


@app.callback(
    Output("observability_title", "children"),
    [
        Input("summary_tabs", "value"),
        Input("submit_observability", "n_clicks"),
        Input("object-data", "data"),
    ],
    [
        State("dateobs", "value"),
    ],
    prevent_initial_call=True,
    background=True,
    running=[
        (Output("submit_observability", "disabled"), True, False),
        (Output("submit_observability", "loading"), True, False),
    ],
)
def show_observability_title(
    summary_tab,
    nclick,
    object_data,
    dateobs,
):
    if summary_tab != "Observability":
        raise PreventUpdate

    msg = "Observability for the night between "
    msg += (Time(dateobs) - 1 * u.day).to_value("iso", subfmt="date")
    msg += " and "
    msg += Time(dateobs).to_value("iso", subfmt="date")
    return msg


@app.callback(
    Output("blazar_plot", "children"),
    [
        Input("summary_tabs", "value"),
        Input("submit_blazar", "n_clicks"),
        Input("object-release", "data"),
    ],
    [
        State("quantile_blazar", "value"),
        State("object-data", "data"),
        State("object-release", "data"),
    ],
    prevent_initial_call=True,
    background=True,
    running=[
        (Output("submit_blazar", "disabled"), True, False),
        (Output("submit_blazar", "loading"), True, False),
    ],
)
def plot_blazar(
    summary_tab,
    nclick,
    object_release_in,
    quantile_blazar,
    object_data,
    object_release,
):
    if summary_tab != "Blazars":
        raise PreventUpdate

    """TBD"""
    # Prepare the data
    pdf_ = pd.read_json(io.StringIO(object_data))
    cols = [
        "i:jd",
        "i:magpsf",
        "i:sigmapsf",
        "i:fid",
        "i:distnr",
        "i:magnr",
        "i:sigmagnr",
        "i:magzpsci",
        "i:isdiffpos",
        "i:objectId",
    ]
    pdf = pdf_.loc[:, cols]
    pdf = pdf.sort_values("i:jd", ascending=False)

    # Data release?..
    if object_release_in or object_release:
        pdf_release = pd.read_json(io.StringIO(object_release))
        pdf_release = pdf_release[pdf_release["filtercode"].isin(["zr", "zg"])].copy()
        pdf_release = pdf_release.sort_values("mjd", ascending=False)
        dates_release = convert_jd(pdf_release["mjd"], format="mjd")
        pdf_release["flux_dc"], pdf_release["sigma_flux_dc"] = apparent_flux_dr(
            pdf_release["mag"], pdf_release["magerr"]
        )
        # pdf_release["flux_dc"] *= 1000
        # pdf_release["sigma_flux_dc"] *= 1000
    else:
        pdf_release = pd.DataFrame(
            {
                "mag": [],
                "magerr": [],
                "filtercode": [],
                "mjd": [],
                "flux_dc": [],
                "sigma_flux_dc": [],
                "std_flux_dc": [],
                "std_sigma_flux_dc": [],
            }
        )
        dates_release = np.array([])

    pdf["mag"], pdf["magerr"] = np.transpose(
        [
            dc_mag(*args)
            for args in zip(
                pdf["i:magpsf"].astype(float).to_numpy(),
                pdf["i:sigmapsf"].astype(float).to_numpy(),
                pdf["i:magnr"].astype(float).to_numpy(),
                pdf["i:sigmagnr"].astype(float).to_numpy(),
                pdf["i:isdiffpos"].to_numpy(),
            )
        ],
    )
    pdf["flux_dc"], pdf["sigma_flux_dc"] = np.transpose(
        [
            apparent_flux(*args)
            for args in zip(
                pdf["i:magpsf"].astype(float).to_numpy(),
                pdf["i:sigmapsf"].astype(float).to_numpy(),
                pdf["i:magnr"].astype(float).to_numpy(),
                pdf["i:sigmagnr"].astype(float).to_numpy(),
                pdf["i:isdiffpos"].to_numpy(),
            )
        ],
    )

    jd = pdf["i:jd"].astype(float)
    dates = convert_jd(jd)

    # Normalise flux
    # Median is computed on historical data
    # hence the quantile 50 is probably not aligning with 1
    # with new alert data coming in.
    # TODO: compute median on-the-fly

    # Avoid covering of alerts and DR
    maskTime = np.ones(len(pdf), dtype=bool)
    if len(dates_release) > 0:
        maskTime = pdf["i:jd"].to_numpy() - 2400000.5 > pdf_release["mjd"].iloc[0]

    # Merge bands from alerts and DR
    flux = np.concatenate(
        (pdf["flux_dc"].to_numpy()[maskTime], pdf_release["flux_dc"].to_numpy())
    )[::-1]
    filts_release = np.ones(len(pdf_release))
    filts_release[pdf_release["filtercode"].to_numpy() == "zr"] = 2
    filts = np.concatenate((pdf["i:fid"].to_numpy()[maskTime], filts_release))[::-1]
    mjds = np.concatenate(
        (pdf["i:jd"].to_numpy()[maskTime] - 2400000.5, pdf_release["mjd"].to_numpy())
    )[::-1]

    # Compute meaningful median
    delta_max_time = 0.5
    possible_filts = np.unique(filts)
    medians = dict.fromkeys(possible_filts)
    if len(possible_filts) == 1:
        medians[possible_filts[0]] = np.median(flux)
    else:
        other_filt = {1: 2, 2: 1}
        concomitant_measurements = {filt: [] for filt in possible_filts}
        start = -np.inf
        for index_flux in range(len(flux)):
            if mjds[index_flux] > start + delta_max_time:
                start = mjds[index_flux]
                maskTime = (mjds >= start) & (mjds <= start + delta_max_time)
                filt = filts[index_flux]
                maskFilt = filts == filt
                if np.any(maskTime & (~maskFilt)):
                    concomitant_measurements[filt].append(
                        np.mean(flux[maskTime & maskFilt])
                    )
                    concomitant_measurements[other_filt[filt]].append(
                        np.mean(flux[maskTime & (~maskFilt)])
                    )
        for filt in possible_filts:
            medians[filt] = np.median(concomitant_measurements[filt])

    conv_dict = {"zg": 1, "zr": 2}
    for filt in pdf["i:fid"].unique():
        maskFilt = pdf["i:fid"] == filt
        pdf.loc[maskFilt, "std_flux_dc"] = pdf.loc[maskFilt, "flux_dc"] / medians[filt]
        pdf.loc[maskFilt, "std_sigma_flux_dc"] = (
            pdf.loc[maskFilt, "sigma_flux_dc"] / medians[filt]
        )

    for filt in pdf_release["filtercode"].unique():
        maskFilt = pdf_release["filtercode"] == filt
        pdf_release.loc[maskFilt, "std_flux_dc"] = (
            pdf_release.loc[maskFilt, "flux_dc"] / medians[conv_dict[filt]]
        )
        pdf_release.loc[maskFilt, "std_sigma_flux_dc"] = (
            pdf_release.loc[maskFilt, "sigma_flux_dc"] / medians[conv_dict[filt]]
        )

    # Divive by the median of the whole LC to equal it to 1
    tot_median = np.median(
        np.concatenate(
            (pdf["std_flux_dc"].to_numpy(), pdf_release["std_flux_dc"].to_numpy())
        )
    )
    pdf["std_flux_dc"] /= tot_median
    pdf["std_sigma_flux_dc"] /= tot_median
    pdf_release["std_flux_dc"] /= tot_median
    pdf_release["std_sigma_flux_dc"] /= tot_median

    # Quantiles
    low_quantile = np.percentile(
        np.concatenate(
            (pdf["std_flux_dc"].to_numpy(), pdf_release["std_flux_dc"].to_numpy())
        ),
        quantile_blazar,
    )
    high_quantile = np.percentile(
        np.concatenate(
            (pdf["std_flux_dc"].to_numpy(), pdf_release["std_flux_dc"].to_numpy())
        ),
        100 - quantile_blazar,
    )

    # Initialize figures
    figure = {
        "data": [],
        "layout": copy.deepcopy(layout_blazar),
    }

    hovertemplate = r"""
    <b>%{yaxis.title.text}</b>:%{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x}<br>
    <b>Apparent magnitude</b>: %{customdata[0]:.2f} &plusmn; %{customdata[1]:.2f}<br>
    <b>Brightness level &#981;/&#981;<sub>%{customdata[2]}</sub></b>: %{customdata[3]:.2f}
    <extra></extra>
    """

    # Light curve display
    for fid, fname, color in (
        (1, "g", COLORS_ZTF[0]),
        (2, "r", COLORS_ZTF[1]),
    ):
        if fid in np.unique(pdf["i:fid"].to_numpy()):
            # Original data
            idx = pdf["i:fid"] == fid
            figure["data"].append(
                {
                    "x": dates[idx],
                    "y": pdf["std_flux_dc"].to_numpy()[idx],
                    "error_y": {
                        "type": "data",
                        "array": pdf["std_sigma_flux_dc"][idx],
                        "visible": True,
                        "width": 0,
                        "opacity": 0.5,
                        "color": color,
                    },
                    "mode": "markers",
                    "name": f"{fname} band",
                    "legendgroup": f"{fname} band",
                    "customdata": np.stack(
                        [
                            pdf["mag"].to_numpy()[idx],
                            pdf["magerr"].to_numpy()[idx],
                            quantile_blazar * np.ones(len(pdf))[idx],
                            pdf["std_flux_dc"].to_numpy()[idx] / low_quantile,
                        ],
                        axis=-1,
                    ),
                    "hovertemplate": hovertemplate,
                    "marker": {"size": 10, "color": color, "symbol": "o"},
                }
            )

    for fid, fname, color in (
        ("zg", "g (DR)", COLORS_ZTF[0]),
        ("zr", "r (DR)", COLORS_ZTF[1]),
    ):
        if fid in np.unique(pdf_release["filtercode"].to_numpy()):
            # Original data
            idx = pdf_release["filtercode"] == fid
            figure["data"].append(
                {
                    "x": dates_release[idx],
                    "y": pdf_release["std_flux_dc"].to_numpy()[idx],
                    "error_y": {
                        "type": "data",
                        "array": pdf_release["std_sigma_flux_dc"][idx],
                        "visible": True,
                        "width": 0,
                        "opacity": 0.3,
                        "color": color,
                    },
                    "mode": "markers",
                    "name": f"{fname} band",
                    "legendgroup": f"{fname} band",
                    "customdata": np.stack(
                        [
                            pdf_release["mag"].to_numpy()[idx],
                            pdf_release["magerr"].to_numpy()[idx],
                            quantile_blazar * np.ones(len(pdf_release[idx])),
                            pdf_release["std_flux_dc"].to_numpy()[idx] / low_quantile,
                        ],
                        axis=-1,
                    ),
                    "hovertemplate": hovertemplate,
                    "marker": {
                        "size": 7,
                        "color": color,
                        "symbol": "o",
                        "opacity": 0.3,
                    },
                }
            )

    # Quantile display
    if object_release:
        start = dates_release[-1]
    else:
        start = dates[-1]
    figure["layout"]["shapes"] = [
        {
            "type": "line",
            "xref": "x",
            "x0": start,
            "x1": dates[0],
            "yref": "y",
            "y0": low_quantile,
            "y1": low_quantile,
            "line": {"color": "black", "dash": "dash", "width": 1},
        },
        {
            "type": "line",
            "xref": "x",
            "x0": start,
            "x1": dates[0],
            "yref": "y",
            "y0": high_quantile,
            "y1": high_quantile,
            "line": {"color": "black", "dash": "dash", "width": 1},
        },
    ]

    # Graphs
    graph = dcc.Graph(
        figure=figure,
        style={
            "width": "100%",
            "height": "25pc",
        },
        config={"displayModeBar": False},
        responsive=True,
    )

    return graph


@app.callback(
    [
        Output("variable_plot", "children"),
        Output("card_explanation_variable", "value"),
    ],
    Input("submit_variable", "n_clicks"),
    [
        State("nterms_base", "value"),
        State("nterms_band", "value"),
        State("manual_period", "value"),
        State("period_min", "value"),
        State("period_max", "value"),
        State("object-data", "data"),
        State("object-release", "data"),
    ],
    prevent_initial_call=True,
    background=True,
    running=[
        (Output("submit_variable", "disabled"), True, False),
        (Output("submit_variable", "loading"), True, False),
    ],
)
def plot_variable_star(
    n_clicks,
    nterms_base,
    nterms_band,
    manual_period,
    period_min,
    period_max,
    object_data,
    object_release,
):
    """Fit for the period of a star using gatspy

    See https://zenodo.org/record/47887
    See https://ui.adsabs.harvard.edu/abs/2015ApJ...812...18V/abstract
    """
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if triggered_id != "submit_variable":
        raise PreventUpdate

    # Safety checks - opens the help panel if they fails
    if type(nterms_base) not in [int]:
        return None, "info"
    if type(nterms_band) not in [int]:
        return None, "info"
    if manual_period is not None and type(manual_period) not in [int, float]:
        return None, "info"
    if period_min is not None and type(period_min) not in [int, float]:
        return None, "info"
    if period_max is not None and type(period_max) not in [int, float]:
        return None, "info"

    # Prepare the data
    pdf_ = pd.read_json(io.StringIO(object_data))
    cols = [
        "i:jd",
        "i:magpsf",
        "i:sigmapsf",
        "i:fid",
        "i:distnr",
        "i:magnr",
        "i:sigmagnr",
        "i:magzpsci",
        "i:isdiffpos",
        "i:objectId",
    ]
    pdf = pdf_.loc[:, cols]
    pdf = pdf.sort_values("i:jd", ascending=False)

    # Data release?..
    if object_release:
        pdf_release = pd.read_json(io.StringIO(object_release))
        pdf_release = pdf_release.sort_values("mjd", ascending=False)
        dates_release = convert_jd(pdf_release["mjd"], format="mjd")
    else:
        pdf_release = pd.DataFrame()

    # Should we correct DC magnitudes for the nearby source?..
    is_dc_corrected = is_source_behind(pdf["i:distnr"].to_numpy()[0])

    if is_dc_corrected:
        mag, err = np.transpose(
            [
                dc_mag(*args)
                for args in zip(
                    pdf["i:magpsf"].astype(float).to_numpy(),
                    pdf["i:sigmapsf"].astype(float).to_numpy(),
                    pdf["i:magnr"].astype(float).to_numpy(),
                    pdf["i:sigmagnr"].astype(float).to_numpy(),
                    pdf["i:isdiffpos"].to_numpy(),
                )
            ],
        )
        # Keep only "good" measurements
        idx = err < 1
        pdf, mag, err = (_[idx] for _ in [pdf, mag, err])
    else:
        mag, err = pdf["i:magpsf"], pdf["i:sigmapsf"]

    jd = pdf["i:jd"].astype(float)
    dates = convert_jd(jd)

    fit_period = False if manual_period is not None else True
    model = periodic.LombScargleMultiband(
        Nterms_base=int(nterms_base),
        Nterms_band=int(nterms_band),
        fit_period=fit_period,
    )

    # Not sure about that...
    model.optimizer.period_range = (period_min, period_max)
    model.optimizer.quiet = True

    model.fit(
        jd,
        mag,
        err,
        pdf["i:fid"],
    )

    if fit_period:
        period = model.best_period
    else:
        period = manual_period

    phase = jd % period
    tfit = np.linspace(0, period, 100)
    tfit_unfolded = np.linspace(
        np.min(jd),
        np.max(jd),
        # Between 100 and 10000 points, to hopefully have 10 per period
        min(10000, max(100, int(10 * (np.max(jd) - np.min(jd)) / period))),
    )
    dates_unfolded = convert_jd(tfit_unfolded)

    # Initialize figures
    figure, figure_unfolded, figure_periodogram = (
        {
            "data": [],
            "layout": copy.deepcopy(layout_phase),
        }
        for _ in range(3)
    )

    figure_unfolded["layout"]["xaxis"]["title"] = "Observation date"

    hovertemplate = r"""
    <b>%{yaxis.title.text}</b>:%{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x:.2f}
    <extra></extra>
    """

    hovertemplate_model = r"""
    <b>%{yaxis.title.text}</b>:%{y:.2f}<br>
    <extra></extra>
    """

    hovertemplate_unfolded = r"""
    <b>%{yaxis.title.text}</b>:%{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
    <extra></extra>
    """

    for fid, fname, color in (
        (1, "g", COLORS_ZTF[0]),
        (2, "r", COLORS_ZTF[1]),
    ):
        if fid in np.unique(pdf["i:fid"].to_numpy()):
            # Original data
            idx = pdf["i:fid"] == fid
            figure["data"].append(
                {
                    "x": phase[idx] / period,
                    "y": mag[idx],
                    "error_y": {
                        "type": "data",
                        "array": err[idx],
                        "visible": True,
                        "width": 0,
                        "opacity": 0.5,
                        "color": color,
                    },
                    "mode": "markers",
                    "name": f"{fname} band",
                    "legendgroup": f"{fname} band",
                    "hovertemplate": hovertemplate,
                    "marker": {"size": 10, "color": color, "symbol": "o"},
                }
            )

            # Release data
            if not pdf_release.empty:
                idxr = pdf_release["filtercode"] == "z" + fname
                figure["data"].append(
                    {
                        "x": ((pdf_release["mjd"][idxr] + 2400000.5) % period) / period,
                        "y": pdf_release["mag"][idxr],
                        "error_y": {
                            "type": "data",
                            "array": pdf_release["magerr"][idxr],
                            "visible": True,
                            "width": 0,
                            "opacity": 0.25,
                            "color": color,
                        },
                        "mode": "markers",
                        "name": "",
                        "hovertemplate": hovertemplate,
                        "legendgroup": f"{fname} band release",
                        "marker": {
                            "color": color,
                            "symbol": ".",
                        },
                        "opacity": 0.5,
                        # 'showlegend': False
                    },
                )

                figure_unfolded["data"].append(
                    {
                        "x": dates_release[idxr],
                        "y": pdf_release["mag"][idxr],
                        "error_y": {
                            "type": "data",
                            "array": pdf_release["magerr"][idxr],
                            "visible": True,
                            "width": 0,
                            "opacity": 0.25,
                            "color": color,
                        },
                        "mode": "markers",
                        "name": "",
                        "hovertemplate": hovertemplate,
                        "legendgroup": f"{fname} band release",
                        "marker": {
                            "color": color,
                            "symbol": ".",
                        },
                        "opacity": 0.5,
                        # 'showlegend': False
                    },
                )

            # Original data, unfolded
            figure_unfolded["data"].append(
                {
                    "x": dates[idx],
                    "y": mag[idx],
                    "error_y": {
                        "type": "data",
                        "array": err[idx],
                        "visible": True,
                        "width": 0,
                        "opacity": 0.5,
                        "color": color,
                    },
                    "mode": "markers",
                    "name": f"{fname} band",
                    "legendgroup": f"{fname} band",
                    "hovertemplate": hovertemplate_unfolded,
                    "marker": {"size": 10, "color": color, "symbol": "o"},
                }
            )

            # Model
            magfit = model.predict(tfit, period=period, filts=fid)
            figure["data"].append(
                {
                    "x": tfit / period,
                    "y": magfit,
                    "mode": "lines",
                    "name": f"fit {fname} band",
                    "legendgroup": f"{fname} band",
                    "hovertemplate": hovertemplate_model,
                    "showlegend": False,
                    "line": {
                        "color": color,
                        "opacity": 0.5,
                        "width": 2,
                    },
                }
            )

            # Model, unfolded
            magfit = model.predict(tfit_unfolded, period=period, filts=fid)
            figure_unfolded["data"].append(
                {
                    "x": dates_unfolded,
                    "y": magfit,
                    "mode": "lines",
                    "name": f"fit {fname} band",
                    "legendgroup": f"{fname} band",
                    "hovertemplate": hovertemplate_model,
                    "showlegend": False,
                    "line": {
                        "color": color,
                        "opacity": 0.5,
                        "width": 0.5,
                    },
                }
            )

    # Periodogram
    # periods,powers = model.periodogram_auto()
    periods = 1 / np.linspace(1 / period_max, 1 / period_min, 10000)
    powers = model.periodogram(periods)

    figure_periodogram["layout"]["xaxis"]["title"] = "Period, days"
    figure_periodogram["layout"]["xaxis"]["type"] = "log"
    figure_periodogram["layout"]["yaxis"]["title"] = "Periodogram"
    figure_periodogram["layout"]["yaxis"]["autorange"] = True

    figure_periodogram["data"] = [
        {
            "x": periods,
            "y": powers,
            "mode": "lines",
            "name": "Multiband LS periodogram",
            "legendgroup": "periodogram",
            "hovertemplate": "<b>Period</b>: %{x}<extra></extra>",
            "showlegend": False,
            "line": {
                "color": "#3C8DFF",
            },
        },
    ]

    figure_periodogram["layout"]["shapes"] = [
        {
            "type": "line",
            "xref": "x",
            "x0": period,
            "x1": period,
            "yref": "paper",
            "y0": 0,
            "y1": 1,
            "line": {"color": "#F5622E", "dash": "dash", "width": 1},
        },
    ]

    # Graphs
    graph, graph_unfolded, graph_periodogram = (
        dcc.Graph(
            figure=fig,
            style={
                "width": "100%",
                "height": "25pc",
            },
            config={"displayModeBar": False},
            responsive=True,
        )
        for fig in [figure, figure_unfolded, figure_periodogram]
    )

    # Layout
    results = dmc.Stack(
        [
            dmc.Tabs(
                [
                    dmc.TabsList(
                        [
                            dmc.TabsTab("Folded", value="folded"),
                            dmc.TabsTab("Unfolded", value="unfolded"),
                            dmc.TabsTab("Periodogram", value="periodogram"),
                        ],
                    ),
                    dmc.TabsPanel(
                        graph,
                        value="folded",
                    ),
                    dmc.TabsPanel(
                        graph_unfolded,
                        value="unfolded",
                    ),
                    dmc.TabsPanel(
                        graph_periodogram,
                        value="periodogram",
                    ),
                ],
                value="folded",
                style={"width": "100%"},
            ),
            dcc.Markdown(
                f"""
                Period = `{period}` days, score = `{model.score(period):.2f}`
                """,
            ),
        ],
        align="center",
    )

    return results, None


@app.callback(
    Output("classbar", "figure"),
    [
        Input("object-data", "data"),
    ],
    prevent_initial_call=True,
)
def plot_classbar(object_data):
    """Display a bar chart with individual alert classifications

    Parameters
    ----------
    object_data: json data
        cached alert data
    """
    pdf = pd.read_json(io.StringIO(object_data))
    grouped = pdf.groupby("v:classification").count()
    alert_per_class = grouped["i:objectId"].to_dict()

    # descending date values
    top_labels = pdf["v:classification"].to_numpy()[::-1]
    customdata = convert_jd(pdf["i:jd"])[::-1]
    x_data = [[1] * len(top_labels)]
    y_data = top_labels

    palette = dmc.DEFAULT_THEME["colors"]

    colors = [
        palette[class_colors["Simbad"]][6]
        if j not in class_colors.keys()
        else palette[class_colors[j]][6]
        for j in top_labels
    ]

    fig = go.Figure()

    is_seen = []
    for i in range(len(x_data[0])):
        for xd, yd in zip(x_data, y_data):
            if top_labels[i] in is_seen:
                showlegend = False
            else:
                showlegend = True
        is_seen.append(top_labels[i])

        percent = np.round(alert_per_class[top_labels[i]] / len(pdf) * 100).astype(
            int
        )
        name_legend = top_labels[i] + f": {percent}%"
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
            ),
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
    fig.update_layout(title_text="Individual alert classification")
    fig.update_layout(title_y=0.15)
    fig.update_layout(title_x=0.0)
    fig.update_layout(title_font_size=12)

    return fig


@app.callback(
    Output("lightcurve_cutouts", "figure"),
    [
        Input("switch-mag-flux", "value"),
        Input("object-data", "data"),
        Input("object-upper", "data"),
        Input("object-uppervalid", "data"),
        Input("object-release", "data"),
        Input("lightcurve_show_color", "checked"),
    ],
    prevent_initial_call=True,
)
def draw_lightcurve(
    switch: int,
    object_data,
    object_upper,
    object_uppervalid,
    object_release,
    show_color,
) -> dict:
    """Draw object lightcurve with errorbars

    Parameters
    ----------
    switch: int
        Choose:
          - 0 to display difference magnitude
          - 1 to display dc magnitude
          - 2 to display flux

    Returns
    -------
    figure: dict
    """
    # Primary high-quality data points
    pdf_ = pd.read_json(io.StringIO(object_data))
    cols = [
        "i:jd",
        "i:magpsf",
        "i:sigmapsf",
        "i:fid",
        "i:distnr",
        "i:magnr",
        "i:sigmagnr",
        "i:magzpsci",
        "i:isdiffpos",
        "i:candid",
    ]
    pdf = pdf_.loc[:, cols]

    # Upper limits
    pdf_upper = pd.read_json(io.StringIO(object_upper))

    # Lower-quality data points
    pdf_upperv = pd.read_json(io.StringIO(object_uppervalid))

    # type conversion
    dates = convert_jd(pdf["i:jd"])
    dates_upper = convert_jd(pdf_upper["i:jd"])
    dates_upperv = convert_jd(pdf_upperv["i:jd"])

    if object_release:
        # Data release photometry
        pdf_release = pd.read_json(io.StringIO(object_release))
        dates_release = convert_jd(pdf_release["mjd"], format="mjd")
    else:
        pdf_release = pd.DataFrame()

    # Exclude lower-quality points overlapping higher-quality ones
    mask = np.in1d(pdf_upperv["i:jd"].to_numpy(), pdf["i:jd"].to_numpy())
    pdf_upperv, dates_upperv = (_[~mask] for _ in (pdf_upperv, dates_upperv))

    # shortcuts
    mag = pdf["i:magpsf"]
    err = pdf["i:sigmapsf"]

    # Should we correct DC magnitudes for the nearby source?..
    is_dc_corrected = is_source_behind(pdf["i:distnr"].to_numpy()[0])

    # We should never modify global variables!!!
    layout = deepcopy(layout_lightcurve)

    if switch == "Difference magnitude":
        layout["yaxis"]["title"] = "Difference magnitude"
        layout["yaxis"]["autorange"] = "reversed"
        scale = 1.0
    elif switch == "DC magnitude":
        if is_dc_corrected:
            # inplace replacement for DC corrected flux
            mag, err = np.transpose(
                [
                    dc_mag(*args)
                    for args in zip(
                        mag.astype(float).to_numpy(),
                        err.astype(float).to_numpy(),
                        pdf["i:magnr"].astype(float).to_numpy(),
                        pdf["i:sigmagnr"].astype(float).to_numpy(),
                        pdf["i:isdiffpos"].to_numpy(),
                    )
                ],
            )
            # Keep only "good" measurements
            idx = err < 1
            pdf, dates, mag, err = (_[idx] for _ in [pdf, dates, mag, err])

        layout["yaxis"]["title"] = "Apparent DC magnitude"
        layout["yaxis"]["autorange"] = "reversed"
        scale = 1.0
    elif switch == "DC flux":
        # inplace replacement
        mag, err = np.transpose(
            [
                apparent_flux(*args)
                for args in zip(
                    mag.astype(float).to_numpy(),
                    err.astype(float).to_numpy(),
                    pdf["i:magnr"].astype(float).to_numpy()
                    if is_dc_corrected
                    else [99.0] * len(pdf.index),
                    pdf["i:sigmagnr"].astype(float).to_numpy(),
                    pdf["i:isdiffpos"].to_numpy(),
                )
            ],
        )

        layout["yaxis"]["title"] = "Apparent DC flux (milliJansky)"
        layout["yaxis"]["autorange"] = True
        scale = 1e3

    layout["shapes"] = []

    figure = {
        "data": [],
        "layout": layout,
    }

    for fid, fname, color, color_negative in (
        (1, "g", COLORS_ZTF[0], COLORS_ZTF_NEGATIVE[0]),
        (2, "r", COLORS_ZTF[1], COLORS_ZTF_NEGATIVE[1]),
    ):
        # High-quality measurements
        hovertemplate = r"""
        <b>%{yaxis.title.text}</b>: %{customdata[1]}%{y:.2f} &plusmn; %{error_y.array:.2f}<br>
        <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
        <b>mjd</b>: %{customdata[0]}
        <extra></extra>
        """
        idx = pdf["i:fid"] == fid
        figure["data"].append(
            {
                "x": dates[idx],
                "y": mag[idx] * scale,
                "error_y": {
                    "type": "data",
                    "array": err[idx] * scale,
                    "visible": True,
                    "width": 0,
                    "opacity": 0.5,
                    "color": color,
                },
                "mode": "markers",
                "name": f"{fname} band",
                "customdata": np.stack(
                    (
                        pdf["i:jd"][idx] - 2400000.5,
                        pdf["i:isdiffpos"][idx].apply(
                            lambda x: "(-) " if x == "f" else ""
                        ),
                    ),
                    axis=-1,
                ),
                "hovertemplate": hovertemplate,
                "legendgroup": f"{fname} band",
                "legendrank": 100 + 10 * fid,
                "marker": {
                    "size": 12,
                    "color": pdf["i:isdiffpos"][idx].apply(
                        lambda x,
                        color_negative=color_negative,
                        color=color: color_negative if x == "f" else color
                    ),
                    "symbol": "o",
                },
            },
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
                idx = pdf_upper["i:fid"] == fid
                figure["data"].append(
                    {
                        "x": dates_upper[idx],
                        "y": pdf_upper["i:diffmaglim"][idx],
                        "mode": "markers",
                        "name": "",
                        "customdata": pdf_upper["i:jd"][idx] - 2400000.5,
                        "hovertemplate": hovertemplate_upper,
                        "legendgroup": f"{fname} band upper",
                        "legendrank": 101 + 10 * fid,
                        "marker": {
                            "color": color,
                            "symbol": "triangle-down-open",
                            "opacity": 0.5,
                        },
                        # 'showlegend': False
                    },
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
                idx = pdf_upperv["i:fid"] == fid
                figure["data"].append(
                    {
                        "x": dates_upperv[idx],
                        "y": pdf_upperv["i:magpsf"][idx],
                        "error_y": {
                            "type": "data",
                            "array": pdf_upperv["i:sigmapsf"][idx],
                            "visible": True,
                            "width": 0,
                            "opacity": 0.5,
                            "color": color,
                        },
                        "mode": "markers",
                        "customdata": pdf_upperv["i:jd"][idx] - 2400000.5,
                        "hovertemplate": hovertemplate_upperv,
                        "legendgroup": f"{fname} band",
                        "marker": {
                            "color": color,
                            "symbol": "triangle-up",
                        },
                        "showlegend": False,
                    },
                )

        elif switch == "DC magnitude":
            if is_dc_corrected:
                # Overplot the levels of nearby source magnitudes
                idx = pdf["i:fid"] == fid
                if np.sum(idx):
                    ref = np.mean(pdf["i:magnr"][idx])

                    figure["layout"]["shapes"].append(
                        {
                            "type": "line",
                            "yref": "y",
                            "y0": ref,
                            "y1": ref,  # adding a horizontal line
                            "xref": "paper",
                            "x0": 0,
                            "x1": 1,
                            "line": {"color": color, "dash": "dash", "width": 1},
                            "legendgroup": f"{fname} band",
                            "opacity": 0.3,
                        },
                    )

            # Data release photometry
            if not pdf_release.empty:
                hovertemplate_release = r"""
                <b>Data release magnitude</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
                <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
                <b>mjd</b>: %{customdata}
                <extra></extra>
                """
                idx = pdf_release["filtercode"] == "z" + fname
                figure["data"].append(
                    {
                        "x": dates_release[idx],
                        "y": pdf_release["mag"][idx],
                        "error_y": {
                            "type": "data",
                            "array": pdf_release["magerr"][idx],
                            "visible": True,
                            "width": 0,
                            "opacity": 0.5,
                            "color": color,
                        },
                        "mode": "markers",
                        "name": "",
                        "customdata": pdf_release["mjd"][idx],
                        "hovertemplate": hovertemplate_release,
                        "legendgroup": f"{fname} band release",
                        "legendrank": 102 + 10 * fid,
                        "marker": {
                            "color": color,
                            "symbol": ".",
                        },
                        "opacity": 0.5,
                        # 'showlegend': False
                    },
                )

    if show_color:
        hovertemplate_gr = r"""
        <b>g - r</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
        <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
        <b>mjd</b>: %{customdata}
        <extra></extra>
        """

        pdf_ = None

        if switch == "Difference magnitude":
            pdf_ = pd.concat([pdf, pdf_upperv])
        elif switch == "DC magnitude":
            pdf_ = pd.DataFrame(
                {
                    "i:jd": pdf["i:jd"],
                    "i:fid": pdf["i:fid"],
                    "i:magpsf": mag,
                    "i:sigmapsf": err,
                },
            )

            if not pdf_release.empty:
                pdf_ = pd.concat(
                    [
                        pdf_,
                        pd.DataFrame(
                            {
                                "i:jd": pdf_release["mjd"] + 2400000.5,
                                "i:fid": pdf_release["filtercode"].map(
                                    {"zg": 1, "zr": 2}
                                ),
                                "i:magpsf": pdf_release["mag"],
                                "i:sigmapsf": pdf_release["magerr"],
                            },
                        ),
                    ],
                )

        if pdf_ is not None:
            pdf_gr = extract_color(pdf_)
            dates_gr = convert_jd(pdf_gr["i:jd"])
            color = "#3C8DFF"

            figure["data"].append(
                {
                    "x": dates_gr,
                    "y": pdf_gr["v:g-r"],
                    "error_y": {
                        "type": "data",
                        "array": pdf_gr["v:sigma_g-r"],
                        "visible": True,
                        "width": 0,
                        "opacity": 0.5,
                        "color": color,
                    },
                    "mode": "markers",
                    "name": "g - r",
                    "customdata": pdf_gr["i:jd"] - 2400000.5,
                    "hovertemplate": hovertemplate_gr,
                    "legendgroup": "g-r",
                    "marker": {
                        "color": color,
                        "symbol": "o",
                    },
                    "showlegend": True,
                    "xaxis": "x",
                    "yaxis": "y2",
                },
            )

            figure["layout"]["yaxis2"] = {
                "automargin": True,
                "title": "g-r",
                "domain": [0.0, 0.3],
                "zeroline": True,
                "zerolinecolor": "#c0c0c0",
            }
            figure["layout"]["yaxis"]["domain"] = [0.35, 1.0]
            figure["layout"]["xaxis"]["anchor"] = "free"

            figure["layout"]["shapes"].append(
                {
                    "type": "line",
                    "yref": "paper",
                    "y0": 0.325,
                    "y1": 0.325,
                    "xref": "paper",
                    "x0": -0.1,
                    "x1": 1.05,
                    "line": {"color": "gray", "width": 4},
                    "opacity": 0.1,
                },
            )

    return figure


@app.callback(
    Output("lightcurve_scores", "figure"),
    [
        Input("object-data", "data"),
        Input("object-upper", "data"),
        Input("object-uppervalid", "data"),
    ],
    prevent_initial_call=True,
)
def draw_lightcurve_sn(object_data, object_upper, object_uppervalid) -> dict:
    """Draw object lightcurve with errorbars (SM view - DC mag fixed)

    Returns
    -------
    figure: dict
    """
    pdf_ = pd.read_json(io.StringIO(object_data))
    cols = [
        "i:jd",
        "i:magpsf",
        "i:sigmapsf",
        "i:fid",
        "i:magnr",
        "i:sigmagnr",
        "i:magzpsci",
        "i:isdiffpos",
        "i:candid",
    ]
    pdf = pdf_.loc[:, cols]

    # type conversion
    dates = convert_jd(pdf["i:jd"])

    # shortcuts
    mag = pdf["i:magpsf"]
    err = pdf["i:sigmapsf"]
    layout_lightcurve["yaxis"]["title"] = "Difference magnitude"
    layout_lightcurve["yaxis"]["autorange"] = "reversed"

    hovertemplate = r"""
    <b>%{yaxis.title.text}</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
    <b>mjd</b>: %{customdata}
    <extra></extra>
    """
    figure = {
        "data": [
            {
                "x": dates[pdf["i:fid"] == 1],
                "y": mag[pdf["i:fid"] == 1],
                "error_y": {
                    "type": "data",
                    "array": err[pdf["i:fid"] == 1],
                    "visible": True,
                    "width": 0,
                    "opacity": 0.5,
                    "color": COLORS_ZTF[0],
                },
                "mode": "markers",
                "name": "g band",
                "customdata": pdf["i:jd"][pdf["i:fid"] == 1] - 2400000.5,
                "hovertemplate": hovertemplate,
                "marker": {"size": 12, "color": COLORS_ZTF[0], "symbol": "o"},
            },
            {
                "x": dates[pdf["i:fid"] == 2],
                "y": mag[pdf["i:fid"] == 2],
                "error_y": {
                    "type": "data",
                    "array": err[pdf["i:fid"] == 2],
                    "visible": True,
                    "width": 0,
                    "opacity": 0.5,
                    "color": COLORS_ZTF[1],
                },
                "mode": "markers",
                "name": "r band",
                "customdata": pdf["i:jd"][pdf["i:fid"] == 2] - 2400000.5,
                "hovertemplate": hovertemplate,
                "marker": {"size": 12, "color": COLORS_ZTF[1], "symbol": "o"},
            },
        ],
        "layout": layout_lightcurve,
    }
    return figure


def draw_lightcurve_preview(name) -> dict:
    """Draw object lightcurve with errorbars (SM view - DC mag fixed)

    Returns
    -------
    figure: dict
    """
    cols = [
        "i:jd",
        "i:magpsf",
        "i:sigmapsf",
        "i:fid",
        "i:isdiffpos",
        "i:distnr",
        "i:magnr",
        "i:sigmagnr",
        "d:tag",
    ]
    pdf = request_api(
        "/api/v1/objects",
        json={
            "objectId": name,
            "withupperlim": "True",
            "columns": ",".join(cols),
            "output-format": "json",
        },
    )

    # Mask upper-limits (but keep measurements with bad quality)
    mag_ = pdf["i:magpsf"]
    mask = ~np.isnan(mag_)
    pdf = pdf[mask]

    # type conversion
    dates = convert_jd(pdf["i:jd"])

    # shortcuts
    mag = pdf["i:magpsf"]
    err = pdf["i:sigmapsf"]

    # Should we correct DC magnitudes for the nearby source?..
    is_dc_corrected = is_source_behind(pdf["i:distnr"].to_numpy()[0])

    # We should never modify global variables!!!
    layout = deepcopy(layout_lightcurve_preview)

    layout["yaxis"]["title"] = "Difference magnitude"
    layout["yaxis"]["autorange"] = "reversed"
    layout["paper_bgcolor"] = "rgba(0,0,0,0.0)"
    layout["plot_bgcolor"] = "rgba(0,0,0,0.2)"
    layout["showlegend"] = False
    layout["shapes"] = []

    if is_dc_corrected:
        # inplace replacement for DC corrected flux
        mag, err = np.transpose(
            [
                dc_mag(*args)
                for args in zip(
                    mag.astype(float).to_numpy(),
                    err.astype(float).to_numpy(),
                    pdf["i:magnr"].astype(float).to_numpy(),
                    pdf["i:sigmagnr"].astype(float).to_numpy(),
                    pdf["i:isdiffpos"].to_numpy(),
                )
            ],
        )
        # Keep only "good" measurements
        idx = err < 1
        pdf, dates, mag, err = (_[idx] for _ in [pdf, dates, mag, err])

        layout["yaxis"]["title"] = "Apparent DC magnitude"

    hovertemplate = r"""
    <b>%{yaxis.title.text}%{customdata[2]}</b>: %{customdata[1]}%{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
    <b>mjd</b>: %{customdata[0]}
    <extra></extra>
    """
    figure = {
        "data": [],
        "layout": layout,
    }

    for fid, fname, color, color_negative in (
        (1, "g", COLORS_ZTF[0], COLORS_ZTF_NEGATIVE[0]),
        (2, "r", COLORS_ZTF[1], COLORS_ZTF_NEGATIVE[1]),
    ):
        idx = pdf["i:fid"] == fid

        if not np.sum(idx):
            continue

        figure["data"].append(
            {
                "x": dates[idx],
                "y": mag[idx],
                "error_y": {
                    "type": "data",
                    "array": err[idx],
                    "visible": True,
                    "width": 0,
                    "color": color,  # It does not support arrays of colors so let's use positive one for all points
                    "opacity": 0.5,
                },
                "mode": "markers",
                "name": f"{fname} band",
                "customdata": np.stack(
                    (
                        pdf["i:jd"][idx] - 2400000.5,
                        pdf["i:isdiffpos"].apply(lambda x: "(-) " if x == "f" else "")[
                            idx
                        ],
                        pdf["d:tag"].apply(
                            lambda x: "" if x == "valid" else " (low quality)"
                        )[idx],
                    ),
                    axis=-1,
                ),
                "hovertemplate": hovertemplate,
                "marker": {
                    "size": pdf["d:tag"].apply(lambda x: 12 if x == "valid" else 6)[
                        idx
                    ],
                    "color": pdf["i:isdiffpos"].apply(
                        lambda x,
                        color_negative=color_negative,
                        color=color: color_negative if x == "f" else color
                    )[idx],
                    "symbol": pdf["d:tag"].apply(
                        lambda x: "o" if x == "valid" else "triangle-up"
                    )[idx],
                    "line": {"width": 0},
                    "opacity": 1,
                },
            },
        )

        if is_dc_corrected:
            # Overplot the levels of nearby source magnitudes
            ref = np.mean(pdf["i:magnr"][idx])

            figure["layout"]["shapes"].append(
                {
                    "type": "line",
                    "yref": "y",
                    "y0": ref,
                    "y1": ref,  # adding a horizontal line
                    "xref": "paper",
                    "x0": 0,
                    "x1": 1,
                    "line": {"color": color, "dash": "dash", "width": 1},
                    "legendgroup": f"{fname} band",
                    "opacity": 0.3,
                },
            )

    return figure


@app.callback(
    Output("scores", "figure"),
    [
        Input("object-data", "data"),
    ],
    prevent_initial_call=True,
)
def draw_scores(object_data) -> dict:
    """Draw scores from SNN module

    Returns
    -------
    figure: dict

    TODO: memoise me
    """
    pdf = pd.read_json(io.StringIO(object_data))

    # type conversion
    dates = convert_jd(pdf["i:jd"])

    hovertemplate = """
    <b>%{customdata[0]}</b>: %{y:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
    <b>mjd</b>: %{customdata[1]}
    <extra></extra>
    """
    figure = {
        "data": [
            {
                "x": dates,
                "y": [0.5] * len(dates),
                "mode": "lines",
                "showlegend": False,
                "hoverinfo": "skip",
                "line": {
                    "color": "black",
                    "width": 2.5,
                    "dash": "dash",
                },
            },
            {
                "x": dates,
                "y": pdf["d:snn_snia_vs_nonia"],
                "mode": "markers",
                "name": "SN Ia score",
                "customdata": list(
                    zip(
                        ["SN Ia score"] * len(pdf),
                        pdf["i:jd"] - 2400000.5,
                    ),
                ),
                "hovertemplate": hovertemplate,
                "marker": {"size": 10, "color": "#15284F", "symbol": "circle"},
            },
            {
                "x": dates,
                "y": pdf["d:snn_sn_vs_all"],
                "mode": "markers",
                "name": "SNe score",
                "customdata": list(
                    zip(
                        ["SNe score"] * len(pdf),
                        pdf["i:jd"] - 2400000.5,
                    ),
                ),
                "hovertemplate": hovertemplate,
                "marker": {"size": 10, "color": "#F5622E", "symbol": "square"},
            },
            {
                "x": dates,
                "y": pdf["d:rf_snia_vs_nonia"],
                "mode": "markers",
                "name": "Early SN Ia score",
                "customdata": list(
                    zip(
                        ["Early SN Ia score"] * len(pdf),
                        pdf["i:jd"] - 2400000.5,
                    ),
                ),
                "hovertemplate": hovertemplate,
                "marker": {"size": 10, "color": "#3C8DFF", "symbol": "diamond"},
            },
        ],
        "layout": layout_scores,
    }
    return figure


def extract_max_t2(pdf):
    """ """
    cols = [i for i in pdf.columns if i.startswith("d:t2")]

    if cols == []:
        return pd.DataFrame()

    filt = pdf[cols].apply(lambda x: np.sum(x) > 0, axis=1)

    if pdf[filt].empty:
        return pd.DataFrame()

    series = pdf[cols][filt].apply(lambda x: np.array(x) == np.max(x), axis=1)
    df_tmp = pd.DataFrame(list(series.to_numpy()), columns=pdf[cols].columns).T.sum(
        axis=1
    )
    df = pd.DataFrame(
        {
            "r": df_tmp.to_numpy(),
            "theta": df_tmp.index,
        },
        columns=["r", "theta"],
    )

    return df


@app.callback(
    Output("t2", "children"),
    [
        Input("object-data", "data"),
    ],
    prevent_initial_call=True,
)
def draw_t2(object_data) -> dict:
    """Draw scores from SNN module

    Returns
    -------
    figure: dict

    TODO: memoise me
    """
    pdf = pd.read_json(io.StringIO(object_data))

    df = extract_max_t2(pdf)

    if df.empty:
        msg = """
        No classification from T2 yet
        """
        out = dmc.Alert(msg, color="red")
    else:
        figure = go.Figure(
            data=go.Scatterpolar(
                r=df.r,
                theta=[i.split("_")[-1] for i in df.theta],
                fill="toself",
                line=dict(color="#F5622E"),
            ),
        )
        # figure = px.line_polar(df, r='r', theta='theta', line_close=True)
        # figure.update_traces(fill='toself')
        figure.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                ),
            ),
            showlegend=False,
            margin=dict(l=10, r=10, b=20, t=10),
        )

        graph = dcc.Graph(
            id="t2",
            figure=figure,
            style={
                "width": "100%",
                "height": "20pc",
            },
            config={"displayModeBar": False},
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
            label=msg,
        )
        out = dmc.Center(
            children=[
                dmc.Group(
                    [
                        tooltip,
                        graph,
                    ],
                    justify="center",
                ),
            ],
        )

    return out


@app.callback(
    Output("colors", "figure"),
    [
        Input("object-data", "data"),
    ],
    prevent_initial_call=True,
)
def draw_color(object_data) -> dict:
    """Draw color evolution

    Returns
    -------
    figure: dict
    """
    pdf = pd.read_json(io.StringIO(object_data))

    # type conversion
    dates = convert_jd(pdf["i:jd"])

    hovertemplate = """
    <b>%{yaxis.title.text}</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
    <b>mjd</b>: %{customdata}
    <extra></extra>
    """
    color = "#3C8DFF"
    idx = pdf["i:fid"] == 1  # Show colors at g points only
    figure = {
        "data": [
            {
                "x": dates[idx],
                "y": pdf["v:g-r"][idx],
                "error_y": {
                    "type": "data",
                    "array": pdf["v:sigma(g-r)"][idx],
                    "visible": True,
                    "width": 0,
                    "color": color,
                    "opacity": 0.5,
                },
                "mode": "markers",
                "name": "g-r (mag)",
                "customdata": list(
                    pdf["i:jd"] - 2400000.5,
                ),
                "hovertemplate": hovertemplate,
                "marker": {
                    "size": 10,
                    "color": color,
                    "symbol": "circle",
                },
            },
        ],
        "layout": layout_colors,
    }
    return figure


@app.callback(
    Output("colors_rate", "figure"),
    [
        Input("object-data", "data"),
    ],
    prevent_initial_call=True,
)
def draw_color_rate(object_data) -> dict:
    """Draw color rate

    Returns
    -------
    figure: dict

    TODO: memoise me
    """
    pdf = pd.read_json(io.StringIO(object_data))

    # type conversion
    dates = convert_jd(pdf["i:jd"])

    hovertemplate_rate = """
    <b>%{customdata[0]} in mag/day</b>: %{y:.3f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
    <b>mjd</b>: %{customdata[1]}
    <extra></extra>
    """
    m1 = pdf["i:fid"] == 1
    m2 = pdf["i:fid"] == 2
    figure = {
        "data": [
            {
                "x": dates[m1],
                "y": pdf["v:rate(g-r)"][m1],
                "error_y": {
                    "type": "data",
                    "array": pdf["v:sigma(rate(g-r))"][m1],
                    "visible": True,
                    "width": 0,
                    "color": "#3C8DFF",
                    "opacity": 0.5,
                },
                "mode": "markers",
                "name": "rate g-r (mag/day)",
                "customdata": list(
                    zip(
                        ["rate(g - r)"] * len(pdf["i:jd"][m1]),
                        pdf["i:jd"][m1] - 2400000.5,
                    ),
                ),
                "hovertemplate": hovertemplate_rate,
                "marker": {
                    "size": 10,
                    "color": "#3C8DFF",
                    "symbol": "circle",
                },
            },
            {
                "x": dates[m1],
                "y": pdf["v:rate"][m1],
                "error_y": {
                    "type": "data",
                    "array": pdf["v:sigma(rate)"][m1],
                    "visible": True,
                    "width": 0,
                    "color": "#15284F",
                    "opacity": 0.5,
                },
                "mode": "markers",
                "name": "rate g (mag/day)",
                "customdata": list(
                    zip(
                        ["rate(g)"] * len(pdf["i:jd"][m1]),
                        pdf["i:jd"][m1] - 2400000.5,
                    ),
                ),
                "hovertemplate": hovertemplate_rate,
                "marker": {
                    "size": 10,
                    "color": "#15284F",
                    "symbol": "square",
                },
            },
            {
                "x": dates[m2],
                "y": pdf["v:rate"][m2],
                "error_y": {
                    "type": "data",
                    "array": pdf["v:sigma(rate)"][m2],
                    "visible": True,
                    "width": 0,
                    "color": "#F5622E",
                    "opacity": 0.5,
                },
                "mode": "markers",
                "name": "rate r (mag/day)",
                "customdata": list(
                    zip(
                        ["rate(r)"] * len(pdf["i:jd"][m2]),
                        pdf["i:jd"][m2] - 2400000.5,
                    ),
                ),
                "hovertemplate": hovertemplate_rate,
                "marker": {
                    "size": 10,
                    "color": "#F5622E",
                    "symbol": "diamond",
                },
            },
        ],
        "layout": layout_colors_rate,
    }
    return figure


# The function assumes that it got pairs of `relayoutData` and `figure` for each
# of graphs where it will link x axis zoom, in both input and output. Outputs should
# probably be declared with `allow_duplicate=True` if they are used in actual plotters too
linked_zoom_plots_xaxis_js = """
function linked_zoom_xaxis() {
    const ctx = dash_clientside.callback_context;
    const triggered = ctx.triggered.map(t => t.prop_id);
    const aid = Object.keys(ctx.inputs).findIndex((x) => x == triggered);
    const Nfigs = arguments.length / 2;

    if (aid < 0)
        // Initial call, or something went wrong
        return Array(Nfigs*2).fill(dash_clientside.no_update);

    var relayout = arguments[aid];

    let results = Array();

    for(i = 0; i < Nfigs; i++) {
        var figure_state = arguments[2*i + 1];
        if (figure_state === undefined)
            continue;
        figure_state = JSON.parse(JSON.stringify(figure_state));

        if ('xaxis.autorange' in relayout) {
            figure_state['layout']['xaxis']['autorange'] = true;
            figure_state['layout']['yaxis']['autorange'] = true;
        } else if ('xaxis.range[0]' in relayout){
            figure_state['layout']['xaxis']['range'] = [
                relayout['xaxis.range[0]'], relayout['xaxis.range[1]']
            ];
            figure_state['layout']['xaxis']['autorange'] = false;
        } else {
            // TODO: return no_updates?..
        }

        results.push(relayout);
        results.push(figure_state);
    }

    return results;
}
"""

clientside_callback(
    linked_zoom_plots_xaxis_js,
    [
        Output("lightcurve_scores", "relayoutData", allow_duplicate=True),
        Output("lightcurve_scores", "figure", allow_duplicate=True),
        Output("scores", "relayoutData", allow_duplicate=True),
        Output("scores", "figure", allow_duplicate=True),
        # TODO: add t2
        Output("colors", "relayoutData", allow_duplicate=True),
        Output("colors", "figure", allow_duplicate=True),
        Output("colors_rate", "relayoutData", allow_duplicate=True),
        Output("colors_rate", "figure", allow_duplicate=True),
    ],
    [
        Input("lightcurve_scores", "relayoutData"),
        Input("lightcurve_scores", "figure"),
        Input("scores", "relayoutData"),
        Input("scores", "figure"),
        # TODO: add t2
        Input("colors", "relayoutData"),
        Input("colors", "figure"),
        Input("colors_rate", "relayoutData"),
        Input("colors_rate", "figure"),
    ],
    prevent_initial_call=True,
)


def extract_cutout(object_data, time0, kind):
    """Extract cutout data from the alert

    Parameters
    ----------
    object_data: json
        Jsonified pandas DataFrame
    time0: str
        ISO time of the cutout to extract
    kind: str
        science, template, or difference

    Returns
    -------
    data: np.array
        2D array containing cutout data
    """
    pdf_ = pd.read_json(io.StringIO(object_data))

    if time0 is None:
        position = 0
    else:
        pdf_ = pdf_.sort_values("i:jd", ascending=False)
        # Round to avoid numerical precision issues
        jds = pdf_["i:jd"].apply(lambda x: np.round(x, 3)).to_numpy()
        jd0 = np.round(Time(time0, format="iso").jd, 3)
        if jd0 in jds:
            position = np.where(jds == jd0)[0][0]
        else:
            return None

    # Construct the query
    payload = {
        "objectId": pdf_["i:objectId"].to_numpy()[0],
        "kind": kind.capitalize(),
        "output-format": "FITS",
    }

    if position > 0 and "i:candid" in pdf_.columns:
        payload["candid"] = str(pdf_["i:candid"].to_numpy()[position])

    # Extract the cutout data
    r = request_api(
        "/api/v1/cutouts",
        json=payload,
        output="raw",
    )

    cutout = readstamp(r, gzipped=False)

    if (
        kind == "difference"
        and "i:isdiffpos" in pdf_.columns
        and pdf_["i:isdiffpos"].to_numpy()[position] == "f"
    ):
        # Negative event, let's invert the diff cutout
        cutout *= -1

    return cutout


@app.callback(
    Output("stamps", "children"),
    [
        Input("lightcurve_cutouts", "clickData"),
        Input("object-data", "data"),
    ],
    prevent_initial_call=True,
)
def draw_cutouts(clickData, object_data):
    """Draw cutouts data based on lightcurve data"""
    if clickData is not None:
        jd0 = clickData["points"][0]["x"]
    else:
        jd0 = None

    figs = []
    for kind in ["science", "template", "difference"]:
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
            ),
        )

    return figs


@app.callback(
    Output("stamps_modal_content", "children"),
    [
        Input("object-data", "data"),
        Input("date_modal_select", "value"),
        Input("stamps_modal", "is_open"),
    ],
    prevent_initial_call=True,
)
def draw_cutouts_modal(object_data, date_modal_select, is_open):
    """Draw cutouts data based on lightcurve data"""
    if not is_open:
        raise PreventUpdate

    figs = []
    for kind in ["science", "template", "difference"]:
        try:
            cutout = extract_cutout(object_data, date_modal_select, kind=kind)
            if cutout is None:
                return no_update
            data = draw_cutout(cutout, kind, id_type="stamp_modal")
        except OSError:
            data = dcc.Markdown("Load fail, refresh the page")

        figs.append(
            dbc.Col(
                [
                    html.Div(kind.capitalize(), className="text-center"),
                    data,
                ],
                xs=4,
                className="p-0",
            ),
        )

    return figs


def draw_cutouts_quickview(name, kinds=None):
    """Draw Science cutout data for the preview service"""
    if kinds is None:
        kinds = ["science"]
    figs = []
    for kind in kinds:
        try:  # noqa: PERF203
            # We may manually construct the payload to avoid extra API call
            object_data = f'{{"i:objectId":{{"0": "{name}"}}}}'
            data = extract_cutout(object_data, None, kind=kind)
            figs.append(draw_cutout(data, kind, zoom=False))
        except OSError:  # noqa: PERF203
            data = dcc.Markdown("Load fail, refresh the page")
            figs.append(data)
    return figs


def create_circular_mask(h, w, center=None, radius=None):
    if center is None:  # use the middle of the image
        center = (int(w / 2), int(h / 2))
    if radius is None:  # use the smallest distance between the center and image walls
        radius = min(center[0], center[1], w - center[0], h - center[1])

    x, y = np.ogrid[:h, :w]
    dist_from_center = np.sqrt((x - center[0]) ** 2 + (y - center[1]) ** 2)

    mask = dist_from_center <= radius
    return mask


def sigmoid(img: list) -> list:
    """Sigmoid function used for img_normalizer

    Parameters
    ----------
    img: float array
        a float array representing a non-normalized image

    Returns
    -------
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
    """Image normalisation between vmin and vmax using Sigmoid function

    Parameters
    ----------
    img: float array
        a float array representing a non-normalized image

    Returns
    -------
    out: float array where data are bounded between vmin and vmax
    """
    return (vmax - vmin) * sigmoid(img) + vmin


def legacy_normalizer(data: list, stretch="asinh", pmin=0.5, pmax=99.5) -> list:
    """Old cutout normalizer which use the central pixel

    Parameters
    ----------
    data: float array
        a float array representing a non-normalized image

    Returns
    -------
    out: float array where data are bouded between vmin and vmax
    """
    size = len(data)
    vmax = data[int(size / 2), int(size / 2)]
    vmin = np.min(data) + 0.2 * np.median(np.abs(data - np.median(data)))
    return _data_stretch(
        data, vmin=vmin, vmax=vmax, pmin=pmin, pmax=pmax, stretch=stretch
    )


def plain_normalizer(
    img: list, vmin: float, vmax: float, stretch="linear", pmin=0.5, pmax=99.5
) -> list:
    """Image normalisation between vmin and vmax

    Parameters
    ----------
    img: float array
        a float array representing a non-normalized image

    Returns
    -------
    out: float array where data are bounded between vmin and vmax
    """
    limits = np.percentile(img, [pmin, pmax])
    data = _data_stretch(
        img, vmin=limits[0], vmax=limits[1], stretch=stretch, vmid=0.1, exponent=2
    )
    data = (vmax - vmin) * data + vmin

    return data


def draw_cutout(data, title, lower_bound=0, upper_bound=1, zoom=True, id_type="stamp"):
    """Draw a cutout data"""
    # Update graph data for stamps
    data = np.nan_to_num(data)

    # data = sigmoid_normalizer(data, lower_bound, upper_bound)
    data = plain_normalizer(
        data,
        lower_bound,
        upper_bound,
        stretch="linear" if title in ["difference"] else "asinh",
        pmin=0.5,
        pmax=99.95,
    )

    data = data[::-1]
    # data = convolve(data, smooth=1, kernel='gauss')
    shape = data.shape

    zsmooth = False

    fig = go.Figure(
        data=go.Heatmap(
            z=data,
            showscale=False,
            hoverinfo="skip",
            colorscale="Blues_r",
            zsmooth=zsmooth,
        ),
    )
    # Greys_r

    axis_template = dict(
        autorange=True,
        showgrid=False,
        zeroline=False,
        linecolor="black",
        showticklabels=False,
        ticks="",
        range=[0, 60],
    )

    fig.update_layout(
        title=title,
        margin=dict(t=0, r=0, b=0, l=0),
        xaxis=axis_template,
        yaxis=axis_template,
        showlegend=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    fig.update_layout(width=shape[1], height=shape[0])
    fig.update_layout(yaxis={"scaleanchor": "x", "scaleratio": 1})

    style = {"display": "block", "aspect-ratio": "1", "margin": "1px"}
    classname = "zoom"
    classname = ""

    graph = dcc.Graph(
        id={"type": id_type, "id": title} if zoom else "undefined",
        figure=fig,
        style=style,
        config={"displayModeBar": False},
        className=classname,
        responsive=True,
    )

    return graph


zoom_cutouts_js = """
function zoom_cutouts(relayout_data, figure_states) {
    if (relayout_data.includes(undefined)) {
        return [dash_clientside.no_update, dash_clientside.no_update];
    }

    let unique_data = null;
    for (i in relayout_data)
        if (relayout_data.reduce((v,x) => v + (JSON.stringify(x) == JSON.stringify(relayout_data[i]) ? 1 : 0), 0) == 1)
            unique_data = relayout_data[i];

    if (unique_data) {
        for (i in figure_states) {
            figure_states[i] = JSON.parse(JSON.stringify(figure_states[i]));
            if ('xaxis.autorange' in unique_data) {
                figure_states[i]['layout']['xaxis']['autorange'] = true;
                figure_states[i]['layout']['yaxis']['autorange'] = true;
            } else {
                figure_states[i]['layout']['xaxis']['range'] = [
                    unique_data['xaxis.range[0]'], unique_data['xaxis.range[1]']
                ];
                figure_states[i]['layout']['yaxis']['range'] = [
                    unique_data['yaxis.range[0]'], unique_data['yaxis.range[1]']
                ];
                figure_states[i]['layout']['xaxis']['autorange'] = false;
                figure_states[i]['layout']['yaxis']['autorange'] = false;
            }
        }

        return [[unique_data, unique_data, unique_data], figure_states];
    }

    return [dash_clientside.no_update, dash_clientside.no_update];
}
"""

clientside_callback(
    zoom_cutouts_js,
    [
        Output({"type": "stamp", "id": ALL}, "relayoutData"),
        Output({"type": "stamp", "id": ALL}, "figure"),
    ],
    [
        Input({"type": "stamp", "id": ALL}, "relayoutData"),
    ],
    State({"type": "stamp", "id": ALL}, "figure"),
    prevent_initial_call=True,
)

clientside_callback(
    zoom_cutouts_js,
    [
        Output({"type": "stamp_modal", "id": ALL}, "relayoutData"),
        Output({"type": "stamp_modal", "id": ALL}, "figure"),
    ],
    [
        Input({"type": "stamp_modal", "id": ALL}, "relayoutData"),
    ],
    State({"type": "stamp_modal", "id": ALL}, "figure"),
    prevent_initial_call=True,
)


@app.callback(
    Output("aladin-lite-runner", "run"),
    Input("object-data", "data"),
    prevent_initial_call=True,
)
def integrate_aladin_lite(object_data):
    """Integrate aladin light in the 2nd Tab of the dashboard.

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
    pdf_ = pd.read_json(io.StringIO(object_data))
    cols = [
        "i:jd",
        "i:ra",
        "i:dec",
        "i:ranr",
        "i:decnr",
        "i:magnr",
        "i:sigmagnr",
        "i:fid",
    ]
    pdf = pdf_.loc[:, cols]
    pdf = pdf.sort_values("i:jd", ascending=False)

    # Coordinate of the current alert
    ra0 = pdf["i:ra"].to_numpy()[0]
    dec0 = pdf["i:dec"].to_numpy()[0]

    # Javascript. Note the use {{}} for dictionary
    img = f"""
    var aladin = A.aladin('#aladin-lite-div',
              {{
                survey: 'https://alasky.cds.unistra.fr/Pan-STARRS/DR1/color-z-zg-g/',
                fov: 0.025,
                target: '{ra0} {dec0}',
                reticleColor: '#ff89ff',
                reticleSize: 32,
                showContextMenu: true,
                showCooGridControl: true,
    }});
    var cat = 'https://axel.u-strasbg.fr/HiPSCatService/Simbad';
    var hips = A.catalogHiPS(cat, {{onClick: 'showTable', name: 'Simbad'}});
    aladin.addCatalog(hips);
    """

    # Unique positions of nearest reference object
    pdfnr = pdf[["i:ranr", "i:decnr", "i:magnr", "i:sigmagnr", "i:fid"]][
        np.isfinite(pdf["i:magnr"])
    ].drop_duplicates()

    if len(pdfnr.index):
        img += """
        var catnr_zg = A.catalog({name: 'ZTF Reference nearest, zg', sourceSize: 6, shape: 'plus', color: 'green', onClick: 'showPopup', limit: 1000});
        var catnr_zr = A.catalog({name: 'ZTF Reference nearest, zr', sourceSize: 6, shape: 'plus', color: 'red', onClick: 'showPopup', limit: 1000});
        """

        for _, row in pdfnr.iterrows():
            img += """
            catnr_{}.addSources([A.source({}, {}, {{ZTF: 'Reference', mag: {:.2f}, err: {:.2f}, filter: '{}'}})]);
            """.format(
                {1: "zg", 2: "zr", 3: "zi"}.get(row["i:fid"]),
                row["i:ranr"],
                row["i:decnr"],
                row["i:magnr"],
                row["i:sigmagnr"],
                {1: "zg", 2: "zr", 3: "zi"}.get(row["i:fid"]),
            )

        img += """aladin.addCatalog(catnr_zg);"""
        img += """aladin.addCatalog(catnr_zr);"""

    # img cannot be executed directly because of formatting
    # We split line-by-line and remove comments
    img_to_show = [i for i in img.split("\n") if "// " not in i]

    return " ".join(img_to_show)


def draw_sso_lightcurve(pdf) -> dict:
    """Draw SSO object lightcurve with errorbars, and ephemerides on top from the miriade IMCCE service.

    Returns
    -------
    figure: dict
    """
    if pdf.empty:
        return html.Div()

    # type conversion
    dates = convert_jd(pdf["i:jd"])
    pdf["i:fid"] = pdf["i:fid"].astype(int)

    # shortcuts
    mag = pdf["i:magpsf"]
    err = pdf["i:sigmapsf"]

    layout_sso_lightcurve["yaxis"]["title"] = "Difference magnitude"
    layout_sso_lightcurve["yaxis"]["autorange"] = "reversed"

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
        "x": dates[pdf["i:fid"] == 1],
        "y": mag[pdf["i:fid"] == 1],
        "error_y": {
            "type": "data",
            "array": err[pdf["i:fid"] == 1],
            "visible": True,
            "width": 0,
            "opacity": 0.5,
            "color": COLORS_ZTF[0],
        },
        "mode": "markers",
        "name": "g band",
        "customdata": pdf["i:jd"][pdf["i:fid"] == 1] - 2400000.5,
        "hovertemplate": hovertemplate,
        "marker": {"size": 6, "color": COLORS_ZTF[0], "symbol": "o"},
    }
    to_plot.append(gobs)

    if "SDSS:g" in pdf.columns:
        gephem = {
            "x": dates[pdf["i:fid"] == 1],
            "y": pdf["SDSS:g"][pdf["i:fid"] == 1],
            "mode": "markers",
            "name": "g (ephem)",
            "customdata": pdf["i:jd"][pdf["i:fid"] == 1] - 2400000.5,
            "hovertemplate": hovertemplate_ephem,
            "marker": {
                "size": 6,
                "color": COLORS_ZTF[0],
                "symbol": "o",
                "opacity": 0.5,
            },
        }
        to_plot.append(gephem)

    robs = {
        "x": dates[pdf["i:fid"] == 2],
        "y": mag[pdf["i:fid"] == 2],
        "error_y": {
            "type": "data",
            "array": err[pdf["i:fid"] == 2],
            "visible": True,
            "width": 0,
            "opacity": 0.5,
            "color": COLORS_ZTF[1],
        },
        "mode": "markers",
        "name": "r band",
        "customdata": pdf["i:jd"][pdf["i:fid"] == 2] - 2400000.5,
        "hovertemplate": hovertemplate,
        "marker": {"size": 6, "color": COLORS_ZTF[1], "symbol": "o"},
    }
    to_plot.append(robs)

    if "SDSS:r" in pdf.columns:
        rephem = {
            "x": dates[pdf["i:fid"] == 2],
            "y": pdf["SDSS:r"][pdf["i:fid"] == 2],
            "mode": "markers",
            "name": "r (ephem)",
            "customdata": pdf["i:jd"][pdf["i:fid"] == 2] - 2400000.5,
            "hovertemplate": hovertemplate_ephem,
            "marker": {
                "size": 6,
                "color": COLORS_ZTF[1],
                "symbol": "o",
                "opacity": 0.5,
            },
        }
        to_plot.append(rephem)

    figure = {
        "data": to_plot,
        "layout": layout_sso_lightcurve,
    }
    graph = dcc.Graph(
        figure=figure,
        style={
            "width": "100%",
            "height": "30pc",
        },
        config={"displayModeBar": False},
    )
    card = dmc.Paper(graph)
    return card


def draw_sso_residual(pdf) -> dict:
    """Draw SSO residuals (observation - ephemerides)

    Returns
    -------
    figure: dict
    """
    if pdf.empty:
        return html.Div()

    if "SDSS:g" not in pdf.columns:
        return dbc.Alert(
            "No colors available from ephemerides for {}".format(
                pdf["i:ssnamenr"].to_numpy()[0]
            ),
            color="danger",
        )

    # type conversion
    pdf["i:fid"] = pdf["i:fid"].astype(int)

    # shortcuts
    mag = pdf["i:magpsf"]
    err = pdf["i:sigmapsf"]

    layout_sso_residual = copy.deepcopy(layout_sso_lightcurve)
    layout_sso_residual["yaxis"]["title"] = "Residuals [mag]"
    layout_sso_residual["xaxis"]["title"] = "Ecliptic longitude [deg]"

    diff1 = mag[pdf["i:fid"] == 1] - pdf["SDSS:g"][pdf["i:fid"] == 1]
    diff2 = mag[pdf["i:fid"] == 2] - pdf["SDSS:r"][pdf["i:fid"] == 2]

    popt1, pcov1 = curve_fit(sine_fit, pdf["Longitude"][pdf["i:fid"] == 1], diff1)
    popt2, pcov2 = curve_fit(sine_fit, pdf["Longitude"][pdf["i:fid"] == 2], diff2)

    hovertemplate = r"""
    <b>objectId</b>: %{customdata[0]}<br>
    <b>%{yaxis.title.text}</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x:.2f}<br>
    <b>date</b>: %{customdata[1]}
    <extra></extra>
    """
    gresiduals = {
        "x": pdf["Longitude"][pdf["i:fid"] == 1],
        "y": diff1,
        "error_y": {
            "type": "data",
            "array": err[pdf["i:fid"] == 1],
            "visible": True,
            "width": 0,
            "opacity": 0.5,
            "color": COLORS_ZTF[0],
        },
        "mode": "markers",
        "name": "g band",
        "customdata": list(
            zip(
                pdf["i:objectId"][pdf["i:fid"] == 1],
                convert_jd(pdf["i:jd"][pdf["i:fid"] == 1]),
            ),
        ),
        "hovertemplate": hovertemplate,
        "marker": {"size": 6, "color": COLORS_ZTF[0], "symbol": "o"},
    }

    rresiduals = {
        "x": pdf["Longitude"][pdf["i:fid"] == 2],
        "y": diff2,
        "error_y": {
            "type": "data",
            "array": err[pdf["i:fid"] == 2],
            "visible": True,
            "width": 0,
            "opacity": 0.5,
            "color": COLORS_ZTF[1],
        },
        "mode": "markers",
        "name": "r band",
        "customdata": list(
            zip(
                pdf["i:objectId"][pdf["i:fid"] == 2],
                convert_jd(pdf["i:jd"][pdf["i:fid"] == 2]),
            ),
        ),
        "hovertemplate": hovertemplate,
        "marker": {"size": 6, "color": COLORS_ZTF[1], "symbol": "o"},
    }

    longitude_arr = np.linspace(0, 360, num=100)
    gfit = {
        "x": longitude_arr,
        "y": sine_fit(longitude_arr, *popt1),
        "mode": "lines",
        "name": "fit",
        "showlegend": False,
        "line": {
            "color": COLORS_ZTF[0],
        },
    }

    rfit = {
        "x": longitude_arr,
        "y": sine_fit(longitude_arr, *popt2),
        "mode": "lines",
        "name": "fit",
        "showlegend": False,
        "line": {
            "color": COLORS_ZTF[1],
        },
    }

    figure = {
        "data": [
            gresiduals,
            gfit,
            rresiduals,
            rfit,
        ],
        "layout": layout_sso_residual,
    }
    graph = dcc.Graph(
        figure=figure,
        style={
            "width": "100%",
            "height": "15pc",
        },
        config={"displayModeBar": False},
    )
    card = dmc.Paper(graph)
    return card


def draw_sso_astrometry(pdf) -> dict:
    """Draw SSO object astrometry, that is difference position wrt ephemerides from the miriade IMCCE service.

    Returns
    -------
    figure: dict
    """
    if pdf.empty:
        msg = """
        Object not referenced in the Minor Planet Center
        """
        return html.Div([html.Br(), dbc.Alert(msg, color="danger")])

    if "RA" not in pdf.columns:
        return dbc.Alert(
            "No ephemerides available for {}".format(pdf["i:ssnamenr"].to_numpy()[0]),
            color="danger",
        )

    # type conversion
    pdf["i:fid"] = pdf["i:fid"].astype(int)

    deltaRAcosDEC = (pdf["i:ra"] - pdf.RA) * np.cos(np.radians(pdf["i:dec"])) * 3600
    deltaDEC = (pdf["i:dec"] - pdf.Dec) * 3600

    hovertemplate = r"""
    <b>objectId</b>: %{customdata[0]}<br>
    <b>%{yaxis.title.text}</b>: %{y:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x:.2f}<br>
    <b>Observation date</b>: %{customdata[1]}
    <extra></extra>
    """
    diff_g = {
        "x": deltaRAcosDEC[pdf["i:fid"] == 1],
        "y": deltaDEC[pdf["i:fid"] == 1],
        "mode": "markers",
        "name": "g band",
        "customdata": list(
            zip(
                pdf["i:objectId"][pdf["i:fid"] == 1],
                Time(pdf["i:jd"][pdf["i:fid"] == 1], format="jd").iso,
            ),
        ),
        "hovertemplate": hovertemplate,
        "marker": {"size": 6, "color": COLORS_ZTF[0], "symbol": "o"},
    }

    diff_r = {
        "x": deltaRAcosDEC[pdf["i:fid"] == 2],
        "y": deltaDEC[pdf["i:fid"] == 2],
        "mode": "markers",
        "name": "r band",
        "customdata": list(
            zip(
                pdf["i:objectId"][pdf["i:fid"] == 2],
                Time(pdf["i:jd"][pdf["i:fid"] == 2], format="jd").iso,
            ),
        ),
        "hovertemplate": hovertemplate,
        "marker": {"size": 6, "color": COLORS_ZTF[1], "symbol": "o"},
    }

    figure = {
        "data": [
            diff_g,
            diff_r,
        ],
        "layout": layout_sso_astrometry,
    }
    graph = dcc.Graph(
        figure=figure,
        style={
            "width": "100%",
            "height": "30pc",
        },
        config={"displayModeBar": False},
    )
    card = dmc.Paper(graph)
    return card


@app.callback(
    Output("sso_phasecurve", "children"),
    [
        Input("switch-phase-curve-band", "value"),
        Input("switch-phase-curve-func", "value"),
    ],
    State("object-sso", "data"),
)
def draw_sso_phasecurve(switch_band: str, switch_func: str, object_sso) -> dict:
    """Draw SSO object phase curve"""
    pdf = pd.read_json(io.StringIO(object_sso))
    if pdf.empty:
        msg = """
        Object not referenced in the Minor Planet Center, or name not found in Fink.
        It may be a SSO candidate.
        """
        return html.Div([html.Br(), dbc.Alert(msg, color="danger")])

    if "i:magpsf_red" not in pdf.columns:
        return dbc.Alert(
            "No ephemerides available for {}".format(pdf["i:ssnamenr"].to_numpy()[0]),
            color="danger",
        )

    pdf = pdf.sort_values("Phase")

    # type conversion
    pdf["i:fid"] = pdf["i:fid"].astype(int)

    # Disctionary for filters
    filters = {1: "g", 2: "r", 3: "i"}
    filts = np.unique(pdf["i:fid"].to_numpy())

    figs = []
    residual_figs = []

    hovertemplate = r"""
    <b>objectId</b>: %{customdata[0]}<br>
    <b>%{yaxis.title.text}</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x:.2f}<br>
    <b>Observation date</b>: %{customdata[1]}
    <extra></extra>
    """

    if switch_func == "HG1G2":
        fitfunc = func_hg1g2
        params = ["H", "G1", "G2"]
        bounds = (
            [-3, 0, 0],
            [30, 1, 1],
        )
        p0 = [15.0, 0.15, 0.15]
        x = np.deg2rad(pdf["Phase"].to_numpy())
    elif switch_func == "HG12":
        fitfunc = func_hg12
        params = ["H", "G12"]
        bounds = (
            [-3, 0],
            [30, 1],
        )
        p0 = [15.0, 0.15]
        x = np.deg2rad(pdf["Phase"].to_numpy())
    elif switch_func == "HG":
        fitfunc = func_hg
        params = ["H", "G"]
        bounds = (
            [-3, 0],
            [30, 1],
        )
        p0 = [15.0, 0.15]
        x = np.deg2rad(pdf["Phase"].to_numpy())
    elif switch_func == "SHG1G2":
        fitfunc = func_hg1g2_with_spin
        params = ["H", "G1", "G2", "R", "alpha0", "delta0"]
        bounds = (
            [-3, 0, 0, 3e-1, 0, -np.pi / 2],
            [30, 1, 1, 1, 2 * np.pi, np.pi / 2],
        )
        p0 = [15.0, 0.15, 0.15, 0.8, np.pi, 0.0]
        x = [
            np.deg2rad(pdf["Phase"].to_numpy()),
            np.deg2rad(pdf["i:ra"].to_numpy()),
            np.deg2rad(pdf["i:dec"].to_numpy()),
        ]

    layout_sso_phasecurve["title"]["text"] = "Reduced &#967;<sup>2</sup>: "
    if switch_band == "per-band":
        dd = {"": [filters[f] + " band" for f in filts]}
        dd.update({i: [""] * len(filts) for i in params})
        df_table = pd.DataFrame(
            dd,
            index=[filters[f] for f in filts],
        )

        # Multi-band fit
        outdic = estimate_sso_params(
            magpsf_red=pdf["i:magpsf_red"].to_numpy(),
            sigmapsf=pdf["i:sigmapsf"].to_numpy(),
            phase=np.deg2rad(pdf["Phase"].to_numpy()),
            filters=pdf["i:fid"].to_numpy(),
            ra=np.deg2rad(pdf["i:ra"].to_numpy()),
            dec=np.deg2rad(pdf["i:dec"].to_numpy()),
            p0=p0,
            bounds=bounds,
            model=switch_func,
            normalise_to_V=False,
        )
        if outdic["fit"] != 0:
            return dbc.Alert(
                "The fitting procedure could not converge.", color="danger"
            )

        for i, f in enumerate(filts):
            cond = pdf["i:fid"] == f
            popt = []
            for pindex, param in enumerate(params):
                # rad2deg
                if pindex >= 3:
                    suffix = ""
                else:
                    suffix = f"_{f}"

                loc = df_table[param].index == filters[f]
                df_table[param][loc] = "{:.2f} &plusmn; {:.2f}".format(
                    outdic[param + suffix],
                    outdic["err_" + param + suffix],
                )

                if pindex <= 3:
                    popt.append(outdic[param + suffix])
                else:
                    popt.append(np.deg2rad(outdic[param + suffix]))

            ydata = pdf.loc[cond, "i:magpsf_red"]

            figs.append(
                {
                    "x": pdf.loc[cond, "Phase"].to_numpy(),
                    "y": ydata.to_numpy(),
                    "error_y": {
                        "type": "data",
                        "array": pdf.loc[cond, "i:sigmapsf"].to_numpy(),
                        "visible": True,
                        "width": 0,
                        "opacity": 0.5,
                        "color": COLORS_ZTF[i],
                    },
                    "mode": "markers",
                    "name": f"{filters[f]}",
                    "customdata": list(
                        zip(
                            pdf.loc[cond, "i:objectId"],
                            Time(pdf.loc[cond, "i:jd"], format="jd").iso,
                        ),
                    ),
                    "hovertemplate": hovertemplate,
                    "marker": {"size": 6, "color": COLORS_ZTF[i], "symbol": "o"},
                },
            )

            if switch_func == "SHG1G2":
                xx = np.array(x)[:, cond]
            else:
                xx = x[cond]

            figs.append(
                {
                    "x": pdf.loc[cond, "Phase"].to_numpy(),
                    "y": fitfunc(xx, *popt),
                    "mode": "markers",
                    "name": f"fit {filters[f]}",
                    "marker": {
                        "size": 6,
                        "color": COLORS_ZTF[i],
                        "symbol": "x",
                        "opacity": 0.5,
                    },
                },
            )

            residual_figs.append(
                {
                    "x": pdf.loc[cond, "Phase"].to_numpy(),
                    "y": ydata.to_numpy() - fitfunc(xx, *popt),
                    "error_y": {
                        "type": "data",
                        "array": pdf.loc[cond, "i:sigmapsf"].to_numpy(),
                        "visible": True,
                        "width": 0,
                        "opacity": 0.5,
                        "color": COLORS_ZTF[i],
                    },
                    "mode": "markers",
                    "name": f"Residual {filters[f]}",
                    "showlegend": False,
                    "marker": {
                        "color": COLORS_ZTF[i],
                    },
                },
            )
    elif switch_band == "combined":
        dd = {"": ["V band"]}
        dd.update({i: [""] for i in params})
        df_table = pd.DataFrame(
            dd,
            index=["V band"],
        )

        outdic = estimate_sso_params(
            magpsf_red=pdf["i:magpsf_red"].to_numpy(),
            sigmapsf=pdf["i:sigmapsf"].to_numpy(),
            phase=np.deg2rad(pdf["Phase"].to_numpy()),
            filters=pdf["i:fid"].to_numpy(),
            ra=np.deg2rad(pdf["i:ra"].to_numpy()),
            dec=np.deg2rad(pdf["i:dec"].to_numpy()),
            p0=p0,
            bounds=bounds,
            model=switch_func,
            normalise_to_V=True,
        )
        if outdic["fit"] != 0:
            return dbc.Alert(
                "The fitting procedure could not converge.", color="danger"
            )

        popt = []
        for pindex, param in enumerate(params):
            # rad2deg
            if pindex >= 3:
                suffix = ""
            else:
                suffix = "_V"

            df_table[param] = "{:.2f} &plusmn; {:.2f}".format(
                outdic[param + suffix],
                outdic["err_" + param + suffix],
            )

            if pindex <= 3:
                popt.append(outdic[param + suffix])
            else:
                popt.append(np.deg2rad(outdic[param + suffix]))

        color = compute_color_correction(pdf["i:fid"].to_numpy())
        ydata = pdf["i:magpsf_red"].to_numpy() + color

        figs.append(
            {
                "x": pdf["Phase"].to_numpy(),
                "y": ydata,
                "error_y": {
                    "type": "data",
                    "array": pdf["i:sigmapsf"].to_numpy(),
                    "visible": True,
                    "width": 0,
                    "opacity": 0.5,
                    "color": COLORS_ZTF[0],
                },
                "mode": "markers",
                "name": "V band",
                "customdata": list(
                    zip(pdf["i:objectId"], Time(pdf["i:jd"], format="jd").iso),
                ),
                "hovertemplate": hovertemplate,
                "marker": {"size": 6, "color": COLORS_ZTF[0], "symbol": "o"},
            },
        )

        figs.append(
            {
                "x": pdf["Phase"].to_numpy(),
                "y": fitfunc(x, *popt),
                "mode": "markers",
                "name": "fit combined",
                "marker": {
                    "size": 6,
                    "color": COLORS_ZTF[0],
                    "symbol": "x",
                    "opacity": 0.5,
                },
            },
        )

        residual_figs.append(
            {
                "x": pdf["Phase"].to_numpy(),
                "y": ydata - fitfunc(x, *popt),
                "error_y": {
                    "type": "data",
                    "array": pdf["i:sigmapsf"].to_numpy(),
                    "visible": True,
                    "width": 0,
                    "opacity": 0.5,
                    "color": COLORS_ZTF[0],
                },
                "mode": "markers",
                "name": "Residual",
                "showlegend": False,
                "marker": {
                    "color": COLORS_ZTF[0],
                },
            },
        )
    layout_sso_phasecurve["title"]["text"] += "  {:.2f}  ".format(outdic["chi2red"])

    residual_figure = {
        "data": residual_figs,
        "layout": layout_sso_phasecurve_residual,
    }

    figure = {
        "data": figs,
        "layout": layout_sso_phasecurve,
    }

    columns = [
        {
            "id": c,
            "name": c,
            "type": "text",
            # 'hideable': True,
            "presentation": "markdown",
        }
        for c in df_table.columns
    ]

    table = dash_table.DataTable(
        id="phasecurve_table",
        columns=columns,
        data=df_table.to_dict("records"),
        style_as_list_view=True,
        style_data={
            "backgroundColor": "rgb(248, 248, 248, .7)",
        },
        style_table={"maxWidth": "100%"},
        style_cell={
            "padding": "5px",
            "textAlign": "left",
            "border": "0.5px solid grey",
        },
        style_filter={"backgroundColor": "rgb(238, 238, 238, .7)"},
        style_header={
            "backgroundColor": "rgb(230, 230, 230)",
            "fontWeight": "bold",
        },
    )

    graph1 = dcc.Graph(
        figure=figure,
        style={
            "width": "100%",
            "height": "25pc",
        },
        config={"displayModeBar": False},
    )

    graph2 = dcc.Graph(
        figure=residual_figure,
        style={
            "width": "100%",
            "height": "15pc",
        },
        config={"displayModeBar": False},
    )
    card = dmc.Paper(
        [
            graph1,
            html.Br(),
            graph2,
            html.Br(),
            table,
        ],
    )
    return card


def draw_tracklet_lightcurve(pdf) -> dict:
    """Draw tracklet object lightcurve with errorbars

    Returns
    -------
    figure: dict

    """
    if pdf.empty:
        msg = """
        Object not associated to a tracklet
        """
        return html.Div([html.Br(), dbc.Alert(msg, color="danger")])

    # type conversion
    pdf["i:fid"] = pdf["i:fid"].astype(int)

    # shortcuts
    mag = pdf["i:magpsf"]
    err = pdf["i:sigmapsf"]

    layout_tracklet_lightcurve["yaxis"]["title"] = "Difference magnitude"
    layout_tracklet_lightcurve["yaxis"]["autorange"] = "reversed"

    hovertemplate = r"""
    <b>objectId</b>: %{customdata[0]}<br>
    <b>%{yaxis.title.text}</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x:.2f}<br>
    <b>Date</b>: %{customdata[1]}
    <extra></extra>
    """

    def generate_plot(filt, marker, color, showlegend):
        if filt == 1:
            name = "g band"
        else:
            name = "r band"
        dic = {
            "x": pdf["i:ra"][pdf["i:fid"] == filt],
            "y": mag[pdf["i:fid"] == filt],
            "error_y": {
                "type": "data",
                "array": err[pdf["i:fid"] == filt],
                "visible": True,
                "width": 0,
                "opacity": 0.5,
                "color": color,
            },
            "mode": "markers",
            "name": name,
            "showlegend": showlegend,
            "customdata": list(
                zip(
                    pdf["i:objectId"][pdf["i:fid"] == filt],
                    pdf["v:lastdate"][pdf["i:fid"] == filt],
                ),
            ),
            "hovertemplate": hovertemplate,
            "marker": {"size": 12, "color": color, "symbol": marker},
        }
        return dic

    data_ = []
    for filt in np.unique(pdf["i:fid"]):
        if filt == 1:
            data_.append(
                generate_plot(1, marker="o", color=COLORS_ZTF[0], showlegend=True)
            )
        elif filt == 2:
            data_.append(
                generate_plot(2, marker="o", color=COLORS_ZTF[1], showlegend=True)
            )

    figure = {
        "data": data_,
        "layout": layout_tracklet_lightcurve,
    }

    graph = dcc.Graph(
        figure=figure,
        style={
            "width": "100%",
            "height": "25pc",
        },
        config={"displayModeBar": False},
    )

    card = html.Div(
        [
            dmc.Paper(
                graph,
            ),
        ],
    )
    return card


def draw_tracklet_radec(pdf) -> dict:
    """Draw tracklet object radec

    Returns
    -------
    figure: dict
    """
    if pdf.empty:
        msg = ""
        return msg

    # shortcuts
    ra = pdf["i:ra"].astype(float)
    dec = pdf["i:dec"].astype(float)

    hovertemplate = r"""
    <b>objectId</b>: %{customdata[0]}<br>
    <b>%{yaxis.title.text}</b>: %{y:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x:.2f}<br>
    <b>Date</b>: %{customdata[1]}
    <extra></extra>
    """
    figure = {
        "data": [
            {
                "x": ra,
                "y": dec,
                "mode": "markers",
                "name": "Observations",
                "customdata": list(
                    zip(
                        pdf["i:objectId"],
                        pdf["v:lastdate"],
                    ),
                ),
                "hovertemplate": hovertemplate,
                "marker": {"size": 12, "color": "#d62728", "symbol": "circle-open-dot"},
            },
        ],
        "layout": layout_sso_radec,
    }
    graph = dcc.Graph(
        figure=figure,
        style={
            "width": "100%",
            "height": "15pc",
        },
        config={"displayModeBar": False},
    )
    card = html.Div(
        [
            dmc.Paper(
                graph,
            ),
        ],
    )
    return card


@app.callback(
    Output("alert_table", "children"),
    [
        Input("object-data", "data"),
        Input("lightcurve_cutouts", "clickData"),
    ],
    prevent_initial_call=True,
)
def alert_properties(object_data, clickData):
    pdf_ = pd.read_json(io.StringIO(object_data))

    if clickData is not None:
        time0 = clickData["points"][0]["x"]
        # Round to avoid numerical precision issues
        jds = pdf_["i:jd"].apply(lambda x: np.round(x, 3)).to_numpy()
        jd0 = np.round(Time(time0, format="iso").jd, 3)
        if jd0 in jds:
            pdf_ = pdf_[jds == jd0]
        else:
            return no_update

    pdf = pdf_.head(1)
    pdf = pd.DataFrame({"Name": pdf.columns, "Value": pdf.to_numpy()[0]})
    columns = [
        {
            "id": c,
            "name": c,
            # 'hideable': True,
            "presentation": "input",
            "type": "text" if c == "Name" else "numeric",
            "format": dash_table.Format.Format(precision=8),
        }
        for c in pdf.columns
    ]
    data = pdf.to_dict("records")
    table = dash_table.DataTable(
        data=data,
        columns=columns,
        id="result_table_alert",
        # page_size=10,
        page_action="none",
        style_as_list_view=True,
        filter_action="native",
        markdown_options={"link_target": "_blank"},
        # fixed_columns={'headers': True},#, 'data': 1},
        persistence=True,
        persistence_type="memory",
        style_data={
            "backgroundColor": "rgb(248, 248, 248, 1.0)",
        },
        style_table={"maxWidth": "100%", "maxHeight": "300px", "overflow": "auto"},
        style_cell={
            "padding": "5px",
            "textAlign": "left",
            "overflow": "hidden",
            "overflow-wrap": "anywhere",
            "max-width": "100%",
            "font-family": "sans-serif",
            "fontSize": 14,
        },
        style_filter={"backgroundColor": "rgb(238, 238, 238, 1.0)"},
        style_filter_conditional=[
            {
                "if": {"column_id": "Value"},
                "textAlign": "left",
            },
        ],
        style_data_conditional=[
            {
                "if": {"row_index": "odd"},
                "backgroundColor": "rgb(248, 248, 248, 1.0)",
            },
            {
                "if": {"column_id": "Name"},
                "backgroundColor": "rgb(240, 240, 240, 1.0)",
                "white-space": "normal",
                "min-width": "8pc",
            },
            {
                "if": {"column_id": "Value"},
                "white-space": "normal",
                "min-width": "8pc",
            },
        ],
        style_header={
            "backgroundColor": "rgb(230, 230, 230, 1.0)",
            "fontWeight": "bold",
            "textAlign": "center",
        },
        # Align the text in Markdown cells
        css=[dict(selector="p", rule="margin: 0; text-align: left")],
    )
    return table


@app.callback(
    Output("heatmap_stat", "children"),
    Input("object-stats", "data"),
    prevent_initial_call=True,
)
def plot_heatmap(object_stats):
    """Plot heatmap"""
    pdf = pd.read_json(io.StringIO(object_stats))
    pdf["date"] = [
        Time(x[4:8] + "-" + x[8:10] + "-" + x[10:12]).datetime
        for x in pdf.index.to_numpy()
    ]
    years = np.unique(pdf["date"].apply(lambda x: x.year)).tolist()

    idx = pd.date_range(
        Time(f"{np.min(years)}-01-01").datetime,
        Time(f"{np.max(years)}-12-31").datetime,
    )
    pdf.index = pd.DatetimeIndex(pdf.date)
    pdf = pdf.drop(columns="date")
    pdf = pdf.reindex(idx, fill_value=0)
    pdf["date"] = pdf.index.to_numpy()

    fig = display_years(pdf, years)

    graph = dcc.Graph(
        figure=fig,
        config={"displayModeBar": False},
        style={
            "width": "100%",
        },
    )

    card = dbc.Card(
        dbc.CardBody(graph, className="m-0 p-1"),
        className="mt-3",
    )
    return card


@app.callback(
    Output("evolution", "children"),
    [
        Input("dropdown_params", "value"),
        Input("switch-cumulative", "value"),
    ],
)
def plot_stat_evolution(param_name, switch):
    """Plot evolution of parameters as a function of time

    TODO: connect the callback to a dropdown button to choose the parameter
    """
    if param_name is None or param_name == "":
        param_name = "basic:sci"

    if param_name != "basic:sci":
        param_name_ = param_name + ",basic:sci"
    else:
        param_name_ = param_name

    pdf = query_and_order_statistics(columns=param_name_)
    pdf = pdf.fillna(0)

    pdf["date"] = [
        Time(x[4:8] + "-" + x[8:10] + "-" + x[10:12]).datetime
        for x in pdf.index.to_numpy()
    ]

    if param_name in dic_names:
        newcol = dic_names[param_name]
    else:
        newcol = param_name.replace("class", "SIMBAD")

    if 1 in switch:
        pdf[param_name] = pdf[param_name].astype(int).cumsum()
        if param_name != "basic:sci":
            pdf["basic:sci"] = pdf["basic:sci"].astype(int).cumsum()
    if 2 in switch:
        pdf[param_name] = (
            pdf[param_name].astype(int) / pdf["basic:sci"].astype(int) * 100
        )

    pdf = pdf.rename(columns={param_name: newcol})

    fig = px.bar(
        pdf,
        y=newcol,
        x="date",
        text=newcol,
    )
    fig.update_traces(
        textposition="outside",
        marker_color="rgb(21, 40, 79)",
    )
    fig.update_layout(
        uniformtext_minsize=8,
        uniformtext_mode="hide",
        showlegend=True,
    )
    fig.update_layout(
        title="",
        margin=dict(t=0, r=0, b=0, l=0),
        showlegend=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    graph = dcc.Graph(
        figure=fig,
        style={
            "width": "100%",
            "height": "35pc",
        },
        config={"displayModeBar": False},
    )
    card = dbc.Card(
        dbc.CardBody(graph),
        className="mt-3",
    )
    return card


def display_year(
    data, year: int = None, month_lines: bool = True, fig=None, row: int = None
):
    """Display one year as heatmap

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
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    month_days = [
        31,
        28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
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
        else 53
        for i in dates_in_year
    ]

    # Careful, first days of January can belong to week 53...
    # so to avoid messing up, we set them to 1, and shift all
    # other weeks by one
    if weeknumber_of_dates[0] == 53:
        weeknumber_of_dates = [i + 1 for i in weeknumber_of_dates]
        weeknumber_of_dates = [
            1 if (j.month == 1 and i == 54) else i
            for i, j in zip(weeknumber_of_dates, dates_in_year)
        ]

    # Gives something like list of strings like ‘2018-01-25’
    # for each date. Used in data trace to make good hovertext.
    # text = [str(i) for i in dates_in_year]
    text = [f"{int(i):,} alerts processed in {j}" for i, j in zip(data, dates_in_year)]

    # Some examples
    colorscale = [[False, "#eeeeee"], [True, "#76cf63"]]
    colorscale = [[False, "#495a7c"], [True, "#F5622E"]]
    colorscale = [[False, "#15284F"], [True, "#3C8DFF"]]
    colorscale = [[False, "#3C8DFF"], [True, "#15284F"]]
    colorscale = [[False, "#4563a0"], [True, "#F5622E"]]
    colorscale = [[False, "#eeeeee"], [True, "#F5622E"]]

    # handle end of year
    data = [
        go.Heatmap(
            x=weeknumber_of_dates,
            y=weekdays_in_year,
            z=data,
            text=text,
            hoverinfo="text",
            xgap=3,  # this
            ygap=3,  # and this is used to make the grid-like apperance
            showscale=False,
            colorscale=colorscale,
            zmax=300000,  # avoid large peaks
            zmid=150000,
            zmin=0,
        ),
    ]

    if month_lines:
        kwargs = dict(
            mode="lines",
            line=dict(
                color="#9e9e9e",
                width=1,
            ),
            hoverinfo="skip",
        )
        for date, dow, wkn in zip(dates_in_year, weekdays_in_year, weeknumber_of_dates):
            if date.day == 1:
                data += [
                    go.Scatter(
                        x=[wkn - 0.5, wkn - 0.5],
                        y=[dow - 0.5, 6.5],
                        **kwargs,
                    ),
                ]
                if dow:
                    data += [
                        go.Scatter(
                            x=[wkn - 0.5, wkn + 0.5],
                            y=[dow - 0.5, dow - 0.5],
                            **kwargs,
                        ),
                        go.Scatter(
                            x=[wkn + 0.5, wkn + 0.5],
                            y=[dow - 0.5, -0.5],
                            **kwargs,
                        ),
                    ]

    layout = go.Layout(
        title="Fink activity chart: number of ZTF alerts processed per night\n",
        height=150,
        yaxis=dict(
            showline=False,
            showgrid=False,
            zeroline=False,
            tickmode="array",
            ticktext=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            tickvals=[0, 1, 2, 3, 4, 5, 6],
            autorange="reversed",
        ),
        xaxis=dict(
            showline=False,
            showgrid=False,
            zeroline=False,
            tickmode="array",
            ticktext=month_names,
            tickvals=month_positions,
        ),
        font={"size": 10, "color": "#9e9e9e"},
        plot_bgcolor=("#fff"),
        margin=dict(t=40),
        showlegend=False,
    )

    if fig is None:
        fig = go.Figure(data=data, layout=layout)
    else:
        fig.add_traces(data, rows=[(row + 1)] * len(data), cols=[1] * len(data))
        fig.update_layout(layout)
        fig.update_xaxes(layout["xaxis"])
        fig.update_yaxes(layout["yaxis"])
        fig.update_layout(
            title={
                "y": 0.995,
                "x": 0.5,
                "xanchor": "center",
                "yanchor": "top",
            },
        )

    return fig


def display_years(pdf, years):
    """Display all heatmaps stacked

    Parameters
    ----------
    pdf: pd.DataFrame
        DataFrame from the REST API
    years: list or tuple of int
        years to display

    Returns
    -------
    fig: plotly figure object
    """
    fig = make_subplots(rows=len(years), cols=1, subplot_titles=years)
    for i, year in enumerate(years):
        # select the data for the year
        data = pdf[pdf["date"].apply(lambda x, year=year: x.year == year)][
            "basic:sci"
        ].to_numpy()

        # Display year
        display_year(data, year=year, fig=fig, row=i, month_lines=True)

        # Fix the height
        fig.update_layout(height=200 * len(years))
    return fig


def make_daily_card(
    pdf,
    color,
    linecolor,
    title,
    description,
    height="12pc",
    scale="lin",
    withpercent=True,
    norm=None,
):
    """ """
    if withpercent and norm != 0:
        text = [f"{int(i) / norm * 100:.0f}%" for i in pdf.to_numpy()[0]]
    else:
        text = pdf.to_numpy()[0]

    pdf = pdf.replace("", 0)
    pdf = pdf.fillna(0).astype(int)
    fig = go.Figure(
        [
            go.Bar(x=pdf.columns, y=pdf.to_numpy()[0], text=text, textposition="auto"),
        ],
    )

    fig.update_layout(
        title="",
        margin=dict(t=0, r=0, b=0, l=0),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    fig.update_traces(
        marker_color=color,
        marker_line_color=linecolor,
        marker_line_width=1.5,
        opacity=0.6,
    )

    if scale == "log":
        fig.update_yaxes(type="log")

    graph = dcc.Graph(
        figure=fig,
        style={
            "width": "100%",
            "height": height,
        },
        config={"displayModeBar": False},
    )
    myid = "{}_stat".format(title.split(" ")[0])
    card = dbc.Card(
        [
            dbc.CardBody(
                [
                    html.H6(
                        [
                            title,
                            html.I(
                                className="fa fa-question-circle fa-1x",
                                style={
                                    "border": "0px black solid",
                                    "background": "rgba(255, 255, 255, 0.0)",
                                    "color": "#15284F90",
                                    "float": "right",
                                },
                                id=myid,
                            ),
                        ],
                        className="card-subtitle",
                    ),
                    graph,
                ],
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
    Output("hist_sci_raw", "children"),
    Input("dropdown_days", "value"),
)
def hist_sci_raw(dropdown_days):
    """Make an histogram"""
    pdf = query_and_order_statistics(columns="basic:raw,basic:sci")

    if dropdown_days is None or dropdown_days == "":
        dropdown_days = pdf.index[-1]
    pdf = pdf[pdf.index == dropdown_days]

    pdf = pdf.rename(columns={"basic:raw": "Received", "basic:sci": "Processed"})
    norm = int(pdf["Received"].to_numpy()[0])

    description = """
    Received alerts go through a series of quality cuts defined by Fink.
    Only alerts passing quality cuts are then further processed by the science pipelines.
    """

    card = make_daily_card(
        pdf[["Received", "Processed"]],
        color="rgb(158,202,225)",
        linecolor="rgb(8,48,107)",
        title="Quality cuts",
        description=description,
        norm=norm,
    )

    return card


@app.callback(
    Output("hist_catalogued", "children"),
    Input("dropdown_days", "value"),
)
def hist_catalogued(dropdown_days):
    """Make an histogram"""
    pdf = query_and_order_statistics(
        columns="class:Solar System MPC,class:simbad_tot,basic:sci"
    )
    pdf = pdf.fillna(0)

    pdf = pdf.rename(
        columns={"class:Solar System MPC": "MPC", "class:simbad_tot": "SIMBAD"}
    )

    if dropdown_days is None or dropdown_days == "":
        dropdown_days = pdf.index[-1]
    pdf = pdf[pdf.index == dropdown_days]

    norm = int(pdf["basic:sci"].to_numpy()[0])
    pdf = pdf.drop(columns=["basic:sci"])

    description = """
    All alerts passing quality cuts are matched against the SIMBAD database and the Minor Planet Center catalog.
    Percentages are given with respect to the number of processed alerts (i.e. the ones that pass quality cuts).
    """

    card = make_daily_card(
        pdf,
        color="rgb(21, 40, 79)",
        linecolor="rgb(4, 14, 33)",
        title="Crossmatch to",
        description=description,
        norm=norm,
    )

    return card


@app.callback(
    Output("hist_classified", "children"),
    Input("dropdown_days", "value"),
)
def hist_classified(dropdown_days):
    """Make an histogram"""
    pdf = query_and_order_statistics(columns="basic:sci,class:Unknown")
    pdf = pdf.fillna(0)

    pdf["Classified"] = pdf["basic:sci"].astype(int) - pdf["class:Unknown"].astype(int)
    pdf = pdf.rename(columns={"class:Unknown": "Unclassified"})

    if dropdown_days is None or dropdown_days == "":
        dropdown_days = pdf.index[-1]
    pdf = pdf[pdf.index == dropdown_days]

    norm = int(pdf["basic:sci"].to_numpy()[0])
    pdf = pdf.drop(columns=["basic:sci"])

    description = """
    Each alert goes through the Fink science modules, and eventually gets a classification label, either from machine learning based modules or from crossmatch.
    Percentages are given with respect to the number of processed alerts (i.e. the ones that pass quality cuts).
    """

    card = make_daily_card(
        pdf,
        color="rgb(245, 98, 46)",
        linecolor="rgb(135, 86, 69)",
        title="Classification",
        description=description,
        norm=norm,
    )

    return card


@app.callback(
    Output("hist_candidates", "children"),
    Input("dropdown_days", "value"),
)
def hist_candidates(dropdown_days):
    """Make an histogram"""
    pdf = query_and_order_statistics(
        columns="class:Solar System candidate,class:SN candidate,class:Early SN Ia candidate,class:Kilonova candidate"
    )

    pdf = pdf.rename(
        columns={
            "class:Solar System candidate": "SSO",
            "class:SN candidate": "SNe",
            "class:Early SN Ia candidate": "SN Ia",
            "class:Kilonova candidate": "Kilonova",
        },
    )

    if dropdown_days is None or dropdown_days == "":
        dropdown_days = pdf.index[-1]
    pdf = pdf[pdf.index == dropdown_days]

    description = """
    Number of alerts for a subset of classes: early type Ia supernova (SN Ia), supernovae or core-collapse (SNe), Kilonova, or Solar System candidates (SSO).
    """

    card = make_daily_card(
        pdf,
        color="rgb(213, 213, 211)",
        linecolor="rgb(138, 138, 132)",
        title="Selected Fink candidates",
        description=description,
        withpercent=False,
    )

    return card


@app.callback(
    Output("daily_classification", "children"),
    Input("dropdown_days", "value"),
)
def fields_exposures(dropdown_days):
    """Make an histogram"""
    pdf = query_and_order_statistics(columns="*")

    to_drop = [i for i in pdf.columns if i.startswith("basic:")]
    pdf = pdf.drop(columns=to_drop)

    pdf = pdf.rename(columns={i: i.split(":")[1] for i in pdf.columns})

    if dropdown_days is None or dropdown_days == "":
        dropdown_days = pdf.index[-1]
    pdf = pdf[pdf.index == dropdown_days]

    description = "Histogram of Fink labels for all processed alerts during the night. For readability the plot displays only a few labels on the x-axis. Select a region to zoom in and discover more labels (alphabetical sort)."

    card = make_daily_card(
        pdf,
        color="rgb(21, 40, 79)",
        linecolor="rgb(4, 14, 33)",
        title="Individual Fink classifications",
        description=description,
        height="20pc",
        scale="log",
        withpercent=False,
    )

    return card


@app.callback(
    Output("coordinates", "children"),
    [
        Input("object-data", "data"),
        Input("coordinates_chips", "value"),
    ],
    prevent_initial_call=True,
)
def draw_alert_astrometry(object_data, kind) -> dict:
    """Draw SSO object astrometry

    This is the difference position wrt ephemerides from the miriade IMCCE service.

    Returns
    -------
    figure: dict
    """
    pdf = pd.read_json(io.StringIO(object_data))

    mean_ra = np.mean(pdf["i:ra"])
    mean_dec = np.mean(pdf["i:dec"])

    deltaRAcosDEC = (pdf["i:ra"] - mean_ra) * np.cos(np.radians(pdf["i:dec"])) * 3600
    deltaDEC = (pdf["i:dec"] - mean_dec) * 3600

    hovertemplate = r"""
    <b>%{yaxis.title.text}</b>: %{y:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x:.2f}<br>
    <b>Observation date</b>: %{customdata}
    <extra></extra>
    """
    diff_g = {
        "x": deltaRAcosDEC[pdf["i:fid"] == 1],
        "y": deltaDEC[pdf["i:fid"] == 1],
        "mode": "markers",
        "name": "g band",
        "customdata": Time(pdf["i:jd"][pdf["i:fid"] == 1], format="jd").iso,
        "hovertemplate": hovertemplate,
        "marker": {"size": 6, "color": COLORS_ZTF[0], "symbol": "o"},
    }

    diff_r = {
        "x": deltaRAcosDEC[pdf["i:fid"] == 2],
        "y": deltaDEC[pdf["i:fid"] == 2],
        "mode": "markers",
        "name": "r band",
        "customdata": Time(pdf["i:jd"][pdf["i:fid"] == 2], format="jd").iso,
        "hovertemplate": hovertemplate,
        "marker": {"size": 6, "color": COLORS_ZTF[1], "symbol": "o"},
    }

    figure = {
        "data": [
            diff_g,
            diff_r,
        ],
        "layout": layout_sso_astrometry,
    }
    # Force equal aspect ratio
    figure["layout"]["yaxis"]["scaleanchor"] = "x"
    # figure['layout']['yaxis']['scaleratio'] = 1

    graph = dcc.Graph(
        figure=figure,
        style={
            "width": "100%",
            "height": "20pc",
            # Prevent occupying more than 60% of the screen height
            "max-height": "60vh",
            # Force equal aspect
            # 'display':'block',
            # 'aspect-ratio': '1',
            # 'margin': '1px'
        },
        config={"displayModeBar": False},
        responsive=True,
    )
    card1 = dmc.Paper(
        graph, radius="sm", p="xs", shadow="sm", withBorder=True, className="mb-1"
    )

    coord = SkyCoord(mean_ra, mean_dec, unit="deg")

    # degrees
    if kind == "GAL":
        coords_deg = coord.galactic.to_string("decimal", precision=6)
    else:
        coords_deg = coord.to_string("decimal", precision=6)

    # hmsdms
    if kind == "GAL":
        # Galactic coordinates are in DMS only
        coords_hms = coord.galactic.to_string("dms", precision=2)
        coords_hms2 = coord.galactic.to_string("dms", precision=2, sep=" ")
    else:
        coords_hms = coord.to_string("hmsdms", precision=2)
        coords_hms2 = coord.to_string("hmsdms", precision=2, sep=" ")

    card_coords = html.Div(
        [
            dmc.Group(
                [
                    html.Code(coords_deg, id="alert_coords_deg"),
                    dcc.Clipboard(
                        target_id="alert_coords_deg",
                        title="Copy to clipboard",
                        style={"color": "gray"},
                    ),
                ],
                justify="space-between",
                style={"width": "100%"},
            ),
            dmc.Group(
                [
                    html.Code(coords_hms, id="alert_coords_hms"),
                    dcc.Clipboard(
                        target_id="alert_coords_hms",
                        title="Copy to clipboard",
                        style={"color": "gray"},
                    ),
                ],
                justify="space-between",
                style={"width": "100%"},
            ),
            dmc.Group(
                [
                    html.Code(coords_hms2, id="alert_coords_hms2"),
                    dcc.Clipboard(
                        target_id="alert_coords_hms2",
                        title="Copy to clipboard",
                        style={"color": "gray"},
                    ),
                ],
                justify="space-between",
                style={"width": "100%"},
            ),
        ],
        className="mx-auto",
        style={"max-width": "17em"},
    )

    return html.Div([card1, card_coords])

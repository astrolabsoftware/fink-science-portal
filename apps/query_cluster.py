# Copyright 2022-2023 AstroLab Software
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
import textwrap
from datetime import date, datetime, timedelta

import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import numpy as np
import pandas as pd
import requests
import yaml
from dash import Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify
from fink_utils.xmatch.simbad import get_simbad_labels

from app import APIURL, app
from apps.mining.utils import (
    estimate_size_gb_elasticc,
    estimate_size_gb_ztf,
    submit_spark_job,
    upload_file_hdfs,
)
from apps.utils import request_api

simbad_types = get_simbad_labels("old_and_new")
simbad_types = sorted(simbad_types, key=lambda s: s.lower())

tns_types = pd.read_csv("assets/tns_types.csv", header=None)[0].to_numpy()
tns_types = sorted(tns_types, key=lambda s: s.lower())

elasticc_v1_classes = pd.read_csv("assets/elasticc_v1_classes.csv")
elasticc_v1_dates = pd.read_csv("assets/elasticc_v1_dates.csv")
elasticc_v1_dates["date"] = elasticc_v1_dates["date"].astype("str")

elasticc_v2_classes = pd.read_csv("assets/elasticc_v2_classes.csv")
elasticc_v2_dates = pd.read_csv("assets/elasticc_v2_dates.csv")
elasticc_v2_dates["date"] = elasticc_v2_dates["date"].astype("str")

elasticc_v2p1_classes = pd.read_csv("assets/elasticc_v2p1_classes.csv")
elasticc_v2p1_dates = pd.read_csv("assets/elasticc_v2p1_dates.csv")
elasticc_v2p1_dates["date"] = elasticc_v2p1_dates["date"].astype("str")

coeffs_per_class = pd.read_parquet("assets/fclass_2022_060708_coeffs.parquet")


@app.callback(
    Output("timeline_data_transfer", "children"),
    [
        Input("trans_datasource", "value"),
        Input("date-range-picker", "value"),
        Input("class_select", "value"),
        Input("extra_cond", "value"),
        Input("trans_content", "value"),
    ],
)
def timeline_data_transfer(
    trans_datasource, date_range_picker, class_select, extra_cond, trans_content
):
    """ """
    steps = [trans_datasource, date_range_picker, trans_content]

    active_ = np.where(np.array([i is not None for i in steps]))[0]
    tmp = len(active_)
    nsteps = 0 if tmp < 0 else tmp

    if date_range_picker is None:
        date_range_picker = [None, None]

    timeline = dmc.Timeline(
        active=nsteps,
        bulletSize=15,
        lineWidth=2,
        children=[
            dmc.TimelineItem(
                title="Select data source",
                children=[
                    dmc.Text(
                        [
                            f"Source: {trans_datasource}",
                        ],
                        c="dimmed",
                        size="sm",
                    ),
                ],
            ),
            dmc.TimelineItem(
                title="Filter alerts",
                children=[
                    dmc.Text(
                        [
                            "Dates: {} - {}".format(*date_range_picker),
                        ],
                        c="dimmed",
                        size="sm",
                    ),
                    dmc.Text(
                        [
                            f"Classe(s): {class_select}",
                        ],
                        c="dimmed",
                        size="sm",
                    ),
                    dmc.Text(
                        [
                            f"Conditions: {extra_cond}",
                        ],
                        c="dimmed",
                        size="sm",
                    ),
                ],
            ),
            dmc.TimelineItem(
                title="Select content",
                lineVariant="dashed",
                children=[
                    dmc.Text(
                        [
                            f"Content: {trans_content}",
                        ],
                        c="dimmed",
                        size="sm",
                    ),
                ],
            ),
            dmc.TimelineItem(
                [
                    dmc.Text(
                        [
                            "Trigger your job!",
                        ],
                        c="dimmed",
                        size="sm",
                    ),
                ],
                title="Submit",
            ),
        ],
    )

    return timeline


def filter_tab():
    """Section containing filtering options"""
    options = html.Div(
        [
            dmc.DatePicker(
                type="range",
                id="date-range-picker",
                label="Date Range",
                description="Pick up start and stop dates (included).",
                hideOutsideDates=True,
                numberOfColumns=2,
                allowSingleDateInRange=True,
                required=True,
            ),
            dmc.Space(h=10),
            dmc.MultiSelect(
                label="Alert class",
                description="Select all classes you like! Default is all classes.",
                placeholder="start typing...",
                id="class_select",
                searchable=True,
            ),
            dmc.Space(h=10),
            dmc.Textarea(
                id="extra_cond",
                label="Extra conditions",
                autosize=True,
                minRows=2,
            ),
        ],
    )
    tab = html.Div(
        [
            dmc.Space(h=10),
            dmc.Divider(variant="solid", label="Filters"),
            options,
        ],
        id="filter_tab",
        style={"display": "none"},
    )
    return tab


@app.callback(
    [
        Output("filter_tab", "style"),
        Output("date-range-picker", "minDate"),
        Output("date-range-picker", "maxDate"),
        Output("class_select", "data"),
        Output("extra_cond", "description"),
        Output("extra_cond", "placeholder"),
        Output("trans_content", "children"),
    ],
    [
        Input("trans_datasource", "value"),
    ],
    prevent_initial_call=True,
)
def display_filter_tab(trans_datasource):
    if trans_datasource is None:
        PreventUpdate  # noqa: B018
    else:
        if trans_datasource == "ZTF":
            minDate = date(2019, 11, 1)
            maxDate = date.today()
            data_class_select = [
                {"label": "All classes", "value": "allclasses"},
                {"label": "Unknown", "value": "Unknown"},
                {
                    "label": "(Fink) Early Supernova Ia candidates",
                    "value": "Early SN Ia candidate",
                },
                {"label": "(Fink) Supernova candidates", "value": "SN candidate"},
                {"label": "(Fink) Kilonova candidates", "value": "Kilonova candidate"},
                {
                    "label": "(Fink) Microlensing candidates",
                    "value": "Microlensing candidate",
                },
                {"label": "(Fink) Solar System (MPC)", "value": "Solar System MPC"},
                {
                    "label": "(Fink) Solar System (candidates)",
                    "value": "Solar System candidate",
                },
                {
                    "label": "(Fink) Tracklet (space debris & satellite glints)",
                    "value": "Tracklet",
                },
                {"label": "(Fink) Ambiguous", "value": "Ambiguous"},
                *[
                    {"label": "(TNS) " + simtype, "value": "(TNS) " + simtype}
                    for simtype in tns_types
                ],
                *[
                    {"label": "(SIMBAD) " + simtype, "value": "(SIMBAD) " + simtype}
                    for simtype in simbad_types
                ],
            ]
            description = [
                "One condition per line (SQL syntax), ending with semi-colon. See ",
                dmc.Anchor(
                    "here", href=f"{APIURL}/api/v1/columns", size="xs", target="_blank"
                ),
                " (and also ",
                dmc.Anchor(
                    "here",
                    href="https://fink-broker.readthedocs.io/en/latest/science/added_values/",
                    size="xs",
                    target="_blank",
                ),
                ") for fields description and ",
                dmc.Anchor(
                    "here",
                    href="https://fink-broker.readthedocs.io/en/latest/services/data_transfer/",
                    size="xs",
                    target="_blank",
                ),
                " for examples.",
            ]
            placeholder = "e.g. candidate.magpsf > 19.5;"
            labels = [
                "Lightcurve (~1.4 KB/alert)",
                "Cutouts (~41 KB/alert)",
                "Full packet (~55 KB/alert)",
            ]
            values = ["Lightcurve", "Cutouts", "Full packet"]
            data_content = dmc.Group(
                [
                    dmc.Radio(label=label, value=k, size="sm", color="orange")
                    for label, k in zip(labels, values)
                ]
            )
        elif trans_datasource == "ELASTiCC (v1)":
            minDate = date(2023, 11, 27)
            maxDate = date(2026, 12, 5)
            data_class_select = [
                {"label": "All classes", "value": "allclasses"},
                *[
                    {"label": str(simtype), "value": str(simtype)}
                    for simtype in sorted(elasticc_v1_classes["classId"].to_numpy())
                ],
            ]
            description = [
                "One condition per line (SQL syntax), ending with semi-colon. See ",
                dmc.Anchor(
                    "here",
                    href="https://portal.nersc.gov/cfs/lsst/DESC_TD_PUBLIC/ELASTICC/#alertschema",
                    size="xs",
                    target="_blank",
                ),
                " for fields description and ",
                dmc.Anchor(
                    "here",
                    href="https://fink-broker.readthedocs.io/en/latest/services/data_transfer/",
                    size="xs",
                    target="_blank",
                ),
                " for examples.",
            ]
            placeholder = "e.g. diaSource.psFlux > 0.0;"
            labels = ["Full packet (~1.4 KB/alert)"]
            values = ["Full packet"]
            data_content = dmc.Group(
                [
                    dmc.Radio(label=label, value=k, size="sm", color="orange")
                    for label, k in zip(labels, values)
                ]
            )
        elif trans_datasource == "ELASTiCC (v2.0)":
            minDate = date(2023, 11, 27)
            maxDate = date(2026, 12, 5)
            data_class_select = [
                {"label": "All classes", "value": "allclasses"},
                *[
                    {"label": str(simtype), "value": str(simtype)}
                    for simtype in sorted(elasticc_v2_classes["classId"].to_numpy())
                ],
            ]
            description = [
                "One condition per line (SQL syntax), ending with semi-colon. See ",
                dmc.Anchor(
                    "here",
                    href="https://portal.nersc.gov/cfs/lsst/DESC_TD_PUBLIC/ELASTICC/#alertschema",
                    size="xs",
                    target="_blank",
                ),
                " for fields description and ",
                dmc.Anchor(
                    "here",
                    href="https://fink-broker.readthedocs.io/en/latest/services/data_transfer/",
                    size="xs",
                    target="_blank",
                ),
                " for examples.",
            ]
            placeholder = "e.g. diaSource.psFlux > 0.0;"
            labels = ["Full packet (~1.4 KB/alert)"]
            values = ["Full packet"]
            data_content = dmc.Group(
                [
                    dmc.Radio(label=label, value=k, size="sm", color="orange")
                    for label, k in zip(labels, values)
                ]
            )
        elif trans_datasource == "ELASTiCC (v2.1)":
            minDate = date(2023, 11, 27)
            maxDate = date(2026, 12, 5)
            data_class_select = [
                {"label": "All classes", "value": "allclasses"},
                *[
                    {"label": str(simtype), "value": str(simtype)}
                    for simtype in sorted(elasticc_v2p1_classes["classId"].to_numpy())
                ],
            ]
            description = [
                "One condition per line (SQL syntax), ending with semi-colon. See ",
                dmc.Anchor(
                    "here",
                    href="https://portal.nersc.gov/cfs/lsst/DESC_TD_PUBLIC/ELASTICC/#alertschema",
                    size="xs",
                    target="_blank",
                ),
                " for fields description and ",
                dmc.Anchor(
                    "here",
                    href="https://fink-broker.readthedocs.io/en/latest/services/data_transfer/",
                    size="xs",
                    target="_blank",
                ),
                " for examples.",
            ]
            placeholder = "e.g. diaSource.psFlux > 0.0;"
            labels = ["Full packet (~1.4 KB/alert)"]
            values = ["Full packet"]
            data_content = dmc.Group(
                [
                    dmc.Radio(label=label, value=k, size="sm", color="orange")
                    for label, k in zip(labels, values)
                ]
            )

        return (
            {},
            minDate,
            maxDate,
            data_class_select,
            description,
            placeholder,
            data_content,
        )


def content_tab():
    """Section containing filtering options"""
    tab = html.Div(
        [
            dmc.Space(h=10),
            dmc.Divider(variant="solid", label="Alert content"),
            dmc.RadioGroup(
                children=[],
                id="trans_content",
                label="Choose the content you want to retrieve",
            ),
        ],
        style={"display": "none"},
        id="content_tab",
    )
    return tab


@app.callback(
    Output("content_tab", "style"),
    [
        Input("date-range-picker", "value"),
    ],
    prevent_initial_call=True,
)
def update_content_tab(date_range_picker):
    if date_range_picker is None:
        PreventUpdate  # noqa: B018
    else:
        return {}


def estimate_alert_number_ztf(date_range_picker, class_select):
    """Callback to estimate the number of alerts to be transfered

    This can be improved by using the REST API directly to get number of
    alerts per class.
    """
    dic = {"basic:sci": 0}
    dstart = date(*[int(i) for i in date_range_picker[0].split("-")])
    dstop = date(*[int(i) for i in date_range_picker[1].split("-")])
    delta = dstop - dstart

    columns = "basic:sci"
    column_names = []
    if (class_select is not None) and (class_select != []):
        if "allclasses" not in class_select:
            for elem in class_select:
                if elem.startswith("(TNS)"):
                    continue

                # name correspondance
                if elem.startswith("(SIMBAD)"):
                    elem = elem.replace("(SIMBAD) ", "class:")
                else:
                    # prepend class:
                    elem = "class:" + elem
                columns += f",{elem}"
                column_names.append(elem)

    # Initialise count
    for column_name in column_names:
        dic[column_name] = 0

    for i in range(delta.days + 1):
        tmp = (dstart + timedelta(i)).strftime("%Y%m%d")
        r = request_api(
            "/api/v1/statistics",
            json={
                "date": tmp,
                "columns": columns,
                "output-format": "json",
            },
            output="json",
        )
        if r != []:
            payload = r[0]
            dic["basic:sci"] += int(payload["basic:sci"])
            for column_name in column_names:
                if column_name in payload.keys():
                    dic[column_name] += int(payload[column_name])
                else:
                    dic[column_name] += 0

    # Add TNS estimation
    if (class_select is not None) and (class_select != []):
        if "allclasses" not in class_select:
            for elem in class_select:
                elem = int(elem)  # fink-science-portal#650
                # name correspondance
                if elem.startswith("(TNS)"):
                    filt = coeffs_per_class["fclass"] == elem

                    if np.sum(filt) == 0:
                        # Nothing found. This could be because we have
                        # no alerts from this class, or because it has not
                        # yet entered the statistics. To be conservative,
                        # we do not apply any coefficients.
                        dic[elem] = 0
                    else:
                        dic[elem.replace("(TNS) ", "class:")] = int(
                            dic["basic:sci"]
                            * coeffs_per_class[filt]["coeff"].to_numpy()[0]
                        )
            count = np.sum([i[1] for i in dic.items() if "class:" in i[0]])
        else:
            # allclasses mean all alerts
            count = dic["basic:sci"]
    else:
        count = dic["basic:sci"]

    return dic["basic:sci"], count


def estimate_alert_number_elasticc(
    date_range_picker, class_select, elasticc_dates, elasticc_classes
):
    """Callback to estimate the number of alerts to be transfered"""
    dic = {"basic:sci": 0}
    dstart = date(*[int(i) for i in date_range_picker[0].split("-")])
    dstop = date(*[int(i) for i in date_range_picker[1].split("-")])
    delta = dstop - dstart

    # count all raw number of alerts
    for i in range(delta.days + 1):
        tmp = (dstart + timedelta(i)).strftime("%Y%m%d")
        filt = elasticc_dates["date"] == tmp
        if np.sum(filt) > 0:
            dic["basic:sci"] += int(elasticc_dates[filt]["count"].to_numpy()[0])

    # Add class estimation
    if (class_select is not None) and (class_select != []):
        if "allclasses" not in class_select:
            for elem in class_select:
                # name correspondance
                filt = elasticc_classes["classId"] == elem

                if np.sum(filt) == 0:
                    # Nothing found. This could be because we have
                    # no alerts from this class, or because it has not
                    # yet entered the statistics. To be conservative,
                    # we do not apply any coefficients.
                    dic[elem] = 0
                else:
                    coeff = (
                        elasticc_classes[filt]["count"].to_numpy()[0]
                        / elasticc_classes["count"].sum()
                    )
                    dic["class:" + str(elem)] = int(dic["basic:sci"] * coeff)
            count = np.sum([i[1] for i in dic.items() if "class:" in i[0]])
        else:
            # allclasses mean all alerts
            count = dic["basic:sci"]
    else:
        count = dic["basic:sci"]

    return dic["basic:sci"], count


@app.callback(
    Output("summary_tab", "children"),
    [
        Input("trans_content", "value"),
        Input("trans_datasource", "value"),
        Input("date-range-picker", "value"),
        Input("class_select", "value"),
        Input("extra_cond", "value"),
    ],
    prevent_initial_call=True,
)
def summary_tab(
    trans_content, trans_datasource, date_range_picker, class_select, extra_cond
):
    """Section containing summary"""
    if trans_content is None:
        html.Div(style={"display": "none"})
    elif date_range_picker is None:
        PreventUpdate  # noqa: B018
    else:
        msg = """
        You are about to submit a job on the Fink Apache Spark & Kafka clusters.
        Review your parameters, and take into account the estimated number of
        alerts before hitting submission! Note that the estimation takes into account
        the days requested and the classes, but not the extra conditions (which could reduce the
        number of alerts).
        """
        if trans_datasource == "ZTF":
            total, count = estimate_alert_number_ztf(date_range_picker, class_select)
            sizeGb = estimate_size_gb_ztf(trans_content)
        elif trans_datasource == "ELASTiCC (v1)":
            total, count = estimate_alert_number_elasticc(
                date_range_picker, class_select, elasticc_v1_dates, elasticc_v1_classes
            )
            sizeGb = estimate_size_gb_elasticc(trans_content)
        elif trans_datasource == "ELASTiCC (v2.0)":
            total, count = estimate_alert_number_elasticc(
                date_range_picker, class_select, elasticc_v2_dates, elasticc_v2_classes
            )
            sizeGb = estimate_size_gb_elasticc(trans_content)
        elif trans_datasource == "ELASTiCC (v2.1)":
            total, count = estimate_alert_number_elasticc(
                date_range_picker,
                class_select,
                elasticc_v2p1_dates,
                elasticc_v2p1_classes,
            )
            sizeGb = estimate_size_gb_elasticc(trans_content)

        if count == 0:
            msg_title = "No alerts found. Try to update your criteria."
        else:
            msg_title = (
                f"Estimated number of alerts: {int(count):,} ({count / total * 100:.2f}%) or {count * sizeGb:.2f} GB",
            )

        if count == 0:
            icon = "codicon:chrome-close"
            color = "gray"
        elif count < 250000:
            icon = "codicon:check"
            color = "green"
        elif count > 10000000:
            icon = "emojione-v1:face-screaming-in-fear"
            color = "red"
        else:
            icon = "codicon:flame"
            color = "orange"
        block = dmc.Blockquote(
            msg_title,
            cite=msg,
            icon=[DashIconify(icon=icon, width=30)],
            color=color,
        )
        tab = html.Div(
            [
                dmc.Space(h=10),
                dmc.Divider(variant="solid", label="Submit"),
                dmc.Space(h=10),
                block,
            ],
        )
        return tab


def make_buttons():
    buttons = dmc.Group(
        [
            dmc.Button(
                "Submit job",
                id="submit_datatransfer",
                variant="outline",
                color="indigo",
                leftSection=DashIconify(
                    icon="fluent:database-plug-connected-20-filled"
                ),
            ),
        ],
    )
    return buttons


@app.callback(
    Output("transfer_buttons", "style"),
    [
        Input("trans_content", "value"),
    ],
    prevent_initial_call=True,
)
def update_make_buttons(trans_content):
    if trans_content is None:
        PreventUpdate  # noqa: B018
    else:
        return {}


@app.callback(
    Output("batch_log", "children"),
    [
        Input("update_batch_log", "n_clicks"),
        Input("batch_id", "children"),
    ],
)
def update_log(n_clicks, batchid):
    if n_clicks:
        if batchid != "":
            response = requests.get(
                f"http://134.158.75.222:21111/batches/{batchid}/log"
            )

            if "log" in response.json():
                bad_words = ["Error", "Traceback"]
                failure_log = [
                    row
                    for row in response.json()["log"]
                    if np.any([i in row for i in bad_words])
                ]
                if len(failure_log) > 0:
                    initial_traceback = failure_log[0]
                    log = response.json()["log"]
                    index = log.index(initial_traceback)
                    failure_msg = [
                        f"Batch ID: {batchid}",
                        "Failed. Please, contact contact@fink-broker.org with your batch ID and the message below.",
                        "------------- Traceback -------------",
                        *log[index:],
                    ]
                    output = html.Div(
                        "\n".join(failure_msg), style={"whiteSpace": "pre-wrap"}
                    )
                    return output
                # catch and return tailored error msg if fail (with batchid and contact@fink-broker.org)
                livy_log = [row for row in response.json()["log"] if "-Livy-" in row]
                livy_log = [f"Batch ID: {batchid}", "Starting..."] + livy_log
                output = html.Div("\n".join(livy_log), style={"whiteSpace": "pre-wrap"})
            elif "msg" in response.json():
                output = html.Div(response.text)
            return output
        else:
            return html.Div("batch ID is empty")


def make_final_helper():
    """ """
    accordion = dmc.Accordion(
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl("Monitor your job"),
                    dmc.AccordionPanel(
                        [
                            dmc.Button(
                                "Update log", id="update_batch_log", color="orange"
                            ),
                            html.Div(id="batch_log"),
                        ],
                    ),
                ],
                value="monitor",
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl("Get your data"),
                    dmc.AccordionPanel(
                        [
                            html.Div(id="final_accordion_1"),
                        ],
                    ),
                ],
                value="get_data",
            ),
        ],
        id="final_accordion",
        style={"display": "none"},
    )
    return accordion


@app.callback(
    Output("final_accordion_1", "children"),
    [
        Input("topic_name", "children"),
    ],
)
def update_final_accordion1(topic_name):
    """ """
    if topic_name != "":
        if "elasticc" in topic_name:
            partition = "classId"
        else:
            partition = "finkclass"

        msg = """
        Once data has started to flow in the topic, you can easily download your alerts using the [fink-client](https://github.com/astrolabsoftware/fink-client). Install the latest version and
        use e.g.
        """
        code_block = f"""
        fink_datatransfer \\
            -topic {topic_name} \\
            -outdir {topic_name} \\
            -partitionby {partition} \\
            --verbose
        """
        out = html.Div(
            [
                dcc.Markdown(msg, link_target="_blank"),
                dmc.CodeHighlight(code=code_block, language="bash"),
            ],
        )

        return out


@app.callback(
    Output("submit_datatransfer", "disabled"),
    Output("streaming_info", "children"),
    Output("batch_id", "children"),
    Output("topic_name", "children"),
    Output("final_accordion", "style"),
    [
        Input("submit_datatransfer", "n_clicks"),
    ],
    [
        State("trans_content", "value"),
        State("trans_datasource", "value"),
        State("date-range-picker", "value"),
        State("class_select", "value"),
        State("extra_cond", "value"),
    ],
    prevent_initial_call=True,
)
def submit_job(
    n_clicks,
    trans_content,
    trans_datasource,
    date_range_picker,
    class_select,
    extra_cond,
):
    """Submit a job to the Apache Spark cluster via Livy"""
    if n_clicks:
        # define unique topic name
        d = datetime.utcnow()

        if trans_datasource == "ZTF":
            topic_name = f"ftransfer_ztf_{d.date().isoformat()}_{d.microsecond}"
            fn = "assets/spark_ztf_transfer.py"
            basepath = "/user/julien.peloton/archive/science"
        elif trans_datasource == "ELASTiCC (v1)":
            topic_name = f"ftransfer_elasticc_v1_{d.date().isoformat()}_{d.microsecond}"
            fn = "assets/spark_elasticc_transfer.py"
            basepath = "/user/julien.peloton/elasticc_curated_truth_int"
        elif trans_datasource == "ELASTiCC (v2.0)":
            topic_name = f"ftransfer_elasticc_v2_{d.date().isoformat()}_{d.microsecond}"
            fn = "assets/spark_elasticc_transfer.py"
            basepath = "/user/julien.peloton/elasticc-2023-training_v2"
        elif trans_datasource == "ELASTiCC (v2.1)":
            topic_name = (
                f"ftransfer_elasticc_v2p1_{d.date().isoformat()}_{d.microsecond}"
            )
            fn = "assets/spark_elasticc_transfer.py"
            basepath = "/user/julien.peloton/elasticc_training_v2p1_partitioned"
        filename = f"stream_{topic_name}.py"

        with open(fn) as f:
            data = f.read()
        code = textwrap.dedent(data)

        input_args = yaml.load(open("config_datatransfer.yml"), yaml.Loader)
        status_code, hdfs_log = upload_file_hdfs(
            code,
            input_args["WEBHDFS"],
            input_args["NAMENODE"],
            input_args["USER"],
            filename,
        )

        if status_code != 201:
            text = f"[Status code {status_code}] Unable to upload resources on HDFS, with error: {hdfs_log}. Contact an administrator at contact@fink-broker.org."
            return True, text, "", "", {"display": "none"}

        # get the job args
        job_args = [
            f"-startDate={date_range_picker[0]}",
            f"-stopDate={date_range_picker[1]}",
            f"-content={trans_content}",
            f"-basePath={basepath}",
            f"-topic_name={topic_name}",
            "-kafka_bootstrap_servers={}".format(input_args["KAFKA_BOOTSTRAP_SERVERS"]),
            "-kafka_sasl_username={}".format(input_args["KAFKA_SASL_USERNAME"]),
            "-kafka_sasl_password={}".format(input_args["KAFKA_SASL_PASSWORD"]),
            "-path_to_tns=/spark_mongo_tmp/julien.peloton/tns.parquet",
        ]
        if class_select is not None:
            [job_args.append(f"-fclass={elem}") for elem in class_select]

        if extra_cond is not None:
            extra_cond_list = extra_cond.split(";")
            [job_args.append(f"-extraCond={elem.strip()}") for elem in extra_cond_list]

        # submit the job
        filepath = "hdfs:///user/{}/{}".format(input_args["USER"], filename)
        batchid, status_code, spark_log = submit_spark_job(
            input_args["LIVYHOST"],
            filepath,
            input_args["SPARKCONF"],
            job_args,
        )

        if status_code != 201:
            text = f"[Batch ID {batchid}][Status code {status_code}] Unable to submit job on the Spark cluster, with error: {spark_log}. Contact an administrator at contact@fink-broker.org."
            return True, text, "", "", {"display": "none"}

        text = dmc.Blockquote(
            f"Your topic name is: {topic_name}",
            icon=[DashIconify(icon="system-uicons:pull-down", width=30)],
            color="green",
        )
        if n_clicks:
            return True, text, batchid, topic_name, {}
        else:
            return False, text, batchid, topic_name, {}
    else:
        return False, "", "", "", {"display": "none"}


def query_builder():
    """Build iteratively the query based on user inputs."""
    tab = html.Div(
        [
            dmc.Divider(variant="solid", label="Data Source"),
            dmc.RadioGroup(
                children=dmc.Group(
                    [
                        dmc.Radio(k, value=k, size="sm", color="orange")
                        for k in [
                            "ZTF",
                            "ELASTiCC (v1)",
                            "ELASTiCC (v2.0)",
                            "ELASTiCC (v2.1)",
                        ]
                    ]
                ),
                id="trans_datasource",
                value=None,
                label="Choose the type of alerts you want to retrieve",
            ),
        ],
    )
    return tab


def mining_helper():
    """Helper"""
    msg = """
    The Fink data transfer service allows you to select and transfer the Fink processed alert data at scale.
    We provide alert data from ZTF (more than 110 million alerts as of 2023), and from the DESC/ELASTiCC data challenge (more than 50 million alerts).
    Fill the fields on the right (note the changing timeline on the left when you update parameters),
    and once ready, submit your job on the Fink Apache Spark & Kafka clusters and retrieve your data.
    To retrieve the data, you need to get an account. See [fink-client](https://github.com/astrolabsoftware/fink-client) and
    this [post](https://fink-broker.readthedocs.io/en/latest/services/data_transfer) for more information.
    """

    cite = """
    You need an account to retrieve the data. See [fink-client](https://github.com/astrolabsoftware/fink-client) if you are not yet registered.
    """

    accordion = dmc.Accordion(
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Description",
                        icon=[
                            DashIconify(
                                icon="material-symbols:info-outline",
                                width=30,
                                color="black",
                            ),
                        ],
                    ),
                    dmc.AccordionPanel(
                        dcc.Markdown(msg, link_target="_blank"),
                    ),
                ],
                value="description",
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Log in",
                        icon=[
                            DashIconify(
                                icon="bx:log-in-circle", width=30, color="orange"
                            ),
                        ],
                    ),
                    dmc.AccordionPanel(
                        dcc.Markdown(cite, link_target="_blank"),
                    ),
                ],
                value="login",
            ),
        ],
    )
    return accordion


def layout():
    """Layout for the data transfer service"""
    qb = query_builder()
    ft = filter_tab()
    ct = content_tab()
    btns = make_buttons()

    title = dbc.Row(
        children=[
            dmc.Space(h=20),
            dmc.Stack(
                children=[
                    dmc.Title(
                        children="Fink Data Transfer",
                        style={"color": "#15284F"},
                    ),
                    dmc.Anchor(
                        dmc.ActionIcon(
                            DashIconify(icon="fluent:question-16-regular", width=20),
                            size=30,
                            radius="xl",
                            variant="light",
                            color="orange",
                        ),
                        href="https://fink-broker.org/2023-01-17-data-transfer",
                        target="_blank",
                        className="d-block d-md-none",
                    ),
                ],
                align="center",
                justify="center",
            ),
        ],
    )

    layout_ = dbc.Container(
        [
            title,
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div(id="timeline_data_transfer"),
                            html.Br(),
                            mining_helper(),
                        ],
                        md=3,
                        className="d-none d-md-block",
                    ),
                    dbc.Col(
                        [
                            qb,
                            ft,
                            ct,
                            html.Div(id="summary_tab"),
                            dmc.Space(h=10),
                            html.Div(
                                btns, id="transfer_buttons", style={"display": "none"}
                            ),
                            html.Div(id="streaming_info"),
                            html.Div("", id="batch_id", style={"display": "none"}),
                            html.Div("", id="topic_name", style={"display": "none"}),
                            make_final_helper(),
                            html.Br(),
                            html.Br(),
                        ],
                        md=9,
                    ),
                ],
                justify="around",
                className="g-2 mt-2",
            ),
        ],
        fluid="lg",
    )

    # Wrap it to re-define the background
    layout_ = html.Div(
        layout_,
        className="bg-opaque-90",
    )

    return layout_

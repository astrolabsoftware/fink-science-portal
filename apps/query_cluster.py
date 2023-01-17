# Copyright 2022 AstroLab Software
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
import dash
from dash import html, dcc, Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from app import app
from app import APIURL
from apps.mining.utils import upload_file_hdfs, submit_spark_job
from apps.mining.utils import estimate_size_gb

import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date
import requests
import yaml
import textwrap

from fink_utils.xmatch.simbad import get_simbad_labels

simbad_types = get_simbad_labels('old_and_new')
simbad_types = sorted(simbad_types, key=lambda s: s.lower())

tns_types = pd.read_csv('assets/tns_types.csv', header=None)[0].values
tns_types = sorted(tns_types, key=lambda s: s.lower())

coeffs_per_class = pd.read_parquet('assets/fclass_2022_060708_coeffs.parquet')

@app.callback(
    Output("timeline_data_transfer", "children"),
    [
        Input('trans_datasource', 'value'),
        Input('date-range-picker', 'value'),
        Input('class_select', 'value'),
        Input('extra_cond', 'value'),
        Input('trans_content', 'value')
    ]
)
def timeline_data_transfer(trans_datasource, date_range_picker, class_select, extra_cond, trans_content):
    """
    """
    active_ = np.where(
        np.array([trans_datasource, date_range_picker, trans_content]) != None
    )[0]
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
                            "Source: {}".format(trans_datasource)
                        ],
                        color="dimmed",
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
                        color="dimmed",
                        size="sm",
                    ),
                    dmc.Text(
                        [
                            "Classe(s): {}".format(class_select),
                        ],
                        color="dimmed",
                        size="sm",
                    ),
                    dmc.Text(
                        [
                            "Conditions: {}".format(extra_cond),
                        ],
                        color="dimmed",
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
                            "Content: {}".format(trans_content),
                        ],
                        color="dimmed",
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
                        color="dimmed",
                        size="sm",
                    ),
                ],
                title="Submit",
            ),
        ],
    )

    return timeline

def filter_tab():
    """ Section containing filtering options
    """
    options = html.Div(
        [
            dmc.DateRangePicker(
                id="date-range-picker",
                label="Date Range",
                description="Pick up start and stop dates (included).",
                minDate=date(2019, 11, 1),
                maxDate=date.today(),
                value=None,
                style={"width": 500},
                hideOutsideDates=True,
                amountOfMonths=2,
                allowSingleDateInRange=True,
                required=True
            ),
            dmc.Space(h=10),
            dmc.MultiSelect(
                label="Alert class",
                description="Select all classes you like! Default is all classes.",
                placeholder="start typing...",
                id="class_select",
                value=None,
                data = [
                    {'label': 'All classes', 'value': 'allclasses'},
                    {'label': 'Unknown', 'value': 'Unknown'},
                    {'label': '(Fink) Early Supernova Ia candidates', 'value': 'Early SN Ia candidate'},
                    {'label': '(Fink) Supernova candidates', 'value': 'SN candidate'},
                    {'label': '(Fink) Kilonova candidates', 'value': 'Kilonova candidate'},
                    {'label': '(Fink) Microlensing candidates', 'value': 'Microlensing candidate'},
                    {'label': '(Fink) Solar System (MPC)', 'value': 'Solar System MPC'},
                    {'label': '(Fink) Solar System (candidates)', 'value': 'Solar System candidate'},
                    {'label': '(Fink) Tracklet (space debris & satellite glints)', 'value': 'Tracklet'},
                    {'label': '(Fink) Ambiguous', 'value': 'Ambiguous'},
                    *[{'label': '(TNS) ' + simtype, 'value': '(TNS) ' + simtype} for simtype in tns_types],
                    *[{'label': '(SIMBAD) ' + simtype, 'value': '(SIMBAD) ' + simtype} for simtype in simbad_types]
                ],
                searchable=True,
                style={"width": 500},
            ),
            dmc.Space(h=10),
            dmc.Textarea(
                id="extra_cond",
                label="Extra conditions",
                description=[
                    "One condition per line (SQL syntax), ending with semi-colon. See ",
                    dmc.Anchor("here", href="https://fink-portal.org/api/v1/columns", size="xs"),
                    " for field description.",
                ],
                placeholder="e.g. magpsf > 19.5;",
                style={"width": 500},
                autosize=True,
                minRows=2,              ),
        ]
    )
    tab = html.Div(
        [
            dmc.Space(h=10),
            dmc.Divider(variant="solid", label='Filters'),
            options,
        ], id='filter_tab', style={'display': 'none'}
    )
    return tab

@app.callback(
    Output("filter_tab", "style"),
    [
        Input('trans_datasource', 'value')
    ], prevent_initial_call=True
)
def display_filter_tab(trans_datasource):
    if trans_datasource is None:
        PreventUpdate
    else:
        return {}

def content_tab():
    """ Section containing filtering options
    """
    tab = html.Div(
        [
            dmc.Space(h=10),
            dmc.Divider(variant="solid", label='Alert content'),
            dmc.RadioGroup(
                id="trans_content",
                data=[
                    {"value": "Lightcurve", "label": "Lightcurve (~1.4 KB/alert)"},
                    {"value": "Cutouts", "label": "Cutouts (~41 KB/alert)"},
                    {"value": "Full packet", "label": "Full packet (~55 KB/alert)"},
                ],
                value=None,
                label="Choose the content you want to retrieve",
                size="sm",
                color='orange'
            ),
        ], style={'display': 'none'}, id='content_tab'
    )
    return tab

@app.callback(
    Output("content_tab", "style"),
    [
        Input('date-range-picker', 'value')
    ], prevent_initial_call=True
)
def update_content_tab(date_range_picker):
    if date_range_picker is None:
        PreventUpdate
    else:
        return {}

def estimate_alert_number(date_range_picker, class_select):
    """ Callback to estimate the number of alerts to be transfered

    This can be improved by using the REST API directly to get number of
    alerts per class.
    """
    dic = {'basic:sci': 0}
    dstart = date(*[int(i) for i in date_range_picker[0].split('-')])
    dstop = date(*[int(i) for i in date_range_picker[1].split('-')])
    delta = dstop - dstart

    columns = 'basic:sci'
    column_names = []
    if (class_select is not None) and (class_select != []):
        if 'allclasses' not in class_select:
            for elem in class_select:
                if elem.startswith('(TNS)'):
                    continue

                # name correspondance
                if elem.startswith('(SIMBAD)'):
                    elem = elem.replace('(SIMBAD) ', 'class:')
                else:
                    # prepend class:
                    elem = 'class:' + elem
                columns += ',{}'.format(elem)
                column_names.append(elem)

    # Initialise count
    for column_name in column_names:
        dic[column_name] = 0


    for i in range(delta.days + 1):
        tmp = (dstart + timedelta(i)).strftime('%Y%m%d')
        r = requests.post(
            '{}/api/v1/statistics'.format(APIURL),
            json={
                'date': tmp,
                'columns': columns,
                'output-format': 'json'
            }
        )
        if r.json() != []:
            payload = r.json()[0]
            dic['basic:sci'] += int(payload['basic:sci'])
            for column_name in column_names:
                if column_name in payload.keys():
                    dic[column_name] += int(payload[column_name])
                else:
                    dic[column_name] += 0

    # Add TNS estimation
    if (class_select is not None) and (class_select != []):
        if 'allclasses' not in class_select:
            for elem in class_select:
                # name correspondance
                if elem.startswith('(TNS)'):
                    filt = coeffs_per_class['fclass'] == elem

                    if np.sum(filt) == 0:
                        # Nothing found. This could be because we have
                        # no alerts from this class, or because it has not
                        # yet entered the statistics. To be conservative,
                        # we do not apply any coefficients.
                        dic[elem] = 0
                    else:
                        dic[elem.replace('(TNS) ', 'class:')] = int(dic['basic:sci'] * coeffs_per_class[filt]['coeff'].values[0])
            count = np.sum([i[1] for i in dic.items() if 'class:' in i[0]])
        else:
            # allclasses mean all alerts
            count = dic['basic:sci']
    else:
        count = dic['basic:sci']

    return dic['basic:sci'], count

@app.callback(
    Output("summary_tab", "children"),
    [
        Input('trans_content', 'value'),
        Input('trans_datasource', 'value'),
        Input('date-range-picker', 'value'),
        Input('class_select', 'value'),
        Input('extra_cond', 'value'),
    ],
    prevent_initial_call=True
)
def summary_tab(trans_content, trans_datasource, date_range_picker, class_select, extra_cond):
    """ Section containing summary
    """
    if trans_content is None:
        html.Div(style={'display': 'none'})
    elif date_range_picker is None:
        PreventUpdate
    else:
        msg = """
        You are about to submit a streaming job on our Apache Spark cluster.
        Review your parameters, and take into account the estimated number of
        alerts before hitting submission! Note that the estimation takes into account
        the days requested and the classes, but not the extra conditions (which could reduce the
        number of alerts).
        """
        total, count = estimate_alert_number(date_range_picker, class_select)

        sizeGb = estimate_size_gb(trans_content)

        if count == 0:
            msg_title = 'No alerts found. Try to update your criteria.'
        else:
            msg_title = "Estimated number of alerts: {:,} ({:.2f}%) or {:.2f} GB".format(
                int(count),
                count / total * 100,
                count * sizeGb
            ),

        if count == 0:
            icon = 'codicon:chrome-close'
            color = 'gray'
        elif count < 250000:
            icon = "codicon:check"
            color = 'green'
        elif count > 10000000:
            icon = "emojione-v1:face-screaming-in-fear"
            color = "red"
        else:
            icon = "codicon:flame"
            color = 'orange'
        block = dmc.Blockquote(
            msg_title,
            cite=msg,
            icon=[DashIconify(icon=icon, width=30)],
            color=color,
        )
        tab = html.Div(
            [
                dmc.Space(h=10),
                dmc.Divider(variant="solid", label='Submit'),
                block
            ],
        )
        return tab

def make_buttons():
    buttons = dmc.Group(
        [
            dmc.Button(
                "Submit job",
                id='submit_datatransfer',
                variant="outline",
                color='indigo',
                leftIcon=[DashIconify(icon="fluent:database-plug-connected-20-filled")],
            ),
            dmc.Button(
                "Test job (LIMIT 10)",
                id='submit_datatransfer_test',
                variant="outline",
                color='orange',
                leftIcon=[DashIconify(icon="fluent:battery-2-24-regular")],
            ),
        ]
    )
    return buttons

@app.callback(
    Output("transfer_buttons", "style"),
    [
        Input('trans_content', 'value')
    ], prevent_initial_call=True
)
def update_make_buttons(trans_content):
    if trans_content is None:
        PreventUpdate
    else:
        return {}

@app.callback(
    Output("batch_log", "children"),
    [
        Input('update_batch_log', 'n_clicks'),
        Input('batch_id', 'children')
    ]
)
def update_log(n_clicks, batchid):
        if n_clicks:
            if batchid != "":
                response = requests.get('http://134.158.75.222:21111/batches/{}/log'.format(batchid))

                if 'log' in response.json():
                    livy_log = [row for row in response.json()['log'] if '-Livy-' in row]
                    livy_log = ['Batch ID: {}'.format(batchid), 'Starting...'] + livy_log
                    output = html.Div('\n'.join(livy_log), style={'whiteSpace': 'pre-wrap'})
                elif 'msg' in response.json():
                    output = html.Div(response.text)
                return output
            else:
                return html.Div('batch ID is empty')

def make_final_helper():
    """
    """
    accordion = dmc.Accordion(
        children=[
            dmc.AccordionItem(
                children=html.Div(id='final_accordion_1'),
                label="Get your data",
            ),
            dmc.AccordionItem(
                children=[
                    dmc.Button("Update log", id='update_batch_log', color='orange'),
                    html.Div(id='batch_log')
                ],
                label="Monitor your job",
            ),
        ],
        id='final_accordion',
        style={'display': 'none'}
    )
    return accordion

@app.callback(
    Output("final_accordion_1", "children"),
    [
        Input('topic_name', 'children')
    ]
)
def update_final_accordion1(topic_name):
    """
    """
    if topic_name != "":
        msg = """
        You can easily download your alerts using the [fink-client](https://github.com/astrolabsoftware/fink-client). Install the latest version and
        use e.g.
        """
        code_block = """
        fink_datatransfer \\
            -topic {} \\
            -outdir {} \\
            -partitionby finkclass \\
            --verbose
        """.format(topic_name, topic_name)
        out = html.Div(
            [
                dcc.Markdown(msg),
                dmc.Prism(children=code_block, language="bash")
            ]
        )

        return out

@app.callback(
    Output("submit_datatransfer", "disabled"),
    Output("submit_datatransfer_test", "disabled"),
    Output("streaming_info", "children"),
    Output("batch_id", "children"),
    Output("topic_name", "children"),
    Output("final_accordion", "style"),
    [
        Input('submit_datatransfer', 'n_clicks'),
        Input('submit_datatransfer_test', 'n_clicks'),
    ],
    [
        State('trans_content', 'value'),
        State('trans_datasource', 'value'),
        State('date-range-picker', 'value'),
        State('class_select', 'value'),
        State('extra_cond', 'value'),
    ],
    prevent_initial_call=True
)
def submit_job(n_clicks, n_clicks_test, trans_content, trans_datasource, date_range_picker, class_select, extra_cond):
    """ Submit a job to the Apache Spark cluster via Livy
    """
    if n_clicks or n_clicks_test:
        # define unique topic name
        d = datetime.utcnow()
        topic_name = 'ftransfer_{}_{}'.format(d.date().isoformat(), d.microsecond)

        with open('assets/spark_transfer.py', 'r') as f:
            data = f.read()
        code = textwrap.dedent(data)

        filename = 'stream_{}.py'.format(topic_name)
        input_args = yaml.load(open('config_datatransfer.yml'), yaml.Loader)
        status_code, hdfs_log = upload_file_hdfs(
            code,
            input_args['WEBHDFS'],
            input_args['NAMENODE'],
            input_args['USER'],
            filename
        )

        if status_code != 201:
            text = "[Status code {}] Unable to upload resources on HDFS, with error: {}. Contact an administrator at contact@fink-broker.org.".format(status_code, hdfs_log)
            return True, True, text, "", "", {'display': 'none'}

        # get the job args
        job_args = [
            '-startDate={}'.format(date_range_picker[0]),
            '-stopDate={}'.format(date_range_picker[1]),
            '-content={}'.format(trans_content),
            '-basePath=/user/julien.peloton/archive/science',
            '-topic_name={}'.format(topic_name),
            '-kafka_bootstrap_servers={}'.format(input_args['KAFKA_BOOTSTRAP_SERVERS']),
            '-kafka_sasl_username={}'.format(input_args['KAFKA_SASL_USERNAME']),
            '-kafka_sasl_password={}'.format(input_args['KAFKA_SASL_PASSWORD']),
            '-path_to_tns=/spark_mongo_tmp/julien.peloton/tns.parquet',
        ]
        if class_select is not None:
            for elem in class_select:
                job_args.append('-fclass={}'.format(elem))

        if extra_cond is not None:
            extra_cond_list = extra_cond.split(';')
            for elem in extra_cond_list:
                job_args.append('-extraCond={}'.format(elem.strip()))

        if n_clicks_test and not (n_clicks is not None):
            job_args.append('--limit_output')
        # submit the job
        filepath = 'hdfs:///user/{}/{}'.format(input_args['USER'], filename)
        batchid, status_code, spark_log = submit_spark_job(
            input_args['LIVYHOST'],
            filepath,
            input_args['SPARKCONF'],
            job_args
        )

        if status_code != 201:
            text = "[Batch ID {}][Status code {}] Unable to submit job on the Spark cluster, with error: {}. Contact an administrator at contact@fink-broker.org.".format(batchid, status_code, spark_log)
            return True, True, text, "", "", {'display': 'none'}

        text = dmc.Blockquote(
            "Your topic name is: {}".format(
                topic_name
            ),
            icon=[DashIconify(icon="system-uicons:pull-down", width=30)],
            color="green",
        )
        if n_clicks:
            return True, True, text, batchid, topic_name, {}
        else:
            return False, True, text, batchid, topic_name, {}
    else:
        return False, False, "", "", "", {'display': 'none'}


def query_builder():
    """ Build iteratively the query based on user inputs.
    """
    tab = html.Div(
        [
            html.Br(),
            html.Br(),
            dmc.Divider(variant="solid", label='Data Source'),
            dmc.RadioGroup(
                id="trans_datasource",
                data=[
                    {"value": "ZTF", "label": "ZTF"},
                    # {"value": "elasticc", "label": "ELASTiCC"},
                ],
                value=None,
                label="Choose the type of alerts you want to retrieve",
                size="sm",
                color='orange'
            ),
        ]
    )
    return tab

def mining_helper():
    """ Helper
    """
    msg = """
    The Fink data mining service allows you to select and transfer the Fink processed alert data at scale.
    The only data source currently available is ZTF, with more than 110 million alerts as of 2023.
    Fill the fields on the right (note the changing timeline on the left when you update parameters),
    and once you are happy, submit your job on the Fink Apache Spark Cluster and retrieve your data!
    """

    accordion = dmc.Accordion(
        children=[
            dmc.AccordionItem(
                dcc.Markdown(msg),
                label="Description",
            ),
        ],
    )
    return accordion

def layout(is_mobile):
    """ Layout for the data transfer service
    """
    qb = query_builder()
    ft = filter_tab()
    ct = content_tab()
    btns = make_buttons()
    fh = make_final_helper()
    layout_ = html.Div(
        [
            html.Br(),
            html.Br(),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Br(),
                            html.Br(),
                            html.Div(id='timeline_data_transfer'),
                            html.Br(),
                            mining_helper(),
                        ], width={"size": 3},
                    ),
                    dbc.Col(
                        [
                            qb,
                            ft,
                            ct,
                            html.Div(id='summary_tab'),
                            dmc.Space(h=10),
                            html.Div(btns, id='transfer_buttons', style={'display': 'none'}),
                            html.Div(id='streaming_info'),
                            html.Div("", id='batch_id', style={'display': 'none'}),
                            html.Div("", id='topic_name', style={'display': 'none'}),
                            make_final_helper(),
                            html.Br(),
                            html.Br(),

                        ],
                        width=8)
                ],
                justify="around", className="g-0"
            ),
        ], className='home', style={'background-image': 'linear-gradient(rgba(255,255,255,0.9), rgba(255,255,255,0.9)), url(/assets/background.png)', 'background-size': 'cover'}
    )

    return layout_
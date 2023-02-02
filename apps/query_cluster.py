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
from apps.mining.utils import estimate_size_gb_ztf, estimate_size_gb_elasticc

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

elasticc_classes = pd.read_csv('assets/elasticc_classes.csv')
elasticc_dates = pd.read_csv('assets/elasticc_dates.csv')
elasticc_dates['date'] = elasticc_dates['date'].astype('str')

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

def filter_tab(is_mobile):
    """ Section containing filtering options
    """
    if is_mobile:
        width = '100%'
        amountOfMonths = 1
    else:
        width = '50%'
        amountOfMonths = 2
    options = html.Div(
        [
            dmc.DateRangePicker(
                id="date-range-picker",
                label="Date Range",
                description="Pick up start and stop dates (included).",
                style={"width": width},
                hideOutsideDates=True,
                amountOfMonths=amountOfMonths,
                allowSingleDateInRange=True,
                required=True
            ),
            dmc.Space(h=10),
            dmc.MultiSelect(
                label="Alert class",
                description="Select all classes you like! Default is all classes.",
                placeholder="start typing...",
                id="class_select",
                searchable=True,
                style={"width": width},
            ),
            dmc.Space(h=10),
            dmc.Textarea(
                id="extra_cond",
                label="Extra conditions",
                style={"width": width},
                autosize=True,
                minRows=2,
            ),
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
    [
        Output("filter_tab", "style"),
        Output("date-range-picker", "minDate"),
        Output("date-range-picker", "maxDate"),
        Output("class_select", "data"),
        Output("extra_cond", "description"),
        Output("extra_cond", "placeholder"),
        Output("trans_content", "children")
    ],
    [
        Input('trans_datasource', 'value')
    ], prevent_initial_call=True
)
def display_filter_tab(trans_datasource):
    if trans_datasource is None:
        PreventUpdate
    else:
        if trans_datasource == 'ZTF':
            minDate = date(2019, 11, 1)
            maxDate = date.today()
            data_class_select = [
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
            ]
            description = [
                "One condition per line (SQL syntax), ending with semi-colon. See ",
                dmc.Anchor("here", href="https://fink-broker.readthedocs.io/en/latest/science/added_values/", size="xs", target="_blank"),
                " for field description.",
            ]
            placeholder = "e.g. candidate.magpsf > 19.5;"
            labels = ["Lightcurve (~1.4 KB/alert)", "Cutouts (~41 KB/alert)", "Full packet (~55 KB/alert)"]
            values = ['Lightcurve', 'Cutouts', 'Full packet']
            data_content = [
                dmc.Radio(label=l, value=k, size='sm', color='orange')
                for l, k in zip(labels, values)
            ]
        elif trans_datasource == 'ELASTiCC':
            minDate = date(2023, 11, 27)
            maxDate = date(2026, 12, 5)
            data_class_select = [
                {'label': 'All classes', 'value': 'allclasses'},
                *[{'label': str(simtype), 'value': simtype} for simtype in sorted(elasticc_classes['classId'].values)],
            ]
            description = [
                "One condition per line (SQL syntax), ending with semi-colon. See ",
                dmc.Anchor("here", href="https://portal.nersc.gov/cfs/lsst/DESC_TD_PUBLIC/ELASTICC/#alertschema", size="xs", target="_blank"),
                " for field description.",
            ]
            placeholder = "e.g. diaSource.psFlux > 0.0;"
            labels = ["Full packet (~1.4 KB/alert)"]
            values = ['Full packet']
            data_content = [
                dmc.Radio(label=l, value=k, size='sm', color='orange')
                for l, k in zip(labels, values)
            ]

        return {}, minDate, maxDate, data_class_select, description, placeholder, data_content

def content_tab():
    """ Section containing filtering options
    """
    tab = html.Div(
        [
            dmc.Space(h=10),
            dmc.Divider(variant="solid", label='Alert content'),
            dmc.RadioGroup(
                id="trans_content",
                label="Choose the content you want to retrieve",
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

def estimate_alert_number_ztf(date_range_picker, class_select):
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

def estimate_alert_number_elasticc(date_range_picker, class_select):
    """ Callback to estimate the number of alerts to be transfered
    """
    dic = {'basic:sci': 0}
    dstart = date(*[int(i) for i in date_range_picker[0].split('-')])
    dstop = date(*[int(i) for i in date_range_picker[1].split('-')])
    delta = dstop - dstart

    # count all raw number of alerts
    for i in range(delta.days + 1):
        tmp = (dstart + timedelta(i)).strftime('%Y%m%d')
        filt = elasticc_dates['date'] == tmp
        if np.sum(filt) > 0:
            dic['basic:sci'] += int(elasticc_dates[filt]['count'].values[0])

    # Add class estimation
    if (class_select is not None) and (class_select != []):
        if 'allclasses' not in class_select:
            for elem in class_select:
                # name correspondance
                filt = elasticc_classes['classId'] == elem

                if np.sum(filt) == 0:
                    # Nothing found. This could be because we have
                    # no alerts from this class, or because it has not
                    # yet entered the statistics. To be conservative,
                    # we do not apply any coefficients.
                    dic[elem] = 0
                else:
                    coeff = elasticc_classes[filt]['count'].values[0] / elasticc_classes['count'].sum()
                    dic['class:' + str(elem)] = int(dic['basic:sci'] * coeff)
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
        You are about to submit a job on the Fink Apache Spark & Kafka clusters.
        Review your parameters, and take into account the estimated number of
        alerts before hitting submission! Note that the estimation takes into account
        the days requested and the classes, but not the extra conditions (which could reduce the
        number of alerts).
        """
        if trans_datasource == 'ZTF':
            total, count = estimate_alert_number_ztf(date_range_picker, class_select)
            sizeGb = estimate_size_gb_ztf(trans_content)
        elif trans_datasource == 'ELASTiCC':
            total, count = estimate_alert_number_elasticc(date_range_picker, class_select)
            sizeGb = estimate_size_gb_elasticc(trans_content)

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
                    failure_log = [row for row in response.json()['log'] if 'Caused by' in row]
                    if len(failure_log) > 0:
                        failure_msg = ['Batch ID: {}'.format(batchid), 'Failed. Please, contact contact@fink-broker.org with your batch ID.']
                        output = html.Div('\n'.join(failure_msg), style={'whiteSpace': 'pre-wrap'})
                        return output
                    # catch and return tailored error msg if fail (with batchid and contact@fink-broker.org)
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
                [
                    dmc.AccordionControl("Monitor your job"),
                    dmc.AccordionPanel(
                        [
                            dmc.Button("Update log", id='update_batch_log', color='orange'),
                            html.Div(id='batch_log')
                        ],
                    ),
                ],
                value='monitor'
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl("Get your data"),
                    dmc.AccordionPanel(
                        [
                            html.Div(id='final_accordion_1'),
                        ],
                    ),
                ],
                value='get_data'
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
        if 'elasticc' in topic_name:
            partition = 'classId'
        else:
            partition = 'finkclass'

        msg = """
        Once data has started to flow in the topic, you can easily download your alerts using the [fink-client](https://github.com/astrolabsoftware/fink-client). Install the latest version and
        use e.g.
        """
        code_block = """
        fink_datatransfer \\
            -topic {} \\
            -outdir {} \\
            -partitionby {} \\
            --verbose
        """.format(topic_name, topic_name, partition)
        out = html.Div(
            [
                dcc.Markdown(msg, link_target="_blank"),
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

        if trans_datasource == 'ZTF':
            topic_name = 'ftransfer_ztf_{}_{}'.format(d.date().isoformat(), d.microsecond)
            fn = 'assets/spark_ztf_transfer.py'
            basepath = '/user/julien.peloton/archive/science'
        elif trans_datasource == 'ELASTiCC':
            topic_name = 'ftransfer_elasticc_{}_{}'.format(d.date().isoformat(), d.microsecond)
            fn = 'assets/spark_elasticc_transfer.py'
            basepath = '/user/julien.peloton/elasticc_curated_truth_one'
        filename = 'stream_{}.py'.format(topic_name)

        with open(fn, 'r') as f:
            data = f.read()
        code = textwrap.dedent(data)

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
            '-basePath={}'.format(basepath),
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
            dmc.Divider(variant="solid", label='Data Source'),
            dmc.RadioGroup(
                [dmc.Radio(k, value=k, size='sm', color='orange') for k in ['ZTF', 'ELASTiCC']],
                id="trans_datasource",
                value=None,
                label="Choose the type of alerts you want to retrieve",
            ),
        ]
    )
    return tab

def mining_helper():
    """ Helper
    """
    msg = """
    The Fink data transfer service allows you to select and transfer the Fink processed alert data at scale.
    We provide alert data from ZTF (more than 110 million alerts as of 2023), and from the DESC/ELASTiCC data challenge (more than 50 million alerts).
    Fill the fields on the right (note the changing timeline on the left when you update parameters),
    and once ready, submit your job on the Fink Apache Spark & Kafka clusters and retrieve your data.
    To retrieve the data, you need to get an account. See [fink-client](https://github.com/astrolabsoftware/fink-client) and
    this [post](https://fink-broker.org/2023-01-17-data-transfer) for more information.
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
                            DashIconify(icon="bx:info-circle", width=30, color='black')
                        ]
                    ),
                    dmc.AccordionPanel(
                        dcc.Markdown(msg, link_target="_blank")
                    ),
                ],
                value='description'
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Log in",
                        icon=[
                            DashIconify(icon="bx:log-in-circle", width=30, color='orange')
                        ]
                    ),
                    dmc.AccordionPanel(
                        dcc.Markdown(cite, link_target="_blank")
                    ),
                ],
                value='login'
            ),
        ],
    )
    return accordion

def layout(is_mobile):
    """ Layout for the data transfer service
    """
    qb = query_builder()
    ft = filter_tab(is_mobile)
    ct = content_tab()
    btns = make_buttons()
    fh = make_final_helper()

    if is_mobile:
        width_right = 10
        title = dbc.Row(
            children=[
                dmc.Space(h=20),
                dmc.Stack(
                    children=[
                        dmc.Title(
                            children='Fink Data Transfer',
                            style={'color': '#15284F'}
                        ),
                        dmc.Anchor(
                            dmc.ActionIcon(
                                DashIconify(icon="fluent:question-16-regular", width=20),
                                size=30,
                                radius="xl",
                                variant="light",
                                color='orange',
                            ),
                            href="https://fink-broker.org/2023-01-17-data-transfer",
                            target="_blank"
                        ),
                    ],
                    align="center",
                    justify="center",
                )
            ]
        )
        left_side = html.Div(id='timeline_data_transfer', style={'display': 'none'})
        style = {
            'background-image': 'linear-gradient(rgba(255,255,255,0.3), rgba(255,255,255,0.3)), url(/assets/background.png)'
        }
    else:
        width_right = 8
        title = html.Div()
        left_side = dbc.Col(
            [
                html.Br(),
                html.Br(),
                html.Div(id='timeline_data_transfer'),
                html.Br(),
                mining_helper(),
            ], width={"size": 3},
        )
        style={
            'background-image': 'linear-gradient(rgba(255,255,255,0.3), rgba(255,255,255,0.3)), url(/assets/background.png)',
            'background-size': 'cover'
        }

    layout_ = html.Div(
        [
            html.Br(),
            html.Br(),
            title,
            dbc.Row(
                [
                    left_side,
                    dbc.Col(
                        [
                            html.Br(),
                            html.Br(),
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
                        width=width_right)
                ],
                justify="around", className="g-0"
            ),
            html.Br(),
        ], className='home', style={'background-image': 'linear-gradient(rgba(255,255,255,0.9), rgba(255,255,255,0.9)), url(/assets/background.png)', 'background-size': 'cover'}
    )

    return layout_

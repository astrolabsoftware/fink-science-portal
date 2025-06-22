# Copyright 2023-2024 AstroLab Software
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
import json
from datetime import date, timedelta
import requests
import numpy as np
import pandas as pd

from apps.utils import query_and_order_statistics, request_api, select_struct

coeffs_per_class = pd.read_parquet("assets/fclass_2022_060708_coeffs.parquet")
coeffs_per_filters = pd.read_parquet("assets/ffilters_2025_01_to_06_coeffs.parquet")

CONV = {
    "float": 4,
    "double": 8,
    "int": 4,
    "string": 8,
    "array": 4 * 60 * 60,
    "boolean": 1,
    "long": 8,
}


def upload_file_hdfs(code, webhdfs, namenode, user, filename):
    """Upload a file to HDFS

    Parameters
    ----------
    code: str
        Code as string
    webhdfs: str
        Location of the code on webHDFS in the format
        http://<IP>:<PORT>/webhdfs/v1/<path>
    namenode: str
        Namenode and port in the format
        <IP>:<PORT>
    user: str
        User name in HDFS
    filename: str
        Name on the file to be created

    Returns
    -------
    status_code: int
        HTTP status code. 201 is a success.
    text: str
        Additional information on the query (log).
    """
    try:
        response = requests.put(
            f"{webhdfs}/{filename}?op=CREATE&user.name={user}&namenoderpcaddress={namenode}&createflag=&createparent=true&overwrite=true",
            data=code,
        )
        status_code = response.status_code
        text = response.text
    except (requests.exceptions.ConnectionError, ConnectionRefusedError) as e:
        status_code = -1
        text = e

    if status_code != 201:
        print(f"Status code: {status_code}")
        print(f"Log: {text}")

    return status_code, text


def submit_spark_job(livyhost, filename, spark_conf, job_args):
    """Submit a job on the Spark cluster via Livy (batch mode)

    Parameters
    ----------
    livyhost: str
        IP:HOST for the Livy service
    filename: str
        Path on HDFS with the file to submit. Format:
        hdfs://<path>/<filename>
    spark_conf: dict
        Dictionary with Spark configuration
    job_args: list of str
        Arguments for the Spark job in the form
        ['-arg1=val1', '-arg2=val2', ...]

    Returns
    -------
    batchid: int
        The number of the submitted batch
    response.status_code: int
        HTTP status code
    response.text: str
        Payload
    """
    headers = {"Content-Type": "application/json"}

    data = {
        "conf": spark_conf,
        "file": filename,
        "args": job_args,
    }
    response = requests.post(
        "http://" + livyhost + "/batches",
        data=json.dumps(data),
        headers=headers,
    )

    batchid = response.json()["id"]

    if response.status_code != 201:
        print(f"Batch ID {batchid}")
        print(f"Status code: {response.status_code}")
        print(f"Log: {response.text}")

    return batchid, response.status_code, response.text


def extract_type(field):
    if isinstance(field, list):
        # null, type
        return field[1]
    else:
        return field


def estimate_size_gb_ztf(content):
    """Estimate the size of the data to download

    Parameters
    ----------
    content: list
        List of selected alert fields
    """
    if content is None:
        return 0
    # Pre-defined schema
    if "Full packet" in content:
        # all nested fields, incl prv_candidates
        sizeGb = 55.0 / 1024 / 1024
    elif "Light packet" in content:
        sizeGb = 1.4 / 1024 / 1024
    else:
        # freedom on candidates + added values
        schema = request_api("/api/v1/schema", method="GET", output="json")
        sizeB = 0
        for k_out in schema.keys():
            for k_in, field in schema[k_out].items():
                if select_struct(k_in) in content:
                    sizeB += CONV[extract_type(field["type"])]
                elif select_struct(k_in, "candidate.") in content:
                    sizeB += CONV[extract_type(field["type"])]

        sizeGb = sizeB / 1024 / 1024 / 1024

    return sizeGb


def estimate_size_gb_elasticc(content):
    """Estimate the size of the data to download

    Parameters
    ----------
    content: str
        Name as given by content_tab
    """
    if "Full packet" in content:
        sizeGb = 1.4 / 1024 / 1024

    return sizeGb


def initialise_classes(class_select):
    """Add classes selected by the user

    Parameters
    ----------
    class_select: list, optional
        List of classes selected by the user.
        None is not class selected.

    Returns
    -------
    columns: str
        Comma-separated names of classes
    column_classes: list
        List of classes. Empty list if no class selected.
    """
    column_names = []
    columns = "basic:sci"
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

    return columns, column_names


def get_statistics(column_names, dstart, dstop, with_class=True):
    """ """
    dic = {"basic:sci": 0}

    # Get total number of alerts for the period
    pdf = query_and_order_statistics(
        drop=False,
    )
    pdf["ISO"] = pdf["key:key"].apply(lambda x: x.split("_")[1])

    f1 = pdf["ISO"] <= dstop.strftime("%Y%m%d")
    f2 = pdf["ISO"] >= dstart.strftime("%Y%m%d")

    pdf = pdf[f1 & f2]
    dic["basic:sci"] += int(pdf["basic:sci"].sum())

    if with_class:
        # Initialise count
        for column_name in column_names:
            if column_name in pdf.columns:
                dic[column_name] = int(pdf[column_name].sum())
            else:
                dic[column_name] = 0

    return dic


def add_tns_estimation(dic, class_select):
    """Add estimation for TNS classes

    TNS statistics is not pushed in /statistics
    """
    if "allclasses" not in class_select:
        for elem in class_select:
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
                        dic["basic:sci"] * coeffs_per_class[filt]["coeff"].to_numpy()[0]
                    )

    return dic


def get_filter_statistics(dic, filter_select):
    """Get stastitics based on a user-defined filter

    Parameters
    ----------
    dic: dict
        Dictionnary containing counts
    filter_select: str, optional
        Filter name
    """
    id_ = coeffs_per_filters["filter"] == filter_select
    if np.sum(id_) == 1:
        dic[filter_select] = (
            coeffs_per_filters[id_]["coeff"].to_numpy()[0] * dic["basic:sci"]
        )

    return dic


def estimate_alert_number_ztf(date_range_picker, class_select, filter_select):
    """Callback to estimate the number of alerts to be transfered

    This can be improved by using the REST API directly to get number of
    alerts per class.
    """
    dstart = date(*[int(i) for i in date_range_picker[0].split("-")])
    dstop = date(*[int(i) for i in date_range_picker[1].split("-")])

    columns, column_names = initialise_classes(class_select)

    with_filter = (
        (filter_select is not None) and (filter_select != "") and (filter_select != [])
    )
    with_class = (
        (class_select is not None) and (class_select != "") and (class_select != [])
    )
    dic = get_statistics(column_names, dstart, dstop, with_class=not with_filter)

    # we check first filter, and then class
    if with_filter:
        dic = get_filter_statistics(dic, filter_select)
        total = dic["basic:sci"]
        count = np.sum([v for k, v in dic.items() if k != "basic:sci"])
    elif with_class:
        dic = add_tns_estimation(dic, class_select)
        total = dic["basic:sci"]
        count = np.sum([v for k, v in dic.items() if k != "basic:sci"])
    else:
        total = dic["basic:sci"]
        count = dic["basic:sci"]

    return total, count


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
                filt = elasticc_classes["classId"].astype(int) == int(elem)

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

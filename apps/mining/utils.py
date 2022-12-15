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
import requests
import json

def upload_file_hdfs(code, webhdfs, namenode, user, filename):
    """ Upload a file to HDFS

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
    ---------
    status_code: int
        HTTP status code. 201 is a success.
    text: str
        Additional information on the query (log).
    """
    try:
        response = requests.put(
            '{}/{}?op=CREATE&user.name={}&namenoderpcaddress={}&createflag=&createparent=true&overwrite=true'.format(webhdfs, filename, user, namenode),
            data=code,
        )
        status_code = response.status_code
        text = response.text
    except (requests.exceptions.ConnectionError, ConnectionRefusedError) as e:
        status_code = -1
        text = e

    if status_code != 201:
        print('Status code: {}'.format(status_code))
        print('Log: {}'.format(text))

    return status_code, text

def submit_spark_job(livyhost, filename, spark_conf):
    """ Submit a job on the Spark cluster via Livy (batch mode)

    Parameters
    ----------
    livyhost: str
        IP:HOST for the Livy service
    filename: str
        Path on HDFS with the file to submit. Format:
        hdfs://<path>/<filename>
    spark_conf: dict
        Dictionary with Spark configuration

    Returns
    ----------
    """
    headers = {'Content-Type': 'application/json'}

    data = {
    'conf': spark_conf,
    'file': filename
    }
    response = requests.post(
        livyhost + '/batches',
        data=json.dumps(data),
        headers=headers
    )

    batchid = response.json()['id']

    if status_code != 200:
        print('Batch ID {}'.format(batchid))
        print('Status code: {}'.format(response.status_code))
        print('Log: {}'.format(response.text))

    return batchid, response.status_code, response.text

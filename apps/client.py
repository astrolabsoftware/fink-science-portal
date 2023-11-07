# Copyright 2023 AstroLab Software
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
from apps import __file__ as apps_loc
import os
import jpype
import jpype.imports

import numpy as np

import yaml


def initialise_jvm(path=None):
    """ Start a JVM

    Parameters
    ----------
    path: str, optional
        Path to the HBase client. Default is relative to apps/
    """
    if not jpype.isJVMStarted():
        if path is None:
            path = os.path.dirname(apps_loc) + '/../bin/FinkBrowser.exe.jar'
        jarpath = "-Djava.class.path={}".format(path)
        jpype.startJVM(jpype.getDefaultJVMPath(), "-ea", jarpath, convertStrings=True)

    jpype.attachThreadToJVM()

def connect_to_hbase_table(tablename: str, nlimit=10000, setphysicalrepo=False, config_path=None):
    """ Return a client connected to a HBase table

    Parameters
    ----------
    tablename: str
        The name of the table
    nlimit: int, optional
        Maximum number of objects to return. Default is 10000
    setphysicalrepo: bool
        If True, store cutouts queried on disk ("/tmp/Lomikel/HBaseClientBinaryDataRepository")
        Needs client 02.01+. Default is False
    config_path: str, optional
        Path to the config file. Default is None (relative to the apps/ folder)
    """
    initialise_jvm()

    if config_path is None:
        config_path = os.path.dirname(apps_loc) + '/../config.yml'
    args = yaml.load(
        open(config_path),
        yaml.Loader
    )

    import com.Lomikel.HBaser
    from com.astrolabsoftware.FinkBrowser.Utils import Init

    Init.init()

    client = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
    client.connect(tablename, args['SCHEMAVER'])
    if setphysicalrepo:
        import com.Lomikel.HBaser.FilesBinaryDataRepository
        client.setRepository(com.Lomikel.HBaser.FilesBinaryDataRepository())
    client.setLimit(nlimit)

    return client

def create_or_update_hbase_table(tablename: str, families: list, schema: dict, create=False, config_path=None):
    """ Create or update a table in HBase

    By default (create=False), it will only update the schema of the table
    otherwise it will create the table in HBase and push the schema. The schema
    has a rowkey `schema`.

    Currently accepts only a single family name

    Parameters
    ----------
    tablename: str
        The name of the table
    families: list
        List of family names, e.g. ['d']
    schema: dict
        Dictionary with column names (keys) and column types (values)
    create: bool
        If true, create the table. Default is False (only update schema)
    config_path: str, optional
        Path to the config file. Default is None (relative to the apps/ folder)
    """
    if len(np.unique(families)) != 1:
        raise NotImplementedError("`create_hbase_table` only accepts one family name")

    initialise_jvm()

    if config_path is None:
        config_path = os.path.dirname(apps_loc) + '/../config.yml'
    args = yaml.load(
        open(config_path),
        yaml.Loader
    )

    import com.Lomikel.HBaser
    from com.astrolabsoftware.FinkBrowser.Utils import Init

    Init.init()

    client = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);

    if create:
        # Create the table and connect without schema
        client.create(tablename, families)
        client.connect(tablename)
    else:
        # Connect by ignoring the current schema
        client.connect(tablename, None)

    # Push the schema
    out = ['{}:{}:{}'.format(families[0], colname, coltype) for colname, coltype in schema.items()]
    client.put('schema', out)

    client.close()
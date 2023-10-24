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
import jpype
import jpype.imports

import yaml


def initialise_jvm():
    """
    """
    if not jpype.isJVMStarted():
        jarpath = "-Djava.class.path=../bin/FinkBrowser.exe.jar"
        jpype.startJVM(jpype.getDefaultJVMPath(), "-ea", jarpath, convertStrings=True)

    jpype.attachThreadToJVM()

def connect_to_hbase_table(tablename: str, nlimit=10000):
    """ Return a client connected to a HBase table

    Parameters
    ----------
    tablename: str
        The name of the table
    """
    initialise_jvm()

    args = yaml.load(open('../config.yml'), yaml.Loader)

    import com.Lomikel.HBaser
    from com.astrolabsoftware.FinkBrowser.Utils import Init

    Init.init()

    client = com.Lomikel.HBaser.HBaseClient(args['HBASEIP'], args['ZOOPORT']);
    client.connect(tablename, args['SCHEMAVER'])
    client.setLimit(nlimit)

    return client
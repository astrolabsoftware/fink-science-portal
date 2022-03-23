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
import java

import pandas as pd
import numpy as np

from app import client
from app import clientU, clientUV
from app import nlimit

from apps.utils import format_hbase_output
from apps.utils import extract_cutouts

def return_object_pdf(objectids, withupperlim=False, withcutouts=False, cols='*'):
    """ Make a query in HBase and format it in a Pandas dataframe

    Parameters
    ----------
    objectids: list
        List of ZTF objectId
    withupperlim: bool
        If True, add upper limit measurements. Default is False.
    withcutouts: bool
        If True, add cutouts. Default is False.
    cols: str
        Comma-separated list of alert fields to transfer.
        Default is all columns `cols='*'`

    Return
    ----------
    out: pandas dataframe
    """
    if cols == '*':
        truncated = False
    else:
        truncated = True

    # Get data from the main table
    results = java.util.TreeMap()
    for to_evaluate in objectids:
        result = client.scan(
            "",
            to_evaluate,
            cols,
            0, True, True
        )
        results.putAll(result)

    schema_client = client.schema()

    # reset the limit in case it has been changed above
    client.setLimit(nlimit)

    pdf = format_hbase_output(
        results, schema_client, group_alerts=False, truncated=truncated
    )

    if withcutouts:
        pdf = extract_cutouts(pdf, client)

    if withupperlim:
        # upper limits
        resultsU = java.util.TreeMap()
        for to_evaluate in objectids:
            resultU = clientU.scan(
                "",
                to_evaluate,
                "*",
                0, False, False
            )
            resultsU.putAll(resultU)

        # bad quality
        resultsUP = java.util.TreeMap()
        for to_evaluate in objectids:
            resultUP = clientUV.scan(
                "",
                to_evaluate,
                "*",
                0, False, False
            )
            resultsUP.putAll(resultUP)

        pdfU = pd.DataFrame.from_dict(resultsU, orient='index')
        pdfUP = pd.DataFrame.from_dict(resultsUP, orient='index')

        pdf['d:tag'] = 'valid'
        pdfU['d:tag'] = 'upperlim'
        pdfUP['d:tag'] = 'badquality'

        if 'i:jd' in pdfUP.columns:
            # workaround -- see https://github.com/astrolabsoftware/fink-science-portal/issues/216
            mask = np.array([False if float(i) in pdf['i:jd'].values else True for i in pdfUP['i:jd'].values])
            pdfUP = pdfUP[mask]

        pdf_ = pd.concat((pdf, pdfU, pdfUP), axis=0)

        # replace
        if 'i:jd' in pdf_.columns:
            pdf_['i:jd'] = pdf_['i:jd'].astype(float)
            pdf = pdf_.sort_values('i:jd', ascending=False)
        else:
            pdf = pdf_

    return pdf

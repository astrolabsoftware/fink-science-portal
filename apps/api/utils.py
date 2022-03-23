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
import healpy as hp

from astropy.coordinates import SkyCoord
from astropy.time import Time, TimeDelta

from app import client
from app import clientU, clientUV
from app import clientP128, clientP4096, clientP131072
from app import clientT
from app import nlimit

from apps.utils import format_hbase_output
from apps.utils import extract_cutouts

from flask import Response

def return_object_pdf(payload: dict) -> pd.DataFrame:
    """ Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/objects

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/objects

    Return
    ----------
    out: pandas dataframe
    """
    if 'columns' in payload:
        cols = payload['columns'].replace(" ", "")
    else:
        cols = '*'

    if ',' in payload['objectId']:
        # multi-objects search
        splitids = payload['objectId'].split(',')
        objectids = ['key:key:{}'.format(i.strip()) for i in splitids]
    else:
        # single object search
        objectids = ["key:key:{}".format(payload['objectId'])]

    if 'withcutouts' in payload and str(payload['withcutouts']) == 'True':
        withcutouts = True
    else:
        withcutouts = False

    if 'withupperlim' in payload and str(payload['withupperlim']) == 'True':
        withupperlim = True
    else:
        withupperlim = False

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

def return_explorer_pdf(payload: dict) -> pd.DataFrame:
    """ Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/explorer

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/explorer

    Return
    ----------
    out: pandas dataframe
    """
    if user_group == 0:
        # objectId search
        to_evaluate = "key:key:{}".format(payload['objectId'])

        results = client.scan(
            "",
            to_evaluate,
            "*",
            0, True, True
        )
        # reset the limit in case it has been changed above
        client.setLimit(nlimit)

        schema_client = client.schema()
    if user_group == 1:
        # Interpret user input
        ra, dec = payload['ra'], payload['dec']
        radius = payload['radius']

        if 'startdate_conesearch' in payload:
            startdate = payload['startdate_conesearch']
        else:
            startdate = None
        if 'window_days_conesearch' in payload and payload['window_days_conesearch'] is not None:
            window_days = float(payload['window_days_conesearch'])
        else:
            window_days = 1.0

        if float(radius) > 18000.:
            rep = {
                'status': 'error',
                'text': "`radius` cannot be bigger than 18,000 arcseconds (5 degrees).\n"
            }
            return Response(str(rep), 400)

        try:
            if 'h' in str(ra):
                coord = SkyCoord(ra, dec, frame='icrs')
            elif ':' in str(ra) or ' ' in str(ra):
                coord = SkyCoord(ra, dec, frame='icrs', unit=(u.hourangle, u.deg))
            else:
                coord = SkyCoord(ra, dec, frame='icrs', unit='deg')
        except ValueError as e:
            rep = {
                'status': 'error',
                'text': e
            }
            return Response(str(rep), 400)

        ra = coord.ra.deg
        dec = coord.dec.deg
        radius_deg = float(radius) / 3600.

        # angle to vec conversion
        vec = hp.ang2vec(np.pi / 2.0 - np.pi / 180.0 * dec, np.pi / 180.0 * ra)

        # Send request
        if float(radius) <= 30.:
            nside = 131072
            clientP_ = clientP131072
        elif (float(radius) > 30.) & (float(radius) <= 1000.):
            nside = 4096
            clientP_ = clientP4096
        else:
            nside = 128
            clientP_ = clientP128

        pixs = hp.query_disc(
            nside,
            vec,
            np.pi / 180 * radius_deg,
            inclusive=True
        )

        # For the future: we could set clientP_.setRangeScan(True)
        # and pass directly the time boundaries here instead of
        # grouping by later.

        # Filter by time - logic to be improved...
        if startdate is not None:
            if ':' in str(startdate):
                jdstart = Time(startdate).jd
            elif str(startdate).startswith('24'):
                jdstart = Time(startdate, format='jd').jd
            else:
                jdstart = Time(startdate, format='mjd').jd
            jdend = jdstart + window_days

            clientP_.setRangeScan(True)
            results = java.util.TreeMap()
            for pix in pixs:
                to_search = "key:key:{}_{},key:key:{}_{}".format(pix, jdstart, pix, jdend)
                result = clientP_.scan(
                    "",
                    to_search,
                    "*",
                    0, True, True
                )
                results.putAll(result)
            clientP_.setRangeScan(False)
        else:
            to_evaluate = ",".join(
                [
                    'key:key:{}'.format(i) for i in pixs
                ]
            )
            # Get matches in the pixel index table
            results = clientP_.scan(
                "",
                to_evaluate,
                "*",
                0, True, True
            )

        # extract objectId and times
        objectids = [i[1]['i:objectId'] for i in results.items()]
        times = [float(i[1]['key:key'].split('_')[1]) for i in results.items()]
        pdf_ = pd.DataFrame({'oid': objectids, 'jd': times})

        # Filter by time - logic to be improved...
        if startdate is not None:
            pdf_ = pdf_[(pdf_['jd'] >= jdstart) & (pdf_['jd'] < jdstart + window_days)]

        # groupby and keep only the last alert per objectId
        pdf_ = pdf_.loc[pdf_.groupby('oid')['jd'].idxmax()]

        # Get data from the main table
        results = java.util.TreeMap()
        for oid, jd in zip(pdf_['oid'].values, pdf_['jd'].values):
            to_evaluate = "key:key:{}_{}".format(oid, jd)

            result = client.scan(
                "",
                to_evaluate,
                "*",
                0, True, True
            )
            results.putAll(result)
        schema_client = client.schema()
    elif user_group == 2:
        if int(payload['window']) > 180:
            rep = {
                'status': 'error',
                'text': "`window` cannot be bigger than 180 minutes.\n"
            }
            return Response(str(rep), 400)
        # Time to jd
        jd_start = Time(payload['startdate']).jd
        jd_end = jd_start + TimeDelta(int(payload['window']) * 60, format='sec').jd

        # Send the request. RangeScan.
        clientT.setRangeScan(True)
        to_evaluate = "key:key:{},key:key:{}".format(jd_start, jd_end)
        results = clientT.scan(
            "",
            to_evaluate,
            "*",
            0, True, True
        )
        schema_client = clientT.schema()

    # reset the limit in case it has been changed above
    client.setLimit(nlimit)

    pdfs = format_hbase_output(
        results,
        schema_client,
        group_alerts=True,
        extract_color=False
    )

    # For conesearch, sort by distance
    if (user_group == 1) and (len(pdfs) > 0):
        sep = coord.separation(
            SkyCoord(
                pdfs['i:ra'],
                pdfs['i:dec'],
                unit='deg'
            )
        ).deg

        pdfs['v:separation_degree'] = sep
        pdfs = pdfs.sort_values('v:separation_degree', ascending=True)

        mask = pdfs['v:separation_degree'] > radius_deg
        pdfs = pdfs[~mask]

    return pdfs

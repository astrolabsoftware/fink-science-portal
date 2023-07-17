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
import io
import java
import gzip
import yaml
import requests

import pandas as pd
import numpy as np
import healpy as hp

from PIL import Image as im
from matplotlib import cm

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time, TimeDelta
from astropy.io import fits, votable
from astropy.table import Table

from app import client
from app import clientU, clientUV
from app import clientP128
from app import clientT, clientTNS, clientS, clientSSO, clientTRCK
from app import clientSSOCAND, clientSSOORB
from app import clientStats
from app import clientANOMALY
from app import clientTNSRESOL
from app import nlimit
from app import APIURL

from apps.utils import get_miriade_data
from apps.utils import format_hbase_output
from apps.utils import extract_cutouts
from apps.utils import hbase_type_converter

from apps.plotting import legacy_normalizer, convolve, sigmoid_normalizer

from flask import Response
from flask import send_file

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

def return_explorer_pdf(payload: dict, user_group: int) -> pd.DataFrame:
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
    truncated = False
    if user_group == 0:
        results = java.util.TreeMap()
        for oid in payload['objectId'].split(','):
            # objectId search
            to_evaluate = "key:key:{}".format(oid.strip())
            result = client.scan(
                "",
                to_evaluate,
                "*",
                0, True, True
            )
            results.putAll(result)

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
        nside = 128

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

            clientP128.setRangeScan(True)
            results = java.util.TreeMap()
            for pix in pixs:
                to_search = "key:key:{}_{},key:key:{}_{}".format(pix, jdstart, pix, jdend)
                result = clientP128.scan(
                    "",
                    to_search,
                    "*",
                    0, True, True
                )
                results.putAll(result)
            clientP128.setRangeScan(False)
        else:
            results = java.util.TreeMap()
            for pix in pixs:
                to_search = "key:key:{}".format(pix)
                result = clientP128.scan(
                    "",
                    to_search,
                    "*",
                    0, True, True
                )
                results.putAll(result)

        schema_client = clientP128.schema()
        truncated = True
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
        truncated=truncated,
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

def return_latests_pdf(payload: dict, return_raw: bool = False) -> pd.DataFrame:
    """ Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/latests

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/latests
    return_raw: bool
        If True, return the HBase output, else pandas DataFrame. Default is False.

    Return
    ----------
    out: pandas dataframe
    """
    if 'n' not in payload:
        nalerts = 10
    else:
        nalerts = int(payload['n'])

    if 'startdate' not in payload:
        # start of the Fink operations
        jd_start = Time('2019-11-01 00:00:00').jd
    else:
        jd_start = Time(payload['startdate']).jd

    if 'stopdate' not in payload:
        jd_stop = Time.now().jd
    else:
        jd_stop = Time(payload['stopdate']).jd

    if 'color' not in payload:
        color = False
    else:
        color = True

    if 'columns' in payload:
        cols = payload['columns'].replace(" ", "")
    else:
        cols = '*'

    if cols == '*':
        truncated = False
    else:
        truncated = True

    # Search for latest alerts for a specific class
    tns_classes = pd.read_csv('assets/tns_types.csv', header=None)[0].values
    is_tns = payload['class'].startswith('(TNS)') and (payload['class'].split('(TNS) ')[1] in tns_classes)
    if is_tns:
        classname = payload['class'].split('(TNS) ')[1]
        clientTNS.setLimit(nalerts)
        clientTNS.setRangeScan(True)
        clientTNS.setReversed(True)

        results = clientTNS.scan(
            "",
            "key:key:{}_{},key:key:{}_{}".format(
                classname,
                jd_start,
                classname,
                jd_stop
            ),
            cols, 0, True, True
        )
        schema_client = clientTNS.schema()
        group_alerts = True
        clientTNS.setLimit(nlimit)
    elif payload['class'].startswith('(SIMBAD)') or payload['class'] != 'allclasses':
        if payload['class'].startswith('(SIMBAD)'):
            classname = payload['class'].split('(SIMBAD) ')[1]
        else:
            classname = payload['class']

        clientS.setLimit(nalerts)
        clientS.setRangeScan(True)
        clientS.setReversed(True)

        results = clientS.scan(
            "",
            "key:key:{}_{},key:key:{}_{}".format(
                classname,
                jd_start,
                classname,
                jd_stop
            ),
            cols, 0, False, False
        )
        schema_client = clientS.schema()
        group_alerts = False
        clientS.setLimit(nlimit)
    elif payload['class'] == 'allclasses':
        clientT.setLimit(nalerts)
        clientT.setRangeScan(True)
        clientT.setReversed(True)

        to_evaluate = "key:key:{},key:key:{}".format(jd_start, jd_stop)
        results = clientT.scan(
            "",
            to_evaluate,
            cols,
            0, True, True
        )
        schema_client = clientT.schema()
        group_alerts = False

        # Restore default limits
        clientT.setLimit(nlimit)

    if return_raw:
        return results

    # We want to return alerts
    # color computation is disabled
    pdfs = format_hbase_output(
        results, schema_client,
        group_alerts=group_alerts,
        extract_color=color,
        truncated=truncated,
        with_constellation=True
    )

    return pdfs

def return_sso_pdf(payload: dict) -> pd.DataFrame:
    """ Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/sso

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/sso

    Return
    ----------
    out: pandas dataframe
    """
    if 'columns' in payload:
        cols = payload['columns'].replace(' ', '')
    else:
        cols = '*'

    if cols == '*':
        truncated = False
    else:
        truncated = True

    if ',' in payload['n_or_d']:
        # multi-objects search
        splitids = payload['n_or_d'].replace(' ', '').split(',')

        # Note the trailing _ to avoid mixing e.g. 91 and 915 in the same query
        names = ['key:key:{}_'.format(i.strip()) for i in splitids]
    else:
        # single object search
        # Note the trailing _ to avoid mixing e.g. 91 and 915 in the same query
        names = ["key:key:{}_".format(payload['n_or_d'].replace(' ', ''))]

    # Get data from the main table
    results = java.util.TreeMap()
    for to_evaluate in names:
        result = clientSSO.scan(
            "",
            to_evaluate,
            cols,
            0, True, True
        )
        results.putAll(result)

    schema_client = clientSSO.schema()

    # reset the limit in case it has been changed above
    clientSSO.setLimit(nlimit)

    pdf = format_hbase_output(
        results,
        schema_client,
        group_alerts=False,
        truncated=truncated,
        extract_color=False
    )

    if 'withEphem' in payload:
        if payload['withEphem'] == 'True' or payload['withEphem'] is True:
            # We should probably add a timeout
            # and try/except in case of miriade shutdown
            pdf = get_miriade_data(pdf)

    return pdf

def return_ssocand_pdf(payload: dict) -> pd.DataFrame:
    """ Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/ssocand

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/ssocand

    Return
    ----------
    out: pandas dataframe
    """
    if 'ssoCandId' in payload:
        trajectory_id = str(payload['ssoCandId'])
    else:
        trajectory_id = None

    payload_name = payload['kind']

    if payload_name == 'orbParams':
        gen_client = clientSSOORB

        if trajectory_id is not None:
            to_evaluate = "key:key:cand_{}".format(trajectory_id)
        else:
            to_evaluate = "key:key:cand_"
    elif payload_name == 'lightcurves':
        gen_client = clientSSOCAND

        if 'start_date' in payload:
            start_date = Time(payload['start_date'], format='iso').jd
        else:
            start_date = Time('2019-11-01', format='iso').jd

        if 'stop_date' in payload:
            stop_date = Time(payload['stop_date'], format='iso').jd
        else:
            stop_date = Time.now().jd

        gen_client.setRangeScan(True)

        if trajectory_id is not None:
            gen_client.setEvaluation("ssoCandId.equals('{}')".format(trajectory_id))

        to_evaluate = "key:key:{}_,key:key:{}_".format(start_date, stop_date)

    results = gen_client.scan(
        "",
        to_evaluate,
        '*',
        0, False, False
    )

    schema_client = gen_client.schema()

    # reset the limit in case it has been changed above
    gen_client.setLimit(nlimit)
    gen_client.setEvaluation("")

    if results.isEmpty():
        return pd.DataFrame({})

    # Construct the dataframe
    pdf = pd.DataFrame.from_dict(results, orient='index')

    # Type conversion
    pdf = pdf.astype(
        {i: hbase_type_converter[schema_client.type(i)] for i in pdf.columns}
    )

    return pdf

def return_tracklet_pdf(payload: dict) -> pd.DataFrame:
    """ Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/tracklet

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/tracklet

    Return
    ----------
    out: pandas dataframe
    """
    if 'columns' in payload:
        cols = payload['columns'].replace(" ", "")
    else:
        cols = '*'

    if cols == '*':
        truncated = False
    else:
        truncated = True

    if 'date' in payload:
        designation = payload['date']
    else:
        rep = {
            'status': 'error',
            'text': "You need tp specify a date at the format YYYY-MM-DD hh:mm:ss\n"
        }
        return Response(str(rep), 400)

    payload_name = 'TRCK_' + designation.replace('-', '').replace(':', '').replace(' ', '_')

    # Note the trailing _
    to_evaluate = "key:key:{}".format(payload_name)

    results = clientTRCK.scan(
        "",
        to_evaluate,
        cols,
        0, True, True
    )

    schema_client = clientTRCK.schema()

    # reset the limit in case it has been changed above
    clientTRCK.setLimit(nlimit)

    pdf = format_hbase_output(
        results,
        schema_client,
        group_alerts=False,
        truncated=truncated,
        extract_color=False
    )

    return pdf

def format_and_send_cutout(payload: dict) -> pd.DataFrame:
    """ Extract data returned by HBase and jsonify it

    Data is from /api/v1/cutouts

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/cutouts

    Return
    ----------
    out: pandas dataframe
    """
    output_format = payload.get('output-format', 'PNG')

    # default stretch is sigmoid
    if 'stretch' in payload:
        stretch = payload['stretch']
    else:
        stretch = 'sigmoid'

    # default name based on parameters
    filename = '{}_{}'.format(
        payload['objectId'],
        payload['kind']
    )

    if output_format == 'PNG':
        filename = filename + '.png'
    elif output_format == 'JPEG':
        filename = filename + '.jpg'
    elif output_format == 'FITS':
        filename = filename + '.fits'

    # Query the Database (object query)
    results = client.scan(
        "",
        "key:key:{}".format(payload['objectId']),
        "b:cutout{}_stampData,i:jd,i:candid".format(payload['kind']),
        0, True, True
    )

    # Format the results
    schema_client = client.schema()
    pdf = format_hbase_output(
        results, schema_client,
        group_alerts=False,
        truncated=True,
        extract_color=False
    )

    # Extract only the alert of interest
    if 'candid' in payload:
        pdf = pdf[pdf['i:candid'].astype(str) == str(payload['candid'])]
    else:
        # pdf has been sorted in `format_hbase_output`
        pdf = pdf.iloc[0:1]

    if pdf.empty:
        return send_file(
            io.BytesIO(),
            mimetype='image/png',
            as_attachment=True,
            attachment_filename=filename
        )
    # Extract cutouts
    if output_format == 'FITS':
        pdf = extract_cutouts(
            pdf,
            client,
            col='b:cutout{}_stampData'.format(payload['kind']),
            return_type='FITS'
        )
    else:
        pdf = extract_cutouts(
            pdf,
            client,
            col='b:cutout{}_stampData'.format(payload['kind']),
            return_type='array'
        )

    array = pdf['b:cutout{}_stampData'.format(payload['kind'])].values[0]

    # send the FITS file
    if output_format == 'FITS':
        return send_file(
            array,
            mimetype='application/octet-stream',
            as_attachment=True,
            attachment_filename=filename
        )
    # send the array
    elif output_format == 'array':
        return pdf[['b:cutout{}_stampData'.format(payload['kind'])]].to_json(orient='records')

    array = np.nan_to_num(np.array(array, dtype=float))
    if stretch == 'sigmoid':
        array = sigmoid_normalizer(array, 0, 1)
    elif stretch is not None:
        pmin = 0.5
        if 'pmin' in payload:
            pmin = float(payload['pmin'])
        pmax = 99.5
        if 'pmax' in payload:
            pmax = float(payload['pmax'])
        array = legacy_normalizer(array, stretch=stretch, pmin=pmin, pmax=pmax)

    if 'convolution_kernel' in payload:
        assert payload['convolution_kernel'] in ['gauss', 'box']
        array = convolve(array, smooth=1, kernel=payload['convolution_kernel'])

    # colormap
    if "colormap" in payload:
        colormap = getattr(cm, payload['colormap'])
    else:
        colormap = lambda x: x
    array = np.uint8(colormap(array) * 255)

    # Convert to PNG
    data = im.fromarray(array)
    datab = io.BytesIO()
    data.save(datab, format='PNG')
    datab.seek(0)
    return send_file(
        datab,
        mimetype='image/png',
        as_attachment=True,
        attachment_filename=filename)

def perform_xmatch(payload: dict) -> pd.DataFrame:
    """ Extract data returned by HBase and jsonify it

    Data is from /api/v1/xmatch

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/xmatch

    Return
    ----------
    out: pandas dataframe
    """
    df = pd.read_csv(io.StringIO(payload['catalog']))

    radius = float(payload['radius'])
    if radius > 18000.:
        rep = {
            'status': 'error',
            'text': "`radius` cannot be bigger than 18,000 arcseconds (5 degrees).\n"
        }
        return Response(str(rep), 400)

    header = payload['header']

    header = [i.strip() for i in header.split(',')]
    if len(header) == 3:
        raname, decname, idname = header
    elif len(header) == 4:
        raname, decname, idname, timename = header
    else:
        rep = {
            'status': 'error',
            'text': "Header should contain 3 or 4 entries from your catalog. E.g. RA,DEC,ID or RA,DEC,ID,Time\n"
        }
        return Response(str(rep), 400)

    if 'window' in payload:
        window_days = payload['window']
    else:
        window_days = None

    # Fink columns of interest
    colnames = [
        'i:objectId', 'i:ra', 'i:dec', 'i:jd', 'd:cdsxmatch', 'i:ndethist'
    ]

    colnames_added_values = [
        'd:cdsxmatch',
        'd:roid',
        'd:mulens_class_1',
        'd:mulens_class_2',
        'd:snn_snia_vs_nonia',
        'd:snn_sn_vs_all',
        'd:rf_snia_vs_nonia',
        'i:ndethist',
        'i:drb',
        'i:classtar',
        'd:rf_kn_vs_nonkn',
        'i:jdstarthist'
    ]

    unique_cols = np.unique(colnames + colnames_added_values).tolist()

    # check units
    ra0 = df[raname].values[0]
    if 'h' in str(ra0):
        coords = [
            SkyCoord(ra, dec, frame='icrs')
            for ra, dec in zip(df[raname].values, df[decname].values)
        ]
    elif ':' in str(ra0) or ' ' in str(ra0):
        coords = [
            SkyCoord(ra, dec, frame='icrs', unit=(u.hourangle, u.deg))
            for ra, dec in zip(df[raname].values, df[decname].values)
        ]
    else:
        coords = [
            SkyCoord(ra, dec, frame='icrs', unit='deg')
            for ra, dec in zip(df[raname].values, df[decname].values)
        ]
    ras = [coord.ra.deg for coord in coords]
    decs = [coord.dec.deg for coord in coords]
    ids = df[idname].values

    if len(header) == 4:
        times = df[timename].values
    else:
        times = np.zeros_like(ras)

    pdfs = pd.DataFrame(columns=unique_cols + [idname] + ['v:classification'])
    for oid, ra, dec, time_start in zip(ids, ras, decs, times):
        if len(header) == 4:
            payload_data = {
                'ra': ra,
                'dec': dec,
                'radius': radius,
                'startdate_conesearch': time_start,
                'window_days_conesearch': window_days

            }
        else:
            payload_data = {
                'ra': ra,
                'dec': dec,
                'radius': radius
            }
        r = requests.post(
            '{}/api/v1/explorer'.format(APIURL),
            json=payload_data
        )
        pdf = pd.read_json(r.content)

        # Loop over results and construct the dataframe
        if not pdf.empty:
            pdf[idname] = [oid] * len(pdf)
            if 'd:rf_kn_vs_nonkn' not in pdf.columns:
                pdf['d:rf_kn_vs_nonkn'] = np.zeros(len(pdf), dtype=float)
            pdfs = pd.concat((pdfs, pdf), ignore_index=True)

    # Final join
    join_df = pd.merge(
        pdfs,
        df,
        on=idname
    )

    # reorganise columns order
    no_duplicate = np.where(pdfs.columns != idname)[0]
    cols = list(df.columns) + list(pdfs.columns[no_duplicate])
    join_df = join_df[cols]

    return join_df.to_json(orient='records')

def return_bayestar_pdf(payload: dict) -> pd.DataFrame:
    """ Extract data returned by HBase and jsonify it

    Data is from /api/v1/bayestar

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/bayestar

    Return
    ----------
    out: pandas dataframe
    """
    # boundaries in day
    n_day_min = 1
    n_day_max = 6

    # Interpret user input
    if 'bayestar' in payload:
        bayestar_data = payload['bayestar']
    elif 'event_name' in payload:
        r = requests.get('https://gracedb.ligo.org/api/superevents/{}/files/bayestar.fits.gz'.format(payload['event_name']))
        if r.status_code == 200:
            bayestar_data = str(r.content)
        else:
            return pd.DataFrame([{'status': r.content}])
    credible_level_threshold = float(payload['credible_level'])

    with gzip.open(io.BytesIO(eval(bayestar_data)), 'rb') as f:
        with fits.open(io.BytesIO(f.read())) as hdul:
            data = hdul[1].data
            header = hdul[1].header

    hpx = data['PROB']
    if header['ORDERING'] == 'NESTED':
        hpx = hp.reorder(hpx, n2r=True)

    i = np.flipud(np.argsort(hpx))
    sorted_credible_levels = np.cumsum(hpx[i])
    credible_levels = np.empty_like(sorted_credible_levels)
    credible_levels[i] = sorted_credible_levels

    # TODO: use that to define the max skyfrac (in conjunction with level)
    # npix = len(hpx)
    # nside = hp.npix2nside(npix)
    # skyfrac = np.sum(credible_levels <= 0.1) * hp.nside2pixarea(nside, degrees=True)

    credible_levels_128 = hp.ud_grade(credible_levels, 128)

    pixs = np.where(credible_levels_128 <= credible_level_threshold)[0]

    # make a condition as well on the number of pixels?
    # print(len(pixs), pixs)

    # For the future: we could set clientP128.setRangeScan(True)
    # and pass directly the time boundaries here instead of
    # grouping by later.

    # 1 day before the event, to 6 days after the event
    jdstart = Time(header['DATE-OBS']).jd - n_day_min
    jdend = jdstart + n_day_max

    clientP128.setRangeScan(True)
    results = java.util.TreeMap()
    for pix in pixs:
        to_search = "key:key:{}_{},key:key:{}_{}".format(pix, jdstart, pix, jdend)
        result = clientP128.scan(
            "",
            to_search,
            "*",
            0, True, True
        )
        results.putAll(result)

    clientP128.setRangeScan(False)
    schema_client = clientP128.schema()

    pdfs = format_hbase_output(
        results,
        schema_client,
        truncated=True,
        group_alerts=True,
        extract_color=False
    )

    if pdfs.empty:
        return pdfs

    pdfs['v:jdstartgw'] = Time(header['DATE-OBS']).jd

    # remove alerts with clear wrong jdstarthist
    mask = (pdfs['i:jd'] - pdfs['i:jdstarthist']) <= n_day_max

    return pdfs[mask]

def return_statistics_pdf(payload: dict) -> pd.DataFrame:
    """ Extract data returned by HBase and jsonify it

    Data is from /api/v1/statistics

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/statistics

    Return
    ----------
    out: pandas dataframe
    """
    if 'columns' in payload:
        cols = payload['columns']
    else:
        cols = '*'

    payload_date = payload['date']

    to_evaluate = "key:key:ztf_{}".format(payload_date)

    results = clientStats.scan(
        "",
        to_evaluate,
        cols,
        0, True, True
    )

    pdf = pd.DataFrame.from_dict(results, orient='index')

    return pdf

def send_data(pdf, output_format):
    """
    """
    if output_format == 'json':
        return pdf.to_json(orient='records')
    elif output_format == 'csv':
        return pdf.to_csv(index=False)
    elif output_format == 'votable':
        f = io.BytesIO()
        table = Table.from_pandas(pdf)
        vt = votable.from_table(table)
        votable.writeto(vt, f)
        f.seek(0)
        return f.read()
    elif output_format == 'parquet':
        f = io.BytesIO()
        pdf.to_parquet(f)
        f.seek(0)
        return f.read()

    rep = {
        'status': 'error',
        'text': "Output format `{}` is not supported. Choose among json, csv, or parquet\n".format(output_format)
    }
    return Response(str(rep), 400)

def return_random_pdf(payload: dict) -> pd.DataFrame:
    """ Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/random

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/random

    Return
    ----------
    out: pandas dataframe
    """
    if 'columns' in payload:
        cols = payload['columns'].replace(" ", "")
    else:
        cols = '*'

    if 'class' in payload and str(payload['class']) != "":
        classsearch = True
    else:
        classsearch = False

    if cols == '*':
        truncated = False
    else:
        truncated = True

    if int(payload['n']) > 16:
        number = 16
    else:
        number = int(payload['n'])

    seed = payload.get('seed', None)
    if seed is not None:
        np.random.seed(int(payload['seed']))

    # logic
    results = []
    clientT.setLimit(1000)
    clientT.setRangeScan(True)

    jd_low = Time('2019-11-02 03:00:00.0').jd
    jd_high = Time.now().jd

    # 1 month
    delta_min = 43200
    delta_jd = TimeDelta(delta_min * 60, format='sec').jd
    while len(results) == 0:
        jdstart = np.random.uniform(jd_low, jd_high)
        jdstop = jdstart + delta_jd

        if classsearch:
            payload_data = {
                'class': payload['class'],
                'n': number,
                'startdate': Time(jdstart, format='jd').iso,
                'stopdate': Time(jdstop, format='jd').iso,
                'columns': "",
                'output-format': 'json'
            }
            results = return_latests_pdf(payload_data, return_raw=True)
        else:
            results = clientT.scan(
                "",
                "key:key:{},key:key:{}".format(jdstart, jdstop),
                "", 0, False, False
            )

    oids = list(dict(results).keys())
    oids = np.array([i.split('_')[-1] for i in oids])

    index_oid = np.random.randint(0, len(oids), number)
    oid = oids[index_oid]

    client.setLimit(2000)
    # Get data from the main table
    results = java.util.TreeMap()
    for oid_ in oid:
        result = client.scan(
            "",
            "key:key:{}".format(oid_),
            "{}".format(cols),
            0, False, False
        )
        results.putAll(result)

    pdf = format_hbase_output(
        results, client.schema(), group_alerts=False, truncated=truncated
    )

    clientT.setLimit(nlimit)
    client.setLimit(nlimit)

    return pdf

def return_anomalous_objects_pdf(payload: dict) -> pd.DataFrame:
    """ Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/anomaly

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/anomaly

    Return
    ----------
    out: pandas dataframe
    """
    if 'n' not in payload:
        nalerts = 10
    else:
        nalerts = int(payload['n'])

    if 'start_date' not in payload:
        # start of the Fink operations
        jd_start = Time('2019-11-01 00:00:00').jd
    else:
        jd_start = Time(payload['start_date']).jd

    if 'stop_date' not in payload:
        jd_stop = Time.now().jd
    else:
        # allow to get unique day
        jd_stop = Time(payload['stop_date']).jd + 1

    if 'columns' in payload:
        cols = payload['columns'].replace(" ", "")
    else:
        cols = '*'

    if cols == '*':
        truncated = False
    else:
        truncated = True

    clientANOMALY.setLimit(nalerts)
    clientANOMALY.setRangeScan(True)
    clientANOMALY.setReversed(True)

    to_evaluate = "key:key:{},key:key:{}".format(jd_start, jd_stop)
    results = clientANOMALY.scan(
        "",
        to_evaluate,
        cols,
        0, True, True
    )
    schema_client = clientANOMALY.schema()

    # Restore default limits
    clientANOMALY.setLimit(nlimit)

    # We want to return alerts
    # color computation is disabled
    pdfs = format_hbase_output(
        results, schema_client,
        group_alerts=False,
        extract_color=False,
        truncated=truncated,
        with_constellation=True
    )

    return pdfs

def return_ssoft_pdf(payload: dict) -> pd.DataFrame:
    """ Send the Fink Flat Table

    Data is from /api/v1/ssoft

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/ssoft

    Return
    ----------
    out: pandas dataframe
    """
    input_args = yaml.load(open('config_datatransfer.yml'), yaml.Loader)
    r = requests.get(
        '{}/ssoft.parquet?op=OPEN&user.name={}&namenoderpcaddress={}'.format(
            input_args['WEBHDFS'],
            input_args['USER'],
            input_args['NAMENODE']
        )
    )

    pdf = pd.read_parquet(io.BytesIO(r.content))

    if 'sso_name' in payload:
        mask = pdf['sso_name'] == pdf['sso_name']
        pdf = pdf[mask]
        pdf = pdf[pdf['sso_name'].astype('str') == payload['sso_name']]
    elif 'sso_number' in payload:
        mask = pdf['sso_number'] == pdf['sso_number']
        pdf = pdf[mask]
        pdf = pdf[pdf['sso_number'].astype('int') == int(payload['sso_number'])]

    return pdf

def return_resolver_pdf(payload: dict) -> pd.DataFrame:
    """ Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/resolver

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/resolver

    Return
    ----------
    out: pandas dataframe
    """
    resolver = payload['resolver']
    name = payload['name']

    if resolver == 'tns':
        # TNS poll -- take the first 10 occurences
        clientTNSRESOL.setLimit(10)
        if 'reverse' in payload:
            to_evaluate = "d:internalname:{}".format(name)
            results = clientTNSRESOL.scan(
                "",
                to_evaluate,
                "*",
                0, False, False
            )
        else:
            to_evaluate = "key:key:{}".format(name)
            results = clientTNSRESOL.scan(
                "",
                to_evaluate,
                "*",
                0, False, False
            )

        # Restore default limits
        clientTNSRESOL.setLimit(nlimit)

        pdfs = pd.DataFrame.from_dict(results, orient='index')
    elif resolver == 'simbad':
        if 'reverse' in payload:
            to_evaluate = "key:key:{}".format(name)
            client.setLimit(10)
            results = client.scan(
                "",
                to_evaluate,
                "i:objectId,d:cdsxmatch,i:ra,i:dec",
                0, False, False
            )
            client.setLimit(nlimit)
            pdfs = pd.DataFrame.from_dict(results, orient='index')
        else:
            r = requests.get(
                'http://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/~S?{}'.format(name)
            )

            check = pd.read_xml(io.BytesIO(r.content))
            if 'Resolver' in check.columns:
                pdfs = pd.read_xml(io.BytesIO(r.content), xpath='.//Resolver')
            else:
                pdfs = pd.DataFrame()
    elif resolver == 'ssodnet':
        pass

    return pdfs

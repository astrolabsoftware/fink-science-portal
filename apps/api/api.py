# Copyright 2020-2022 AstroLab Software
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
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc

from flask import request, jsonify, Response
from flask import send_file

from PIL import Image as im
from matplotlib import cm

from app import client
from app import clientP128, clientP4096, clientP131072
from app import clientT, clientS
from app import clientSSO, clientTNS, clientTRCK
from app import clientU, clientUV, nlimit
from app import clientStats
from app import APIURL
from apps.utils import format_hbase_output
from apps.utils import extract_cutouts
from apps.utils import get_superpixels
from apps.utils import get_miriade_data
from apps.plotting import legacy_normalizer, convolve, sigmoid_normalizer

from apps.api.doc import api_doc_summary, api_doc_object, api_doc_explorer
from apps.api.doc import api_doc_latests, api_doc_sso, api_doc_tracklets
from apps.api.doc import api_doc_cutout, api_doc_xmatch, api_doc_bayestar, api_doc_stats

from apps.api.utils import return_object_pdf

import io
import requests
import java
import gzip

import healpy as hp
import pandas as pd
import numpy as np

import astropy.units as u
from astropy.time import Time, TimeDelta
from astropy.coordinates import SkyCoord
from astropy.table import Table
from astropy.io import fits

from flask import Blueprint

api_bp = Blueprint('', __name__)

def layout(is_mobile):
    if is_mobile:
        width = '95%'
    else:
        width = '80%'
    layout_ = html.Div(
        [
            html.Br(),
            html.Br(),
            html.Br(),
            dbc.Container(
                [
                    dbc.Row(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Markdown(api_doc_summary)
                                ), style={
                                    'backgroundColor': 'rgb(248, 248, 248, .7)'
                                }
                            ),
                        ]
                    ),
                    html.Br(),
                    dbc.Tabs(
                        [
                            dbc.Tab(
                                [
                                    dbc.Card(
                                        dbc.CardBody(
                                            dcc.Markdown(api_doc_object)
                                        ), style={
                                            'backgroundColor': 'rgb(248, 248, 248, .7)'
                                        }
                                    ),
                                ], label="Retrieve object data"
                            ),
                            dbc.Tab(
                                [
                                    dbc.Card(
                                        dbc.CardBody(
                                            dcc.Markdown(api_doc_explorer)
                                        ), style={
                                            'backgroundColor': 'rgb(248, 248, 248, .7)'
                                        }
                                    ),
                                ], label="Query the database"
                            ),
                            dbc.Tab(
                                [
                                    dbc.Card(
                                        dbc.CardBody(
                                            dcc.Markdown(api_doc_latests)
                                        ), style={
                                            'backgroundColor': 'rgb(248, 248, 248, .7)'
                                        }
                                    ),
                                ], label="Get latest alerts"
                            ),
                            dbc.Tab(
                                [
                                    dbc.Card(
                                        dbc.CardBody(
                                            dcc.Markdown(api_doc_sso)
                                        ), style={
                                            'backgroundColor': 'rgb(248, 248, 248, .7)'
                                        }
                                    ),
                                ], label="Get Solar System Objects"
                            ),
                            dbc.Tab(
                                [
                                    dbc.Card(
                                        dbc.CardBody(
                                            dcc.Markdown(api_doc_tracklets)
                                        ), style={
                                            'backgroundColor': 'rgb(248, 248, 248, .7)'
                                        }
                                    ),
                                ], label="Get Tracklet Objects"
                            ),
                            dbc.Tab(
                                [
                                    dbc.Card(
                                        dbc.CardBody(
                                            dcc.Markdown(api_doc_cutout)
                                        ), style={
                                            'backgroundColor': 'rgb(248, 248, 248, .7)'
                                        }
                                    ),
                                ], label="Get Image data"
                            ),
                            dbc.Tab(
                                [
                                    dbc.Card(
                                        dbc.CardBody(
                                            dcc.Markdown(api_doc_xmatch)
                                        ), style={
                                            'backgroundColor': 'rgb(248, 248, 248, .7)'
                                        }
                                    ),
                                ], label="Xmatch"
                            ),
                            dbc.Tab(
                                [
                                    dbc.Card(
                                        dbc.CardBody(
                                            dcc.Markdown(api_doc_bayestar)
                                        ), style={
                                            'backgroundColor': 'rgb(248, 248, 248, .7)'
                                        }
                                    ),
                                ], label="Gravitational Waves"
                            ),
                            dbc.Tab(
                                [
                                    dbc.Card(
                                        dbc.CardBody(
                                            dcc.Markdown(api_doc_stats)
                                        ), style={
                                            'backgroundColor': 'rgb(248, 248, 248, .7)'
                                        }
                                    ),
                                ], label="Statistics"
                            ),
                        ]
                    )
                ], className="mb-8", fluid=True, style={'width': width}
            )
        ], className='home', style={
            'background-image': 'linear-gradient(rgba(255,255,255,0.5), rgba(255,255,255,0.5)), url(/assets/background.png)',
            'background-size': 'contain'
        }
    )
    return layout_


args_objects = [
    {
        'name': 'objectId',
        'required': True,
        'description': 'single ZTF Object ID, or a comma-separated list of object names, e.g. "ZTF19acmdpyr,ZTF21aaxtctv"'
    },
    {
        'name': 'withupperlim',
        'required': False,
        'description': 'If True, retrieve also upper limit measurements, and bad quality measurements. Use the column `d:tag` in your results: valid, upperlim, badquality.'
    },
    {
        'name': 'withcutouts',
        'required': False,
        'description': 'If True, retrieve also uncompressed FITS cutout data (2D array).'
    },
    {
        'name': 'columns',
        'required': False,
        'description': 'Comma-separated data columns to transfer. Default is all columns. See {}/api/v1/columns for more information.'.format(APIURL)
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet'
    }
]

args_explorer = [
    {
        'name': 'objectId',
        'required': True,
        'group': 0,
        'description': 'ZTF Object ID'
    },
    {
        'name': 'ra',
        'required': True,
        'group': 1,
        'description': 'Right Ascension'
    },
    {
        'name': 'dec',
        'required': True,
        'group': 1,
        'description': 'Declination'
    },
    {
        'name': 'radius',
        'required': True,
        'group': 1,
        'description': 'Conesearch radius in arcsec. Maximum is 36,000 arcseconds (10 degrees).'
    },
    {
        'name': 'startdate_conesearch',
        'required': False,
        'group': 1,
        'description': '[Optional] Starting date in UTC for the conesearch query.'
    },
    {
        'name': 'window_days_conesearch',
        'required': False,
        'group': 1,
        'description': '[Optional] Time window in days for the conesearch query.'
    },
    {
        'name': 'startdate',
        'required': True,
        'group': 2,
        'description': 'Starting date in UTC'
    },
    {
        'name': 'window',
        'required': True,
        'group': 2,
        'description': 'Time window in minutes. Maximum is 180 minutes.'
    },
    {
        'name': 'output-format',
        'required': False,
        'group': None,
        'description': 'Output format among json[default], csv, parquet'
    }
]

args_latest = [
    {
        'name': 'class',
        'required': True,
        'description': 'Fink derived class'
    },
    {
        'name': 'n',
        'required': False,
        'description': 'Last N alerts to transfer between stopping date and starting date. Default is 10, max is 1000.'
    },
    {
        'name': 'startdate',
        'required': False,
        'description': 'Starting date in UTC (iso, jd, or MJD). Default is 2019-11-01 00:00:00'
    },
    {
        'name': 'stopdate',
        'required': False,
        'description': 'Stopping date in UTC (iso, jd, or MJD). Default is now.'
    },
    {
        'name': 'columns',
        'required': False,
        'description': 'Comma-separated data columns to transfer. Default is all columns. See {}/api/v1/columns for more information.'.format(APIURL)
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet'
    }
]

args_sso = [
    {
        'name': 'n_or_d',
        'required': False,
        'description': 'IAU number of the object, or designation of the object IF the number does not exist yet. Example for numbers: 8467 (asteroid) or 10P (comet). Example for designations: 2010JO69 (asteroid) or C/2020V2 (comet).'
    },
    {
        'name': 'withEphem',
        'required': False,
        'description': 'Attach ephemerides provided by the Miriade service (https://ssp.imcce.fr/webservices/miriade/api/ephemcc/), as extra columns in the results.'
    },
    {
        'name': 'columns',
        'required': False,
        'description': 'Comma-separated data columns to transfer. Default is all columns. See {}/api/v1/columns for more information.'.format(APIURL)
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet'
    }
]

args_tracklet = [
    {
        'name': 'date',
        'required': False,
        'description': 'A date. Format: YYYY-MM-DD hh:mm:dd. You can use short versions like YYYY-MM-DD only, or YYYY-MM-DD hh.'
    },
    {
        'name': 'columns',
        'required': False,
        'description': 'Comma-separated data columns to transfer. Default is all columns. See {}/api/v1/columns for more information.'.format(APIURL)
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet'
    }
]

args_cutouts = [
    {
        'name': 'objectId',
        'required': True,
        'description': 'ZTF Object ID'
    },
    {
        'name': 'kind',
        'required': True,
        'description': 'Science, Template, or Difference'
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'PNG[default], FITS, array'
    },
    {
        'name': 'candid',
        'required': False,
        'description': 'Candidate ID of the alert belonging to the object with `objectId`. If not filled, the cutouts of the latest alert is returned'
    },
    {
        'name': 'stretch',
        'required': False,
        'description': 'Stretch function to be applied. Available: sigmoid[default], linear, sqrt, power, log.'
    },
    {
        'name': 'colormap',
        'required': False,
        'description': 'Valid matplotlib colormap name (see matplotlib.cm). Default is grayscale.'
    },
    {
        'name': 'pmin',
        'required': False,
        'description': 'The percentile value used to determine the pixel value of minimum cut level. Default is 0.5. No effect for sigmoid.'
    },
    {
        'name': 'pmax',
        'required': False,
        'description': 'The percentile value used to determine the pixel value of maximum cut level. Default is 99.5. No effect for sigmoid.'
    },
    {
        'name': 'convolution_kernel',
        'required': False,
        'description': 'Convolve the image with a kernel (gauss or box). Default is None (not specified).'
    }
]

args_xmatch = [
    {
        'name': 'catalog',
        'required': True,
        'description': 'External catalog as CSV'
    },
    {
        'name': 'header',
        'required': True,
        'description': 'Comma separated names of columns corresponding to RA, Dec, ID, Time[optional] in the input catalog.'
    },
    {
        'name': 'radius',
        'required': True,
        'description': 'Conesearch radius in arcsec. Maximum is 18,000 arcseconds (5 degrees).'
    },
    {
        'name': 'window',
        'required': False,
        'description': '[Optional] Time window in days.'
    },
]

args_bayestar = [
    {
        'name': 'bayestar',
        'required': True,
        'description': 'LIGO/Virgo probability sky maps, as gzipped FITS (bayestar.fits.gz)'
    },
    {
        'name': 'credible_level',
        'required': True,
        'description': 'GW credible region threshold to look for. Note that the values in the resulting credible level map vary inversely with probability density: the most probable pixel is assigned to the credible level 0.0, and the least likely pixel is assigned the credible level 1.0.'
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet'
    }
]

args_stats = [
    {
        'name': 'date',
        'required': True,
        'description': 'Observing date. This can be either a given night (YYYYMMDD), month (YYYYMM), year (YYYY), or eveything (empty string)'
    },
    {
        'name': 'columns',
        'required': False,
        'description': 'Comma-separated data columns to transfer. Default is all columns. See {}/api/v1/columns for more information.'.format(APIURL)
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet'
    }
]

@api_bp.route('/api/v1/objects', methods=['GET'])
def return_object_arguments():
    """ Obtain information about retrieving object data
    """
    return jsonify({'args': args_objects})

@api_bp.route('/api/v1/objects', methods=['POST'])
def return_object():
    """ Retrieve object data from the Fink database
    """
    if 'output-format' in request.json:
        output_format = request.json['output-format']
    else:
        output_format = 'json'

    # Check all required args are here
    required_args = [i['name'] for i in args_objects if i['required'] is True]
    for required_arg in required_args:
        if required_arg not in request.json:
            rep = {
                'status': 'error',
                'text': "A value for `{}` is required. Use GET to check arguments.\n".format(required_arg)
            }
            return Response(str(rep), 400)

    if 'columns' in request.json:
        cols = request.json['columns'].replace(" ", "")
    else:
        cols = '*'

    if ',' in request.json['objectId']:
        # multi-objects search
        splitids = request.json['objectId'].split(',')
        ids = ['key:key:{}'.format(i.strip()) for i in splitids]
    else:
        # single object search
        ids = ["key:key:{}".format(request.json['objectId'])]

    if 'withcutouts' in request.json and str(request.json['withcutouts']) == 'True':
        withcutouts = True
    else:
        withcutouts = False

    if 'withupperlim' in request.json and str(request.json['withupperlim']) == 'True':
        withupperlim = True
    else:
        withupperlim = False

    pdf = return_object_pdf(
        ids, withupperlim=withupperlim, withcutouts=withcutouts, cols=cols
    )

    if output_format == 'json':
        return pdf.to_json(orient='records')
    elif output_format == 'csv':
        return pdf.to_csv(index=False)
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

@api_bp.route('/api/v1/explorer', methods=['GET'])
def query_db_arguments():
    """ Obtain information about querying the Fink database
    """
    return jsonify({'args': args_explorer})

@api_bp.route('/api/v1/explorer', methods=['POST'])
def query_db():
    """ Query the Fink database
    """
    if 'output-format' in request.json:
        output_format = request.json['output-format']
    else:
        output_format = 'json'

    # Check the user specifies only one group
    all_groups = [i['group'] for i in args_explorer if i['group'] is not None and i['name'] in request.json]
    if len(np.unique(all_groups)) != 1:
        rep = {
            'status': 'error',
            'text': "You need to set parameters from the same group\n"
        }
        return Response(str(rep), 400)

    # Check the user specifies all parameters within a group
    user_group = np.unique(all_groups)[0]
    required_args = [i['name'] for i in args_explorer if i['group'] == user_group]
    required = [i['required'] for i in args_explorer if i['group'] == user_group]
    for required_arg, required_ in zip(required_args, required):
        if (required_arg not in request.json) and required_:
            rep = {
                'status': 'error',
                'text': "A value for `{}` is required for group {}. Use GET to check arguments.\n".format(required_arg, user_group)
            }
            return Response(str(rep), 400)

    if user_group == 0:
        # objectId search
        to_evaluate = "key:key:{}".format(request.json['objectId'])

        # Avoid a full scan
        client.setLimit(1000)

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
        ra, dec = request.json['ra'], request.json['dec']
        radius = request.json['radius']

        if 'startdate_conesearch' in request.json:
            startdate = request.json['startdate_conesearch']
        else:
            startdate = None
        if 'window_days_conesearch' in request.json and request.json['window_days_conesearch'] is not None:
            window_days = float(request.json['window_days_conesearch'])
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
        if int(request.json['window']) > 180:
            rep = {
                'status': 'error',
                'text': "`window` cannot be bigger than 180 minutes.\n"
            }
            return Response(str(rep), 400)
        # Time to jd
        jd_start = Time(request.json['startdate']).jd
        jd_end = jd_start + TimeDelta(int(request.json['window']) * 60, format='sec').jd

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

    if output_format == 'json':
        return pdfs.to_json(orient='records')
    elif output_format == 'csv':
        return pdfs.to_csv(index=False)
    elif output_format == 'parquet':
        f = io.BytesIO()
        pdfs.to_parquet(f)
        f.seek(0)
        return f.read()

    rep = {
        'status': 'error',
        'text': "Output format `{}` is not supported. Choose among json, csv, or parquet\n".format(request.json['output-format'])
    }
    return Response(str(rep), 400)

@api_bp.route('/api/v1/latests', methods=['GET'])
def latest_objects_arguments():
    """ Obtain information about latest objects
    """
    return jsonify({'args': args_latest})

@api_bp.route('/api/v1/latests', methods=['POST'])
def latest_objects():
    """ Get latest objects by class
    """
    if 'output-format' in request.json:
        output_format = request.json['output-format']
    else:
        output_format = 'json'

    # Check all required args are here
    required_args = [i['name'] for i in args_latest if i['required'] is True]
    for required_arg in required_args:
        if required_arg not in request.json:
            rep = {
                'status': 'error',
                'text': "A value for `{}` is required. Use GET to check arguments.\n".format(required_arg)
            }
            return Response(str(rep), 400)

    if 'n' not in request.json:
        nalerts = 10
    else:
        nalerts = int(request.json['n'])

    if 'startdate' not in request.json:
        # start of the Fink operations
        jd_start = Time('2019-11-01 00:00:00').jd
    else:
        jd_start = Time(request.json['startdate']).jd

    if 'stopdate' not in request.json:
        jd_stop = Time.now().jd
    else:
        jd_stop = Time(request.json['stopdate']).jd

    if 'columns' in request.json:
        cols = request.json['columns'].replace(" ", "")
        truncated = True
    else:
        cols = '*'
        truncated = False

    # Search for latest alerts for a specific class
    tns_classes = pd.read_csv('assets/tns_types.csv', header=None)[0].values
    is_tns = request.json['class'].startswith('(TNS)') and (request.json['class'].split('(TNS) ')[1] in tns_classes)
    if is_tns:
        classname = request.json['class'].split('(TNS) ')[1]
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
    elif request.json['class'].startswith('(SIMBAD)') or request.json['class'] != 'allclasses':
        if request.json['class'].startswith('(SIMBAD)'):
            classname = request.json['class'].split('(SIMBAD) ')[1]
        else:
            classname = request.json['class']

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
    elif request.json['class'] == 'allclasses':
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

    # We want to return alerts
    # color computation is disabled
    pdfs = format_hbase_output(
        results, schema_client,
        group_alerts=group_alerts,
        extract_color=False,
        truncated=truncated,
        with_constellation=True
    )

    if output_format == 'json':
        return pdfs.to_json(orient='records')
    elif output_format == 'csv':
        return pdfs.to_csv(index=False)
    elif output_format == 'parquet':
        f = io.BytesIO()
        pdfs.to_parquet(f)
        f.seek(0)
        return f.read()

    rep = {
        'status': 'error',
        'text': "Output format `{}` is not supported. Choose among json, csv, or parquet\n".format(request.json['output-format'])
    }
    return Response(str(rep), 400)

@api_bp.route('/api/v1/classes', methods=['GET'])
def class_arguments():
    """ Obtain all Fink derived class
    """
    # TNS
    tns_types = pd.read_csv('assets/tns_types.csv', header=None)[0].values
    tns_types = sorted(tns_types, key=lambda s: s.lower())
    tns_types = ['(TNS) ' + x for x in tns_types]

    # SIMBAD
    simbad_types = pd.read_csv('assets/simbad_types.csv', header=None)[0].values
    simbad_types = sorted(simbad_types, key=lambda s: s.lower())
    simbad_types = ['(SIMBAD) ' + x for x in simbad_types]

    # Fink science modules
    fink_types = pd.read_csv('assets/fink_types.csv', header=None)[0].values
    fink_types = sorted(fink_types, key=lambda s: s.lower())

    types = {
        'Fink classifiers': fink_types,
        'TNS classified data': tns_types,
        'Cross-match with SIMBAD (see http://simbad.u-strasbg.fr/simbad/sim-display?data=otypes)': simbad_types
    }

    return jsonify({'classnames': types})

@api_bp.route('/api/v1/columns', methods=['GET'])
def columns_arguments():
    """ Obtain all alert fields available and their type
    """
    # ZTF candidate fields
    r = requests.get('https://raw.githubusercontent.com/ZwickyTransientFacility/ztf-avro-alert/master/schema/candidate.avsc')
    tmp = pd.DataFrame.from_dict(r.json())
    ztf_candidate = tmp['fields'].apply(pd.Series)
    ztf_candidate = ztf_candidate.append(
        {
            "name": "schemavsn",
            "type": "string",
            "doc": "schema version used"
        }, ignore_index=True
    )
    ztf_candidate = ztf_candidate.append(
        {
            "name": "publisher",
            "type": "string",
            "doc": "origin of alert packet"
        }, ignore_index=True
    )
    ztf_candidate = ztf_candidate.append(
        {
            "name": "objectId",
            "type": "string",
            "doc": "object identifier or name"
        }, ignore_index=True
    )

    ztf_cutouts = pd.DataFrame.from_dict(
        [
            {
                "name": "cutoutScience_stampData",
                "type": "array",
                "doc": "2D array from the Science cutout FITS"
            }
        ]
    )
    ztf_cutouts = ztf_cutouts.append(
        {
            "name": "cutoutTemplate_stampData",
            "type": "array",
            "doc": "2D array from the Template cutout FITS"
        }, ignore_index=True
    )
    ztf_cutouts = ztf_cutouts.append(
        {
            "name": "cutoutDifference_stampData",
            "type": "array",
            "doc": "2D array from the Difference cutout FITS"
        }, ignore_index=True
    )

    # Science modules
    fink_science = pd.DataFrame(
        [
            {'name': 'cdsxmatch', 'type': 'string', 'doc': 'SIMBAD closest counterpart, based on position. See https://fink-portal.org/api/v1/classes'},
            {'name': 'mulens', 'type': 'double', 'doc': 'Probability score of an alert to be a microlensing event by [LIA](https://github.com/dgodinez77/LIA).'},
            {'name': 'rf_snia_vs_nonia', 'type': 'double', 'doc': 'Probability of an alert to be a SNe Ia using a Random Forest Classifier (binary classification). Higher is better.'},
            {'name': 'rf_kn_vs_nonkn', 'type': 'double', 'doc': 'Probability of an alert to be a Kilonova using a PCA & Random Forest Classifier (binary classification). Higher is better.'},
            {'name': 'roid', 'type': 'int', 'doc': 'Determine if the alert is a potential Solar System object (experimental). See https://github.com/astrolabsoftware/fink-science/blob/db57c40cd9be10502e34c5117c6bf3793eb34718/fink_science/asteroids/processor.py#L26'},
            {'name': 'snn_sn_vs_all', 'type': 'double', 'doc': 'The probability of an alert to be a SNe vs. anything else (variable stars and other categories in the training) using SuperNNova'},
            {'name': 'snn_snia_vs_nonia', 'type': 'double', 'doc': 'The probability of an alert to be a SN Ia vs. core-collapse SNe using SuperNNova'},
        ]
    )

    # Science modules
    fink_derived = pd.DataFrame(
        [
            {'name': 'constellation', 'type': 'string', 'doc': 'Name of the constellation an alert on the sky is in'},
            {'name': 'classification', 'type': 'string', 'doc': 'Fink inferred classification. See https://fink-portal.org/api/v1/classes'},
            {'name': 'g-r', 'type': 'double', 'doc': 'Last g-r measurement for this object.'},
            {'name': 'rate(g-r)', 'type': 'double', 'doc': 'g-r rate in mag/day (between last and first available g-r measurements).'},
            {'name': 'lastdate', 'type': 'string', 'doc': 'Datetime for the alert (from the i:jd field).'},
        ]
    )

    # Sort by name
    ztf_candidate = ztf_candidate.sort_values('name')
    fink_science = fink_science.sort_values('name')
    fink_derived = fink_derived.sort_values('name')

    types = {
        'ZTF original fields (i:)': {i: {'type': j, 'doc': k} for i, j, k in zip(ztf_candidate.name, ztf_candidate.type, ztf_candidate.doc)},
        'ZTF original cutouts (b:)': {i: {'type': j, 'doc': k} for i, j, k in zip(ztf_cutouts.name, ztf_cutouts.type, ztf_cutouts.doc)},
        'Fink science module outputs (d:)': {i: {'type': j, 'doc': k} for i, j, k in zip(fink_science.name, fink_science.type, fink_science.doc)},
        'Fink added values (v:)': {i: {'type': j, 'doc': k} for i, j, k in zip(fink_derived.name, fink_derived.type, fink_derived.doc)}
    }

    return jsonify({'fields': types})

@api_bp.route('/api/v1/sso', methods=['GET'])
def return_sso_arguments():
    """ Obtain information about retrieving Solar System Object data
    """
    return jsonify({'args': args_sso})

@api_bp.route('/api/v1/sso', methods=['POST'])
def return_sso():
    """ Retrieve Solar System Object data from the Fink database
    """
    if 'output-format' in request.json:
        output_format = request.json['output-format']
    else:
        output_format = 'json'

    if 'columns' in request.json:
        cols = request.json['columns'].replace(" ", "")
        truncated = True
    else:
        cols = '*'
        truncated = False

    payload = request.json['n_or_d'].replace(' ', '')

    # Note the trailing _ to avoid mixing e.g. 91 and 915 in the same query
    to_evaluate = "key:key:{}_".format(payload)

    # We do not want to perform full scan if the objectid is a wildcard
    clientSSO.setLimit(1000)

    results = clientSSO.scan(
        "",
        to_evaluate,
        cols,
        0, True, True
    )

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

    if 'withEphem' in request.json:
        if request.json['withEphem'] == 'True' or request.json['withEphem'] is True:
            # We should probably add a timeout and try/except in case of miriade shutdown
            pdf = get_miriade_data(pdf)

    if output_format == 'json':
        return pdf.to_json(orient='records')
    elif output_format == 'csv':
        return pdf.to_csv(index=False)
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

@api_bp.route('/api/v1/tracklet', methods=['GET'])
def return_tracklet_arguments():
    """ Obtain information about retrieving Tracklets
    """
    return jsonify({'args': args_tracklet})

@api_bp.route('/api/v1/tracklet', methods=['POST'])
def return_tracklet():
    """ Retrieve tracklet data from the Fink database
    """
    if 'output-format' in request.json:
        output_format = request.json['output-format']
    else:
        output_format = 'json'

    if 'columns' in request.json:
        cols = request.json['columns'].replace(" ", "")
        truncated = True
    else:
        cols = '*'
        truncated = False

    if 'date' in request.json:
        designation = request.json['date']
    else:
        rep = {
            'status': 'error',
            'text': "You need tp specify a date at the format YYYY-MM-DD hh:mm:ss\n"
        }
        return Response(str(rep), 400)

    payload = 'TRCK_' + designation.replace('-', '').replace(':', '').replace(' ', '_')

    # Note the trailing _
    to_evaluate = "key:key:{}".format(payload)

    # We do not want to perform full scan if the objectid is a wildcard
    clientTRCK.setLimit(1000)

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

    if output_format == 'json':
        return pdf.to_json(orient='records')
    elif output_format == 'csv':
        return pdf.to_csv(index=False)
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

@api_bp.route('/api/v1/cutouts', methods=['GET'])
def cutouts_arguments():
    """ Obtain information about cutouts service
    """
    return jsonify({'args': args_cutouts})

@api_bp.route('/api/v1/cutouts', methods=['POST'])
def return_cutouts():
    """ Retrieve cutout data from the Fink database
    """
    assert request.json['kind'] in ['Science', 'Template', 'Difference']

    if 'output-format' in request.json:
        output_format = request.json['output-format']
    else:
        output_format = 'PNG'

    # default stretch is sigmoid
    if 'stretch' in request.json:
        stretch = request.json['stretch']
    else:
        stretch = 'sigmoid'

    # default name based on parameters
    filename = '{}_{}'.format(
        request.json['objectId'],
        request.json['kind']
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
        "key:key:{}".format(request.json['objectId']),
        "b:cutout{}_stampData,i:jd,i:candid".format(request.json['kind']),
        0, True, True
    )
    truncated = True

    # Format the results
    schema_client = client.schema()
    pdf = format_hbase_output(
        results, schema_client,
        group_alerts=False, truncated=truncated,
        extract_color=False
    )

    # Extract only the alert of interest
    if 'candid' in request.json:
        pdf = pdf[pdf['i:candid'].astype(str) == str(request.json['candid'])]
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
            col='b:cutout{}_stampData'.format(request.json['kind']),
            return_type='FITS'
        )
    else:
        pdf = extract_cutouts(
            pdf,
            client,
            col='b:cutout{}_stampData'.format(request.json['kind']),
            return_type='array'
        )

    array = pdf['b:cutout{}_stampData'.format(request.json['kind'])].values[0]

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
        return pdf[['b:cutout{}_stampData'.format(request.json['kind'])]].to_json(orient='records')

    if stretch == 'sigmoid':
        array = sigmoid_normalizer(array, 0, 1)
    else:
        pmin = 0.5
        if 'pmin' in request.json:
            pmin = float(request.json['pmin'])
        pmax = 99.5
        if 'pmax' in request.json:
            pmax = float(request.json['pmax'])
        array = legacy_normalizer(array, stretch=stretch, pmin=pmin, pmax=pmax)

    if 'convolution_kernel' in request.json:
        assert request.json['convolution_kernel'] in ['gauss', 'box']
        array = convolve(array, smooth=1, kernel=request.json['convolution_kernel'])

    # colormap
    if "colormap" in request.json:
        colormap = getattr(cm, request.json['colormap'])
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

@api_bp.route('/api/v1/xmatch', methods=['GET'])
def xmatch_arguments():
    """ Obtain information about the xmatch service
    """
    return jsonify({'args': args_xmatch})

@api_bp.route('/api/v1/xmatch', methods=['POST'])
def xmatch_user():
    """ Xmatch with user uploaded catalog
    """
    df = pd.read_csv(io.StringIO(request.json['catalog']))

    radius = float(request.json['radius'])
    if radius > 18000.:
        rep = {
            'status': 'error',
            'text': "`radius` cannot be bigger than 18,000 arcseconds (5 degrees).\n"
        }
        return Response(str(rep), 400)

    header = request.json['header']

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

    if 'window' in request.json:
        window_days = request.json['window']
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
            payload = {
                'ra': ra,
                'dec': dec,
                'radius': radius,
                'startdate_conesearch': time_start,
                'window_days_conesearch': window_days

            }
        else:
            payload = {
                'ra': ra,
                'dec': dec,
                'radius': radius
            }
        r = requests.post(
           '{}/api/v1/explorer'.format(APIURL),
           json=payload
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

@api_bp.route('/api/v1/bayestar', methods=['GET'])
def query_bayestar_arguments():
    """ Obtain information about inspecting a GW localization map
    """
    return jsonify({'args': args_bayestar})

@api_bp.route('/api/v1/bayestar', methods=['POST'])
def query_bayestar():
    """ Query the Fink database to find alerts inside a GW localization map
    """
    if 'output-format' in request.json:
        output_format = request.json['output-format']
    else:
        output_format = 'json'

    # Interpret user input
    bayestar_data = request.json['bayestar']
    credible_level_threshold = float(request.json['credible_level'])

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
    jdstart = Time(header['DATE-OBS']).jd - 1
    jdend = jdstart + 6

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

    # extract objectId and times
    objectids = [i[1]['i:objectId'] for i in results.items()]
    times = [float(i[1]['key:key'].split('_')[1]) for i in results.items()]
    pdf_ = pd.DataFrame({'oid': objectids, 'jd': times})

    # Filter by time - logic to be improved...
    pdf_ = pdf_[(pdf_['jd'] >= jdstart) & (pdf_['jd'] < jdend)]

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

    pdfs = format_hbase_output(
        results,
        schema_client,
        group_alerts=True,
        extract_color=False
    )

    if output_format == 'json':
        return pdfs.to_json(orient='records')
    elif output_format == 'csv':
        return pdfs.to_csv(index=False)
    elif output_format == 'parquet':
        f = io.BytesIO()
        pdfs.to_parquet(f)
        f.seek(0)
        return f.read()

    rep = {
        'status': 'error',
        'text': "Output format `{}` is not supported. Choose among json, csv, or parquet\n".format(request.json['output-format'])
    }
    return Response(str(rep), 400)

@api_bp.route('/api/v1/statistics', methods=['GET'])
def query_statistics_arguments():
    """ Obtain information about Fink statistics
    """
    return jsonify({'args': args_stats})

@api_bp.route('/api/v1/statistics', methods=['POST'])
def return_statistics():
    """ Retrieve statistics about Fink data
    """
    if 'output-format' in request.json:
        output_format = request.json['output-format']
    else:
        output_format = 'json'

    if 'columns' in request.json:
        cols = request.json['columns'].replace(" ", "")
    else:
        cols = '*'

    payload = request.json['date']

    to_evaluate = "key:key:ztf_{}".format(payload)

    results = clientStats.scan(
        "",
        to_evaluate,
        cols,
        0, True, True
    )

    pdf = pd.DataFrame.from_dict(results, orient='index')

    if output_format == 'json':
        return pdf.to_json(orient='records')
    elif output_format == 'csv':
        return pdf.to_csv(index=False)
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

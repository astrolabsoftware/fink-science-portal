# Copyright 2020-2023 AstroLab Software
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
from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

from flask import request, jsonify, Response

from app import APIURL

from apps.api.doc import api_doc_summary, api_doc_object, api_doc_explorer
from apps.api.doc import api_doc_latests, api_doc_sso, api_doc_tracklets
from apps.api.doc import api_doc_cutout, api_doc_xmatch, api_doc_bayestar
from apps.api.doc import api_doc_stats, api_doc_random, api_doc_ssocand
from apps.api.doc import api_doc_anomaly, api_doc_ssoft, api_doc_resolver

from apps.api.utils import return_object_pdf, return_explorer_pdf
from apps.api.utils import return_latests_pdf, return_sso_pdf
from apps.api.utils import return_ssocand_pdf
from apps.api.utils import return_tracklet_pdf, format_and_send_cutout
from apps.api.utils import perform_xmatch, return_bayestar_pdf
from apps.api.utils import return_statistics_pdf, send_data
from apps.api.utils import return_random_pdf
from apps.api.utils import return_anomalous_objects_pdf
from apps.api.utils import return_ssoft_pdf
from apps.api.utils import return_resolver_pdf
from apps.api.utils import upload_euclid_data
from apps.api.utils import download_euclid_data
from apps.api.utils import retrieve_metadata, post_metadata, retrieve_oid

from fink_utils.xmatch.simbad import get_simbad_labels
from fink_spins.ssoft import COLUMNS, COLUMNS_SHG1G2, COLUMNS_HG1G2, COLUMNS_HG

import io
import requests

import pandas as pd
import numpy as np

from astropy.table import Table
from astropy.io import fits, votable

from flask import Blueprint

api_bp = Blueprint('', __name__)

# Enable CORS for this blueprint only
@api_bp.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

def layout():
    layout_ = dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Card(
                        dbc.CardBody(
                            dcc.Markdown(api_doc_summary)
                        )
                    ),
                ],
                className="mb-4"
            ),
            dbc.Tabs(
                [
                    dbc.Tab(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Markdown(api_doc_object)
                                )
                            ),
                        ], label="Retrieve object data", label_style = {"color": "#000"}
                    ),
                    dbc.Tab(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Markdown(api_doc_explorer)
                                )
                            ),
                        ], label="Query the database", label_style = {"color": "#000"}
                    ),
                    dbc.Tab(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Markdown(api_doc_latests)
                                )
                            ),
                        ], label="Get latest alerts", label_style = {"color": "#000"}
                    ),
                    dbc.Tab(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Markdown(api_doc_sso)
                                )
                            ),
                        ], label="Solar System objects from MPC", label_style = {"color": "#000"}
                    ),
                    dbc.Tab(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Markdown(api_doc_ssocand)
                                )
                            ),
                        ], label="Candidate Solar System objects", label_style = {"color": "#000"}
                    ),
                    dbc.Tab(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Markdown(api_doc_ssoft)
                                )
                            ),
                        ], label="Solar System object parameters table", label_style = {"color": "#000"}
                    ),
                    dbc.Tab(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Markdown(api_doc_tracklets)
                                )
                            ),
                        ], label="Get Tracklet Objects", label_style = {"color": "#000"}
                    ),
                    dbc.Tab(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Markdown(api_doc_cutout)
                                )
                            ),
                        ], label="Get Image data", label_style = {"color": "#000"}
                    ),
                    dbc.Tab(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Markdown(api_doc_xmatch)
                                )
                            ),
                        ], label="Xmatch", label_style = {"color": "#000"}
                    ),
                    dbc.Tab(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Markdown(api_doc_bayestar)
                                )
                            ),
                        ], label="Gravitational Waves", label_style = {"color": "#000"}
                    ),
                    dbc.Tab(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Markdown(api_doc_stats)
                                )
                            ),
                        ], label="Statistics", label_style = {"color": "#000"}
                    ),
                    dbc.Tab(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Markdown(api_doc_anomaly)
                                )
                            ),
                        ], label="Anomaly detection", label_style = {"color": "#000"}
                    ),
                    dbc.Tab(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Markdown(api_doc_random)
                                )
                            ),
                        ], label="Random objects", label_style = {"color": "#000"}
                    ),
                    dbc.Tab(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Markdown(api_doc_resolver)
                                )
                            ),
                        ], label="Name resolver", label_style = {"color": "#000"}
                    ),
                ]
            )
        ], className='api mb-4 mt-4', fluid='lg'
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
        'description': 'Output format among json[default], csv, parquet, votable'
    }
]

args_explorer = [
    {
        'name': 'objectId',
        'required': True,
        'group': 0,
        'description': 'ZTF Object ID, or comma-separated list of Object IDs'
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
        'name': 'startdate',
        'required': False,
        'group': None,
        'description': '[Optional] Starting date in UTC, as either ISO string, JD or MJD.'
    },
    {
        'name': 'stopdate',
        'required': False,
        'group': None,
        'description': '[Optional] Stopping date in UTC, as either ISO string, JD or MJD.'
    },
    {
        'name': 'window',
        'required': False,
        'group': None,
        'description': '[Optional] Time window in days, may be used instead of stopdate'
    },
    {
        'name': 'n',
        'required': False,
        'group': None,
        'description': 'Maximal number of alerts to return. Default is 1000.'
    },
    {
        'name': 'output-format',
        'required': False,
        'group': None,
        'description': 'Output format among json[default], csv, parquet, votable'
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
        'name': 'color',
        'required': False,
        'description': 'If True, extract color information for the transient (default is False).'
    },
    {
        'name': 'columns',
        'required': False,
        'description': 'Comma-separated data columns to transfer. Default is all columns. See {}/api/v1/columns for more information.'.format(APIURL)
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet, votable'
    }
]

args_sso = [
    {
        'name': 'n_or_d',
        'required': False,
        'description': 'IAU number of the object, or designation of the object IF the number does not exist yet. Example for numbers: 8467 (asteroid) or 10P (comet). Example for designations: 2010JO69 (asteroid) or C/2020V2 (comet). You can also give a list of object names (comma-separated).'
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
        'description': 'Output format among json[default], csv, parquet, votable'
    }
]

args_tracklet = [
    {
        'name': 'date',
        'required': False,
        'description': 'A date. Format: YYYY-MM-DD hh:mm:dd. You can use short versions like YYYY-MM-DD only, or YYYY-MM-DD hh.'
    },
    {
        'name': 'id',
        'required': False,
        'description': 'Tracklet ID, in the format TRCK_YYYYMMDD_HHMMSS_NN',
    },
    {
        'name': 'columns',
        'required': False,
        'description': 'Comma-separated data columns to transfer. Default is all columns. See {}/api/v1/columns for more information.'.format(APIURL)
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet, votable'
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
        'required': False,
        'description': 'LIGO/Virgo probability sky maps, as gzipped FITS (bayestar.fits.gz). Not compatible with `event_name`.'
    },
    {
        'name': 'event_name',
        'required': False,
        'description': 'If provided, directly query GraceDB with the `event_name`. Not compatible with the argument `bayestar`.'
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
        'description': 'Comma-separated data columns to transfer. Default is all columns.'
    },
    {
        'name': 'schema',
        'required': False,
        'description': 'If True, return just the schema of statistics table instead of actual data'
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet, votable'
    }
]

args_random = [
    {
        'name': 'n',
        'required': True,
        'description': 'Number of objects to return. Maximum is 16 for performance.'
    },
    {
        'name': 'columns',
        'required': False,
        'description': 'Comma-separated data columns to transfer. Default is all columns. See {}/api/v1/columns for more information.'.format(APIURL)
    },
    {
        'name': 'class',
        'required': False,
        'description': 'Fink derived class. Default is empty string, namely all classes are considered. See {}/api/v1/classes for more information'.format(APIURL)
    },
    {
        'name': 'seed',
        'required': False,
        'description': 'Seed number for random number generator. By default, the seed is not fixed.'
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet, votable'
    }
]

args_ssocand = [
    {
        'name': 'kind',
        'required': True,
        'description': 'Choose to return orbital parameters (orbParams), or lightcurves (lightcurves)'
    },
    {
        'name': 'ssoCandId',
        'required': False,
        'description': '[Optional] Trajectory ID if you know it. Otherwise do not specify to return all.'
    },
    {
        'name': 'start_date',
        'required': False,
        'description': '[Optional] Start date in UTC YYYY-MM-DD. Only used for `kind=lightcurves`. Default is 2019-11-01.'
    },
    {
        'name': 'stop_date',
        'required': False,
        'description': '[Optional] Stop date in UTC YYYY-MM-DD. Only used for `kind=lightcurves`. Default is today.'
    },
    {
        'name': 'maxnumber',
        'required': False,
        'description': 'Maximum number of entries (observations or orbital parameters) to retrieve. Default is 10,000.'
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet, votable'
    }
]

args_anomaly = [
    {
        'name': 'n',
        'required': False,
        'description': 'Last N alerts to transfer between stop and start date (going from most recent to older alerts). Default is 10'
    },
    {
        'name': 'start_date',
        'required': False,
        'description': '[Optional] Start date in UTC YYYY-MM-DD. Default is 2019-11-01.'
    },
    {
        'name': 'stop_date',
        'required': False,
        'description': '[Optional] Stop date in UTC YYYY-MM-DD. Default is today.'
    },
    {
        'name': 'columns',
        'required': False,
        'description': 'Comma-separated data columns to transfer. Default is all columns. See {}/api/v1/columns for more information.'.format(APIURL)
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet, votable'
    }
]

args_ssoft = [
    {
        'name': 'sso_name',
        'required': False,
        'description': 'Official name or provisional designation of the SSO.'
    },
    {
        'name': 'sso_number',
        'required': False,
        'description': 'IAU number of the SSO'
    },
    {
        'name': 'schema',
        'required': False,
        'description': 'If specified, return the schema of the table in json format.'
    },
    {
        'name': 'flavor',
        'required': False,
        'description': 'Data model among SHG1G2 (default), HG1G2, HG.'
    },
    {
        'name': 'version',
        'required': False,
        'description': 'Version of the SSOFT YYYY.MM. By default it uses the latest one. Starts at 2023.07'
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet, votable'
    }
]

args_resolver = [
    {
        'name': 'resolver',
        'required': True,
        'description': 'Resolver among: `simbad`, `ssodnet`, `tns`'
    },
    {
        'name': 'name',
        'required': True,
        'description': 'Object name to resolve'
    },
    {
        'name': 'reverse',
        'required': False,
        'description': 'If True, resolve ZTF* name. Default is False.'
    },
    {
        'name': 'nmax',
        'required': False,
        'description': 'Maximum number of match to return. Default is 10.'
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet, votable'
    }
]

args_euclidin = [
    {
        'name': 'EID',
        'required': True,
        'description': 'ID from Euclid'
    },
    {
        'name': 'pipeline',
        'required': True,
        'description': '`SSOPipe`, `streakdet`, `DL`'
    },
    {
        'name': 'version',
        'required': True,
        'description': 'Version of the processing'
    },
    {
        'name': 'date',
        'required': True,
        'description': 'Date of the processing'
    },
    {
        'name': 'payload',
        'required': True,
        'description': 'Data file'
    },
    {
        'name': 'mode',
        'required': False,
        'description': 'Execution mode among production[default], or sandbox. Choose sandbox if you just want to test the upload without touching the tables.'
    },
]

args_eucliddata = [
    {
        'name': 'pipeline',
        'required': True,
        'description': '`SSOPipe`, `streakdet`, `DL`'
    },
    {
        'name': 'dates',
        'required': True,
        'description': 'Observation dates. It can be a single date (YYYYMMDD), and range (YYYYMMDD:YYYYMMDD), or any superset (e.g. YYYY)'
    },
    {
        'name': 'columns',
        'required': False,
        'description': 'Comma-separated data columns to transfer. Default is all columns. See {}/api/v1/columns for more information.'.format(APIURL)
    },
    {
        'name': 'mode',
        'required': False,
        'description': 'Execution mode among production[default], or sandbox. Choose sandbox if you just want to connect to the test table.'
    },
    {
        'name': 'output-format',
        'required': False,
        'description': 'Output format among json[default], csv, parquet, votable'
    }
]

args_metadata = [
    {
        'name': 'objectId',
        'required': True,
        'description': 'ZTF object ID'
    },
    {
        'name': 'internal_name',
        'required': True,
        'description': 'Internal name to be given'
    },
    {
        'name': 'username',
        'required': True,
        'description': 'The username of the submitter'
    },
    {
        'name': 'comments',
        'required': False,
        'description': 'Any relevant comments for the object'
    },
]

@api_bp.route('/api/v1/objects', methods=['GET'])
def return_object_arguments():
    """ Obtain information about retrieving object data
    """
    if len(request.args) > 0:
        # POST from query URL
        return return_object(payload=request.args)
    else:
        return jsonify({'args': args_objects})

@api_bp.route('/api/v1/objects', methods=['POST'])
def return_object(payload=None):
    """ Retrieve object data from the Fink database
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    # Check all required args are here
    required_args = [i['name'] for i in args_objects if i['required'] is True]
    for required_arg in required_args:
        if required_arg not in payload:
            rep = {
                'status': 'error',
                'text': "A value for `{}` is required. Use GET to check arguments.\n".format(required_arg)
            }
            return Response(str(rep), 400)

    pdf = return_object_pdf(payload)

    # Error propagation
    if isinstance(pdf, Response):
        return pdf

    output_format = payload.get('output-format', 'json')
    return send_data(pdf, output_format)

@api_bp.route('/api/v1/explorer', methods=['GET'])
def query_db_arguments():
    """ Obtain information about querying the Fink database
    """
    if len(request.args) > 0:
        # POST from query URL
        return query_db(payload=request.args)
    else:
        return jsonify({'args': args_explorer})

@api_bp.route('/api/v1/explorer', methods=['POST'])
def query_db(payload=None):
    """ Query the Fink database
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    # Check the user specifies only one group
    all_groups = [i['group'] for i in args_explorer if i['group'] is not None and i['name'] in payload]
    if len(np.unique(all_groups)) > 1:
        rep = {
            'status': 'error',
            'text': "You need to set parameters from the same group\n"
        }
        return Response(str(rep), 400)

    # Check the user specifies all parameters within a group
    if len(np.unique(all_groups)) == 1:
        user_group = np.unique(all_groups)[0]
        required_args = [i['name'] for i in args_explorer if i['group'] == user_group]
        required = [i['required'] for i in args_explorer if i['group'] == user_group]
        for required_arg, required_ in zip(required_args, required):
            if (required_arg not in payload) and required_:
                rep = {
                    'status': 'error',
                    'text': "A value for `{}` is required for group {}. Use GET to check arguments.\n".format(required_arg, user_group)
                }
                return Response(str(rep), 400)
    else:
        user_group = None

    pdfs = return_explorer_pdf(payload, user_group)

    # Error propagation
    if isinstance(pdfs, Response):
        return pdfs

    output_format = payload.get('output-format', 'json')
    return send_data(pdfs, output_format)

@api_bp.route('/api/v1/latests', methods=['GET'])
def latest_objects_arguments():
    """ Obtain information about latest objects
    """
    if len(request.args) > 0:
        # POST from query URL
        return latest_objects(payload=request.args)
    else:
        return jsonify({'args': args_latest})

@api_bp.route('/api/v1/latests', methods=['POST'])
def latest_objects(payload=None):
    """ Get latest objects by class
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    # Check all required args are here
    required_args = [i['name'] for i in args_latest if i['required'] is True]
    for required_arg in required_args:
        if required_arg not in payload:
            rep = {
                'status': 'error',
                'text': "A value for `{}` is required. Use GET to check arguments.\n".format(required_arg)
            }
            return Response(str(rep), 400)

    pdfs = return_latests_pdf(payload)

    # Error propagation
    if isinstance(pdfs, Response):
        return pdfs

    output_format = payload.get('output-format', 'json')
    return send_data(pdfs, output_format)

@api_bp.route('/api/v1/classes', methods=['GET'])
def class_arguments():
    """ Obtain all Fink derived class
    """
    # TNS
    tns_types = pd.read_csv('assets/tns_types.csv', header=None)[0].values
    tns_types = sorted(tns_types, key=lambda s: s.lower())
    tns_types = ['(TNS) ' + x for x in tns_types]

    # SIMBAD
    simbad_types = get_simbad_labels('old_and_new')
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
            {'name': 'cdsxmatch', 'type': 'string', 'doc': 'Object type of the closest source from SIMBAD database; if exists within 1 arcsec. See https://fink-portal.org/api/v1/classes'},
            {'name': 'gcvs', 'type': 'string', 'doc': 'Object type of the closest source from GCVS catalog; if exists within 1 arcsec.'},
            {'name': 'vsx', 'type': 'string', 'doc': 'Object type of the closest source from VSX catalog; if exists within 1 arcsec.'},
            {'name': 'Plx', 'type': 'double', 'doc': 'Absolute stellar parallax (in milli-arcsecond) of the closest source from Gaia catalog; if exists within 1 arcsec.'},
            {'name': 'e_Plx', 'type': 'double', 'doc': 'Standard error of the stellar parallax (in milli-arcsecond) of the closest source from Gaia catalog; if exists within 1 arcsec.'},
            {'name': 'DR3Name', 'type': 'string', 'doc': 'Unique source designation of closest source from Gaia catalog; if exists within 1 arcsec.'},
            {'name': 'mulens', 'type': 'double', 'doc': 'Probability score of an alert to be a microlensing event by [LIA](https://github.com/dgodinez77/LIA).'},
            {'name': 'rf_snia_vs_nonia', 'type': 'double', 'doc': 'Probability of an alert to be a SNe Ia using a Random Forest Classifier (binary classification). Higher is better.'},
            {'name': 'rf_kn_vs_nonkn', 'type': 'double', 'doc': 'Probability of an alert to be a Kilonova using a PCA & Random Forest Classifier (binary classification). Higher is better.'},
            {'name': 'roid', 'type': 'int', 'doc': 'Determine if the alert is a potential Solar System object (experimental). 0: likely not SSO, 1: first appearance but likely not SSO, 2: candidate SSO, 3: found in MPC.'},
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
            {'name': 'sigma(g-r)', 'type': 'double', 'doc': 'Error of last g-r measurement for this object.'},
            {'name': 'rate(g-r)', 'type': 'double', 'doc': 'g-r change rate in mag/day (between last and previous g-r measurements).'},
            {'name': 'sigma(rate(g-r))', 'type': 'double', 'doc': 'Error of g-r rate in mag/day (between last and previous g-r measurements).'},
            {'name': 'rate', 'type': 'double', 'doc': 'Brightness change rate in mag/day (between last and previous measurement in this filter).'},
            {'name': 'sigma(rate)', 'type': 'double', 'doc': 'Error of brightness change rate in mag/day (between last and previous measurement in this filter).'},
            {'name': 'lastdate', 'type': 'string', 'doc': 'Human readable datetime for the alert (from the i:jd field).'},
            {'name': 'firstdate', 'type': 'string', 'doc': 'Human readable datetime for the first detection of the object (from the i:jdstarthist field).'},
            {'name': 'lapse', 'type': 'string', 'doc': 'Number of days between first and last detection.'},
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
    if len(request.args) > 0:
        # POST from query URL
        return return_sso(payload=request.args)
    else:
        return jsonify({'args': args_sso})

@api_bp.route('/api/v1/sso', methods=['POST'])
def return_sso(payload=None):
    """ Retrieve Solar System Object data from the Fink database
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    pdf = return_sso_pdf(payload)

    output_format = payload.get('output-format', 'json')
    return send_data(pdf, output_format)

@api_bp.route('/api/v1/ssocand', methods=['GET'])
def return_ssocand_arguments():
    """ Obtain information about retrieving candidate Solar System Object data
    """
    if len(request.args) > 0:
        # POST from query URL
        return return_ssocand(payload=request.args)
    else:
        return jsonify({'args': args_ssocand})

@api_bp.route('/api/v1/ssocand', methods=['POST'])
def return_ssocand(payload=None):
    """ Retrieve candidate Solar System Object data from the Fink database
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    # Check all required args are here
    required_args = [i['name'] for i in args_ssocand if i['required'] is True]
    for required_arg in required_args:
        if required_arg not in payload:
            rep = {
                'status': 'error',
                'text': "A value for `{}` is required. Use GET to check arguments.\n".format(required_arg)
            }
            return Response(str(rep), 400)

    pdf = return_ssocand_pdf(payload)

    output_format = payload.get('output-format', 'json')
    return send_data(pdf, output_format)

@api_bp.route('/api/v1/tracklet', methods=['GET'])
def return_tracklet_arguments():
    """ Obtain information about retrieving Tracklets
    """
    if len(request.args) > 0:
        # POST from query URL
        return return_tracklet(payload=request.args)
    else:
        return jsonify({'args': args_tracklet})

@api_bp.route('/api/v1/tracklet', methods=['POST'])
def return_tracklet(payload=None):
    """ Retrieve tracklet data from the Fink database
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    pdf = return_tracklet_pdf(payload)

    # Error propagation
    if isinstance(pdf, Response):
        return pdf

    output_format = payload.get('output-format', 'json')
    return send_data(pdf, output_format)

@api_bp.route('/api/v1/cutouts', methods=['GET'])
def cutouts_arguments():
    """ Obtain information about cutouts service
    """
    if len(request.args) > 0:
        # POST from query URL
        return return_cutouts(payload=request.args)
    else:
        return jsonify({'args': args_cutouts})

@api_bp.route('/api/v1/cutouts', methods=['POST'])
def return_cutouts(payload=None):
    """ Retrieve cutout data from the Fink database
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    assert payload['kind'] in ['Science', 'Template', 'Difference']

    return format_and_send_cutout(payload)

@api_bp.route('/api/v1/xmatch', methods=['GET'])
def xmatch_arguments():
    """ Obtain information about the xmatch service
    """
    if len(request.args) > 0:
        # POST from query URL
        return xmatch_user(payload=request.args)
    else:
        return jsonify({'args': args_xmatch})

@api_bp.route('/api/v1/xmatch', methods=['POST'])
def xmatch_user(payload=None):
    """ Xmatch with user uploaded catalog
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    return perform_xmatch(payload)

@api_bp.route('/api/v1/bayestar', methods=['GET'])
def query_bayestar_arguments():
    """ Obtain information about inspecting a GW localization map
    """
    if len(request.args) > 0:
        # POST from query URL
        return query_bayestar(payload=request.args)
    else:
        return jsonify({'args': args_bayestar})

@api_bp.route('/api/v1/bayestar', methods=['POST'])
def query_bayestar(payload=None):
    """ Query the Fink database to find alerts inside a GW localization map
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    pdfs = return_bayestar_pdf(payload)

    # Error propagation
    if isinstance(pdfs, Response):
        return pdfs

    output_format = payload.get('output-format', 'json')
    return send_data(pdfs, output_format)

@api_bp.route('/api/v1/statistics', methods=['GET'])
def query_statistics_arguments():
    """ Obtain information about Fink statistics
    """
    if len(request.args) > 0:
        # POST from query URL
        return return_statistics(payload=request.args)
    else:
        return jsonify({'args': args_stats})

@api_bp.route('/api/v1/statistics', methods=['POST'])
def return_statistics(payload=None):
    """ Retrieve statistics about Fink data
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    pdf = return_statistics_pdf(payload)

    output_format = payload.get('output-format', 'json')
    return send_data(pdf, output_format)

@api_bp.route('/api/v1/random', methods=['GET'])
def return_random_arguments():
    """ Obtain information about retrieving random object data
    """
    if len(request.args) > 0:
        # POST from query URL
        return return_random(payload=request.args)
    else:
        return jsonify({'args': args_random})

@api_bp.route('/api/v1/random', methods=['POST'])
def return_random(payload=None):
    """ Retrieve random object data from the Fink database
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    # Check all required args are here
    required_args = [i['name'] for i in args_random if i['required'] is True]
    for required_arg in required_args:
        if required_arg not in payload:
            rep = {
                'status': 'error',
                'text': "A value for `{}` is required. Use GET to check arguments.\n".format(required_arg)
            }
            return Response(str(rep), 400)

    pdf = return_random_pdf(payload)

    # Error propagation
    if isinstance(pdf, Response):
        return pdf

    output_format = payload.get('output-format', 'json')
    return send_data(pdf, output_format)

@api_bp.route('/api/v1/anomaly', methods=['GET'])
def anomalous_objects_arguments():
    """ Obtain information about anomalous objects
    """
    if len(request.args) > 0:
        # POST from query URL
        return anomalous_objects(payload=request.args)
    else:
        return jsonify({'args': args_anomaly})

@api_bp.route('/api/v1/anomaly', methods=['POST'])
def anomalous_objects(payload=None):
    """ Get anomalous objects
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    # Check all required args are here
    required_args = [i['name'] for i in args_anomaly if i['required'] is True]
    for required_arg in required_args:
        if required_arg not in payload:
            rep = {
                'status': 'error',
                'text': "A value for `{}` is required. Use GET to check arguments.\n".format(required_arg)
            }
            return Response(str(rep), 400)

    pdfs = return_anomalous_objects_pdf(payload)

    # Error propagation
    if isinstance(pdfs, Response):
        return pdfs

    output_format = payload.get('output-format', 'json')
    return send_data(pdfs, output_format)

@api_bp.route('/api/v1/ssoft', methods=['GET'])
def ssoft_arguments():
    """ Obtain information about the Fink Flat Table
    """
    if len(request.args) > 0:
        # POST from query URL
        return ssoft_table(payload=request.args)
    else:
        return jsonify({'args': args_ssoft})

@api_bp.route('/api/v1/ssoft', methods=['POST'])
def ssoft_table(payload=None):
    """ Get the Fink Flat Table
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    # Check all required args are here
    required_args = [i['name'] for i in args_ssoft if i['required'] is True]
    for required_arg in required_args:
        if required_arg not in payload:
            rep = {
                'status': 'error',
                'text': "A value for `{}` is required. Use GET to check arguments.\n".format(required_arg)
            }
            return Response(str(rep), 400)

    if 'schema' in payload:
        if 'flavor' in payload:
            flavor = payload['flavor']
            if flavor not in ['SHG1G2', 'HG1G2', 'HG']:
                rep = {
                    'status': 'error',
                    'text': "flavor needs to be in ['SHG1G2', 'HG1G2', 'HG']\n"
                }
                return Response(str(rep), 400)
            elif flavor == 'SHG1G2':
                SSOFT_COLUMNS = {**COLUMNS, **COLUMNS_SHG1G2}
            elif flavor == 'HG1G2':
                SSOFT_COLUMNS = {**COLUMNS, **COLUMNS_HG1G2}
            elif flavor == 'HG':
                SSOFT_COLUMNS = {**COLUMNS, **COLUMNS_HG}
        else:
            SSOFT_COLUMNS = {**COLUMNS, **COLUMNS_SHG1G2}
        # return the schema of the table
        return jsonify({'args': SSOFT_COLUMNS})

    pdfs = return_ssoft_pdf(payload)

    # Error propagation
    if isinstance(pdfs, Response):
        return pdfs

    output_format = payload.get('output-format', 'json')
    return send_data(pdfs, output_format)

@api_bp.route('/api/v1/resolver', methods=['GET'])
def resolver_arguments():
    """ Obtain information about the resolver service
    """
    if len(request.args) > 0:
        # POST from query URL
        return resolver_table(payload=request.args)
    else:
        return jsonify({'args': args_resolver})

@api_bp.route('/api/v1/resolver', methods=['POST'])
def resolver_table(payload=None):
    """ Get information about an object name
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    # Check all required args are here
    required_args = [i['name'] for i in args_resolver if i['required'] is True]
    for required_arg in required_args:
        if required_arg not in payload:
            rep = {
                'status': 'error',
                'text': "A value for `{}` is required. Use GET to check arguments.\n".format(required_arg)
            }
            return Response(str(rep), 400)

    pdfs = return_resolver_pdf(payload)

    # Error propagation
    if isinstance(pdfs, Response):
        return pdfs

    output_format = payload.get('output-format', 'json')
    return send_data(pdfs, output_format)

@api_bp.route('/api/v1/euclidin', methods=['GET'])
def query_euclidin_arguments():
    """ Obtain information about Euclid input files
    """
    if len(request.args) > 0:
        # POST from query URL
        return query_euclidin(payload=request.args)
    else:
        return jsonify({'args': args_euclidin})

@api_bp.route('/api/v1/euclidin', methods=['POST'])
def query_euclidin(payload=None):
    """ Upload Euclid data in Fink
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    # Check all required args are here
    required_args = [i['name'] for i in args_euclidin if i['required'] is True]
    for required_arg in required_args:
        if required_arg not in payload:
            rep = {
                'status': 'error',
                'text': "A value for `{}` is required. Use GET to check arguments.\n".format(required_arg)
            }
            return Response(str(rep), 400)

    out = upload_euclid_data(payload)

    return out

@api_bp.route('/api/v1/eucliddata', methods=['GET'])
def query_eucliddata_arguments():
    """ Obtain information about Euclid stored data
    """
    if len(request.args) > 0:
        # POST from query URL
        return query_eucliddata(payload=request.args)
    else:
        return jsonify({'args': args_eucliddata})

@api_bp.route('/api/v1/eucliddata', methods=['POST'])
def query_eucliddata(payload=None):
    """ Download Euclid data in Fink
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    # Check all required args are here
    required_args = [i['name'] for i in args_eucliddata if i['required'] is True]
    for required_arg in required_args:
        if required_arg not in payload:
            rep = {
                'status': 'error',
                'text': "A value for `{}` is required. Use GET to check arguments.\n".format(required_arg)
            }
            return Response(str(rep), 400)

    out = download_euclid_data(payload)

    # Error propagation
    if isinstance(out, Response):
        return out

    output_format = payload.get('output-format', 'json')
    return send_data(out, output_format)

@api_bp.route('/api/v1/metadata', methods=['GET'])
def metadata_arguments():
    """ Obtain information about uploading metadata
    """
    if len(request.args) > 0:
        # POST from query URL
        return upload_metadata(payload=request.args)
    else:
        return jsonify({'args': args_metadata})

@api_bp.route('/api/v1/metadata', methods=['POST'])
def upload_metadata(payload=None):
    """ Upload metadata in Fink
    """
    # get payload from the JSON
    if payload is None:
        payload = request.json

    if len(payload) == 1 and 'objectId' in payload:
        # return the associated data
        pdf = retrieve_metadata(payload['objectId'])
        out = send_data(pdf, 'json')
    elif len(payload) == 1 and 'internal_name' in payload:
        # return the associated data
        pdf = retrieve_oid(payload['internal_name'], 'internal_name')
        out = send_data(pdf, 'json')
    elif len(payload) == 1 and 'internal_name_encoded' in payload:
        # return the associated data
        pdf = retrieve_oid(payload['internal_name_encoded'], 'internal_name_encoded')
        out = send_data(pdf, 'json')
    else:
        # Check all required args are here
        required_args = [i['name'] for i in args_metadata if i['required'] is True]
        for required_arg in required_args:
            if required_arg not in payload:
                rep = {
                    'status': 'error',
                    'text': "A value for `{}` is required. Use GET to check arguments.\n".format(required_arg)
                }
                return Response(str(rep), 400)

        out = post_metadata(payload)

    return out

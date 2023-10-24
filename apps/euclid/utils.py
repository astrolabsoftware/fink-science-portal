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

def load_euclid_header(pipeline=None):
    """ Load the header from a Euclid pipeline

    Parameters
    ----------
    pipeline: str
        Name of the pipeline: ssopipe, streakdet, dl

    Returns
    ----------
    header: dict
        Keys are Euclid pipeline names, values are Fink translated names
    """
    if pipeline == 'ssopipe':
        HEADER = {
            'INDEX': 'index',
            'RA': 'ra',
            'DEC': 'dec',
            'PROP_MOT': 'prop_mot',
            'N_DET': 'n_det',
            'CATALOG': 'catalog',
            'X_WORLD': 'x_world',
            'Y_WORLD': 'y_world',
            'ERRA_WORLD': 'erra_world',
            'ERRB_WORLD': 'errb_world',
            'FLUX_AUTO': 'flux_auto',
            'FLUXERR_AUTO': 'fluxerr_auto',
            'MAG_AUTO': 'mag_auto',
            'MAGERR_AUTO': 'magerr_auto',
            'ELONGATION': 'elongation',
            'ELLIPTICITY': 'ellipticity',
            'MJD': 'mjd'
        }
    elif pipeline == 'streakdet':
        HEADER = {
            'Obj_id': 'index',
            'Dither': 'dither',
            'NDet': 'n_det',
            'RA_middle': 'ra_middle',
            'DEC_middle': 'dec_middle',
            'RA_start': 'ra_start',
            'DEC_start': 'dec_start',
            'RA_end': 'ra_end',
            'DEC_end': 'dec_end',
            'MJD_middle': 'mjd_middle',
            'MJD_start': 'mjd_start',
            'MJD_end': 'mjd_end',
            'FLUX_AUTO': 'flux_auto',
            'MAG_AUTO': 'mag_auto'
        }
    elif pipeline == 'dl':
        HEADER = {
            'Obj_id': 'index',
            'Dither': 'dither',
            'NDet': 'n_det',
            'RA_middle': 'ra_middle',
            'DEC_middle': 'dec_middle',
            'RA_start': 'ra_start',
            'DEC_start': 'dec_start',
            'RA_end': 'ra_end',
            'DEC_end': 'dec_end',
            'MJD_middle': 'mjd_middle',
            'MJD_start': 'mjd_start',
            'MJD_end': 'mjd_end',
            'FLUX_AUTO': 'flux_auto',
            'MAG_AUTO': 'mag_auto',
            'Score': 'score'
        }
    else:
        print('Pipeline name {} not understood'.format(pipeline))
        HEADER = {}

    return HEADER


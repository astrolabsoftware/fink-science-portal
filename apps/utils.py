# Copyright 2020 AstroLab Software
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
import numpy as np
import pandas as pd
import gzip
import io
from astropy.io import fits

from astropy.convolution import convolve as astropy_convolve
from astropy.convolution import Gaussian2DKernel
from astropy.convolution import Box2DKernel

from astropy.visualization import AsymmetricPercentileInterval, simple_norm
from astropy.time import Time

import java

def markdownify_objectid(objectid):
    """
    """
    objectid_markdown = '[{}](/{})'.format(
        objectid,
        objectid
    )
    return objectid_markdown

def extract_row(key: str, clientresult: java.util.TreeMap) -> dict:
    """ Extract one row from the client result, and return result as dict
    """
    data = clientresult[key]
    return dict(data)

def readstamp(stamp: str) -> np.array:
    """ Read the stamp data inside an alert.

    Parameters
    ----------
    alert: dictionary
        dictionary containing alert data
    field: string
        Name of the stamps: cutoutScience, cutoutTemplate, cutoutDifference

    Returns
    ----------
    data: np.array
        2D array containing image data
    """
    with gzip.open(io.BytesIO(stamp), 'rb') as f:
        with fits.open(io.BytesIO(f.read())) as hdul:
            data = hdul[0].data
    return data

def extract_properties(data: str, fieldnames: list):
    """
    """
    pdfs = pd.DataFrame()
    for rowkey in data:
        if rowkey == '':
            continue
        properties = extract_row(rowkey, data)
        if fieldnames is not None:
            pdf = pd.DataFrame.from_dict(
                properties, orient='index', columns=[rowkey]).T[fieldnames]
        else:
            pdf = pd.DataFrame.from_dict(
                properties, orient='index', columns=[rowkey]).T
        pdfs = pd.concat((pdfs, pdf))
    return pdfs

def extract_fink_classification_single(data):
    """
    """
    if data is None:
        return 'Error'

    pdf = extract_properties(
        data,
        [
            'i:jd',
            'd:cdsxmatch',
            'd:mulens_class_1',
            'd:mulens_class_2',
            'd:roid',
            'd:snn_sn_vs_all',
            'd:snn_snia_vs_nonia'
        ]
    )
    pdf = pdf.sort_values('i:jd', ascending=False)

    classification = extract_fink_classification(
        pdf['d:cdsxmatch'],
        pdf['d:roid'],
        pdf['d:mulens_class_1'],
        pdf['d:mulens_class_1'],
        pdf['d:snn_snia_vs_nonia'],
        pdf['d:snn_sn_vs_all']
    )
    # cdsxmatch = pdf['d:cdsxmatch'].values[0]
    # roid = int(pdf['d:roid'].values[0])
    # mulens_class_1 = pdf['d:mulens_class_1'].values[0]
    # mulens_class_2 = pdf['d:mulens_class_2'].values[0]
    # rfscore = float(pdf['d:rfscore'].values[0])
    # snn_sn_vs_all = float(pdf['d:snn_sn_vs_all'].values[0])
    # snn_snia_vs_nonia = float(pdf['d:snn_snia_vs_nonia'].values[0])
    #
    # if cdsxmatch != 'Unknown':
    #     classification = cdsxmatch
    # elif roid in [2, 3]:
    #     classification = 'Solar System'
    # elif snn_snia_vs_nonia > 0.5 and snn_sn_vs_all > 0.5:
    #     classification = 'SN candidate'
    # elif mulens_class_1 == 'ML' and mulens_class_2 == 'ML':
    #     classification = 'Microlensing candidate'
    # else:
    #     classification = 'Unknown'

    return classification.values[0]

def extract_fink_classification(cdsxmatch, roid, mulens_class_1, mulens_class_2, snn_snia_vs_nonia, snn_sn_vs_all):
    """
    """
    classification = pd.Series(['Unknown'] * len(cdsxmatch))

    classification[(cdsxmatch != 'Unknown').values] = cdsxmatch[cdsxmatch != 'Unknown']
    classification[(roid.astype(int).isin([2, 3])).values] = 'Solar System'
    classification[((snn_snia_vs_nonia.astype(float) > 0.5)).values * ((snn_sn_vs_all.astype(float) > 0.5)).values] = 'SN candidate'
    classification[((mulens_class_1 == 'ML')).values * ((mulens_class_2 == 'ML')).values] = 'SN candidate'

    classification[classification.isna()] = 'Unknown'

    return classification

def convert_jd(jd, to='iso'):
    """ Convert Julian Date into ISO date (UTC).
    """
    return Time(jd, format='jd').to_value(to)

def convolve(image, smooth=3, kernel='gauss'):
    """ Convolve 2D image. Hacked from aplpy
    """
    if smooth is None and isinstance(kernel, str) and kernel in ['box', 'gauss']:
        return image

    if smooth is not None and not np.isscalar(smooth):
        raise ValueError("smooth= should be an integer - for more complex "
                         "kernels, pass an array containing the kernel "
                         "to the kernel= option")

    # The Astropy convolution doesn't treat +/-Inf values correctly yet, so we
    # convert to NaN here.
    image_fixed = np.array(image, dtype=float, copy=True)
    image_fixed[np.isinf(image)] = np.nan

    if isinstance(kernel, str):
        if kernel == 'gauss':
            kernel = Gaussian2DKernel(
                smooth, x_size=smooth * 5, y_size=smooth * 5)
        elif kernel == 'box':
            kernel = Box2DKernel(smooth, x_size=smooth * 5, y_size=smooth * 5)
        else:
            raise ValueError("Unknown kernel: {0}".format(kernel))

    return astropy_convolve(image, kernel, boundary='extend')

def _data_stretch(
        image, vmin=None, vmax=None, pmin=0.25, pmax=99.75,
        stretch='linear', vmid: float = 10, exponent=2):
    """ Hacked from aplpy
    """
    if vmin is None or vmax is None:
        interval = AsymmetricPercentileInterval(pmin, pmax, n_samples=10000)
        try:
            vmin_auto, vmax_auto = interval.get_limits(image)
        except IndexError:  # no valid values
            vmin_auto = vmax_auto = 0

    if vmin is None:
        #log.info("vmin = %10.3e (auto)" % vmin_auto)
        vmin = vmin_auto
    else:
        pass
        #log.info("vmin = %10.3e" % vmin)

    if vmax is None:
        #log.info("vmax = %10.3e (auto)" % vmax_auto)
        vmax = vmax_auto
    else:
        pass
        #log.info("vmax = %10.3e" % vmax)

    if stretch == 'arcsinh':
        stretch = 'asinh'

    normalizer = simple_norm(
        image, stretch=stretch, power=exponent,
        asinh_a=vmid, min_cut=vmin, max_cut=vmax, clip=False)

    data = normalizer(image, clip=True).filled(0)
    data = np.nan_to_num(data)
    data = np.clip(data * 255., 0., 255.)

    return data.astype(np.uint8)

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
import healpy as hp
import numpy as np
import pandas as pd
import gzip
import io
import requests
import base64
import matplotlib, random

import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import RadialGradiantColorMask

from astropy.io import fits
from astroquery.mpc import MPC

from astropy.convolution import convolve as astropy_convolve
from astropy.convolution import Gaussian2DKernel
from astropy.convolution import Box2DKernel

from astropy.coordinates import SkyCoord, get_constellation
import astropy.units as u

from astropy.visualization import AsymmetricPercentileInterval, simple_norm
from astropy.time import Time

from fink_filters.classification import extract_fink_classification_
from fink_utils.sso.utils import get_miriade_data, query_miriade

hbase_type_converter = {
    'integer': int,
    'long': int,
    'float': float,
    'double': float,
    'string': str,
    'fits/image': str
}

class_colors = {
        'Early SN Ia candidate': 'red',
        'SN candidate': 'orange',
        'Kilonova candidate': 'dark',
        'Microlensing candidate': 'lime',
        'Tracklet': "violet",
        'Solar System MPC': "yellow",
        'Solar System candidate': "indigo",
        'Ambiguous': 'grape',
        'Unknown': 'gray',
        'Simbad': 'blue',
        'Solar System trajectory': "teal",
        'Solar System ephemeris' : 'darkred'
    }

def format_hbase_output(
        hbase_output, schema_client,
        group_alerts: bool, truncated: bool = False,
        extract_color: bool = True, with_constellation: bool = True):
    """
    """
    if hbase_output.isEmpty():
        return pd.DataFrame({})

    # Construct the dataframe
    pdfs = pd.DataFrame.from_dict(hbase_output, orient='index')

    # Tracklet cell contains null if there is nothing
    # and so HBase won't transfer data -- ignoring the column
    if 'd:tracklet' not in pdfs.columns and not truncated:
        pdfs['d:tracklet'] = np.zeros(len(pdfs), dtype='U20')

    # Remove hbase specific fields
    if 'key:key' in pdfs.columns or 'key:time' in pdfs.columns:
        pdfs = pdfs.drop(columns=['key:key', 'key:time'])

    # Type conversion
    pdfs = pdfs.astype(
        {i: hbase_type_converter[schema_client.type(i)] for i in pdfs.columns})

    if not truncated:
        # Fink final classification
        classifications = extract_fink_classification_(
            pdfs['d:cdsxmatch'],
            pdfs['d:roid'],
            pdfs['d:mulens'],
            pdfs['d:snn_snia_vs_nonia'],
            pdfs['d:snn_sn_vs_all'],
            pdfs['d:rf_snia_vs_nonia'],
            pdfs['i:ndethist'],
            pdfs['i:drb'],
            pdfs['i:classtar'],
            pdfs['i:jd'],
            pdfs['i:jdstarthist'],
            pdfs['d:rf_kn_vs_nonkn'],
            pdfs['d:tracklet']
        )

        pdfs['v:classification'] = classifications.values

        if extract_color:
            # Extract color evolution
            pdfs = pdfs.sort_values('i:objectId')
            pdfs['v:g-r'] = extract_last_g_minus_r_each_object(pdfs, kind='last')
            pdfs['v:rate(g-r)'] = extract_last_g_minus_r_each_object(pdfs, kind='rate')

            pdfs = pdfs.sort_values('i:jd', ascending=False)
            pdfs['v:dg'], pdfs['v:rate(dg)'] = extract_delta_color(pdfs, filter_=1)
            pdfs['v:dr'], pdfs['v:rate(dr)'] = extract_delta_color(pdfs, filter_=2)

        # Human readable time
        pdfs['v:lastdate'] = pdfs['i:jd'].apply(convert_jd)
        pdfs['v:firstdate'] = pdfs['i:jdstarthist'].apply(convert_jd)
        pdfs['v:lapse'] = pdfs['i:jd'] - pdfs['i:jdstarthist']

        if with_constellation:
            coords = SkyCoord(
                pdfs['i:ra'],
                pdfs['i:dec'],
                unit='deg'
            )
            constellations = get_constellation(coords)
            pdfs['v:constellation'] = constellations

    # Display only the last alert
    if group_alerts and ('i:jd' in pdfs.columns) and ('i:objectId' in pdfs.columns):
        pdfs['i:jd'] = pdfs['i:jd'].astype(float)
        pdfs = pdfs.loc[pdfs.groupby('i:objectId')['i:jd'].idxmax()]

    # sort values by time
    if 'i:jd' in pdfs.columns:
        pdfs = pdfs.sort_values('i:jd', ascending=False)

    return pdfs

def isoify_time(t):
    try:
        tt = Time(t)
    except ValueError as e:
        ft = float(t)
        if ft // 2400000:
            tt = Time(ft, format='jd')
        else:
            tt = Time(ft, format='mjd')
    return tt.iso

def markdownify_objectid(display, link):
    """
    """
    objectid_markdown = '[{}](/{})'.format(
        display,
        link
    )
    return objectid_markdown

def validate_query(query, query_type):
    """ Validate a query. Need to be rewritten in a better way.
    """
    empty_query_type = (query_type is None) or (query_type == '')

    if empty_query_type:
        # This can only happen in queries formed from URL parameters
        header = "Empty query type"
        text = "You need to specify a query_type in your request (e.g. ?query_type=Conesearch&ra=value&dec=value&radius=value)"
        return {'flag': False, 'header': header, 'text': text}

    empty_query = (query is None) or (query == '')

    # no queries
    if empty_query and ((query_type == 'objectId') or (query_type == 'Conesearch') or (query_type == 'Date Search')):
        header = "Empty query"
        text = "You need to choose a query type and fill the search bar"
        return {'flag': False, 'header': header, 'text': text}

    # bad objectId
    bad_objectid = (query_type == 'objectId') and not (query.startswith('ZTF'))
    if bad_objectid:
        header = "Bad ZTF object ID"
        text = "ZTF object ID must start with `ZTF`"
        return {'flag': False, 'header': header, 'text': text}

    # bad conesearch
    bad_conesearch = (query_type == 'Conesearch') and not ((len(query.split(',')) == 3) or (len(query.split(',')) == 5))
    if bad_conesearch:
        header = "Bad Conesearch formula"
        text = "Conesearch must contain comma-separated RA, Dec, radius or RA, Dec, radius, startdate, window. See Help for more information."
        return {'flag': False, 'header': header, 'text': text}

    # bad search date
    if query_type == 'Date Search':
        try:
            _ = isoify_time(query)
        except (ValueError, TypeError) as e:
            header = 'Bad start time'
            return {'flag': False, 'header': header, 'text': str(e)}

    return {'flag': True, 'header': 'Good query', 'text': 'Well done'}

def extract_row(key: str, clientresult) -> dict:
    """ Extract one row from the client result, and return result as dict
    """
    data = clientresult[key]
    return dict(data)

def readstamp(stamp: str, return_type='array') -> np.array:
    """ Read the stamp data inside an alert.

    Parameters
    ----------
    alert: dictionary
        dictionary containing alert data
    field: string
        Name of the stamps: cutoutScience, cutoutTemplate, cutoutDifference
    return_type: str
        Data block of HDU 0 (`array`) or original FITS uncompressed (`FITS`) as file-object.
        Default is `array`.

    Returns
    ----------
    data: np.array
        2D array containing image data (`array`) or FITS file uncompressed as file-object (`FITS`)
    """
    with gzip.open(io.BytesIO(stamp), 'rb') as f:
        with fits.open(io.BytesIO(f.read())) as hdul:
            if return_type == 'array':
                data = hdul[0].data
            elif return_type == 'FITS':
                data = io.BytesIO()
                hdul.writeto(data)
                data.seek(0)
    return data

def extract_cutouts(pdf: pd.DataFrame, client, col=None, return_type='array') -> pd.DataFrame:
    """ Query and uncompress cutout data from the HBase table

    Inplace modifications

    Parameters
    ----------
    pdf: Pandas DataFrame
        DataFrame returned by `format_hbase_output` (see api/api.py)
    client: com.Lomikel.HBaser.HBaseClient
        HBase client used to query the database
    col: str
        Name of the cutouts to be downloaded (e.g. b:cutoutScience_stampData). If None, return all 3
    return_type: str
        array or original gzipped FITS

    Returns
    ----------
    pdf: Pandas DataFrame
        Modified original DataFrame with cutout data uncompressed (2D array)
    """
    if col is not None:
        cols = ['b:cutoutScience_stampData', 'b:cutoutTemplate_stampData', 'b:cutoutDifference_stampData']
        assert col in cols
        pdf[col] = pdf[col].apply(
            lambda x: readstamp(client.repository().get(x), return_type=return_type)
        )
        return pdf

    if 'b:cutoutScience_stampData' not in pdf.columns:
        pdf['b:cutoutScience_stampData'] = 'binary:' + pdf['i:objectId'] + '_' + pdf['i:jd'].astype('str') + ':cutoutScience_stampData'
        pdf['b:cutoutTemplate_stampData'] = 'binary:' + pdf['i:objectId'] + '_' + pdf['i:jd'].astype('str') + ':cutoutTemplate_stampData'
        pdf['b:cutoutDifference_stampData'] = 'binary:' + pdf['i:objectId'] + '_' + pdf['i:jd'].astype('str') + ':cutoutDifference_stampData'

    pdf['b:cutoutScience_stampData'] = pdf['b:cutoutScience_stampData'].apply(
        lambda x: readstamp(client.repository().get(x), return_type=return_type)
    )
    pdf['b:cutoutTemplate_stampData'] = pdf['b:cutoutTemplate_stampData'].apply(
        lambda x: readstamp(client.repository().get(x), return_type=return_type)
    )
    pdf['b:cutoutDifference_stampData'] = pdf['b:cutoutDifference_stampData'].apply(
        lambda x: readstamp(client.repository().get(x), return_type=return_type)
    )
    return pdf

def extract_properties(data: str, fieldnames: list):
    """
    """
    pdfs = pd.DataFrame.from_dict(data, orient='index')
    if fieldnames is not None:
        return pdfs[fieldnames]
    else:
        return pdfs

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
    #data = np.clip(data * 255., 0., 255.)

    return data#.astype(np.uint8)

def mag2fluxcal_snana(magpsf: float, sigmapsf: float):
    """ Conversion from magnitude to Fluxcal from SNANA manual

    Parameters
    ----------
    magpsf: float
        PSF-fit magnitude from ZTF
    sigmapsf: float

    Returns
    ----------
    fluxcal: float
        Flux cal as used by SNANA
    fluxcal_err: float
        Absolute error on fluxcal (the derivative has a minus sign)

    """
    if magpsf is None:
        return None, None
    fluxcal = 10 ** (-0.4 * magpsf) * 10 ** (11)
    fluxcal_err = 9.21034 * 10 ** 10 * np.exp(-0.921034 * magpsf) * sigmapsf

    return fluxcal, fluxcal_err

def apparent_flux(fid, magpsf, sigmapsf, magnr, sigmagnr, magzpsci, isdiffpos):
    """ Compute apparent flux from difference magnitude supplied by ZTF
    This was heavily influenced by the computation provided by Lasair:
    https://github.com/lsst-uk/lasair/blob/master/src/alert_stream_ztf/common/mag.py
    Paramters
    ---------
    fid
        filter, 1 for green and 2 for red
    magpsf,sigmapsf; floats
        magnitude from PSF-fit photometry, and 1-sigma error
    magnr,sigmagnr: floats
        magnitude of nearest source in reference image PSF-catalog
        within 30 arcsec and 1-sigma error
    magzpsci: float
        Magnitude zero point for photometry estimates
    isdiffpos: str
        t or 1 => candidate is from positive (sci minus ref) subtraction;
        f or 0 => candidate is from negative (ref minus sci) subtraction

    Returns
    --------
    dc_flux: float
        Apparent magnitude
    dc_sigflux: float
        Error on apparent magnitude
    """
    if magpsf is None:
        return None, None
    # zero points. Looks like they are fixed.
    ref_zps = {1: 26.325, 2: 26.275, 3: 25.660}
    magzpref = ref_zps[fid]

    # reference flux and its error
    magdiff = magzpref - magnr
    if magdiff > 12.0:
        magdiff = 12.0
    ref_flux = 10**(0.4 * magdiff)
    ref_sigflux = (sigmagnr / 1.0857) * ref_flux

    # difference flux and its error
    if magzpsci == 0.0:
        magzpsci = magzpref
    magdiff = magzpsci - magpsf
    if magdiff > 12.0:
        magdiff = 12.0
    difference_flux = 10**(0.4 * magdiff)
    difference_sigflux = (sigmapsf / 1.0857) * difference_flux

    # add or subract difference flux based on isdiffpos
    if isdiffpos == 't':
        dc_flux = ref_flux + difference_flux
    else:
        dc_flux = ref_flux - difference_flux

    # assumes errors are independent. Maybe too conservative.
    dc_sigflux = np.sqrt(difference_sigflux**2 + ref_sigflux**2)

    return dc_flux, dc_sigflux

def dc_mag(fid, magpsf, sigmapsf, magnr, sigmagnr, magzpsci, isdiffpos):
    """ Compute apparent magnitude from difference magnitude supplied by ZTF
    Parameters
    Stolen from Lasair.
    ----------
    fid
        filter, 1 for green and 2 for red
    magpsf,sigmapsf
        magnitude from PSF-fit photometry, and 1-sigma error
    magnr,sigmagnr
        magnitude of nearest source in reference image PSF-catalog
        within 30 arcsec and 1-sigma error
    magzpsci
        Magnitude zero point for photometry estimates
    isdiffpos
        t or 1 => candidate is from positive (sci minus ref) subtraction;
        f or 0 => candidate is from negative (ref minus sci) subtraction
    """
    # zero points. Looks like they are fixed.
    ref_zps = {1: 26.325, 2: 26.275, 3: 25.660}
    magzpref = ref_zps[fid]

    # difference flux and its error
    if magzpsci is None:
        magzpsci = magzpref

    dc_flux, dc_sigflux = apparent_flux(
        fid, magpsf, sigmapsf, magnr, sigmagnr, magzpsci, isdiffpos
    )

    # apparent mag and its error from fluxes
    if (dc_flux == dc_flux) and dc_flux > 0.0:
        dc_mag = magzpsci - 2.5 * np.log10(dc_flux)
        dc_sigmag = dc_sigflux / dc_flux * 1.0857
    else:
        dc_mag = magzpsci
        dc_sigmag = sigmapsf

    return dc_mag, dc_sigmag

def g_minus_r(fid, mag):
    """ Compute r-g based on vectors of filters and magnitudes
    """
    if len(fid) == 2:
        # +1 if [g, r]
        # -1 if [r, g]
        sign = np.diff(fid)[0]
    else:
        # last measurement
        last_fid = fid[-1]

        # last measurement with different filter
        # could take the mean
        index_other = np.where(np.array(fid) != last_fid)[0][-1]

        sign = np.diff([fid[index_other], last_fid])[0]
        mag = [mag[index_other], mag[-1]]

    return -1 * sign * np.diff(mag)[0]

def extract_last_g_minus_r_each_object(pdf, kind):
    """ Extract last g-r for each object in a pandas DataFrame
    """
    # extract unique objects
    ids, indices = np.unique(pdf['i:objectId'].values, return_index=True)
    ids = [pdf['i:objectId'].values[index] for index in sorted(indices)]

    if kind == 'last':
        pdf.loc[:, 'v:g-r'] = 0.0
    elif kind == 'rate':
        pdf.loc[:, 'v:rate(g-r)'] = 0.0

    # loop over objects
    for id_ in ids:
        subpdf = pdf[pdf['i:objectId'] == id_]

        subpdf['i:jd'] = subpdf['i:jd'].astype(float)
        subpdf['i:fid'] = subpdf['i:fid'].astype(int)
        subpdf = subpdf.sort_values('i:jd', ascending=False)

        # Compute DC mag
        cols = [
            'i:fid', 'i:magpsf', 'i:sigmapsf', 'i:magnr', 'i:sigmagnr', 'i:magzpsci', 'i:isdiffpos',
        ]

        mag, err = np.array(
            [
                dc_mag(int(i[0]), float(i[1]), float(i[2]), float(i[3]), float(i[4]), float(i[5]), i[6])
                    for i in zip(*[subpdf[j].values for j in cols])
            ]
        ).T
        subpdf['i:dcmag'] = mag

        # group by night
        gpdf = subpdf.groupby('i:nid')[['i:dcmag', 'i:fid', 'i:jd', 'i:nid']].agg(list)

        # take only nights with at least measurements on 2 different filters
        mask = gpdf['i:fid'].apply(
            lambda x: (len(x) > 1) & (np.sum(x) / len(x) != x[0])
        )
        gpdf_night = gpdf[mask]

        # compute r-g for those nights
        values = [g_minus_r(i, j) for i, j in zip(gpdf_night['i:fid'].values, gpdf_night['i:dcmag'].values)]
        nid = [nid_ for nid_ in gpdf[mask]['i:jd'].apply(lambda x: x[0]).values]
        jd = [jd_ for jd_ in gpdf[mask]['i:nid'].apply(lambda x: np.mean(x)).values]

        if kind == 'last':
            vec_ = np.diff(values, prepend=np.nan)
            for val, nid_ in zip(vec_, nid):
                pdf['v:g-r'][pdf['i:jd'] == nid_] = val
        elif kind == 'rate':
            vec_ = np.diff(values, prepend=np.nan)
            jd_diff = np.diff(jd, prepend=np.nan)
            for val, jd_, nid_ in zip(vec_, jd_diff, nid):
                pdf['v:rate(g-r)'][pdf['i:jd'] == nid_] = val / jd_

    if kind == 'last':
        return pdf['v:g-r'].replace(0.0, np.nan).values
    elif kind == 'rate':
        return pdf['v:rate(g-r)'].replace(0.0, np.nan).values

def extract_delta_color(pdf: pd.DataFrame, filter_: int):
    """ Extract last g-r for each object in a pandas DataFrame

    Parameters
    ----------
    pdf: pandas DataFrame
        DataFrame containing alert parameters from an API call
    filter_: int
        Filter band, as integer. g: 1, r: 2

    Returns
    ----------
    vec: np.array
        Vector containing delta(mag) for the filter `filter_`. Last measurement
        shown first.
    rate: np.array
        Vector containing delta(mag)/delta(time) for the filter `filter_`.
        Last measurement shown first.
    """
    # extract unique objects
    ids, indices = np.unique(pdf['i:objectId'].values, return_index=True)
    ids = [pdf['i:objectId'].values[index] for index in sorted(indices)]

    # loop over objects
    vec = []
    rate = []
    for id_ in ids:
        maskId = pdf['i:objectId'] == id_
        subpdf = pdf[maskId]

        subpdf['i:jd'] = subpdf['i:jd'].astype(float)
        subpdf['i:fid'] = subpdf['i:fid'].astype(int)
        subpdf = subpdf.sort_values('i:jd', ascending=False)

        # Compute DC mag
        cols = [
            'i:fid', 'i:magpsf', 'i:sigmapsf', 'i:magnr', 'i:sigmagnr', 'i:magzpsci', 'i:isdiffpos',
        ]

        mag, err = np.array(
            [
                dc_mag(int(i[0]), float(i[1]), float(i[2]), float(i[3]), float(i[4]), float(i[5]), i[6])
                    for i in zip(*[subpdf[j].values for j in cols])
            ]
        ).T
        subpdf['i:dcmag'] = mag

        vec_ = np.zeros_like(mag)
        rate_ = np.zeros_like(mag)

        mask = subpdf['i:fid'] == filter_

        # Diff color
        vec_[mask] = subpdf[mask]['i:dcmag'].diff(periods=-1).values

        # temp diff jd
        djd = subpdf[mask]['i:jd'].diff(periods=-1).values

        # color rate
        rate_[mask] = vec_[mask] / djd
        vec = np.concatenate([vec, vec_])
        rate = np.concatenate([rate, rate_])

    # replace nans by 0.0
    vec = np.nan_to_num(vec)
    rate = np.nan_to_num(rate)

    return vec, rate

def queryMPC(number, kind='asteroid'):
    """Query MPC for information about object 'designation'.

    Parameters
    ----------
    designation: str
        A name for the object that the MPC will understand.
        This can be a number, proper name, or the packed designation.
    kind: str
        asteroid or comet

    Returns
    -------
    pd.Series
        Series containing orbit and select physical information.
    """
    try:
        mpc = MPC.query_object(target_type=kind, number=number)
        mpc = mpc[0]
    except IndexError:
        try:
            mpc = MPC.query_object(target_type=kind, designation=number)
            mpc = mpc[0]
        except IndexError:
            return pd.Series({})
    except IndexError:
        return pd.Series({})
    except RuntimeError:
        return pd.Series({})
    orbit = pd.Series(mpc)
    return orbit

def convert_mpc_type(index):
    dic = {
        0: "Unclassified (mostly Main Belters)",
        1: "Atiras",
        2: "Atens",
        3: "Apollos",
        4: "Amors",
        5: "Mars Crossers",
        6: "Hungarias",
        7: "Phocaeas",
        8: "Hildas",
        9: "Jupiter Trojans",
        10: "Distant Objects",
    }
    return dic[index]

def get_superpixels(idx, nside_subpix, nside_superpix, nest=False):
    """ Compute the indices of superpixels that contain a subpixel.

    Note that nside_subpix > nside_superpix
    """
    idx = np.array(idx)
    nside_superpix = np.asarray(nside_superpix)
    nside_subpix = np.asarray(nside_subpix)

    if not nest:
        idx = hp.ring2nest(nside_subpix, idx)

    ratio = np.array((nside_subpix // nside_superpix) ** 2, ndmin=1)
    idx //= ratio

    if not nest:
        m = idx == -1
        idx[m] = 0
        idx = hp.nest2ring(nside_superpix, idx)
        idx[m] = -1

    return idx

def return_empty_query():
    """ Wrapper for malformed query from URL
    """
    return '', '', None

def extract_parameter_value_from_url(param_dic, key, default):
    """
    """
    if key in param_dic:
        val = param_dic[key]
    else:
        val = default
    return val

def extract_query_url(search: str):
    """ try to infer the query from an URL

    Parameters
    ----------
    search: str
        String returned by `dcc.Location.search` property.
        Typically starts with ?

    Returns
    ----------
    query: str
        The query formed by the args in the URL
    query_type: str
        The type of query (objectID, SSO, Conesearch, etc.)
    dropdown_option: str
        Parameter value used in `Date` or `Class` search.
    """
    # remove trailing ?
    search = search[1:]

    # split parameters
    parameters = search.split('&')

    # Make a dictionary with the parameter keys and values
    param_dic = {s.split('=')[0]: s.split('=')[1] for s in parameters}

    # if the user forgot to specify the query type
    if 'query_type' not in param_dic:
        return return_empty_query()

    query_type = param_dic['query_type']

    if query_type == 'objectId':
        query = extract_parameter_value_from_url(param_dic, 'objectId', None)
        dropdown_option = None
    elif query_type == 'Conesearch':
        ra = extract_parameter_value_from_url(param_dic, 'ra', '')
        dec = extract_parameter_value_from_url(param_dic, 'dec', '')
        radius = extract_parameter_value_from_url(param_dic, 'radius', '')
        startdate = extract_parameter_value_from_url(
            param_dic, 'startdate_conesearch', ''
        )
        window = extract_parameter_value_from_url(
            param_dic, 'window_days_conesearch', ''
        )

        query = '{}, {}, {}'.format(ra, dec, radius)

        if startdate != '' and window != '':
            query += ', {}, {}'.format(startdate.replace('%20', ' '), window)

        dropdown_option = None

    elif query_type == 'Date%20Search':
        startdate = extract_parameter_value_from_url(param_dic, 'startdate', '')
        window = extract_parameter_value_from_url(param_dic, 'window', '')

        query = '{}'.format(startdate.replace('%20', ' '))
        dropdown_option = window

    elif query_type == 'Class%20Search':
        # This one is weird. The Class search has 4 parameters: class, n,
        # startdate, stopdate.
        # But from the webpage, the user can only select the class. The other
        # parameters are fixed (n=100, startdate=2019, stopdate=now).
        # Of course using the API, one can do whatever, but using the
        # webpage (or URL query), one can only change the class... to be fixed
        class_ = extract_parameter_value_from_url(param_dic, 'class', '')

        query = class_.replace('%20', ' ')

        dropdown_option = class_.replace('%20', ' ')

    elif query_type == 'SSO':
        n_or_d = extract_parameter_value_from_url(param_dic, 'n_or_d', '')

        query = n_or_d.replace('%20', ' ')
        dropdown_option = None

    return query, query_type.replace('%20', ' '), dropdown_option

def sine_fit(x, a, b):
    """ Sinusoidal function a*sin( 2*(x-b) )
    :x: float - in degrees
    :a: float - Amplitude
    :b: float - Phase offset

    """
    return a * np.sin(2 * np.radians(x - b))

def pil_to_b64(im, enc_format="png", **kwargs):
    """ Converts a PIL Image into base64 string for HTML displaying

    Parameters
    ----------
    im: PIL Image object
        PIL Image object
    enc_format: str
        The image format for displaying.

    Returns
    -----------
    base64 encoding
    """

    buff = io.BytesIO()
    im.save(buff, format=enc_format, **kwargs)
    encoded = base64.b64encode(buff.getvalue()).decode("utf-8")

    return encoded

def generate_qr(data):
    """ Generate a QR code from the data

    To check the generated QR code, simply use:
    >>> img = generate_qr("https://fink-broker.org")
    >>> img.get_image().show()

    Parameters
    ----------
    data: str
        Typically an URL

    Returns
    ----------
    PIL image
    """
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(data)

    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        eye_drawer=RoundedModuleDrawer(),
        color_mask=RadialGradiantColorMask(edge_color=(245, 98, 46))
    )

    return img

def random_color():
    hex_colors_dic = {}
    rgb_colors_dic = {}
    hex_colors_only = []
    for name, hex in matplotlib.colors.cnames.items():
        hex_colors_only.append(hex)
        hex_colors_dic[name] = hex
        rgb_colors_dic[name] = matplotlib.colors.to_rgb(hex)
    
    return hex_colors_dic, rgb_colors_dic, random.choice(hex_colors_only)

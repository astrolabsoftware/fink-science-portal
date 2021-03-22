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

hbase_type_converter = {
    'integer': int,
    'long': int,
    'float': float,
    'double': float,
    'string': str,
    'fits/image': str
}

def format_hbase_output(hbase_output, schema_client, group_alerts: bool, truncated: bool = False):
    """
    """
    if hbase_output.isEmpty():
        return pd.DataFrame({})

    # Construct the dataframe
    pdfs = pd.DataFrame.from_dict(hbase_output, orient='index')

    # Remove hbase specific fields
    if 'key:key' in pdfs.columns or 'key:time' in pdfs.columns:
        pdfs = pdfs.drop(columns=['key:key', 'key:time'])

    # Type conversion
    pdfs = pdfs.astype(
        {i: hbase_type_converter[schema_client.type(i)] for i in pdfs.columns})

    if not truncated:
        # Fink final classification
        classifications = extract_fink_classification(
            pdfs['d:cdsxmatch'],
            pdfs['d:roid'],
            pdfs['d:mulens_class_1'],
            pdfs['d:mulens_class_2'],
            pdfs['d:snn_snia_vs_nonia'],
            pdfs['d:snn_sn_vs_all'],
            pdfs['d:rfscore'],
            pdfs['i:ndethist'],
            pdfs['i:drb'],
            pdfs['i:classtar']
        )

        pdfs['v:classification'] = classifications

        # Extract color evolution
        pdfs = pdfs.sort_values('i:objectId')
        pdfs['v:r-g'] = extract_last_r_minus_g_each_object(pdfs, kind='last')
        pdfs['v:rate(r-g)'] = extract_last_r_minus_g_each_object(pdfs, kind='rate')

        # Human readable time
        pdfs['v:lastdate'] = pdfs['i:jd'].apply(convert_jd)

    # Display only the last alert
    if group_alerts:
        pdfs['i:jd'] = pdfs['i:jd'].astype(float)
        pdfs = pdfs.loc[pdfs.groupby('i:objectId')['i:jd'].idxmax()]

    # sort values by time
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

def markdownify_objectid(objectid):
    """
    """
    objectid_markdown = '[{}](/{})'.format(
        objectid,
        objectid
    )
    return objectid_markdown

def validate_query(query, query_type):
    """ Validate a query. Need to be rewritten in a better way.
    """
    empty_query = (query is None) or (query == '')

    # no queries
    if empty_query and ((query_type == 'objectID') or (query_type == 'Conesearch') or (query_type == 'Date')):
        header = "Empty query"
        text = "You need to choose a query type and fill the search bar"
        return {'flag': False, 'header': header, 'text': text}

    # bad objectId
    bad_objectid = (query_type == 'objectID') and not (query.startswith('ZTF'))
    if bad_objectid:
        header = "Bad ZTF object ID"
        text = "ZTF object ID must start with `ZTF`"
        return {'flag': False, 'header': header, 'text': text}

    # bad conesearch
    bad_conesearch = (query_type == 'Conesearch') and not (len(query.split(',')) == 3)
    if bad_conesearch:
        header = "Bad Conesearch formula"
        text = "Conesearch must contain comma-separated RA, Dec, radius"
        return {'flag': False, 'header': header, 'text': text}

    # bad search date
    if query_type == 'Date':
        try:
            _ = isoify_time(query)
        except (ValueError, TypeError) as e:
            header = 'Bad start time'
            return {'flag': False, 'header': header, 'text': str(e)}

    return {'flag': True, 'header': 'Good query', 'text': 'Well done'}

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

def extract_cutouts(pdf: pd.DataFrame, client) -> pd.DataFrame:
    """ Query and uncompress cutout data from the HBase table

    Inplace modifications

    Parameters
    ----------
    pdf: Pandas DataFrame
        DataFrame returned by `format_hbase_output` (see api.py)
    client: com.Lomikel.HBaser.HBaseClient
        HBase client used to query the database

    Returns
    ----------
    pdf: Pandas DataFrame
        Modified original DataFrame with cutout data uncompressed (2D array)
    """
    if 'b:cutoutScience_stampData' not in pdf.columns:
        pdf['b:cutoutScience_stampData'] = 'binary:' + pdf['i:objectId'] + '_' + pdf['i:jd'].astype('str') + ':cutoutScience_stampData'
        pdf['b:cutoutTemplate_stampData'] = 'binary:' + pdf['i:objectId'] + '_' + pdf['i:jd'].astype('str') + ':cutoutTemplate_stampData'
        pdf['b:cutoutDifference_stampData'] = 'binary:' + pdf['i:objectId'] + '_' + pdf['i:jd'].astype('str') + ':cutoutDifference_stampData'

    pdf['b:cutoutScience_stampData'] = pdf['b:cutoutScience_stampData'].apply(
        lambda x: readstamp(client.repository().get(x))
    )
    pdf['b:cutoutTemplate_stampData'] = pdf['b:cutoutTemplate_stampData'].apply(
        lambda x: readstamp(client.repository().get(x))
    )
    pdf['b:cutoutDifference_stampData'] = pdf['b:cutoutDifference_stampData'].apply(
        lambda x: readstamp(client.repository().get(x))
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
            'd:snn_snia_vs_nonia',
            'd:rfscore',
            'i:ndethist',
            'i:drb',
            'i:classtar'
        ]
    )
    pdf = pdf.sort_values('i:jd', ascending=False)

    classification = extract_fink_classification(
        pdf['d:cdsxmatch'],
        pdf['d:roid'],
        pdf['d:mulens_class_1'],
        pdf['d:mulens_class_2'],
        pdf['d:snn_snia_vs_nonia'],
        pdf['d:snn_sn_vs_all'],
        pdf['d:rfscore'],
        pdf['i:ndethist'],
        pdf['i:drb'],
        pdf['i:classtar']
    )

    return classification[0]

def extract_fink_classification(
        cdsxmatch, roid, mulens_class_1, mulens_class_2,
        snn_snia_vs_nonia, snn_sn_vs_all, rfscore,
        ndethist, drb, classtar):
    """ Assign label to alerts based on individual science module results

    See https://arxiv.org/abs/2009.10185 for more information
    """
    classification = pd.Series(['Unknown'] * len(cdsxmatch))
    ambiguity = pd.Series([0] * len(cdsxmatch))

    # Microlensing classification
    f_mulens = (mulens_class_1 == 'ML') & (mulens_class_2 == 'ML')

    # SN Ia
    snn1 = snn_snia_vs_nonia.astype(float) > 0.5
    snn2 = snn_sn_vs_all.astype(float) > 0.5
    active_learn = rfscore.astype(float) > 0.5
    low_ndethist = ndethist.astype(int) < 400
    high_drb = drb.astype(float) > 0.5
    high_classtar = classtar.astype(float) > 0.4
    early_ndethist = ndethist.astype(int) <= 20

    list_simbad_galaxies = [
        "galaxy",
        "Galaxy",
        "EmG",
        "Seyfert",
        "Seyfert_1",
        "Seyfert_2",
        "BlueCompG",
        "StarburstG",
        "LSB_G",
        "HII_G",
        "High_z_G",
        "GinPair",
        "GinGroup",
        "BClG",
        "GinCl",
        "PartofG",
    ]
    keep_cds = \
        ["Unknown", "Fail", "Candidate_SN*", "SN", "Transient"] + list_simbad_galaxies

    f_sn = (snn1 | snn2) & cdsxmatch.isin(keep_cds) & low_ndethist & high_drb & high_classtar
    f_sn_early = early_ndethist & active_learn & f_sn

    # Solar System Objects
    f_roid = roid.astype(int).isin([2, 3])

    # Simbad xmatch
    f_simbad = ~cdsxmatch.isin(['Unknown', 'Transient', 'Fail'])

    classification.mask(f_mulens.values, 'Microlensing candidate', inplace=True)
    classification.mask(f_sn.values, 'SN candidate', inplace=True)
    classification.mask(f_sn_early.values, 'Early SN candidate', inplace=True)
    classification.mask(f_roid.values, 'Solar System', inplace=True)

    # If several flags are up, we cannot rely on the classification
    ambiguity[f_mulens.values] += 1
    ambiguity[f_sn.values] += 1
    ambiguity[f_roid.values] += 1
    f_ambiguity = ambiguity > 1
    classification.mask(f_ambiguity.values, 'Ambiguous', inplace=True)

    classification = np.where(f_simbad, cdsxmatch, classification)

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

def r_minus_g(fid, mag):
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

    return sign * np.diff(mag)[0]

def extract_last_r_minus_g_each_object(pdf, kind):
    """ Extract last r-g for each object in a pandas DataFrame
    """
    # extract unique objects
    ids, indices = np.unique(pdf['i:objectId'].values, return_index=True)
    ids = [pdf['i:objectId'].values[index] for index in sorted(indices)]
    out_r_minus_g = []

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
        gpdf = subpdf.groupby('i:nid')[['i:dcmag', 'i:fid', 'i:jd']].agg(list)

        # take only nights with at least measurements on 2 different filters
        mask = gpdf['i:fid'].apply(
            lambda x: (len(x) > 1) & (np.sum(x) / len(x) != x[0])
        )
        gpdf_night = gpdf[mask]

        # compute r-g for those nights
        values = [r_minus_g(i, j) for i, j in zip(gpdf_night['i:fid'].values, gpdf_night['i:dcmag'].values)]

        if kind == 'last':
            if len(values) > 0:
                val = values[-1]
            else:
                val = None
            out_r_minus_g = np.concatenate(
                [
                    out_r_minus_g,
                    [val] * len(subpdf)
                ]
            )
        elif kind == 'rate':
            if len(values) > 1:
                val = values[-1] - values[0]
                dt = np.mean(gpdf_night['i:jd'].values[-1]) - np.mean(gpdf_night['i:jd'].values[0])
                rate = val / dt
            else:
                rate = None
            out_r_minus_g = np.concatenate(
                [
                    out_r_minus_g,
                    [rate] * len(subpdf)
                ]
            )

    return out_r_minus_g

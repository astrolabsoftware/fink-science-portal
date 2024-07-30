# Copyright 2020-2024 AstroLab Software
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
import base64
import gzip
import io

import healpy as hp
import numpy as np
import pandas as pd
import qrcode
import requests
from astropy.convolution import Box2DKernel, Gaussian2DKernel
from astropy.convolution import convolve as astropy_convolve
from astropy.coordinates import SkyCoord, get_constellation
from astropy.io import fits
from astropy.time import Time
from astropy.visualization import AsymmetricPercentileInterval, simple_norm
from astroquery.mpc import MPC
from fink_filters.classification import extract_fink_classification_
from fink_utils.xmatch.simbad import get_simbad_labels
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer

import apps.api
from app import APIURL, LOCALAPI, server

# TODO: split these UI snippets into separate file?..
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash import html

# Access local or remove API endpoint
from json import loads as json_loads

from flask import Response

simbad_types = get_simbad_labels("old_and_new")
simbad_types = sorted(simbad_types, key=lambda s: s.lower())

# For int we use `Int64` due to the presence of NaN
# See https://pandas.pydata.org/pandas-docs/version/1.3/user_guide/integer_na.html
hbase_type_converter = {
    "integer": "Int64",
    "long": int,
    "float": float,
    "double": float,
    "string": str,
    "fits/image": str,
    "boolean": bool,
}

class_colors = {
    "Early SN Ia candidate": "red",
    "SN candidate": "orange",
    "Kilonova candidate": "dark",
    "Microlensing candidate": "lime",
    "Tracklet": "violet",
    "Solar System MPC": "yellow",
    "Solar System candidate": "indigo",
    "Ambiguous": "grape",
    "Unknown": "gray",
    "Simbad": "blue",
}


def hbase_to_dict(hbase_output):
    """Optimize hbase output TreeMap for faster conversion to DataFrame"""
    # Naive Python implementation
    # optimized = {i: dict(j) for i, j in hbase_output.items()}

    # Here we assume JPype is already initialized
    import json

    from org.json import JSONObject

    # We do bulk export to JSON on Java side to avoid overheads of iterative access
    # and then parse it back to Dict in Python
    optimized = json.loads(JSONObject(hbase_output).toString())

    return optimized


def convert_datatype(series: pd.Series, type_: type) -> pd.Series:
    """Convert Series from HBase data with proper type

    Parameters
    ----------
    series: pd.Series
        a column of the DataFrame
    type_: type
        Python built-in type (Int64, int, str, float, bool)
    """
    return series.astype(type_)


def format_hbase_output(
    hbase_output,
    schema_client,
    group_alerts: bool,
    truncated: bool = False,
    extract_color: bool = True,
    with_constellation: bool = True,
):
    """ """
    if len(hbase_output) == 0:
        return pd.DataFrame({})

    # Construct the dataframe
    pdfs = pd.DataFrame.from_dict(hbase_to_dict(hbase_output), orient="index")

    # Tracklet cell contains null if there is nothing
    # and so HBase won't transfer data -- ignoring the column
    if "d:tracklet" not in pdfs.columns and not truncated:
        pdfs["d:tracklet"] = np.zeros(len(pdfs), dtype="U20")

    # Remove hbase specific fields
    for _ in ["key:key", "key:time"]:
        if _ in pdfs.columns:
            pdfs = pdfs.drop(columns=_)

    if "d:spicy_name" in pdfs.columns:
        pdfs = pdfs.drop(columns="d:spicy_name")

    # Remove cutouts if their fields are here but empty
    for _ in ["Difference", "Science", "Template"]:
        colname = f"b:cutout{_}_stampData"
        if colname in pdfs.columns and pdfs[colname].to_numpy()[0].startswith(
            "binary:ZTF"
        ):
            pdfs = pdfs.drop(columns=colname)

    # Type conversion
    for col in pdfs.columns:
        pdfs[col] = convert_datatype(
            pdfs[col],
            hbase_type_converter[schema_client.type(col)],
        )

    # cast 'nan' into `[]` for easier json decoding
    for col in ["d:lc_features_g", "d:lc_features_r"]:
        if col in pdfs.columns:
            pdfs[col] = pdfs[col].replace("nan", "[]")

    pdfs = pdfs.copy()  # Fix Pandas' "DataFrame is highly fragmented" warning

    if not truncated:
        # Fink final classification
        classifications = extract_fink_classification_(
            pdfs["d:cdsxmatch"],
            pdfs["d:roid"],
            pdfs["d:mulens"],
            pdfs["d:snn_snia_vs_nonia"],
            pdfs["d:snn_sn_vs_all"],
            pdfs["d:rf_snia_vs_nonia"],
            pdfs["i:ndethist"],
            pdfs["i:drb"],
            pdfs["i:classtar"],
            pdfs["i:jd"],
            pdfs["i:jdstarthist"],
            pdfs["d:rf_kn_vs_nonkn"],
            pdfs["d:tracklet"],
        )

        pdfs["v:classification"] = classifications.to_numpy()

        if extract_color:
            # Extract color evolution
            pdfs = extract_rate_and_color(pdfs)

        # Human readable time
        pdfs["v:lastdate"] = convert_jd(pdfs["i:jd"])
        pdfs["v:firstdate"] = convert_jd(pdfs["i:jdstarthist"])
        pdfs["v:lapse"] = pdfs["i:jd"] - pdfs["i:jdstarthist"]

        if with_constellation:
            coords = SkyCoord(
                pdfs["i:ra"],
                pdfs["i:dec"],
                unit="deg",
            )
            constellations = get_constellation(coords)
            pdfs["v:constellation"] = constellations

    # Display only the last alert
    if group_alerts and ("i:jd" in pdfs.columns) and ("i:objectId" in pdfs.columns):
        pdfs["i:jd"] = pdfs["i:jd"].astype(float)
        pdfs = pdfs.loc[pdfs.groupby("i:objectId")["i:jd"].idxmax()]

    # sort values by time
    if "i:jd" in pdfs.columns:
        pdfs = pdfs.sort_values("i:jd", ascending=False)

    return pdfs


def query_and_order_statistics(date="", columns="*", index_by="key:key", drop=True):
    """Query /statistics, and order the resulting dataframe

    Parameters
    ----------
    date: str, optional
        Date (default is '')
    columns: str
        Column names (default is '*')
    index_by: str, optional
        Column name on which to index on (default is key:key)
    drop: bool
        If True, drop original column used to index the dataframe.
        Default is False.

    Returns
    -------
    pdf: Pandas DataFrame
        DataFrame with statistics data, ordered from
        oldest (top) to most recent (bottom)
    """
    pdf = request_api(
        "/api/v1/statistics",
        json={
            "date": date,
            "columns": columns,
            "output-format": "json",
        },
    )

    pdf = pdf.sort_values(index_by)
    pdf = pdf.set_index(index_by, drop=drop)

    # Remove hbase specific fields
    if "key:time" in pdf.columns:
        pdf = pdf.drop(columns=["key:time"])

    return pdf


def isoify_time(t):
    try:
        tt = Time(t)
    except ValueError:
        ft = float(t)
        if ft // 2400000:
            tt = Time(ft, format="jd")
        else:
            tt = Time(ft, format="mjd")
    return tt.iso


def markdownify_objectid(objectid):
    """ """
    objectid_markdown = f"[{objectid}](/{objectid})"
    return objectid_markdown


def extract_row(key: str, clientresult) -> dict:
    """Extract one row from the client result, and return result as dict"""
    data = clientresult[key]
    return dict(data)


def readstamp(stamp: str, return_type="array", gzipped=True) -> np.array:
    """Read the stamp data inside an alert.

    Parameters
    ----------
    stamp: str
        String containing binary data for the stamp
    return_type: str
        Data block of HDU 0 (`array`) or original FITS uncompressed (`FITS`) as file-object.
        Default is `array`.

    Returns
    -------
    data: np.array
        2D array containing image data (`array`) or FITS file uncompressed as file-object (`FITS`)
    """
    if return_type == 'raw':
        return io.BytesIO(stamp)

    def extract_stamp(fitsdata):
        with fits.open(fitsdata, ignore_missing_simple=True) as hdul:
            if return_type == "array":
                data = hdul[0].data
            elif return_type == "FITS":
                data = io.BytesIO()
                hdul.writeto(data)
                data.seek(0)
        return data

    if not isinstance(stamp, io.BytesIO):
        stamp = io.BytesIO(stamp)

    if gzipped:
        with gzip.open(stamp, "rb") as f:
            return extract_stamp(io.BytesIO(f.read()))
    else:
        return extract_stamp(stamp)


def extract_cutouts(
    pdf: pd.DataFrame, client, col=None, return_type="array"
) -> pd.DataFrame:
    """Query and uncompress cutout data from the HBase table

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
    -------
    pdf: Pandas DataFrame
        Modified original DataFrame with cutout data uncompressed (2D array)
    """
    cols = [
        "b:cutoutScience_stampData",
        "b:cutoutTemplate_stampData",
        "b:cutoutDifference_stampData",
    ]

    for colname in cols:
        # Skip unneeded columns, if only one is requested
        if col is not None and col != colname:
            continue

        if colname not in pdf.columns:
            pdf[colname] = (
                "binary:"
                + pdf["i:objectId"]
                + "_"
                + pdf["i:jd"].astype("str")
                + colname[1:]
            )

        pdf[colname] = pdf[colname].apply(
            lambda x: readstamp(client.repository().get(x), return_type=return_type),
        )

    return pdf


def extract_properties(data: str, fieldnames: list):
    """ """
    pdfs = pd.DataFrame.from_dict(hbase_to_dict(data), orient="index")
    if fieldnames is not None:
        return pdfs[fieldnames]
    else:
        return pdfs


def convert_jd(jd, to="iso", format="jd"):
    """Convert Julian Date into ISO date (UTC)."""
    return Time(jd, format=format).to_value(to)


def convolve(image, smooth=3, kernel="gauss"):
    """Convolve 2D image. Hacked from aplpy"""
    if smooth is None and isinstance(kernel, str) and kernel in ["box", "gauss"]:
        return image

    if smooth is not None and not np.isscalar(smooth):
        raise ValueError(
            "smooth= should be an integer - for more complex "
            "kernels, pass an array containing the kernel "
            "to the kernel= option"
        )

    # The Astropy convolution doesn't treat +/-Inf values correctly yet, so we
    # convert to NaN here.
    image_fixed = np.array(image, dtype=float, copy=True)
    image_fixed[np.isinf(image)] = np.nan

    if isinstance(kernel, str):
        if kernel == "gauss":
            kernel = Gaussian2DKernel(smooth, x_size=smooth * 5, y_size=smooth * 5)
        elif kernel == "box":
            kernel = Box2DKernel(smooth, x_size=smooth * 5, y_size=smooth * 5)
        else:
            raise ValueError(f"Unknown kernel: {kernel}")

    return astropy_convolve(image, kernel, boundary="extend")


def _data_stretch(
    image,
    vmin=None,
    vmax=None,
    pmin=0.25,
    pmax=99.75,
    stretch="linear",
    vmid: float = 10,
    exponent=2,
):
    """Hacked from aplpy"""
    if vmin is None or vmax is None:
        interval = AsymmetricPercentileInterval(pmin, pmax, n_samples=10000)
        try:
            vmin_auto, vmax_auto = interval.get_limits(image)
        except IndexError:  # no valid values
            vmin_auto = vmax_auto = 0

    if vmin is None:
        # log.info("vmin = %10.3e (auto)" % vmin_auto)
        vmin = vmin_auto
    else:
        pass
        # log.info("vmin = %10.3e" % vmin)

    if vmax is None:
        # log.info("vmax = %10.3e (auto)" % vmax_auto)
        vmax = vmax_auto
    else:
        pass
        # log.info("vmax = %10.3e" % vmax)

    if stretch == "arcsinh":
        stretch = "asinh"

    normalizer = simple_norm(
        image,
        stretch=stretch,
        power=exponent,
        asinh_a=vmid,
        min_cut=vmin,
        max_cut=vmax,
        clip=False,
    )

    data = normalizer(image, clip=True).filled(0)
    data = np.nan_to_num(data)
    # data = np.clip(data * 255., 0., 255.)

    return data  # .astype(np.uint8)


def mag2fluxcal_snana(magpsf: float, sigmapsf: float):
    """Conversion from magnitude to Fluxcal from SNANA manual

    Parameters
    ----------
    magpsf: float
        PSF-fit magnitude from ZTF
    sigmapsf: float

    Returns
    -------
    fluxcal: float
        Flux cal as used by SNANA
    fluxcal_err: float
        Absolute error on fluxcal (the derivative has a minus sign)

    """
    if magpsf is None:
        return None, None
    fluxcal = 10 ** (-0.4 * magpsf) * 10 ** (11)
    fluxcal_err = 9.21034 * 10**10 * np.exp(-0.921034 * magpsf) * sigmapsf

    return fluxcal, fluxcal_err


def extract_rate_and_color(pdf: pd.DataFrame, tolerance: float = 0.3):
    """Extract magnitude rates in different filters, color, and color change rate.

    Notes
    -----
    It fills the following fields:
    - v:rate - magnitude change rate for this filter, defined as magnitude difference since previous measurement, divided by time difference
    - v:sigma(rate) - error of previous value, estimated from per-point errors
    - v:g-r - color, defined by subtracting the measurements in g and r filter closer than `tolerance` days. Is assigned to both g and r data points with the same value
    - v:sigma(g-r) - error of previous value, estimated from per-point errors
    - v:rate(g-r) - color change rate, computed using time differences of g band points
    - v:sigma(rate(g-r)) - error of previous value, estimated from per-point errors

    Parameters
    ----------
    pdf: Pandas DataFrame
        DataFrame returned by `format_hbase_output` (see api/api.py)
    tolerance: float
        Maximum delay between g and r data points to be considered for color computation, in days

    Returns
    -------
    pdf: Pandas DataFrame
        Modified original DataFrame with added columns. Original order is not preserved
    """
    pdfs = pdf.sort_values("i:jd")

    def fn(sub):
        """Extract everything relevant on the sub-group corresponding to single object.

        Notes
        -----
        Assumes it is already sorted by time.
        """
        sidx = []

        # Extract magnitude rates separately in different filters
        for fid in [1, 2]:
            idx = sub["i:fid"] == fid

            dmag = sub["i:magpsf"][idx].diff()
            dmagerr = np.hypot(sub["i:sigmapsf"][idx], sub["i:sigmapsf"][idx].shift())
            djd = sub["i:jd"][idx].diff()
            sub.loc[idx, "v:rate"] = dmag / djd
            sub.loc[idx, "v:sigma(rate)"] = dmagerr / djd

            sidx.append(idx)

        if len(sidx) == 2:
            # We have both filters, let's try to also get the color!
            colnames_gr = ["i:jd", "i:magpsf", "i:sigmapsf"]
            gr = pd.merge_asof(
                sub[sidx[0]][colnames_gr],
                sub[sidx[1]][colnames_gr],
                on="i:jd",
                suffixes=("_g", "_r"),
                direction="nearest",
                tolerance=tolerance,
            )
            # It is organized around g band points, r columns are null when unmatched
            gr = gr.loc[~gr.isna()["i:magpsf_r"]]  # Keep only matched rows

            gr["v:g-r"] = gr["i:magpsf_g"] - gr["i:magpsf_r"]
            gr["v:sigma(g-r)"] = np.hypot(gr["i:sigmapsf_g"], gr["i:sigmapsf_r"])

            djd = gr["i:jd"].diff()
            dgr = gr["v:g-r"].diff()
            dgrerr = np.hypot(gr["v:sigma(g-r)"], gr["v:sigma(g-r)"].shift())

            gr["v:rate(g-r)"] = dgr / djd
            gr["v:sigma(rate(g-r))"] = dgrerr / djd

            # Now we may assign these color values also to corresponding r band points
            sub = pd.merge_asof(
                sub,
                gr[
                    [
                        "i:jd",
                        "v:g-r",
                        "v:sigma(g-r)",
                        "v:rate(g-r)",
                        "v:sigma(rate(g-r))",
                    ]
                ],
                direction="nearest",
                tolerance=tolerance,
            )

        return sub

    # Apply the subroutine defined above to individual objects, and merge the table back
    pdfs = pdfs.groupby("i:objectId").apply(fn).droplevel(0)

    return pdfs


def extract_color(pdf: pd.DataFrame, tolerance: float = 0.3, colnames=None):
    """Extract g-r values for single object a pandas DataFrame

    Parameters
    ----------
    pdf: pandas DataFrame
        DataFrame containing alert parameters from an API call
    tolerance: float
        Maximal distance in days between data points to be associated
    colnames: list
        List of extra column names to keep in the output.

    Returns
    -------
    pdf_gr: pandas DataFrame
        DataFrame containing the time and magnitudes of matched points,
        along with g-r color and its error
    """
    if colnames is None:
        colnames = ["i:jd", "i:magpsf", "i:sigmapsf"]
    else:
        colnames = ["i:jd", "i:magpsf", "i:sigmapsf"] + colnames
        colnames = list(np.unique(colnames))

    pdf_g = pdf[pdf["i:fid"] == 1][colnames]
    pdf_r = pdf[pdf["i:fid"] == 2][colnames]

    # merge_asof expects sorted data
    pdf_g = pdf_g.sort_values("i:jd")
    pdf_r = pdf_r.sort_values("i:jd")

    # As merge_asof does not keep the second jd column - let's make it manually
    pdf_g["v:mjd"] = pdf_g["i:jd"] - 2400000.5
    pdf_r["v:mjd"] = pdf_r["i:jd"] - 2400000.5

    pdf_gr = pd.merge_asof(
        pdf_g,
        pdf_r,
        on="i:jd",
        suffixes=("_g", "_r"),
        direction="nearest",
        tolerance=0.3,
    )
    pdf_gr = pdf_gr[~pdf_gr.isna()["i:magpsf_r"]]  # Keep only matched rows

    pdf_gr["v:g-r"] = pdf_gr["i:magpsf_g"] - pdf_gr["i:magpsf_r"]
    pdf_gr["v:sigma_g-r"] = np.hypot(pdf_gr["i:sigmapsf_g"], pdf_gr["i:sigmapsf_r"])
    pdf_gr["v:delta_jd"] = pdf_gr["v:mjd_g"] - pdf_gr["v:mjd_r"]

    return pdf_gr


def query_mpc(number, kind="asteroid"):
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
    """Compute the indices of superpixels that contain a subpixel.

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
    """Wrapper for malformed query from URL"""
    return "", "", None


def extract_parameter_value_from_url(param_dic, key, default):
    """ """
    if key in param_dic:
        val = param_dic[key]
    else:
        val = default
    return val


def is_float(s: str) -> bool:
    """Check if s can be transformed as a float"""
    try:
        float(s)
        return True
    except ValueError:
        return False


def extract_bayestar_query_url(search: str):
    """Try to infer the query from an URL (GW search)

    Parameters
    ----------
    search: str
        String returned by `dcc.Location.search` property.
        Typically starts with ?

    Returns
    -------
    credible_level: float
        The credible level (0-1)
    event_name: str
        Event name (O3 or O4)
    """
    # remove trailing ?
    search = search[1:]

    # split parameters
    parameters = search.split("&")

    # Make a dictionary with the parameter keys and values
    param_dic = {s.split("=")[0]: s.split("=")[1] for s in parameters}

    credible_level = extract_parameter_value_from_url(param_dic, "credible_level", "")
    event_name = extract_parameter_value_from_url(param_dic, "event_name", "")
    if is_float(credible_level):
        credible_level = float(credible_level)

    return credible_level, event_name


def sine_fit(x, a, b):
    """Sinusoidal function a*sin( 2*(x-b) )

    Parameters
    ----------
    x: float
        in degrees
    a: float
        Amplitude
    b: float
        Phase offset

    """
    return a * np.sin(2 * np.radians(x - b))


def pil_to_b64(im, enc_format="png", **kwargs):
    """Converts a PIL Image into base64 string for HTML displaying

    Parameters
    ----------
    im: PIL Image object
        PIL Image object
    enc_format: str
        The image format for displaying.

    Returns
    -------
    base64 encoding
    """
    buff = io.BytesIO()
    im.save(buff, format=enc_format, **kwargs)
    encoded = base64.b64encode(buff.getvalue()).decode("utf-8")

    return encoded


def generate_qr(data):
    """Generate a QR code from the data

    To check the generated QR code, simply use:
    >>> img = generate_qr("https://fink-broker.org")
    >>> img.get_image().show()

    Parameters
    ----------
    data: str
        Typically an URL

    Returns
    -------
    PIL image
    """
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(data)

    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        eye_drawer=RoundedModuleDrawer(),
        # color_mask=RadialGradiantColorMask(edge_color=(245, 98, 46))
    )

    return img


def retrieve_oid_from_metaname(name):
    """Search for the corresponding ZTF objectId given a metaname"""
    r = request_api(
        "/api/v1/metadata",
        json={
            "internal_name_encoded": name,
        },
        output="json",
    )

    if r != []:
        return r[0]["key:key"]
    return None


def get_first_finite_value(data, pos=0):
    """Returns first finite value from the array at or after given position.

    Parameters
    ----------
    data: np.array
        Data array
    pos: int
        Position in the array to start search

    Returns
    -------
    Value from the array, or np.nan if no finite values found
    """
    data = data[pos:]

    if len(data):
        data = data[np.isfinite(data)]

    if len(data):
        return data[0]
    else:
        return np.nan


def get_first_value(pdf, colname, default=None):
    """Get first value from given column of a DataFrame, or default value if not exists."""
    if colname in pdf.columns:
        return pdf.loc[0, colname]
    else:
        return default


def request_api(endpoint, json=None, output="pandas", method="POST", **kwargs):
    """Output is one of 'pandas' (default), 'raw' or 'json'"""
    if LOCALAPI:
        # Use local API
        urls = server.url_map.bind("")
        func_name = urls.match(endpoint, method)
        if len(func_name) == 2 and func_name[0].startswith("api."):
            func = getattr(apps.api.api, func_name[0].split(".")[1])

            if method == "GET":
                # No args?..
                res = func()
            else:
                res = func(json)
            if isinstance(res, Response):
                if res.direct_passthrough:
                    res.make_sequence()
                result = res.get_data()
            else:
                result = res

            if output == "json":
                return json_loads(result)
            elif output == "raw":
                return result
            else:
                return pd.read_json(result, **kwargs)
        else:
            return None
    else:
        # Use remote API
        if method == "POST":
            r = requests.post(
                f"{APIURL}{endpoint}",
                json=json,
            )
        elif method == "GET":
            # No args?..
            r = requests.get(
                f"{APIURL}{endpoint}",
            )

        if output == "json":
            return r.json()
        elif output == "raw":
            return io.BytesIO(r.content)
        else:
            return pd.read_json(io.BytesIO(r.content), **kwargs)


def loading(item):
    return html.Div(
        [
            item,
            dmc.LoadingOverlay(
                loaderProps={"variant": "dots", "color": "orange", "size": "xl"},
                overlayProps={"radius": "sm", "blur": 2},
                zIndex=100000,
            ),
        ]
    )


def help_popover(text, id, trigger=None, className=None):
    """Make clickable help icon with popover at the bottom right corner of current element"""
    if trigger is None:
        trigger = html.I(
            className="fa fa-question-circle fa-1x",
            id=id,
        )
        if className is None:
            className = "d-flex align-items-end justify-content-end"

    return html.Div(
        [
            trigger,
            dbc.Popover(
                dbc.PopoverBody(
                    text,
                    style={
                        "overflow-y": "auto",
                        "white-space": "pre-wrap",
                        "max-height": "80vh",
                    },
                ),
                target=id,
                trigger="legacy",
                placement="auto",
                style={"width": "80vw", "max-width": "800px"},
                className="shadow-lg",
            ),
        ],
        className=className,
    )


def template_button_for_external_conesearch(
    className="btn btn-default zoom btn-circle btn-lg btn-image",
    style=None,
    color="dark",
    outline=True,
    title="",
    target="_blank",
    href="",
):
    """Template button for external conesearch

    Parameters
    ----------
    className: str, optional
        Styling options. Default is `btn btn-default zoom btn-circle btn-lg btn-image`
    style: dict, optional
        Extra styling options. Default is {}
    color: str, optional
        Color of the button (default is `dark`)
    outline: bool, optional
    title: str, optional
        Title of the object. Default is ''
    target: str, optional
        Open in the same window or in a new tab (default).
    href: str, optional
        targeted URL
    """
    if style is None:
        style = {}

    button = dbc.Button(
        className=className,
        style=style,
        color=color,
        outline=outline,
        title=title,
        target=target,
        href=href,
    )

    return button


def create_button_for_external_conesearch(
    kind: str, ra0: float, dec0: float, radius=None, width=4
):
    """Create a button that triggers an external conesearch

    The button is wrapped within a dbc.Col object.

    Parameters
    ----------
    kind: str
        External resource name. Currently available:
        - asas-sn, snad, vsx, tns, simbad, datacentral, ned, sdss
    ra0: float
        RA for the conesearch center
    dec0: float
        DEC for the conesearch center
    radius: int or float, optional
        Radius for the conesearch. Each external resource has its
        own default value (default), as well as its own units.
    width: int, optional
        dbc.Col width parameter. Default is 4.
    """
    if kind == "asas-sn-variable":
        if radius is None:
            radius = 0.5
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={
                    "background-image": "url(/assets/buttons/assassin_logo.png)",
                    "background-color": "black",
                },
                title="ASAS-SN",
                href=f"https://asas-sn.osu.edu/variables?ra={ra0}&dec={dec0}&radius={radius}&vmag_min=&vmag_max=&amplitude_min=&amplitude_max=&period_min=&period_max=&lksl_min=&lksl_max=&class_prob_min=&class_prob_max=&parallax_over_err_min=&parallax_over_err_max=&name=&references[]=I&references[]=II&references[]=III&references[]=IV&references[]=V&references[]=VI&sort_by=raj2000&sort_order=asc&show_non_periodic=true&show_without_class=true&asassn_discov_only=false&",
            ),
            width=width,
        )
    elif kind == "asas-sn":
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={
                    "background-image": "url(/assets/buttons/assassin_logo.png)",
                    "background-color": "black",
                },
                title="ASAS-SN",
                href=f"https://asas-sn.osu.edu/?ra={ra0}&dec={dec0}",
            ),
            width=width,
        )
    elif kind == "snad":
        if radius is None:
            radius = 5
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={"background-image": "url(/assets/buttons/snad.svg)"},
                title="SNAD",
                href=f"https://ztf.snad.space/search/{ra0} {dec0}/{radius}",
            ),
            width=width,
        )
    elif kind == "vsx":
        if radius is None:
            radius = 0.1
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={"background-image": "url(/assets/buttons/vsx.png)"},
                title="AAVSO VSX",
                href=f"https://www.aavso.org/vsx/index.php?view=results.get&coords={ra0}+{dec0}&format=d&size={radius}",
            ),
            width=width,
        )
    elif kind == "tns":
        if radius is None:
            radius = 5
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={
                    "background-image": "url(/assets/buttons/tns_logo.png)",
                    "background-size": "auto 100%",
                    "background-position-x": "left",
                },
                title="TNS",
                href=f"https://www.wis-tns.org/search?ra={ra0}&decl={dec0}&radius={radius}&coords_unit=arcsec",
            ),
            width=width,
        )
    elif kind == "simbad":
        if radius is None:
            radius = 0.08
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={"background-image": "url(/assets/buttons/simbad.png)"},
                title="SIMBAD",
                href=f"http://simbad.u-strasbg.fr/simbad/sim-coo?Coord={ra0}%20{dec0}&Radius={radius}",
            ),
            width=width,
        )
    elif kind == "datacentral":
        if radius is None:
            radius = 2.0
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={"background-image": "url(/assets/buttons/dclogo_small.png)"},
                title="DataCentral Data Aggregation Service",
                href=f"https://das.datacentral.org.au/open?RA={ra0}&DEC={dec0}&FOV={0.5}&ERR={radius}",
            ),
            width=width,
        )
    elif kind == "ned":
        if radius is None:
            radius = 1.0
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={
                    "background-image": "url(/assets/buttons/NEDVectorLogo_WebBanner_100pxTall_2NoStars.png)",
                    "background-color": "black",
                },
                title="NED",
                href=f"http://ned.ipac.caltech.edu/cgi-bin/objsearch?search_type=Near+Position+Search&in_csys=Equatorial&in_equinox=J2000.0&ra={ra0}&dec={dec0}&radius={radius}&obj_sort=Distance+to+search+center&img_stamp=Yes",
            ),
            width=width,
        )
    elif kind == "sdss":
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={"background-image": "url(/assets/buttons/sdssIVlogo.png)"},
                title="SDSS",
                href=f"http://skyserver.sdss.org/dr13/en/tools/chart/navi.aspx?ra={ra0}&dec={dec0}",
            ),
            width=width,
        )

    return button

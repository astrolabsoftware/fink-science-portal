# Copyright 2022-2024 AstroLab Software
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
import datetime
import json
import gzip
import io

import astropy.units as u
import healpy as hp
import numpy as np
import pandas as pd
import requests
import yaml

from astropy.coordinates import SkyCoord
from astropy.io import fits, votable
from astropy.table import Table
from astropy.time import Time, TimeDelta
from flask import Response, send_file, jsonify
from matplotlib import cm
from PIL import Image

from app import APIURL
from apps.client import connect_to_hbase_table
from apps.euclid.utils import (
    add_columns,
    check_header,
    compute_rowkey,
    load_euclid_header,
)
from apps.plotting import legacy_normalizer, sigmoid_normalizer
from apps.utils import (
    convert_datatype,
    convolve,
    format_hbase_output,
    hbase_to_dict,
    hbase_type_converter,
    isoify_time,
)
from apps.sso.utils import resolve_sso_name, resolve_sso_name_to_ssnamenr
from fink_utils.sso.utils import get_miriade_data
from fink_utils.sso.spins import func_hg1g2_with_spin, estimate_sso_params


def return_object_pdf(payload: dict) -> pd.DataFrame:
    """Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/objects

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/objects

    Return
    ----------
    out: pandas dataframe
    """
    if "columns" in payload:
        cols = payload["columns"].replace(" ", "")
    else:
        cols = "*"

    if "," in payload["objectId"]:
        # multi-objects search
        splitids = payload["objectId"].split(",")
        objectids = [f"key:key:{i.strip()}" for i in splitids]
    else:
        # single object search
        objectids = ["key:key:{}".format(payload["objectId"])]

    if "withcutouts" in payload and str(payload["withcutouts"]) == "True":
        withcutouts = True
    else:
        withcutouts = False

    if "withupperlim" in payload and str(payload["withupperlim"]) == "True":
        withupperlim = True
    else:
        withupperlim = False

    if cols == "*":
        truncated = False
    else:
        truncated = True

    client = connect_to_hbase_table("ztf")

    # Get data from the main table
    results = {}
    for to_evaluate in objectids:
        result = client.scan(
            "",
            to_evaluate,
            cols,
            0,
            True,
            True,
        )
        results.update(result)

    schema_client = client.schema()

    pdf = format_hbase_output(
        results,
        schema_client,
        group_alerts=False,
        truncated=truncated,
    )

    if withcutouts:
        # Default `None` returns all 3 cutouts
        cutout_kind = payload.get("cutout-kind", "All")

        def download_cutout(objectId, candid, kind):
            r = requests.post(
                "{}/api/v1/cutouts".format(APIURL),
                json={
                    "objectId": objectId,
                    "candid": candid,
                    "kind": kind,
                    "output-format": "array",
                },
            )
            if r.status_code == 200:
                data = json.loads(r.content)
            else:
                # TODO: different return based on `kind`?
                return []

            if kind != "All":
                return data["b:cutout{}_stampData".format(kind)]
            else:
                return [
                    data["b:cutout{}_stampData".format(k)]
                    for k in ["Science", "Template", "Difference"]
                ]

        if cutout_kind == "All":
            cols = [
                "b:cutoutScience_stampData",
                "b:cutoutTemplate_stampData",
                "b:cutoutDifference_stampData",
            ]
            pdf[cols] = pdf[["i:objectId", "i:candid"]].apply(
                lambda x: pd.Series(download_cutout(x.iloc[0], x.iloc[1], cutout_kind)),
                axis=1,
            )
        else:
            colname = "b:cutout{}_stampData".format(cutout_kind)
            pdf[colname] = pdf[["i:objectId", "i:candid"]].apply(
                lambda x: pd.Series(
                    [download_cutout(x.iloc[0], x.iloc[1], cutout_kind)]
                ),
                axis=1,
            )

    if withupperlim:
        clientU = connect_to_hbase_table("ztf.upper")
        # upper limits
        resultsU = {}
        for to_evaluate in objectids:
            resultU = clientU.scan(
                "",
                to_evaluate,
                "*",
                0,
                False,
                False,
            )
            resultsU.update(resultU)

        # bad quality
        clientUV = connect_to_hbase_table("ztf.uppervalid")
        resultsUP = {}
        for to_evaluate in objectids:
            resultUP = clientUV.scan(
                "",
                to_evaluate,
                "*",
                0,
                False,
                False,
            )
            resultsUP.update(resultUP)

        pdfU = pd.DataFrame.from_dict(hbase_to_dict(resultsU), orient="index")
        pdfUP = pd.DataFrame.from_dict(hbase_to_dict(resultsUP), orient="index")

        pdf["d:tag"] = "valid"
        pdfU["d:tag"] = "upperlim"
        pdfUP["d:tag"] = "badquality"

        if "i:jd" in pdfUP.columns:
            # workaround -- see https://github.com/astrolabsoftware/fink-science-portal/issues/216
            mask = np.array(
                [
                    False if float(i) in pdf["i:jd"].to_numpy() else True
                    for i in pdfUP["i:jd"].to_numpy()
                ]
            )
            pdfUP = pdfUP[mask]

        # Hacky way to avoid converting concatenated column to float
        pdfU["i:candid"] = -1  # None
        pdfUP["i:candid"] = -1  # None

        pdf_ = pd.concat((pdf, pdfU, pdfUP), axis=0)

        # replace
        if "i:jd" in pdf_.columns:
            pdf_["i:jd"] = pdf_["i:jd"].astype(float)
            pdf = pdf_.sort_values("i:jd", ascending=False)
        else:
            pdf = pdf_

        clientU.close()
        clientUV.close()

    client.close()

    return pdf


def return_explorer_pdf(payload: dict, user_group: int) -> pd.DataFrame:
    """Extract data returned by HBase and format it in a Pandas dataframe

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

    if "startdate" in payload:
        jd_start = Time(isoify_time(payload["startdate"])).jd
    else:
        jd_start = Time("2019-11-01 00:00:00").jd

    if "stopdate" in payload:
        jd_stop = Time(isoify_time(payload["stopdate"])).jd
    elif "window" in payload and "startdate" in payload:
        window = float(payload["window"])
        jd_stop = jd_start + window
    else:
        jd_stop = Time.now().jd

    n = int(payload.get("n", 1000))

    if user_group == 0:
        # objectId search
        client = connect_to_hbase_table("ztf")
        results = {}
        for oid in payload["objectId"].split(","):
            # objectId search
            to_evaluate = f"key:key:{oid.strip()}"
            result = client.scan(
                "",
                to_evaluate,
                "*",
                0,
                True,
                True,
            )
            results.update(result)

        schema_client = client.schema()
    elif user_group == 1:
        # Conesearch with optional date range
        client = connect_to_hbase_table("ztf.pixel128")
        client.setLimit(n)

        # Interpret user input
        ra, dec = payload["ra"], payload["dec"]
        radius = payload["radius"]

        if float(radius) > 18000.0:
            rep = {
                "status": "error",
                "text": "`radius` cannot be bigger than 18,000 arcseconds (5 degrees).\n",
            }
            return Response(str(rep), 400)

        try:
            if "h" in str(ra):
                coord = SkyCoord(ra, dec, frame="icrs")
            elif ":" in str(ra) or " " in str(ra):
                coord = SkyCoord(ra, dec, frame="icrs", unit=(u.hourangle, u.deg))
            else:
                coord = SkyCoord(ra, dec, frame="icrs", unit="deg")
        except ValueError as e:
            rep = {
                "status": "error",
                "text": e,
            }
            return Response(str(rep), 400)

        ra = coord.ra.deg
        dec = coord.dec.deg
        radius_deg = float(radius) / 3600.0

        # angle to vec conversion
        vec = hp.ang2vec(np.pi / 2.0 - np.pi / 180.0 * dec, np.pi / 180.0 * ra)

        # Send request
        nside = 128

        pixs = hp.query_disc(
            nside,
            vec,
            np.pi / 180 * radius_deg,
            inclusive=True,
        )

        # Filter by time
        if "startdate" in payload:
            client.setRangeScan(True)
            results = {}
            for pix in pixs:
                to_search = f"key:key:{pix}_{jd_start},key:key:{pix}_{jd_stop}"
                result = client.scan(
                    "",
                    to_search,
                    "*",
                    0,
                    True,
                    True,
                )
                results.update(result)
            client.setRangeScan(False)
        else:
            results = {}
            for pix in pixs:
                to_search = f"key:key:{pix}_"
                result = client.scan(
                    "",
                    to_search,
                    "*",
                    0,
                    True,
                    True,
                )
                results.update(result)

        schema_client = client.schema()
        truncated = True
    else:
        # Plain date search
        client = connect_to_hbase_table("ztf.jd")

        # Limit the time window to 3 hours days
        if jd_stop - jd_start > 3 / 24:
            jd_stop = jd_start + 3 / 24

        # Send the request. RangeScan.
        client.setRangeScan(True)
        client.setLimit(n)
        to_evaluate = f"key:key:{jd_start},key:key:{jd_stop}"
        results = client.scan(
            "",
            to_evaluate,
            "*",
            0,
            True,
            True,
        )
        schema_client = client.schema()

    client.close()

    pdfs = format_hbase_output(
        results,
        schema_client,
        truncated=truncated,
        group_alerts=True,
        extract_color=False,
    )

    # For conesearch, sort by distance
    if (user_group == 1) and (len(pdfs) > 0):
        sep = coord.separation(
            SkyCoord(
                pdfs["i:ra"],
                pdfs["i:dec"],
                unit="deg",
            ),
        ).deg

        pdfs["v:separation_degree"] = sep
        pdfs = pdfs.sort_values("v:separation_degree", ascending=True)

        mask = pdfs["v:separation_degree"] > radius_deg
        pdfs = pdfs[~mask]

    return pdfs


def return_conesearch_pdf(payload: dict) -> pd.DataFrame:
    """Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/conesearch

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/conesearch

    Return
    ----------
    out: pandas dataframe
    """
    if "startdate" in payload:
        jd_start = Time(isoify_time(payload["startdate"])).jd
    else:
        jd_start = Time("2019-11-01 00:00:00").jd

    if "stopdate" in payload:
        jd_stop = Time(isoify_time(payload["stopdate"])).jd
    elif "window" in payload and "startdate" in payload:
        window = float(payload["window"])
        jd_stop = jd_start + window
    else:
        jd_stop = Time.now().jd

    n = int(payload.get("n", 1000))

    # Conesearch with optional date range
    client = connect_to_hbase_table("ztf.pixel128")
    client.setLimit(n)

    # Interpret user input
    ra, dec = payload["ra"], payload["dec"]
    radius = payload["radius"]

    if float(radius) > 18000.0:
        rep = {
            "status": "error",
            "text": "`radius` cannot be bigger than 18,000 arcseconds (5 degrees).\n",
        }
        return Response(str(rep), 400)

    try:
        if "h" in str(ra):
            coord = SkyCoord(ra, dec, frame="icrs")
        elif ":" in str(ra) or " " in str(ra):
            coord = SkyCoord(ra, dec, frame="icrs", unit=(u.hourangle, u.deg))
        else:
            coord = SkyCoord(ra, dec, frame="icrs", unit="deg")
    except ValueError as e:
        rep = {
            "status": "error",
            "text": e,
        }
        return Response(str(rep), 400)

    ra = coord.ra.deg
    dec = coord.dec.deg
    radius_deg = float(radius) / 3600.0

    # angle to vec conversion
    vec = hp.ang2vec(np.pi / 2.0 - np.pi / 180.0 * dec, np.pi / 180.0 * ra)

    # Send request
    nside = 128

    pixs = hp.query_disc(
        nside,
        vec,
        np.pi / 180 * radius_deg,
        inclusive=True,
    )

    # Filter by time
    if "startdate" in payload:
        client.setRangeScan(True)
        results = {}
        for pix in pixs:
            to_search = f"key:key:{pix}_{jd_start},key:key:{pix}_{jd_stop}"
            result = client.scan(
                "",
                to_search,
                "*",
                0,
                True,
                True,
            )
            results.update(result)
        client.setRangeScan(False)
    else:
        results = {}
        for pix in pixs:
            to_search = f"key:key:{pix}_"
            result = client.scan(
                "",
                to_search,
                "*",
                0,
                True,
                True,
            )
            results.update(result)

    schema_client = client.schema()

    client.close()

    pdfs = format_hbase_output(
        results,
        schema_client,
        truncated=True,
        group_alerts=True,
        extract_color=False,
    )

    # For conesearch, sort by distance
    if len(pdfs) > 0:
        sep = coord.separation(
            SkyCoord(
                pdfs["i:ra"],
                pdfs["i:dec"],
                unit="deg",
            ),
        ).deg

        pdfs["v:separation_degree"] = sep
        pdfs = pdfs.sort_values("v:separation_degree", ascending=True)

        mask = pdfs["v:separation_degree"] > radius_deg
        pdfs = pdfs[~mask]

    return pdfs


def return_latests_pdf(payload: dict, return_raw: bool = False) -> pd.DataFrame:
    """Extract data returned by HBase and format it in a Pandas dataframe

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
    if "n" not in payload:
        nalerts = 10
    else:
        nalerts = int(payload["n"])

    if "startdate" not in payload:
        # start of the Fink operations
        jd_start = Time("2019-11-01 00:00:00").jd
    else:
        jd_start = Time(payload["startdate"]).jd

    if "stopdate" not in payload:
        jd_stop = Time.now().jd
    else:
        jd_stop = Time(payload["stopdate"]).jd

    if "color" not in payload:
        color = False
    else:
        color = True

    if "columns" in payload:
        cols = payload["columns"].replace(" ", "")
    else:
        cols = "*"

    if cols == "*":
        truncated = False
    else:
        truncated = True

    # Search for latest alerts for a specific class
    tns_classes = pd.read_csv("assets/tns_types.csv", header=None)[0].to_numpy()
    is_tns = payload["class"].startswith("(TNS)") and (
        payload["class"].split("(TNS) ")[1] in tns_classes
    )
    if is_tns:
        client = connect_to_hbase_table("ztf.tns")
        classname = payload["class"].split("(TNS) ")[1]
        client.setLimit(nalerts)
        client.setRangeScan(True)
        client.setReversed(True)

        results = client.scan(
            "",
            f"key:key:{classname}_{jd_start},key:key:{classname}_{jd_stop}",
            cols,
            0,
            True,
            True,
        )
        schema_client = client.schema()
        group_alerts = True
    elif payload["class"].startswith("(SIMBAD)") or payload["class"] != "allclasses":
        if payload["class"].startswith("(SIMBAD)"):
            classname = payload["class"].split("(SIMBAD) ")[1]
        else:
            classname = payload["class"]

        client = connect_to_hbase_table("ztf.class")

        client.setLimit(nalerts)
        client.setRangeScan(True)
        client.setReversed(True)

        results = client.scan(
            "",
            f"key:key:{classname}_{jd_start},key:key:{classname}_{jd_stop}",
            cols,
            0,
            False,
            False,
        )
        schema_client = client.schema()
        group_alerts = False
    elif payload["class"] == "allclasses":
        client = connect_to_hbase_table("ztf.jd")
        client.setLimit(nalerts)
        client.setRangeScan(True)
        client.setReversed(True)

        to_evaluate = f"key:key:{jd_start},key:key:{jd_stop}"
        results = client.scan(
            "",
            to_evaluate,
            cols,
            0,
            True,
            True,
        )
        schema_client = client.schema()
        group_alerts = False

    client.close()

    if return_raw:
        return results

    # We want to return alerts
    # color computation is disabled
    pdfs = format_hbase_output(
        results,
        schema_client,
        group_alerts=group_alerts,
        extract_color=color,
        truncated=truncated,
        with_constellation=True,
    )

    return pdfs


def return_sso_pdf(payload: dict) -> pd.DataFrame:
    """Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/sso

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/sso

    Return
    ----------
    out: pandas dataframe
    """
    if "columns" in payload:
        cols = payload["columns"].replace(" ", "")
    else:
        cols = "*"

    if cols == "*":
        truncated = False
    else:
        truncated = True

    with_ephem, with_residuals, with_cutouts = False, False, False
    if "withResiduals" in payload and (
        payload["withResiduals"] == "True" or payload["withResiduals"] is True
    ):
        with_residuals = True
        with_ephem = True
    if "withEphem" in payload and (
        payload["withEphem"] == "True" or payload["withEphem"] is True
    ):
        with_ephem = True
    if "withcutouts" in payload and (
        payload["withcutouts"] == "True" or payload["withcutouts"] is True
    ):
        with_cutouts = True

    n_or_d = str(payload["n_or_d"])

    if "," in n_or_d:
        ids = n_or_d.replace(" ", "").split(",")
        multiple_objects = True
    else:
        ids = [n_or_d.replace(" ", "")]
        multiple_objects = False

    # We cannot do multi-object and phase curve computation
    if multiple_objects and with_residuals:
        rep = {
            "status": "error",
            "text": "You cannot request residuals for a list object names.\n",
        }
        return Response(str(rep), 400)

    # Get all ssnamenrs
    ssnamenrs = []
    ssnamenr_to_sso_name = {}
    ssnamenr_to_sso_number = {}
    for id_ in ids:
        if id_.startswith("C/"):
            start = id_[0:6]
            stop = id_[6:]
            r = requests.get(
                "https://api.ssodnet.imcce.fr/quaero/1/sso?q={} {}&type=Comet".format(
                    start, stop
                )
            )
            if r.status_code == 200 and r.json() != []:
                sso_name = r.json()["data"][0]["name"]
            else:
                sso_name = id_
            sso_number = None
        elif id_.endswith("P"):
            sso_name = id_
            sso_number = None
        else:
            # resolve the name of asteroids using rocks
            sso_name, sso_number = resolve_sso_name(id_)

        if not isinstance(sso_number, int) and not isinstance(sso_name, str):
            rep = {
                "status": "error",
                "text": "{} is not a valid name or number according to quaero.\n".format(
                    n_or_d
                ),
            }
            return Response(str(rep), 400)

        # search all ssnamenr corresponding quaero -> ssnamenr
        if isinstance(sso_name, str):
            new_ssnamenrs = resolve_sso_name_to_ssnamenr(sso_name)
            ssnamenrs = np.concatenate((ssnamenrs, new_ssnamenrs))
        else:
            new_ssnamenrs = resolve_sso_name_to_ssnamenr(sso_number)
            ssnamenrs = np.concatenate((ssnamenrs, new_ssnamenrs))

        for ssnamenr_ in new_ssnamenrs:
            ssnamenr_to_sso_name[ssnamenr_] = sso_name
            ssnamenr_to_sso_number[ssnamenr_] = sso_number

    # Get data from the main table
    client = connect_to_hbase_table("ztf.ssnamenr")
    results = {}
    for to_evaluate in ssnamenrs:
        result = client.scan(
            "",
            f"key:key:{to_evaluate}_",
            cols,
            0,
            True,
            True,
        )
        results.update(result)

    schema_client = client.schema()

    # reset the limit in case it has been changed above
    client.close()

    pdf = format_hbase_output(
        results,
        schema_client,
        group_alerts=False,
        truncated=truncated,
        extract_color=False,
    )

    # Propagate name and number
    pdf["sso_name"] = pdf["i:ssnamenr"].apply(lambda x: ssnamenr_to_sso_name[x])
    pdf["sso_number"] = pdf["i:ssnamenr"].apply(lambda x: ssnamenr_to_sso_number[x])

    if with_cutouts:
        # Extract cutouts
        cutout_kind = payload.get("cutout-kind", "Science")
        if cutout_kind not in ["Science", "Template", "Difference"]:
            rep = {
                "status": "error",
                "text": "`cutout-kind` must be `Science`, `Difference`, or `Template`.\n",
            }
            return Response(str(rep), 400)

        colname = "b:cutout{}_stampData".format(cutout_kind)

        # get all cutouts
        cutouts = []
        for result in results.values():
            r = requests.post(
                f"{APIURL}/api/v1/cutouts",
                json={
                    "objectId": result["i:objectId"],
                    "candid": result["i:candid"],
                    "kind": cutout_kind,
                    "output-format": "array",
                },
            )
            if r.status_code == 200:
                # the result should be unique (based on candid)
                cutouts.append(json.loads(r.content)[colname])
            else:
                rep = {
                    "status": "error",
                    "text": r.content,
                }
                return Response(str(rep), r.status_code)

        pdf[colname] = cutouts

    if with_ephem:
        # We should probably add a timeout
        # and try/except in case of miriade shutdown
        pdf = get_miriade_data(pdf, sso_colname="sso_name")
        if "i:magpsf_red" not in pdf.columns:
            rep = {
                "status": "error",
                "text": "We could not obtain the ephemerides information. Check Miriade availabilities.",
            }
            return Response(str(rep), 400)

    if with_residuals:
        # get phase curve parameters using
        # the sHG1G2 model

        # Phase angle, in radians
        phase = np.deg2rad(pdf["Phase"].values)

        # Required for sHG1G2
        ra = np.deg2rad(pdf["i:ra"].values)
        dec = np.deg2rad(pdf["i:dec"].values)

        outdic = estimate_sso_params(
            magpsf_red=pdf["i:magpsf_red"].to_numpy(),
            sigmapsf=pdf["i:sigmapsf"].to_numpy(),
            phase=phase,
            filters=pdf["i:fid"].to_numpy(),
            ra=ra,
            dec=dec,
            p0=[15.0, 0.15, 0.15, 0.8, np.pi, 0.0],
            bounds=(
                [0, 0, 0, 3e-1, 0, -np.pi / 2],
                [30, 1, 1, 1, 2 * np.pi, np.pi / 2],
            ),
            model="SHG1G2",
            normalise_to_V=False,
        )

        # check if fit converged else return NaN
        if outdic["fit"] != 0:
            pdf["residuals_shg1g2"] = np.nan
        else:
            # per filter construction of the residual
            pdf["residuals_shg1g2"] = 0.0
            for filt in np.unique(pdf["i:fid"]):
                cond = pdf["i:fid"] == filt
                model = func_hg1g2_with_spin(
                    [phase[cond], ra[cond], dec[cond]],
                    outdic["H_{}".format(filt)],
                    outdic["G1_{}".format(filt)],
                    outdic["G2_{}".format(filt)],
                    outdic["R"],
                    np.deg2rad(outdic["alpha0"]),
                    np.deg2rad(outdic["delta0"]),
                )
                pdf.loc[cond, "residuals_shg1g2"] = (
                    pdf.loc[cond, "i:magpsf_red"] - model
                )

    return pdf


def return_ssocand_pdf(payload: dict) -> pd.DataFrame:
    """Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/ssocand

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/ssocand

    Return
    ----------
    out: pandas dataframe
    """
    if "ssoCandId" in payload:
        trajectory_id = str(payload["ssoCandId"])
    else:
        trajectory_id = None

    if "maxnumber" in payload:
        maxnumber = payload["maxnumber"]
    else:
        maxnumber = 10000

    payload_name = payload["kind"]

    if payload_name == "orbParams":
        gen_client = connect_to_hbase_table("ztf.orb_cand")

        if trajectory_id is not None:
            to_evaluate = f"key:key:cand_{trajectory_id}"
        else:
            to_evaluate = "key:key:cand_"
    elif payload_name == "lightcurves":
        gen_client = connect_to_hbase_table("ztf.sso_cand")

        if "start_date" in payload:
            start_date = Time(payload["start_date"], format="iso").jd
        else:
            start_date = Time("2019-11-01", format="iso").jd

        if "stop_date" in payload:
            stop_date = Time(payload["stop_date"], format="iso").jd
        else:
            stop_date = Time.now().jd

        gen_client.setRangeScan(True)
        gen_client.setLimit(maxnumber)

        if trajectory_id is not None:
            gen_client.setEvaluation(f"ssoCandId.equals('{trajectory_id}')")

        to_evaluate = f"key:key:{start_date}_,key:key:{stop_date}_"

    results = gen_client.scan(
        "",
        to_evaluate,
        "*",
        0,
        False,
        False,
    )

    schema_client = gen_client.schema()
    gen_client.close()

    if results.isEmpty():
        return pd.DataFrame({})

    # Construct the dataframe
    pdf = pd.DataFrame.from_dict(hbase_to_dict(results), orient="index")

    if "key:time" in pdf.columns:
        pdf = pdf.drop(columns=["key:time"])

    # Type conversion
    for col in pdf.columns:
        pdf[col] = convert_datatype(
            pdf[col],
            hbase_type_converter[schema_client.type(col)],
        )

    return pdf


def return_tracklet_pdf(payload: dict) -> pd.DataFrame:
    """Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/tracklet

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/tracklet

    Return
    ----------
    out: pandas dataframe
    """
    if "columns" in payload:
        cols = payload["columns"].replace(" ", "")
    else:
        cols = "*"

    if cols == "*":
        truncated = False
    else:
        truncated = True

    if "id" in payload:
        payload_name = payload["id"]
    elif "date" in payload:
        designation = payload["date"]
        payload_name = "TRCK_" + designation.replace("-", "").replace(":", "").replace(
            " ", "_"
        )
    else:
        rep = {
            "status": "error",
            "text": "You need to specify a date at the format YYYY-MM-DD hh:mm:ss\n",
        }
        return Response(str(rep), 400)

    # Note the trailing _
    to_evaluate = f"key:key:{payload_name}"

    client = connect_to_hbase_table("ztf.tracklet")
    results = client.scan(
        "",
        to_evaluate,
        cols,
        0,
        True,
        True,
    )

    schema_client = client.schema()

    # reset the limit in case it has been changed above
    client.close()

    pdf = format_hbase_output(
        results,
        schema_client,
        group_alerts=False,
        truncated=truncated,
        extract_color=False,
    )

    return pdf


def format_and_send_cutout(payload: dict) -> pd.DataFrame:
    """Extract data returned by HBase and jsonify it

    Data is from /api/v1/cutouts

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/cutouts

    Return
    ----------
    out: pandas dataframe
    """
    output_format = payload.get("output-format", "PNG")

    # default stretch is sigmoid
    if "stretch" in payload:
        stretch = payload["stretch"]
    else:
        stretch = "sigmoid"

    if payload["kind"] == "All" and payload["output-format"] != "array":
        # TODO: error 400
        pass

    # default name based on parameters
    filename = "{}_{}".format(
        payload["objectId"],
        payload["kind"],
    )

    if output_format == "PNG":
        filename = filename + ".png"
    elif output_format == "JPEG":
        filename = filename + ".jpg"
    elif output_format == "FITS":
        filename = filename + ".fits"

    # Query the Database (object query)
    client = connect_to_hbase_table("ztf.cutouts")
    results = client.scan(
        "",
        "key:key:{}".format(payload["objectId"]),
        "d:hdfs_path,i:jd,i:candid,i:objectId",
        0,
        False,
        False,
    )

    # Format the results
    schema_client = client.schema()
    client.close()

    pdf = format_hbase_output(
        results,
        schema_client,
        group_alerts=False,
        truncated=True,
        extract_color=False,
    )

    json_payload = {}
    # Extract only the alert of interest
    if "candid" in payload:
        mask = pdf["i:candid"].astype(str) == str(payload["candid"])
        json_payload.update({"candid": str(payload["candid"])})
        pos_target = np.where(mask)[0][0]
    else:
        # pdf has been sorted in `format_hbase_output`
        pdf = pdf.iloc[0:1]
        pos_target = 0

    json_payload.update(
        {
            "hdfsPath": pdf["d:hdfs_path"].to_numpy()[pos_target].split("8020")[1],
            "kind": payload["kind"],
            "objectId": pdf["i:objectId"].to_numpy()[pos_target],
        }
    )

    if pdf.empty:
        return send_file(
            io.BytesIO(),
            mimetype="image/png",
            as_attachment=True,
            download_name=filename,
        )
    # Extract cutouts
    if output_format == "FITS":
        json_payload.update({"return_type": "FITS"})
        r0 = requests.post("http://localhost:24001/api/v1/cutouts", json=json_payload)
        cutout = io.BytesIO(r0.content)
    elif output_format in ["PNG", "array"]:
        json_payload.update({"return_type": "array"})
        r0 = requests.post("http://localhost:24001/api/v1/cutouts", json=json_payload)
        cutout = json.loads(r0.content)

    # send the FITS file
    if output_format == "FITS":
        return send_file(
            cutout,
            mimetype="application/octet-stream",
            as_attachment=True,
            download_name=filename,
        )
    # send the array
    elif output_format == "array":
        if payload["kind"] != "All":
            return jsonify({"b:cutout{}_stampData".format(payload["kind"]): cutout[0]})
        else:
            out = {
                "b:cutoutScience_stampData": cutout[0],
                "b:cutoutTemplate_stampData": cutout[1],
                "b:cutoutDifference_stampData": cutout[2],
            }
            return jsonify(out)

    array = np.nan_to_num(np.array(cutout[0], dtype=float))
    if stretch == "sigmoid":
        array = sigmoid_normalizer(array, 0, 1)
    elif stretch is not None:
        pmin = 0.5
        if "pmin" in payload:
            pmin = float(payload["pmin"])
        pmax = 99.5
        if "pmax" in payload:
            pmax = float(payload["pmax"])
        array = legacy_normalizer(array, stretch=stretch, pmin=pmin, pmax=pmax)

    if "convolution_kernel" in payload:
        assert payload["convolution_kernel"] in ["gauss", "box"]
        array = convolve(array, smooth=1, kernel=payload["convolution_kernel"])

    # colormap
    if "colormap" in payload:
        colormap = getattr(cm, payload["colormap"])
    else:
        colormap = lambda x: x  # noqa: E731
    array = np.uint8(colormap(array) * 255)

    # Convert to PNG
    data = Image.fromarray(array)
    datab = io.BytesIO()
    data.save(datab, format="PNG")
    datab.seek(0)
    return send_file(
        datab, mimetype="image/png", as_attachment=True, download_name=filename
    )


def perform_xmatch(payload: dict) -> pd.DataFrame:
    """Extract data returned by HBase and jsonify it

    Data is from /api/v1/xmatch

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/xmatch

    Return
    ----------
    out: pandas dataframe
    """
    df = pd.read_csv(io.StringIO(payload["catalog"]))

    radius = float(payload["radius"])
    if radius > 18000.0:
        rep = {
            "status": "error",
            "text": "`radius` cannot be bigger than 18,000 arcseconds (5 degrees).\n",
        }
        return Response(str(rep), 400)

    header = payload["header"]

    header = [i.strip() for i in header.split(",")]
    if len(header) == 3:
        raname, decname, idname = header
    elif len(header) == 4:
        raname, decname, idname, timename = header
    else:
        rep = {
            "status": "error",
            "text": "Header should contain 3 or 4 entries from your catalog. E.g. RA,DEC,ID or RA,DEC,ID,Time\n",
        }
        return Response(str(rep), 400)

    if "window" in payload:
        window_days = payload["window"]
    else:
        window_days = None

    # Fink columns of interest
    colnames = [
        "i:objectId",
        "i:ra",
        "i:dec",
        "i:jd",
        "d:cdsxmatch",
        "i:ndethist",
    ]

    colnames_added_values = [
        "d:cdsxmatch",
        "d:roid",
        "d:mulens_class_1",
        "d:mulens_class_2",
        "d:snn_snia_vs_nonia",
        "d:snn_sn_vs_all",
        "d:rf_snia_vs_nonia",
        "i:ndethist",
        "i:drb",
        "i:classtar",
        "d:rf_kn_vs_nonkn",
        "i:jdstarthist",
    ]

    unique_cols = np.unique(colnames + colnames_added_values).tolist()

    # check units
    ra0 = df[raname].to_numpy()[0]
    if "h" in str(ra0):
        coords = [
            SkyCoord(ra, dec, frame="icrs")
            for ra, dec in zip(df[raname].to_numpy(), df[decname].to_numpy())
        ]
    elif ":" in str(ra0) or " " in str(ra0):
        coords = [
            SkyCoord(ra, dec, frame="icrs", unit=(u.hourangle, u.deg))
            for ra, dec in zip(df[raname].to_numpy(), df[decname].to_numpy())
        ]
    else:
        coords = [
            SkyCoord(ra, dec, frame="icrs", unit="deg")
            for ra, dec in zip(df[raname].to_numpy(), df[decname].to_numpy())
        ]
    ras = [coord.ra.deg for coord in coords]
    decs = [coord.dec.deg for coord in coords]
    ids = df[idname].to_numpy()

    if len(header) == 4:
        times = df[timename].to_numpy()
    else:
        times = np.zeros_like(ras)

    pdfs = pd.DataFrame(columns=unique_cols + [idname] + ["v:classification"])
    for oid, ra, dec, time_start in zip(ids, ras, decs, times):
        if len(header) == 4:
            payload_data = {
                "ra": ra,
                "dec": dec,
                "radius": radius,
                "startdate_conesearch": time_start,
                "window_days_conesearch": window_days,
            }
        else:
            payload_data = {
                "ra": ra,
                "dec": dec,
                "radius": radius,
            }
        r = requests.post(
            f"{APIURL}/api/v1/explorer",
            json=payload_data,
        )
        pdf = pd.read_json(io.BytesIO(r.content))

        # Loop over results and construct the dataframe
        if not pdf.empty:
            pdf[idname] = [oid] * len(pdf)
            if "d:rf_kn_vs_nonkn" not in pdf.columns:
                pdf["d:rf_kn_vs_nonkn"] = np.zeros(len(pdf), dtype=float)
            pdfs = pd.concat((pdfs, pdf), ignore_index=True)

    # Final join
    join_df = pdfs.merge(df, on=idname)

    # reorganise columns order
    no_duplicate = np.where(pdfs.columns != idname)[0]
    cols = list(df.columns) + list(pdfs.columns[no_duplicate])
    join_df = join_df[cols]

    return join_df.to_json(orient="records")


def return_bayestar_pdf(payload: dict) -> pd.DataFrame:
    """Extract data returned by HBase and jsonify it

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
    if "bayestar" in payload:
        bayestar_data = payload["bayestar"]
    elif "event_name" in payload:
        r = requests.get(
            "https://gracedb.ligo.org/api/superevents/{}/files/bayestar.fits.gz".format(
                payload["event_name"]
            )
        )
        if r.status_code == 200:
            bayestar_data = str(r.content)
        else:
            return pd.DataFrame([{"status": r.content}])
    credible_level_threshold = float(payload["credible_level"])

    with gzip.open(io.BytesIO(eval(bayestar_data)), "rb") as f:
        with fits.open(io.BytesIO(f.read())) as hdul:
            data = hdul[1].data
            header = hdul[1].header

    hpx = data["PROB"]
    if header["ORDERING"] == "NESTED":
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
    jdstart = Time(header["DATE-OBS"]).jd - n_day_min
    jdend = jdstart + n_day_max

    client = connect_to_hbase_table("ztf.pixel128")
    client.setRangeScan(True)
    results = {}
    for pix in pixs:
        to_search = f"key:key:{pix}_{jdstart},key:key:{pix}_{jdend}"
        result = client.scan(
            "",
            to_search,
            "*",
            0,
            True,
            True,
        )
        results.update(result)

    schema_client = client.schema()
    client.close()

    pdfs = format_hbase_output(
        results,
        schema_client,
        truncated=True,
        group_alerts=True,
        extract_color=False,
    )

    if pdfs.empty:
        return pdfs

    pdfs["v:jdstartgw"] = Time(header["DATE-OBS"]).jd

    # remove alerts with clear wrong jdstarthist
    mask = (pdfs["i:jd"] - pdfs["i:jdstarthist"]) <= n_day_max

    return pdfs[mask]


def return_statistics_pdf(payload: dict) -> pd.DataFrame:
    """Extract data returned by HBase and jsonify it

    Data is from /api/v1/statistics

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/statistics

    Return
    ----------
    out: pandas dataframe
    """
    if "columns" in payload:
        cols = payload["columns"]
    else:
        cols = "*"

    client = connect_to_hbase_table("statistics_class")
    if "schema" in payload and str(payload["schema"]) == "True":
        schema = client.schema()
        results = list(schema.columnNames())
        pdf = pd.DataFrame({"schema": results})
    else:
        payload_date = payload["date"]

        to_evaluate = f"key:key:ztf_{payload_date}"
        results = client.scan(
            "",
            to_evaluate,
            cols,
            0,
            True,
            True,
        )
        pdf = pd.DataFrame.from_dict(hbase_to_dict(results), orient="index")

        # See https://github.com/astrolabsoftware/fink-science-portal/issues/579
        pdf = pdf.replace(regex={r"^\x00.*$": 0})

    client.close()

    return pdf


def send_data(pdf, output_format):
    """ """
    if output_format == "json":
        return pdf.to_json(orient="records")
    elif output_format == "csv":
        return pdf.to_csv(index=False)
    elif output_format == "votable":
        f = io.BytesIO()
        table = Table.from_pandas(pdf)
        vt = votable.from_table(table)
        votable.writeto(vt, f)
        f.seek(0)
        return f.read()
    elif output_format == "parquet":
        f = io.BytesIO()
        pdf.to_parquet(f)
        f.seek(0)
        return f.read()

    rep = {
        "status": "error",
        "text": f"Output format `{output_format}` is not supported. Choose among json, csv, or parquet\n",
    }
    return Response(str(rep), 400)


def return_random_pdf(payload: dict) -> pd.DataFrame:
    """Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/random

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/random

    Return
    ----------
    out: pandas dataframe
    """
    if "columns" in payload:
        cols = payload["columns"].replace(" ", "")
    else:
        cols = "*"

    if "class" in payload and str(payload["class"]) != "":
        classsearch = True
    else:
        classsearch = False

    if cols == "*":
        truncated = False
    else:
        truncated = True

    if int(payload["n"]) > 16:
        number = 16
    else:
        number = int(payload["n"])

    seed = payload.get("seed")
    if seed is not None:
        np.random.seed(int(payload["seed"]))

    # logic
    client = connect_to_hbase_table("ztf.jd")
    results = []
    client.setLimit(1000)
    client.setRangeScan(True)

    jd_low = Time("2019-11-02 03:00:00.0").jd
    jd_high = Time.now().jd

    # 1 month
    delta_min = 43200
    delta_jd = TimeDelta(delta_min * 60, format="sec").jd
    while len(results) == 0:
        jdstart = np.random.uniform(jd_low, jd_high)
        jdstop = jdstart + delta_jd

        if classsearch:
            payload_data = {
                "class": payload["class"],
                "n": number,
                "startdate": Time(jdstart, format="jd").iso,
                "stopdate": Time(jdstop, format="jd").iso,
                "columns": "",
                "output-format": "json",
            }
            results = return_latests_pdf(payload_data, return_raw=True)
        else:
            results = client.scan(
                "",
                f"key:key:{jdstart},key:key:{jdstop}",
                "",
                0,
                False,
                False,
            )

    oids = list(dict(results).keys())
    oids = np.array([i.split("_")[-1] for i in oids])

    index_oid = np.random.randint(0, len(oids), number)
    oid = oids[index_oid]
    client.close()

    client = connect_to_hbase_table("ztf")
    client.setLimit(2000)
    # Get data from the main table
    results = {}
    for oid_ in oid:
        result = client.scan(
            "",
            f"key:key:{oid_}",
            f"{cols}",
            0,
            False,
            False,
        )
        results.update(result)

    pdf = format_hbase_output(
        results,
        client.schema(),
        group_alerts=False,
        truncated=truncated,
    )

    client.close()

    return pdf


def return_anomalous_objects_pdf(payload: dict) -> pd.DataFrame:
    """Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/anomaly

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/anomaly

    Return
    ----------
    out: pandas dataframe
    """
    if "n" not in payload:
        nalerts = 10
    else:
        nalerts = int(payload["n"])

    if "start_date" not in payload:
        # start of the Fink operations
        jd_start = Time("2019-11-01 00:00:00").jd
    else:
        jd_start = Time(payload["start_date"]).jd

    if "stop_date" not in payload:
        jd_stop = Time.now().jd
    else:
        # allow to get unique day
        jd_stop = Time(payload["stop_date"]).jd + 1

    if "columns" in payload:
        cols = payload["columns"].replace(" ", "")
    else:
        cols = "*"

    if cols == "*":
        truncated = False
    else:
        truncated = True

    client = connect_to_hbase_table("ztf.anomaly")
    client.setLimit(nalerts)
    client.setRangeScan(True)
    client.setReversed(True)

    to_evaluate = f"key:key:{jd_start},key:key:{jd_stop}"
    results = client.scan(
        "",
        to_evaluate,
        cols,
        0,
        True,
        True,
    )
    schema_client = client.schema()
    client.close()

    # We want to return alerts
    # color computation is disabled
    pdfs = format_hbase_output(
        results,
        schema_client,
        group_alerts=False,
        extract_color=False,
        truncated=truncated,
        with_constellation=True,
    )

    return pdfs


def return_ssoft_pdf(payload: dict) -> pd.DataFrame:
    """Send the Fink Flat Table

    Data is from /api/v1/ssoft

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/ssoft

    Return
    ----------
    out: pandas dataframe
    """
    if "version" in payload:
        version = payload["version"]

        # version needs YYYY.MM
        yyyymm = version.split(".")
        if (len(yyyymm[0]) != 4) or (len(yyyymm[1]) != 2):
            rep = {
                "status": "error",
                "text": "version needs to be YYYY.MM\n",
            }
            return Response(str(rep), 400)
        if version < "2023.07":
            rep = {
                "status": "error",
                "text": "version starts on 2023.07\n",
            }
            return Response(str(rep), 400)
    else:
        now = datetime.datetime.now()
        version = f"{now.year}.{now.month:02d}"

    if "flavor" in payload:
        flavor = payload["flavor"]
        if flavor not in ["SSHG1G2", "SHG1G2", "HG1G2", "HG"]:
            rep = {
                "status": "error",
                "text": "flavor needs to be in ['SSHG1G2', 'SHG1G2', 'HG1G2', 'HG']\n",
            }
            return Response(str(rep), 400)
    else:
        flavor = "SHG1G2"

    input_args = yaml.load(open("config_datatransfer.yml"), yaml.Loader)
    r = requests.get(
        "{}/SSOFT/ssoft_{}_{}.parquet?op=OPEN&user.name={}&namenoderpcaddress={}".format(
            input_args["WEBHDFS"],
            flavor,
            version,
            input_args["USER"],
            input_args["NAMENODE"],
        ),
    )

    if payload.get("output-format", "parquet") != "parquet":
        return pd.read_parquet(io.BytesIO(r.content))

    if "sso_name" in payload:
        pdf = pd.read_parquet(io.BytesIO(r.content))
        mask = pdf["sso_name"] == pdf["sso_name"]
        pdf = pdf[mask]
        pdf = pdf[pdf["sso_name"].astype("str") == payload["sso_name"]]
        return pdf
    elif "sso_number" in payload:
        pdf = pd.read_parquet(io.BytesIO(r.content))
        mask = pdf["sso_number"] == pdf["sso_number"]
        pdf = pdf[mask]
        pdf = pdf[pdf["sso_number"].astype("int") == int(payload["sso_number"])]
        return pdf

    # return blob
    return io.BytesIO(r.content)


def return_resolver_pdf(payload: dict) -> pd.DataFrame:
    """Extract data returned by HBase and format it in a Pandas dataframe

    Data is from /api/v1/resolver

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/resolver

    Return
    ----------
    out: pandas dataframe
    """
    resolver = payload["resolver"]
    name = payload["name"]
    if "nmax" in payload:
        nmax = payload["nmax"]
    else:
        nmax = 10

    reverse = False
    if "reverse" in payload:
        if payload["reverse"] is True:
            reverse = True

    if resolver == "tns":
        client = connect_to_hbase_table("ztf.tns_resolver")
        client.setLimit(nmax)
        if name == "":
            # return the full table
            results = client.scan(
                "",
                "",
                "*",
                0,
                False,
                False,
            )
        elif reverse:
            # Prefix search on second part of the key which is `fullname_internalname`
            to_evaluate = f"key:key:_{name}:substring"
            results = client.scan(
                "",
                to_evaluate,
                "*",
                0,
                False,
                False,
            )
        else:
            # indices are case-insensitive
            to_evaluate = f"key:key:{name.lower()}"
            results = client.scan(
                "",
                to_evaluate,
                "*",
                0,
                False,
                False,
            )

        # Restore default limits
        client.close()

        pdfs = pd.DataFrame.from_dict(hbase_to_dict(results), orient="index")
    elif resolver == "simbad":
        client = connect_to_hbase_table("ztf")
        if reverse:
            to_evaluate = f"key:key:{name}"
            client.setLimit(nmax)
            results = client.scan(
                "",
                to_evaluate,
                "i:objectId,d:cdsxmatch,i:ra,i:dec,i:candid,i:jd",
                0,
                False,
                False,
            )
            client.close()
            pdfs = pd.DataFrame.from_dict(hbase_to_dict(results), orient="index")
        else:
            r = requests.get(
                f"http://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/~S?{name}",
            )

            check = pd.read_xml(io.BytesIO(r.content))
            if "Resolver" in check.columns:
                pdfs = pd.read_xml(io.BytesIO(r.content), xpath=".//Resolver")
            else:
                pdfs = pd.DataFrame()
    elif resolver == "ssodnet":
        if reverse:
            # ZTF alerts -> ssnmanenr
            client = connect_to_hbase_table("ztf")
            to_evaluate = f"key:key:{name}"
            client.setLimit(nmax)
            results = client.scan(
                "",
                to_evaluate,
                "i:objectId,i:ssnamenr",
                0,
                False,
                False,
            )
            client.close()
            pdfs = pd.DataFrame.from_dict(hbase_to_dict(results), orient="index")

            # ssnmanenr -> MPC name & number
            if not pdfs.empty:
                client = connect_to_hbase_table("ztf.sso_resolver")
                ssnamenrs = np.unique(pdfs["i:ssnamenr"].to_numpy())
                results = {}
                for ssnamenr in ssnamenrs:
                    result = client.scan(
                        "",
                        f"i:ssnamenr:{ssnamenr}:exact",
                        "i:number,i:name,i:ssnamenr",
                        0,
                        False,
                        False,
                    )
                    results.update(result)
                client.close()
                pdfs = pd.DataFrame.from_dict(hbase_to_dict(results), orient="index")
        else:
            # MPC -> ssnamenr
            # keys follow the pattern <name>-<deduplication>
            client = connect_to_hbase_table("ztf.sso_resolver")

            if nmax == 1:
                # Prefix with internal marker
                to_evaluate = f"key:key:{name.lower()}-"
            elif nmax > 1:
                # This enables e.g. autocompletion tasks
                client.setLimit(nmax)
                to_evaluate = f"key:key:{name.lower()}"

            results = client.scan(
                "",
                to_evaluate,
                "i:ssnamenr,i:name,i:number",
                0,
                False,
                False,
            )
            client.close()
            pdfs = pd.DataFrame.from_dict(hbase_to_dict(results), orient="index")

    return pdfs


def upload_euclid_data(payload: dict) -> pd.DataFrame:
    """Upload Euclid data

    Data is from /api/v1/euclidin

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/euclidin

    Return
    ----------
    out: pandas dataframe
    """
    # Interpret user input
    data = payload["payload"]
    pipeline_name = payload["pipeline"].lower()

    # Read data into pandas DataFrame
    pdf = pd.read_csv(io.BytesIO(eval(data)), header=0, sep=" ", index_col=False)

    # Add Fink defined columns
    pdf = add_columns(
        pdf,
        pipeline_name,
        payload["version"],
        payload["date"],
        payload["EID"],
    )

    # Load official headers for HBase
    header = load_euclid_header(pipeline_name)
    euclid_header = header.keys()

    msg = check_header(pdf, list(euclid_header))
    if msg != "ok":
        return Response(msg, 400)

    # Push data in the HBase table
    mode = payload.get("mode", "production")
    if mode == "production":
        table = "euclid.in"
    elif mode == "sandbox":
        table = "euclid.test"
    client = connect_to_hbase_table(table, schema_name=f"schema_{pipeline_name}")

    for index, row in pdf.iterrows():
        # Compute the row key
        rowkey = compute_rowkey(row, index)

        # Compute the payload
        out = [f"d:{name}:{value}" for name, value in row.items()]

        client.put(
            rowkey,
            out,
        )
    client.close()

    return Response(
        "{} - {} - {} - {} - Uploaded!".format(
            payload["EID"],
            payload["pipeline"],
            payload["version"],
            payload["date"],
        ),
        200,
    )


def download_euclid_data(payload: dict) -> pd.DataFrame:
    """Download Euclid data

    Data is from /api/v1/eucliddata

    Parameters
    ----------
    payload: dict
        See https://fink-portal.org/api/v1/eucliddata

    Return
    ----------
    out: pandas dataframe
    """
    # Interpret user input
    pipeline = payload["pipeline"].lower()

    if "columns" in payload:
        cols = payload["columns"].replace(" ", "")
    else:
        cols = "*"

    # Push data in the HBase table
    mode = payload.get("mode", "production")
    if mode == "production":
        table = "euclid.in"
    elif mode == "sandbox":
        table = "euclid.test"

    client = connect_to_hbase_table(table, schema_name=f"schema_{pipeline}")

    # TODO: put a regex instead?
    if ":" in payload["dates"]:
        start, stop = payload["dates"].split(":")
        to_evaluate = f"key:key:{pipeline}_{start},key:key:{pipeline}_{stop}"
        client.setRangeScan(True)
    elif payload["dates"].replace(" ", "") == "*":
        to_evaluate = f"key:key:{pipeline}"
    else:
        start = payload["dates"]
        to_evaluate = f"key:key:{pipeline}_{start}"

    results = client.scan(
        "",
        to_evaluate,
        cols,
        0,
        False,
        False,
    )

    pdf = pd.DataFrame.from_dict(hbase_to_dict(results), orient="index")

    # Remove hbase specific fields
    if "key:key" in pdf.columns:
        pdf = pdf.drop(columns=["key:key"])
    if "key:time" in pdf.columns:
        pdf = pdf.drop(columns=["key:time"])

    # Type conversion
    schema = client.schema()
    for col in pdf.columns:
        pdf[col] = convert_datatype(
            pdf[col],
            hbase_type_converter[schema.type(col)],
        )

    client.close()

    return pdf


def post_metadata(payload: dict) -> Response:
    """Upload metadata in Fink"""
    client = connect_to_hbase_table("ztf.metadata")
    encoded = payload["internal_name"].replace(" ", "")
    client.put(
        payload["objectId"].strip(),
        [
            "d:internal_name:{}".format(payload["internal_name"]),
            f"d:internal_name_encoded:{encoded}",
            "d:comments:{}".format(payload["comments"]),
            "d:username:{}".format(payload["username"]),
        ],
    )
    client.close()

    return Response(
        "Thanks {} - You can visit {}/{}".format(
            payload["username"],
            APIURL,
            encoded,
        ),
        200,
    )


def retrieve_metadata(objectId: str) -> pd.DataFrame:
    """Retrieve metadata in Fink given a ZTF object ID"""
    client = connect_to_hbase_table("ztf.metadata")
    to_evaluate = f"key:key:{objectId}"
    results = client.scan(
        "",
        to_evaluate,
        "*",
        0,
        False,
        False,
    )
    pdf = pd.DataFrame.from_dict(hbase_to_dict(results), orient="index")
    client.close()
    return pdf


def retrieve_oid(metaname: str, field: str) -> pd.DataFrame:
    """Retrieve a ZTF object ID given metadata in Fink"""
    client = connect_to_hbase_table("ztf.metadata")
    to_evaluate = f"d:{field}:{metaname}:exact"
    results = client.scan(
        "",
        to_evaluate,
        "*",
        0,
        True,
        True,
    )
    pdf = pd.DataFrame.from_dict(hbase_to_dict(results), orient="index")
    client.close()

    return pdf

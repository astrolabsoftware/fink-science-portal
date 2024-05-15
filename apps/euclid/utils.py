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
import numpy as np
from astropy.time import Time


def load_euclid_header(pipeline=None):
    """Load the header from a Euclid pipeline (names, types)

    Parameters
    ----------
    pipeline: str
        Name of the pipeline: ssopipe, streakdet, dl

    Returns
    -------
    header: dict
        Keys are Euclid pipeline names, values are column types
    """
    if pipeline == "ssopipe":
        HEADER = {
            "INDEX": "integer",
            "RA": "double",
            "DEC": "double",
            "PROP_MOT": "double",
            "N_DET": "integer",
            "CATALOG": "string",
            "X_WORLD": "double",
            "Y_WORLD": "double",
            "ERRA_WORLD": "double",
            "ERRB_WORLD": "double",
            "FLUX_AUTO": "double",
            "FLUXERR_AUTO": "double",
            "MAG_AUTO": "double",
            "MAGERR_AUTO": "double",
            "ELONGATION": "double",
            "ELLIPTICITY": "double",
            "MJD": "double",
        }
    elif pipeline == "streakdet":
        HEADER = {
            "Obj_id": "integer",
            "Dither": "double",
            "NDet": "integer",
            "RA_middle": "double",
            "DEC_middle": "double",
            "RA_start": "double",
            "DEC_start": "double",
            "RA_end": "double",
            "DEC_end": "double",
            "MJD_middle": "double",
            "MJD_start": "double",
            "MJD_end": "double",
            "FLUX_AUTO": "double",
            "MAG_AUTO": "double",
        }
    elif pipeline == "dl":
        HEADER = {
            "Obj_id": "integer",
            "Dither": "double",
            "NDet": "integer",
            "RA_middle": "double",
            "DEC_middle": "double",
            "RA_start": "double",
            "DEC_start": "double",
            "RA_end": "double",
            "DEC_end": "double",
            "MJD_middle": "double",
            "MJD_start": "double",
            "MJD_end": "double",
            "FLUX_AUTO": "double",
            "MAG_AUTO": "double",
            "Score": "double",
        }
    else:
        print(f"Pipeline name {pipeline} not understood")
        HEADER = {}

    # Fink added columns
    HEADER.update({"pipeline": "string"})
    HEADER.update({"version": "string"})
    HEADER.update({"submission_date": "integer"})
    HEADER.update({"EID": "string"})

    return HEADER

def add_columns(pdf, pipeline: str, version: str, submission_date: int, eid: str):
    """Add Fink based column names to an incoming Euclid dataFrame

    Parameters
    ----------
    pdf: pd.DataFrame
        Incoming data from Euclid
    pipeline: str
        Name of the pipeline: ssopipe, streakdet, dl
    version: str
        Pipeline version
    submission_date: int
        Date provided by the user
    eid: str
        Unique ID for a detection

    Returns
    -------
    pdf: pd.DataFrame
    """
    # add a column with the name of the pipeline
    pdf["pipeline"] = pipeline
    pdf["version"] = version
    pdf["submission_date"] = submission_date
    pdf["EID"] = eid

    return pdf

def compute_rowkey(row: dict, index: int):
    """Compute the row key based on a formatted dataframe

    Parameters
    ----------
    row: dict
        Row of the Euclid dataframe
    index: int
        Index of the row

    Returns
    -------
    rowkey: string
        <pipeline>_<date>_<EID>_<index>
    """
    if row["pipeline"] == "ssopipe":
        t0 = row["MJD"]
    else:
        t0 = row["MJD_start"]

    iso = Time(t0, format="mjd").strftime("%Y%m%d")

    rowkey = "{}_{}_{}_{}".format(row["pipeline"], iso, row["EID"], index)

    return rowkey

def check_header(pdf, euclid_header):
    """Check if the columns of the DataFrame match those expected

    Parameters
    ----------
    pdf: pd.DataFrame
        Euclid DataFrame for a given pipeline
    euclid_header: list
        List of column names for a given pipeline
    """
    cols1 = np.sort(pdf.columns)
    cols2 = np.sort(euclid_header)
    if ~np.all(cols1 == cols2):
        missingfields = [field for field in euclid_header if field not in pdf.columns]
        newfields = [field for field in pdf.columns if field not in euclid_header]
        msg = f"""
        WARNING: we detected a difference in the schema with respect to what is defined on the server.
        Missing fields: {missingfields}
        New fields: {newfields}
        """
    else:
        msg = "ok"
    return msg

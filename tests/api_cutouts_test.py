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
import requests
import numpy as np

from astropy.io import fits

from PIL import Image

import io
import sys

APIURL = sys.argv[1]


def cutouttest(
    objectId="ZTF21aaxtctv",
    kind="Science",
    stretch="sigmoid",
    colormap="viridis",
    pmin=0.5,
    pmax=99.5,
    convolution_kernel=None,
    output_format="PNG",
    candid=None,
):
    """Perform a cutout search in the Science Portal using the Fink REST API"""
    payload = {
        "objectId": objectId,
        "kind": kind,  # Science, Template, Difference
        "stretch": stretch,  # sigmoid[default], linear, sqrt, power, log, asinh
        "colormap": colormap,  # Valid matplotlib colormap name (see matplotlib.cm). Default is grayscale.
        "pmin": pmin,  # The percentile value used to determine the pixel value of minimum cut level. Default is 0.5. No effect for sigmoid.
        "pmax": pmax,  # The percentile value used to determine the pixel value of maximum cut level. Default is 99.5. No effect for sigmoid.
        "output-format": output_format,
    }

    if candid is not None:
        payload.update({"candid": candid})

    # Convolve the image with a kernel (gauss or box). Default is None (not specified).
    if convolution_kernel is not None:
        payload.update({"convolution_kernel": convolution_kernel})

    r = requests.post("{}/api/v1/cutouts".format(APIURL), json=payload)

    assert r.status_code == 200, r.content

    if output_format == "PNG":
        # Format output in a DataFrame
        data = Image.open(io.BytesIO(r.content))
    elif output_format == "FITS":
        data = fits.open(io.BytesIO(r.content), ignore_missing_simple=True)
    elif output_format == "array":
        data = r.json()["b:cutout{}_stampData".format(kind)]

    return data


def test_png_cutout() -> None:
    """
    Examples
    --------
    >>> test_png_cutout()
    """
    data = cutouttest()

    assert data.format == "PNG"
    assert data.size == (63, 63)


def test_fits_cutout() -> None:
    """
    Examples
    --------
    >>> test_fits_cutout()
    """
    data = cutouttest(output_format="FITS")

    assert len(data) == 1
    assert np.shape(data[0].data) == (63, 63)


def test_array_cutout() -> None:
    """
    Examples
    --------
    >>> test_array_cutout()
    """
    data = cutouttest(output_format="array")

    assert np.shape(data) == (63, 63), data
    assert isinstance(data, list)


def test_kind_cutout() -> None:
    """
    Examples
    --------
    >>> test_kind_cutout()
    """
    data1 = cutouttest(kind="Science", output_format="array")
    data2 = cutouttest(kind="Template", output_format="array")
    data3 = cutouttest(kind="Difference", output_format="array")

    assert data1 != data2
    assert data2 != data3


def test_pvalues_cutout() -> None:
    """
    Examples
    --------
    >>> test_pvalues_cutout()
    """
    # pmin and pmax have no effect if stretch = sigmoid
    data1 = cutouttest()
    data2 = cutouttest(pmin=0.1, pmax=0.5)

    assert data1.getextrema() == data2.getextrema()

    # pmin and pmax have an effect otherwise
    data1 = cutouttest()
    data2 = cutouttest(pmin=0.1, pmax=0.5, stretch="linear")

    assert data1.getextrema() != data2.getextrema()


def test_stretch_cutout() -> None:
    """
    Examples
    --------
    >>> test_stretch_cutout()
    """
    # pmin and pmax have no effect if stretch = sigmoid
    data1 = cutouttest(stretch="sigmoid")

    for stretch in ["linear", "sqrt", "power", "log"]:
        data2 = cutouttest(stretch=stretch)
        assert data1.getextrema() != data2.getextrema()


def test_colormap_cutout() -> None:
    """
    Examples
    --------
    >>> test_colormap_cutout()
    """
    data1 = cutouttest()
    data2 = cutouttest(colormap="Greys")

    assert data1.getextrema() != data2.getextrema()


def test_convolution_kernel_cutout() -> None:
    """
    Examples
    --------
    >>> test_convolution_kernel_cutout()
    """
    data1 = cutouttest()
    data2 = cutouttest(convolution_kernel="gauss")

    assert data1.getextrema() != data2.getextrema()


def test_candid_cutout() -> None:
    """
    Examples
    --------
    >>> test_candid_cutout()
    """
    data1 = cutouttest()
    data2 = cutouttest(candid="1622215345315015012")

    assert data1.getextrema() != data2.getextrema()


if __name__ == "__main__":
    """ Execute the test suite """
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])

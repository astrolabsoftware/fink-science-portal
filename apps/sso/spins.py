# Copyright 2022 AstroLab Software
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
import pandas as pd
import numpy as np
import io

from astropy.coordinates import SkyCoord
import astropy.units as u

import scipy
from scipy.optimize import curve_fit

def func_hg(ph, h, g):
    """ Return f(H, G) part of the lightcurve in mag space

    Parameters
    ----------
    ph: array-like
        Phase angle in radians
    h: float
        Absolute magnitude in mag
    G: float
        G parameter (no unit)
    """
    from sbpy.photometry import HG

    # Standard G part
    func1 = (1 - g) * HG._hgphi(ph, 1) + g * HG._hgphi(ph, 2)
    func1 = -2.5 * np.log10(func1)

    return h + func1

def func_hg12(ph, h, g12):
    """ Return f(H, G) part of the lightcurve in mag space

    Parameters
    ----------
    ph: array-like
        Phase angle in radians
    h: float
        Absolute magnitude in mag
    G: float
        G parameter (no unit)
    """
    from sbpy.photometry import HG1G2, HG12

    # Standard G1G2 part
    g1 = HG12._G12_to_G1(g12)
    g2 = HG12._G12_to_G2(g12)
    func1 = g1*HG1G2._phi1(ph)+g2*HG1G2._phi2(ph)+(1-g1-g2)*HG1G2._phi3(ph)
    func1 = -2.5 * np.log10(func1)

    return h + func1

def func_hg1g2(ph, h, g1, g2):
    """ Return f(H, G1, G2) part of the lightcurve in mag space

    Parameters
    ----------
    ph: array-like
        Phase angle in radians
    h: float
        Absolute magnitude in mag
    G1: float
        G1 parameter (no unit)
    G2: float
        G2 parameter (no unit)
    """
    from sbpy.photometry import HG1G2

    # Standard G1G2 part
    func1 = g1*HG1G2._phi1(ph)+g2*HG1G2._phi2(ph)+(1-g1-g2)*HG1G2._phi3(ph)
    func1 = -2.5 * np.log10(func1)

    return h + func1

def func_hg1g2_with_spin(pha, h, g1, g2, R, lambda0, beta0):
    """ Return f(H, G1, G2, R, lambda0, beta0) part of the lightcurve in mag space

    Parameters
    ----------
    pha: array-like [3, N]
        List containing [phase angle in radians, RA in radians, Dec in radians]
    h: float
        Absolute magnitude in mag
    G1: float
        G1 parameter (no unit)
    G2: float
        G2 parameter (no unit)
    R: float
        Oblateness (no units)
    lambda0: float
        RA of the spin (radian)
    beta0: float
        Dec of the spin (radian)
    """
    ph = pha[0]
    ra = pha[1]
    dec = pha[2]

    # Standard HG1G2 part: h + f(alpha, G1, G2)
    func1 = func_hg1g2(ph, h, g1, g2)

    # Spin part
    geo = np.sin(dec) * np.sin(beta0) + np.cos(dec) * np.cos(beta0) * np.cos(ra - lambda0)
    func2 = 1 - (1 - R) * np.abs(geo)
    func2 = -2.5 * np.log10(func2)

    return func1 + func2

def add_ztf_color_correction(pdf, combined=False):
    """ Add a new column with ZTF color correction.

    The factor is color-dependent, and assumed to be:
    - V_minus_g = -0.32
    - V_minus_r = 0.13

    g --> g + (V - g)
    r --> r + (V - r) - (V - g)

    Parameters
    ----------
    pdf: pd.DataFrame
        Pandas DataFrame with Fink ZTF data
    combined: bool
        If True, normalised using g

    Returns
    ----------
    out: pd.DataFrame
        Input Pandas DataFrame with a new column `color_corr`
    """
    filts = np.unique(pdf['i:fid'].values)
    color_sso = np.ones_like(pdf['i:magpsf'])
    for i, filt in enumerate(filts):
        # SSO Color index
        V_minus_g = -0.32
        V_minus_r = 0.13

        cond = pdf['i:fid'] == filt

        # Color conversion
        if filt == 1:
            color_sso[cond] = V_minus_g
        else:
            if combined:
                color_sso[cond] = V_minus_r - V_minus_g
            else:
                color_sso[cond] = V_minus_r

    pdf['color_corr'] = color_sso

    return pdf

def estimate_sso_params(pdf, func, bounds=([0, 0, 0, 1e-6, 0, -np.pi/2], [30, 1, 1, 1, 2*np.pi, np.pi/2])):
    """
    """
    ydata = pdf['i:magpsf_red'] + pdf['color_corr']

    # Values in radians
    alpha = np.deg2rad(pdf['Phase'].values)
    ra = np.deg2rad(pdf['i:ra'].values)
    dec = np.deg2rad(pdf['i:dec'].values)
    pha = np.transpose([[i, j, k] for i, j, k in zip(alpha, ra, dec)])

    if func.__name__ == 'func_hg1g2_with_spin':
        nparams = 6
        x = pha
    elif func.__name__ == 'func_hg1g2':
        nparams = 3
        x = alpha
    elif func.__name__ == 'func_hg12':
        nparams = 2
        x = alpha
    elif func.__name__ == 'func_hg':
        nparams = 2
        x = alpha

    if not np.alltrue([i == i for i in ydata.values]):
        popt = [None] * nparams
        perr = [None] * nparams
        chisq_red = None
        return popt, perr, chisq_red

    try:
        popt, pcov = curve_fit(
            func,
            x,
            ydata.values,
            # sigma=pdf['i:sigmapsf'],
            bounds=bounds,
            # jac=Dfunc_hg1g2_with_spin
        )

        perr = np.sqrt(np.diag(pcov))

        r = ydata.values - func(x, *popt)
        chisq = np.sum((r / pdf['i:sigmapsf'])**2)
        chisq_red = 1. / len(ydata.values - 1 - nparams) * chisq

    except RuntimeError as e:
        print(e)
        popt = [None] * nparams
        perr = [None] * nparams
        chisq_red = None

    return popt, perr, chisq_red
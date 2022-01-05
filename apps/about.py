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
import dash_html_components as html
import dash_bootstrap_components as dbc

msg = """
Fink is a broker infrastructure enabling a wide range of applications and services to connect to large streams of alerts issued from telescopes all over the world.
"""
msg_infra="""
Architecture of Fink. Each box is a cluster of machines deployed on a cloud. The main streams of alerts for Fink (ZTF, and LSST) are collected and processed inside the Processing cluster running Apache Spark. At the end of the processing, a series of filter divides the stream into substreams based on user needs, and data is sent to subscribers via the Communication cluster running Apache Kafka. At the end of the night, all processed data is aggregated and pushed into the Science Portal, based on
Apache HBase, where users can connect via a web browser and explore all processed Fink data. Alert data and added-values are stored at various stages on the Hadoop Distributed File System (HDFS). Other survey data streams (such as alert data from LIGO/Virgo, Fermi or Swift) are collected by the Communication cluster and sent to the Processing cluster to be used to enrich the main stream of alerts.
"""
msg_results="""
Footprint of the ZTF alert stream from November 2019 to June 2020 associated to a subset of transient types using current Fink science modules: confirmed and candidates Solar System objects (top-left blue), variable stars from the cross-match with the Simbad catalog (orange top-right), alerts matched to a galaxy in the Simbad catalog (green middle-left), supernovae type Ia candidates selected using SuperNNova (red middle-right), microlensing event candidates selected using LIA (purple
bottom-left), and all 7,975,588 processed alerts by Fink that pass quality cuts (bottom-right). The Planck Commander thermal dust map (Akrami et al. 2018) is shown in the background for reference. All maps are in the Galactic coordinate system, with a healpix resolution parameter equal to Nside=128 (Gorski et al. 2005), except for alerts matching galaxies (green middle-left) where Nside=64 has been used to increase the readability. More information at https://arxiv.org/abs/2009.10185.
"""
msg_alert="""
Fink comes to join a few other brokers currently operating on other experiments, such as the Zwicky Transient Facility (ZTF, Bellm et al. 2018) or the High cadence Transient Survey (HiTS, Förster et al. 2016). Among these are ALeRCE (Förster et al. 2020), Ampel (Nordin et al. 2019), Antares (Narayan et al. 2018), Lasair (Smith et al. 2019), MARS and SkyPortal (van der Walt et al. 2019). ZTF has the particularity to use an alert system design that is very close to the one envisioned by LSST (Patterson et al. 2019), hence allowing to prototype and test systems with the relevant features and communication protocols prior to the start of LSST operations.
"""
msg_thanks="""
We are grateful to all supporters of the project. Fink is supported by CNRS/IN2P3 within LSST-France (https://www.lsst.fr/). We acknowledge the support from the VirtualData cloud at Université Paris-Saclay which provides the computing resources.
The project received support from the Google Summer of Code 2019 and 2020. The project acknowledges financial support from CNRS-MOMENTUM 2018-2020, NASA grant 80NSSC19K0291, European Structural and Investment Fund and the Czech Ministry of Education, Youth and Sports (Project CoGraDS-CZ.02.1.01/0.0/0.0/15003/0000437).
This research makes use of ZTF (https://www.ztf.caltech.edu/) public alert data. ZTF is supported by National Science Foundation grant AST-1440341 and a collaboration including Caltech, IPAC, the Weizmann Institute for Science, the Oskar Klein Center at Stockholm University, the University of Maryland, the University of Washington, Deutsches Elektronen-Synchrotron and Humboldt University, Los Alamos National Laboratories, the TANGO Consortium of Taiwan, the University of Wisconsin at Milwaukee, and Lawrence Berkeley National Laboratories. Operations are conducted by COO, IPAC, and UW.
This research has made use of "Aladin sky atlas" developed at CDS, Strasbourg Observatory, France (see 2000A&AS..143...33B and 2014ASPC..485..277B).
"""

layout = html.Div([
    dbc.Container([
        dbc.Row(
            [
                dbc.Col(html.H2("Fink infrastructure"), className="mb-5 mt-5")
            ]
        ),
        dbc.Row(
            dbc.Col(
                html.Img(
                    src="/assets/infrastructure.png",
                    height='300px',
                    width='75%'
                )
            ), style={'textAlign': 'center'}
        ),
        dbc.Row(
            html.H5(children=msg_infra, className='text-align')
        ),
        dbc.Row(
            [
                dbc.Col(html.H2("Fink results"), className="mb-5 mt-5")
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    html.H5(children=msg_results, className='text-align')
                ),
                dbc.Col(
                    html.Img(
                        src="/assets/footprint_nside128.png",
                        height='500px',
                        width='100%'
                    )
                ),
            ]
        ),
        dbc.Row(
            [
                dbc.Col(html.H2("LSST alert ecosystem"), className="mb-5 mt-5")
            ]
        ),
        dbc.Row(
            [
                dbc.Col(html.H5(children=msg_alert, className='text-align')),
            ]
        ),
        dbc.Row(
            [
                dbc.Col(html.H2("Acknowledgments"), className="mb-5 mt-5")
            ]
        ),
        dbc.Row(
            [
                dbc.Col(html.H5(children=msg_thanks, className='text-align')),
            ]
        ),
        html.Br(),
        dbc.Row([
            html.Img(src="/assets/cnrs.png", height='100px', width='100px'),
            html.Img(src="/assets/lsstfr.png", height='100px', width='200px'),
            html.Img(src="/assets/ztf.png", height='100px', width='150px'),
        ], justify='center'),
        html.Br()
    ])

])

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

layout = html.Div([
    dbc.Container([
        dbc.Row(dbc.Col(html.Img(src="/assets/Fink_PrimaryLogo_WEB.png", height='100%', width='40%')), style={'textAlign': 'center'}),
        dbc.Row([
            dbc.Col(
                dbc.CardDeck([
                    dbc.Card(children=[
                        html.H3(children="Explore Fink historical data", className="text-center"),
                        html.H6(children="Browse all alert data collected and processed by Fink", className="text-center"),
                        dbc.Button(
                            "Explorer",
                            href="/explorer",
                            color="secondary",
                            className="mt-3"
                        ),
                    ], body=True, color="dark", outline=True, style={'background-color': 'rgba(245, 245, 245, .75)'}
                    ),
                    dbc.Card(children=[
                        html.H3(children="Cross-match with Fink data", className="text-center"),
                        html.H6(children="Upload your catalog and cross-match against Fink alert data", className="text-center"),
                        dbc.Button(
                            "Xmatch",
                            href="/xmatch",
                            color="secondary",
                            className="mt-3"
                        ),
                    ], body=True, color="dark", outline=True, style={'background-color': 'rgba(245, 245, 245, .75)'}
                    ),
                    dbc.Card(children=[
                        html.H3(children='Explore the Graph database', className="text-center"),
                        html.H6(children="Visualise links between alerts and detect patterns in Fink data", className="text-center"),
                        dbc.Button(
                            "Grafink (Not yet available)",
                            href="/grafink",
                            color="secondary",
                            disabled=True,
                            className="mt-3"),
                        ], body=True, color="dark", outline=True, style={'background-color': 'rgba(245, 245, 245, .75)'})
                        ]
                    ),
                )]
            ),
        html.Br(),
        ], className='Absolute-Center'),
    html.Footer(
        [
            html.Img(src="/assets/cnrs.png", height='30px', width='30px'),
            html.Img(src="/assets/lsstfr.png", height='30px', width='60px'),
            html.Img(src="/assets/ztf.png", height='30px', width='45px')
        ], className='footer')

    ], className='home', style={
            'background-image': 'url(/assets/background.png)', 'background-size': 'contain'})

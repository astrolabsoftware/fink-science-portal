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
from dash import html, dcc, Input, Output
import dash_mantine_components as dmc

from app import app

import requests

dcc.Location(id='url', refresh=False)

@app.callback(
    Output("batch_log", "children"),
    [
        Input('update_batch_log', 'n_clicks'),
        Input('url', 'pathname')
    ]
)
def update_log(n_clicks, pathname):
    if n_clicks:
        batchid = pathname.split('/batch/')[-1]
        response = requests.get('http://134.158.75.222:21111/batches/{}/log'.format(batchid))
        output = html.Div(response.text)
        return output

def layout(path, is_mobile):
    layout_ = html.Div(
        [
            html.Br(),
            html.Br(),
            dmc.Button("Update log", id='update_batch_log', color='orange'),
            html.Div(id='batch_log')
        ], className='home', style={'background-image': 'linear-gradient(rgba(255,255,255,0.9), rgba(255,255,255,0.9)), url(/assets/background.png)', 'background-size': 'cover'}
    )
    return layout_
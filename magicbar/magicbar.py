import dash
from dash import html, dcc, Input, Output, State, dash_table, no_update
import requests
import dash_bootstrap_components as dbc
import visdcc
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import pandas as pd
import io
import re
import numpy as np
from fink_utils.xmatch.simbad import get_simbad_labels

simbad_types = get_simbad_labels('old_and_new')
simbad_types = sorted(simbad_types, key=lambda s: s.lower())

tns_types = pd.read_csv('../assets/tns_types.csv', header=None)[0].values
tns_types = sorted(tns_types, key=lambda s: s.lower())

finkclasses = [
    'Unknown',
    'Early Supernova Ia candidates',
    'Supernova candidates',
    'Kilonova candidates',
    'Microlensing candidates',
    'Solar System (MPC)',
    'Solar System (candidates)',
    'Tracklet (space debris & satellite glints)',
    'Ambiguous',
    *['(TNS) ' + t for t in tns_types],
    *['(SIMBAD) ' + t for t in simbad_types]
]

APIURL = 'https://fink-portal.org'

# bootstrap theme
external_stylesheets = [
    dbc.themes.SPACELAB,
    '//aladin.u-strasbg.fr/AladinLite/api/v2/latest/aladin.min.css',
    '//use.fontawesome.com/releases/v5.7.2/css/all.css',
]
external_scripts = [
    '//code.jquery.com/jquery-1.12.1.min.js',
    '//aladin.u-strasbg.fr/AladinLite/api/v2/latest/aladin.min.js',
    '//cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.4/MathJax.js?config=TeX-MML-AM_CHTML',
]

app = dash.Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    external_scripts=external_scripts,
    meta_tags=[{
        "name": "viewport",
        "content": "width=device-width, initial-scale=1"
    }]
)

def call_resolver(data, kind):
    """ Call the resolver

    Parameters
    ----------
    data: str
        Query payload
    kind: str
        Resolver name: ssodnet, tns, simbad

    Returns
    ----------
    payload: dict
        Payload returned by the /api/v1/resolver endpoint
    """
    r = requests.post(
        '{}/api/v1/resolver'.format(APIURL),
        json={
            'resolver': kind,
            'name': str(data),
        }
    )
    payload = r.json()

    return payload

def define_templates_and_regex(badge):
    """ Define the templates used to extract information from
    user requests

    Parameters
    ----------
    badge: str
        Kind of query: Conesearch, Solar System, ...

    Returns
    ----------
    template: str
        template message to be displayed on the Portal
    regex: str
        Corresponding regex to extract values
    """
    if badge == 'Solar System':
        template = 'badge={} | {} (type={}, class={})'
        regex = r"^badge\=(?P<badge>\w+\s+\w+?) \| (?P<name>\w+?) \(type\=(?P<type>\w+?), class\=(?P<class>\w+?)\>(?P<class2>\w+?)\)$"
    elif badge == 'Conesearch':
        template = 'badge={} | ra={}, dec={}, radius={}'
        regex = r"^badge\=(?P<badge>\w+?) \| ra\=(?P<ra>[+-]?\d*\.?\d+)\,\s+?dec\=(?P<dec>[+-]?\d*\.?\d+)\,\s+?radius\=(?P<radius>\d*\.?\d+)$"
    elif badge == 'ZTF':
        template = 'badge=ZTF | objectId={}'
        regex = r"^badge\=(?P<badge>\w+?) \| objectId=(?P<objectId>.+)$"
    elif badge == 'Fink tag':
        template = 'badge=Fink tag | tag={}'
        regex = r"^badge\=(?P<badge>\w+\s+\w+?) \| tag=(?P<tag>.+)$"
    elif badge == 'TNS':
        template = 'badge={} | {} (internal={}, type={}, pos={}, {})'
        regex = r"^badge\=(?P<badge>\w+?) \| (?P<name>\w+\s?\w+?) \(internal\=(?P<internal>\w+?)\, type\=(?P<type>\w+\s?\w+?)\, pos\=(?P<ra>[+-]?\d*\.?\d+)\, (?P<dec>[+-]?\d*\.?\d+)\)$"
    elif badge == 'SIMBAD':
        template = 'badge={} | {} (type={}, pos={})'
        regex = r"^badge\=(?P<badge>\w+?) \| (?P<name>\w+\s+?\w+?) \(type\=(?P<type>\w+\W*)\, pos\=(?P<ra>[+-]?\d+\:\d+\:\d+\.\d+?) (?P<dec>[+-]?\d+\:\d+\:\d+\.\d+?)\)$"
    elif badge == 'Satellite':
        template = 'badge=Satellite | date={}'
        regex = r"^badge\=(?P<badge>\w+?) \| date=(?P<date>\s?\d+\-\d+\-\d+\s?\d*?\:?\d*?\:?\d*?\.?\d*?)$"
    elif badge == 'badge':
        template = ''
        regex = r"^badge\=(?P<badge>\w+\s?\w+?) \| .+$"
    else:
        print('{} not understood'.format(badge))
    return template, regex

def process_regex(regex, data):
    """ Extract parameters from a regex given the data

    Parameters
    ----------
    regex: str
        Regular expression to use
    data: str
        Data entered by the user

    Returns
    ----------
    parameters: dict or None
        Parameters (key: value) extracted from the data
    """
    template = re.compile(regex)
    m = template.match(data)
    if m is None:
        return None

    parameters = m.groupdict()
    return parameters

def failure_message(badge):
    """ Display a message for malformed queries

    Parameters
    ----------
    badge: str
        The kind of queries

    Returns
    ----------
    msg: str
        The message to display
    """
    if badge == 'Satellite':
        return 'Bad satellite query. You must use <Satellite YYYY-MM-HH hh:mm:ss>. Note the <MM-HH hh:mm:ss> part is optional.'
    elif badge == 'Conesearch':
        return 'Bad conesearch query. You must at least specify comma-separated RA, DEC, radius. Optionally, you can also specify starting date (YYYY-MM-DD), and a time window in days.'
    elif badge == 'Fink tag':
        return 'Bad Fink tag. You must select a valid class name from {}/api/v1/classes'.format(APIURL)
    elif badge == 'ZTF':
        return 'Bad ZTF name.'
    elif badge == 'Solar System':
        return 'Bad Solar System object name'
    elif badge == 'TNS':
        return 'Bad TNS name.'
    elif badge == 'SIMBAD':
        return 'Bad SIMBAD name'
    else:
        return 'Query not understood'

@app.callback(
    Output('select', 'options'),
    Input('select', 'search_value'),
)
def autocomplete(data):
    """ Search for SSO names matching in IMCCE database

    Return only the 10 first results (autocomplete and resolver)
    """
    if not data:
        raise PreventUpdate

    if data is not None:
        if ',' in str(data):
            # conesearch or datesearch
            badge = 'Conesearch'
            vals = [i.strip() for i in data.split(',')]
            template = 'badge={} | ra={}, dec={}, radius={}'
            if len(vals) == 1:
                val = template.format(badge, vals[0], '', '')
            elif len(vals) == 2:
                val = template.format(badge, vals[0], vals[1], '')
            elif len(vals) == 3:
                val = template.format(badge, *vals)
            options = [{'label': dmc.Group([html.Div(val), dmc.Badge(badge, variant="outline", color='grey')], noWrap=False), 'value': val}]
            return options
        elif data.startswith('ZTF'):
            template = 'badge=ZTF | objectId={}'.format(data)
            options = [{'label': dmc.Group([html.Div(template), dmc.Badge("ZTF", variant="outline", color='dark')], noWrap=False), 'value': template}]
            return options
        elif data.startswith('Satellite'):
            tmp = data.split('Satellite')
            template = 'badge=Satellite | date={}'.format(tmp[-1])
            options = [{'label': dmc.Group([html.Div(template), dmc.Badge("Satellite", variant="outline", color='red')], noWrap=False), 'value': template}]
            return options
        else:
            sso_payload = call_resolver(data, 'ssodnet')
            simbad_payload = call_resolver(data, 'simbad')
            tns_payload = call_resolver(data, 'tns')
            finkmatches = [i for i in finkclasses if i.startswith(data)]

            options = []

            if len(sso_payload) > 0:
                # it is a SSO?
                badge = 'Solar System'
                template = 'badge={} | {} (type={}, class={})'
                names = []
                for i in sso_payload:
                    if ('class' in i.keys()) and (i['class'] is not None):
                        txt = template.format(badge, i['name'], i['type'], '>'.join(i['class']))
                    else:
                        txt = template.format(badge, i['name'], i['type'], '>None')
                    names.append(txt)
                options += [{'label': dmc.Group([html.Div(name.split('|')[-1]), dmc.Badge("Solar System", variant="outline", color='lime')], noWrap=False), 'value': name, 'search': str(data)} for name in names]
            if len(finkmatches) > 0:
                template = 'badge=Fink tag | tag={}'
                options += [{'label': dmc.Group([html.Div(template.format(finkmatch)), dmc.Badge("Fink tag", variant="outline", color='orange')], noWrap=False), 'value': template.format(finkmatch), 'search': str(data)} for finkmatch in finkmatches]
                # return options
            if len(tns_payload) > 0:
                badge = 'TNS'
                template = 'badge={} | {} (internal={}, type={}, pos={}, {})'
                names = []
                for i in tns_payload:
                    txt = template.format(badge, i['d:fullname'], i['d:internalname'], i['d:type'], i['d:ra'], i['d:declination'])
                    names.append(txt)
                options += [{'label': dmc.Group([html.Div(name), dmc.Badge("TNS", variant="outline", color='pink')], noWrap=False), 'value': name, 'search': str(data)} for name in names]
            if len(simbad_payload) > 0:
                badge = 'SIMBAD'
                template = 'badge={} | {} (type={}, pos={})'
                names = []
                for i in simbad_payload:
                    txt = template.format(badge, i['oname'], i['otype'], i['jpos'])
                    names.append(txt)
                options += [{'label': dmc.Group([html.Div(name), dmc.Badge("SIMBAD", variant="outline")], noWrap=False), 'value': name, 'search': str(data)} for name in names]
    else:
        options = [{'label': str(data), 'value': str(data)}]

    return options

@app.callback(
    Output('check', 'children'),
    Input('select', 'value'),
)
def check(data):
    """ now need to construct the table below
    """
    if (data is None) or (data == ''):
        raise PreventUpdate

    _, regex = define_templates_and_regex('badge')
    badge = process_regex(regex, data)['badge']

    _, regex = define_templates_and_regex(badge)
    parameters = process_regex(regex, data)

    if parameters is None:
        msg = failure_message(badge)
        return dmc.Alert(msg)

    return html.Div(str(parameters))


# embedding the navigation bar
fink_search_bar = dbc.InputGroup(
    [
        dcc.Dropdown(
            id='select',
            options=[],
            placeholder='Enter first letters or numbers of a SSO (e.g. cer)',
            style={"border": "0px black solid", 'background': 'rgba(255, 255, 255, 0.0)', 'color': 'grey', 'width': '100pc'},
        )
    ], style={"border": "0.5px grey solid", 'background': 'rgba(255, 255, 255, .75)'}, className='rcorners2'
)

app.layout = html.Div(
    [
        dbc.Container(
            [
                html.Br(),
                dbc.Row(fink_search_bar),
                html.Div(id='check'),
            ]
        )
    ]
)

app.run_server('localhost', debug=True)

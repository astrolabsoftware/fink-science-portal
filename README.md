# Fink Science Portal

[![Sentinel](https://github.com/astrolabsoftware/fink-science-portal/workflows/Sentinel/badge.svg)](https://github.com/astrolabsoftware/fink-science-portal/actions?query=workflow%3ASentinel)

![fronted](assets/frontend.png)

The Fink Science Portal allows users to browse and display alert data collected and processed by Fink from a web browser: [https://fink-portal.org](https://fink-portal.org).

The backend is using [Apache HBase](https://hbase.apache.org/), a distributed non-relational database. The frontend is based on [Dash](https://plotly.com/dash/), a Python web framework built on top of Flask, Plotly and React. The frontend has also integrated components to perform fit on the data, such as [gatspy](https://www.astroml.org/gatspy/) for variable stars, [pyLIMA](https://github.com/ebachelet/pyLIMA) for microlensing, or the [imcce](https://ssp.imcce.fr/webservices/miriade/) tools for Solar System objects.

## Backend structure

After each observation night, the data is aggregated and pushed into Apache HBase tables. The main table contains all alert data processed by Fink since 2019-11-01. This represents more than 271 million alerts collected, and about 184 million scientifically valid as of 01/2025. The main table data is indexed along the `objectId` of alerts, and the emission date `jd`.

In order to allow multi-indexing with HBase, we create _index tables_. These tables are indexed along different properties (time, sky position, classification, ...). They contain the same number of rows than the main table but fewer columns. These index tables are used to perform fast search along arbitrary properties and isolate interesting candidates, while the main table is used to display final data.

We developed custom HBase clients to manipulate the data efficiently (Lomikel, FinkBrowser, more information [here](https://hrivnac.web.cern.ch/hrivnac/Activities/index.html)).

## Local deployment

The portal has been tested on Python 3.9 to 3.11. Other versions might work. First you need to install the Python dependencies:

```bash
python -m venv portal_env
source portal_env/bin/activate

pip install -r requirements.txt
```

The default configuration file (`config.yml`) should be enough to deploy, so just execute:

```bash
python index.py
```

and navigate to [http://localhost:24000/](http://localhost:24000/).

## Cloud deployment

The procedure for developpers and maintainers can be found on the [Fink GitLab](https://gitlab.in2p3.fr/fink/rubin-performance-check/-/blob/main/portal/README.md?ref_type=heads) repository (auth required).

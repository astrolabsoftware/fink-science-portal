# Fink Science Portal

The Fink Science Portal allows users to browse and display alert data collected and processed by Fink from a web browser. The Portal can be accessed from the Fink website: [https://fink-broker.org](https://fink-broker.org).

The backend is using [Apache HBase](https://hbase.apache.org/), a distributed non-relational database. The frontend is based on [Dash](https://plotly.com/dash/), a Python web framework built on top of Flask, Plotly and React. The frontend has also integrated components to perform fit on the data, such as [gatspy](https://www.astroml.org/gatspy/) for variable stars or [pyLIMA](https://github.com/ebachelet/pyLIMA) for microlensing.

## Backend structure

After each observation night, the data is aggregated and pushed into Apache HBase tables. The main table contains all alert data processed by Fink since 2019-11-01. This represents more than 50 million alerts collected (2 TB), and about 20 million processed (700 GB) after one year of operation. The main table data is indexed along the `objectId` of alerts, and the emission date `jd`.

In order to allow multi-indexing with HBase, we create _index tables_. These tables are indexed along different properties (time, sky position, classification, ...). They contain the same number of rows than the main table but fewer columns. These index tables are used to perform fast search along arbitrary properties and isolate interesting candidates, while the main table is used to display final data.

We developed custom HBase clients to manipulate the data efficiently (Lomikel, FinkBrowser, more information [here](https://hrivnac.web.cern.ch/hrivnac/Activities/index.html)).

## Deployment & monitoring

The frontend is host at the VirtualData cloud at Université Paris-Saclay, France. To deploy it:

```python
# debug mode
python index.py

# production mode
gunicorn index:server -b :24000 --workers=N
```

Note that you need the Java HBase client (the jar is not distributed here), which you can compile from the [FinkBrowser](https://hrivnac.web.cern.ch/hrivnac/Activities/Packages/FinkBrowser/) repository. We also put in place a [Grafana dashboard](https://supervision.lal.in2p3.fr/dashboard/db/fink-web-dashboard?refresh=1m&orgId=1) with some metrics to monitor the service.

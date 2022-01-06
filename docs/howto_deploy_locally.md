# Deploy and test the portal locally

For test purposes, we summarise here the steps to deploy the portal locally. This has been tested on a machine with Centos 7 (os.8) on the cloud at VirtualData.

## Basic environment

First, install basic tools

```bash
yum install git wget gcc-c++
```

Then install [Miniconda](https://docs.conda.io/en/latest/miniconda.html). We will focus on Python 3.7 as we did not test more recent versions:

```bash
cd $HOME
wget https://repo.anaconda.com/miniconda/Miniconda3-py37_4.10.3-Linux-x86_64.sh
bash Miniconda3-py37_4.10.3-Linux-x86_64.sh
# answer with all defaults
rm Miniconda3-py37_4.10.3-Linux-x86_64.sh
```

Then clone the the Fink Science Portal repository, and install dependencies:

```bash
cd $HOME
git clone https://github.com/astrolabsoftware/fink-science-portal.git

cd fink-science-portal
pip install -r requirements.txt
```

Update your `.bash_profile` (or whatever you are using) with the path to the Portal:

```bash
echo "export FSP_HOME=$HOME/fink-science-portal" >> ~/.bash_profile
source ~/.bash_profile
```

## Java, HBase, Spark

To work, the Portal needs Apache HBase, where data is stored inside tables. First, make sure you have Java 8 (required by Spark 2.4.x, see later) installed otherwise install it:

```bash
yum install java-1.8.0-openjdk

# Adapt the path to your configuration
echo "export JAVA_HOME=/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.312.b07-1.el7_9.x86_64/jre" >> ~/.bash_profile
source ~/.bash_profile
```

Then install HBase, and launch it (locally):

```bash
cd $HOME/fink-science-portal

./bin/install_hbase.sh
```

This will install HBase in `$HOME/hbase-2.2.7`. In case you need to restart the service:

```bash
cd $HOME/hbase-2.2.7

./bin/start-hbase.sh
```

Then install Apache Spark (2.4.7, required by Fink):

```bash
cd $HOME/fink-science-portal

bin/install_spark.sh
source ~/.bash_profile
```

And finally clone the fink-broker repository and install dependencies:

```bash
cd $HOME
git clone https://github.com/astrolabsoftware/fink-broker.git
cd fink-broker

./install_python_deps.sh
source ~/.bash_profile
```

Add some variable in your `~/.bash_profile`:

```bash
# ~/.bash_profile
export FINK_HOME=/root/fink-broker
export PATH=$PATH:$FINK_HOME/bin
export PYTHONPATH=$PYTHONPATH:$FINK_HOME
```

and source it.

## Injecting alert data into HBase

We share some real ZTF alert data for test purposes. The alerts are in the internal format Fink is using (partitioned Parquet files), and can be found in `$FSP_HOME/archive`. You need then to push this data into HBase (as is done by Fink at the end of the observation night):

```bash
cd $HOME/fink-science-portal
./bin/database_service.sh
```

if all goes right you should have tables in HBase (otherwise, check the `logs/` folder):

```bash
$ cd $HOME/hbase-2.2.7
$ bin/hbase shell
hbase(main):001:0> list

TABLE
statistics_class
test_sp
test_sp.class
test_sp.jd
test_sp.pixel128
test_sp.pixel131072
test_sp.pixel4096
test_sp.ssnamenr
test_sp.tracklet
test_sp.upper
test_sp.uppervalid
11 row(s)
```

then go to `$HOME/fink-science-portal`, and in `index.py` put your IP address and port (make sure your port is open):

```python
# index.py
app.run_server(IP, debug=True, port=PORT)
```

and edit also `app.py` with your IP address and port:

```python
APIURL = "http://IP:PORT"
```

Execute `python index.py`, open a browser on your local machine, and go to `http://IP:PORT`. Et voilà!

## Troubleshooting

You might see this error when executing `python index.py`:

```bash
  936 ERROR (HBaser.HBaseClient            : 382) : Cannot search
org.apache.hadoop.hbase.TableNotFoundException: test_sp.tns
	at org.apache.hadoop.hbase.client.ConnectionImplementation.locateRegionInMeta(ConnectionImplementation.java:889)
	at org.apache.hadoop.hbase.client.ConnectionImplementation.locateRegion(ConnectionImplementation.java:784)
	at org.apache.hadoop.hbase.client.HRegionLocator.getRegionLocation(HRegionLocator.java:64)
	at org.apache.hadoop.hbase.client.RegionLocator.getRegionLocation(RegionLocator.java:58)
	at org.apache.hadoop.hbase.client.RegionLocator.getRegionLocation(RegionLocator.java:47)
	at org.apache.hadoop.hbase.client.RegionServerCallable.prepare(RegionServerCallable.java:223)
	at org.apache.hadoop.hbase.client.RpcRetryingCallerImpl.callWithRetries(RpcRetryingCallerImpl.java:105)
	at org.apache.hadoop.hbase.client.HTable.get(HTable.java:384)
	at org.apache.hadoop.hbase.client.HTable.get(HTable.java:358)
	at com.Lomikel.HBaser.HBaseClient.scan(HBaseClient.java:376)
	at com.Lomikel.HBaser.HBaseClient.scan(HBaseClient.java:300)
	at com.Lomikel.HBaser.HBaseClient.scan(HBaseClient.java:241)
	at com.Lomikel.HBaser.HBaseClient.connect(HBaseClient.java:181)
	at com.Lomikel.HBaser.HBaseClient.connect(HBaseClient.java:147)
```

This is perfectly normal -- to populate the TNS table you would need credentials. Hence, this table is not created, and the client cannot find it! But you can ignore the error, and continue as normal.



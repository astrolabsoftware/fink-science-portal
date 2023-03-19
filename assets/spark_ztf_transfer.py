from pyspark import SparkContext
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.column import Column, _to_java_column
import pyspark.sql.functions as F
from pyspark.sql.functions import struct, lit
from pyspark.sql.functions import pandas_udf, PandasUDFType
from pyspark.sql.types import StringType

from fink_filters.classification import extract_fink_classification

from time import time
import pandas as pd
import numpy as np
from astropy.coordinates import SkyCoord
from astropy import units as u

import io
import os
import glob
import shutil
import json
import fastavro
import sys
import subprocess
import argparse
import requests

import logging
from logging import Logger

COLS_FINK = [
    'finkclass',
    'tnsclass',
    'cdsxmatch',
    'roid',
    'mulens',
    'DR3Name',
    'Plx',
    'e_Plx',
    'gcvs',
    'vsx',
    'snn_snia_vs_nonia',
    'snn_sn_vs_all',
    'rf_snia_vs_nonia',
    'rf_kn_vs_nonkn',
    'tracklet',
    'x4lac',
    'x3hsp',
    'mangrove',
    't2',
    'anomaly_score'
]

def get_fink_logger(name: str = "test", log_level: str = "INFO") -> Logger:
    """ Initialise python logger. Suitable for both driver and executors.

    Parameters
    ----------
    name : str
        Name of the application to be logged. Typically __name__ of a
        function or module.
    log_level : str
        Minimum level of log wanted: DEBUG, INFO, WARNING, ERROR, CRITICAL, OFF

    Returns
    ----------
    logger : logging.Logger
        Python Logger

    Examples
    ----------
    >>> log = get_fink_logger(__name__, "INFO")
    >>> log.info("Hi!")
    """
    # Format of the log message to be printed
    FORMAT = "%(asctime)-15s "
    FORMAT += "-Livy- "
    FORMAT += "%(message)s"

    # Date format
    DATEFORMAT = "%y/%m/%d %H:%M:%S"

    logging.basicConfig(format=FORMAT, datefmt=DATEFORMAT)
    logger = logging.getLogger(name)

    # Set the minimum log level
    logger.setLevel(log_level)

    return logger

def add_classification(spark, df, path_to_tns):
    """ Add classification from Fink & TNS

    Parameters
    ----------
    spark:
    df: DataFrame
        Spark DataFrame containing ZTF alert data
    path_to_tns: str
        Path to TNS data (parquet)

    Returns
    ----------
    df: DataFrame
        Input DataFrame with 2 new columns `finkclass` and
        `tnsclass` containing classification tags.
    """
    # extract Fink classification
    df = df.withColumn(
        'finkclass',
        extract_fink_classification(
            df['cdsxmatch'],
            df['roid'],
            df['mulens'],
            df['snn_snia_vs_nonia'],
            df['snn_sn_vs_all'],
            df['rf_snia_vs_nonia'],
            df['candidate.ndethist'],
            df['candidate.drb'],
            df['candidate.classtar'],
            df['candidate.jd'],
            df['candidate.jdstarthist'],
            df['rf_kn_vs_nonkn'],
            df['tracklet']
        )
    )

    pdf_tns_filt = pd.read_parquet(path_to_tns)
    pdf_tns_filt_b = spark.sparkContext.broadcast(pdf_tns_filt)

    @pandas_udf(StringType(), PandasUDFType.SCALAR)
    def crossmatch_with_tns(objectid, ra, dec):
        # TNS
        pdf = pdf_tns_filt_b.value
        ra2, dec2, type2 = pdf['ra'], pdf['declination'], pdf['type']

        # create catalogs
        catalog_ztf = SkyCoord(
            ra=np.array(ra, dtype=np.float) * u.degree,
            dec=np.array(dec, dtype=np.float) * u.degree
        )
        catalog_tns = SkyCoord(
            ra=np.array(ra2, dtype=np.float) * u.degree,
            dec=np.array(dec2, dtype=np.float) * u.degree
        )

        # cross-match
        idx, d2d, d3d = catalog_tns.match_to_catalog_sky(catalog_ztf)

        sub_pdf = pd.DataFrame({
            'objectId': objectid.values,
            'ra': ra.values,
            'dec': dec.values,
        })

        # cross-match
        idx2, d2d2, d3d2 = catalog_ztf.match_to_catalog_sky(catalog_tns)

        # set separation length
        sep_constraint2 = d2d2.degree < 1.5 / 3600

        sub_pdf['TNS'] = ['Unknown'] * len(sub_pdf)
        sub_pdf['TNS'][sep_constraint2] = type2.values[idx2[sep_constraint2]]

        to_return = objectid.apply(
            lambda x: 'Unknown' if x not in sub_pdf['objectId'].values
            else sub_pdf['TNS'][sub_pdf['objectId'] == x].values[0]
        )

        return to_return

    df = df.withColumn(
        'tnsclass',
        crossmatch_with_tns(
            df['objectId'],
            df['candidate.ra'],
            df['candidate.dec']
        )
    )

    return df

def to_avro(dfcol: Column) -> Column:
    """Serialize the structured data of a DataFrame column into
    avro data (binary).

    Note:
    Since Pyspark does not have a function to convert a column to and from
    avro data, this is a wrapper around the scala function 'to_avro'.
    Just like the function above, to be able to use this you need to have
    the package org.apache.spark:spark-avro_2.11:2.x.y in the classpath.

    Parameters
    ----------
    dfcol: Column
        A DataFrame Column with Structured data

    Returns
    ----------
    out: Column
        DataFrame Column encoded into avro data (binary).
        This is what is required to publish to Kafka Server for distribution.

    Examples
    ----------
    >>> from pyspark.sql.functions import col, struct
    >>> avro_example_schema = '''
    ... {
    ...     "type" : "record",
    ...     "name" : "struct",
    ...     "fields" : [
    ...             {"name" : "col1", "type" : "long"},
    ...             {"name" : "col2", "type" : "string"}
    ...     ]
    ... }'''
    >>> df = spark.range(5)
    >>> df = df.select(struct("id",\
                 col("id").cast("string").alias("id2"))\
                 .alias("struct"))
    >>> avro_df = df.select(to_avro(col("struct")).alias("avro"))
    """
    sc = SparkContext._active_spark_context
    avro = sc._jvm.org.apache.spark.sql.avro
    f = getattr(getattr(avro, "package$"), "MODULE$").to_avro
    return Column(f(_to_java_column(dfcol)))

def save_avro_schema(df: DataFrame, schema_path: str):
    """Writes the avro schema to a file at schema_path

    This routine checks if an avro schema file exist at the given path
    and creates one if it doesn't.

    To automatically change the schema with changing requirements, ensure to
    delete the schema file at the given path whenever the structure of DF
    read from science db or the contents to be distributed are changed.

    Parameters
    ----------
    df: DataFrame
        A Spark DataFrame
    schema_path: str
        Path where to store the avro schema
    """

    # Check if the file exists
    if not os.path.isfile(schema_path):
        # Store the df as an avro file
        path_for_avro = os.path.join(os.environ["PWD"], "flatten_hbase.avro")
        if os.path.exists(path_for_avro):
            shutil.rmtree(path_for_avro)
        df.write.format("avro").save(path_for_avro)

        # Read the avro schema from .avro file
        avro_file = glob.glob(path_for_avro + "/part*")[0]
        avro_schema = readschemafromavrofile(avro_file)

        # Write the schema to a file for decoding Kafka messages
        with open(schema_path, 'w') as f:
            json.dump(avro_schema, f, indent=2)

        # Remove .avro files and directory
        shutil.rmtree(path_for_avro)
    else:
        msg = """
            {} already exists - cannot write the new schema
        """.format(schema_path)
        print(msg)

def readschemadata(bytes_io: io._io.BytesIO) -> fastavro._read.reader:
    """Read data that already has an Avro schema.

    Parameters
    ----------
    bytes_io : `_io.BytesIO`
        Data to be decoded.

    Returns
    -------
    `fastavro._read.reader`
        Iterator over records (`dict`) in an avro file.

    Examples
    ----------
    Open an avro file, and read the schema and the records
    >>> with open(ztf_alert_sample, mode='rb') as file_data:
    ...   data = readschemadata(file_data)
    ...   # Read the schema
    ...   schema = data.schema
    ...   # data is an iterator
    ...   for record in data:
    ...     print(type(record))
    <class 'dict'>
    """
    bytes_io.seek(0)
    message = fastavro.reader(bytes_io)
    return message

def readschemafromavrofile(fn: str) -> dict:
    """ Reach schema from a binary avro file.

    Parameters
    ----------
    fn: str
        Input Avro file with schema.

    Returns
    ----------
    schema: dict
        Dictionary (JSON) describing the schema.

    Examples
    ----------
    >>> schema = readschemafromavrofile(ztf_alert_sample)
    >>> print(schema['version'])
    3.3
    """
    with open(fn, mode='rb') as file_data:
        data = readschemadata(file_data)
        schema = data.schema
    return schema

def write_to_kafka(sdf, key, kafka_bootstrap_servers, kafka_sasl_username, kafka_sasl_password, topic_name, npart=10):
    """ Send data to a Kafka cluster using Apache Spark

    Parameters
    ----------
    sdf: Spark DataFrame
        DataFrame
    key: str
        key for each Avro message
    kafka_bootstrap_servers: str
        Comma-separated list of ip:port of the Kafka machines
    kafka_sasl_username: str
        Username for writing into the Kafka cluster
    kafka_sasl_password: str
        Password for writing into the Kafka cluster
    topic_name: str
        Kafka topic (does not need to exist)
    npart: int, optional
        Number of Kafka partitions. Default is 10.
    """
    # Create a StructType column in the df for distribution.
    df_struct = sdf.select(struct(sdf.columns).alias("struct"))
    df_kafka = df_struct.select(to_avro("struct").alias("value"))
    df_kafka = df_kafka.withColumn('key', key)
    df_kafka = df_kafka.withColumn('partition', (F.rand(seed=0) * npart).astype('int'))

    # Send schema
    disquery = df_kafka\
        .write\
        .format("kafka")\
        .option("kafka.bootstrap.servers", kafka_bootstrap_servers)\
        .option("kafka.sasl.username", kafka_sasl_username)\
        .option("kafka.sasl.password", kafka_sasl_password)\
        .option("topic", topic_name)\
        .save()

def check_path_exist(dateToCheck):
    """ Check we have data for the given night

    Parameters
    ----------
    dateToCheck: str
        YYYY-MM-DD

    Returns
    ----------
    out: bool
    """
    r = requests.post(
        'https://fink-portal.org/api/v1/statistics',
        json={
            'date': '{}{}{}'.format(*dateToCheck.split('-')),
            'columns': 'basic:sci',
            'output-format': 'json'
        }
    )
    if r.json() == []:
        return False
    else:
        return True

def generate_spark_paths(startDate, stopDate, basePath):
    """ Generate individual data paths

    Parameters
    ----------
    startDate: str
        YYYY-MM-DD
    stopDate: str
        YYYY-MM-DD
    basePath: str
        HDFS basepath for the data

    Returns
    ----------
    paths: list of str
        List of paths
    """
    endPath = '/year={}/month={}/day={}'

    if startDate == stopDate:
        # easy case -- one night
        if check_path_exist(startDate):
            paths = [basePath + endPath.format(*startDate.split('-'))]
        else:
            paths = []
    else:
        # more than one night
        dateRange = pd.date_range(
            start=startDate,
            end=stopDate
        ).astype('str').values

        paths = []
        for aDate in dateRange:
            if check_path_exist(aDate):
                paths.append(basePath + endPath.format(*aDate.split('-')))

    return paths

def main(args):
    spark = SparkSession.builder.getOrCreate()

    # reduce Java verbosity
    spark.sparkContext.setLogLevel("WARN")

    log = get_fink_logger(__file__)

    log.info("Generating data paths...")
    paths = generate_spark_paths(args.startDate, args.stopDate, args.basePath)
    if paths == []:
        log.info('No alert data found in between {} and {}'.format(args.startDate, args.stopDate))
        spark.stop()
        sys.exit(1)

    df = spark.read.format('parquet').option('basePath', args.basePath).load(paths)

    df = add_classification(spark, df, args.path_to_tns)

    # need fclass and extra conditions
    if args.fclass is not None:
        if args.fclass != []:
            if 'allclasses' not in args.fclass:
                tns_class = [i for i in args.fclass if i.startswith('(TNS)')]
                other_class = [i for i in args.fclass if i not in tns_class]
                sanitized_other_class = [i.replace('(SIMBAD) ', '') for i in other_class]

                if tns_class != [] and sanitized_other_class != []:
                    f1 = df['finkclass'].isin(sanitized_other_class)
                    f2 = df['tnsclass'].isin(tns_class)
                    df = df.filter(f1 | f2)
                elif tns_class != []:
                    f1 = df['tnsclass'].isin(tns_class)
                    df = df.filter(f1)
                elif sanitized_other_class != []:
                    f1 = df['finkclass'].isin(sanitized_other_class)
                    df = df.filter(f1)

    if args.extraCond is not None:
        for cond in args.extraCond:
            if cond == '':
                continue
            df = df.filter(cond)

    if args.content == 'Full packet':
        # Cast fields to ease the distribution
        cnames = df.columns
        cnames[cnames.index('timestamp')] = 'cast(timestamp as string) as timestamp'
        cnames[cnames.index('cutoutScience')] = 'struct(cutoutScience.*) as cutoutScience'
        cnames[cnames.index('cutoutTemplate')] = 'struct(cutoutTemplate.*) as cutoutTemplate'
        cnames[cnames.index('cutoutDifference')] = 'struct(cutoutDifference.*) as cutoutDifference'
        cnames[cnames.index('prv_candidates')] = 'explode(array(prv_candidates)) as prv_candidates'
        cnames[cnames.index('candidate')] = 'struct(candidate.*) as candidate'
        cnames[cnames.index('lc_features_g')] = 'struct(lc_features_g.*) as lc_features_g'
        cnames[cnames.index('lc_features_r')] = 'struct(lc_features_r.*) as lc_features_r'
    elif args.content == 'Lightcurve':
        cnames = [
            'objectId',
            'candidate.candid',
            'candidate.magpsf',
            'candidate.sigmapsf',
            'candidate.fid',
            'candidate.jd',
            'candidate.ra',
            'candidate.dec'
        ]

        for col in COLS_FINK:
            # added values are at the root level
            if col in df.columns:
                cnames.append(col)

    elif args.content == 'Cutouts':
        cnames = [
            'objectId',
            'candidate.candid',
            'candidate.magpsf',
            'candidate.ra',
            'candidate.dec',
            'candidate.jd',
            'cutoutScience',
            'cutoutTemplate',
            'cutoutDifference'
        ]

        for col in COLS_FINK:
            # added values are at the root level
            if col in df.columns:
                cnames.append(col)

        cnames[cnames.index('cutoutScience')] = 'struct(cutoutScience.*) as cutoutScience'
        cnames[cnames.index('cutoutTemplate')] = 'struct(cutoutTemplate.*) as cutoutTemplate'
        cnames[cnames.index('cutoutDifference')] = 'struct(cutoutDifference.*) as cutoutDifference'

    # Wrap alert data
    df = df.selectExpr(cnames)

    # save schema
    log.info("Determining data schema...")
    path_for_avro = 'new_schema_{}.avro'.format(time())
    df.coalesce(1).limit(1).write.format("avro").save(path_for_avro)

    # retrieve data on local disk
    subprocess.run(["hdfs", "dfs", '-get', path_for_avro])

    # Read the avro schema from .avro file
    avro_file = glob.glob(path_for_avro + "/part*")[0]
    avro_schema = readschemafromavrofile(avro_file)

    # Write the schema to a file for decoding Kafka messages
    with open('/tmp/{}'.format(path_for_avro.replace('.avro', '.avsc')), 'w') as f:
        json.dump(avro_schema, f, indent=2)

    # reload the schema
    with open('/tmp/{}'.format(path_for_avro.replace('.avro', '.avsc')), 'r') as f:
        schema_ = json.dumps(f.read())

    schema = json.loads(schema_)

    log.info("Schema OK...")

    # create a fake dataframe with 100 entries
    df_schema = spark.createDataFrame(
        pd.DataFrame(
            {
                'schema': [path_for_avro.replace('.avro', '.avsc')] * 1000
            }
        )
    )

    log.info("Sending the schema to Kafka...")

    # Send schema
    write_to_kafka(
        df_schema,
        lit(schema),
        args.kafka_bootstrap_servers,
        args.kafka_sasl_username,
        args.kafka_sasl_password,
        args.topic_name + '_schema'
    )

    log.info('Starting to send data to topic {}'.format(args.topic_name))

    # Send data
    if args.limit_output:
        log.info('Limiting to 10 first entries...')
        df = df.coalesce(1).limit(10)

    write_to_kafka(
        df,
        lit(args.topic_name),
        args.kafka_bootstrap_servers,
        args.kafka_sasl_username,
        args.kafka_sasl_password,
        args.topic_name
    )

    log.info('Data ({}) available at topic: {}'.format(args.content, args.topic_name))
    log.info('End.')


if __name__ == "__main__":
    """ Execute the test suite """
    parser = argparse.ArgumentParser()

    parser.add_argument('-startDate')
    parser.add_argument('-stopDate')
    parser.add_argument('-fclass', action='append')
    parser.add_argument('-extraCond', action='append')
    parser.add_argument('-content')
    parser.add_argument('-basePath')
    parser.add_argument('-topic_name')
    parser.add_argument('-kafka_bootstrap_servers')
    parser.add_argument('-kafka_sasl_username')
    parser.add_argument('-kafka_sasl_password')
    parser.add_argument('-path_to_tns')
    parser.add_argument('--limit_output', action='store_true', default=False)

    args = parser.parse_args()
    main(args)

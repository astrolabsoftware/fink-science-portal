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

def write_to_kafka(sdf, key, kafka_bootstrap_servers, kafka_sasl_username, kafka_sasl_password, topic_name):
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
    """
    # Create a StructType column in the df for distribution.
    df_struct = sdf.select(struct(sdf.columns).alias("struct"))
    df_kafka = df_struct.select(to_avro("struct").alias("value"))
    df_kafka = df_kafka.withColumn('key', key)

    # Send schema
    disquery = df_kafka\
        .write\
        .format("kafka")\
        .option("kafka.bootstrap.servers", kafka_bootstrap_servers)\
        .option("kafka.sasl.username", kafka_sasl_username)\
        .option("kafka.sasl.password", kafka_sasl_password)\
        .option("topic", topic_name)\
        .save()

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
        year, month, day = startDate.split('-')
        paths = [basePath + endPath.format(year, int(month), int(day))]
    else:
        # more than one night
        dateRange = pd.date_range(
            start=startDate,
            end=stopDate
        ).astype('str').values

        paths = []
        for aDate in dateRange:
            year, month, day = aDate.split('-')
            paths.append(basePath + endPath.format(year, int(month), int(day)))

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
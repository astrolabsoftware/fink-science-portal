# Copyright 2023 AstroLab Software
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
from pyspark import SparkContext
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.column import Column, _to_java_column
import pyspark.sql.functions as F
from pyspark.sql.functions import struct, lit
from pyspark.sql.functions import pandas_udf, PandasUDFType
from pyspark.sql.types import StringType

from fink_filters.classification import extract_fink_classification
from fink_utils.spark import schema_converter

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

def check_path_exist(spark, path):
    """ Check we have data for the given night on HDFS

    Parameters
    ----------
    path: str
        Path on HDFS (file or folder)

    Returns
    ----------
    out: bool
    """
    # check on hdfs
    jvm = spark._jvm
    jsc = spark._jsc
    fs = jvm.org.apache.hadoop.fs.FileSystem.get(jsc.hadoopConfiguration())
    if fs.exists(jvm.org.apache.hadoop.fs.Path(path)):
        return True
    else:
        return False

def generate_spark_paths(spark, startDate, stopDate, basePath):
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

    paths = []
    if startDate == stopDate:
        year, month, day = startDate.split('-')
        path = basePath + endPath.format(year, month, day)
        if check_path_exist(spark, path):
            paths = [path]
    else:
        # more than one night
        dateRange = pd.date_range(
            start=startDate,
            end=stopDate
        ).astype('str').values

        for aDate in dateRange:
            year, month, day = aDate.split('-')
            path = basePath + endPath.format(year, month, day)
            if check_path_exist(spark, path):
                paths.append(path)

    return paths

def main(args):
    spark = SparkSession.builder.getOrCreate()

    # reduce Java verbosity
    spark.sparkContext.setLogLevel("WARN")

    log = get_fink_logger(__file__)

    log.info("Generating data paths...")
    paths = generate_spark_paths(spark, args.startDate, args.stopDate, args.basePath)
    if paths == []:
        log.info('No alert data found in between {} and {}'.format(args.startDate, args.stopDate))
        spark.stop()
        sys.exit(1)

    df = spark.read.format('parquet').option('basePath', args.basePath).load(paths)

    # need fclass and extra conditions
    if args.fclass is not None:
        if args.fclass != []:
            if 'allclasses' not in args.fclass:
                df = df.filter(df['classId'].isin(args.fclass))

    if args.extraCond is not None:
        for cond in args.extraCond:
            if cond == '':
                continue
            df = df.filter(cond)

    if args.content == 'Full packet':
        # Cast fields to ease the distribution
        cnames = df.columns
        cnames[cnames.index('timestamp')] = 'cast(timestamp as string) as timestamp'
        cnames[cnames.index('classId')] = 'cast(classId as integer) as classId'

    # Wrap alert data
    df = df.selectExpr(cnames)

    # extract schema
    log.info("Determining data schema...")
    schema = schema_converter.to_avro(df.coalesce(1).limit(1).schema)

    log.info("Schema OK...")

    # create a fake dataframe with 100 entries
    df_schema = spark.createDataFrame(
        pd.DataFrame(
            {
                'schema': ['new_schema_{}.avsc'.format(time())] * 1000
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

    args = parser.parse_args()
    main(args)
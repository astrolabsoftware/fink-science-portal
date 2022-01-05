#!/bin/bash
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
set -e

SPARK_VERSION=2.4.7

wget https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop2.7.tgz
tar -xf spark-${SPARK_VERSION}-bin-hadoop2.7.tgz
rm spark-${SPARK_VERSION}-bin-hadoop2.7.tgz

echo "export SPARK_HOME=$FSP_HOME/spark-${SPARK_VERSION}-bin-hadoop2.7" >> ~/.bash_profile
export SPARK_HOME=$FSP_HOME/spark-${SPARK_VERSION}-bin-hadoop2.7

echo "export PATH=$PATH:${SPARK_HOME}/bin:${SPARK_HOME}/sbin" >> ~/.bash_profile
echo "spark.yarn.jars=${SPARK_HOME}/jars/*.jar" > ${SPARK_HOME}/conf/spark-defaults.conf
echo "ARROW_PRE_0_15_IPC_FORMAT=1" > ${SPARK_HOME}/conf/spark-env.sh

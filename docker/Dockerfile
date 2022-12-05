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
FROM centos:centos7

WORKDIR /root


RUN yum -y update \
&& yum -y install git wget java-1.8.0-openjdk gcc-c++ \
&& yum -y clean all \
&& rm -rf /var/cache \
&& echo "export JAVA_HOME=$(dirname $(dirname $(readlink -f $(type -P java))))" > /etc/profile.d/javahome.sh


RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-py37_4.11.0-Linux-x86_64.sh -O ~/miniconda.sh \
&& bash ~/miniconda.sh -b -p /miniconda

ENV PYTHONPATH=/miniconda
ENV PATH=/miniconda/bin:/usr/local/bin:${PATH}

ADD requirements.txt .

# Install Python deps.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
&& pip install -r requirements.txt

ENTRYPOINT /bin/bash


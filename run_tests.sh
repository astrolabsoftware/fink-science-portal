#!/bin/bash
# Copyright 2019 AstroLab Software
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
## Script to launch the python test suite and measure the coverage.
## Must be launched as fink_test
set -e
message_help="""
Run the test suite of the modules\n\n
Usage:\n
    \t./run_tests.sh [--url]\n\n

--url is the Science Portal URL you would like to test against.
"""
# Grab the command line arguments
while [ "$#" -gt 0 ]; do
  case "$1" in
    --url)
        URL="$2"
        shift 2
        ;;
    -h)
        echo -e $message_help
        exit
        ;;
  esac
done

if [[ -f $URL ]]; then
  echo "You need to specify an URL" $URL
  exit
fi

# Run the test suite on the utilities
cd tests
for filename in ./*.py
do
  echo $filename
  # Run test suite
  python $filename $URL
done

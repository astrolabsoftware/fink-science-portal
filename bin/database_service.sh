#!/bin/bash

source ~/.bash_profile

NIGHT=19881103

mkdir -p logs

echo "science_archival"
fink start science_archival -c fink.conf.travis --night ${NIGHT} > logs/science_archival_${NIGHT}.log 2>&1

echo "Update index tables"
fink start index_archival -c fink.conf.travis --night ${NIGHT} --index_table jd_objectId > logs/index_jd_objectId_${NIGHT}.log 2>&1
fink start index_archival -c fink.conf.travis --night ${NIGHT} --index_table pixel128_jd > logs/index_pixel128_jd_${NIGHT}.log 2>&1
fink start index_archival -c fink.conf.travis --night ${NIGHT} --index_table pixel4096_jd > logs/index_pixel4096_jd_${NIGHT}.log 2>&1
fink start index_archival -c fink.conf.travis --night ${NIGHT} --index_table pixel131072_jd > logs/index_pixel131072_jd_${NIGHT}.log 2>&1
fink start index_archival -c fink.conf.travis --night ${NIGHT} --index_table class_jd_objectId > logs/index_class_jd_objectId_${NIGHT}.log 2>&1
fink start index_archival -c fink.conf.travis --night ${NIGHT} --index_table upper_objectId_jd > logs/index_upper_objectId_jd_${NIGHT}.log 2>&1
fink start index_archival -c fink.conf.travis --night ${NIGHT} --index_table ssnamenr_jd > logs/index_ssnamenr_jd_${NIGHT}.log 2>&1
fink start index_archival -c fink.conf.travis --night ${NIGHT} --index_table uppervalid_objectId_jd > logs/index_uppervalid_objectId_jd_${NIGHT}.log 2>&1
fink start index_archival -c fink.conf.travis --night ${NIGHT} --index_table tracklet_objectId > logs/index_tracklet_objectId_${NIGHT}.log 2>&1
# fink start index_archival -c fink.conf.travis --night ${NIGHT} --index_table tns_jd --tns_folder ${FINK_HOME}/tns_logs > logs/index_tns_jd_${NIGHT}.log 2>&1

echo "Update statistics"
fink start stats -c fink.conf.travis --night ${NIGHT}

exit

#!/bin/bash
# Process every CICIoT2023 capture as soon as data/ciciot/list.tsv.log marks it OK (SHA verified).
cd "$(dirname "$0")"; mkdir -p out/ciciot
LOG=../data/ciciot/list.tsv.log
TOTAL=$(wc -l < ../data/ciciot/list.tsv)
while true; do
  n=0
  for f in $(grep ' OK ' $LOG | awk '{print $4}'); do
    cls=$(basename $(dirname $f)); b=$(basename $f .pcap); p=out/ciciot/${cls}__${b}
    n=$((n+1))
    [ -f $p.stats.json ] && continue
    ./flowfeat $p $f 2>> out/ciciot_feat.log && echo "FEAT $p" >> out/ciciot_feat.log
  done
  [ $n -ge $TOTAL ] && break
  sleep 60
done
echo CICIOT-FEAT-DONE >> out/ciciot_feat.log

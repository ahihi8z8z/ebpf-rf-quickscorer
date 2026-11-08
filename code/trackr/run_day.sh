#!/usr/bin/env bash
# Track-R offline evaluation of Hara's shipped models on one CIC-IDS2017 day (server3).
#   ./run_day.sh <day> <pcap|pcapng> <csv> [<csv> ...]
# Outputs in out/days/<day>_*: .cls (DT,NN binary), .lab.npy/.json, .feat (dir/bidir), .nn7 (AF_XDP 7-class)
set -euo pipefail
cd "$(dirname "$0")"
DAY=$1; PCAP=$2; shift 2
O=out/days/$DAY; mkdir -p out/days
./hara_ref "$PCAP" ${O}_dir_ns --key dir --dump-feat 2> ${O}_dir_ns.log &
./hara_ref "$PCAP" ${O}_bidir_ns --key bidir --dump-feat 2> ${O}_bidir_ns.log &
./hara_ref "$PCAP" ${O}_dir_ns_lru1024 --key dir --lru 1024 2> ${O}_dir_ns_lru1024.log &
wait
python3 label_packets.py ${O}_dir_ns.meta ${O}.lab.npy "$@" > ${O}_label.log
rm -f ${O}_bidir_ns.meta ${O}_dir_ns_lru1024.meta ${O}_dir_ns.meta
for k in dir bidir; do
  ./nn7_eval ${O}_${k}_ns.feat ${O}_${k}_ns.cls ${O}_nn7_${k}_raw.nn7 2> ${O}_nn7_${k}_raw.log &
  ./nn7_eval ${O}_${k}_ns.feat ${O}_${k}_ns.cls ${O}_nn7_${k}_norm.nn7 --normalize 2> ${O}_nn7_${k}_norm.log &
done
wait
cat ${O}_*_ns.log ${O}_dir_ns_lru1024.log; grep -A12 per_class ${O}_label.log | head -14
echo "DAY-DONE $DAY"

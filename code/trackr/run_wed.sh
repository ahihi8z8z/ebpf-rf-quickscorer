#!/usr/bin/env bash
# Track-R offline evaluation of Hara's shipped DT/NN on CIC-IDS2017 Wednesday (server3).
set -euo pipefail
cd "$(dirname "$0")"
PCAP=${PCAP:-$HOME/ebpf/data/cicids2017/wed.pcap}
CSV=${CSV:-"$HOME/ebpf/data/cicids2017/TrafficLabelling /Wednesday-workingHours.pcap_ISCX.csv"}
mkdir -p out
run() { ./hara_ref "$PCAP" "out/wed_$1" "${@:2}" 2> "out/wed_$1.log"; cat "out/wed_$1.log"; }
run dir_ns   --key dir   --iat-div 1
python3 label_packets.py out/wed_dir_ns.meta out/wed.lab.npy "$CSV" > out/wed_label.log
cat out/wed_label.log
run dir_ns_lru1024   --key dir   --iat-div 1 --lru 1024 &
run bidir_ns         --key bidir --iat-div 1 &
run bidir_us         --key bidir --iat-div 1000 &
run dir_us           --key dir   --iat-div 1000 &
run bidir_ns_lru1024 --key bidir --iat-div 1 --lru 1024 &
wait
rm -f out/wed_*_*.meta.keep
for f in out/wed_*.meta; do [ "$f" = out/wed_dir_ns.meta ] || rm -f "$f"; done
echo done

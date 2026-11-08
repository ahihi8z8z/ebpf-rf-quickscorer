#!/usr/bin/env bash
# TG: blast UDP from data0 toward the DUT with in-kernel pktgen (multi-thread, one per queue).
# usage: sudo pktgen_tx.sh [seconds=10] [pkt_size=64] [threads=4] [flows=1024] [dst_mac=DUT data0]
set -euo pipefail
DUR=${1:-10}; SIZE=${2:-64}; THREADS=${3:-4}; FLOWS=${4:-1024}
DEV=data0
DST_MAC=${5:-52:54:00:51:a0:51}
SRC_IP=10.50.0.2; DST_IP=10.51.0.2
modprobe pktgen
pg() { echo "$2" > "/proc/net/pktgen/$1"; }
# pgctrl starts every configured generator, including devices left by a prior
# run with more threads. Reset all threads before configuring this run.
pg pgctrl "stop"
for control in /proc/net/pktgen/kpktgend_*; do
  [ -f "$control" ] || continue
  echo rem_device_all > "$control"
done
for ((t=0; t<THREADS; t++)); do
  d="$DEV@$t"
  pg kpktgend_$t "add_device $d"
  pg "$d" "count 0"; pg "$d" "pkt_size $SIZE"; pg "$d" "delay 0"
  pg "$d" "queue_map_min $t"; pg "$d" "queue_map_max $t"
  pg "$d" "dst_mac $DST_MAC"; pg "$d" "src_min $SRC_IP"; pg "$d" "src_max $SRC_IP"
  pg "$d" "dst $DST_IP"
  pg "$d" "udp_src_min 1024"; pg "$d" "udp_src_max $((1024 + FLOWS - 1))"
  pg "$d" "udp_dst_min 9"; pg "$d" "udp_dst_max 9"
  pg "$d" "flag UDPSRC_RND"; pg "$d" "flows $FLOWS"; pg "$d" "flowlen 8"
  pg "$d" "burst 32"
done
( sleep "$DUR"; echo stop > /proc/net/pktgen/pgctrl ) &
echo start > /proc/net/pktgen/pgctrl || true
wait
tot=0
for ((t=0; t<THREADS; t++)); do
  sent=$(grep -oP 'pkts-sofar: \K\d+' "/proc/net/pktgen/$DEV@$t")
  r=$((sent / DUR))
  echo "thread $t: sent=$sent pps=$r"; tot=$((tot + r))
done
echo "TOTAL tx pps=$tot"

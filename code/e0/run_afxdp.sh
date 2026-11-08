#!/usr/bin/env bash
# usage: run_afxdp.sh <NN|DT|RF> [extra xsknf opts e.g. -p] [secs=10]
M=${1:?}; X=${2:-}; SECS=${3:-10}
DUT=haipt@192.168.101.51; TG=haipt@192.168.101.52; OUT=/tmp/e0/afxdp_${M}${X// /}
ssh $DUT "mkdir -p $OUT; setsid nohup bash -c 'cd ~/ebpf-classifier/xsknf && sudo timeout -s INT $((SECS+8)) taskset -c ${CPU:-1} stdbuf -oL ./examples/mlids/${BIN:-mlids} -i data0:c -M COMBINED $X -w 1 -- -m $M' > $OUT/app.log 2>&1 < /dev/null &"
sleep 6
MODE=$(ssh $DUT "sudo bpftool net show dev data0 | grep -oE '(driver|generic) id' | head -1")
D0=$(ssh $DUT "cat /sys/class/net/data0/statistics/rx_packets")
TX=$(ssh $TG "sudo bash pktgen_tx.sh $SECS 64 4 1024 | tail -1")
D1=$(ssh $DUT "cat /sys/class/net/data0/statistics/rx_packets")
sleep 6
echo "AF_XDP m=$M opts='$X' attach=$MODE | $TX | dut_rx_pps=$(( (D1-D0)/SECS ))"
ssh $DUT "grep -A1 TOTAL $OUT/app.log | grep '^rx' | awk '{print \$2}' | sort -n | tail -3 | tr '\n' ' ' | sed 's/^/  app_rx_pps(top3)= /'; echo; grep -iE 'error|fail' $OUT/app.log | head -3; ip link show data0 | grep -q xdp && echo WARN_still_attached"

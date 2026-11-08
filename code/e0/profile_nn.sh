#!/usr/bin/env bash
# From server3: profile a Hara NN variant on qs-dut CPU0 (data0 RX, 1 queue) under saturating pktgen.
# usage: [VARIANT=clean_drop] [MODEL=nn] profile_nn.sh [secs=8]
set -euo pipefail
SECS=${1:-8}; VARIANT=${VARIANT:-clean_drop}; MODEL=${MODEL:-nn}
DUT=haipt@192.168.101.51; TG=haipt@192.168.101.52
case $MODEL in nn) D=nn-filter; S=nn_filter_xdp.py ;; dt) D=dt-filter; S=dt_filter_xdp.py ;; filter) D=filter; S=filter_xdp.py ;; esac
OUT=/tmp/e0/prof/$VARIANT-$MODEL
ssh $DUT "sudo sysctl -qw net.core.bpf_jit_kallsyms=1 kernel.perf_event_paranoid=-1; sudo ethtool -L data0 combined 1 >/dev/null; \
  rm -rf $OUT; mkdir -p $OUT; setsid nohup bash -c 'cd ~/e0/variants/$VARIANT/$D && sudo timeout -s INT $((SECS+30)) python3 -u $S data0 $OUT -D' > $OUT/app.log 2>&1 < /dev/null &"
sleep 6
ssh $TG "setsid nohup sudo bash pktgen_tx.sh $((SECS+6)) 64 4 1024 > /tmp/pg.log 2>&1 < /dev/null &"
sleep 3
ssh $DUT "cd $OUT && sudo perf record -q -e cycles -C 0 -o perf.data -- sleep $SECS 2>/dev/null; \
  sudo perf stat -e cycles,instructions,cache-misses,branch-misses -C 0 -x, -o stat.csv -- sleep 2 2>/dev/null; \
  sudo chown \$USER perf.data stat.csv; \
  perf report -i perf.data --no-children --sort sym --stdio --percent-limit 0.7 2>/dev/null | grep -v '^#' | grep -v '^\$' | head -40; \
  echo '--- by DSO'; perf report -i perf.data --no-children --sort dso --stdio 2>/dev/null | grep -v '^#' | grep -v '^\$' | head -8; \
  echo '--- perf stat CPU0 (2s)'; cat stat.csv | grep -v '^#'"
sleep $((SECS+20))
ssh $DUT "ip link show data0 | grep -q xdp && echo WARN_still_attached || true"

#!/usr/bin/env bash
# E0 run (from server3): load a Hara in-kernel classifier variant on qs-dut:data0, offer pktgen load
# from qs-tg; record attach mode, program-reported inference rate, sink pps, per-program BPF stats
# (run_cnt / run_time_ns -> ns per invocation; needs kernel.bpf_stats_enabled=1), sizes, class histogram.
#
# usage: [VARIANT=faithful|hist|clean_pass|clean_drop] run_smoke.sh <none|xdpdrop|filter|dt|nn> \
#          [mode_flag=-D] [secs=10] [pkt_size=64] [flows=1024] [threads=4]
set -euo pipefail
M=${1:?}; FLAG=${2:--D}; SECS=${3:-10}; SIZE=${4:-64}; FLOWS=${5:-1024}; THR=${6:-4}
VARIANT=${VARIANT:-faithful}
DUT=haipt@192.168.101.51; TG=haipt@192.168.101.52
if [ "$VARIANT" = faithful ]; then REPO='~/ebpf-classifier'; else REPO="~/e0/variants/$VARIANT"; fi
OUT=/tmp/e0/$VARIANT/$M$FLAG
T=$((SECS+25))

case $M in
  dt)      APP="cd $REPO/dt-filter && sudo timeout -s INT $T python3 -u dt_filter_xdp.py data0 $OUT $FLAG" ;;
  nn)      APP="cd $REPO/nn-filter && sudo timeout -s INT $T python3 -u nn_filter_xdp.py data0 $OUT $FLAG" ;;
  filter)  APP="cd $REPO/filter && sudo timeout -s INT $T python3 -u filter_xdp.py data0 $OUT $FLAG" ;;
  xdpdrop) APP="sudo timeout -s INT $T xdp-bench drop -m native -i 1 data0" ;;
  none)    APP="sleep $T" ;;
  *) echo "bad model $M"; exit 2 ;;
esac

# per-program stats: "name run_cnt run_time_ns xlated jited" for every xdp program
PSTATS='sudo bpftool -j prog show | python3 -c "import json,sys
for p in json.load(sys.stdin):
  if p.get(\"type\") in (\"xdp\",\"ext\"): print(p.get(\"name\",\"?\"), p.get(\"run_cnt\",0), p.get(\"run_time_ns\",0), p.get(\"bytes_xlated\",0), p.get(\"bytes_jited\",0))"'

ssh $DUT "rm -rf $OUT; mkdir -p $OUT; sudo sh -c 'echo > /sys/kernel/debug/tracing/trace'; setsid nohup bash -c \"$APP\" > $OUT/app.log 2>&1 < /dev/null &"
sleep 6
MODE=$(ssh $DUT "ip -d link show data0 | grep -oE 'xdp(generic|offload)?' | head -1 || true")
S0=$(ssh $DUT "$PSTATS")
R0=$(ssh $TG "sudo ip netns exec rx cat /sys/class/net/data1/statistics/rx_packets")
D0=$(ssh $DUT "cat /sys/class/net/data0/statistics/rx_packets")
if [ "${TRAFFIC:-pktgen}" = replay ]; then
  TX=$(ssh $TG "sudo tcpreplay -q -i data0 --pps=${PPS:-5000} ${PCAP:-eq_trace.pcap} 2>&1 | grep -oE 'Actual: [0-9]+ packets' | sed 's/Actual: /replayed=/'")
else
  TX=$(ssh $TG "sudo bash pktgen_tx.sh $SECS $SIZE $THR $FLOWS | tail -1")
fi
R1=$(ssh $TG "sudo ip netns exec rx cat /sys/class/net/data1/statistics/rx_packets")
D1=$(ssh $DUT "cat /sys/class/net/data0/statistics/rx_packets")
S1=$(ssh $DUT "$PSTATS")
sleep $((T - SECS - 6 + 2))
TRACE=$(ssh $DUT "sudo cat /sys/kernel/debug/tracing/trace | grep -vc '^#'" || true)
INF=$(ssh $DUT "{ grep -E '^[0-9]{4}-' $OUT/app.log | awk '{print \$NF}'; cat $OUT/rxpps.log 2>/dev/null; } | sort -n | tail -3 | tr '\n' ' '" || true)
HIST=$(ssh $DUT "awk '\$2>0{printf \"%s:%s \", \$1, \$2}' $OUT/cls_hist.txt 2>/dev/null" || true)
# per-program ns/invocation over the traffic window (match by name, exclude programs absent in S0)
PROG=$(python3 - "$S0" "$S1" <<'EOF'
import sys
a={l.split()[0]:list(map(int,l.split()[1:])) for l in sys.argv[1].splitlines() if l.strip()}
out=[]
for l in sys.argv[2].splitlines():
    if not l.strip(): continue
    n,*v=l.split(); v=list(map(int,v))
    if n in a and v[0]>a[n][0]:
        dc=v[0]-a[n][0]; dt=v[1]-a[n][1]
        out.append(f"{n}:{dt/dc:.1f}ns/run,cnt={dc},xl={v[2]},jit={v[3]}")
print(" ".join(out) or "-")
EOF
)
echo "variant=$VARIANT model=$M flag=$FLAG attach=${MODE:-none} | $TX | dut_rx_pps=$(( (D1-D0)/SECS )) sink_pps=$(( (R1-R0)/SECS )) | inf_per_s(top3)=[$INF] | prog=[$PROG] | hist=[$HIST] trace=$TRACE"
ssh $DUT "ip link show data0 | grep -q xdp && echo 'WARN: XDP still attached' || true"

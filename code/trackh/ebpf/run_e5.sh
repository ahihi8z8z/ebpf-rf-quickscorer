#!/bin/bash
# E5 v2 (pcapfix replay, exact offline reference, parallel top4 load); then releases run_e4b.sh.
cd "$(dirname "$0")/.."
PY=${PY:-python3}
for ds in d1 d2 d3; do
  echo "[$(date)] E5 $ds"
  $PY -I ebpf/e5_run.py run $ds out/e5/${ds}_variants.json out/e5/xdp_performance.csv top,top4,50000 2>&1
done
echo "[$(date)] ALL-AFTER-E2-DONE" | tee -a out/after_e2.log

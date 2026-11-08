#!/bin/bash
# E2 rerun, G-RF-x family only (all other rows already in deployability_raw.csv are skipped by e2_sweep).
cd "$(dirname "$0")/.."
PY=${PY:-python3}
cp out/e2/deployability_raw.csv out/e2/deployability_raw.before_grfx.csv
echo "[$(date)] E2x start"
for ds in d1 d2 d3; do
  $PY -I ebpf/e2_sweep.py out/$ds.npz out/e1/models out/e2/work out/e2/deployability_raw.csv $(cat out/e2/e2x_$ds.txt) > out/e2/${ds}_grfx.log 2>&1
  echo "[$(date)] $ds done"
done
$PY -I ebpf/e2_matrix.py out/e2/deployability_raw.csv out/e2/deployability_matrix.csv > out/e2/matrix.md 2>&1
echo "[$(date)] E2x-DONE"

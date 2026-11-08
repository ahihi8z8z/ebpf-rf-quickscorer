#!/bin/bash
# E4b mechanism study; waits for the E1-C/E4/E5 chain so the DUT is idle.
cd "$(dirname "$0")/.."
PY=${PY:-python3}
until grep -q ALL-AFTER-E2-DONE out/after_e2.log 2>/dev/null; do sleep 300; done
echo "[$(date)] E4b start"
M=out/e1/models
$PY -I ebpf/e4b_mech.py out/e4b/mech.csv $M/d1_multiclass_RF_T64L64_s0.npz $M/d1_binary_RF_T64L64_s0.npz \
   $M/d1_multiclass_RF_T64D6_s0.npz $M/d1_multiclass_RF_T128L64_s0.npz $M/d3_binary_RF_T64L64_s0.npz \
   $M/d3_multiclass_RF_T128L64_s0.npz $M/d2_multiclass_RF_T64L64_s0.npz 2>&1
echo "[$(date)] E4b-DONE"

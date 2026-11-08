#!/bin/bash
# E4b follow-up (timing-regime cross-check + JIT images); waits for e4b_mech to finish.
cd "$(dirname "$0")/.."
PY=${PY:-python3}
until grep -q E4b-DONE out/e4b/run.log 2>/dev/null; do sleep 120; done
echo "[$(date)] E4b-post start"
M=out/e1/models
$PY -I ebpf/e4b_post.py out/e4b/regime.csv $M/d1_multiclass_RF_T64L64_s0.npz $M/d1_binary_RF_T64L64_s0.npz \
   $M/d1_multiclass_RF_T64D6_s0.npz $M/d1_multiclass_RF_T128L64_s0.npz $M/d3_binary_RF_T64L64_s0.npz \
   $M/d3_multiclass_RF_T128L64_s0.npz $M/d2_multiclass_RF_T64L64_s0.npz 2>&1
echo "[$(date)] E4b-post-DONE"

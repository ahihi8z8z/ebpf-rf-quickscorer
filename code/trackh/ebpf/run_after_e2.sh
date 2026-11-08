#!/bin/bash
# Runs after the E2 sweep chain: E2 matrix -> E1 C bench -> E4 -> E5 (DUT used by one stage at a time).
cd "$(dirname "$0")/.."
PY=${PY:-python3}
until grep -q E2-ALL-DONE out/e2/d2.log 2>/dev/null; do sleep 120; done
echo "[$(date)] E2 done"
# E2b: leaf-limited RFs (QuickScorer regime, <=64 leaves/tree = one bitvector word), seed 0, L64 x T{64..512}
until grep -q LEAF-TRAIN-DONE out/e1/d3_leaf.log 2>/dev/null; do sleep 120; done
for ds in d1 d3 d2; do
  echo "[$(date)] E2-leaf $ds"
  $PY -I ebpf/e2_sweep.py out/$ds.npz out/e1/models out/e2/work out/e2/deployability_raw.csv "${ds}_*_RF_T*L64_s0.npz" > out/e2/${ds}_leaf.log 2>&1
done
$PY -I ebpf/e2_matrix.py out/e2/deployability_raw.csv out/e2/deployability_matrix.csv > out/e2/matrix.md 2>&1
mkdir -p out/e4
for ds in d1 d2 d3; do
  echo "[$(date)] E1-C $ds"; $PY -I ebpf/e1_cbench.py out/$ds.npz out/e1/models out/e1/cwork out/e1/cbench.csv $ds 2>&1
done
for ds in d1 d2 d3; do
  echo "[$(date)] E4 $ds"; $PY -I ebpf/e4_bench.py out/$ds.npz out/e2/deployability_raw.csv out/e1/model_quality.csv out/e1/models out/e4/work out/e4/inference_bench.csv $ds 2>&1
done
for ds in d1 d2 d3; do
  echo "[$(date)] E5 $ds"
  $PY -I ebpf/e5_variants.py $ds out/e1/model_quality.csv out/e2/deployability_raw.csv out/e1/models out/e5/${ds}_variants.json 2>&1
  $PY -I ebpf/e5_run.py run $ds out/e5/${ds}_variants.json out/e5/xdp_performance.csv top,200000 2>&1
done
echo "[$(date)] ALL-AFTER-E2-DONE"

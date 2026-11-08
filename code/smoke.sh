#!/usr/bin/env bash
# Offline smoke test, no testbed needed. Uses the shipped sample model and 2 000 test vectors.
#   1. generate every runtime from one RF (D1 multiclass, T64, <=64 leaves)
#   2. C benchmark (gcc): tree walk vs QuickScorer, bit-exact check against the integer reference
#   3. compile the eBPF programs (clang -target bpf)
#   4. optional, needs root + libbpf: load each program (verifier) and run it with BPF_PROG_TEST_RUN
# Usage:  PY=python3 bash code/smoke.sh [--load]
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PY=${PY:-python3}
E=$ROOT/code/trackh/ebpf
W=${WORK:-$ROOT/work/smoke}
M=$ROOT/sample/d1_multiclass_RF_T64L64_s0.npz
mkdir -p "$W"

echo "== 1. codegen -> $W"
"$PY" -I "$E/codegen.py" "$M" "$W" --grf-k 64 --grf-k 4 --grfx-k 64 --qs-g 1 --qs-g 2 --rfw-g 4 --null-g 1

echo "== 2. C benchmark (walk / qs / qs_bpf / qs_vol), cold regime, 3 passes"
cp "$ROOT/sample/tv2k.X.i32" "$W/tv.X.i32"; cp "$ROOT/sample/tv2k.pred.u8" "$W/tv.pred.u8"
gcc -O2 -march=native -I"$W" -I"$E" "$E/rfm.c" -o "$W/rfm"
(cd "$W" && ./rfm tv.X.i32 tv.pred.u8 3 | tail -1)

echo "== 3. compile eBPF programs"
for c in "$W"/*.bpf.c; do
  clang -O2 -g -target bpf -I"$W" -c "$c" -o "${c%.c}.o" && echo "  ok $(basename "${c%.c}.o")"
done

if [[ "${1:-}" == "--load" ]]; then
  echo "== 4. verifier load + BPF_PROG_TEST_RUN (root)"
  gcc -O2 -I"$E" -o "$W/bench" "$E/bench.c" -lbpf
  for o in "$W"/*.bpf.o; do
    printf '  %-16s ' "$(basename "$o")"
    sudo "$W/bench" "$o" "$W/tv.X.i32" "$W/tv.pred.u8" 2000 50 2>/dev/null | tail -1 || echo "load failed"
  done
fi

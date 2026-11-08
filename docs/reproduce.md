# Reproducing the experiments

All commands run from the repository root unless stated otherwise. `PY` is a Python 3.12 with numpy, pandas and
scikit-learn (we used a conda env; run scripts with `-I`).

## 0. What can be reproduced without the testbed

| Level | Needs | What you get |
|---|---|---|
| **A. Read** | nothing | every table in `SUMMARY.md` / `docs/pilot_report.md` is backed by a CSV in `results/` |
| **B. Smoke test** | gcc, clang ≥ 14, numpy | `bash code/smoke.sh`: code generation of all runtimes from the shipped RF, C benchmark walk vs QuickScorer (bit-exact), eBPF compile |
| **C. Verifier + isolated inference** | any Linux ≥ 6.1 with root and libbpf | `bash code/smoke.sh --load`: loads every program and runs it with `BPF_PROG_TEST_RUN`. Reproduces the key E2 effect on one model: `grf_k64` fails with E2BIG at 1 000 001 processed insns, `grfx_k64` loads with ~32 k |
| **D. Full E1–E4b** | datasets (~150 GB of pcaps), a root Linux box | dataset build, training, E2 sweep, E4/E4b |
| **E. E5** | 2 hosts or VMs with a back-to-back link, native XDP | end-to-end replay |

Expected output of B on an x86 server (D1 multiclass T64 ≤ 64 leaves, 2 000 rows):
`walk_ns ≈ 3.7 µs, qs_ns ≈ 3.4 µs, all *_mismatch = 0` (QS slightly faster than the walk in C, as in E4b).
Expected output of C: every program `mismatch: 0` except `null_g1` (no model) and `grf_k64` (not loadable).

## 1. Datasets (Track-H)

| ID | Source | Fetch |
|---|---|---|
| D1 CIC-IDS2017 | 5 day pcaps + `TrafficLabelling` CSVs; HF mirror `bencorn/CICIDS2017` (SHA-256 in `results/trackr/dataset_sha256.txt`) | manual / `huggingface-cli` |
| D2 UNSW-NB15 | official SharePoint pcaps (80 files) + `UNSW-NB15_[1-4].csv` | `PY -I code/data/fetch.py code/data/unsw/list.tsv 4` (resumable; slow) |
| D3 CICIoT2023 | HF mirror `bencorn/CIC-IoT-2023`, pinned subset of 39 files | `PY -I code/data/fetch.py code/data/ciciot/list.tsv 4` |

`list.tsv` rows are `url  dest  size  sha256`; `list.tsv.log` records the SHA-256 we obtained. Destination paths are
relative to the repository root (`data/...`).

Pipeline per dataset (frozen protocol, `docs/dataset_protocol.md`):

```bash
cd code/trackh
gcc -O2 -o flowfeat flowfeat.c                        # online feature schema v1 (N = 8, 17 int features)
./flowfeat [--n 8] [--timeout-s 120] <out_prefix> <capture>...   # -> <prefix>.flows / .trig
PY -I label_flows.py cic|unsw|ciciot <prefix> ...      # flow labels (see docstring)
PY -I ciciot_hosts.py out/ciciot/*.flows               # D3 only: attacker IPs are not published
PY -I make_dataset.py d1|d2|d3 out/d1.npz <prefix>...  # split = 300 s (D1/D2) / 60 s (D3) time blocks, 3:1:1
PY -I dataset_audit.py out/d1.npz out/d1_audit.json <prefix>...
```
Validation of the extractor: `flowfeat_ref.py` (independent Python implementation) must agree exactly
(`results/flowfeat_validation/compare.txt`).

## 2. E1: model quality

```bash
OMP_NUM_THREADS=8 PY -I code/trackh/train_e1.py out/d1.npz out/e1     # DT, NN 16x16 int8, RF grid, 3 seeds
PY -I code/trackh/train_e1.py out/d1.npz out/e1 --rf-deep              # RFdeep extension (T16-64 x D10/12); --rf-leaf: RFleaf (<= 64 leaves)
PY -I code/trackh/e1_summary.py out/e1/model_quality.csv > out/e1/summary.md
PY -I code/trackh/ebpf/e1_cbench.py out/d1.npz out/e1/models out/e1/cwork out/e1/cbench.csv d1   # C cost
```
Result: `results/e1/`. Models are `models/<ds>_<task>_<family>_<cfg>_s<seed>.npz`; one is shipped in `sample/`.

## 3. E2: deployability sweep

```bash
cd code/trackh
QS_DUT=user@host PY -I ebpf/e2_sweep.py out/d1.npz out/e1/models out/e2/work out/e2/deployability_raw.csv 'd1_*_RF_*_s0.npz'
PY -I ebpf/e2_matrix.py out/e2/deployability_raw.csv out/e2/deployability_matrix.csv > out/e2/matrix.md
```
- `e2_sweep.py` generates code locally (`ebpf/codegen.py`), copies it to `QS_DUT` over ssh, and runs `bench`
  there (needs passwordless `sudo -n`). For a single local box use `QS_DUT=localhost`.
- Families and their codegen flags: `--grf-k` (G-RF), `--grfm-k` (G-RF-mem), `--grfx-k` (**G-RF-x, the fixed
  generator**), `--qs-g` (QS-mask / QS-bounds / QS-bpfloop), `--rfw-g` (RF-walk-table / -bpfloop).
- Per model, the grouping parameter is searched by halving from the whole forest down to ≤ 33 stages.
- The exact 65 models of the report: `results/e2/e2x_d{1,2,3}.txt`.
- Runtime: about 5 h for the full grid; the G-RF-x rerun took 4 h.

## 4. E4 / E4b: matched-model cost and mechanism

```bash
PY -I ebpf/e4_bench.py out/d1.npz out/e2/deployability_raw.csv out/e1/model_quality.csv out/e1/models out/e4/work out/e4/inference_bench.csv d1
PY -I ebpf/e4b_mech.py out/e4b/mech.csv out/e1/models/d1_multiclass_RF_T64L64_s0.npz ...   # counters, C + eBPF, ablations
PY -I ebpf/e4b_post.py out/e4b/regime.csv <same models>                                    # cold/warm regimes
PY -I ebpf/e4b_analyze.py                                                                   # -> mechanism.csv / .md
```
- C side: `ebpf/rfm.c` (walk, qs, qs_bpf = verifier-shaped loop, qs_vol = forced load/store; argv[4] = rowrep).
- eBPF side: `ebpf/bench.c` (`bench obj X ref ntime repeat [--perf]`).
- JIT image: `ebpf/jitdump.c` (bpftool on Ubuntu 24.04 has no JIT disassembler); disassemble locally with
  `objdump -D -b binary -mi386:x86-64`.
- The 7 E4b models are listed in `docs/pilot_report.md` §5. Listings for one of them are in `results/e4b/code/`.

`e4b_analyze.py` can be rerun from the shipped CSVs alone (`E4B_DIR=results/e4b PY -I code/trackh/ebpf/e4b_analyze.py`).

## 5. E5: end-to-end XDP

```bash
PY -I ebpf/e5_select.py d1 out/e5/d1_spec.json          # labelled 300 s replay slices
PY -I ebpf/e5_run.py prep d1 out/e5/d1_spec.json        # cut + fix pcaps (e5_pcapfix.py), offline reference
PY -I ebpf/e5_variants.py d1 out/e1/model_quality.csv out/e2/deployability_raw.csv out/e1/models out/e5/d1_variants.json
QS_TG=user@tg PY -I ebpf/e5_run.py run d1 out/e5/d1_variants.json out/e5/xdp_performance.csv
```
- XDP frontend: `ebpf/frontend.h` (+ `fe_collect.c`, `fe_compare.py` for the bit-exactness check against `flowfeat`).
- Specs and variants used: `results/e5/*.json`. The testbed scripts are in `code/testbed/` (libvirt on one host,
  two VMs, two back-to-back virtio links; see `docs/testbed.md`).

## 6. Old xdp-program branches (verifier sweep, §3 of SUMMARY)

The sweep built the user's earlier `random_forest` (map walk) and `quickscore` branches with
T ∈ {10..500} × L ∈ {16, 64} and loaded them with `bpftool -d prog loadall`. The repository itself is not included.
The fix for the RF branch (votes accumulated in map memory) is `code/xdpold/rf_kern_votes_in_map.c`; numbers are in
`results/xdpold/verifier_sweep.txt`.

## 7. E0 / Track-R (Hara et al. 2024 reproduction)

Upstream: https://github.com/oakeshott/ebpf-classifier, pinned at `d2466660` (submodule xsknf `4825b2bd`).
Scripts: `code/e0/` (variants, AF_XDP runs, throughput), `code/trackr/` (per-packet labelling, bit-exact C reference
`hara_ref.c`, metrics). Full description and commands: `docs/hara_reproduction.md`. Summaries: `results/e0/`,
`results/trackr/`.

---

# Pitfalls found during the experiments (read before re-running)

**Verifier**
- **State explosion from scalar tracking is the dominant limit, not code size.**
  - Feature values kept in registers/locals carry range refinements across trees and block pruning.
  - So do vote counters that are compared at the end.
  - Read features through a `volatile` pointer to map memory and accumulate votes in map memory. That turns the cost
    from exponential into linear (~340–550 processed insns per 64-leaf tree).
- Long bounded loops on one path hit `The sequence of 8193 jumps is too complex` (EFAULT) on kernel 6.8, long before 1 M insns.
- A QuickScorer bitvector on the BPF stack never verifies (every slot is tracked); keep it in per-CPU map memory.
- Use `-mcpu=v4` if you want sign-extending loads; the default BPF CPU emits `shl 32; sar 32`.

**Measurement**
- `BPF_PROG_TEST_RUN(.repeat = R)` runs the *same* row R times. The branch predictor learns the path, which favours
  tree walks. Use `repeat = 1` over distinct rows ("cold") for XDP-realistic numbers.
- In a VM the kernel-mode `cycles` counter can read 0. Derive cycles from time and the nominal clock; L1D counters are unreliable.
- Subtract a null chain with the same number of tail-call stages to get model-only cost.
- E2 single-run timings vary ±30 % between variants; use them for "loads / order of magnitude" only.

**Data / replay**
- D1 (CIC-IDS2017) captures contain >1500 B frames from GRO/TSO offload: 99.7 % of DDoS flows. They cannot cross a
  real 1500 B link, so replayed DDoS looks different (`docs/dataset_protocol.md` §7).
- `tcprewrite` 4.4.4 silently rewrites IP total length 40 → 46 in padded 60 B frames. Use `e5_pcapfix.py`, which only rewrites MACs.
- D2 pcaps are Linux SLL; convert to Ethernet before replay.
- D3 attacker IPs are not published; derive them with `ciciot_hosts.py`.
- The UNSW SharePoint download needs a fresh anonymous FedAuth cookie per attempt (`fetch.py` handles it).
- A single tcpreplay reaches ~200 kpps; use several senders with distinct address offsets.

**Testbed**
- DUT and TG vCPUs shared physical cores (SMT siblings), and CPU pinning was not applied. Absolute ns/pps are
  placement-dependent; ratios between runtimes are what the conclusions use.

**Tooling**
- pandas parses the string `null` as NaN: use `keep_default_na=False` when reading the CSVs.
- bpftool on Ubuntu 24.04 cannot disassemble JIT code; use `jitdump.c`.

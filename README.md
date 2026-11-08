# QuickScorer vs. if-else Random Forests in eBPF/XDP: a closed negative result

This repository archives a pilot study (Nov 2026). It asked whether **QuickScorer (QS)**, the branch-free,
bitvector-based tree-ensemble algorithm, lets a Random Forest (RF) run better inside the Linux eBPF/XDP datapath than
a plain code-generated if-else RF. "Better" meant two things: deploying larger forests within the verifier's limits,
or running faster per inference.

**Answer: no. The direction is closed (NO-GO).**

- **Deployability.** A correctly generated if-else RF ("G-RF-x") loads all 65 tested forests, up to 512 trees × 64
  leaves, as **one program without tail calls**. QS has no configuration that only it can deploy.
  - The earlier impression that "QS embeds more trees" came from verifier state explosion in the if-else and map-walk
    code generators: feature values and vote counters kept in registers.
  - It was not a real limit of if-else.
- **Speed.** QS is slower than if-else everywhere: median **12×**, 4.5–20× in the realistic one-row-per-call
  regime, and up to ~1900× for deep trees. QS is also slightly slower than a table-driven tree walk.
- **Why.** QuickScorer's published advantage is IPC: dense, independent memory operations at IPC ≈ 3. eBPF inflates
  its inner loop **2.8×**, from 9 to 25 x86 instructions per bitvector update.
  - Most of the inflation comes from the BPF ISA and its JIT: no scaled addressing, no memory operands, sign
    extension, two-operand form, register pressure, no ctz.
  - Only a small part comes from the verifier.
  - QS also does 3–11× more node work than the if-else, which costs ~5.5 instructions per visited node.
- **End-to-end (XDP replay).** On D3 with a deep model, QS costs ~0.5 ms per inference and drops 15–25 % of packets.
  G-RF and the tree walk are indistinguishable from an empty program.

Start with **[SUMMARY.md](SUMMARY.md)** (Vietnamese, 1 page per experiment). The full report is
**[docs/pilot_report.md](docs/pilot_report.md)** (English).

## Layout

```
SUMMARY.md                  short summary of all results (Vietnamese)
docs/
  experimental_plan.md      pre-registered plan: hypotheses H-model / H-runtime, experiments E0-E5, GO/NO-GO gates
  pilot_report.md           full report: E1-E5, E4b mechanism study, G-RF-x rerun, recommendation
  dataset_protocol.md       frozen feature schema (17 int features at packet 8), labels, splits, leakage audit,
                            D1 offload-frame artefact (sec. 7)
  e1_report.md              E1 model quality in detail
  hara_reproduction.md      E0 / Track-R: audit and reproduction of Hara & Sasabe 2024 (DT/NN in XDP)
  testbed.md                the two-VM testbed (DUT + traffic generator)
  reproduce.md              how to reproduce each experiment, plus a list of pitfalls  <- read before re-running
code/
  smoke.sh                  offline smoke test on the shipped sample model (no testbed needed)
  trackh/                   dataset pipeline (flowfeat.c, label_flows.py, make_dataset.py, train_e1.py, ...)
  trackh/ebpf/              code generators and harnesses: codegen.py (G-RF, G-RF-x, QS, RF-walk, null),
                            bench.c (BPF_PROG_TEST_RUN), rfm.c (C reference/bench), e2_sweep.py, e4*_*.py, e5_*.py,
                            frontend.h (XDP feature extractor), jitdump.c
  e0/, trackr/              Hara reproduction scripts and bit-exact C reference
  testbed/                  libvirt scripts for the testbed
  data/                     dataset fetcher and pinned file lists with SHA-256
  xdpold/                   fix for the old map-walk RF program (votes in map memory)
results/                    summarized results; every table in the docs comes from these files
  e1/ e2/ e4/ e4b/ e5/      per experiment (CSV + markdown tables)
  e0/ trackr/ datasets/ xdpold/ flowfeat_validation/
sample/                     one trained RF (D1 multiclass, 64 trees, <= 64 leaves) + 2 000 test vectors
```

## Quick start (no testbed)

```bash
# needs: gcc, clang (BPF target), python3 with numpy
PY=python3 bash code/smoke.sh            # codegen + C walk-vs-QS benchmark + eBPF compile
PY=python3 bash code/smoke.sh --load     # + verifier load and BPF_PROG_TEST_RUN (root, libbpf, Linux >= 6.1)
```

The `--load` step shows the central E2 effect on one model:
- `grf_k64` (old generator, 64 trees in one program) fails at 1 000 001 processed instructions.
- `grfx_k64` (fixed generator) loads with ~32 k.
- All loaded runtimes are bit-exact against the integer reference.

Re-derive the analysis tables from the shipped CSVs:

```bash
python3 -I code/trackh/ebpf/e2_matrix.py results/e2/deployability_raw.csv /tmp/m.csv > /tmp/matrix.md   # = results/e2/matrix.md
E4B_DIR=<copy of results/e4b> python3 -I code/trackh/ebpf/e4b_analyze.py                                  # = mechanism.csv/.md
```

The full pipeline, with datasets, a root Linux box and two hosts for E5, is described in
[docs/reproduce.md](docs/reproduce.md).

## What is *not* in the repository

- **Datasets and derived feature files** (~150 GB). They are fetched with `code/data/fetch.py` from the pinned lists.
- **Trained models other than the sample, and generated code and objects.** They are regenerated by `train_e1.py`
  and `codegen.py`.
- **Raw logs, per-run work directories, and the invalid E5 v1 run.**
- **Third-party sources**: Hara's `ebpf-classifier`, Galvao's `eBPF-Classification`, and the earlier `xdp-program`
  branches. They are referenced by URL and commit in the docs.

## Environment used

- Hosts: Linux 6.8 (Ubuntu 24.04), clang 18, libbpf 1.3, gcc 13, Python 3.12 (numpy, pandas, scikit-learn).
- DUT: KVM guest with 8 vCPU on a Xeon Silver 4210, virtio-net with native XDP.
- No CPU pinning. Absolute ns are placement-dependent; the conclusions rest on ratios measured on the same host.

# E1: is RF a meaningful alternative to the lightweight NN? (Track-H, D1–D3)

**Status:** 2026-11-04. Model quality is complete for D1–D3. The C inference profile is in §3.

**Sources.**
- Data: `results/e1/model_quality.csv` (one row per model × config × seed × precision) and `results/e1/summary.md`.
- Protocol and data integrity: `dataset_protocol.md`.
- Code: `trackh/train_e1.py`.

**Setup.**
- All models use the same 17 Track-H integer features at packet N = 8 and the same time-block split.
- Models are selected on validation macro-F1. Numbers are **test macro-F1 of the deployable integer model**, as mean ± sd over seeds 0–2.
- Integer inference agrees with float inference on ≥ 0.999 of test rows for every RF and DT. For the NN, agreement is 0.994–0.999, except D3 multiclass at 0.944.

**Grids.**
- The frozen grid follows the plan: DT D∈{4,6,8,10,12}; RF T∈{16,32,64,128,256} × D∈{4,6,8}; NN 17→16→16→C, int8 with 8-bit log-quantised input.
- **RFdeep** is a post-hoc extension, T∈{16,32,64} × D∈{10,12}. It was added after D3 showed that the frozen RF grid (D ≤ 8) loses to DT D12. It is reported separately. Its selection is also on validation only.

## 1. Val-selected operating points

| dataset / task | DT (val-sel.) | NN 16×16 | RF frozen grid (val-sel.) | RFdeep (val-sel.) |
|---|---|---|---|---|
| D1 CIC-IDS2017 / binary | D10: 0.9906 ± 0.0000, 286 nodes | 0.974 ± 0.009 | T128D8: 0.9925 ± 0.0001, 24.9 k nodes | T16D12: 0.9936 ± 0.0012, 9.0 k nodes |
| D1 / multiclass (5 cl.) | D10: 0.879 ± 0.000 | 0.698 ± 0.123 | T256D8: 0.887 ± 0.004, 52.9 k nodes | T64D12: 0.910 ± 0.012 (T32D12: 0.918) |
| D2 UNSW-NB15 / binary | D12: 0.9361 ± 0.0001, 766 nodes | 0.904 ± 0.005 | T128D8: 0.9351 ± 0.0000 | T16D12: 0.9351 ± 0.0003 |
| D2 / multiclass (9 cl.) | D12: **0.631** ± 0.001, 1.3 k nodes | 0.232 ± 0.001 | T128D8: 0.490 ± 0.002 | T32D12: 0.586 ± 0.015 |
| D3 CICIoT2023 / binary | D12: 0.918 ± 0.000, 1.2 k nodes | 0.867 ± 0.019 | T32D8: 0.899 ± 0.006 | T64D12: 0.922 ± 0.001, 73 k nodes |
| D3 / multiclass (8 cl.) | D12: 0.618 ± 0.000, 2.2 k nodes | 0.390 ± 0.029 | T32D8: 0.547 ± 0.004 | T32D12: 0.652 ± 0.007, 78 k nodes |

Per-class F1 values are in `results/e1/summary.md`. Points to note:

- **D1 multiclass.** RF and DT both separate DDoS, DoS and BruteForce; Bot stays hard for both.
- **D2 multiclass.** Analysis F1 = 0 for every model, and DoS F1 ≤ 0.19. RF D≤8 loses Backdoor and Generic, and these are what DT D12 retains.
- **D3 multiclass.** Web F1 ≈ 0–0.12 and BruteForce ≤ 0.45. Their flows are mostly background flows that carry the capture's label (protocol §2).

## 2. Findings

1. **The NN at Hara's capacity (16×16) is the weakest family on every dataset and task.** The gap is 0.02–0.03 macro-F1 in binary and 0.2–0.4 in multiclass. Its seed variance is high: sd 0.12 on D1 multiclass.

   Against a *shallow* DT (D4, Hara's comparison), the result is mixed:

   | multiclass | NN | DT D4 |
   |---|---|---|
   | D1 | 0.698 | 0.598 |
   | D2 | 0.232 | 0.355 |
   | D3 | 0.390 | 0.362 |

   Hara's "NN beats a shallow DT" therefore holds on D1 and D3 but not on D2. Any DT of depth ≥ 8 beats the NN everywhere.

2. **RF versus DT is dataset-dependent and depth-limited, with no RF advantage at equal depth.**
   - **Binary.** All tree models are within 0.002–0.02 of one another. RF adds nothing material over DT D10–D12 on D1 and D2. On D3 binary, the frozen-grid RF is 0.019 *worse* than DT D12; only RFdeep matches DT (+0.004).
   - **Frozen grid, multiclass.** RF D≤8 beats DT only on D1 (+0.008). It loses on D2 (−0.14) and D3 (−0.07), because DT is allowed depth 12 while frozen-grid RF stops at depth 8.
   - **RFdeep, multiclass.** RFdeep beats DT on D1 (+0.03 to +0.04) and D3 (+0.034). It still loses on D2 (−0.045).

3. **Cost of the RF operating points.** The useful RF points have 9–78 k nodes, 30–270× the DT's 0.3–2.2 k. QS tables grow to 0.27–8.5 MB, above the ~4 MB map-value limit at the top. A useful RF is therefore at least an order of magnitude more expensive than DT D10–12 at equal or slightly better quality.

4. **The resp_port shortcut matters for D1 and D2 multiclass.** Without it, the RF T64D8 drops from 0.91 to 0.72 (D1) and from 0.48 to 0.40 (D2). Binary detection is insensitive to it. See protocol §6.

## 2b. Leaf-limited RF (RFleaf: the QuickScorer regime)

**What it is.** A second post-hoc extension, added on 2026-11-04 after E2 on D1 showed QS losing to the tree walk.
- Grid: `max_leaf_nodes` ∈ {32, 64}, unlimited depth, T ∈ {64, 128, 256, 512}, seeds 0–2.
- Selection is on validation only. The frozen-grid selection is unchanged.
- At ≤ 64 leaves, every tree's QS bitvector fits in one 64-bit word (W = 1). This is the regime in which QuickScorer was designed to win.

**Quality.** Test macro-F1 of the val-selected point, mean ± sd over 3 seeds:

| dataset / task | RFleaf (val-sel.) | vs DT (val-sel.) | vs best other RF |
|---|---|---|---|
| D1 binary | T512L64 0.992 (T64L64 also 0.992, 8 k nodes) | +0.001 | = |
| D1 multiclass | T128L64 0.914 ± 0.010; T64L64 0.920 | **+0.035 / +0.041** | ≥ RFdeep (0.909), at 8–16 k nodes |
| D2 binary | 0.935 | −0.001 | = |
| D2 multiclass | T512L64 0.496 | −0.135 | < RFdeep (0.586) |
| D3 binary | T64L64 0.916 | −0.002 | ≈ RFdeep (0.922), at 1/9 of its nodes |
| D3 multiclass | T64L64 0.541 ± 0.016 | −0.077 | < RFdeep (0.652) |

**Reading the table.**
- Quality saturates at T = 64. Larger T only makes inference more expensive.
- On D1, the ≤ 64-leaf RF is the best RF operating point in any grid. So the QS-friendly regime is not an artificial configuration on D1.
- On D2 and D3 multiclass it is clearly worse than DT D12 and RFdeep. Those tasks need deep trees, which is the regime in which QS loses (§3, E2).

## 3. C inference profile (isolated, userspace, one thread, DUT VM)

**Setup.** `code/trackh/ebpf/e1_cbench.py` → `results/e1/cbench.csv`, 210 seed-0 models.
- Each model is run on 20 000 test rows; the reported time is the median of 7 passes.
- Build: `gcc -O2 -march=native`, run on the DUT VM after E2 had finished, so the DUT was not shared.
- Tree walk and QuickScorer read the *same* integer tables.
- Every runtime matches the Python integer reference bit-exactly: **0 mismatches**.

**Per-row cost**

| model | tree walk | QuickScorer | QS / walk (median, range) |
|---|---|---|---|
| DT D4–D12 | 8–37 ns | — | 3.9–36× (QS always slower) |
| RF D4 | — | — | 1.02 (0.38–1.97) |
| RF D6 | — | — | 1.26 (0.55–2.92) |
| RF ≤ 32 leaves | — | — | **0.82** (0.34–2.48) |
| RF ≤ 64 leaves | — | — | 1.07 (0.46–2.95) |
| RF D8 | — | — | 3.5 (1.6–14) |
| RF D10 | — | — | 15 (1.9–41) |
| RF D12 | — | — | 24 (9–251) |
| NN 16×16 int8 | 406–533 ns | — | — |

**QuickScorer in plain C**
- QS beats the walk in 51 of 204 tree models, all with ≤ 64 leaves per tree (D4, D6, L32, L64) and T ≥ 64.
- At T = 256–512 with L32, QS is 2–3× faster (e.g. D1 multiclass T512L32: 10.6 µs vs 27.5 µs).
- This is the published QuickScorer regime, and **the algorithmic advantage is reproduced in plain C**.
- In deep trees (D ≥ 8), QS scans most thresholds and loses by an order of magnitude or more.

**Reading the walk times.** The C tree walk is a generic table walk, so it is not the fastest tree runtime. In eBPF, the code-generated G-RF runs T64 forests in about 1 µs per call (E2/E4).

**DT vs NN cost.** DT inference costs tens of ns, while the int8 NN costs about 0.5 µs: 10–60× more, at lower quality (§2).

## 4. E1 decision (plan §4 E1)

> Continue only if at least two datasets show a defensible RF operating point: useful quality at plausible deployment cost. Record a failure on D3 rather than replacing it.

| dataset | defensible RF point? | reason |
|---|---|---|
| D1 | **yes (weak)** | Multiclass RFdeep T16D12 is +0.034 over DT D10 at 9 k nodes. Binary gain ≤ 0.003. |
| D2 | **no** | DT D12 ≥ every RF on both tasks. |
| D3 | **only with the post-hoc deep extension** | Frozen-grid RF < DT. RFdeep T32D12 is +0.034 multiclass, at 78 k nodes / 8.5 MB QS tables. |

- **Frozen plan grid:** the E1 gate **fails**. Only D1 has an RF point that beats DT.
- **With the documented RFdeep extension:** the gate passes **narrowly** on D1 and D3, and only in multiclass. The cost is 30–70× DT's model size.

**Caveat added 2026-11-08:** D1 quality partly rests on oversize offload frames in the captures; see `dataset_protocol.md` §7 and `pilot_report.md` §4.2.

H-model is therefore **weakly supported at best**. We continue to E2–E5 because the user asked for the full pipeline and because E2–E5 decide H-runtime independently. The paper's motivation must not overstate RF's application relevance.

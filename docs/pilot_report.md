# Pilot report: QuickScorer for RF inference in eBPF/XDP (Track-H, D1–D3)

**Status:** 2026-11-08. All experiments E1–E5 and the E4b mechanism study are complete.

**Recommendation: NO-GO for the QuickScorer paper claim.**
- H-model is weakly supported at best.
- H-runtime is rejected on all three datasets, on deployability (GO-A), on matched-model cost (GO-B) and end-to-end (E5).
- The negative result is kept, together with a measured explanation of *why* the published QuickScorer advantage, which we reproduce in C, does not carry over to eBPF.

**Artifacts:**

| file | contents |
|---|---|
| `dataset_protocol.md` | features, labels, splits, leakage audit; §7 is the offload artefact found in E5 |
| `results/e1/model_quality.csv`, `e1_report.md` | E1 |
| `results/e2/deployability_raw.csv` (2 012 load attempts), `deployability_matrix.csv`, `matrix.md` | E2/E3 |
| `results/e4/inference_bench.csv` | E4 |
| `results/e4b/{mech,regime,mechanism}.csv`, `mechanism.md`, `code/` (BPF xlated, JIT images, gcc objdump) | E4b, the mechanism study |
| `results/e5/xdp_performance.csv` | E5, the v2 replay; the invalid v1 run is not included (raw) |

**Testbed:**
- DUT is the qs-dut VM: 8 vCPU Xeon Silver 4210 at 2.2 GHz, Linux 6.8, virtio-net with 8 queues, native XDP.
- TG is the qs-tg VM: 6 vCPU, tcpreplay 4.4.4.
- CPU pinning was not used (user decision). The DUT was not shared during any timing run.

---

## 1. H-model: is an RF a useful operating point? (E1, `e1_report.md`)

**Setup:** 17 integer features at packet N = 8 and a time-block split. Results are test macro-F1 of the deployed integer model, 3 seeds.

**Findings:**
- **The NN at Hara's capacity (16×16 int8) is the weakest family everywhere.** It trails by 0.02–0.03 in binary and 0.2–0.4 in multiclass. In C it costs 0.4–0.5 µs, 10–60× a DT.
- **RF vs DT is dataset-dependent.**
  - Binary: all tree models are within 0.002–0.02 of each other.
  - Multiclass: an RF beats the val-selected DT only on D1 (+0.03–0.04: RFdeep, and the ≤ 64-leaf RF T64L64 at 0.920) and on D3 with deep trees (RFdeep T32D12 +0.034, at 78 k nodes). On D2, DT D12 beats every RF.
- **The frozen-grid E1 gate fails.** Only D1 has an RF point above DT. It passes narrowly only with the post-hoc RFdeep/RFleaf extensions.
- **New caveat from E5 (protocol §7).** The D1 captures contain oversize offload frames: 99.7 % of DDoS flows have `len_max` > 1500. Part of D1's RF/DT quality rests on this artefact and cannot be reached on a real 1500-byte link.

**Verdict:** H-model is **weakly supported at best**. RF and DT both beat the NN, but an RF adds little over a DT except on D1 multiclass (artefact-affected) and on D3 multiclass with very large forests.

## 2. Deployability (E2/E3, GO-A)

**What was run:**
- 65 RF configurations: T 16–512, depth 4–12 or ≤ 64 leaves, binary and multiclass, D1–D3. This gives 2 012 compile/verify/load attempts.
- 7 runtime families, each tuned over its grouping parameter:
  - G-RF and G-RF-mem: code-generated if/else, tail-call stages;
  - QS-mask, QS-bounds and QS-bpfloop: multi-stage QuickScorer, G ∈ {1, 2, 4, 8};
  - RF-walk-table and RF-walk-bpfloop: table-driven tree walk, tail-call stages.
- Every loaded variant was checked bit-exactly against the integer reference on 20 000 rows.

| | configurations loaded (of 65) |
|---|---|
| any QS variant | 65 |
| any RF-walk variant | 65 |
| any G-RF variant | 52 (65 with the fixed generator G-RF-x, §2.1) |

**The 13 configurations that the original G-RF generator cannot load** (all load with G-RF-x, §2.1):
- They fail on the 33-tail-call cap or on E2BIG (1 M processed instructions) at T ≥ 256.
- In **all 13**, RF-walk also loads and is **as fast as or faster than** the best QS: E4 ratio QS/walk 0.95–3.5.
- **None of the 13 has quality value.** RFleaf quality saturates at T = 64, and T256D6/D8 is not better than T64.

**QS-only coverage (QS loads, neither G-RF nor walk does): 0 configurations.**

**Verdict:** **GO-A fails.** Multi-stage QS creates no deployability that a tuned tree-walk baseline lacks. The apparent limit of G-RF, its tail-call and instruction budget, is already lifted by a data-driven walk. It also turned out to be a code-generator artefact: G-RF-x loads all 65 configurations in a single program each (§2.1).

### 2.1 Update 2026-11-08: the G-RF limit above was an artefact of our code generator

**What was wrong.** The E2 G-RF generator loads the 17 features into local variables once per program. After each comparison the verifier narrows the range of that variable on each branch. So at the start of the next tree every path carries different feature ranges, the verifier cannot prune, and the explored paths multiply across trees. A stage of only 8 D4 trees already cost 57 843 processed instructions, about 480 per node.

**The fix** (`code/trackh/ebpf/grf_mapx.py`, same trees, same code otherwise): read the feature from the per-CPU scratch (`volatile`) at every comparison. No range state crosses a tree boundary, so verification becomes about linear in the number of nodes.

| model (previously "G-RF ✗") | variant | programs | verified insns | mismatches | ns / inference | E2 best QS | E2 best walk |
|---|---|---|---|---|---|---|---|
| D1 binary T256L64 | old generator, 1 / 4 / 8 programs | 1–8 | > 1 000 000 (E2BIG) | — | — | 20.5 µs | 16.0 µs |
| D1 binary T256L64 | fixed, 1 program | **1 (no tail call)** | 86 724 | 0 | **5.2 µs** | 20.5 µs | 16.0 µs |
| D1 binary T512L64 | fixed, 1 program | 1 | 175 912 | 0 | **9.4 µs** | 45.4 µs | 41.7 µs |
| D1 multiclass T512L64 | fixed, 4 programs | 4 | 184 354 | 0 | **8.9 µs** | 47.3 µs | 33.9 µs |
| D1 multiclass T256D8 | fixed, 2 programs | 2 | 144 895 | 0 | **5.7 µs** | 51.8 µs | 18.0 µs |

(One timing run each, warm harness: `repeat = 50`, 2 000 rows.)

**Consequences:**
- About 340 processed instructions per tree of 64 leaves. **One program can hold about 2 500–3 000 such trees** within the 1 M budget (extrapolated, not tested), and a 33-program tail-call chain about 30× more.
- QS therefore has **no deployability advantage over a correctly generated if-else RF at all**. GO-A fails more clearly than stated above.

**Full E2 rerun with the fixed generator.**
- **Setup:** new family `G-RF-x` (`codegen.py --grfx-k`), the same 65 E2 models and the same harness as §2. Stages started at K = T, i.e. the whole forest in one program, then K was halved twice more. 195 variants.
- **Data:** `results/e2/deployability_raw.csv` (it includes the pre-rerun rows; the pre-rerun copy itself is not included), `deployability_matrix.csv` and `matrix.md`.

| | QS (any) | walk (any) | old G-RF / G-RF-mem | **G-RF-x** |
|---|---|---|---|---|
| configurations deployable (of 65) | 65 | 65 | 52 | **65** |
| of which in **one program, no tail call** | — | — | — | **65** |
| load failures / mismatching variants | | | | **0 / 0** of 195 |

**Results:**
- **Every model, including all 13 T ≥ 256 configurations that the old G-RF could not load, verifies as a single program.**
- The largest program is D3 multiclass T256D8 with 424 068 verified instructions. All T512L64 programs need 176 k–345 k, so the 1 M budget is not binding anywhere in E2.
- **Speed, best variant per family:**
  - G-RF-x / old G-RF: median **0.71** (range 0.40–1.33). G-RF-x is faster on 40 of the 52 models both can load, so per-comparison loads cost nothing measurable.
  - QS / G-RF-x: median **12.4×** (range 2.5–1 919×). The walk / G-RF-x: median 4.9× (range 1.9–9.6×).
  - G-RF-x is the fastest family on 53 of 65 models. On the other 12, old G-RF is at most 1.33× faster, which is within the harness noise.
- **On the 13 previously ✗ configurations:** G-RF-x takes 2.2–8.9 µs, against 14.6–59 µs for QS (4.7–16× slower) and 10.9–42 µs for the walk.
- **Caveat:** the timings are E2's warm harness and single runs, so variant-to-variant noise is about ±30 %. Read the result as "loads, and roughly how many µs", not as a fine ranking.
- **Consequence for GO-A:** the "QS/walk-only" set of §2 is empty. A plain if-else RF, generated so that the verifier can prune, deploys everything QS deploys, without tail calls, and is an order of magnitude faster.
- E4/E5 were run with the old G-RF on models it could load. Since G-RF-x is equal or faster there, their verdicts stand unchanged.

## 3. Matched-model inference cost (E4, GO-B)

**Method:**
- BPF_PROG_TEST_RUN on the same RF and the same 20 000 rows.
- 5 interleaved passes, with CI95 over passes.
- A null tail-call chain is measured for every stage count: 168 ns + 12.3 ns per stage.

**Fastest QS variant vs fastest baseline, per configuration (77 models incl. DT/NN reference rows):**

| comparison | configs | QS slower in | QS/baseline median | range |
|---|---|---|---|---|
| QS vs G-RF | 52 | **52** | **12.0×** | 2.9–1442× |
| … ≤ 64-leaf regime (D4, D6, L32, L64) | 26 | 26 | 6.2× | 2.9–19× |
| QS vs RF-walk | 65 | 64 | 2.6× | 0.95–305× |
| … ≤ 64-leaf regime | 37 | 36 | 1.6× | 0.95–3.5× |

- The single nominal QS win, D1 T256D4 at 0.95, has overlapping CIs. **No QS win is CI-separated.**
- In deep trees (D ≥ 10), QS needs W > 1 words per tree. It costs 30–945 µs per inference, against 1–8 µs for G-RF and walk.

**Harness caveat (found in E4b, §5.1).** BPF_PROG_TEST_RUN repeats each row, which favours the branchy walk. In the realistic one-new-row-per-call regime, QS/walk in the ≤ 64-leaf regime is 1.04–1.21 rather than 1.17–1.97, and QS/G-RF is 4.5–20×. QS still never wins.

**Verdict:** **GO-B fails.** QS is never better on matched-model cost than the tuned baselines.

## 4. End-to-end XDP (E5)

**Setup:**
- One native-XDP frontend computes the 17 features in a per-flow map. At the 8th packet of a flow it runs the classifier through tail calls and emits a 96-byte ringbuf event.
- Models: the val-selected DT, the NN, a null chain, and the best E2-swept RF in three runtimes (G-RF, QS, walk). The RF is the same model in all three.
- Labelled replay: 5 × 300 s capture slices per dataset, with an offline reference computed on exactly the replayed packets.
- Load: one tcpreplay at top speed (~160–270 kpps); four parallel senders with distinct /8 address offsets (~400–430 kpps); and 50 kpps.

### 4.1 Fidelity

| | D1 | D2 | D3 |
|---|---|---|---|
| events matched to offline flows | 0.9999 | 0.9991 | 0.9991 |
| non-timing features bit-exact | 1.0000 | 0.9998–1.0000 | 0.9999 |
| class agreement online vs offline (trees) | 0.982–0.9995 | 0.996–0.9996 | 0.998–0.9987 |
| timing features, median relative error | 0.7 % | 2 % | 4 % |

- Online macro-F1 matches offline-on-the-same-flows to within 0.004 on D1 and D2.
- D3 loses 0.02–0.04, from the replay's timing features.

### 4.2 Labelled-replay quality

| model | D1 | D2 | D3 |
|---|---|---|---|
| DT | 0.41 | 0.89 | 0.68 |
| NN | 0.42 | 0.86 | 0.62 |
| RF in all three runtimes (identical predictions) | 0.47 | 0.88–0.89 | 0.68–0.69 |

The D1 numbers are low because DDoS flows lose their oversize frames on a real link (protocol §7). The same flows scored 0.99 on capture features.

### 4.3 Load

**Inference trigger rate:** 0.9 % (D2) to 4.3 % (D3) of packets.

**D1/D2 loss is model-independent.** At the 4-sender load, D1 loses 2–7 % and D2 18 % of packets for **every** program, including the null chain. That is a virtio/receive limit of the testbed, not the classifier. DUT CPU is 300–480 ns/packet for all programs.

**D3 (RF T64D12, the val-selected RF with deep trees):**

| runtime | CPU ns/pkt (top / top4) | delivered share (top / top4) |
|---|---|---|
| null chain | 220 / 236 | 1.000 / 1.000 |
| DT | 220 / 262 | 1.000 / 1.000 |
| G-RF | 243 / 253 | 1.000 / 1.000 |
| RF-walk | 245 / 260 | 1.000 / 1.000 |
| **QS** | **13 805 / 8 576** | **0.846 / 0.755** |

- QS on D3 costs about 0.5 ms per inference. It drops 15 % of packets at 168 kpps and 25 % at 400 kpps.
- G-RF and walk are indistinguishable from the null chain.

**Verdict (E5):** there is no end-to-end benefit to carry over.
- Where QS is merely slower (D1, D2: shallow-ish models, 1–3 % of packets inferring), the difference is hidden by per-packet costs.
- Where the useful model is deep (D3), QS collapses the datapath.
- The Pareto point for every dataset is a DT or a G-RF RF, never QS.

## 5. Why QS loses in eBPF although it wins in C (E4b)

**The question:**
- In plain C (E1 §3), QuickScorer beats the table walk in the ≤ 64-leaf regime: 51 of 204 models, up to 3× faster.
- In eBPF (E4) it is 1.6× slower than the walk and 6× slower than G-RF.
- The suggested explanation was untested: verifier masks and bounds, read-modify-write of map memory, no SIMD.

**E4b measures it directly.** It uses 7 representative RFs, all in the W = 1 regime (≤ 64 leaves, or depth 6):
- D1 binary T64L64, D1 multiclass T64L64 / T64D6 / T128L64;
- D2 multiclass T64L64;
- D3 binary T64L64, D3 multiclass T128L64.

Same tables, same 20 000 test rows, all runtimes bit-exact (0 mismatches).

**Measurements:**
- **Hardware counters per inference.**
  - eBPF: kernel-mode instructions, branches and branch misses around BPF_PROG_TEST_RUN, minus a null chain with the same number of stages.
  - C: user-mode counters including cycles.
  - The DUT vPMU returns no kernel-mode cycle count, so eBPF cycles are (ns − null ns) × 2.195 GHz.
- **Work per row** (counted in `rfm.c`): internal nodes visited by the walk, and false-node bitvector updates by QS.
- **Code:** BPF xlated code (`bpftool`), the x86 JIT image (`code/trackh/ebpf/jitdump.c`, because bpftool on the DUT has no disassembler) and the gcc code. All are in `results/e4b/code/`.
- **Ablations:**
  - in C: `qs_bpf`, the QS loop with the code shape the verifier forces (masked indices, `QS_N` bound, break inside the body); `qs_vol`, the same with a volatile bitvector, i.e. forced load+store; a build with auto-vectorisation off;
  - in eBPF: `qss`, the bitvector on the BPF stack instead of the per-CPU map.
- **Timing regimes:**
  - "warm" is the E4 harness: BPF_PROG_TEST_RUN `.repeat = 200` runs *one* row 200 times in a row.
  - "cold" means every call is a new row: eBPF `repeat = 1` over 20 000 rows, and C cycling through rows.
  - Both runtimes are measured in both regimes.
- **Files:**
  - data: `results/e4b/mech.csv`, `regime.csv`;
  - derived: `mechanism.csv`, `mechanism.md`, `regime_summary.csv`;
  - scripts: `code/trackh/ebpf/e4b_mech.py`, `e4b_post.py`, `e4b_analyze.py`.

### 5.1 Result 1: the reversal is real, and E4's harness exaggerated it

QS time / walk time (lower favours QS). eBPF numbers are the best variant of each family, null-subtracted.

| model | steps / updates per row | C cold | C warm | eBPF cold | eBPF warm (E4 harness) | eBPF cold: QS / G-RF |
|---|---|---|---|---|---|---|
| D1 bin T64L64 | 455 / 1671 | **0.86** | 1.71 | 1.04 | 1.17 | 6.7× |
| D1 mc T64L64 | 453 / 1712 | **0.92** | 1.64 | 1.21 | 1.69 | 6.3× |
| D1 mc T64D6 | 374 / 1199 | **0.84** | 1.49 | 1.07 | 1.40 | 6.7× |
| D1 mc T128L64 | 905 / 3423 | **0.73** | 1.49 | 1.18 | 1.97 | 6.0× |
| D3 mc T128L64 | 717 / 3600 | **0.84** | 2.01 | 1.20 | 1.76 | 4.5× |
| D3 bin T64L64 | 274 / 1719 | 1.52 | 3.13 | 1.89 | 2.27 | 10.5× |
| D2 mc T64L64 | 184 / 1981 | 2.62 | 3.33 | 3.77 | 4.60 | 20.5× |

**The harness bias:**
- The E4/warm harness favours the walk. Repeating one row lets the branch predictor learn its path: walk branch misses fall from 19–253 per inference to 0.5–26, in C and in eBPF alike.
- In C that turns QS's win into a 1.5–2× loss.
- So part of E4's "QS 1.6× slower than walk" is a harness effect. **The cold regime is the realistic one for XDP**, where every inference is a different flow.

**What survives in the realistic (cold) regime:**
- In the 5 models where QS wins in C (0.73–0.92), it **still loses in eBPF (1.04–1.21)**.
- QS stays **4.5–20× slower than G-RF**.
- Neither E4 verdict changes.

### 5.2 Result 2: in C, QuickScorer wins on IPC, not on instruction count

C, cold, 7 models:

| | QS | walk |
|---|---|---|
| work per row | 3.2–10.8× more updates than walk steps | — |
| instructions per row | 2.6–4.9× the walk's | — |
| instructions per unit of work | 9.7–11.8 per update | 10.7–31 per step |
| IPC | **2.9–3.2** | **0.65–1.0** (1.9 on D2) |
| cycles per unit of work | **3.0–3.9 per update** | **12.5–18.5 per step** |

- The walk is a chain of dependent loads (node → feature → `x[feature]` → threshold → child) and mispredicts every few steps.
- QS is a stream of independent load-AND-store operations with one predictable branch per update.
- QS wins whenever its work ratio (updates / steps) is below its per-unit cycle advantage (walk cycles per step ÷ QS cycles per update, 3.8–6.0×).
- The work ratio is 3.2–3.8× on the four D1 models and 5.0× on D3 multiclass, so QS wins.
- It is 6.3× on D3 binary and 10.8× on D2, so QS loses even in C.

### 5.3 Result 3: in eBPF, QS pays its instruction inflation in full, while the walk hides it

eBPF, cold, same 7 models, null-subtracted:

| | QS | walk | G-RF |
|---|---|---|---|
| instructions per unit of work | **27–32 per update (2.6–3.1× C)** | **40–62 per step (2.0–4.0× C)** | **5.4–6.3 per step** |
| cycles per unit of work | **5.7–8.2 (1.6–2.1× C)** | **17.8–26.6 (1.2–1.5× C)** | ≈ 3–4 |

**QS has nowhere to hide its extra instructions.** Its loop already runs at about 3 IPC in C, so 2.6–3.1× more instructions turn directly into about 1.8× more cycles per update.

**The walk hides most of its 2–4× instruction inflation.**
- Its IPC rises from about 0.9 to 2.0 (warm; cold is similar).
- The extra instructions execute in the shadow of the load-latency chain.
- Its cycles per step grow only about 1.35×.
- Branch misses barely matter in eBPF: the cold eBPF walk has 20–243 misses and is no slower than warm.

**Net effect:**
- QS's cycle advantage per unit of work falls from 3.8–6.0× (C) to 2.9–4.2× (eBPF).
- For the five models where QS wins in C, that is now below the work ratio of 3.2–5.0×, so QS/walk goes from 0.73–0.92 to 1.04–1.21.

**G-RF removes the walk's load chain entirely.** Thresholds and feature indices are immediates in the code, so it does no table loads. It needs about 5.5 instructions and about 3–4 cycles per step, while doing 3–11× less work than QS. That is why it wins by 4.5–20×.

### 5.4 Where the QS instruction inflation comes from (direct code comparison)

D1 multiclass T64L64, one bitvector update. The full listings are in `results/e4b/code/`: `qs_g1.dump` (xlated), `qs_g1.jit.s` (x86 JIT) and `rfm_gcc.objdump`.

**gcc `qs`: 9 x86 instructions.**
```
movzwl (%r10,%rax,2),%edx        ; tree id          (scaled-index load)
mov    (%r9,%rax,8),%r13         ; mask
and    %r13,(%rcx,%rdx,8)        ; v[tree] &= mask  (memory-operand RMW, scaled index)
lea 0x1(%rax),%rdx ; cmp %rax,%rsi ; je ; mov %rdx,%rax
cmp    %edi,(%r8,%rax,4) ; jl    ; threshold < x    (memory-operand compare)
```

**eBPF `qs_g1` after JIT: 22 BPF instructions → 25 x86 instructions.**

| category | x86 instructions | cause |
|---|---|---|
| essential: thr load, compare+jump, tree id load, mask load, word load, AND, word store, loop test, increment | 11 | same work as gcc, but no memory-operand compare or AND |
| sign-extension of the 32-bit threshold (`shl 32; sar 32`) | 2 | BPF has no sign-extending 32-bit load (LLVM's default BPF CPU) |
| index → address (`shl 3; add`) | 2 | BPF has no scaled-index addressing |
| verifier: `and $0x3f` on the bitvector index; `QS_N` bound (`mov $0xfc0; cmp; ja`) | 4 | the verifier needs provable bounds on map-value offsets and on the loop |
| 3 extra strength-reduced pointer increments | 3 | consequence of no scaled addressing: one pointer per table |
| register copies (two-operand form) | 2 | |
| base-pointer reload from the stack every update | 1 | register pressure: BPF exposes 10 registers, and the address add clobbers the base |

- 25 against 9 x86 instructions is **2.8×**, matching the 2.6–3.1× measured with counters.
- **Only 4 of the 16 extra instructions are verifier-forced. 12 come from the BPF ISA and its JIT:** no scaled-index addressing, no memory-operand ALU or compare, the sign extension, the two-operand form, and register pressure.
- The leaf-extraction phase adds to this. gcc uses one `tzcnt`; BPF has no count-trailing-zeros, so it uses a de Bruijn multiply plus a table load, made opaque so clang does not fold it into an unsupported `cttz`.

### 5.5 The three proposed explanations, tested

| proposed cause | test | result |
|---|---|---|
| index masks and bounds checks for the verifier | gcc compiling the exact verifier-forced loop shape (`qs_bpf`) | +28 % instructions, +39 % cycles per update. eBPF costs +160 % instructions. **Contributes, but explains < 1/4 of the gap**; also 4 of the 16 extra JIT instructions |
| bitvector read-modify-write in map memory | `qs_vol` (forced load+store, no register caching) in C; `qss` (bitvector on the BPF stack) in eBPF | C: 16 instructions and 4.0–8.0 cycles per update, still below eBPF's 9.3 warm / 5.7 cold. eBPF: the stack version **cannot be loaded**, because the verifier hits its 1 M processed-instruction limit (`processed 1000001`, E2BIG): it tracks every stack slot of the bitvector and cannot prune loop states. So map memory is a verifier constraint, but the RMW itself is not the main cost: x86 performs it as one memory-operand `and` |
| no SIMD in eBPF | gcc with `-fno-tree-vectorize -fno-tree-slp-vectorize` | QS unchanged: 2 294 against 2 275 ns. The gcc inner loop is scalar; SIMD is used only for the 512-byte bitvector init. **Not a factor for W = 1.** It would matter only for W > 1, where QS already loses on work |

**Conclusion of E4b:**
- QuickScorer's published advantage is an *IPC* advantage: dense, independent, branch-light memory operations against a latency-bound pointer-chasing walk.
- eBPF removes that advantage through **instruction inflation** of about 2.8×. It comes mostly from the BPF ISA and JIT (no scaled-index addressing, no memory-operand ALU, sign extension, two-operand form, register pressure, no ctz) and only partly from verifier-forced masks and bounds.
- QS's loop is already throughput-bound, so the inflation lands directly in cycles. The latency-bound walk absorbs a similar inflation almost for free.
- Code-generated G-RF has neither QS's extra work nor the walk's load chain, and is 4.5–20× faster than QS.
- The E4 harness exaggerated the QS/walk gap by about 1.2–1.7× by replaying each row 200 times. This changes no verdict.

## 6. Failures and deviations (all kept)

**E5 v1 was invalid and was discarded.**
- tcprewrite 4.4.4 silently rewrote IP total length 40 → 46 in padded 60-byte frames.
- Oversize offload frames (> 1514 B) could not cross the link.
- D2 is in Linux-SLL format.
- Features matched offline for only 16.6 % of flows. Fixed by `e5_pcapfix.py`, which rewrites the MACs only, converts SLL to Ethernet and drops oversize frames, and by recomputing the offline reference on the replayed packets.

**Oversize frames are a D1 dataset artefact** (protocol §7). D1 replay F1 is 0.40–0.47 against 0.99 on capture features.

**Single-sender limit.** One tcpreplay process reaches only about 200 kpps. Four parallel senders reach about 400–430 kpps. D2 (and slightly D1) lose packets at that rate for every program including null, so it is a testbed receive limit. The true DUT saturation point was not reached for the fast programs.

**Not investigated.**
- A few T512 variants fail with "Bad address" (EFAULT) at load.
- The vPMU does not count kernel-mode cycles; eBPF cycles are time-derived. L1D counters are not reliable in the VM and are not used.
- bpftool on the DUT has no JIT disassembler. JIT images were read with `code/trackh/ebpf/jitdump.c` (bpf_prog_get_info_by_fd) and disassembled locally with objdump.
- In E4b, `qs_g4` of D1 multiclass T128L64 and every `qss` (stack bitvector) variant hit the verifier's 1 M-instruction limit.
- In the warm harness, QS itself was 1.2–1.6× slower than in the cold one on some models. This was not investigated; the cold numbers are used for the mechanism.

**No CPU pinning** (user decision). Run-to-run noise of eBPF timings in the VM is about ±10–20 % per pass. All claims are on interleaved medians or CIs.

**Post-hoc grids.** RFdeep and RFleaf were added after the frozen grid and are labelled as such.

## 7. Recommendation

**NO-GO**, by the plan's own criteria:
- tuned baselines (G-RF, plus a data-driven walk where G-RF hits the tail-call cap) match or exceed QS-G's deployable coverage and runtime efficiency on every tested model;
- the only configurations where our first G-RF generator failed (T ≥ 256) all load as single programs with the fixed generator (full E2 rerun, §2.1), are 4.7–16× faster than QS there, and have no quality value anyway.

**Possibly reusable outside this claim:**
1. The measured explanation (§5) of why branch-free, memory-streaming tree algorithms lose in eBPF while code-generated trees win. This is a short negative-result or workshop note at most.
2. The validated Track-H XDP pipeline: bit-exact online features.
3. The D1 offload-artefact finding.

# E0: Hara & Sasabe reproduction — status report

**Status: partially complete.**
- **Done:** the faithful code is cloned, pinned, audited, built, loaded and run under traffic on the testbed. The clean performance variants (plan step E0.5) are also done and checked against the faithful code (§4b).
- **Done (§4h, §4i):** CIC-IDS2017 model quality on all five days (55.95 M labelled packets), with the shipped DT and NN run bit-exactly as the kernel does.
  - Pooled binary results: DT acc 0.718 / F1 0.284 and NN 0.649 / 0.195 (kernel semantics). The paper reports 0.977 / 0.954 and 0.975 / 0.952.
  - AF_XDP 7-class NN: best accuracy 0.767, against the paper's 0.974.
  - About 30 % of benign packets are flagged as attacks, even on the all-benign Monday.
  - A depth-5 DT that we trained on the same features and labels reaches acc 0.974–0.985 binary and 0.976–0.984 7-class, so the task is learnable and the shipped parameters do not fit it.
  - **Track-R status: not reproduced with the shipped parameters.** The cause cannot be determined, because the repo has no training code (§3).
Date: 2026-11-03. Testbed: `testbed/README.md` (qs-dut 192.168.101.51 / qs-tg 192.168.101.52 on fil100).

## 1. Pinned source and environment

| item | value |
| --- | --- |
| repo | https://github.com/oakeshott/ebpf-classifier @ `d24666607fba0a59130a5c2ee3b8c17a3f2d103c` (2025-11-14) |
| submodule `xsknf` | `4825b2bddebfeb5dee66ebd004a27eaa2a8f4821` (URL rewritten from `git@` to `https://`; this is the only clone-time change) |
| `xsknf/xdp-tools` | `f1b14b0a7610d8a63fd6615f0dcaa65ac5c02211` (v1.0.0-beta3-296) |
| `xsknf/xdp-tools/lib/libbpf` | `e99f34e14447866bcbc38944387531c36f6c85fe` (v0.6.0-68) |
| DUT | Ubuntu 24.04, kernel 6.8.0-147, KVM guest, 8 vCPU, virtio-net (vhost, 8 queues) |
| toolchain | clang 18.1.3, gcc 13.3, BCC/python3-bpfcc 0.29.1, Python 3.12.3, bpftool 7.4, libbpf 1.3 (system) |
| paper environment (NoF'23 precursor) | Xeon Gold 5317, Intel X710, Ubuntu 20.04, kernel 5.15, hping3 TCP, 1 CPU via `chcpu` |

Clone location on qs-dut: `~/ebpf-classifier`.

The README's own clone command points at the wrong repo (`oakeshott/mlids.git`). Its NN path (`cd nn_filter`) is also wrong: the directory is `nn-filter`.

## 2. Paper reference used

I could not retrieve the journal full text (Comput. Netw. 240, 110188): ScienceDirect returned 403 and the NAIST repository returned 503.
Every paper-side fact below comes from the **NoF 2023 precursor** ("On Practicality of Kernel Packet Processing Empowered by Lightweight NN and DT", the authors' submitted version, saved to `~/qs-lab-cache/papers/hara2023_nof.pdf` on server3).
The journal adds AF_XDP and may differ, so **its numbers still need to be filled in from the journal PDF**.

From the precursor paper:
- **Data and features:** CIC-IDS2017, per-packet classification over 5-tuple flows. There are 12 features: sport, dport, proto, length and direction, plus the flow running mean and running mean-absolute-deviation of length, inter-arrival time (IAT) and direction.
- **Classes:** binary, and 7-class: Botnet, Brute force, DoS, Infiltration, Normal, Portscan, Web attack.
- **Split:** random 67/33 train/test, with train further split 80/20 into train/validation. This is not session-disjoint (see §5, item Q1).
- **NN:** 12-16-16-{2|7} MLP trained in PyTorch, 8-bit post-training quantization, fixed-point Q16.
- **DT:** scikit-learn, depth 5.
- **Binary results (Table II):** DT(C) accuracy 0.977, F1 0.954. NN(C) accuracy 0.975, F1 0.952.
- **Multiclass accuracy (Table III):** DT(sklearn) 0.969, NN(PyTorch) 0.974.
- **Throughput:** in-kernel XDP_DRV, 1 core, reached about 300 kpps (NN) and about 450 kpps (DT).

## 3. Inventory of what the repo actually contains

| component | files | model | notes |
| --- | --- | --- | --- |
| H-NN-XDP | `nn-filter/nn_filter_xdp.py` (BCC) | `nn-filter/mlp_params.json`: 12-16-16-**2** (binary) | 3 programs, 2 tail calls (`nn1`, `nn2`) |
| H-NN-TC / raw socket | `nn_filter_tc.py`, `nn_filter_rawsocket_us.{py,c}` | same | |
| H-DT-XDP | `dt-filter/dt_filter_xdp.py` (BCC) | `dt-filter/runs/*`: 53 nodes, 27 leaves, **depth 5**, binary | uses features {0,1,4,6,8,9,10,11} |
| features-only baseline | `filter/filter_xdp.py` | — | the paper's "XDP_DRV (Flow Extraction)" |
| H-NN-AFXDP | `xsknf/examples/mlids` (libbpf, `-M COMBINED`) | `xsknf/examples/nn/mlp_params.c`: 12-16-16-**7** (multiclass, *different weights*) | prebuilt `mlids` binary is committed |
| DT for AF_XDP | `xsknf/examples/dt/dt.c` | same 53-node tree, hard-coded | |
| RF for AF_XDP | `xsknf/examples/rf/rf.c` | 10 trees × 55 nodes, binary, hard-coded | **broken, see B6** |
| harness | `tests/test.py`, `script/*.sh` | — | hping3 over SSH to the authors' own hosts; throughput only |

**Absent from the repo:**
- training code;
- CIC-IDS2017 preprocessing, packet labelling and the train/test split;
- quantization (PTQ) code;
- a reference inference script, and any accuracy test.

The in-kernel NN is binary-only. The only multiclass NN is the AF_XDP one. There is no multiclass DT.

## 4. What was run (faithful code, unmodified)

Scripts: `e0/run_smoke.sh` (in-kernel) and `e0/run_afxdp.sh` (AF_XDP). Raw logs are in `e0/*.log`.
- **Traffic:** qs-tg runs pktgen with 64B UDP, 4 threads, 1024 flows, offering about 0.45–1.0 Mpps.
- **DUT data0:** the RX queues are reduced to 1 with `ethtool -L data0 combined 1`. This is the analogue of the paper's single core.
- **Repetitions:** in-kernel runs were interleaved, 3 repetitions. AF_XDP runs had 2 repetitions.

All programs **compile, pass the verifier and attach on kernel 6.8** without source changes. The only exception was building `xsknf`, which needed the extra package `m4`. Its unrelated `load_balancer` example fails under clang 18 with `-Werror`; `mlids` builds fine.

| variant (faithful) | attach mode | program-reported rate (pps) | paper (NoF'23) |
| --- | --- | --- | --- |
| no program (kernel forwarding) | — | sink ≈ 380–400 k (forwarding limit) | — |
| `filter` (features only) | native | **450 k** (449–461 k) | ~flow-extraction curve |
| DT (`-D`) | native | **425 k** (418–440 k) | ≈450 k |
| NN (`-D`) | native | **190 k** (188–193 k) | ≈300 k |
| AF_XDP COMBINED, copy mode, `-m NN` | native + xsk | 327 k | (journal only) |
| AF_XDP COMBINED, copy mode, `-m DT` | native + xsk | 507 k | (journal only) |
| AF_XDP COMBINED, copy mode, `-m RF` | native + xsk | 507 k | (journal only) |
| `-p` (poll) variants | same | within 1% of non-poll | |

How to read these numbers:
- **In-kernel programs:** "rate" is the program's `dropcnt` counter, which counts packets that reached a verdict. The programs return `XDP_PASS`, so the kernel forwarding stack runs on the same core and is included in the cost.
- **AF_XDP:** the "rate" is the xsknf user-space rx pps. The worker was pinned with `taskset -c 1`, i.e. one softirq core plus one worker core (see D3), and the packets are dropped.
- **Do not compare** in-kernel against AF_XDP numbers here as a model effect: the core counts and final actions differ.

The qualitative ordering filter > DT > NN reproduces the paper. Absolute numbers are virtio- and VM-bound, so the gap to the paper's 300 k (NN) is not interpretable as a regression.

## 4b. Clean performance variants (E0.5)

**How the variants are built.**
- `e0/make_variants.py` generates them from the pinned sources. Every hunk is asserted to match exactly once.
- On qs-dut they live in `~/e0/variants/<variant>/`.
- No variant touches feature extraction or inference arithmetic. Bugs Q2 and Q3 are kept deliberately, so the inference semantics stay Hara's.

| variant | change relative to faithful |
| --- | --- |
| `hist` | Adds a per-CPU class histogram `cls_hist` (observability only). |
| `clean_pass` | `hist`, plus: removes the B4 debug work (NN `bpf_trace_printk`; DT `DEBUG_BUILD` and its 3 per-packet hash updates) and fixes the B1 mode flag. The post-inference action is unchanged (`XDP_PASS`). |
| `clean_drop` | `clean_pass` with `FINAL_ACTION=XDP_DROP` after inference, for every model alike. This excludes the cost of kernel forwarding. |

**Equivalence check.**
- *Method:* `e0/gen_trace.py` builds a synthetic, non-dataset trace of 16 000 packets over 400 flows, mixing TCP and UDP, well-known and ephemeral ports, and sizes from 54 to 1454 B. It is replayed with tcpreplay at 5 kpps, below saturation, on one queue. There were 3 repetitions each of `hist`, `clean_pass` and `clean_drop`; the log is `e0/equiv_replay.log`.
- *Result:* all 9 runs per model gave identical class histograms. DT was 8352 / 7648 (class 0 / class 1) and NN was 10369 / 5631. Even with the live IAT features, the runs reproduced exactly.
- *Original limit:* this replay compares per-class totals. A subsequent deterministic full-BPF test compares every packet, including the NN ablations; see §4d.
- *B1:* the fix is verified. With `-S`, the clean DT and filter now attach as `xdpgeneric`.

**Per-packet cost and throughput, 1 queue, saturating pktgen load.**
- *Runs:* 3 interleaved repetitions. Raw data: `e0/tput_1q.log`, `e0/tput_1q.csv`.
- *Metric:* `ns/pkt` is the entry program's `run_time_ns / run_cnt` from `kernel.bpf_stats_enabled=1`. It covers the **whole tail-call chain**, and includes about 20–40 ns of stats overhead.
- *Format:* each cell is the median [min–max] of the 3 repetitions.

| model | variant | ns/pkt | inferences/s | xlated / JIT bytes |
| --- | --- | --- | --- | --- |
| bare `XDP_DROP` | — | 40.5 [39.5–43.0] | (offered ≈ 0.90 M) | 184 / 141 |
| filter | faithful | 329.8 [328–333] | 424 k | 1824 / 998 |
| filter | clean_pass | 336.4 [336–402] | 421 k | 1912 / 1042 |
| filter | clean_drop | 313.5 [308–322] | 905 k (offered-load bound) | 1912 / 1042 |
| DT | faithful | **866.3** [857–869] | 419 k | 4016 / 2324 |
| DT | clean_pass | 578.7 [576–599] | 406 k | 3912 / 2275 |
| DT | clean_drop | **545.2** [544–564] | 946 k (offered-load bound) | 3928 / 2282 |
| NN | faithful | **3470** [3419–3479] | 197 k | 4408 / 2567 (entry program) |
| NN | clean_pass | 3088 [2992–3486] | 209 k | 4408 / 2567 |
| NN | clean_drop | **2964** [2764–3891] | 291 k (CPU bound) | 4408 / 2567 |

How to read the table:

**R1. Debug overhead (B4) is large in the faithful numbers.**
- *DT:* its `DEBUG_BUILD` maps add about 290–320 ns per packet, i.e. 866 vs 545–579 ns, or 37 %.
- *NN:* its printk adds about 380–500 ns per packet.
- *Filter:* this variant has no debug code and is unchanged (330 vs 314–336 ns), which serves as a sanity check.

**R2. `XDP_PASS` measurements are stack-bound, not model-bound.**
- With `XDP_PASS`, filter, DT and the paper-style "inferences/s" all saturate at about 400–420 k pps, the limit of kernel forwarding on one core. So DT looks about as fast as the filter, even though its program costs 1.7× the filter's.
- This plausibly explains the paper's observation that DT gets close to the maximum.
- Classifier comparisons should use `clean_drop` with ns/pkt, or another common action.

**R3. Model-only cost**, i.e. variant cost minus the filter cost, on `clean_drop`:

| model | model-only cost | ratio to DT |
| --- | --- | --- |
| DT | ≈ 230 ns | 1× |
| NN | ≈ 2650 ns | ≈ 11.5× |

For comparison, the paper's user-space C timings give 6.38 vs 0.86 µs, i.e. 7.4×.
- *Cause investigated subsequently:* the NN performs 1 map lookup per weight, about 480 `lookup_or_init` calls per packet across its 3 layers. Profiling and data-layout ablations are now complete; see §4c.
- *Why it matters:* it is directly relevant to how G-RF and QuickScorer should lay out their models in later experiments.

**R4. Noise.**
- TG-side pktgen occasionally under-offered: rep 1 NN clean_pass offered 343 kpps and NN clean_drop 440 kpps; rep 2 filter clean_pass offered 257 kpps.
- These runs are kept in the log and the CSV. They widen the min–max ranges above.
- ns/pkt is much less sensitive to this than pps is.

## 5. Audit findings (source behaviour that affects any reuse)

**Bugs affecting measured cost or semantics**

**B1. DT and `filter`: the attach-mode flag is ignored.**
- *Where:* `dt_filter_xdp.py` and `filter_xdp.py`.
- *What:* the flags are parsed only `if len(sys.argv) == 3`, i.e. when no flag was given. So `-S`, `-D` and `-H` have no effect.
- *Verified:* `-S` gives `xdpgeneric` for the NN but native `xdp` for DT and filter.
- *Effect:* any "XDP_SKB (DT)" number from this code is actually native mode, or whatever default the driver picks.

**B2. AF_XDP `mlids`: missing `break`s in `switch(opt_ml_method)`.**
- *What:* `-m NN` runs NN, DT, RF and NN again. `-m DT` runs DT, RF and NN. `-m RF` runs RF and NN.
- *Verified:* adding only the breaks (`mlids_brk`) raises NN from 327 k to **510 k** and DT/RF from 507 k to **848 k**, which hits the offered-load ceiling.
- *Effect:* faithful AF_XDP per-model costs are not per-model.

**B3. AF_XDP COMBINED: per-packet syscall and a dangling pointer.**
- *What:* user space calls `bpf_map_lookup_elem()` on the kernel `sessions` map for every packet, which is a syscall. It then uses `&value` from a returned stack frame, which is undefined behaviour.
- *Also:* updated flow state is never written back, so the AF_XDP features never accumulate beyond what the kernel stores.
- *Pure `-M AF_XDP` mode:* sessions are never inserted (`store_session` is commented out), so **no inference ever runs**.

**B4. Debug overhead is left enabled.**
- *NN:* `nn2` calls `bpf_trace_printk` on every packet.
- *DT:* `DEBUG_BUILD` is defined, which adds 3 extra `BPF_HASH` updates keyed by the Ethernet header on every classified packet. It also turns the "anomaly" verdict into `XDP_PASS`.
- *AF_XDP:* `handle_xdp` calls `bpf_printk` on every redirected packet.
- *Effect:* all of these are in the faithful numbers above.

**B5. No in-kernel variant acts on the verdict.**
- The NN always returns `XDP_PASS`, and `dropcnt` counts inferences, not drops.
- The DT returns `XDP_PASS` for both classes, because of `DEBUG_BUILD`.
- The `forward` (FIB redirect) code is either unreachable (DT) or commented out (NN).

**B6. The RF is invalid.**
- *What:* `rf.c` indexes the node arrays as `rf_*[j*N + node]`, where `N` is the batch size, which is 1.
- *Effect:* tree *j* starts at offset *j* instead of *j·55*, so trees 1–9 walk mis-aligned node arrays.
- *Implication:* the repo's RF **cannot** be used as an RF baseline or as an RF accuracy reference. Our RF work must use G-RF (Galvao) and our own exporter.

**Bugs affecting features or accuracy**

**Q1. Random split.** The paper splits packets randomly, not by flow or session. Packets from one flow, and their cumulative features, appear in both train and test, which likely inflates the reported quality. This conflicts with experimental.md §3.2, so Track R reproduces it as-is and Track H must not.

**Q2. The direction feature is constant.**
- *What:* `x[5] = (pkt_key.sport == pkt_leaf->sport)`, but the session key is the directional 5-tuple, so this is always 1.
- *Effect:* the direction feature is constant 1, its running mean is constant 1, and its running mean absolute deviation is 0. These are Q16 values 65536, 65536 and 0 respectively. (The earlier report incorrectly said the mean was 0.)
- *Paper vs code:* the paper defines direction as incoming = 1, else 0. The training data is computed offline and might differ from this, but that cannot be checked because the training code is missing.

**Q3. The DT stalls on zero-valued features.**
- *What:* the in-kernel DT only descends `if (current_feature_value)`. For a zero feature (e.g. IAT of a flow's first packet, or a mean deviation of 0) it stays at the current internal node for all 20 iterations, then returns that internal node's `value`.
- *Effect:* this is not equivalent to the sklearn tree. The AF_XDP `dt.c` does not have this guard, so the in-kernel and AF_XDP DTs disagree.

**Q4. Model mismatch.** The in-kernel NN (binary) and the AF_XDP NN (7-class) have different weights. The AF_XDP NN is the only multiclass model.

**Q5. Per-packet inference.** Every packet triggers inference, including the first packet of a flow (IAT = 0). There is no N-packet trigger. Track H (N = 8) is therefore a deliberate protocol change relative to Hara.

**Q6. Flow table sizes differ.** The in-kernel flow table is an LRU hash with 1024 entries; AF_XDP uses 1 M. Under many concurrent flows, the in-kernel features are silently reset by eviction.

**Q7. The NN ignores all IAT features.** The shipped normaliser has `data_scale = 0` for iat, avg_iat and mad_iat, so those inputs are always 0 after normalisation (§4h). The DT does use IAT thresholds, whose unit (ns in the kernel) is undocumented.

**Q8. The NN quantiser clamp never fires.** `quantize()` compares the integer part of the activation with `127 * s_x_inv` instead of `127 / s_x`; activations beyond the int8 range wrap in the cast instead of saturating. 27 packets on Wednesday wrap with kernel semantics, 5.46 M with bidirectional sessions (§4h).

## 6. Blockers and deviations

**Blockers**

- **K1. Dataset access (resolved 2026-11-03).** The official cicresearch.ca links redirect to UNB's registration form. We use the Hugging Face mirror `bencorn/CICIDS2017` (same files and LFS SHA-256 as `bvsam/cic-ids-2017`). The mirror is verified against copies obtained independently: its `Wednesday-workingHours.pcap` (SHA-256 cd2674db7559a53f…) and `GeneratedLabelledFlows.zip` (7bdbef286f8893f3…) are byte-identical to the copies already on server3 at `~/ebpf/data/cicids2017`. The other four days' PCAPs are downloaded to `trackr/data/cicids2017/` by `fetch.sh`, which checks every file against the mirror's SHA-256.
- **K2. No training or labelling pipeline.** A quality reproduction needs packet-to-label linkage, i.e. matching packets against the CICFlowMeter CSV flows by 5-tuple and time window, re-implemented by us.
  - With that, the **shipped** DT and NN parameters can be evaluated offline with the repo's own C inference (`dt.c`, `nn-filter/include/*`).
  - Re-training with the paper's settings would be a *documented re-implementation*, not a reproduction.

**Deviations from the paper setup**

- **D1. Testbed.**
  - *Hardware:* virtio-net in KVM instead of an X710 on bare metal.
  - *Traffic:* pktgen UDP instead of hping3 TCP.
  - *Single core:* `ethtool -L combined 1` instead of `chcpu`.
  - *Effect:* absolute pps is not comparable to the paper. Use the testbed only for relative comparisons.
- **D2. AF_XDP mode.** virtio_net on kernel 6.8 has no AF_XDP zero-copy, so the runs use `-i data0:c` (copy mode). The paper's NIC presumably ran zero-copy.
- **D3. AF_XDP core placement.** With 1 queue, xsknf pins its worker to the first allowed CPU. That is the same CPU as the RX IRQ, and under overload the worker received 0 packets (livelock). The runs therefore used `taskset -c 1`, i.e. one IRQ core plus one worker core.
- **D5. Clean variants.** These live in separate trees (`~/e0/variants/`) and are generated by `e0/make_variants.py`. The pinned checkout is not modified.
- **D4. Extra binary.** `mlids_brk` adds only the `break`s and is used only to demonstrate B2. It is an untracked file, `xsknf/examples/mlids/mlids_brk*`. The faithful `mlids` was rebuilt from source; the committed prebuilt binary is kept in `~/e0/mlids.prebuilt`.

## 7. Next steps for E0

1. **Dataset (K1):** submit the UNB form and pull the CIC-IDS2017 PCAPs plus the `MachineLearningCVE`/`TrafficLabelling` CSVs to server3. Then record checksums.
2. **Offline reference:** write a replay that computes Hara's 12 features exactly as the kernel code does, including Q2 and Q3, and also a "fixed" variant. Run the shipped DT and NN, both binary and the AF_XDP 7-class NN, and compare against Tables II and III.
3. ~~Clean performance variant~~: **done**, see §4b.
   - *Done subsequently:* a per-packet equivalence check using the complete BPF programs and tail-call chains with controlled PCAP timestamps; see §4d. This is a deterministic test-run check, not another live replay.
   - *Done subsequently:* a repaired AF_XDP candidate fixing B2/B3 and removing per-packet `bpf_printk`; see §4e. This changes flow-state ownership, so it is explicitly an architectural repair rather than a faithful-equivalence variant.
4. **Throughput:** `XDP_DROP` isolation is **done** (§4b).
   - *Remaining:* `bpftool prog profile` cycles and instructions per program. The TG cannot offer more than about 0.9–1.0 Mpps, so filter and DT under `clean_drop` are offered-load bound. Use ns/pkt for them, or add a second TG thread or queue.
   - *Done subsequently:* NN map-access cost attribution; see §4c. These optimizations are not presented as Hara's design.

## 4h. Track-R quality on CIC-IDS2017 Wednesday (offline, shipped parameters)

**Data.** Found on server3 at `~/ebpf/data/cicids2017/` (downloaded by another project; used read-only):
the Wednesday PCAP converted to classic pcap (`wed.pcap`) and `GeneratedLabelledFlows.zip` (all
days' TrafficLabelling CSVs). Only Wednesday has a PCAP, so only BENIGN vs DoS (Hulk, GoldenEye,
slowloris, Slowhttptest) and Heartbleed can be scored. SHA-256 in `results/trackr/dataset_sha256.txt`
(`wed.pcap` a703c76b…, Wednesday CSV ed538e85…).

**Method** (`trackr/`, all on server3):
- `hara_ref.c` transcribes the kernel parsing, session state, 12-feature arithmetic, DT walk and NN
  fixed-point code with the same C integer types (`gcc -O2 -fwrapv`); parameters come unmodified from
  the repo via `gen_params.py`. **Validated bit-exact** against `BPF_PROG_TEST_RUN` of the real programs
  (§4d): 16 000 / 16 000 packets identical for DT and NN, faithful and clean_drop.
- `label_packets.py`: per-packet labels from the CSV by direction-free 5-tuple and minute window
  (±2 min, UTC−3; {BENIGN, attack} → attack). This is our re-implementation; Hara's is unpublished.
  Wednesday: 13 788 878 records, 13 704 886 labelled (11.22 M BENIGN, 2.49 M attack), 283 unlabelled,
  0 ambiguous, 83 709 not IPv4 TCP/UDP.
- `metrics.py` (binary, attack = positive, per packet, every labelled packet scored).
- Variants: session key `dir` (kernel: directional 5-tuple, so direction ≡ 1, Q2) or `bidir`
  (paper-intended: one session per connection; direction = initiator side); IAT in ns (kernel) or µs;
  unbounded table or exact LRU of 1024 (kernel map size, Q6).

**Results** (`results/trackr/wed_metrics.md`, `.json`). Paper Table II (full dataset, random split): DT acc 0.977 / F1 0.954, NN 0.975 / 0.952.

| variant | model | acc | precision | recall | F1 | FPR |
|---|---|---|---|---|---|---|
| dir, ns, unbounded (kernel semantics, no eviction) | DT | 0.711 | 0.362 | 0.773 | 0.493 | 0.303 |
| | NN | 0.636 | 0.260 | 0.547 | 0.353 | 0.345 |
| dir, ns, LRU 1024 (as deployed) | DT | 0.685 | 0.294 | 0.522 | 0.376 | 0.278 |
| | NN | 0.647 | 0.270 | 0.556 | 0.363 | 0.333 |
| dir, µs | DT | 0.697 | 0.325 | 0.622 | 0.427 | 0.286 |
| bidir, ns | DT | 0.514 | 0.261 | 0.919 | 0.407 | 0.576 |
| | NN | 0.577 | 0.253 | 0.681 | 0.369 | 0.446 |
| bidir, µs | DT | 0.568 | 0.278 | 0.862 | 0.420 | 0.497 |

NN results do not depend on the IAT unit: the shipped normaliser has `data_scale = 0` for all three
IAT features, so **the NN ignores IAT entirely** (new finding Q7). Per-attack recall is in the CSV/MD.

**Controls.**
- *Learnability* (`control_dt.py`, `out/control_dt.md`): a depth-5 sklearn DT trained on the very same
  features and labels with the paper's random 67/33 split reaches test acc 0.985 / F1 0.957 (`dir`) and
  0.991 / 0.975 (`bidir`), 3 seeds, spread < 0.0005. The labelled task is therefore at paper level
  with this pipeline; the gap lies in the shipped parameters vs these features.
- *DT zero-stall (Q3)* (`shipped_dt_nostall.py`): the shipped tree under plain CART semantics is no
  better (dir: acc 0.675 / F1 0.297; bidir: 0.512 / 0.410). The kernel-semantics row reproduces the C
  reference exactly (0.711), an independent cross-check.
- *Feature ranges vs the shipped NN normaliser*: the training data had a varying direction feature
  (avg_dir min 0.0625, mad_dir range 0.485) and IP lengths up to 32 776 B, neither of which the kernel
  can produce (`dir`: direction ≡ 1). With `bidir`, 42 % of packets have mad_dir above the training max.

**New audit finding Q8: the NN quantiser's clamp is dimensionally wrong.** `quantize()` compares the
integer part of the activation with `127 * s_x_inv` (a Q16 reciprocal scale) instead of `127 / s_x`,
so out-of-range activations are never clamped and wrap in the `(int8_t)` cast (e.g. 128 → −128).
Counted in `hara_ref`: 27 packets wrap at layer 1 with `dir`, **5.46 M** with `bidir` (the mad_dir
overflow above). This silently flips inputs from maximal to minimal.

**Interpretation.** The shipped parameters do not reproduce the paper's quality on the Wednesday
traffic under any of the six feature/state semantics tried, while a model of the same kind trained on
the same features does. Plausible causes, not distinguishable without Hara's training code: the
shipped parameters come from a different feature definition (direction, IAT unit, flow key, length
source) or data subset, or are not the paper's model. Limitations: one day only (attacks of other days
unseen; the shipped model may have been tuned to the whole dataset), our labelling rule, binary only
(the 7-class AF_XDP NN is not scored yet). Track-R is recorded as **not reproduced with shipped
parameters**; a documented re-training is the fallback the plan allows, and it is not a reproduction.

**AF_XDP 7-class NN** (`nn7_eval.c` links Hara's unmodified `xsknf/examples/nn/*.c`; `nn7_metrics.py`,
`out/nn7_metrics.md`). Run on the same kernel-defined features, as if sessions were stored (B3 means the
pure AF_XDP path never infers). Class order assumed alphabetical as in the paper (0 Botnet … 2 DoS, 4
Normal, 6 Web attack); the confusion matrices are consistent with that. New finding **Q9**: `mlids_user.c`
passes the raw Q16 features to `run_mlp()` with **no min/scale normalisation**, although the model's
input quantiser expects [−1, 1] (`layer_1_s_x` = 127). Results (Heartbleed excluded from 7-class acc):

| features | normalisation | binary acc / F1 / FPR | 7-class acc on Wednesday |
|---|---|---|---|
| dir | none (as shipped) | 0.478 / 0.367 / 0.601 | 0.437 |
| dir | binary model's normaliser (charitable) | 0.687 / 0.392 / 0.284 | 0.690 |
| bidir | none | 0.348 / 0.341 / 0.781 | 0.330 |
| bidir | binary model's normaliser | 0.757 / 0.515 / 0.233 | 0.756 |

Paper Table III multiclass accuracy: NN 0.974. Not reproduced either.

Reproduce on server3:
```bash
cd ~/ebpf_quickscorer/trackr
python3 gen_params.py hara_src > params.h && gcc -O2 -fwrapv -o hara_ref hara_ref.c
./hara_ref data/eq_trace.pcap data/eq_dir --key dir     # then compare with e0/sequence/*.csv
./run_wed.sh                                            # 6 variants + labels, ~4 min
python3 metrics.py out/wed.lab.npy out/wed_*.cls
~/miniconda3/envs/vnpt/bin/python -I control_dt.py out/wed.lab.npy out/featdir.feat out/featbidir.feat
```
(`featdir/featbidir.feat` come from `hara_ref ... --dump-feat`.)

## 4i. Track-R on all five CIC-IDS2017 days (offline, shipped parameters)

**Data.** Monday, Tuesday, Thursday and Friday PCAPs come from the Hugging Face mirror
`huggingface.co/datasets/bencorn/CICIDS2017` (`pcaps/*.pcap`). It has the same LFS SHA-256 as
`bvsam/cic-ids-2017`, and its Wednesday file has the same hash as the server3 copy (cd2674db…). The
downloads were checked against the mirror's SHA-256 values (`trackr/data/cicids2017/fetch.sh`):

| file | SHA-256 prefix |
|---|---|
| Monday | f6eac599358f216b |
| Tuesday | 080c2250154c5a17 |
| Thursday | 38f8b1bb276849bf |
| Friday | beff0dcce1eebc9b |

Wednesday is the server3 file. The labels come from the official TrafficLabelling CSVs:
- Thursday: WebAttacks + Infilteration.
- Friday: Morning + PortScan + DDos.

**Pipeline.** The same as §4h, run per day by `run_day.sh` and `run_all_days.sh`, then pooled with
`aggregate.py` (`out/trackr_all.md`, `out/days/trackr_all.json`).

**Label coverage.** 55 951 952 packets are labelled out of 56 370 702 records. Per day, between 283 and 716 packets are unlabelled and 0 are ambiguous; the rest are not IPv4 TCP/UDP. Of the labelled packets, 51.49 M are BENIGN and 4.46 M are attacks (attack share 0.080). Heartbleed (49 296 packets) has no paper class and is excluded from the 7-class scoring.

**Binary, pooled over 5 days.** Paper Table II: DT acc 0.977 / F1 0.954; NN 0.975 / 0.952.

| features / state | model | acc | precision | recall | F1 | FPR |
|---|---|---|---|---|---|---|
| dir, unbounded (kernel semantics) | DT | 0.718 | 0.178 | 0.701 | 0.284 | 0.280 |
| | NN | 0.649 | 0.119 | 0.531 | 0.195 | 0.340 |
| dir, LRU 1024 (as deployed) | DT | 0.721 | 0.144 | 0.506 | 0.224 | 0.260 |
| | NN | 0.661 | 0.124 | 0.536 | 0.201 | 0.329 |
| bidir | DT | 0.483 | 0.119 | 0.853 | 0.208 | 0.549 |
| | NN | 0.585 | 0.124 | 0.693 | 0.210 | 0.424 |

**Per day** (dir, unbounded). The FPR stays at 0.24–0.35 on every day, including Monday, which is all BENIGN.

| day | attack share | DT acc / F1 / FPR | NN acc / F1 / FPR |
|---|---|---|---|
| Monday | 0.000 | 0.717 / – / 0.283 | 0.645 / – / 0.355 |
| Tuesday | 0.024 | 0.697 / 0.054 / 0.294 | 0.648 / 0.051 / 0.346 |
| Wednesday | 0.182 | 0.711 / 0.493 / 0.303 | 0.636 / 0.353 / 0.345 |
| Thursday | 0.011 | 0.758 / 0.021 / 0.237 | 0.676 / 0.028 / 0.322 |
| Friday | 0.161 | 0.717 / 0.436 / 0.275 | 0.651 / 0.332 / 0.328 |

**AF_XDP 7-class NN, pooled.** 55.90 M packets. Paper Table III: accuracy 0.974.

| variant | acc | macro recall |
|---|---|---|
| dir, no normalisation (as shipped, Q9) | 0.355 | 0.171 |
| dir, binary model's normaliser | 0.711 | 0.187 |
| bidir, no normalisation | 0.272 | 0.205 |
| bidir, binary model's normaliser | 0.767 | 0.352 |

Recall is 0.000 for Web attack in every variant, and 0.000 for Portscan, Brute force and Botnet in the best `dir` variant.

**Learnability control.** `control_all.py`, `out/control_all.md`: a depth-5 sklearn DT on the same 12 kernel features, trained on 4 M labelled packets sampled uniformly per day (20 M in total), random 67/33 split, 3 seeds (spread ≤ 0.0005 on accuracy).

| features | binary acc / F1 | 7-class acc / macro F1 |
|---|---|---|
| dir | 0.974 / 0.802 | 0.976 / 0.542 |
| bidir | 0.985 / 0.899 | 0.984 / 0.653 |

Our own model of the paper's kind therefore reaches the paper's accuracy (0.977 binary, 0.974 7-class) on our labels and features. Its F1 is lower than the paper's 0.954. The likely reason is the low attack share of the full capture (8 %), which a depth-5 tree cannot separate for the rare classes (macro F1 0.54–0.65). The paper does not report its class balance or any subsampling, so this F1 gap is not attributed to anything.

**Conclusion.** The five-day result confirms the Wednesday-only result in §4h, and resolves that section's "one day only" limitation:
- **Track-R is not reproduced with the shipped parameters,** binary or 7-class, under any of the feature/state semantics tried.
- The shipped models flag about 28–34 % of benign packets as attacks on every day. That is incompatible with the paper's 0.977 accuracy on a dataset that is 92 % benign.
- The labelled task itself is learnable to the paper's accuracy with the kernel's own features.
- The remaining route is a documented re-training (Track-H / E1), which is not a reproduction.

## 4c. Where the NN's time goes (clean_drop, 1 queue)

Raw data:
- profile: `e0/prof_nn_clean_drop.txt` (script `e0/profile_nn.sh`)
- ablations: `e0/abl_nn.log`, `e0/abl_nn_tput.csv` (script `e0/make_nn_ablations.py`)

**Profile (`perf record` on CPU 0 at saturation).**
- *Cycle split:* JITed BPF code takes 62% of the cycles: entry program 28.7%, `nn1` 26.7%, `nn2` 6.4%. Kernel code takes 38%.
- *Biggest kernel costs:* helpers for the per-CPU activation maps, about 13% (`array_map_update_elem`, `bpf_obj_memcpy`, `bpf_obj_free_fields`, `memcpy`), plus 1.6% for per-CPU lookups. `pvclock` (`bpf_ktime` in the VM) takes 2.1%, and the session LRU hash about 2%.
- *Bottleneck type:* IPC is 2.88 and cache misses are negligible, so the code is bound by instruction count, not memory.
- *Instructions per MAC:* the translated code of `nn1` shows the loops are not unrolled. Each MAC costs about 27 BPF instructions, of which only 2 are the multiply-add. The rest are rebuilding and spilling the key (4), the inlined array lookup with its NULL check (about 10), loads with sign-extension (6), and loop bookkeeping.

**Ablations.** Each changes only where values are fetched or stored. All ablations reproduce the NN class counts exactly (10369 / 5631, 2 reps each). Saturation runs used 3 interleaved reps; ns/pkt is the median.

| variant | ns/pkt | Δ vs clean_drop | inferences/s |
| --- | --- | --- | --- |
| clean_drop | 3088 [3078–3271] | — | 279 k |
| abl_w: weights packed into 1 map value per layer | 1800 [1794–1805] | −1288 ns (−42%) | 434 k |
| abl_io: activations in 1 per-CPU struct per stage | 2394 [2343–2550] | −694 ns (−22%) | 347 k |
| abl_w_io: both | **1237** [1235–1259] | −1851 ns (−60%) | 573 k |

**Conclusion.**
- About 60% of Hara's in-kernel NN cost is **data access pattern**, not inference arithmetic. One map access per weight costs about 1.3 µs, and handing activations between tail-call stages through map-update helpers costs about 0.7 µs. The two effects are roughly additive.
- What remains (about 1.24 µs) includes feature extraction plus the session map, measured at about 314 ns in the filter variant.
- **Implication for E1/E5:** "NN vs DT/RF" cost comparisons depend strongly on model layout. For a fair H-model comparison, pack the RF/QS model and the NN weights alike. Report the faithful Hara layout separately as Hara's design.
- The ablations are attribution experiments and candidate optimizations. They are not Hara's code.

## 4d. Per-packet BPF equivalence (E0 continuation, 2026-11-03)

`e0/check_sequence.py` runs the actual BPF entry programs and NN tail-call chain
using system libbpf's `bpf_prog_test_run_opts`, once per packet, on one pinned CPU.
It imports each generated classifier without running its attachment/main loop,
initializes every model map before execution, and creates fresh flow state for
each variant. No live XDP program is attached during this test.

The only test instrumentation is a class/hit-count output array and replacement
of `bpf_ktime_get_ns()` with a map-supplied timestamp. Timestamps are the original
PCAP-relative timestamps plus one second, identical across all variants. This
controls IAT rather than assuming separate wire replays have identical timing.
All original feature arithmetic and the known direction/DT-zero-feature bugs
remain. Output is indexed by PCAP ordinal, so equal class totals cannot hide
packet-level differences. The test also checks that each packet emits exactly
one prediction and observes the final XDP action.

Results on the original synthetic trace, 16,000 packets / 400 flows:

| model | variants compared against faithful | mismatches | missing / duplicate | classes |
| --- | --- | --- | --- | --- |
| DT | hist, clean_pass, clean_drop | 0 | 0 / 0 | 8352 / 7648 |
| NN | hist, clean_pass, clean_drop, abl_w, abl_io, abl_w_io | 0 | 0 / 0 | 10369 / 5631 |

Every faithful/hist/clean_pass packet returns `XDP_PASS`; every clean_drop and
NN-ablation packet returns `XDP_DROP`. There are 11 full variant runs, each with
16,000 predictions. Raw per-packet CSVs and machine-readable summary are in
`e0/sequence/`; the execution log is `e0/sequence_check.log`.
PCAP SHA-256: `ee8f8f1710048b906ec75194516e47a67cec55f6e6e7ef2205fa39c41c90d83a`.
This establishes equivalence on this trace, not dataset accuracy or a proof for
all inputs, multicore execution, or overflow edge cases. Test-run timing is not
used for performance claims.

**Complementary live-wire check.** `e0/add_seqlog.py` creates `<variant>_seq`
copies that log each packet's class by arrival order on one RX queue.
- *Method:* the trace above was replayed from the TG with tcpreplay at 5 kpps through
  attached native XDP, so the real clock was used, not the test-run timestamps.
- *Result:* all 11 runs had 0 mismatches against the `hist` reference: NN in hist ×2,
  clean_pass, clean_drop, abl_w, abl_io and abl_w_io; DT in hist ×2, clean_pass and
  clean_drop. There were exactly two distinct sequence hashes, one per model.
  Logs: `e0/seq/*.bin`.
- *Interpretation:* on this trace, live IAT jitter does not move any packet across a
  split threshold. This adds no coverage beyond the deterministic test above.

Reproduce on the DUT (trace copied from TG `~/eq_trace.pcap` to `~/e0/eq_trace.pcap`):

```bash
sudo python3 ~/e0/check_sequence.py ~/ebpf-classifier ~/e0/variants \
  ~/e0/eq_trace.pcap ~/e0/sequence
```

## 4e. Repaired AF_XDP candidate (E0 continuation, 2026-11-03)

**This is an architectural repair, not a semantics-preserving cleanup of the
faithful COMBINED program.** Its unsafe stack pointer, racing/incomplete flow
state and model fallthrough make faithful output an unsuitable correctness
reference. The repaired candidate puts feature extraction and flow state wholly
in its one userspace worker; XDP only redirects packets. It retains the shipped
AF_XDP 12-16-16-7 NN and DT inference implementations and parameters. The original
AF_XDP NN does not normalize inputs before `run_mlp`; this behavior is preserved,
not silently repaired. No accuracy claim is made for these weights/features.

`e0/make_afxdp_clean.py` creates `~/e0/afxdp-clean` from the pinned xsknf tree,
without changing `~/ebpf-classifier`. Generated application assets are
`e0/afxdp_state.h`, `e0/afxdp_processor.c`, and `e0/afxdp_redirect.c`.

Repairs and scope:

- Calls exactly one selected NN or DT model. RF is explicitly rejected because
  the shipped forest is invalid (B6).
- Removes the per-packet map-lookup syscall and dangling stack pointer by giving
  a single worker exclusive ownership of feature state; no kernel/user-space
  shared-session update race remains.
- Replaces the upstream string hash/`strcmp` operations on binary five-tuples
  with FNV-1a over all key bytes and `memcmp`. Flow state is zero-initialized and
  created before processing the first packet, which also triggers inference.
- Initializes all state before starting workers. Counters are read after workers
  have joined. The pilot enforces one interface, one worker and batch size <=255.
- Uses a 65,536-slot table, capped at 32,768 directional flows, with no eviction
  or timeout. When full, new flows increment `unavailable`; existing flows
  continue. All received packets are ultimately dropped for this benchmark.
- Makes the original parser assumptions explicit: only complete, unfragmented,
  20-byte-header IPv4 TCP/UDP packets are eligible. Other input is counted as
  rejected. Direction remains the author's constant-direction convention.
- Removes per-packet kernel logging. During initial replay, the upstream fill
  ring recycler exited when reserve returned 0, reporting `errno: 0/Success`.
  The candidate retries without losing UMEM addresses, bounded at 100,000
  attempts; exhaustion reports `EAGAIN`. Original failed logs are retained in
  `e0/afxdp_clean_failed/`. Retry counts are emitted on clean shutdown.

**Offline validation:** `e0/check_afxdp_state.py` recomputes all 12 features with
an independent Python implementation, then compares C feature values and the
selected-model prediction against direct calls to the original model functions.
On 16,000 packets / 400 flows there are zero feature or prediction mismatches.
It also tests 32,768 binary keys containing zero bytes, rejects flow 32,769,
and verifies an existing flow still updates after capacity exhaustion.
Results: `e0/afxdp_state_check.log`. The deterministic reference gives DT
8343/7657; NN class counts (0..6) are 487/378/3309/5006/6495/95/230.
These differ from in-kernel models, as expected from their different parameters,
preprocessing and the in-kernel DT zero-feature bug.

Build and validate on DUT after copying the generator and assets into `~/e0`:

```bash
python3 ~/e0/make_afxdp_clean.py ~/ebpf-classifier/xsknf ~/e0/afxdp-clean
cd ~/e0/afxdp-clean
make -o update_submodules examples/mlids/mlids
python3 ~/e0/check_afxdp_state.py ~/e0/afxdp-clean ~/e0/eq_trace.pcap
```

The build skips the upstream automatic submodule-update target because the
separate copy has no Git metadata and already contains the pinned, populated
dependency sources/libraries. Generator refuses an existing destination.

Live replay and throughput are orchestrated from server3 with
`python3 -u e0/run_afxdp_clean.py`. It uses native XDP, AF_XDP **copy mode**, one
RX queue and one worker pinned to guest CPU1 (RX is on CPU0). It restores the
initial RX queue count. Complete application/generator logs and all interval
rates, including low/zero intervals, are saved under `e0/afxdp_clean_runs/`.
These results use two cores and a changed feature-extraction placement; do not
interpret any difference from faithful Hara or in-kernel programs as a
matched-model runtime speedup.

**Live results:** both model replays classified all 16,000 packets / 400 flows,
with no state-unavailable events. NN additionally received and rejected one
background noneligible packet. Live class counts vary slightly from the
controlled-clock offline reference because the IATs differ: NN classes 0..6 are
487/378/3309/5007/6495/95/229 and DT is 8344/7656. These live replays are coverage
checks, not bit-exact comparisons against different timestamps.

Three interleaved load repetitions used 64-byte pktgen UDP, 1,024 configured
flows, four TG threads, and a nominal ten-second generation interval. The table
reports median [min–max]. "Classified / nominal second" is the total inference
count after drain divided by the configured ten seconds, not isolated model
capacity. Actual script/SSH wall times and every interval rate are also retained
in the JSON summary; no top-three rate selection is used.

| repaired model | offered pps | classified / nominal second | unavailable | fill-ring retries per run |
| --- | --- | --- | --- | --- |
| AF_XDP NN (7 classes) | 867026 [858046–869667] | 860679 [847300–865135] | 0 | 0 / 0 / 0 |
| AF_XDP DT (binary) | 874929 [873425–883628] | 873611 [873397–883544] | 0 | 12 / 131 / 1 |

The repaired systems process almost the offered traffic on this workload. This
does not establish their maximum capacity or a model speedup: the TG/virtio path
limits offered load, and the NN is a different model from the in-kernel binary
NN. All eight final replay/load runs finished with clean counters and detached
their XDP programs. Raw results: `e0/afxdp_clean_campaign.log` and
`e0/afxdp_clean_runs/{summary.json,summary.csv}`. The initial fill-ring failure
is retained separately, not omitted from the experimental record.

Environment snapshots are `e0/continuation_environment.txt` and
`e0/continuation_host.txt`. Host CPU governor was `ondemand`, with variable
frequencies. Reading system-wide libvirt VM occupancy was unavailable without
host sudo; the unprivileged session's empty VM list must not be interpreted as
an idle host. These are VM-local diagnostic measurements, not controlled
bare-metal comparisons.

## 4f. Six-thread offered-load pilot and TG cleanup

`e0/run_more_load.sh` tried six TG threads instead of four, with one DUT RX
queue, 64-byte UDP, 1,024 configured flows and eight-second load. This is one
pilot per model, not a repeated performance comparison. Results are preserved
in `e0/more_load_6threads.{log,csv}`:

| clean_drop model | offered pps | DUT received pps | BPF ns/pkt |
| --- | --- | --- | --- |
| filter | 427445 | 426966 | 317.9 |
| DT | 411334 | 409447 | 599.5 |

This attempt did not raise the offered-load ceiling. Its cause has not been
isolated, and this single run must not be used to claim a model regression or
that six threads are inherently slower. Higher-load model-capacity measurements
remain open. Use the retained BPF per-packet costs rather than peak interval
rates from the old harness.

The experiment also exposed a harness hazard: `pgctrl start` starts **all**
configured pktgen devices, but the original `pktgen_tx.sh` cleared only the
threads requested by the next run. A six-thread run followed by four threads
could therefore still run six generators. `testbed/guest/pktgen_tx.sh` now stops
pktgen and clears devices on every generator thread before configuring the
requested ones; the same version is installed on TG. A two-second one-thread
check after the six-thread pilot verifies only `data0@0` remains configured;
see `e0/pktgen_thread_reset_check.log`. All devices are removed after that check.
The AF_XDP campaign above preceded the six-thread pilot.

## 4g. Cause of the offered-load ceiling: host CPU placement (diagnosis; not applied by user decision)

**Measurements** (bare `xdp-bench drop` on the DUT, pktgen with 4 threads, 64 B packets):

| DUT RX queues | TG tx pps | DUT rx pps |
| --- | --- | --- |
| 1 | 898 664 | 898 666 |
| 2 | 829 768 | 829 768 |
| 4 | 735 325 | 735 327 |

- *No loss anywhere:* tx equals rx in every run, so the rate is set by how fast the TG can send.
- *More DUT queues lower the rate:* adding queues means more host threads.
- *Repeat runs are not stable:* an identical repeat later reached only 461 kpps.

**Host-side cause, from fil100 `top -H`, `taskset` and `lscpu`:**

1. **vhost threads inherit their VM's cpuset.**
   - qs-tg's 4 pktgen vCPUs use about 0.95 core each, and its 4 TX vhost threads about 0.55 each.
   - Together that is about 6 cores, i.e. qs-tg's entire 6-CPU cpuset (10–15). More TG threads cannot help, which is consistent with §4f.
2. **The DUT and TG cpusets share physical cores.**
   - The host has 10 cores with 2 hardware threads each; CPU *k* and CPU *k+10* are siblings on the same core.
   - The DUT's CPUs 2–5 are siblings of the TG's CPUs 12–15. TG CPUs 10 and 11 are siblings of host CPUs 0 and 1.
   - So the DUT's measured vCPU can share a physical core with a busy-looping pktgen vCPU. That inflates and adds noise to DUT ns/pkt.
3. **There is another tenant on the host.** The `mtd-*` VMs (another project, not ours to touch) float over CPUs 0–19, and their vhost threads were active during these runs.
4. **The clock frequency varies.** The host governor is `ondemand`, which ran between 1.0 and 3.2 GHz.

**Consequence for the numbers already in this report.**
- E0 *relative*, interleaved comparisons are still usable (§4b–4c).
- Absolute pps and ns/pkt are host-placement dependent and should not be quoted as properties of the classifiers.

**Proposed fix.** Applying it needs a decision from the user; see the summary. Pin our VMs to disjoint *physical* cores and pin their emulator and vhost threads too, for example:
- DUT vCPUs on cores 2–5 (CPUs 2–5 and 12–15);
- TG vCPUs on cores 6–8 (CPUs 6–8 and 16–18);
- vhost/emulator threads on core 9 (CPUs 9 and 19);
- host and mtd VMs on cores 0–1.

Ideally the governor would also be set to `performance`. That is a host-wide setting.

## 8. Remaining work after this continuation

- Track-R is finished for all five days and all model variants (§4h, §4i): **not reproduced with the shipped parameters**. Still open: a documented re-training (Track-H/E1), which will not count as a reproduction.
- E2 prep: the Galvao et al. repo has been cloned and inventoried (`e2/galvao_inventory.md`). It is a BCC XDP program with a 10-tree emlearn RF chained over 3 tail calls, 4 windowed IAT features, and GTP-U decapsulation.
- Per-program hardware cycles/instructions and a stronger offered-load setup
  are still open. Host governor/occupancy and variable frequency limit present
  performance interpretation.
- The AF_XDP repair is validated for the single-worker pilot, not multicore
  deployment, long-lived unbounded traffic, or accuracy equivalence with the
  unsafe original implementation.
- E1–E5, the three-dataset harmonized protocol and G-RF/QS implementations have
  not started. The project's decision gates remain unchanged.

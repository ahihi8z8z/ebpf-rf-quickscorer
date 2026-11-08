# Experiment Plan: Multi-stage QuickScorer for Random Forest Inference in eBPF/XDP

**Status:** Pre-registered pilot proposal; no experimental result has been established.
**Research target:** An implementation-level contribution, not a new Random Forest or QuickScorer algorithm.
**Scope:** Same packet-processing task and reproducible evaluation of DT, lightweight NN, and RF, followed by a matched-model comparison of RF execution mechanisms.

## 1. Research motivation and falsifiable claims

Hara and Sasabe (Computer Networks 2024) found that a lightweight quantized NN improved detection of several attack classes over a shallow DT, but incurred higher packet-processing costs. Their paper also compared in-kernel XDP with AF_XDP. Critically, the DT comparison was not a Random Forest comparison.

We investigate whether an RF executed using QuickScorer can occupy a useful intermediate accuracy-cost point while respecting eBPF verifier, memory, and execution constraints. The paper's technical contribution, if supported, will be an eBPF-specific multi-program QuickScorer runtime, not the known idea of grouping trees.

Two distinct hypotheses must be tested:

- **H-model (application relevance):** On multiple independently collected traffic datasets, an appropriately sized RF can offer a competitive accuracy-versus-inference-cost point relative to a shallow DT and a lightweight NN. This is a motivation for, not the novelty of, QuickScorer.
- **H-runtime (main contribution):** For the **same trained, quantized RF**, multi-program QuickScorer enlarges the deployable RF envelope and/or improves inference efficiency against a carefully tuned RF tree-walk + tail-call implementation.

Never use a cross-model accuracy difference as evidence that QuickScorer is faster than RF tree-walk. Never use different RF sizes to claim a matched-model speedup.

## 2. Prior-work baselines and reusable source code

| ID | Baseline | Provenance | Role |
| --- | --- | --- | --- |
| H-DT | Shallow DT, in-kernel XDP | Hara & Sasabe 2024 source | Reproduce a lightweight tree classifier |
| H-NN-XDP | Quantized lightweight NN, in-kernel XDP, layer-wise tail calls | Hara & Sasabe 2024 source | Strong NN reference for classification and XDP throughput |
| H-NN-AFXDP | Quantized NN via AF_XDP (poll variant) | Hara & Sasabe 2024 source/submodule | Architectural reference; not a matched in-kernel comparison |
| G-RF | RF tree-walk/emlearn using XDP tail calls | Galvao et al. 2026 source | **Main RF runtime baseline**; tune tree grouping |
| QS-1 | QuickScorer, single eBPF program | Existing team implementation | Quantify whether staging helps QuickScorer |
| QS-G | Proposed tree-grouped, multi-program QuickScorer | New implementation | Candidate contribution |
| RF-C | Identical RF in C userspace | Common exporter | Numeric/reference and isolated inference sanity check |

**Hara 2024:** https://doi.org/10.1016/j.comnet.2024.110188

**Official paper-linked Hara code:** https://github.com/oakeshott/ebpf-classifier

Repository includes `dt-filter/`, `nn-filter/`, `xsknf/` (submodule), `script/`, `tests/`; README describes XDP/TC and AF_XDP execution. The README also contains potentially stale paths/clone commands: inspect the actual checked-out tree. Pin the main commit and submodule commits. Reproduce the source **before** adapting it; do not silently change architecture, feature counts, tensor dimensions, debug logging, or training model.

**Galvao RF source:** https://github.com/jose-galvao/eBPF-Classification

**QuickScorer algorithm prior art:** Lucchese et al., SIGIR 2015 (including BlockWise-QS); Vasiloudis et al., SIGIR 2019. Tree grouping and feature partition must not be claimed as new algorithms.

## 3. Multiple datasets are mandatory (minimum three)

| Dataset | Why included | Public raw traffic | Evaluation obligation |
| --- | --- | --- | --- |
| **D1: CIC-IDS2017** | Hara paper reference and reproduction anchor | PCAP and labelled flows | Reproduction + all harmonized experiments |
| **D2: UNSW-NB15** | Independent enterprise/security traffic and attack taxonomy | PCAP and CSV/labels | All harmonized experiments |
| **D3: CICIoT2023** | Different IoT traffic environment and large attack corpus | PCAP and CSV/labels | All harmonized experiments |

Official dataset sources:
- CIC-IDS2017: https://www.unb.ca/cic/datasets/ids-2017.html
- UNSW-NB15: https://research.unsw.edu.au/projects/unsw-nb15-dataset
- CICIoT2023: https://www.unb.ca/cic/datasets/iotdataset-2023.html

**Mandatory across D1-D3:** model quality, model complexity, verifier/deployability, isolated inference performance, and end-to-end XDP evaluation with dataset-derived traffic. A missing dataset is an **incomplete pilot**, not a negative result.

### 3.1 Two separate evaluation tracks

**Track R - Hara reproduction:** Reproduce Hara's original CIC-IDS2017 task, features, label mapping, training configuration, quantization, and published binary/multiclass experiments as closely as source permits. State reproduced/not reproduced and exact modifications. Do not modify its task to make the original publication numbers easier to match.

**Track H - harmonized three-dataset evaluation:** Define **one online-computable feature schema** used by DT, NN, and RF on each dataset. Prefer features available from packet headers and bounded per-flow state, such as packet length, direction, inter-arrival times, and TCP flags. Freeze the schema **before** model selection. A feature is eligible only if it can be computed using packets visible up to the inference trigger. Recompute features from PCAP; do not substitute full-flow CSV features containing future traffic.

For every dataset, report a binary benign/attack task and a native multiclass task, subject to verified class support. Use dataset-specific label mappings. Do not merge incompatible taxonomies or compare raw macro-F1 across different class sets as if they described the same task.

### 3.2 Data integrity and repeatability

- Pin dataset download/version, PCAP subsets, checksums, data-processing source, and class mapping. Report the exact samples/classes excluded and why.
- Establish packet-to-flow-to-label linkage before replay. If linkage or timestamps are insufficient to derive honest early-flow labels, document it and use valid labelled subsets; never infer per-packet labels from full-flow properties without justification.
- Fix the inference trigger **N packets** (initial pilot: N=8 if each dataset supports it) and use the identical flow timeout, direction conventions, counters, and feature normalization for every model. Report the fraction of flows that reach N; do not silently drop short flows from the denominator.
- Split by capture session/day/device/host where feasible, not random individual packets. Eliminate duplicates, train/test leakage, and identifiers serving as shortcuts. Freeze splits and preprocessing using training data only.
- Use >=3 independent model seeds for DT, NN, and RF. Preserve an untouched final evaluation partition. Report class distribution, macro-F1, per-class F1, balanced accuracy, false-positive rate, and coverage at N packets.
- **Within-dataset generalization** is mandatory. Cross-dataset transfer is a separate question and is **not** claimed unless labels/features and validation protocol genuinely support it.

## 4. Experimental sequence and decision gates

### E0 - Reproduce Hara's NN and DT baselines (D1)

**Question:** Are the paper's actual NN/DT implementations runnable and numerically faithful in the available environment?

1. Clone and pin `oakeshott/ebpf-classifier`, including `xsknf` submodule. Record build dependencies and kernel/clang/BCC versions.
2. Inventory binary versus multiclass model support, model weights, feature extraction, quantization, any hard-coded input/output dimensions, and debug/per-packet reporting.
3. Run author-provided tests and CIC-IDS2017 reference inference. Repeat at least one published NN versus DT quality comparison.
4. Build native XDP NN and DT. Test AF_XDP NN separately, subject to host/NIC support.
5. Separate **faithful author reproduction** from a **clean performance variant** (debug prints/per-packet telemetry disabled for both, otherwise the same inference semantics).

**Output:** `hara_reproduction.md`: pinned commits, exact commands, model and feature inventory, paper-versus-local metrics, deviations, and known blockers.

**Gate:** If the original code cannot support the intended multiclass task, implement a documented extension and validate against an independent reference. Do not claim reproduction of unpublished settings.

### E1 - Is RF a meaningful alternative to the lightweight NN? (D1-D3)

**Question:** Does RF offer a credible accuracy-versus-complexity point across more than one dataset?

1. Train DT, lightweight NN based on Hara's capacity (with necessary input/output adaptation), and RF using identical Track-H features/splits.
2. Evaluate RF forest sizes T in {16,32,64,128,256}, depths D in {4,6,8}; prune the sweep after an initial small pilot. Train at least three seeds.
3. Quantize NN and RF for deployable integer inference. Report floating-point reference, quantized reference, and any loss caused by quantization separately.
4. Compare model quality (macro-F1, per-class F1, balanced accuracy, false-positive rate), number of operations/nodes, and model bytes. Profile C inference to remove XDP integration effects at this stage.
5. Summarize each dataset separately, then describe patterns that recur across D1-D3. Do not pool raw scores across different class distributions.

**Decision:** Continue with the QuickScorer paper story only if at least two datasets show a defensible RF operating point: useful quality at plausible deployment cost. Record a failure on D3 rather than replacing D3 with a friendlier dataset.

### E2 - Establish the real eBPF scalability limitation (D1-D3)

**Question:** Where do QS-1 and tuned G-RF cease to load, execute correctly, or remain efficient?

For a representative model grid sampled from all three datasets:

- Compile, verify, and load the **same exact trained RF** with G-RF, QS-1, and a common quantized reference.
- Record success/failure, verifier diagnostics, JIT/code size, program instruction counts, stack, map/model memory, verifier time, and prediction correctness.
- Tune G-RF grouping within its supported program/tail-call bounds. Verify input representation and vote/soft-score semantics remain identical.
- If QS-1 fails, diagnose whether the failure stems from verifier complexity, generated code shape, memory layout, bounds, stack, or other causes. Compare a bounded-loop/data-driven QS representation if this could solve the failure without staging.

**Decision:** Do not build multi-stage QS solely because QS-1 fails. Advance only with a demonstrated failure mode that stage partitioning plausibly fixes, or an explicit matched-model performance hypothesis.

### E3 - Implement and validate multi-stage QuickScorer (D1-D3)

**Question:** Does QS-G create a capability missing from QS-1 or tuned G-RF?

1. Partition whole trees across XDP programs; first test G in {1,2,4,8}. Tail calls chain stages.
2. Each stage evaluates its full assigned trees with QuickScorer and accumulates class scores; the final stage returns the class.
3. Transfer state using correctly bounded packet metadata or a justified map design; validate CPU concurrency, misses, stack lifetime, and reset semantics.
4. Require bit-exact agreement with a common quantized RF reference for thresholds, ties, class scores, and integer overflow edge cases.
5. Compare equal-tree grouping against node/work-balanced grouping; do not invent predicate-level partitioning unless E2 demonstrates why whole-tree grouping cannot resolve the measured failure.
6. Repeat verifier/deployability sweeps over **all three datasets**, and retain failed configurations in the results.

**Output:** `deployability_matrix.csv` with accepted/rejected model variants and exact failure reasons.

**Gate:** If tuned G-RF already covers the desired model envelope and QS-G shows no credible efficiency advantage, stop; do not describe tree grouping itself as an algorithmic novelty.

### E4 - Matched-model inference cost (D1-D3)

**Question:** At fixed RF and fixed features, is QS-G cheaper than tuned G-RF?

For all common-loadable RF configurations on D1-D3, report:

- cycles/inference and p50/p95/p99 inference runtime (same timer/harness);
- CPU instructions/inference where measurable;
- tail calls, map accesses, model/program memory and handoff bytes;
- class agreement and inference-unavailable events;
- null tail-call-chain overhead and number-of-stages ablation.

Run interleaved baseline/proposed repeats; isolate one-core measurements and record CPU governor, frequency, NUMA, kernel and XDP mode. Do not compare runtime of RFs with different numbers of trees or classifiers with different input feature costs.

**Gate:** Any performance claim must be repeatable and have a plausible kernel-level explanation; provide uncertainty intervals and failures, not only a best-case speedup.

### E5 - End-to-end XDP trade-off against Hara's NN (D1-D3)

**Question:** Does QS-G produce a useful model-quality-versus-packet-processing-cost point once the classifier is placed in a real datapath?

Evaluate H-DT, H-NN-XDP, G-RF, and QS-G in the **same native XDP frontend**, with identical feature extraction, N-packet inference trigger, flow-state limits, and forwarding action. Keep H-NN-AFXDP as a separately reported architecture alternative; do not claim that its differences arise from the model alone.

Use two complementary workloads on **each** dataset:

1. **Labelled PCAP replay:** Validate event timing, prediction/label association, number of eligible flows, and per-class effectiveness. Respect capture-time order where possible.
2. **Controlled offered-load test:** Generate reproducible traffic with packet sizes, flow lifetimes, features, and inference-trigger rates derived from each dataset; increase load to saturation. Do not represent synthetic traffic as an authentic replay or report packet throughput as if every packet triggers inference.

Measure:

- offered pps, received/forwarded pps, loss/drop rate, CPU use, cores, and throughput at a predefined acceptable loss threshold;
- actual inference events/s, cycles/inference, latency, map memory, and feature-only versus model-only versus combined overhead;
- macro-F1/per-class F1/FPR for the labelled replay, separately from raw throughput;
- sensitivity to flow arrival rate, concurrency, and stage count;
- system behavior on missing state/tail-call failure (mark inference unavailable; use a documented fail-open/pass-through policy for the pilot).

Compare the **accuracy-throughput/resource Pareto points** separately for D1, D2, and D3. Quality comparisons across model families are valid only with a shared Track-H task and features. Runtime-mechanism speedups are valid only for the same RF.

## 5. Results and minimum evidence for a paper

The pilot must produce these reusable artifacts:

1. `hara_reproduction.md` - faithful source reproduction and implementation audit.
2. `dataset_protocol.md` - three datasets, exact label/split schemes, N-packet feature extraction and leakage audit.
3. `model_quality.csv` - per-dataset/per-class DT, NN and RF results with seeds.
4. `deployability_matrix.csv` - accepted/rejected RF variants for G-RF, QS-1 and QS-G, including verifier reasons.
5. `inference_bench.csv` - matched-model runtime, cycles, maps, tail calls and uncertainty.
6. `xdp_performance.csv` - end-to-end pps, packet loss, inference rate, CPU, memory, attack detection by dataset.
7. `pilot_report.md` - answers to H-model and H-runtime, failures, figure-ready plots, stop/go recommendation.

**Paper GO-A (deployability):** QS-G runs practically valuable RF configurations that a well-tuned RF baseline cannot run, across representative models from multiple datasets, with correct predictions and measured viable overhead.

**Paper GO-B (efficiency):** QS-G is repeatedly better on meaningful matched-model inference cost compared with G-RF, with evidence explaining why; E5 must establish whether the benefit survives end-to-end processing.

**NO-GO:** Across the tested useful models, tuned G-RF matches or exceeds QS-G's deployable coverage and runtime efficiency, or the only benefit is an artificial model configuration with no quality/application value. Keep the negative result and stop this paper claim.

**No-go on multi-dataset evidence:** A finding seen on only one dataset is labelled dataset-specific; do not generalize it to traffic classifiers broadly. Any inability to complete D1-D3 is reported transparently.

## 6. Execution order for the coding agent

1. Reproduce Hara original code on CIC-IDS2017; document source commit, submodules, paper alignment, model output dimensions and debug effects.
2. Construct one common N-packet, online-feature and label pipeline for CIC-IDS2017, UNSW-NB15, CICIoT2023. Freeze split manifests.
3. Train DT, NN and RF under this harmonized protocol; finish E1 before investing in complex staging.
4. Port and tune Galvao RF baseline; run E2; record the *actual* failure mechanism.
5. Implement minimal tree-grouped QS only if E2 gate passes; correctness before benchmarking.
6. Run E3-E5 on D1-D3; produce matrices and plots; apply GO/NO-GO rules without adding speculative algorithms.

**Out of scope:** QAT/retraining, online model updates, predicate-level QS split, new attack detection models, cross-dataset domain adaptation, or claiming a new tree-ensemble algorithm.

## References

- Hara, T. and Sasabe, M. (2024), Computer Networks 240, 110188: https://doi.org/10.1016/j.comnet.2024.110188
- Hara official paper-linked source: https://github.com/oakeshott/ebpf-classifier
- Galvao et al. (2026), source: https://github.com/jose-galvao/eBPF-Classification
- QuickScorer, SIGIR 2015: https://doi.org/10.1145/2766462.2767733
- Vasiloudis et al. (2019), Block-distributed Gradient Boosted Trees: https://arxiv.org/abs/1904.10522
- CIC-IDS2017: https://www.unb.ca/cic/datasets/ids-2017.html
- UNSW-NB15: https://research.unsw.edu.au/projects/unsw-nb15-dataset
- CICIoT2023: https://www.unb.ca/cic/datasets/iotdataset-2023.html

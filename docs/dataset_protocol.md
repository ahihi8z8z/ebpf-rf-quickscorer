# Track-H dataset protocol (D1 CIC-IDS2017, D2 UNSW-NB15, D3 CICIoT2023)

**Status:** schema v1 frozen on 2026-11-04, before any model selection. Results are in `e1_report.md`. Code is in `trackh/`.

This protocol implements experimental.md §3.1 (Track H) and §3.2. The same feature schema, inference trigger, flow timeout, direction convention, split rule and class-support rule are used for every model family (DT, NN, RF) and every dataset. Anything that differs per dataset is listed in §5 below.

## 1. Online feature schema v1 (`trackh/flowfeat.c`)

**Flows**
- A flow is the bidirectional IPv4 5-tuple. Ports are used for TCP and UDP; ICMP, other protocols and non-first fragments get port 0.
- The **initiator** is the source of the flow's first packet.
- A flow ends after **120 s idle**; the next packet starts a new flow. There is no FIN/RST handling, so the same rule holds for every protocol.
- IPv6 and non-IP frames are counted and excluded.

**Inference trigger: the N-th packet of a flow, N = 8.** At that packet, the 17 features below are computed from packets 1..N. They need O(1) per-flow state, integer arithmetic only, and nothing seen after packet N:

| # | feature | definition |
|---|---|---|
| f0 | proto | IP protocol |
| f1 | resp_port | destination port of packet 1 (0 if none) |
| f2 | n_fwd | packets from the initiator |
| f3 | bytes_fwd | sum of IP total length, initiator → responder |
| f4 | bytes_bwd | sum of IP total length, responder → initiator |
| f5 | len_first | IP length of packet 1 |
| f6 | len_min | minimum IP length |
| f7 | len_max | maximum IP length |
| f8 | dur_us | t_N − t_1 (µs, saturating at 2^31−1) |
| f9 | iat_min_us | minimum inter-arrival time |
| f10 | iat_max_us | maximum inter-arrival time |
| f11–f15 | n_syn, n_fin, n_rst, n_psh, n_ack | TCP flag counts (0 for non-TCP) |
| f16 | n_dirchg | number of direction switches between consecutive packets |

**Excluded on purpose:**
- IP addresses, the source port, TTL and the TCP window. These are testbed identifiers and known shortcuts in these datasets.
- Payload, because XDP parsing cost depends on it.

`resp_port` is kept: it is the service port, it is legitimately available online, and Hara also uses ports. A no-port ablation is reported so its influence is visible.

**Input representation per model family**
- **Trees** (DT and RF) use the raw integers. Integer features make floor(threshold) exact.
- **The NN** uses an 8-bit monotone log quantizer computed with shifts in eBPF: q(x) = 4·⌊log2(x+1)⌋ plus the next 2 mantissa bits, range 0..127 (`train_e1.py: logq`).

**Validation.** `trackh/flowfeat_ref.py` is an independent Python implementation written from this table. It agrees exactly with `flowfeat` on `eq_trace.pcap` (400/400 flows). On the first 3 M packets of the Wednesday capture, the two implementations also agree exactly: 2 780/2 780 triggered flows, 0 mismatches (`results/flowfeat_validation/compare.txt`). That check found one bug, in the comparison key of the reference script, not in the extractor: one NTP client starts three flows in the same microsecond.

## 2. Labels (`trackh/label_flows.py`)

Each triggered flow gets the dataset's native label through packet-to-flow-to-label linkage on the flow's **first-packet time**.

- **D1 CIC-IDS2017.** The official TrafficLabelling CSVs (CICFlowMeter). A flow matches the rows of its direction-free 5-tuple whose minute window, widened by ±2 min, contains the flow's start minute. CSV times are UTC−3 on a 12-hour clock without AM/PM; this is the rule validated in Track-R. If the candidates are {BENIGN, attack}, the flow is labelled with the attack. More than one attack label makes the flow ambiguous, and it is excluded.
- **D2 UNSW-NB15.** The official Argus records UNSW-NB15_1..4.csv (`Stime`, `Ltime`, `attack_cat`). A flow matches the rows of its direction-free 5-tuple with Stime − 2 s ≤ t_first ≤ Ltime + 2 s. A blank `attack_cat` means Normal. The {Normal, attack} rule is the same as D1.
  *D2 notes (2026-11-04, before any D2 model was trained):*
  - Argus protocol names are mapped to IP protocol numbers through `/etc/protocols`. Names with no number (`unas`, `any`, `arp`, a few rare names) cannot match an IPv4 flow; those records are ignored.
  - A flow with no matching record is **unlabelled and excluded**. It is never defaulted to Normal. The official CSVs have time gaps; for example, 17-2 00:47–01:03 UTC has no records at all. Over the two days, 65 414 triggered flows (3.9 %) are excluded this way and 395 are ambiguous.
  - The 22-1 files 6, 7 and 13–53 are merged pcapng captures whose timestamps step backwards between merged sources (3.5 M packets clamped to monotone time by `flowfeat`). Timing features on that day carry this artifact.
  - Download integrity: the first fetcher resumed with `curl -C -` without `--fail`, so two files got an HTTP error body written at offset 0 (22-1/49.pcap: "403 FORBIDDEN", 16 B; 17-2/23.pcap: a SharePoint HTML page). Both were repaired by re-fetching that byte range (`data/tools/repair_range.py`). After the repair, all 80 pcaps pass a full record-structure walk (`data/tools/pcapcheck`). The exception is 17-2/27.pcap, whose last record is truncated identically on the server.
- **D3 CICIoT2023.** Each capture file is one attack session. The dataset's own CSV labels every window of a file with that file's attack, and **we follow that convention: every flow of a capture gets the capture's class.**

  *Amendment (2026-11-04, made before any D3 model was trained).* The protocol first planned to relabel flows in attack files that touch no attacker address as `Background`. That plan was dropped, for two reasons:
  - The dataset does not publish the attacker addresses.
  - `trackh/ciciot_hosts.py` shows the attacking Raspberry Pis change address between captures (DHCP). For example, the top initiators are .186/.196/.17/.65/.20/.42 in DDoS-PSHACK but .123/.196/.65/.17/.42/.12 in DDoS-ACK_Fragmentation. Any per-file attacker list would therefore be an ad-hoc heuristic.

  **Limitation:** benign background flows inside attack captures inherit the attack label, exactly as in the official CSVs. Part of the D3 task is therefore capture-session recognition. The effect is largest for the small web and malware captures (Backdoor, BrowserHijacking, CommandInjection: a few thousand flows, mostly background). D3 results are read with this caveat, and per-class F1 is reported so that it stays visible.

## 3. Splits (`trackh/make_dataset.py`)

**Time-block split.** Each flow belongs to the time block of its first packet:
- 300 s blocks for D1 and D2 (absolute time, capture days);
- 60 s blocks for D3 (relative to each capture file, because each file is a separate session).

Blocks are assigned train, train, train, val, test by block index mod 5. As a result:
- no flow is shared between partitions;
- no 5-minute window is shared between partitions;
- every attack lasting at least 5 blocks reaches all three partitions.

This is a **within-capture temporal split**. It is not a cross-campaign or cross-site split, so the plan's "within-dataset generalisation" applies and cross-dataset transfer is not claimed.

**Test partition.** It is touched only to report final numbers. Model selection (depth, T, D, NN epoch) uses val.

**Caps.**
- Train is capped at 200 000 flows per class, uniformly with sampling seed 12345, which is independent of the model seed.
- Val and test are capped the same way to bound compute.
- Caps are reported as the n_train, n_val and n_test columns.

**Duplicates.** Identical feature vectors occur naturally, for example in floods. Every row is kept. The share of test vectors that also appear in train with the same label is reported per dataset, and a test-minus-duplicates sensitivity is given.

## 4. Tasks and class support

- **Binary.** Benign (BENIGN / Normal / Benign) versus everything else.
- **Multiclass, native taxonomy.**
  - D1: Benign, DoS, DDoS, PortScan, BruteForce, WebAttack, Bot, Infiltration, Heartbleed.
  - D2: the 10 UNSW `attack_cat` values.
  - D3: the authors' 8 groups (Benign, DDoS, DoS, Mirai, Recon, Spoofing, Web, BruteForce).
- **Support rule.** A class enters the multiclass task only if it has at least 100 train, 30 val and 30 test flows. Excluded classes stay in the binary task, and their counts are reported.

## 5. Dataset sources and subsets (pinned)

| dataset | source | captures used | checksums |
|---|---|---|---|
| D1 CIC-IDS2017 | Wednesday: server3 `~/ebpf/data/cicids2017/wed.pcap`; Mon/Tue/Thu/Fri: HF mirror `bencorn/CICIDS2017` | all 5 days | `trackr/data/cicids2017/fetch.log`, `results/trackr/dataset_sha256.txt` |
| D2 UNSW-NB15 | official UNSW SharePoint (anonymous share link on the UNSW-NB15 page) | all 80 pcaps (22-1-2015: 53, 17-2-2015: 27) + UNSW-NB15_1..4.csv | `data/unsw/list.tsv.log` (sizes match the listing; SHA-256 recorded) |
| D3 CICIoT2023 | HF mirror `bencorn/CIC-IoT-2023` (PCAP/) | every class: all Benign_Final files, all files of classes with ≤ 2 files, and the first file of each larger class (39 files, 49.4 GB of 605 GB) | `data/ciciot/list.tsv.log` (SHA-256 verified against the mirror's LFS oids) |

The D3 subset is a fixed rule, written down before any result. Large flood classes are therefore represented by their first 2 GB capture file. Per-class flow counts are reported.

## 6. Coverage and data-integrity results

Sources: `results/datasets/<ds>.json` (make_dataset) and `results/datasets/<ds>_audit.json` (dataset_audit).

| | D1 CIC-IDS2017 | D2 UNSW-NB15 | D3 CICIoT2023 (subset) |
|---|---|---|---|
| triggered labelled flows | 602 322 | 1 590 194 | 5 867 667 |
| excluded: unlabelled / ambiguous | 139 / 0 | 65 414 / 395 (CSV time gaps) | 0 / 0 (file-level labels) |
| train / val / test rows | 376 392 / 107 068 / 118 862 | 958 018 / 316 942 / 315 234 | 4 271 710 / 723 726 / 872 231 |
| multiclass classes (support rule) | Benign, Bot, BruteForce, DDoS, DoS (PortScan, WebAttack, Infiltration, Heartbleed excluded) | Normal + 8 attacks (Worms excluded) | all 8 groups |
| coverage at N = 8 (share of all flows reaching packet 8) | 0.327 (PortScan 0.13 %) | 0.805 (Recon 0.59, Shellcode 0.50) | 0.565 (ACK-Frag 0.5 %, HostDiscovery 1.5 %, PortScan 10 %) |
| test rows duplicated in train (all / attack) | 1.2 % / 0 % | 10.1 % / 0 % | 0 % / 0 % |
| RF T64D8 test macro-F1, binary: all 17 / no resp_port | 0.992 / 0.990 | 0.910 / 0.910 | 0.745 / 0.753 |
| RF T64D8 test macro-F1, multiclass: all 17 / no resp_port | 0.913 / 0.720 | 0.479 / 0.399 | 0.519 / 0.501 |

Results without the test-train duplicates differ by ≤ 0.0004 macro-F1 in every cell.

**Reading the coverage numbers.** Coverage at N is a property of the trigger, not of the model. Scan-like and fragment floods mostly never reach packet 8, so the online system **does not see them at all** at N = 8. This is the price of the fixed-N trigger, and it applies equally to every model family.

**Reading the resp_port ablation.** In D1, multiclass separation relies strongly on the service port. Binary detection does not.



## 7. Validity issue found in E5: oversize frames (capture offload artefact)

*Added 2026-11-08, after E5. Schema v1 and every E1–E4 result are unchanged. This section limits how those results may be read.*

**What the captures contain.** Some captures hold IP packets larger than the 1500-byte MTU. They were recorded on a host with segmentation/receive offload (TSO/GRO) enabled, so several wire packets were merged into one record (up to about 12 kB).

Share of Track-H flows (all splits) with `len_max` > 1500:

| dataset | all flows | by class |
|---|---|---|
| D1 CIC-IDS2017 | 31.9 % | **DDoS 99.7 %**, DoS 81.2 %, Benign 21.5 %, Bot 6.5 %, BruteForce 0 % |
| D2 UNSW-NB15 | 0 % | — |
| D3 CICIoT2023 | 1.7 % | 0.2 % (DDoS) to 17 % (Spoofing) |

**Consequence.**
- On D1, `len_max` and the byte sums partly encode *how the capture host was configured*, not only the attack.
- A real 1500-byte-MTU link cannot carry these frames. E5 drops them before replay (`e5_pcapfix.py`; 4–19 % of D1 packets).
- On the replayable traffic, the D1 binary DT predicts benign for 98 % of the DDoS flows in replay slice 3: 661 of 12 347 detected. On the original capture features it detected 12 346 of 12 349.
- So the D1 offline macro-F1 (0.99 binary) is **not reachable on a real link**. On the replayed slices it is 0.40–0.47 for every model family.
- The XDP pipeline itself is exact: online equals offline on the replayed packets (§E5 in `pilot_report.md`).
- D2 is unaffected. D3 is only marginally affected, which is consistent with its replay F1 being close to offline.

**Rule for reporting.**
- D1 model-quality numbers are labelled "capture-feature quality".
- The D1 RF > DT multiclass advantage (E1 §2) may rest partly on this artefact. It must not be presented as evidence of application value without a retrain on offload-free features, which is out of the pilot's scope.

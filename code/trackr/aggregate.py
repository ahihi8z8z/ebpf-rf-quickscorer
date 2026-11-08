#!/usr/bin/env python3
"""Track-R: aggregate Hara shipped-model results over all CIC-IDS2017 days processed by run_day.sh.
    python3 aggregate.py out/days monday tuesday wednesday thursday friday > out/trackr_all.md
Binary: attack = any non-BENIGN label, packets with a definite label and a prediction; confusion
counts are summed over days (pooled per-packet metrics, as the paper evaluates one pooled dataset).
7-class: CIC labels mapped to the paper's classes (Heartbleed has no stated class: excluded and
counted). AF_XDP NN class order assumed alphabetical (0 Botnet ... 4 Normal ... 6 Web attack)."""
import json, os, sys
import numpy as np

D, DAYS = sys.argv[1], sys.argv[2:]
P7 = ['Botnet', 'Brute force', 'DoS', 'Infiltration', 'Normal', 'Portscan', 'Web attack']
from aggregate_map import map7

def binm(c):
    tp, fp, fn, tn = c
    p = tp / max(tp + fp, 1); r = tp / max(tp + fn, 1)
    return dict(acc=(tp + tn) / max(tp + fp + fn + tn, 1), precision=p, recall=r,
                f1=2 * p * r / max(p + r, 1e-12), fpr=fp / max(fp + tn, 1), n=tp + fp + fn + tn)

BIN = [('dir_ns', 'kernel semantics, unbounded table'), ('dir_ns_lru1024', 'kernel semantics, LRU 1024 (deployed)'),
       ('bidir_ns', 'bidirectional sessions')]
N7 = [('dir_raw', 'dir, no normalisation (as shipped)'), ('dir_norm', 'dir, binary normaliser'),
      ('bidir_raw', 'bidir, no normalisation'), ('bidir_norm', 'bidir, binary normaliser')]
tot = {(v, m): np.zeros(4, np.int64) for v, _ in BIN for m in (0, 1)}
tot7 = {v: np.zeros((7, 7), np.int64) for v, _ in N7}
perday, lab_tot, excl = [], {}, 0
for day in DAYS:
    meta = json.load(open(f'{D}/{day}.lab.json')); cls = meta['classes']
    lab = np.load(f'{D}/{day}.lab.npy'); NC = len(cls)
    for k, n in meta['per_class'].items(): lab_tot[k] = lab_tot.get(k, 0) + n
    y_all = lab > 0
    for v, _ in BIN:
        c = np.fromfile(f'{D}/{day}_{v}.cls', np.uint8).reshape(-1, 2)
        for m in (0, 1):
            ok = (lab < NC) & (c[:, m] <= 1); y, yh = y_all[ok], c[ok, m] == 1
            cnt = np.array([(y & yh).sum(), (~y & yh).sum(), (y & ~yh).sum(), (~y & ~yh).sum()])
            tot[(v, m)] += cnt
            if v == 'dir_ns': perday.append((day, 'DT' if m == 0 else 'NN', binm(cnt), meta['per_class']))
    m7 = np.array([map7(c) for c in cls] + [-1] * (256 - NC))
    t7 = m7[lab]
    excl += int(((lab < NC) & (t7 < 0)).sum())
    for v, _ in N7:
        p = np.fromfile(f'{D}/{day}_nn7_{v}.nn7', np.uint8); ok = (lab < NC) & (t7 >= 0) & (p < 7)
        np.add.at(tot7[v], (t7[ok], p[ok]), 1)

print('## Labelled packets per CIC label (all processed days)\n')
print('| label | packets |\n|---|---|')
for k, n in sorted(lab_tot.items(), key=lambda x: -x[1]): print(f'| {k} | {n} |')
print(f'\nDays: {", ".join(DAYS)}. Heartbleed packets excluded from 7-class scoring: {excl}.\n')
print('## Binary, pooled over days (paper Table II: DT acc 0.977 / F1 0.954; NN 0.975 / 0.952)\n')
print('| features / state | model | packets | acc | precision | recall | F1 | FPR |\n|---|---|---|---|---|---|---|---|')
res = {}
for v, desc in BIN:
    for m in (0, 1):
        r = binm(tot[(v, m)]); res[f'{v}/{"DT" if m == 0 else "NN"}'] = r
        print(f'| {desc} | {"DT" if m == 0 else "NN"} | {r["n"]} | {r["acc"]:.3f} | {r["precision"]:.3f} | '
              f'{r["recall"]:.3f} | {r["f1"]:.3f} | {r["fpr"]:.3f} |')
print('\n## Binary per day (kernel semantics, unbounded)\n')
print('| day | model | packets | acc | F1 | FPR | attack share |\n|---|---|---|---|---|---|---|')
for day, m, r, pc in perday:
    att = sum(n for k, n in pc.items() if k != 'BENIGN') / max(sum(pc.values()), 1)
    print(f'| {day} | {m} | {r["n"]} | {r["acc"]:.3f} | {r["f1"]:.3f} | {r["fpr"]:.3f} | {att:.3f} |')
print('\n## AF_XDP 7-class NN, pooled (paper Table III: NN accuracy 0.974)\n')
print('| variant | packets | accuracy | macro recall | ' + ' | '.join(f'recall {c}' for c in P7) + ' |')
print('|---|---|---|---|' + '---|' * 7)
for v, desc in N7:
    M = tot7[v]; n = M.sum(); rec = M.diagonal() / np.maximum(M.sum(1), 1)
    present = M.sum(1) > 0
    res[f'nn7/{v}'] = dict(n=int(n), acc=float(M.trace() / max(n, 1)), recall=rec.tolist(), confusion=M.tolist())
    print(f'| {desc} | {n} | {M.trace() / max(n, 1):.3f} | {rec[present].mean():.3f} | ' +
          ' | '.join(f'{x:.3f}' if present[i] else '-' for i, x in enumerate(rec)) + ' |')
json.dump(res, open(os.path.join(D, 'trackr_all.json'), 'w'), indent=1, default=lambda o: o.item())

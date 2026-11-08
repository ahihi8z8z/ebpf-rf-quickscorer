#!/usr/bin/env python3
"""Data-integrity audit for one Track-H dataset (experimental.md §3.2).
    python -I dataset_audit.py <d.npz> <out.json> <prefix>...      (prefixes as given to make_dataset)
1. Coverage at N: fraction of flows (all flows, from <prefix>.flows + .flab labels) that reach the
   N-th packet, overall and per native label (packet-to-flow linkage identical to the triggered set).
2. Train/test duplicates: share of test rows whose (feature vector, label) also occurs in train.
3. Shortcut ablation: RF T64 D8 (seed 0) with and without f1 resp_port, binary and multiclass,
   validated on val, reported on test (and on test minus train duplicates)."""
import collections, json, os, sys
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from label_flows import FLOW


def main():
    npz, out, prefixes = sys.argv[1], sys.argv[2], sys.argv[3:]
    res = {}
    # 1 coverage
    tot = collections.Counter(); trig = collections.Counter()
    for p in prefixes:
        if not os.path.exists(p + '.flab.npy'): continue
        fl = np.fromfile(p + '.flows', FLOW); lab = np.load(p + '.flab.npy'); js = json.load(open(p + '.flab.json'))
        cls = js['classes'] + ['?'] * (256 - len(js['classes']))
        names = np.array([cls[i] if i < len(js['classes']) else ('unlabelled' if i == 254 else 'ambiguous' if i == 253 else '?') for i in range(256)])
        for c, t in zip(*np.unique(lab, return_counts=True)): tot[names[c]] += int(t)
        for c, t in zip(*np.unique(lab[fl['triggered'] == 1], return_counts=True)): trig[names[c]] += int(t)
    if tot:
        res['coverage_at_N'] = {k: dict(flows=tot[k], reach_N=trig[k], share=round(trig[k] / tot[k], 4)) for k in sorted(tot)}
        res['coverage_at_N_all'] = round(sum(trig.values()) / sum(tot.values()), 4)
    # 2 duplicates
    D = np.load(npz)
    X, sp, yb, ym, yn = D['X'], D['split'], D['y_bin'], D['y_mc'], D['y_nat']   # load once (NpzFile re-reads per access)
    def rows(m, y): return {r.tobytes() + bytes([int(l) & 255]) for r, l in zip(X[m], y[m])}
    trset = rows(sp == 0, yn)
    te = np.flatnonzero(sp == 2)
    dup = np.array([X[i].tobytes() + bytes([int(yn[i]) & 255]) in trset for i in te])
    res['test_rows'] = int(len(te)); res['test_dup_in_train_share'] = round(float(dup.mean()), 4)
    res['test_dup_in_train_share_attack'] = round(float(dup[yb[te] == 1].mean()), 4) if (yb[te] == 1).any() else None
    # 3 ablation
    rng = np.random.default_rng(12345)
    def cap(idx, y, c=200_000):
        o = []
        for k in np.unique(y[idx]):
            m = idx[y[idx] == k]; o.append(m if len(m) <= c else rng.choice(m, c, replace=False))
        return np.sort(np.concatenate(o))
    abl = {}
    for task, y in (('binary', yb.astype(int)), ('multiclass', ym.astype(int))):
        ok = y >= 0
        tr = cap(np.flatnonzero(ok & (sp == 0)), y); tt = np.flatnonzero(ok & (sp == 2))
        nodup = tt[~np.isin(tt, te[dup])]
        for name, cols in (('all17', list(range(17))), ('no_resp_port', [i for i in range(17) if i != 1])):
            m = RandomForestClassifier(64, max_depth=8, max_features='sqrt', n_jobs=12, random_state=0).fit(X[tr][:, cols], y[tr])
            abl[f'{task}/{name}'] = dict(test_macro_f1=round(f1_score(y[tt], m.predict(X[tt][:, cols]), average='macro'), 4),
                                         test_nodup_macro_f1=round(f1_score(y[nodup], m.predict(X[nodup][:, cols]), average='macro'), 4) if len(nodup) else None,
                                         n_test=int(len(tt)), n_test_nodup=int(len(nodup)))
    res['ablation_rf_T64D8_s0'] = abl
    json.dump(res, open(out, 'w'), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()

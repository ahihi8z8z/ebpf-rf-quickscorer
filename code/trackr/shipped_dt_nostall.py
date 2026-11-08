#!/usr/bin/env python3
"""Shipped Hara DT with plain CART semantics (descend on every feature value, incl. 0) vs the
kernel walk that stalls on zero-valued features (Q3). Same features (hara_ref --dump-feat).
    python3 shipped_dt_nostall.py out/wed.lab.npy out/featdir.feat [...]"""
import json, sys
import numpy as np
R = 'hara_src/dt-filter/runs/'
L, Rr, F, T, V = (np.array(json.load(open(R + k))) for k in
                  ('childrenLeft', 'childrenRight', 'feature', 'threshold', 'value'))
lab = np.load(sys.argv[1]); NC = len(json.load(open(sys.argv[1][:-4] + '.json'))['classes'])
print('| features | DT semantics | acc | precision | recall | F1 | FPR |\n|---|---|---|---|---|---|---|')
for path in sys.argv[2:]:
    X = np.fromfile(path, np.int64).reshape(-1, 12)
    ok = lab < NC; X = X[ok]; y = lab[ok] > 0
    for stall in (True, False):
        node = np.zeros(len(X), np.int64)
        for _ in range(20):
            inner = L[node] != -1
            v = X[np.arange(len(X)), np.where(inner, F[node], 0)]
            go = inner & ((v != 0) if stall else True)
            node = np.where(go, np.where(v <= T[node], L[node], Rr[node]), node)
        yh = V[node] == 1
        tp = (y & yh).sum(); fp = (~y & yh).sum(); fn = (y & ~yh).sum(); tn = (~y & ~yh).sum()
        p = tp / max(tp + fp, 1); r = tp / max(tp + fn, 1)
        print(f'| {path} | {"kernel (stall on 0)" if stall else "CART (no stall)"} | {(tp+tn)/len(y):.3f} | '
              f'{p:.3f} | {r:.3f} | {2*p*r/max(p+r,1e-12):.3f} | {fp/max(fp+tn,1):.3f} |')

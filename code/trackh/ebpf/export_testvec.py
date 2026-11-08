#!/usr/bin/env python3
"""Write test vectors and the Python integer-reference predictions for a model export.
    export_testvec.py <dataset.npz> <model.npz> <out_prefix> [max_rows]
-> <out>.X.i32 (rows x 17 int32, test partition), <out>.pred.u8 (reference class per row)."""
import sys
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 2)[0])
from train_e1 import forest_scores_q, argmax_low, nn_int, logq
D = np.load(sys.argv[1]); m = np.load(sys.argv[2])
nmax = int(sys.argv[4]) if len(sys.argv) > 4 else 100000
X = D['X'][D['split'] == 2].astype(np.int32)
X = X[np.random.default_rng(0).permutation(len(X))[:nmax]]
if 'Wq0' in m:
    L = [dict(Wq=m[f'Wq{i}'], bq=m[f'bq{i}'], M=m[f'M{i}']) for i in range(3)]
    p = nn_int(L, logq(X)).argmax(1).astype(np.uint8)
else:
    off = m['offsets']
    trees = [dict(left=m['left'][a:b], right=m['right'][a:b], feat=m['feat'][a:b], thr=m['thr'][a:b], leafq=m['leafq'][a:b])
             for a, b in zip(off[:-1], off[1:])]
    p = argmax_low(forest_scores_q(trees, X)).astype(np.uint8)
X.tofile(sys.argv[3] + '.X.i32'); p.tofile(sys.argv[3] + '.pred.u8')
print(len(X), np.bincount(p))

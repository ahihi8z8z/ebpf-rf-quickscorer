#!/usr/bin/env python3
"""Control for the Track-R pipeline (not a reproduction): is the per-packet task, as labelled and
featurised by our pipeline, learnable at the paper's quality with the paper's protocol?
    python control_dt.py out/wed.lab.npy out/featdir.feat out/featbidir.feat > out/control_dt.md
Trains a depth-5 sklearn DT (paper: depth 5) on Hara's 12 features computed exactly as the kernel
does (hara_ref --dump-feat), with the paper's random 67/33 packet split (Q1, leaky by design), 3
seeds. Also prints each feature's observed range next to the range implied by the shipped NN
normaliser (range = 65536 / data_scale, min = data_min / 65536), to locate train/deploy mismatch."""
import json, sys
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, f1_score

NAMES = ['sport', 'dport', 'proto', 'len', 'iat', 'dir', 'avg_len', 'avg_iat', 'avg_dir',
         'mad_len', 'mad_iat', 'mad_dir']
lab = np.load(sys.argv[1])
NC = len(json.load(open(sys.argv[1].replace('.npy', '') + '.json'))['classes'])
nn = json.load(open('hara_src/nn-filter/mlp_params.json'))
dmin = np.array(nn['data_min']) / 65536
drng = np.array([65536 / s if s else np.inf for s in nn['data_scale']])

for path in sys.argv[2:]:
    X = np.fromfile(path, np.int64).reshape(-1, 12)
    assert len(X) == len(lab)
    ok = lab < NC
    X = X[ok] / 65536.0; y = (lab[ok] > 0).astype(np.int8)
    print(f'\n### {path}  ({len(y)} labelled packets, attack share {y.mean():.3f})\n')
    print('| feature | observed min | observed max | NN-normaliser min | NN-normaliser max | share above norm. max |')
    print('|---|---|---|---|---|---|')
    for k, n in enumerate(NAMES):
        hi = dmin[k] + drng[k]
        print(f'| {n} | {X[:, k].min():.4g} | {X[:, k].max():.4g} | {dmin[k]:.4g} | {hi:.4g} | '
              f'{(X[:, k] > hi).mean():.4f} |')
    print('\n| seed | test acc | test F1 (attack) | top features |')
    print('|---|---|---|---|')
    for seed in (0, 1, 2):
        rng = np.random.default_rng(seed)
        te = rng.random(len(y)) < 0.33
        clf = DecisionTreeClassifier(max_depth=5, random_state=seed).fit(X[~te], y[~te])
        yh = clf.predict(X[te])
        top = ', '.join(NAMES[i] for i in np.argsort(-clf.feature_importances_)[:4])
        print(f'| {seed} | {accuracy_score(y[te], yh):.4f} | {f1_score(y[te], yh):.4f} | {top} |')

#!/usr/bin/env python3
"""Learnability control over all processed days (not a reproduction; paper protocol on our pipeline).
    ~/miniconda3/envs/vnpt/bin/python -I control_all.py out/days monday ... friday > out/control_all.md
Depth-5 sklearn DT (paper: depth 5) on Hara's 12 kernel-defined features, random 67/33 packet split
(paper protocol, leaky by design, Q1), binary and paper 7-class. Up to PER_DAY labelled packets are
sampled uniformly from each day (memory bound); 3 seeds."""
import json, sys
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, f1_score

sys.path.insert(0, '.')
from aggregate_map import map7
PER_DAY = 4_000_000
D, DAYS = sys.argv[1], sys.argv[2:]
for key in ('dir', 'bidir'):
    Xs, ys, y7s = [], [], []
    rng = np.random.default_rng(12345)
    for day in DAYS:
        cls = json.load(open(f'{D}/{day}.lab.json'))['classes']
        lab = np.load(f'{D}/{day}.lab.npy')
        X = np.memmap(f'{D}/{day}_{key}_ns.feat', np.int64, 'r').reshape(-1, 12)
        idx = np.flatnonzero(lab < len(cls))
        if len(idx) > PER_DAY: idx = np.sort(rng.choice(idx, PER_DAY, replace=False))
        Xs.append((X[idx] / 65536.0).astype(np.float32)); l = lab[idx]
        ys.append(l > 0); y7s.append(np.array([map7(c) for c in cls])[l])
    X = np.concatenate(Xs); y = np.concatenate(ys); y7 = np.concatenate(y7s)
    print(f'\n### {key} features: {len(y)} sampled labelled packets, attack share {y.mean():.3f}\n')
    print('| seed | binary acc | binary F1 | 7-class acc (Heartbleed excl.) | 7-class macro F1 |\n|---|---|---|---|---|')
    for seed in (0, 1, 2):
        te = np.random.default_rng(seed).random(len(y)) < 0.33
        b = DecisionTreeClassifier(max_depth=5, random_state=seed).fit(X[~te], y[~te])
        yh = b.predict(X[te])
        k = y7 >= 0
        m = DecisionTreeClassifier(max_depth=5, random_state=seed).fit(X[~te & k], y7[~te & k])
        y7h = m.predict(X[te & k])
        print(f'| {seed} | {accuracy_score(y[te], yh):.4f} | {f1_score(y[te], yh):.4f} | '
              f'{accuracy_score(y7[te & k], y7h):.4f} | {f1_score(y7[te & k], y7h, average="macro"):.4f} |')

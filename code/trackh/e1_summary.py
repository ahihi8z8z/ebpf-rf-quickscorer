#!/usr/bin/env python3
"""Summarise model_quality.csv: per dataset and task, mean +- std over seeds of the deployable
(integer) models; DT depth and RF (T, D) selected on VALIDATION macro-F1 only.
    python -I e1_summary.py out/e1/model_quality.csv > out/e1/summary.md"""
import sys
import numpy as np
import pandas as pd

df = pd.read_csv(sys.argv[1])
df = df.drop_duplicates(subset=['dataset', 'task', 'model', 'config', 'seed', 'precision'], keep='last')
out = []
for (ds, task), g in df.groupby(['dataset', 'task'], sort=False):
    out.append(f'\n## {ds} / {task}  (train {g.n_train.iloc[0]}, val {g.n_val.iloc[0]}, test {g.n_test.iloc[0]})\n')
    gi = g[g.precision == 'int']
    agg = gi.groupby(['model', 'config']).agg(
        seeds=('seed', 'nunique'), val_f1=('val_macro_f1', 'mean'), test_f1=('test_macro_f1', 'mean'),
        test_f1_sd=('test_macro_f1', 'std'), bal_acc=('test_bal_acc', 'mean'), fpr=('test_fpr', 'mean'),
        acc=('test_acc', 'mean'), nodes=('nodes', 'mean'), walk_kB=('walk_bytes', lambda x: x.mean() / 1024),
        qs_kB=('qs_bytes', lambda x: x.mean() / 1024), nn_macs=('nn_macs', 'mean'),
        agree=('quant_agreement', 'mean')).reset_index()
    fl = g[g.precision == 'float'].groupby(['model', 'config']).test_macro_f1.mean()
    agg['float_test_f1'] = [fl.get((m, c), np.nan) for m, c in zip(agg.model, agg.config)]
    out.append('| model | config | seeds | val F1 | test macro-F1 (int) | sd | float test F1 | bal.acc | FPR | nodes | walk kB | QS kB | NN MACs | int=float agreement |')
    out.append('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    order = {'DT': 0, 'NN': 1, 'RF': 2, 'RFdeep': 3}
    agg['o'] = agg.model.map(order)
    agg['T'] = agg.config.str.extract(r'T(\d+)').astype(float).fillna(0)
    agg['D'] = agg.config.str.extract(r'D(\d+)').astype(float).fillna(0)
    best = {m: agg[agg.model == m].sort_values('val_f1', ascending=False).config.iloc[0] for m in agg.model.unique()}
    for _, r in agg.sort_values(['o', 'T', 'D']).iterrows():
        mark = ' **(val-selected)**' if best[r.model] == r.config else ''
        out.append(f'| {r.model} | {r.config}{mark} | {r.seeds} | {r.val_f1:.4f} | {r.test_f1:.4f} | {r.test_f1_sd:.4f} | '
                   f'{r.float_test_f1:.4f} | {r.bal_acc:.4f} | {r.fpr:.4f} | {"" if np.isnan(r.nodes) else int(r.nodes)} | '
                   f'{"" if np.isnan(r.walk_kB) else f"{r.walk_kB:.1f}"} | {"" if np.isnan(r.qs_kB) else f"{r.qs_kB:.1f}"} | '
                   f'{"" if np.isnan(r.nn_macs) else int(r.nn_macs)} | {r.agree:.4f} |')
    sel = gi[gi.config.isin(best.values()) & gi.model.isin(best.keys())]
    sel = sel[[best[m] == c for m, c in zip(sel.model, sel.config)]]
    out.append('\nPer-class test F1 of the val-selected configurations (seed 0):\n')
    for m in ('DT', 'NN', 'RF', 'RFdeep'):
        r = sel[(sel.model == m) & (sel.seed == 0)]
        if len(r): out.append(f'- {m} {best[m]}: {r.test_per_class_f1.iloc[0]}')
print('\n'.join(out))

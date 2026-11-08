#!/usr/bin/env python3
"""Pick the E5 XDP variants for one dataset (binary task, seed-0 models), from E1 and E2 results only:
  - val-selected DT as G-RF k1 (one program) and the NN 16x16 (one stage);
  - the RF swept in E2 for this task with the best mean val macro-F1 (RF or RFdeep), each runtime
    family's fastest variant that loaded with 0 mismatches (G-RF / G-RF-mem, QS-*, RF-walk-*);
  - a null program (parser + flow state + event only) as the load-test floor.
    python -I e5_variants.py <ds> <model_quality.csv> <deployability_raw.csv> <models dir> <out.json>"""
import json, os, sys
import numpy as np
import pandas as pd

ds, mqp, rawp, mdir, outp = sys.argv[1:6]
mdir = os.path.abspath(mdir)
task = 'binary'
mq = pd.read_csv(mqp); mq = mq[(mq.dataset == ds) & (mq.task == task) & (mq.precision == 'int')]
raw = pd.read_csv(rawp).drop_duplicates(subset=['model', 'variant'], keep='last')
raw = raw[(raw.dataset == ds) & (raw.task == task)]
raw = raw[(raw.loaded == 1) & (raw.mismatch.fillna(1) == 0)]


def best_cfg(fams):
    g = mq[mq.model.isin(fams)].groupby(['model', 'config']).val_macro_f1.mean()
    return g.idxmax()


out = []
_, dt = best_cfg(['DT']); _, nn = best_cfg(['NN'])
dtp = os.path.join(mdir, f'{ds}_{task}_DT_{dt}_s0.npz'); nnp = os.path.join(mdir, f'{ds}_{task}_NN_{nn}_s0.npz')
out += [dict(model=dtp, variant='grf_k1', family='DT'), dict(model=nnp, variant='nn_s1', family='NN'),
        dict(model=dtp, variant='null_g1', family='null')]
swept = set(raw.model)
g = mq[mq.model.isin(['RF', 'RFdeep'])].groupby('config').val_macro_f1.mean()
g = g[[f'{ds}_{task}_RF_{c}_s0' in swept for c in g.index]]
if len(g):
    rf = g.idxmax(); name = f'{ds}_{task}_RF_{rf}_s0'; r = raw[raw.model == name]
    for fams, lab in ((['G-RF', 'G-RF-mem'], 'RF-G-RF'), (['QS-mask', 'QS-bounds', 'QS-bpfloop'], 'RF-QS'),
                      (['RF-walk-table', 'RF-walk-bpfloop'], 'RF-walk')):
        x = r[r.family.isin(fams)]
        if len(x):
            b = x.loc[x.ns_mean.idxmin()]
            out.append(dict(model=os.path.join(mdir, name + '.npz'), variant=b.variant, family=lab,
                            e2_ns=float(b.ns_mean), stages=int(b.stages)))
        else:
            out.append(dict(model=os.path.join(mdir, name + '.npz'), variant=None, family=lab, note='not deployable in E2'))
for v in out: print(v)
json.dump([v for v in out if v['variant']], open(outp, 'w'), indent=1)

#!/usr/bin/env python3
"""Aggregate deployability_raw.csv -> deployability_matrix.csv (one row per model x runtime family) and
print a compact markdown matrix.
    python -I e2_matrix.py <deployability_raw.csv> <deployability_matrix.csv> [> matrix.md]
Per (model, family): variants tried, variants loaded (verified + correct on all rows), the fastest
loaded variant and its mean/p99 ns, the fewest stages that loaded, and the failure reasons with counts.
A variant only counts as deployable if it loaded AND had 0 mismatches against the integer reference."""
import sys
import pandas as pd

raw = pd.read_csv(sys.argv[1])
raw = raw.drop_duplicates(subset=['model', 'variant'], keep='last')
raw['ok'] = (raw.loaded == 1) & (raw.mismatch.fillna(1) == 0)
rows = []
for (model, fam), g in raw.groupby(['model', 'family'], sort=False):
    ok = g[g.ok]
    best = ok.loc[ok.ns_mean.idxmin()] if len(ok) else None
    reasons = g[~g.ok].error.fillna('loaded-but-mismatch').str.replace(r'^bench: .*', 'bench-failure', regex=True)
    r0 = g.iloc[0]
    rows.append(dict(dataset=r0.dataset, task=r0.task, model=model, T=r0['T'], D=r0['D'], family=fam,
                     tried=len(g), deployable=len(ok), any_deployable=int(len(ok) > 0),
                     best_variant=best.variant if best is not None else '', best_stages=int(best.stages) if best is not None else '',
                     best_ns_mean=round(best.ns_mean, 1) if best is not None else '',
                     best_ns_p99=best.ns_p99 if best is not None else '',
                     min_stages_loaded=int(ok.stages.min()) if len(ok) else '',
                     max_verified_insns_best=int(best.verified_insns_max_prog) if best is not None else '',
                     isa_best=best.isa if best is not None else '',
                     failures='; '.join(f'{k} x{v}' for k, v in reasons.value_counts().items())))
m = pd.DataFrame(rows)
m.to_csv(sys.argv[2], index=False)
fams = ['G-RF', 'G-RF-mem', 'G-RF-x', 'QS-mask', 'QS-bounds', 'QS-bpfloop', 'RF-walk-table', 'RF-walk-bpfloop']
print('| dataset/task | T | D | ' + ' | '.join(fams) + ' |')
print('|---|---|---|' + '---|' * len(fams))
for (ds, task, model), g in m.groupby(['dataset', 'task', 'model'], sort=False):
    cells = []
    for f in fams:
        r = g[g.family == f]
        if not len(r): cells.append('n/a'); continue
        r = r.iloc[0]
        cells.append(f"{r.best_ns_mean / 1000:.2f} µs ({r.best_variant})" if r.any_deployable else '✗')
    print(f'| {ds}/{task} | {g['T'].iloc[0]} | {g['D'].iloc[0]} | ' + ' | '.join(cells) + ' |')

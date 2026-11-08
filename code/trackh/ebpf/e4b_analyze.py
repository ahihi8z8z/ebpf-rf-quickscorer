#!/usr/bin/env python3
"""E4b analysis -> out/e4b/mechanism.csv + out/e4b/mechanism.md
Model-only cost of an eBPF variant = variant - null chain with the same number of stages (same harness).
Cycles: the DUT vPMU returns ~0 for the kernel-mode cycles event, so eBPF cycles are derived from time
(ns x 2.195 GHz, DUT nominal clock; frequency scaling is not exposed in the VM); C cycles are counted.
Work units: QS = false-node updates per row, walk/G-RF = internal nodes visited per row (rfm.c counts).
    python -I e4b_analyze.py   (from trackh/)"""
import os
import numpy as np
import pandas as pd

GHZ = 2.195
TH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
O = os.environ.get('E4B_DIR') or os.path.join(TH, 'out', 'e4b')
NUM = ['ns', 'instructions', 'cycles', 'branches', 'branch_misses']


def load(p, regime):
    d = pd.read_csv(p, keep_default_na=False)
    if 'regime' not in d: d['regime'] = regime
    d = d[pd.to_numeric(d.ns, errors='coerce').notna()].copy()
    for c in NUM: d[c] = pd.to_numeric(d[c], errors='coerce')
    return d



def main():
    m = load(os.path.join(O, 'mech.csv'), None)
    m.loc[m.side == 'eBPF', 'regime'] = 'warm_repeat200'
    m.loc[m.side == 'C', 'regime'] = 'cold_rowrep1'
    m.loc[m.side == 'C-novec', 'regime'] = 'cold_rowrep1_novec'
    m.loc[m.side == 'C-novec', 'side'] = 'C'
    parts = [m]
    if os.path.exists(os.path.join(O, 'regime.csv')): parts.append(load(os.path.join(O, 'regime.csv'), None))
    d = pd.concat(parts, ignore_index=True)
    work = m.groupby('model')[['walk_steps', 'qs_updates']].first()
    g = d.groupby(['model', 'side', 'regime', 'variant', 'family', 'stages'], dropna=False)[NUM].median().reset_index()
    rows = []
    for _, r in g.iterrows():
        if r.family == 'null' or r.variant.startswith('null'): continue
        o = r.to_dict()
        if r.side == 'eBPF':
            n = g[(g.model == r.model) & (g.regime == r.regime) & (g.variant == f'null_g{int(r.stages)}')]
            if not len(n): continue
            n = n.iloc[0]
            for c in ('ns', 'instructions', 'branches', 'branch_misses'): o[c] = r[c] - n[c]
            o['cycles'] = o['ns'] * GHZ; o['cycles_src'] = 'ns*GHz'
        else:
            o['cycles_src'] = 'counted'
        qsw = r.variant.startswith('qs') if r.side == 'C' else str(r.family).startswith('QS')
        w = work.loc[r.model, 'qs_updates' if qsw else 'walk_steps']
        o['work'] = w; o['ipc'] = o['instructions'] / o['cycles'] if o['cycles'] else np.nan
        o['insn_per_work'] = o['instructions'] / w; o['cyc_per_work'] = o['cycles'] / w
        rows.append(o)
    a = pd.DataFrame(rows)
    a.to_csv(os.path.join(O, 'mechanism.csv'), index=False)
    # compact table: per model, the runtimes that matter
    keep = {('C', 'walk'): 'C walk', ('C', 'qs'): 'C QS', ('C', 'qs_bpf'): 'C QS (eBPF shape)', ('C', 'qs_vol'): 'C QS (eBPF shape + volatile)'}
    out = ['# E4b mechanism table (model-only cost per inference, medians of 3 passes)\n',
           'eBPF cycles = (variant − null) ns × 2.195 GHz; C cycles counted. Units of work: walk steps / QS updates per row.\n']
    for (model, regime), s in a.groupby(['model', 'regime']):
        out.append(f'\n## {model} — {regime}\n')
        out.append('| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |')
        out.append('|---|---|---|---|---|---|---|---|---|---|')
        for _, r in s.sort_values(['side', 'ns']).iterrows():
            out.append(f'| {r.side} | {r.variant} | {r.family} | {r.ns:.0f} | {r.instructions:.0f} | {r.cycles:.0f} | {r.ipc:.2f} | '
                       f'{r.insn_per_work:.1f} | {r.cyc_per_work:.1f} | {r.branch_misses:.1f} |')
    open(os.path.join(O, 'mechanism.md'), 'w').write('\n'.join(out) + '\n')
    print('\n'.join(out))


if __name__ == '__main__':
    main()

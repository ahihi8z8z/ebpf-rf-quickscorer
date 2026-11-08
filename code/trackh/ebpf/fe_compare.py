#!/usr/bin/env python3
"""Compare fe_check events with flowfeat .trig and the integer model reference.
    fe_compare.py <events> <flowfeat .trig> <model.npz> [max_ts_us]"""
import sys
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 2)[0])
from label_flows import TRIG
from train_e1 import forest_scores_q, argmax_low
EV = np.dtype([('ts_first_us', '<u8'), ('ini_ip', '<u4'), ('resp_ip', '<u4'), ('ini_port', '<u2'), ('resp_port', '<u2'),
               ('proto', 'u1'), ('cls', 'u1'), ('pad', 'u1', 2), ('f', '<i4', 17), ('pad2', '<u4')])
ev = np.fromfile(sys.argv[1], EV); tr = np.fromfile(sys.argv[2], TRIG); m = np.load(sys.argv[3])
if len(sys.argv) > 4: tr = tr[tr['ts_trig_us'] <= int(sys.argv[4])]
key = lambda r: (int(r['ts_first_us']), int(r['ini_ip']), int(r['ini_port']), int(r['proto']))
ref = {key(r): r['f'].tolist() for r in tr}
got = {key(r): r for r in ev}
miss = [k for k in ref if k not in got]; extra = [k for k in got if k not in ref]
badf = [k for k in ref if k in got and got[k]['f'].tolist() != ref[k]]
off = m['offsets']
trees = [dict(left=m['left'][a:b], right=m['right'][a:b], feat=m['feat'][a:b], thr=m['thr'][a:b], leafq=m['leafq'][a:b])
         for a, b in zip(off[:-1], off[1:])]
p = argmax_low(forest_scores_q(trees, ev['f'].astype(np.int32)))
print(f'events={len(ev)} flowfeat_trig={len(tr)} missing={len(miss)} extra={len(extra)} feature_mismatch={len(badf)} '
      f'class_mismatch={int((p != ev["cls"]).sum())}')
for k in badf[:3]: print('  feat', k, ref[k], got[k]['f'].tolist())

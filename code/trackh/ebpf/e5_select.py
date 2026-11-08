#!/usr/bin/env python3
"""Pick the E5 replay slices: for every multiclass family of the dataset, the TEST time block that
contains the most flows of that family (ties: more benign flows); one slice per family, deduplicated.
Only test-partition blocks are used, so replayed flows were never trained or validated on.
    python -I e5_select.py <ds> <out spec.json>"""
import json, os, sys
import numpy as np

TH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TH)
from label_flows import TRIG
ROOT = os.path.dirname(TH)
D1PCAP = {'monday': f'{ROOT}/trackr/data/cicids2017/Monday-WorkingHours.pcap',
          'tuesday': f'{ROOT}/trackr/data/cicids2017/Tuesday-WorkingHours.pcap',
          'wednesday': os.path.expanduser('~/ebpf/data/cicids2017/wed.pcap'),
          'thursday': f'{ROOT}/trackr/data/cicids2017/Thursday-WorkingHours.pcap',
          'friday': f'{ROOT}/trackr/data/cicids2017/Friday-WorkingHours.pcap'}


def main():
    ds, outp = sys.argv[1], sys.argv[2]
    d = np.load(os.path.join(TH, 'out', f'{ds}.npz')); js = json.load(open(os.path.join(TH, 'out', f'{ds}.json')))
    bs = js['block_s']; mc = [str(s) for s in d['mc_names']]
    t = d['split'] == 2
    g, b, ym = d['group'][t], d['block'][t], d['y_mc'][t]
    slices, seen = [], set()
    for c in range(len(mc)):
        best, bk = None, None
        for key in set(zip(g[ym == c].tolist(), b[ym == c].tolist())):
            m = (g == key[0]) & (b == key[1])
            score = ((ym[m] == c).sum(), (ym[m] == 0).sum())
            if best is None or score > best: best, bk = score, key
        if bk is None or bk in seen: continue
        seen.add(bk)
        pre = js['prefixes'][bk[0]]
        if ds == 'd3':
            tr = np.fromfile(os.path.join(TH, pre + '.trig'), TRIG)
            start = round(int(tr["ts_first_us"].min()) / 1e6 + bk[1] * bs, 6)   # make_dataset: block relative to file start
            cls, f = os.path.basename(pre).split('__')
            pcap = f'{ROOT}/data/ciciot/pcap/{cls}/{f}.pcap'
        elif ds == 'd1':
            start = bk[1] * bs; pcap = D1PCAP[os.path.basename(pre)]
        else:   # d2: a capture day is many files; take the file holding the block start and the next one
            start = bk[1] * bs
            day = os.path.basename(pre)
            fs = [(float(t), f) for f, t in (l.split() for l in open(os.path.join(TH, 'out', 'unsw', 'file_start.txt')))
                  if f.startswith(day + '/')]
            fs.sort()
            i = max(j for j, (t, f) in enumerate(fs) if t <= start) if any(t <= start for t, f in fs) else 0
            pcap = [f'{ROOT}/data/unsw/pcap/{f}' for t, f in fs[i:i + 2]]
        slices.append(dict(family=mc[c], prefix=pre, pcap=pcap, block=bk[1], start=start, dur=bs,
                           n_family=int(best[0]), n_benign=int(best[1])))
        print(slices[-1])
    json.dump(dict(dataset=ds, mc_names=mc, slices=slices), open(outp, 'w'), indent=1)


if __name__ == '__main__':
    main()

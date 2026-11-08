#!/usr/bin/env python3
"""Confusion of the AF_XDP 7-class MLP on Wednesday labels.
Class order assumed alphabetical as listed in the paper: 0 Botnet, 1 Brute force, 2 DoS,
3 Infiltration, 4 Normal, 5 Portscan, 6 Web attack (undocumented in the repo; the confusion shows
whether it is consistent). Binary view: attack = predicted != Normal."""
import json, sys
import numpy as np
P = ['Botnet', 'BruteForce', 'DoS', 'Infiltration', 'Normal', 'Portscan', 'WebAttack']
lab = np.load(sys.argv[1]); classes = json.load(open(sys.argv[1][:-4] + '.json'))['classes']
NC = len(classes)
for path in sys.argv[2:]:
    p = np.fromfile(path, np.uint8); ok = (lab < NC) & (p < 7)
    l, q = lab[ok], p[ok]
    print(f'\n### {path}\n\n| true \\ pred | ' + ' | '.join(P) + ' |\n|---|' + '---|' * 7)
    for k in range(NC):
        r = np.bincount(q[l == k], minlength=7) / max((l == k).sum(), 1)
        print(f'| {classes[k]} | ' + ' | '.join(f'{x:.3f}' for x in r) + ' |')
    y = l > 0; yh = q != 4
    tp = (y & yh).sum(); fp = (~y & yh).sum(); fn = (y & ~yh).sum(); tn = (~y & ~yh).sum()
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    dos = np.isin(l, [k for k, c in enumerate(classes) if c.startswith('DoS')])
    print(f'\nbinary (pred != Normal): acc {(tp+tn)/len(y):.3f} precision {pr:.3f} recall {rc:.3f} '
          f'F1 {2*pr*rc/max(pr+rc,1e-12):.3f} FPR {fp/max(fp+tn,1):.3f}; '
          f'7-class accuracy on Wednesday (BENIGN->Normal, DoS*->DoS): '
          f'{(((l == 0) & (q == 4)) | (dos & (q == 2))).sum() / (l != 5).sum():.3f} (Heartbleed excluded)')

#!/usr/bin/env python3
"""Per-packet binary metrics of hara_ref outputs against label_packets labels.
    python3 metrics.py out/wed.lab.npy out/wed_<variant>.cls [...] > out/wed_metrics.md
Positive = attack (any non-BENIGN label). Only packets with a definite label (BENIGN or attack)
and a prediction (0/1) are scored; coverage of the remaining packets is reported, not hidden."""
import json, os, sys
import numpy as np

lab = np.load(sys.argv[1])
classes = json.load(open(sys.argv[1].replace('.npy', '') + '.json'))['classes']
NC = len(classes)
rows = []
print('| variant | model | scored pkts | acc | precision | recall | F1 | bal.acc | FPR | ' +
      ' | '.join(f'recall {c}' for c in classes[1:]) + ' |')
print('|' + '---|' * (9 + NC - 1))
for path in sys.argv[2:]:
    v = os.path.basename(path).replace('.cls', '')
    c = np.fromfile(path, np.uint8).reshape(-1, 2)
    assert len(c) == len(lab), (len(c), len(lab))
    for j, model in enumerate(('DT', 'NN')):
        p = c[:, j]
        ok = (lab < NC) & (p <= 1)
        y, yh, l = (lab[ok] > 0), (p[ok] == 1), lab[ok]
        tp = int((y & yh).sum()); tn = int((~y & ~yh).sum())
        fp = int((~y & yh).sum()); fn = int((y & ~yh).sum())
        acc = (tp + tn) / len(y); prec = tp / max(tp + fp, 1); rec = tp / max(tp + fn, 1)
        f1 = 2 * prec * rec / max(prec + rec, 1e-12); fpr = fp / max(fp + tn, 1)
        bal = (rec + (1 - fpr)) / 2
        per = [float(yh[l == k].mean()) if (l == k).any() else float('nan') for k in range(1, NC)]
        unpred = int(((lab < NC) & (p > 1)).sum())
        rows.append(dict(variant=v, model=model, scored=int(ok.sum()), unpredicted=unpred, tp=tp, tn=tn,
                         fp=fp, fn=fn, acc=acc, precision=prec, recall=rec, f1=f1, bal_acc=bal,
                         fpr=fpr, per_class_recall=dict(zip(classes[1:], per))))
        print(f'| {v} | {model} | {ok.sum()} | {acc:.3f} | {prec:.3f} | {rec:.3f} | {f1:.3f} | '
              f'{bal:.3f} | {fpr:.3f} | ' + ' | '.join(f'{x:.3f}' for x in per) + ' |')
json.dump(rows, open(os.path.join(os.path.dirname(sys.argv[2]), 'wed_metrics.json'), 'w'), indent=1)

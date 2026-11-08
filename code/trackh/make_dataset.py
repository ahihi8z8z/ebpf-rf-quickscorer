#!/usr/bin/env python3
"""Assemble one Track-H dataset (frozen protocol, dataset_protocol.md) from flowfeat + label_flows
outputs:  make_dataset.py <d1|d2|d3> <out.npz> <prefix>...
Per triggered flow: X (17 int32 features), native label, binary label, multiclass label (dataset
mapping below; -1 = not in the multiclass task), split (0 train / 1 val / 2 test), group id.
Split: time blocks of BLOCK_S seconds of the flow's first packet, interleaved 3:1:1 by block index
(train, train, train, val, test), so that no flow and no block is shared between partitions and every
attack lasting >= 5 blocks reaches every partition. D1/D2 blocks are absolute time (capture days);
D3 blocks are relative to each capture file's first packet (each file is one capture session).
Multiclass support rule: a class enters the multiclass task only if it has >= 100 train, >= 30 val
and >= 30 test flows; other attack flows stay in the binary task and are reported as excluded.
Unlabelled / ambiguous / 'Background' flows are excluded from both tasks and counted."""
import json, sys
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from label_flows import TRIG

BLOCK_S = {'d1': 300, 'd2': 300, 'd3': 60}
MIN_TR, MIN_VA, MIN_TE = 100, 30, 30

# Native label -> multiclass family (dataset's own taxonomy; D1 CIC grouping as in Hara/Track-R;
# D3 = the 8 groups defined by the CICIoT2023 authors).
D1 = {'BENIGN': 'Benign', 'DoS Hulk': 'DoS', 'DoS GoldenEye': 'DoS', 'DoS slowloris': 'DoS',
      'DoS Slowhttptest': 'DoS', 'DDoS': 'DDoS', 'PortScan': 'PortScan', 'FTP-Patator': 'BruteForce',
      'SSH-Patator': 'BruteForce', 'Web Attack - Brute Force': 'WebAttack', 'Web Attack - XSS': 'WebAttack',
      'Web Attack - Sql Injection': 'WebAttack', 'Bot': 'Bot', 'Infiltration': 'Infiltration',
      'Heartbleed': 'Heartbleed'}
D3 = {'Benign': 'Benign', 'Backdoor_Malware': 'Web', 'BrowserHijacking': 'Web', 'CommandInjection': 'Web',
      'SqlInjection': 'Web', 'Uploading_Attack': 'Web', 'XSS': 'Web', 'DictionaryBruteForce': 'BruteForce',
      'DNS_Spoofing': 'Spoofing', 'MITM-ArpSpoofing': 'Spoofing', 'Recon-HostDiscovery': 'Recon',
      'Recon-OSScan': 'Recon', 'Recon-PingSweep': 'Recon', 'Recon-PortScan': 'Recon',
      'VulnerabilityScan': 'Recon', 'Mirai-greeth_flood': 'Mirai', 'Mirai-greip_flood': 'Mirai',
      'Mirai-udpplain': 'Mirai'}
BENIGN = {'BENIGN', 'Normal', 'Benign'}


def family(ds, lab):
    if ds == 'd1': return D1[lab]
    if ds == 'd2': return lab
    if lab in D3: return D3[lab]
    return lab.split('-')[0]             # DDoS-*, DoS-*


def main():
    ds, out, prefixes = sys.argv[1], sys.argv[2], sys.argv[3:]
    Xs, nat, ts, grp = [], [], [], []
    names = []
    excl = {}
    for gi, p in enumerate(prefixes):
        tr = np.fromfile(p + '.trig', TRIG)
        lab = np.load(p + '.lab.npy'); js = json.load(open(p + '.lab.json'))
        assert len(lab) == len(tr)
        cls = js['classes']
        ok = lab < len(cls)
        for c in ('unlabelled', 'ambiguous'): excl[c] = excl.get(c, 0) + js[c]
        for k, n in js['per_class'].items():
            if k == 'Background': excl['background'] = excl.get('background', 0) + n
        keep = ok & np.array([c != 'Background' for c in cls] + [False] * (256 - len(cls)))[lab]
        Xs.append(tr['f'][keep]); ts.append(tr['ts_first_us'][keep].astype(np.int64))
        if ds == 'd3': ts[-1] = ts[-1] - int(tr['ts_first_us'].min())
        for c in cls:
            if c not in names: names.append(c)
        nat.append(np.array([names.index(c) for c in cls], np.int16)[lab[keep]])
        grp.append(np.full(keep.sum(), gi, np.int16))
    X = np.concatenate(Xs); y_nat = np.concatenate(nat); t = np.concatenate(ts); g = np.concatenate(grp)
    blk = t // (BLOCK_S[ds] * 10**6)
    split = np.array([0, 0, 0, 1, 2], np.int8)[blk % 5]
    y_bin = np.array([0 if n in BENIGN else 1 for n in names], np.int8)[y_nat]
    fam_of = [family(ds, n) for n in names]
    fams = sorted(set(fam_of), key=lambda f: (f not in ('Benign', 'Normal'), f))
    fam = np.array([fams.index(f) for f in fam_of], np.int16)[y_nat]
    support = {f: [int(((fam == i) & (split == s)).sum()) for s in (0, 1, 2)] for i, f in enumerate(fams)}
    kept = [f for f in fams if support[f][0] >= MIN_TR and support[f][1] >= MIN_VA and support[f][2] >= MIN_TE]
    y_mc = np.array([kept.index(f) if f in kept else -1 for f in fams], np.int16)[fam]
    np.savez_compressed(out, X=X, y_nat=y_nat, y_bin=y_bin, y_mc=y_mc, split=split, group=g, block=blk,
                        native_names=np.array(names), mc_names=np.array(kept))
    meta = dict(dataset=ds, prefixes=prefixes, flows=int(len(X)), block_s=BLOCK_S[ds],
                excluded=excl, native_counts={n: int((y_nat == i).sum()) for i, n in enumerate(names)},
                family_support_train_val_test=support, multiclass_classes=kept,
                multiclass_excluded_flows=int((y_mc < 0).sum()),
                split_sizes=[int((split == s).sum()) for s in (0, 1, 2)],
                attack_share=[float(y_bin[split == s].mean()) for s in (0, 1, 2)])
    json.dump(meta, open(out.replace('.npz', '.json'), 'w'), indent=1)
    print(json.dumps(meta, indent=1))


if __name__ == '__main__':
    main()

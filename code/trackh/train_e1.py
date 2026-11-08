#!/usr/bin/env python3
"""E1: DT vs lightweight NN vs RF on one Track-H dataset, binary and multiclass tasks.
    OMP_NUM_THREADS=8 python -I train_e1.py <dataset.npz> <out_dir> [--quick]
Protocol (frozen, dataset_protocol.md):
- train/val/test from make_dataset.py (time-block split); the test partition is used only for the
  final numbers of every configuration (no selection on it). Train is capped at CAP flows per class
  (uniform, fixed sampling seed 12345, independent of the model seed); val/test capped likewise for
  compute (caps reported).
- DT depth {4,6,8,10,12}; RF T {16,32,64,128,256} x D {4,6,8} (sqrt features, bootstrap);
  NN = Hara capacity F->16->16->C (ReLU) on 8-bit log-quantized inputs. Seeds 0,1,2.
- Quantized deployable inference: trees use integer thresholds (features are integers, so
  x <= t  <=>  x <= floor(t): exact) and leaf class scores quantized to uint8 (round(255 p)), summed in
  uint32, argmax with lowest-index tie-break. DT leaf = argmax class (no loss). NN: int8 weights
  (per-output-channel symmetric), int32 accumulation, per-layer requantization with a 16-bit
  fixed-point multiplier, uint7 activations. Float and quantized metrics are both reported.
Outputs: <out>/model_quality.csv (one row per dataset/task/model/config/seed/precision),
<out>/models/*.npz (quantized model exports for C/eBPF code generation)."""
import csv, json, os, sys, time
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, balanced_accuracy_score, accuracy_score
from sklearn.tree import DecisionTreeClassifier

CAP = 200_000
SEEDS = (0, 1, 2)
DT_DEPTHS = (4, 6, 8, 10, 12)
RF_T = (16, 32, 64, 128, 256)
RF_D = (4, 6, 8)


# ---------------------------------------------------------------- data
def capped(idx, y, cap, rng):
    out = []
    for c in np.unique(y[idx]):
        m = idx[y[idx] == c]
        out.append(m if len(m) <= cap else rng.choice(m, cap, replace=False))
    return np.sort(np.concatenate(out))


def logq(X):
    """8-bit monotone log quantizer computable in eBPF with shifts: 4*floor(log2(x+1)) + the next
    two mantissa bits; x >= 0 int32 -> 0..127."""
    x = np.maximum(X.astype(np.int64), 0) + 1
    e = np.floor(np.log2(x)).astype(np.int64)            # exact for int64 < 2^53
    e = np.where((1 << e) > x, e - 1, e); e = np.where((1 << (e + 1)) <= x, e + 1, e)
    mant = np.where(e >= 2, (x >> np.maximum(e - 2, 0)) & 3, (x << np.maximum(2 - e, 0)) & 3)
    return np.minimum(4 * e + mant, 127).astype(np.int32)


# ---------------------------------------------------------------- metrics
def metrics(y, p, benign=0):
    labels = np.unique(np.concatenate([y]))
    f1s = f1_score(y, p, labels=labels, average=None, zero_division=0)
    neg = y == benign
    return dict(acc=accuracy_score(y, p), macro_f1=float(f1s.mean()),
                bal_acc=balanced_accuracy_score(y, p), fpr=float((p[neg] != benign).mean()) if neg.any() else float('nan'),
                per_class_f1={int(c): float(f) for c, f in zip(labels, f1s)})


# ---------------------------------------------------------------- trees
def tree_export(est, C):
    t = est.tree_
    leaf = t.children_left == -1
    val = t.value[:, 0, :]
    val = val / np.maximum(val.sum(1, keepdims=True), 1e-12)          # class probabilities
    full = np.zeros((t.node_count, C)); full[:, est.classes_.astype(int)] = val
    q = np.rint(full * 255).astype(np.uint8)
    thr = np.where(leaf, 0, np.floor(t.threshold)).astype(np.int64)
    return dict(left=t.children_left.astype(np.int32), right=t.children_right.astype(np.int32),
                feat=np.where(leaf, -1, t.feature).astype(np.int16), thr=thr.astype(np.int32),
                leafq=q, prob=full)


def forest_scores_q(trees, X):
    """Integer reference: walk every tree with integer thresholds, sum uint8 leaf scores."""
    C = trees[0]['leafq'].shape[1]
    S = np.zeros((len(X), C), np.uint32)
    for tr in trees:
        node = np.zeros(len(X), np.int64)
        for _ in range(64):
            f = tr['feat'][node]; act = f >= 0
            if not act.any(): break
            go_left = X[np.arange(len(X)), np.maximum(f, 0)] <= tr['thr'][node]
            node = np.where(act, np.where(go_left, tr['left'][node], tr['right'][node]), node)
        S += tr['leafq'][node]
    return S


def argmax_low(S):
    return S.argmax(1)        # numpy returns the first (lowest index) maximum


def tree_stats(trees):
    n = sum(len(t['feat']) for t in trees); leaves = sum(int((t['feat'] < 0).sum()) for t in trees)
    C = trees[0]['leafq'].shape[1]
    inner = n - leaves
    maxleaves = max(int((t['feat'] < 0).sum()) for t in trees)
    words = (maxleaves + 63) // 64
    # tree-walk layout: per node feature u8 + threshold i32 + 2x u16 children = 9 B -> 12 B aligned,
    # plus C uint8 scores per leaf; QuickScorer: per inner node feature u8, threshold i32, tree id u16
    # and a words*8 B leaf mask, plus C uint8 per leaf
    return dict(nodes=n, inner=inner, leaves=leaves, max_leaves_per_tree=maxleaves,
                walk_bytes=12 * n + C * leaves, qs_bytes=inner * (8 + 8 * words) + C * leaves)


# ---------------------------------------------------------------- NN
def train_nn(Xq_tr, y_tr, Xq_va, y_va, C, seed, epochs=30):
    import torch
    torch.manual_seed(seed); np.random.seed(seed)
    torch.set_num_threads(8)
    F = Xq_tr.shape[1]
    net = torch.nn.Sequential(torch.nn.Linear(F, 16), torch.nn.ReLU(), torch.nn.Linear(16, 16),
                              torch.nn.ReLU(), torch.nn.Linear(16, C))
    opt = torch.optim.Adam(net.parameters(), 1e-3)
    xt = torch.tensor(Xq_tr / 127.0, dtype=torch.float32); yt = torch.tensor(y_tr, dtype=torch.long)
    xv = torch.tensor(Xq_va / 127.0, dtype=torch.float32)
    best, best_state = -1, None
    rng = np.random.default_rng(seed)
    for ep in range(epochs):
        perm = torch.tensor(rng.permutation(len(xt)))
        net.train()
        for i in range(0, len(xt), 1024):
            b = perm[i:i + 1024]
            opt.zero_grad(); loss = torch.nn.functional.cross_entropy(net(xt[b]), yt[b]); loss.backward(); opt.step()
        net.eval()
        with torch.no_grad(): pv = net(xv).argmax(1).numpy()
        f = f1_score(y_va, pv, average='macro', zero_division=0)
        if f > best: best, best_state = f, {k: v.clone() for k, v in net.state_dict().items()}
    net.load_state_dict(best_state)
    Ws = [net[i].weight.detach().numpy().astype(np.float64) for i in (0, 2, 4)]
    bs = [net[i].bias.detach().numpy().astype(np.float64) for i in (0, 2, 4)]
    return Ws, bs


def nn_float(Ws, bs, Xq):
    h = Xq / 127.0
    for i, (W, b) in enumerate(zip(Ws, bs)):
        h = h @ W.T + b
        if i < 2: h = np.maximum(h, 0)
    return h


def nn_quantize(Ws, bs, Xq_cal):
    """Post-training integer quantization. Input a0 = uint7 (0..127) with real value a0/127.
    Layer l: acc = sum(Wq * a) + bq (int32); real = acc * sw * sa; next activation
    a' = clamp(round(real / sa'), 0, 127) = (acc * M) >> 16 with M = round(sw * sa / sa' * 2^16)."""
    sa = [1 / 127.0]
    h = Xq_cal / 127.0
    for i, (W, b) in enumerate(zip(Ws[:2], bs[:2])):
        h = np.maximum(h @ W.T + b, 0)
        sa.append(max(np.percentile(h, 99.99), 1e-6) / 127.0)
    layers = []
    for i, (W, b) in enumerate(zip(Ws, bs)):
        sw = np.maximum(np.abs(W).max(1), 1e-12) / 127.0                     # per output channel
        Wq = np.clip(np.rint(W / sw[:, None]), -127, 127).astype(np.int32)
        bq = np.rint(b / (sw * sa[i])).astype(np.int64)
        if i < 2: M = np.rint(sw * sa[i] / sa[i + 1] * 65536).astype(np.int64)
        else: M = np.rint(sw / sw.max() * 65536).astype(np.int64)   # logits up to a common positive scale
        layers.append(dict(Wq=Wq, bq=bq.astype(np.int32), M=M.astype(np.int32)))
    return layers


def nn_int(layers, Xq):
    a = Xq.astype(np.int64)
    for i, L in enumerate(layers):
        acc = a @ L['Wq'].T.astype(np.int64) + L['bq']
        if i < 2: a = np.clip((acc * L['M']) >> 16, 0, 127)
        else: return (acc * L['M']) >> 16          # logits on a common scale; argmax decides
    return a


# ---------------------------------------------------------------- main
def main():
    npz, out = sys.argv[1], sys.argv[2]
    quick = '--quick' in sys.argv
    # --rf-deep: post-hoc EXTENSION (added 2026-11-04 after D3 showed DT D12 > RF D<=8). Only RF
    # T{16,32,64} x D{10,12}; rows tagged model 'RFdeep' so the frozen-grid selection is unchanged.
    deep = '--rf-deep' in sys.argv
    # --rf-leaf: post-hoc EXTENSION (added 2026-11-04 after E2 showed QS losing to the tree walk):
    # the classic QuickScorer regime, leaf-limited trees (max_leaf_nodes 32/64 -> one 64-bit word per
    # tree), unlimited depth, many trees. Rows tagged 'RFleaf', config T{T}L{L}.
    leaf = '--rf-leaf' in sys.argv
    deep = deep or leaf
    os.makedirs(out + '/models', exist_ok=True)
    D = np.load(npz, allow_pickle=False)
    ds = os.path.basename(npz).split('.')[0]
    X = D['X'].astype(np.int32); split = D['split']
    rows = []
    fields = ['dataset', 'task', 'model', 'config', 'seed', 'precision', 'n_train', 'n_val', 'n_test',
              'val_macro_f1', 'test_acc', 'test_macro_f1', 'test_bal_acc', 'test_fpr', 'test_per_class_f1',
              'nodes', 'leaves', 'max_leaves_per_tree', 'walk_bytes', 'qs_bytes', 'nn_params', 'nn_macs',
              'quant_agreement', 'train_s']
    fcsv = open(out + '/model_quality.csv', 'a', newline='')
    w = csv.DictWriter(fcsv, fieldnames=fields)
    if fcsv.tell() == 0: w.writeheader()
    for task in ('binary', 'multiclass'):
        y = (D['y_bin'] if task == 'binary' else D['y_mc']).astype(np.int64)
        names = ['benign', 'attack'] if task == 'binary' else [str(s) for s in D['mc_names']]
        C = len(names)
        valid = y >= 0
        rng = np.random.default_rng(12345)
        tr = capped(np.flatnonzero(valid & (split == 0)), y, CAP, rng)
        va = capped(np.flatnonzero(valid & (split == 1)), y, CAP, rng)
        te = capped(np.flatnonzero(valid & (split == 2)), y, CAP, rng)
        if quick: tr, va, te = tr[::20], va[::20], te[::20]
        Xq = logq(X)
        base = dict(dataset=ds, task=task, n_train=len(tr), n_val=len(va), n_test=len(te))
        print(f'[{ds}/{task}] C={C} train={len(tr)} val={len(va)} test={len(te)} names={names}', flush=True)

        def emit(model, config, seed, prec, pv, pt, extra, t0, agree=''):
            mv = metrics(y[va], pv); mt = metrics(y[te], pt)
            r = dict(base, model=model, config=config, seed=seed, precision=prec, val_macro_f1=mv['macro_f1'],
                     test_acc=mt['acc'], test_macro_f1=mt['macro_f1'], test_bal_acc=mt['bal_acc'],
                     test_fpr=mt['fpr'], test_per_class_f1=json.dumps({names[k]: round(v, 4) for k, v in mt['per_class_f1'].items()}),
                     quant_agreement=agree, train_s=round(time.time() - t0, 1), **extra)
            w.writerow({k: r.get(k, '') for k in fields}); fcsv.flush()
            print(f'  {model:3s} {config:10s} s{seed} {prec:5s} valF1={mv["macro_f1"]:.4f} testF1={mt["macro_f1"]:.4f} '
                  f'acc={mt["acc"]:.4f} fpr={mt["fpr"]:.4f}', flush=True)

        for seed in SEEDS:
            # ---- DT
            for d in (() if deep else DT_DEPTHS):
                t0 = time.time()
                m = DecisionTreeClassifier(max_depth=d, random_state=seed).fit(X[tr], y[tr])
                trees = [tree_export(m, C)]
                pv_q = argmax_low(forest_scores_q(trees, X[va])); pt_q = argmax_low(forest_scores_q(trees, X[te]))
                pt_f = m.predict(X[te])
                emit('DT', f'D{d}', seed, 'int', pv_q, pt_q, tree_stats(trees), t0, agree=float((pt_q == pt_f).mean()))
                np.savez_compressed(f'{out}/models/{ds}_{task}_DT_D{d}_s{seed}.npz', **_pack(trees), names=np.array(names))
            # ---- RF
            grid = ([(T, L) for T in (64, 128, 256, 512) for L in (32, 64)] if leaf else
                    [(T, d) for T in ((16, 32, 64) if deep else RF_T) for d in ((10, 12) if deep else RF_D)])
            for T, d in grid:
                if True:
                    t0 = time.time()
                    kw = dict(max_depth=None, max_leaf_nodes=d) if leaf else dict(max_depth=d)
                    m = RandomForestClassifier(n_estimators=T, max_features='sqrt', n_jobs=16,
                                               random_state=seed, **kw).fit(X[tr], y[tr])
                    trees = [tree_export(e, C) for e in m.estimators_]
                    st = tree_stats(trees)
                    pv_f = m.predict(X[va]); pt_f = m.predict(X[te])
                    emit(('RFleaf' if leaf else 'RFdeep' if deep else 'RF'), (f'T{T}L{d}' if leaf else f'T{T}D{d}'), seed, 'float', pv_f, pt_f, st, t0)
                    pv_q = argmax_low(forest_scores_q(trees, X[va])); pt_q = argmax_low(forest_scores_q(trees, X[te]))
                    emit(('RFleaf' if leaf else 'RFdeep' if deep else 'RF'), (f'T{T}L{d}' if leaf else f'T{T}D{d}'), seed, 'int', pv_q, pt_q, st, t0, agree=float((pt_q == pt_f).mean()))
                    np.savez_compressed(f'{out}/models/{ds}_{task}_RF_T{T}{"L" if leaf else "D"}{d}_s{seed}.npz', **_pack(trees), names=np.array(names))
            if deep: continue
            # ---- NN
            t0 = time.time()
            Ws, bs = train_nn(Xq[tr], y[tr], Xq[va], y[va], C, seed, epochs=8 if quick else 30)
            F = X.shape[1]
            nst = dict(nn_params=sum(W.size + b.size for W, b in zip(Ws, bs)), nn_macs=F * 16 + 16 * 16 + 16 * C)
            pv_f = nn_float(Ws, bs, Xq[va]).argmax(1); pt_f = nn_float(Ws, bs, Xq[te]).argmax(1)
            emit('NN', '16x16', seed, 'float', pv_f, pt_f, nst, t0)
            L = nn_quantize(Ws, bs, Xq[tr][:200000])
            pv_q = nn_int(L, Xq[va]).argmax(1); pt_q = nn_int(L, Xq[te]).argmax(1)
            emit('NN', '16x16', seed, 'int', pv_q, pt_q, nst, t0, agree=float((pt_q == pt_f).mean()))
            np.savez_compressed(f'{out}/models/{ds}_{task}_NN_16x16_s{seed}.npz',
                                **{f'{k}{i}': v for i, Lr in enumerate(L) for k, v in Lr.items()}, names=np.array(names))
    fcsv.close()


def _pack(trees):
    """Concatenate trees into flat arrays (node offsets per tree) for code generators."""
    off = np.cumsum([0] + [len(t['feat']) for t in trees]).astype(np.int32)
    return dict(offsets=off, left=np.concatenate([t['left'] for t in trees]),
                right=np.concatenate([t['right'] for t in trees]), feat=np.concatenate([t['feat'] for t in trees]),
                thr=np.concatenate([t['thr'] for t in trees]), leafq=np.concatenate([t['leafq'] for t in trees]))


if __name__ == '__main__':
    main()

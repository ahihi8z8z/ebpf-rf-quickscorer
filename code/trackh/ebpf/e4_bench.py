#!/usr/bin/env python3
"""E4 matched-model cost. For every RF swept in E2 (deployability_raw.csv) the fastest LOADED variant of
each runtime family is regenerated and timed together with the other families of the SAME model, a
null tail-call chain of the same stage count (chain overhead ablation) and, per (dataset, task), the
val-selected DT (as G-RF k1 and QS g1) and the NN (1 and 3 stages), in interleaved round-robin
passes with benchmulti.c on the DUT.
    python -I e4_bench.py <dataset.npz> <deployability_raw.csv> <model_quality.csv> <models dir> <work> <out csv> <ds>
Output: one row per (model, variant) with mean of per-pass means, 95% CI over passes, pooled p50/p95/p99."""
import csv, json, math, os, subprocess, sys
from collections import defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from e2_sweep import compile_one, DUT, sh, PY

RDIR = 'trackh/e4'
PASSES, NTIME, REPEAT = 10, 2000, 200
FIELDS = ['dataset', 'task', 'model', 'variant', 'family', 'stages', 'role', 'loaded', 'mismatch', 'rows',
          'ns_mean', 'ci95_lo', 'ci95_hi', 'pass_sd', 'ns_p50', 'ns_p95', 'ns_p99', 'passes', 'isa']
T975 = {9: 2.262, 4: 2.776, 19: 2.093}


def gen(mp, gdir, variant):
    pre, num = variant.split('_')
    flag = {'grf': '--grf-k', 'grfm': '--grfm-k', 'qs': '--qs-g', 'qsb': '--qs-g', 'qsl': '--qs-g',
            'rfw': '--rfw-g', 'rfwl': '--rfw-g', 'null': '--null-g'}.get(pre)
    args = [PY, '-I', os.path.join(HERE, 'codegen.py'), mp, gdir]
    if flag: args += [flag, num[1:]]
    sh(args)
    return os.path.join(gdir, variant + '.bpf.c')


def val_best(mq, ds, task, fam):
    best = {}
    for r in mq:
        if r['dataset'] == ds and r['task'] == task and r['model'] == fam and r['precision'] == 'int':
            best.setdefault(r['config'], []).append(float(r['val_macro_f1']))
    return max(best, key=lambda c: np.mean(best[c])) if best else None


def run_group(dsnpz, tvmodel, items, work, w, fo, ds, task):
    """items: list of (model npz, variant, family, stages, role). Test vectors from tvmodel; rows whose
    model differs are checked against their own reference only for mismatch reporting (separate tv)."""
    gdir = os.path.join(work, os.path.basename(tvmodel)[:-4]); os.makedirs(gdir, exist_ok=True)
    tv = os.path.join(gdir, 'tv')
    sh([PY, '-I', os.path.join(HERE, 'export_testvec.py'), dsnpz, tvmodel, tv, '20000'])
    objs, meta = [], []
    for mp, v, fam, st, role in items:
        d = os.path.join(work, os.path.basename(mp)[:-4]); os.makedirs(d, exist_ok=True)
        c = compile_one(gen(mp, d, v))
        if not c['compiled']: print('compile fail', mp, v, c['error'], flush=True); continue
        tag = f'{os.path.basename(mp)[:-4]}__{v}.bpf.o'
        sh(['scp', '-q', os.path.join(d, v + '.bpf.o'), f'{DUT}:{RDIR}/{tag}'])
        objs.append(tag); meta.append((mp, v, fam, st, role, c['isa']))
    sh(['scp', '-q', tv + '.X.i32', tv + '.pred.u8', f'{DUT}:{RDIR}/'])
    r = sh(['ssh', DUT, f'cd {RDIR} && sudo -n ./benchmulti tv.X.i32 tv.pred.u8 {NTIME} {REPEAT} {PASSES} ' + ' '.join(objs) +
            ' 2>/dev/null; rm -f ' + ' '.join(objs)], timeout=7200)
    res = {}
    for line in r.stdout.splitlines():
        try: j = json.loads(line); res[j['obj']] = j
        except Exception: pass
    for tag, (mp, v, fam, st, role, isa) in zip(objs, meta):
        j = res.get(tag, dict(loaded=0))
        row = dict(dataset=ds, task=task, model=os.path.basename(mp)[:-4], variant=v, family=fam, stages=st, role=role,
                   loaded=j.get('loaded', 0), isa=isa)
        if j.get('loaded'):
            pm = np.array(j['pass_mean_ns']); n = len(pm); m, sd = pm.mean(), pm.std(ddof=1)
            h = T975.get(n - 1, 2.0) * sd / math.sqrt(n)
            # mismatch is meaningful only for objects of the test-vector model (others: other model / null)
            mm = j['mismatch'] if mp == tvmodel and role != 'null' else ''
            row.update(mismatch=mm, rows=j['rows'], ns_mean=round(m, 1), ci95_lo=round(m - h, 1), ci95_hi=round(m + h, 1),
                       pass_sd=round(sd, 1), ns_p50=j['p50'], ns_p95=j['p95'], ns_p99=j['p99'], passes=n)
        w.writerow({k: row.get(k, '') for k in FIELDS}); fo.flush()
        print(row['model'], v, row.get('ns_mean'), row.get('ci95_lo'), row.get('ci95_hi'), row.get('mismatch'), flush=True)


def main():
    dsnpz, rawcsv, mqcsv, mdir, work, outcsv, ds = sys.argv[1:8]
    raw = [r for r in csv.DictReader(open(rawcsv)) if r['dataset'] == ds]
    mq = list(csv.DictReader(open(mqcsv)))
    done = {(r['model'], r['variant']) for r in csv.DictReader(open(outcsv))} if os.path.exists(outcsv) else set()
    fo = open(outcsv, 'a', newline=''); w = csv.DictWriter(fo, fieldnames=FIELDS)
    if fo.tell() == 0: w.writeheader()
    os.makedirs(work, exist_ok=True)
    sh(['ssh', DUT, f'mkdir -p {RDIR}'])
    sh(['scp', '-q', os.path.join(HERE, 'benchmulti.c'), f'{DUT}:{RDIR}/'])
    sh(['ssh', DUT, f'cd {RDIR} && gcc -O2 -o benchmulti benchmulti.c -lbpf'])
    by = defaultdict(list)
    for r in raw: by[r['model']].append(r)
    tasks = sorted({r['task'] for r in raw})
    for task in tasks:
        # model-family baselines for this task: val-selected DT and NN (seed 0)
        dt = val_best(mq, ds, task, 'DT'); nn = val_best(mq, ds, task, 'NN')
        dtp = os.path.join(mdir, f'{ds}_{task}_DT_{dt}_s0.npz'); nnp = os.path.join(mdir, f'{ds}_{task}_NN_{nn}_s0.npz')
        if (os.path.basename(dtp)[:-4], 'grf_k1') not in done and os.path.exists(dtp):
            run_group(dsnpz, dtp, [(dtp, 'grf_k1', 'DT-ifelse', 1, 'baseline'), (dtp, 'qs_g1', 'DT-QS', 1, 'baseline'),
                                   (dtp, 'rfwl_g1', 'DT-walk-bpfloop', 1, 'baseline'), (dtp, 'null_g1', 'null', 1, 'null'),
                                   (nnp, 'nn_s1', 'NN', 1, 'baseline'), (nnp, 'nn_s3', 'NN', 3, 'baseline'),
                                   (dtp, 'null_g3', 'null', 3, 'null')], work, w, fo, ds, task)
        if (os.path.basename(nnp)[:-4], 'nn_s1') not in done and os.path.exists(nnp):
            # NN correctness against its own reference (timing also recorded)
            run_group(dsnpz, nnp, [(nnp, 'nn_s1', 'NN', 1, 'check'), (nnp, 'nn_s3', 'NN', 3, 'check')], work, w, fo, ds, task)
        for model, rows in sorted(by.items()):
            if rows[0]['task'] != task: continue
            mp = os.path.join(mdir, model + '.npz')
            items, stages = [], set()
            fams = defaultdict(list)
            for r in rows:
                if r['loaded'] == '1' and r['ns_mean'] and r['mismatch'] in ('0', ''):
                    fams[r['family']].append(r)
            for fam, rs in sorted(fams.items()):
                b = min(rs, key=lambda r: float(r['ns_mean']))
                items.append((mp, b['variant'], fam, int(b['stages']), 'best-of-family')); stages.add(int(b['stages']))
            for s in sorted(stages):
                items.append((mp, f'null_g{s}', 'null', s, 'null'))
            if all((model, it[1]) in done for it in items): continue
            run_group(dsnpz, mp, items, work, w, fo, ds, task)
    fo.close()


if __name__ == '__main__':
    main()

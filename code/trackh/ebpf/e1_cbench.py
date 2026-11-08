#!/usr/bin/env python3
"""E1 step 4: isolated C inference cost of every seed-0 model (DT depths, RF grid, NN) of a dataset,
single thread on the DUT VM (same host as E2-E5; userspace, no XDP integration).
    python -I e1_cbench.py <dataset.npz> <models dir> <work dir> <out.csv> <ds>
RF/DT: tree walk and QuickScorer over identical tables (rfc.c); NN: nnc.c. Every runtime is checked
bit-exactly against the Python integer reference on 20 000 test rows before timing (median of 7
passes)."""
import csv, glob, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
DUT = os.environ.get('QS_DUT', 'haipt@192.168.101.51')


def sh(c, **k):
    return subprocess.run(c, capture_output=True, text=True, **k)


def main():
    dsnpz, mdir, work, outcsv, ds = sys.argv[1:6]
    os.makedirs(work, exist_ok=True)
    done = set()
    if os.path.exists(outcsv):
        done = {r['model'] for r in csv.DictReader(open(outcsv))}
    fields = ['dataset', 'task', 'model', 'family', 'config', 'rows', 'walk_ns', 'qs_ns', 'nn_ns', 'mismatch', 'NT', 'W', 'NC']
    fo = open(outcsv, 'a', newline=''); w = csv.DictWriter(fo, fieldnames=fields)
    if fo.tell() == 0: w.writeheader()
    sh(['ssh', DUT, 'mkdir -p trackh/e1c'])
    sh(['scp', '-q', os.path.join(HERE, 'rfc.c'), os.path.join(HERE, 'nnc.c'), f'{DUT}:trackh/e1c/'])
    for mp in sorted(glob.glob(os.path.join(mdir, f'{ds}_*_s0.npz'))):
        name = os.path.basename(mp)[:-4]
        if name in done: continue
        _, task, fam, cfg, _ = name.split('_')
        d = os.path.join(work, name); os.makedirs(d, exist_ok=True)
        sh([PY, '-I', os.path.join(HERE, 'export_testvec.py'), dsnpz, mp, os.path.join(d, 'tv'), '20000'])
        if fam == 'NN':
            sh([PY, '-I', os.path.join(HERE, 'nnc_gen.py'), mp, d]); files = ['nnc.h']; src, binn = 'nnc.c', 'nnc'
        else:
            sh([PY, '-I', os.path.join(HERE, 'codegen.py'), mp, d]); files = ['model.h', 'tw.h', 'qs1.h']; src, binn = 'rfc.c', 'rfc'
        rd = f'trackh/e1c/{name}'
        sh(['ssh', DUT, f'mkdir -p {rd}'])
        sh(['scp', '-q'] + [os.path.join(d, f) for f in files + ['tv.X.i32', 'tv.pred.u8']] + [f'{DUT}:{rd}/'])
        r = sh(['ssh', DUT, f'cd {rd} && gcc -O2 -march=native -I. ../{src} -o {binn} 2>&1 | tail -2 && ./{binn} tv.X.i32 tv.pred.u8 7; cd .. && rm -rf {name}'])
        try:
            j = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            print('FAIL', name, r.stdout[-300:], r.stderr[-300:], flush=True); continue
        row = dict(dataset=ds, task=task, model=name, family=fam, config=cfg, rows=j['rows'],
                   walk_ns=j.get('walk_ns', ''), qs_ns=j.get('qs_ns', ''), nn_ns=j.get('nn_ns', ''),
                   mismatch=j.get('walk_mismatch', 0) + j.get('qs_mismatch', 0) + j.get('nn_mismatch', 0),
                   NT=j.get('NT', ''), W=j.get('W', ''), NC=j.get('NC', ''))
        w.writerow(row); fo.flush()
        print(name, row['walk_ns'], row['qs_ns'], row['nn_ns'], row['mismatch'], flush=True)
    fo.close()


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""E4b: WHY QuickScorer wins in C but loses in eBPF in the <=64-leaf regime (direct measurement).
For each model (same 20 000 test rows, same tables):
  M1 hardware counters per inference
     - eBPF (kernel mode, BPF_PROG_TEST_RUN timing loop only; bench.c --perf): best G-RF, RF-walk
       (table, bpf_loop), QS (mask, bounds) from E4, the stack-bitvector QS ablation (qss), and a
       null chain for every stage count -> model-only cost = variant - null(same stages)
     - C (user mode; rfm.c): walk, qs, qs_bpf (eBPF code shape), qs_vol (+ volatile bitvector)
     - work counts per row: walk steps, QS updates (rfm.c)
  M2 JIT code: bpftool dump of xlated and jited code of stage 0 of every eBPF variant, and
     objdump of rfm (gcc) -> saved under out/e4b/code/<model>/
  M3 ablations: qs_bpf / qs_vol in C (verifier-forced code shape), qss_g* in eBPF (bitvector on
     the BPF stack instead of per-CPU map memory), rfm built with -fno-tree-vectorize (SIMD off)
    python -I e4b_mech.py <out csv> <model npz> [<model npz> ...]   (run from trackh/, DUT idle)"""
import csv, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TH = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from e2_sweep import compile_one, DUT, sh, PY

RDIR = 'trackh/e4b'
PASSES, NTIME, REPEAT = 3, 2000, 200
CNT = ['instructions', 'cycles', 'branches', 'branch_misses', 'l1d_loads', 'l1d_load_misses']
FIELDS = ['dataset', 'task', 'model', 'side', 'variant', 'family', 'stages', 'pass', 'ns', 'mismatch',
          'walk_steps', 'qs_updates', 'xlated_bytes', 'jited_bytes'] + CNT
FAM = {'grf': 'G-RF', 'grfm': 'G-RF-mem', 'qs': 'QS-mask', 'qsb': 'QS-bounds', 'qsl': 'QS-bpfloop',
       'rfw': 'RF-walk-table', 'rfwl': 'RF-walk-bpfloop', 'qss': 'QS-stack', 'null': 'null'}


def stages_of(v, T):
    pre, num = v.split('_'); k = int(num[1:])
    return -(-T // k) if pre in ('grf', 'grfm') else k


def gen(mp, gdir, v):
    pre, num = v.split('_')
    if pre == 'qss':        # ablation: same code as qs_g*, bitvector in a BPF stack array
        src = open(gen(mp, gdir, 'qs_' + num)).read()
        assert 'S->v[' in src
        src = src.replace('S->v[', 'qv[')
        src = re.sub(r'(struct scratch \*S = (?:entry\(ctx\)|get_scr\(\));)', r'\1 __u64 qv[VM + 1];', src)
        p = os.path.join(gdir, v + '.bpf.c'); open(p, 'w').write(src); return p
    flag = {'grf': '--grf-k', 'grfm': '--grfm-k', 'qs': '--qs-g', 'qsb': '--qs-g', 'qsl': '--qs-g',
            'rfw': '--rfw-g', 'rfwl': '--rfw-g', 'null': '--null-g'}[pre]
    sh([PY, '-I', os.path.join(HERE, 'codegen.py'), mp, gdir, flag, num[1:]])
    return os.path.join(gdir, v + '.bpf.c')


def pick_variants(name, T, e4):
    """fastest loaded variant per family from E4 (falls back to E2 raw), + qs/qss with <=32 trees/stage."""
    best = {}
    for r in e4:
        if r['model'] != name or r.get('loaded') != '1' or not r['ns_mean'] or r['variant'].startswith('null'): continue
        f = r['family']
        if f not in best or float(r['ns_mean']) < float(best[f]['ns_mean']): best[f] = r
    vs = [r['variant'] for r in best.values()]
    g = max(1, -(-T // 32))
    vs += [f'qs_g{g}', f'qss_g{g}']
    vs = list(dict.fromkeys(vs))
    vs += sorted({f'null_g{stages_of(v, T)}' for v in vs}, key=lambda s: int(s.split('_g')[1]))
    return vs


def main():
    outcsv, models = sys.argv[1], sys.argv[2:]
    e4p = os.path.join(TH, 'out', 'e4', 'inference_bench.csv')
    e4 = list(csv.DictReader(open(e4p))) if os.path.exists(e4p) else []
    fo = open(outcsv, 'a', newline=''); w = csv.DictWriter(fo, fieldnames=FIELDS)
    if fo.tell() == 0: w.writeheader()
    sh(['ssh', DUT, f'mkdir -p {RDIR}'])
    sh(['scp', '-q'] + [os.path.join(HERE, f) for f in ('bench.c', 'perfc.h', 'rfm.c')] + [f'{DUT}:{RDIR}/'])
    r = sh(['ssh', DUT, f'cd {RDIR} && gcc -O2 -o bench bench.c -lbpf 2>&1'])
    if r.stdout.strip(): print(r.stdout)
    for mp in models:
        name = os.path.basename(mp)[:-4]
        ds, task, _, cfg, _ = name.split('_')
        T = int(re.match(r'T(\d+)', cfg).group(1))
        dsnpz = os.path.join(TH, 'out', ds + '.npz')
        gdir = os.path.join(TH, 'out', 'e4b', 'work', name); os.makedirs(gdir, exist_ok=True)
        cdir = os.path.join(TH, 'out', 'e4b', 'code', name); os.makedirs(cdir, exist_ok=True)
        base = dict(dataset=ds, task=task, model=name)
        sh([PY, '-I', os.path.join(HERE, 'export_testvec.py'), dsnpz, mp, os.path.join(gdir, 'tv'), '20000'])
        sh([PY, '-I', os.path.join(HERE, 'codegen.py'), mp, gdir])           # model.h tw.h qs1.h
        rd = f'{RDIR}/{name}'
        sh(['ssh', DUT, f'mkdir -p {rd}'])
        sh(['scp', '-q'] + [os.path.join(gdir, f) for f in ('model.h', 'tw.h', 'qs1.h', 'tv.X.i32', 'tv.pred.u8')] + [f'{DUT}:{rd}/'])
        # ---- C side (M1 + M3 SIMD-off build) + gcc code (M2)
        for tag, extra in (('C', ''), ('C-novec', '-fno-tree-vectorize -fno-tree-slp-vectorize')):
            r = sh(['ssh', DUT, f'cd {rd} && gcc -O2 -march=native {extra} -I. -I.. ../rfm.c -o rfm 2>&1 | tail -3 && '
                                f'./rfm tv.X.i32 tv.pred.u8 5'])
            try: j = json.loads(r.stdout.strip().splitlines()[-1])
            except Exception: print('rfm FAIL', name, r.stdout[-300:], r.stderr[-300:], flush=True); continue
            if tag == 'C':
                d = sh(['ssh', DUT, f'cd {rd} && objdump -d --no-show-raw-insn rfm'])
                open(os.path.join(cdir, 'rfm_gcc.objdump'), 'w').write(d.stdout)
            for rt in ('walk', 'qs', 'qs_bpf', 'qs_vol'):
                row = dict(base, side=tag, variant=rt, family='C-' + rt, stages=1, ns=j.get(f'{rt}_ns'),
                           mismatch=j.get(f'{rt}_mismatch'), walk_steps=j['walk_steps'], qs_updates=j['qs_updates'],
                           **{c: j.get(f'{rt}_{c}') for c in CNT})
                w.writerow(row); fo.flush()
            print(name, tag, {k: j[k] for k in ('walk_steps', 'qs_updates', 'walk_ns', 'qs_ns', 'qs_bpf_ns', 'qs_vol_ns',
                                                 'walk_instructions', 'qs_instructions')}, flush=True)
            steps, upd = j['walk_steps'], j['qs_updates']
        # ---- eBPF side
        vs = pick_variants(name, T, e4)
        objs = {}
        for v in vs:
            c = compile_one(gen(mp, gdir, v))
            if c['compiled']:
                objs[v] = os.path.join(gdir, v + '.bpf.o')
                sh(['scp', '-q', objs[v], f'{DUT}:{rd}/{v}.bpf.o'])
            else:
                w.writerow(dict(base, side='eBPF', variant=v, family=FAM[v.split('_')[0]], stages=stages_of(v, T), ns='compile-failed'))
        print(name, 'eBPF variants', list(objs), flush=True)
        for p in range(PASSES):                    # interleaved passes
            for v in objs:
                r = sh(['ssh', DUT, f'cd {rd} && sudo -n timeout 900 ../bench {v}.bpf.o tv.X.i32 tv.pred.u8 {NTIME} {REPEAT} --perf 2>/dev/null | tail -1'])
                try: j = json.loads(r.stdout.strip().splitlines()[-1])
                except Exception: j = dict(loaded=0, error=(r.stdout + r.stderr)[-200:])
                row = dict(base, side='eBPF', variant=v, family=FAM[v.split('_')[0]], stages=stages_of(v, T), **{'pass': p},
                           walk_steps=steps, qs_updates=upd)
                if j.get('loaded'):
                    row.update(ns=j['ns_mean'], mismatch=j['mismatch'], xlated_bytes=j['xlated_bytes'], jited_bytes=j['jited_bytes'],
                               **{c: j.get('k_' + c) for c in CNT})
                else:
                    row.update(ns='load-failed: ' + str(j.get('error', ''))[:120])
                w.writerow(row); fo.flush()
                print(name, v, p, row['ns'], row.get('instructions'), flush=True)
        # ---- M2: xlated + jited code of every program of each variant
        for v in objs:
            pin = f'/sys/fs/bpf/e4b_{v}'
            r = sh(['ssh', DUT, f'cd {rd} && sudo -n rm -rf {pin}; sudo -n bpftool prog loadall {v}.bpf.o {pin} type xdp >/dev/null 2>&1; '
                                f'for p in $(sudo -n ls {pin}); do echo "=== $p xlated"; sudo -n bpftool prog dump xlated pinned {pin}/$p; '
                                f'echo "=== $p jited"; sudo -n bpftool prog dump jited pinned {pin}/$p; done; sudo -n rm -rf {pin}'])
            open(os.path.join(cdir, v + '.dump'), 'w').write(r.stdout)
        sh(['ssh', DUT, f'rm -rf {rd}'])
    fo.close()


if __name__ == '__main__':
    main()

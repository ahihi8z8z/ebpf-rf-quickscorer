#!/usr/bin/env python3
"""E2 (and E3 deployability) sweep: for each exported RF, generate and compile every runtime
variant, then load / verify / check / time it on the DUT with bench.c.
    python -I e2_sweep.py <dataset.npz> <models dir> <work dir> <out csv> <model glob>...
Variants per model (all the same quantized RF, same integer semantics):
  grf_k<K>   G-RF (Galvao-style if/else trees, K trees per tail-call stage). Grouping is tuned by
             halving K from T until a variant loads, then two more halvings are measured to show
             the trend (ceil(T/K) <= 33 stages, the tail-call limit).
  qs_g<G>    QuickScorer, masked table indices          G in {1,2,4,8}
  qsb_g<G>   QuickScorer, explicit bound checks          G in {1,2,4,8}
  qsl_g<G>   QuickScorer in bpf_loop callbacks           G in {1,2,4,8}
Rows already present in <out csv> (same model + variant) are skipped, so the sweep resumes."""
import csv, re, glob, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
DUT = os.environ.get('QS_DUT', 'haipt@192.168.101.51')
RDIR = 'trackh/e2'
CLANG = ['clang', '-O2', '-g', '-target', 'bpf', '-I/usr/include/x86_64-linux-gnu']
FIELDS = ['dataset', 'task', 'model', 'T', 'D', 'seed', 'variant', 'family', 'grouping', 'stages', 'compiled',
          'compile_s', 'loaded', 'error', 'errno', 'processed_insns_last', 'verified_insns', 'verified_insns_max_prog',
          'load_s', 'xlated_bytes', 'jited_bytes', 'rows', 'mismatch', 'bad_run', 'ns_mean', 'ns_p50', 'ns_p95',
          'ns_p99', 'ns_max', 'source_bytes', 'object_bytes', 'isa']


def sh(cmd, timeout=None, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


def compile_one(src, timeout=1800):
    """Default BPF ISA first; if the program is too long for 16-bit branch offsets, retry with
    -mcpu=v4 (32-bit gotol, supported by the DUT kernel 6.8) and record it."""
    obj = src.replace('.c', '.o')
    t0 = time.time(); isa = 'default'
    try:
        r = sh(CLANG + ['-I', os.path.dirname(src), '-c', src, '-o', obj], timeout=timeout)
        if r.returncode and 'Branch target out of insn range' in r.stderr:
            isa = 'v4'
            r = sh(CLANG + ['-mcpu=v4', '-I', os.path.dirname(src), '-c', src, '-o', obj], timeout=timeout)
        ok = r.returncode == 0
        err = '' if ok else (r.stderr.strip().splitlines() or ['?'])[-1][:200]
    except subprocess.TimeoutExpired:
        ok, err = False, f'compile timeout {timeout}s'
    return dict(compiled=int(ok), compile_s=round(time.time() - t0, 1), error='' if ok else err, isa=isa,
                source_bytes=os.path.getsize(src), object_bytes=os.path.getsize(obj) if ok else '')


def bench(objpath, tag):
    sh(['scp', '-q', objpath, f'{DUT}:{RDIR}/{tag}.bpf.o'])
    r = sh(['ssh', DUT, f'cd {RDIR} && sudo -n timeout 900 ./bench {tag}.bpf.o tv_{tag.split("__")[0]}.X.i32 '
                        f'tv_{tag.split("__")[0]}.pred.u8 2000 200 2>/dev/null | tail -1; '
                        f'gzip -f {tag}.bpf.o.vlog; rm -f {tag}.bpf.o'])
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return dict(loaded=0, error='bench: ' + (r.stdout + r.stderr)[-200:].replace('\n', ' '))


def main():
    dsnpz, mdir, work, outcsv = sys.argv[1:5]
    pats = sys.argv[5:]
    os.makedirs(work, exist_ok=True)
    done = set()
    if os.path.exists(outcsv):
        done = {(r['model'], r['variant']) for r in csv.DictReader(open(outcsv))}
    fo = open(outcsv, 'a', newline=''); w = csv.DictWriter(fo, fieldnames=FIELDS)
    if fo.tell() == 0: w.writeheader()
    sh(['ssh', DUT, f'mkdir -p {RDIR}'])
    sh(['scp', '-q', os.path.join(HERE, 'bench.c'), f'{DUT}:{RDIR}/'])
    sh(['ssh', DUT, f'cd {RDIR} && gcc -O2 -o bench bench.c -lbpf'])
    models = sorted({m for p in pats for m in glob.glob(os.path.join(mdir, p))})
    for mp in models:
        name = os.path.basename(mp)[:-4]
        ds, task, fam, cfg, seed = name.split('_')
        T = int(re.match(r'T(\d+)', cfg).group(1))
        D = int(cfg.split('D')[1]) if 'D' in cfg else 0   # leaf-limited T..L.. models: D=0 (unbounded depth)
        gdir = os.path.join(work, name); os.makedirs(gdir, exist_ok=True)
        base = dict(dataset=ds, task=task, model=name, T=T, D=D, seed=seed[1:])
        tvp = os.path.join(gdir, 'tv')
        if not os.path.exists(tvp + '.pred.u8'):
            sh([PY, '-I', os.path.join(HERE, 'export_testvec.py'), dsnpz, mp, tvp, '20000'])
        sh(['scp', '-q', tvp + '.X.i32', f'{DUT}:{RDIR}/tv_{name}.X.i32'])
        sh(['scp', '-q', tvp + '.pred.u8', f'{DUT}:{RDIR}/tv_{name}.pred.u8'])
        G_LIST = [1, 2, 4, 8]
        qs_vars = [f'{p}_g{g}' for g in G_LIST for p in ('qs', 'qsb', 'qsl', 'rfw', 'rfwl')]
        todo = [v for v in qs_vars if (name, v) not in done]
        if todo:
            sh([PY, '-I', os.path.join(HERE, 'codegen.py'), mp, gdir] + sum([['--qs-g', str(g), '--rfw-g', str(g)] for g in G_LIST], []))
        with ThreadPoolExecutor(6) as ex:
            comp = dict(zip(todo, ex.map(lambda v: compile_one(os.path.join(gdir, v + '.bpf.c')), todo)))
        for v in todo:
            g = int(v.split('_g')[1])
            row = dict(base, variant=v, family={'qs': 'QS-mask', 'qsb': 'QS-bounds', 'qsl': 'QS-bpfloop', 'rfw': 'RF-walk-table',
                                               'rfwl': 'RF-walk-bpfloop'}[v.split('_')[0]],
                       grouping='equal-trees', stages=g, **comp[v])
            if row['compiled']: row.update(bench(os.path.join(gdir, v + '.bpf.o'), f'{name}__{v}'))
            w.writerow({k: row.get(k, '') for k in FIELDS}); fo.flush()
            print(name, v, row.get('loaded'), row.get('ns_mean'), row.get('error', ''), flush=True)
        # G-RF grouping search (register accumulation = Galvao style; grfm = scores accumulated in
        # scratch memory, a verifier-friendlier variant)
        # grfx = G-RF with per-comparison feature reads from scratch (verifier-linear; added 2026-11-08)
        for pre, fam, flag in (('grf', 'G-RF', '--grf-k'), ('grfm', 'G-RF-mem', '--grfm-k'), ('grfx', 'G-RF-x', '--grfx-k')):
            K, measured_after = T, 0
            while K >= 1 and measured_after < 3:
                stages = -(-T // K)
                v = f'{pre}_k{K}'
                if stages <= 33 and (name, v) not in done:
                    sh([PY, '-I', os.path.join(HERE, 'codegen.py'), mp, gdir, flag, str(K)])
                    row = dict(base, variant=v, family=fam, grouping=f'{K} trees/stage', stages=stages,
                               **compile_one(os.path.join(gdir, v + '.bpf.c')))
                    if row['compiled']: row.update(bench(os.path.join(gdir, v + '.bpf.o'), f'{name}__{v}'))
                    w.writerow({k: row.get(k, '') for k in FIELDS}); fo.flush()
                    print(name, v, row.get('loaded'), row.get('ns_mean'), row.get('error', ''), flush=True)
                    for ext in ('.bpf.c', '.bpf.o'):
                        p = os.path.join(gdir, v + ext)
                        if os.path.exists(p) and os.path.getsize(p) > 20 << 20: os.remove(p)
                    loaded = int(row.get('loaded') or 0)
                elif stages <= 33:
                    prev = [r for r in csv.DictReader(open(outcsv)) if r['model'] == name and r['variant'] == v]
                    loaded = int(prev[0]['loaded'] or 0) if prev else 0
                else:
                    loaded = 0
                if loaded or measured_after: measured_after += 1
                K //= 2
        sh(['ssh', DUT, f'rm -f {RDIR}/tv_{name}.*'])
    fo.close()


if __name__ == '__main__':
    main()

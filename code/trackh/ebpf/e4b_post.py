#!/usr/bin/env python3
"""E4b follow-up: is the C-vs-eBPF reversal an artefact of the timing regime?
BPF_PROG_TEST_RUN(.repeat=R) runs ONE row R times in a row (warm branch predictor, warm lines), while rfm.c
cycles through all rows. Measure both runtimes in both regimes on the DUT, same models / tables:
  eBPF cold : bench ntime=20000 repeat=1 --perf (every call a new row), 3 interleaved passes, incl. null
  eBPF warm : already in out/e4b/mech.csv (repeat=200)
  C warm    : rfm rowrep=200 (each row 200 times in a row)
  C cold    : already in out/e4b/mech.csv (rowrep=1)
Also saves the raw JIT image (bpftool ... dump jited file) of stage 0 of qs_g1 / best walk / best G-RF and
disassembles it locally with objdump (bpftool on the DUT has no JIT disassembler).
    python -I e4b_post.py <out csv> <model npz> [...]     (run from trackh/, DUT idle, after e4b_mech)"""
import csv, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TH = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from e2_sweep import DUT, sh
from e4b_mech import CNT, FAM, stages_of, RDIR

FIELDS = ['dataset', 'task', 'model', 'side', 'regime', 'variant', 'family', 'stages', 'pass', 'ns', 'mismatch'] + CNT


def main():
    outcsv, models = sys.argv[1], sys.argv[2:]
    mech = [r for r in csv.DictReader(open(os.path.join(TH, 'out', 'e4b', 'mech.csv'))) if r['side'] == 'eBPF']
    fo = open(outcsv, 'a', newline=''); w = csv.DictWriter(fo, fieldnames=FIELDS)
    if fo.tell() == 0: w.writeheader()
    sh(['ssh', DUT, f'mkdir -p {RDIR}'])
    sh(['scp', '-q'] + [os.path.join(HERE, f) for f in ('bench.c', 'perfc.h', 'rfm.c')] + [f'{DUT}:{RDIR}/'])
    sh(['ssh', DUT, f'cd {RDIR} && gcc -O2 -o bench bench.c -lbpf'])
    for mp in models:
        name = os.path.basename(mp)[:-4]
        ds, task, _, cfg, _ = name.split('_')
        T = int(re.match(r'T(\d+)', cfg).group(1))
        gdir = os.path.join(TH, 'out', 'e4b', 'work', name)
        cdir = os.path.join(TH, 'out', 'e4b', 'code', name); os.makedirs(cdir, exist_ok=True)
        base = dict(dataset=ds, task=task, model=name)
        rd = f'{RDIR}/post_{name}'
        sh(['ssh', DUT, f'mkdir -p {rd}'])
        sh(['scp', '-q'] + [os.path.join(gdir, f) for f in ('model.h', 'tw.h', 'qs1.h', 'tv.X.i32', 'tv.pred.u8')] + [f'{DUT}:{rd}/'])
        # ---- C warm (rowrep 200 on the first 2000 rows: 400k calls per pass)
        r = sh(['ssh', DUT, f'cd {rd} && head -c {2000 * 17 * 4} tv.X.i32 > x2k && head -c 2000 tv.pred.u8 > p2k && '
                            f'gcc -O2 -march=native -I. -I.. ../rfm.c -o rfm && ./rfm x2k p2k 3 200'])
        try:
            j = json.loads(r.stdout.strip().splitlines()[-1])
            for rt in ('walk', 'qs', 'qs_bpf', 'qs_vol'):
                w.writerow(dict(base, side='C', regime='warm_rowrep200', variant=rt, family='C-' + rt, stages=1,
                                ns=j.get(f'{rt}_ns'), mismatch=j.get(f'{rt}_mismatch'), **{c: j.get(f'{rt}_{c}') for c in CNT}))
            fo.flush(); print(name, 'C warm', {k: j[k] for k in ('walk_ns', 'qs_ns')}, flush=True)
        except Exception:
            print('rfm FAIL', name, r.stdout[-300:], r.stderr[-300:], flush=True)
        # ---- eBPF cold: same variant set as e4b_mech (minus the qss ablation)
        vs = list(dict.fromkeys(rr['variant'] for rr in mech if rr['model'] == name and not rr['variant'].startswith('qss')))
        vs = [v for v in vs if os.path.exists(os.path.join(gdir, v + '.bpf.o'))]
        sh(['scp', '-q'] + [os.path.join(gdir, v + '.bpf.o') for v in vs] + [f'{DUT}:{rd}/'])
        for p in range(3):
            for v in vs:
                r = sh(['ssh', DUT, f'cd {rd} && sudo -n timeout 900 ../bench {v}.bpf.o tv.X.i32 tv.pred.u8 20000 1 --perf 2>/dev/null | tail -1'])
                try: j = json.loads(r.stdout.strip().splitlines()[-1])
                except Exception: j = dict(loaded=0)
                row = dict(base, side='eBPF', regime='cold_repeat1', variant=v, family=FAM[v.split('_')[0]], stages=stages_of(v, T), **{'pass': p})
                if j.get('loaded'): row.update(ns=j['ns_mean'], mismatch=j['mismatch'], **{c: j.get('k_' + c) for c in CNT})
                else: row.update(ns='load-failed')
                w.writerow(row); fo.flush(); print(name, 'cold', v, p, row['ns'], row.get('instructions'), flush=True)
        # ---- raw JIT images of stage 0 -> local objdump
        for v in vs:
            if v.startswith('null'): continue
            pin = f'/sys/fs/bpf/e4bp_{v}'
            sh(['ssh', DUT, f'cd {rd} && sudo -n rm -rf {pin}; sudo -n bpftool prog loadall {v}.bpf.o {pin} type xdp >/dev/null 2>&1; '
                            f'p=$(sudo -n ls {pin} | sort | head -1); sudo -n bpftool prog dump jited pinned {pin}/$p file {v}.jit; '
                            f'sudo -n chmod a+r {v}.jit; sudo -n rm -rf {pin}'])
            loc = os.path.join(cdir, v + '.jit')
            if sh(['scp', '-q', f'{DUT}:{rd}/{v}.jit', loc]).returncode == 0:
                d = subprocess.run(['objdump', '-D', '-b', 'binary', '-mi386:x86-64', '--no-show-raw-insn', loc], capture_output=True, text=True)
                open(loc + '.s', 'w').write(d.stdout)
        sh(['ssh', DUT, f'rm -rf {rd}'])
    fo.close()


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""E5 end-to-end XDP: online Track-H frontend + model in native XDP on the DUT, traffic replayed by the TG.
    python -I e5_run.py prep <ds> <spec.json>              build labelled replay slices (server3)
    python -I e5_run.py run  <ds> <variants.json> <out.csv> fidelity (1x) + offered-load runs
spec.json: {"slices": [{"pcap": path, "start": epoch_s, "dur": s, "prefix": trackh prefix (full .trig/.lab)}],
            "mc_names": [...]}   (written by e5_select.py)
variants.json: [{"model": npz, "variant": "grf_k8"|"qs_g1"|...|"nn_s1"|"null_g1", "family": str}]

Fidelity run (1x replay of all slices, in order): online events are matched to the offline flowfeat
records of the same slices (5-tuple + occurrence order); we report coverage, exact agreement of the
14 timing-free features, timing-feature error, online-vs-offline class agreement and online macro-F1
against the offline labels next to the offline macro-F1 of the same model on the same flows.
Offered-load runs: tcpreplay --topspeed / fixed --pps with --loop and --unique-ip (new 5-tuples per
loop); DUT packet counter vs TG sent, DUT CPU busy+softirq seconds per packet."""
import csv, json, os, re, subprocess, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TH = os.path.dirname(HERE)
sys.path.insert(0, TH); sys.path.insert(0, HERE)
from label_flows import TRIG
from e2_sweep import compile_one, sh, PY, DUT
TG = os.environ.get('QS_TG', 'haipt@192.168.101.52')
DUT_MAC, TG_MAC = '52:54:00:51:a0:51', '52:54:00:51:a0:52'
EV = np.dtype([('ts_first_us', '<u8'), ('ini_ip', '<u4'), ('resp_ip', '<u4'), ('ini_port', '<u2'), ('resp_port', '<u2'),
               ('proto', 'u1'), ('cls', 'u1'), ('pad', 'u1', 2), ('f', '<i4', 17), ('pad2', '<u4')])
TIMING = [8, 9, 10]
NOTIME = [i for i in range(17) if i not in TIMING]


def macro_f1(y, p, C):
    f = []
    for c in range(C):
        tp = ((p == c) & (y == c)).sum(); fp = ((p == c) & (y != c)).sum(); fn = ((p != c) & (y == c)).sum()
        if tp + fp + fn: f.append(2 * tp / (2 * tp + fp + fn))
    return float(np.mean(f)) if f else float('nan')


# ------------------------------------------------------------------ prep
def prep(ds, spec_path):
    from make_dataset import family, BENIGN
    spec = json.load(open(spec_path)); mc = spec['mc_names']
    out = os.path.join(TH, 'out', 'e5', ds); os.makedirs(out, exist_ok=True)
    allrec, ybin, ymc, sl = [], [], [], []
    for i, s in enumerate(spec['slices']):
        pc = os.path.join(out, f'slice{i}.pcap')
        if not os.path.exists(pc):
            srcs = s['pcap'] if isinstance(s['pcap'], list) else [s['pcap']]
            parts = []
            for k, src in enumerate(srcs):
                part = pc + f'.part{k}'
                subprocess.run(['editcap', '-F', 'pcap', '-A', str(s['start']), '-B', str(s['start'] + s['dur']), src, part], check=True)
                parts.append(part)
            if len(parts) == 1: os.rename(parts[0], pc)
            else:   # consecutive capture files: concatenate in file order (keeps the original packet order)
                subprocess.run(['mergecap', '-F', 'pcap', '-a', '-w', pc] + parts, check=True)
                for part in parts: os.remove(part)
        # the replayed packets: Ethernet, MACs set, every other byte kept, >1514-byte frames dropped
        tx = os.path.join(out, f'slice{i}.tx.pcap')
        if not os.path.exists(tx):
            r = subprocess.run([PY, '-I', os.path.join(HERE, 'e5_pcapfix.py'), pc, tx, DUT_MAC, TG_MAC], check=True, capture_output=True, text=True)
            open(os.path.join(out, f'slice{i}.tx.json'), 'w').write(r.stdout)
        txst = json.loads(open(os.path.join(out, f'slice{i}.tx.json')).read())
        # offline reference = flowfeat over exactly the replayed packets
        pre = os.path.join(out, f'slice{i}tx')
        if not os.path.exists(pre + '.trig'):
            subprocess.run([os.path.join(TH, 'flowfeat'), pre, tx], check=True, capture_output=True)
        tr = np.fromfile(pre + '.trig', TRIG)
        full = np.fromfile(os.path.join(TH, s['prefix'] + '.trig'), TRIG)
        lab = np.load(os.path.join(TH, s['prefix'] + '.lab.npy'))
        names = json.load(open(os.path.join(TH, s['prefix'] + '.lab.json')))['classes']
        key = lambda r: (int(r['ts_first_us']), int(r['ini_ip']), int(r['ini_port']), int(r['resp_ip']), int(r['resp_port']), int(r['proto']))
        idx = {key(r): j for j, r in enumerate(full)}
        # fallback when an oversize first packet was dropped: same direction-free 5-tuple, latest full-capture
        # flow that started at most 120 s (the flow timeout) before the replayed flow's first packet
        dfree = lambda r: (min((int(r['ini_ip']), int(r['ini_port'])), (int(r['resp_ip']), int(r['resp_port']))),
                           max((int(r['ini_ip']), int(r['ini_port'])), (int(r['resp_ip']), int(r['resp_port']))), int(r['proto']))
        byk = {}
        for j, r in enumerate(full): byk.setdefault(dfree(r), []).append((int(r['ts_first_us']), j))
        nfb = 0
        for r in tr:
            j = idx.get(key(r))
            if j is None:
                c = [(t, jj) for t, jj in byk.get(dfree(r), []) if 0 <= int(r['ts_first_us']) - t <= 120_000_000]
                if c: j = max(c)[1]; nfb += 1
            l = lab[j] if j is not None else 255
            if j is None or l >= len(names):           # starts before the slice / unlabelled / ambiguous
                ybin.append(-1); ymc.append(-1)
            else:
                nat = names[l]; fam = family(ds, nat)
                ybin.append(0 if nat in BENIGN else 1); ymc.append(mc.index(fam) if fam in mc else -1)
        allrec.append(tr); sl += [i] * len(tr)
        print(f'slice{i}: {len(tr)} triggered flows, labelled {sum(1 for v in ybin[-len(tr):] if v >= 0)} '
              f'(label fallback {nfb}); replay {json.dumps(txst)}', flush=True)
        s['replay'] = dict(txst, label_fallback=nfb)
    tr = np.concatenate(allrec)
    if os.path.exists(os.path.join(out, 'offline.npz')) and not os.path.exists(os.path.join(out, 'offline_v1_tcprewrite.npz')):
        os.rename(os.path.join(out, 'offline.npz'), os.path.join(out, 'offline_v1_tcprewrite.npz'))
    np.savez(os.path.join(out, 'offline.npz'), trig=tr.view(np.uint8).reshape(len(tr), -1), y_bin=np.array(ybin),
             y_mc=np.array(ymc), slice=np.array(sl), mc_names=np.array(mc))
    # stage slices on the TG with rewritten MACs
    sh(['ssh', TG, f'mkdir -p e5/{ds}'])
    for i in range(len(spec['slices'])):
        sh(['scp', '-q', os.path.join(out, f'slice{i}.tx.pcap'), f'{TG}:e5/{ds}/s{i}.pcap'])
    json.dump(dict(spec, n_slices=len(spec['slices'])), open(os.path.join(out, 'spec.json'), 'w'), indent=1)


# ------------------------------------------------------------------ run
def build(v, work):
    mp = v['model']; name = os.path.basename(mp)[:-4]
    d = os.path.join(work, name); os.makedirs(d, exist_ok=True)
    pre, num = v['variant'].split('_')
    flag = {'grf': '--grf-k', 'grfm': '--grfm-k', 'qs': '--qs-g', 'qsb': '--qs-g', 'qsl': '--qs-g',
            'rfw': '--rfw-g', 'rfwl': '--rfw-g', 'null': '--null-g'}.get(pre)
    sh([PY, '-I', os.path.join(HERE, 'codegen.py'), mp, d] + ([flag, num[1:]] if flag else []))
    src = os.path.join(d, v['variant'] + '.bpf.c')
    fe = os.path.join(d, 'fe_' + v['variant'] + '.bpf.c')
    open(fe, 'w').write('#define FRONTEND 1\n#define FE_EVENT_FEAT 1\n' + open(src).read())
    sh(['cp', os.path.join(HERE, 'frontend.h'), d])
    c = compile_one(fe)
    return fe.replace('.c', '.o') if c['compiled'] else None, name


def collect(obj, tag, seconds, tg_cmd):
    """start fe_collect on the DUT, wait for READY, run tg_cmd on the TG, wait for the collector."""
    sh(['scp', '-q', obj, f'{DUT}:trackh/e5/{tag}.o'])
    p = subprocess.Popen(['ssh', DUT, f'cd trackh/e5 && sudo -n ./fe_collect {tag}.o data0 {tag}.ev {seconds} 96'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    line = p.stdout.readline()
    if 'READY' not in line:
        return dict(error='collector: ' + line + p.stderr.read()[-300:]), None
    t0 = time.time(); r = sh(['ssh', TG, tg_cmd]); tg_s = time.time() - t0
    sh(['ssh', DUT, 'sudo -n pkill -INT fe_collect'])
    out, err = p.communicate(timeout=120)
    try: j = json.loads(out.strip().splitlines()[-1])
    except Exception: return dict(error='collector: ' + out[-200:] + err[-200:]), None
    # one or several (parallel) tcpreplay reports: total packets / longest sender time
    acts = re.findall(r'Actual: (\d+) packets .* in ([\d.]+) seconds', r.stdout)
    j['tg_sent'] = sum(int(a) for a, _ in acts) if acts else ''
    j['tg_s'] = max(float(b) for _, b in acts) if acts else round(tg_s, 2)
    j['tg_pps'] = round(j['tg_sent'] / j['tg_s'], 1) if acts and j['tg_s'] else ''
    return j, f'{tag}.ev'


def fidelity(ev, off, cls_off, C, task):
    tr = off['trig']; y = off['y_bin'] if task == 'binary' else off['y_mc']
    k5 = lambda a: list(zip(a['ini_ip'].tolist(), a['ini_port'].tolist(), a['resp_ip'].tolist(), a['resp_port'].tolist(), a['proto'].tolist()))
    pos = {}
    for j, k in enumerate(k5(tr)): pos.setdefault(k, []).append(j)
    used = {}; match = np.full(len(ev), -1)
    for i, k in enumerate(k5(ev)):
        lst = pos.get(k); n = used.get(k, 0)
        if lst and n < len(lst): match[i] = lst[n]; used[k] = n + 1
    m = match >= 0; mi = match[m]
    fo, fe = tr['f'][mi], ev['f'][m]
    exact = (fo[:, NOTIME] == fe[:, NOTIME]).all(1)
    terr = np.abs(fo[:, TIMING].astype(np.int64) - fe[:, TIMING]) / np.maximum(1, np.abs(fo[:, TIMING]))
    lab = y[mi] >= 0
    on, offp = ev['cls'][m].astype(int), cls_off[mi]
    return dict(online_events=len(ev), offline_flows=len(tr), matched=int(m.sum()), match_share=round(m.sum() / max(1, len(tr)), 4),
                feat_exact_notiming=round(float(exact.mean()), 4) if m.any() else '',
                timing_relerr_p50=round(float(np.median(terr)), 4) if m.any() else '',
                timing_relerr_p95=round(float(np.percentile(terr, 95)), 4) if m.any() else '',
                class_agree=round(float((on == offp).mean()), 4) if m.any() else '',
                labelled=int(lab.sum()), online_macro_f1=round(macro_f1(y[mi][lab], on[lab], C), 4),
                offline_macro_f1_same_flows=round(macro_f1(y[mi][lab], offp[lab], C), 4),
                offline_macro_f1_all=round(macro_f1(y[y >= 0], cls_off[y >= 0], C), 4))


def offline_pred(mp, X):
    from train_e1 import forest_scores_q, argmax_low, nn_int, logq
    m = np.load(mp)
    if 'Wq0' in m:
        return nn_int([dict(Wq=m[f'Wq{i}'], bq=m[f'bq{i}'], M=m[f'M{i}']) for i in range(3)], logq(X)).argmax(1)
    off = m['offsets']
    trees = [dict(left=m['left'][a:b], right=m['right'][a:b], feat=m['feat'][a:b], thr=m['thr'][a:b], leafq=m['leafq'][a:b])
             for a, b in zip(off[:-1], off[1:])]
    return argmax_low(forest_scores_q(trees, X))


FIELDS = ['dataset', 'task', 'model', 'variant', 'family', 'run', 'replay', 'loops', 'tg_sent', 'tg_s', 'tg_pps', 'packets',
          'pkt_share', 'triggers', 'events', 'ev_dropped', 'unavailable', 'cpu_busy_s', 'cpu_softirq_s', 'cpu_ns_per_pkt',
          'online_events', 'offline_flows', 'matched', 'match_share', 'feat_exact_notiming', 'timing_relerr_p50',
          'timing_relerr_p95', 'class_agree', 'labelled', 'online_macro_f1', 'offline_macro_f1_same_flows',
          'offline_macro_f1_all', 'error']


def run(ds, vpath, outcsv, loads):
    out = os.path.join(TH, 'out', 'e5', ds); spec = json.load(open(os.path.join(out, 'spec.json')))
    o = np.load(os.path.join(out, 'offline.npz'))
    off = dict(trig=o['trig'].reshape(-1).view(TRIG), y_bin=o['y_bin'], y_mc=o['y_mc'])
    X = off['trig']['f'].astype(np.int32)
    files = ' '.join(f's{i}.pcap' for i in range(spec['n_slices']))
    dur = sum(s['dur'] for s in spec['slices'])
    sh(['ssh', DUT, 'mkdir -p trackh/e5'])
    sh(['scp', '-q', os.path.join(HERE, 'fe_collect.c'), f'{DUT}:trackh/e5/'])
    sh(['ssh', DUT, 'cd trackh/e5 && gcc -O2 -o fe_collect fe_collect.c -lbpf'])
    done = {(r['model'], r['variant'], r['run']) for r in csv.DictReader(open(outcsv))} if os.path.exists(outcsv) else set()
    fo = open(outcsv, 'a', newline=''); w = csv.DictWriter(fo, fieldnames=FIELDS)
    if fo.tell() == 0: w.writeheader()
    work = os.path.join(out, 'work')
    for v in json.load(open(vpath)):
        obj, name = build(v, work)
        task = name.split('_')[1]; C = 2 if task == 'binary' else len(spec['mc_names'])
        base = dict(dataset=ds, task=task, model=name, variant=v['variant'], family=v['family'])
        if obj is None:
            w.writerow(dict(base, run='build', error='compile failed')); fo.flush(); continue
        cls_off = offline_pred(v['model'], X) if not v['variant'].startswith('null') else np.zeros(len(X), int)
        # null has no classifier: offered-load floor only (feature fidelity is checked with every real model)
        runs = [] if v['variant'].startswith('null') else [('fidelity_1x', f'cd e5/{ds} && sudo -n tcpreplay -i data0 {files}', dur + 30, 1)]
        for pps in loads:
            lp = 3
            if pps.startswith('top') and pps != 'top':      # topK: K parallel senders, disjoint address spaces
                K = int(pps[3:])
                cmd = (f'cd e5/{ds} && for k in $(seq 0 {K - 1}); do sudo -n tcpreplay-edit -i data0 '
                       f'--pnat=0.0.0.0/0:$((10+k)).0.0.0/8 --unique-ip --loop={lp} --topspeed {files} > /tmp/e5r$k.log 2>&1 & done; '
                       f'wait; cat /tmp/e5r*.log; rm -f /tmp/e5r*.log')
            else:
                cmd = (f'cd e5/{ds} && sudo -n tcpreplay -i data0 --unique-ip --loop={lp} ' +
                       ('--topspeed ' if pps == 'top' else f'--pps={pps} ') + files)
            runs.append((f'load_{pps}', cmd, 3600, lp))
        for rn, cmd, secs, lp in runs:
            if (name, v['variant'], rn) in done: continue
            tag = f'{name}__{v["variant"]}__{rn}'
            j, evf = collect(obj, tag, secs, cmd)
            row = dict(base, run=rn, replay=re.sub(r'\s+', ' ', cmd.split('&&', 1)[1])[:200], loops=lp, **{k: j.get(k, '') for k in
                       ('tg_sent', 'tg_s', 'tg_pps', 'packets', 'triggers', 'events', 'ev_dropped', 'unavailable',
                        'cpu_busy_s', 'cpu_softirq_s', 'error')})
            if j.get('packets') and j.get('tg_sent'):
                row['pkt_share'] = round(j['packets'] / j['tg_sent'], 4)
                row['cpu_ns_per_pkt'] = round(1e9 * j['cpu_busy_s'] / j['packets'], 1)
            if evf and rn == 'fidelity_1x':
                lev = os.path.join(work, tag + '.ev')
                sh(['scp', '-q', f'{DUT}:trackh/e5/{evf}', lev])
                row.update(fidelity(np.fromfile(lev, EV), off, cls_off, C, task))
            sh(['ssh', DUT, f'rm -f trackh/e5/{tag}.ev trackh/e5/{tag}.o'])
            w.writerow({k: row.get(k, '') for k in FIELDS}); fo.flush()
            print(json.dumps({k: row.get(k) for k in ('model', 'variant', 'run', 'tg_pps', 'pkt_share', 'cpu_ns_per_pkt',
                                                      'match_share', 'feat_exact_notiming', 'class_agree', 'online_macro_f1',
                                                      'offline_macro_f1_same_flows', 'error')}), flush=True)
    fo.close()


if __name__ == '__main__':
    if sys.argv[1] == 'prep': prep(sys.argv[2], sys.argv[3])
    else: run(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5].split(',') if len(sys.argv) > 5 else ['top'])

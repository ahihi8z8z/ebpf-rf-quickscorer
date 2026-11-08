#!/usr/bin/env python3
"""Labels for Track-H triggered flows (flowfeat .trig records). See dataset_protocol.md.
    label_flows.py cic   <prefix> <TrafficLabelling CSV>...   [--match-min 2]
    label_flows.py unsw  <prefix> <UNSW-NB15_[1-4].csv>...    [--match-s 2]
    label_flows.py ciciot <prefix> <class name> [--attackers ip,ip,...]
Writes <prefix>.lab.npy (uint8 index into the label list, 254 unlabelled, 253 ambiguous) and
<prefix>.lab.json (label list, counts). Labels are the dataset's own native labels; class mapping
and splits are applied later (make_splits.py).
cic : a flow takes the label of the CICFlowMeter rows of its direction-free 5-tuple whose minute
      window [start, start+duration] (+-match-min) contains the flow's first-packet minute (CSV time is
      UTC-3, 12-hour clock without AM/PM). {BENIGN, attack} -> attack (CICFlowMeter BENIGN rows
      for attack tails, as in Track-R); several attack labels -> ambiguous.
unsw: rows of UNSW-NB15_1..4.csv (Argus) with the same direction-free 5-tuple whose [Stime, Ltime]
      (+-match-s seconds) contains the flow's first-packet time; attack_cat blank -> 'Normal'.
      Same {Normal, attack} -> attack rule.
ciciot: every flow of a capture file gets that file's class (the dataset's own labelling: each
      capture is one attack session); with --attackers, flows of an attack file that do not involve
      an attacker address are labelled 'Background' (kept out of the attack class)."""
import collections, csv, json, socket, struct, sys
import numpy as np

TRIG = np.dtype([('ts_first_us', '<u8'), ('ts_trig_us', '<u8'), ('ini_ip', '<u4'), ('resp_ip', '<u4'),
                 ('ini_port', '<u2'), ('resp_port', '<u2'), ('proto', 'u1'), ('pad', 'u1', 3),
                 ('flow_id', '<u4'), ('f', '<i4', 17), ('pad2', '<u4', 2)])
FLOW = np.dtype([('ts_first_us', '<u8'), ('ts_last_us', '<u8'), ('ini_ip', '<u4'), ('resp_ip', '<u4'),
                 ('ini_port', '<u2'), ('resp_port', '<u2'), ('proto', 'u1'), ('triggered', 'u1'), ('pad', '<u2'),
                 ('npkts', '<u4'), ('flow_id', '<u4')])
SRC = dict(rec='.trig', dt=TRIG, out='.lab')   # switched to all flows by --all-flows (coverage audit)
UNLAB, AMBIG = 254, 253
PROTO = {'tcp': 6, 'udp': 17, 'icmp': 1}


def proto_num(name, _cache={}):
    """Argus protocol name -> IP protocol number (/etc/protocols); None for non-IP / unknown ('arp', 'unas', 'any')."""
    name = name.strip().lower()
    if name not in _cache:
        import socket
        try: _cache[name] = PROTO.get(name) or socket.getprotobyname(name)
        except OSError: _cache[name] = None
    return _cache[name]


def ip_u32(s):
    return struct.unpack('<I', socket.inet_aton(s.strip()))[0]


def port(s):
    s = s.strip()
    if not s or s == '-': return 0
    return int(s, 16) if s.lower().startswith('0x') else int(s)


def resolve(cands, benign):
    if len(cands) == 2 and benign in cands: cands = cands - {benign}
    if len(cands) == 1: return next(iter(cands))
    return None if not cands else 'AMBIG'


def finish(prefix, labs, extra):
    names = sorted({l for l in labs if l not in (None, 'AMBIG')})
    benign = [n for n in names if n in ('BENIGN', 'Normal', 'Benign')]
    names = benign + [n for n in names if n not in benign]
    idx = {n: i for i, n in enumerate(names)}
    out = np.array([UNLAB if l is None else AMBIG if l == 'AMBIG' else idx[l] for l in labs], np.uint8)
    np.save(prefix + SRC['out'] + '.npy', out)
    c = collections.Counter(out.tolist())
    js = dict(classes=names, flows=len(out), per_class={names[k]: v for k, v in c.items() if k < len(names)},
              unlabelled=c.get(UNLAB, 0), ambiguous=c.get(AMBIG, 0), **extra)
    json.dump(js, open(prefix + SRC['out'] + '.json', 'w'), indent=1)
    print(json.dumps(js))


def keyof(r):
    a = (int(r['ini_ip']), int(r['ini_port'])); b = (int(r['resp_ip']), int(r['resp_port']))
    return (min(a, b), max(a, b), int(r['proto']))


def cic(prefix, csvs, match_min=2.0):
    rows = collections.defaultdict(list)
    for path in csvs:
        with open(path, encoding='latin1') as f:
            r = csv.reader(f); h = [x.strip() for x in next(r)]
            iS, iSP, iD, iDP, iP, iT, iDur, iL = [h.index(x) for x in (
                'Source IP', 'Source Port', 'Destination IP', 'Destination Port', 'Protocol',
                'Timestamp', 'Flow Duration', 'Label')]
            for row in r:
                if len(row) < len(h) or not row[iS]: continue
                ea = (ip_u32(row[iS]), int(row[iSP])); eb = (ip_u32(row[iD]), int(row[iDP]))
                hh, mm = map(int, row[iT].split()[1].split(':')[:2])
                minute = (hh + 12 if hh < 8 else hh) * 60 + mm
                rows[(min(ea, eb), max(ea, eb), int(row[iP]))].append(
                    (minute, minute + max(0, int(float(row[iDur]))) / 60e6, row[iL].strip().replace('\x96', '-')))
    tr = np.fromfile(prefix + SRC['rec'], SRC['dt'])
    labs = []
    for r in tr:
        t = ((int(r['ts_first_us']) // 10**6) - 3 * 3600) % 86400 // 60
        rs = rows.get(keyof(r), ())
        labs.append(resolve({l for m0, m1, l in rs if m0 - match_min <= t <= m1 + match_min}, 'BENIGN'))
    finish(prefix, labs, dict(rule='cic 5-tuple minute window', match_min=match_min, csv=csvs))


def unsw(prefix, csvs, match_s=2.0):
    rows = collections.defaultdict(list)
    for path in csvs:
        with open(path, encoding='latin1', newline='') as f:
            for row in csv.reader(f):
                if len(row) < 49: continue
                p = proto_num(row[4])
                if p is None: continue
                hasport = p in (6, 17)
                try:
                    ea = (ip_u32(row[0].lstrip('\xef\xbb\xbf\ufeff')), port(row[1]) if hasport else 0)
                    eb = (ip_u32(row[2]), port(row[3]) if hasport else 0)
                    st, lt = int(row[28]), int(row[29])
                except ValueError:
                    continue
                cat = row[47].strip() or 'Normal'
                cat = {'Backdoors': 'Backdoor'}.get(cat, cat)
                rows[(min(ea, eb), max(ea, eb), p)].append((st, lt, cat))
    tr = np.fromfile(prefix + SRC['rec'], SRC['dt'])
    labs = []
    for r in tr:
        t = int(r['ts_first_us']) / 1e6
        rs = rows.get(keyof(r), ())
        labs.append(resolve({c for s, l, c in rs if s - match_s <= t <= l + match_s}, 'Normal'))
    finish(prefix, labs, dict(rule='unsw argus 5-tuple [Stime,Ltime]', match_s=match_s, csv=csvs))


def ciciot(prefix, cls, attackers=None):
    tr = np.fromfile(prefix + SRC['rec'], SRC['dt'])
    if not attackers or cls == 'Benign':
        labs = [cls] * len(tr)
    else:
        att = {ip_u32(a) for a in attackers}
        hit = np.isin(tr['ini_ip'], list(att)) | np.isin(tr['resp_ip'], list(att))
        labs = [cls if h else 'Background' for h in hit]
    finish(prefix, labs, dict(rule='ciciot capture-file label', attackers=attackers or []))


if __name__ == '__main__':
    mode, prefix = sys.argv[1], sys.argv[2]
    args = sys.argv[3:]
    if '--all-flows' in args:
        args.remove('--all-flows'); SRC.update(rec='.flows', dt=FLOW, out='.flab')
    opt = {}
    for k in ('--match-min', '--match-s', '--attackers'):
        if k in args:
            i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
    if mode == 'cic': cic(prefix, args, float(opt.get('--match-min', 2)))
    elif mode == 'unsw': unsw(prefix, args, float(opt.get('--match-s', 2)))
    elif mode == 'ciciot': ciciot(prefix, args[0], opt['--attackers'].split(',') if '--attackers' in opt else None)
    else: sys.exit('mode?')

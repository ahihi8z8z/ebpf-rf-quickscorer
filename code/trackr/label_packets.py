#!/usr/bin/env python3
"""Per-packet CIC-IDS2017 labels for a pcap, from the CICFlowMeter TrafficLabelling CSV.
    python3 label_packets.py <hara_ref .meta> <out .lab.npy> <day CSV> [<CSV> ...] [--match-min 2]
Hara's labelling code is not published (hara_reproduction.md K2); this is our re-implementation.
Rule (same as ~/ebpf/pilot/src/traffic_replay/pcap2flows.py, but per packet instead of per flow):
a packet matches the CSV rows of its direction-free 5-tuple whose [start, start+duration] minute
window, widened by --match-min, contains the packet's local minute (CSV time is UTC-3, minute
resolution, 12-hour clock without AM/PM). One label -> that label; {BENIGN, one attack} -> the
attack (CICFlowMeter emits BENIGN rows for tails of attack connections); otherwise AMBIGUOUS.
No row at all -> UNLABELED. Output: uint8 per pcap record, index into CLASSES; 254 = unlabeled,
253 = ambiguous, 255 = not an IPv4 TCP/UDP packet (hara_ref did not classify it)."""
import argparse, collections, csv, json, socket, struct
import numpy as np

META = np.dtype([('ts_us', '<u8'), ('saddr', '<u4'), ('daddr', '<u4'), ('sport', '<u2'),
                 ('dport', '<u2'), ('proto', 'u1'), ('parsed', 'u1'), ('ip_len', '<u2'), ('pad', '<u4'), ('pad2', '<u4')])
UNLAB, AMBIG, NOPKT = 254, 253, 255
TZ_S = -3 * 3600


def ip_u32(s):
    return struct.unpack('<I', socket.inet_aton(s))[0]     # same byte order as the raw memcpy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('meta'); ap.add_argument('out'); ap.add_argument('csv', nargs='+')
    ap.add_argument('--match-min', type=float, default=2)
    a = ap.parse_args()

    rows = collections.defaultdict(list)
    labels = set()
    for path in a.csv:
      with open(path, encoding='latin1') as f:
        r = csv.reader(f)
        h = [x.strip() for x in next(r)]
        iS, iSP, iD, iDP, iP, iT, iDur, iL = [h.index(x) for x in (
            'Source IP', 'Source Port', 'Destination IP', 'Destination Port', 'Protocol',
            'Timestamp', 'Flow Duration', 'Label')]
        for row in r:
            if len(row) < len(h) or not row[iS]:
                continue
            ea = (ip_u32(row[iS]), int(row[iSP])); eb = (ip_u32(row[iD]), int(row[iDP]))
            hh, mm = map(int, row[iT].split()[1].split(':')[:2])
            minute = (hh + 12 if hh < 8 else hh) * 60 + mm
            dur_min = max(0, int(float(row[iDur]))) / 60e6
            lab = row[iL].strip().replace('\x96', '-')
            labels.add(lab)
            rows[(min(ea, eb), max(ea, eb), int(row[iP]))].append((minute, minute + dur_min, lab))
    classes = sorted(labels, key=lambda x: (x != 'BENIGN', x))
    cid = {c: i for i, c in enumerate(classes)}

    m = np.fromfile(a.meta, META)
    out = np.full(len(m), NOPKT, np.uint8)
    ok = np.flatnonzero(m['parsed'] == 1)
    mm = m[ok]
    a_ = (mm['saddr'].astype(np.uint64) << 16) | mm['sport']
    b_ = (mm['daddr'].astype(np.uint64) << 16) | mm['dport']
    lo, hi = np.minimum(a_, b_), np.maximum(a_, b_)
    minute = ((mm['ts_us'] // 1_000_000).astype(np.int64) + TZ_S) % 86400 // 60
    key = np.zeros(len(mm), [('lo', '<u8'), ('hi', '<u8'), ('p', 'u1'), ('t', '<i8')])
    key['lo'], key['hi'], key['p'], key['t'] = lo, hi, mm['proto'], minute
    uk, inv = np.unique(key, return_inverse=True)
    ulab = np.empty(len(uk), np.uint8)
    for i, (l, hh, p, t) in enumerate(uk.tolist()):
        k = ((l >> 16, l & 0xffff), (hh >> 16, hh & 0xffff), p)
        rs = rows.get(k)
        if not rs:
            ulab[i] = UNLAB; continue
        ls = {x for m0, m1, x in rs if m0 - a.match_min <= t <= m1 + a.match_min}
        if len(ls) == 2 and 'BENIGN' in ls:
            ls.discard('BENIGN')
        ulab[i] = cid[ls.pop()] if len(ls) == 1 else (UNLAB if not ls else AMBIG)
    out[ok] = ulab[inv.ravel()]
    np.save(a.out, out)
    cnt = collections.Counter(out.tolist())
    summary = dict(meta=a.meta, csv=a.csv, match_min=a.match_min, classes=classes, records=len(m),
                   per_class={classes[c]: n for c, n in cnt.items() if c < len(classes)},
                   unlabeled=cnt.get(UNLAB, 0), ambiguous=cnt.get(AMBIG, 0),
                   not_ipv4_tcp_udp=cnt.get(NOPKT, 0))
    json.dump(summary, open(a.out.replace('.npy', '') + '.json', 'w'), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()

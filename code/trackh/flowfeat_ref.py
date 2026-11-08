#!/usr/bin/env python3
"""Independent pure-Python reference of the Track-H schema v1 (dataset_protocol.md), written from
the specification, not from flowfeat.c. Classic pcap (Ethernet) only; used to cross-check
flowfeat on a capture prefix.
    python3 -I flowfeat_ref.py <in.pcap> <max_packets> <flowfeat .trig> [N] [timeout_s]
Prints the number of triggered flows compared and any mismatching feature vectors."""
import struct, sys
import numpy as np

TRIG = np.dtype([('ts_first_us', '<u8'), ('ts_trig_us', '<u8'), ('ini_ip', '<u4'), ('resp_ip', '<u4'),
                 ('ini_port', '<u2'), ('resp_port', '<u2'), ('proto', 'u1'), ('pad', 'u1', 3),
                 ('flow_id', '<u4'), ('f', '<i4', 17), ('pad2', '<u4', 2)])

def packets(path, maxn):
    with open(path, 'rb') as fh:
        g = fh.read(24); magic, = struct.unpack('<I', g[:4])
        mul = 1000 if magic == 0xa1b2c3d4 else 1
        assert struct.unpack('<I', g[20:24])[0] == 1
        last = 0
        for _ in range(maxn):
            h = fh.read(16)
            if len(h) < 16: return
            s, sub, cl, _ = struct.unpack('<IIII', h); d = fh.read(cl)
            ts = (s * 10**9 + sub * mul) // 1000
            last = max(last, ts)
            et = d[12] << 8 | d[13]; o = 14
            while et in (0x8100, 0x88a8): et = d[o + 2] << 8 | d[o + 3]; o += 4
            if et != 0x0800 or (d[o] >> 4) != 4: continue
            ihl = (d[o] & 15) * 4; ln = d[o + 2] << 8 | d[o + 3]; pr = d[o + 9]
            src, dst = struct.unpack('<II', d[o + 12:o + 20])
            frag = (d[o + 6] << 8 | d[o + 7]) & 0x1fff
            sp = dp = fl = 0
            if not frag and pr in (6, 17) and len(d) >= o + ihl + 4:
                sp, dp = struct.unpack('>HH', d[o + ihl:o + ihl + 4])
                if pr == 6 and len(d) >= o + ihl + 14: fl = d[o + ihl + 13]
            yield last, src, dst, sp, dp, pr, ln, fl

def main():
    path, maxn, trig = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    N = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    TO = (int(sys.argv[5]) if len(sys.argv) > 5 else 120) * 10**6
    flows, out = {}, []
    for t, src, dst, sp, dp, pr, ln, fl in packets(path, maxn):
        k = (min((src, sp), (dst, dp)), max((src, sp), (dst, dp)), pr)
        st = flows.get(k)
        if st is None or t - st['last'] > TO:
            st = flows[k] = dict(first=t, last=t, ini=(src, sp), resp=dp, pk=[])
        st['pk'].append((t, 0 if (src, sp) == st['ini'] else 1, ln, fl))
        if (src, sp) == (dst, dp): st['pk'][-1] = (t, 0, ln, fl)
        st['last'] = t
        if len(st['pk']) == N:
            p = st['pk']; ts = [x[0] for x in p]; dr = [x[1] for x in p]; ls = [x[2] for x in p]
            iat = [b - a for a, b in zip(ts, ts[1:])] or [0]
            f = [pr, st['resp'], dr.count(0), sum(l for l, d_ in zip(ls, dr) if d_ == 0),
                 sum(l for l, d_ in zip(ls, dr) if d_ == 1), ls[0], min(ls), max(ls), min(ts[-1] - ts[0], 2**31 - 1),
                 min(min(iat), 2**31 - 1), min(max(iat), 2**31 - 1)]
            f += [sum(1 for x in p if x[3] & m) for m in (2, 1, 4, 8, 16)]
            f += [sum(1 for a, b in zip(dr, dr[1:]) if a != b)]
            out.append((st['first'], st['ini'], k, f))
            st['pk'] = p + [None]          # stop collecting
        elif len(st['pk']) > N:
            st['pk'].pop()
    ref = np.fromfile(trig, TRIG)
    # key: first-packet time + initiator + the direction-free 5-tuple (several flows of one initiator can
    # start in the same microsecond, e.g. one NTP client polling three servers)
    def kk(a, pa, b, pb, pr): return (min((a, pa), (b, pb)), max((a, pa), (b, pb)), pr)
    got = {(int(r['ts_first_us']), int(r['ini_ip']), int(r['ini_port']),
            kk(int(r['ini_ip']), int(r['ini_port']), int(r['resp_ip']), int(r['resp_port']), int(r['proto']))): r['f'].tolist() for r in ref}
    bad = 0
    for first, ini, k, f in out:
        g = got.get((first, ini[0], ini[1], k))
        if g != f:
            bad += 1
            if bad <= 5: print('MISMATCH', first, ini, f, g)
    print(f'compared {len(out)} triggered flows, mismatches {bad}')

if __name__ == '__main__':
    main()

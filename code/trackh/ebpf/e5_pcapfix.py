#!/usr/bin/env python3
"""Make a replayable Ethernet pcap for E5 WITHOUT tcprewrite (tcprewrite 4.4.4 silently rewrote the IP
total length of padded 60-byte frames, 40 -> 46, which changed the replayed features).
Every byte after the link header is kept exactly. Per record:
  - Ethernet (DLT 1): destination/source MAC replaced
  - Linux cooked (DLT 113, UNSW-NB15): 16-byte SLL header replaced by a 14-byte Ethernet header with the
    SLL protocol field
  - frames longer than 1514 bytes (segmentation-offload artifacts of the capture; cannot cross the
    1500-byte-MTU data link) are DROPPED and counted
    python -I e5_pcapfix.py <in.pcap> <out.pcap> <dst mac> <src mac>  -> prints JSON stats"""
import json, struct, sys

MAXF = 1514


def main():
    src, dst, dmac, smac = sys.argv[1:5]
    mac = bytes.fromhex(dmac.replace(':', '')) + bytes.fromhex(smac.replace(':', ''))
    fi, fo = open(src, 'rb'), open(dst, 'wb')
    gh = fi.read(24)
    magic = struct.unpack('<I', gh[:4])[0]
    if magic not in (0xa1b2c3d4, 0xa1b23c4d): raise SystemExit(f'unsupported pcap magic {magic:#x}')
    lt = struct.unpack('<I', gh[20:24])[0]
    if lt not in (1, 113): raise SystemExit(f'unsupported linktype {lt}')
    fo.write(gh[:16] + struct.pack('<II', 65535, 1))     # snaplen, DLT_EN10MB
    st = dict(linktype_in=lt, n_in=0, n_out=0, dropped_oversize=0, dropped_short=0, bytes_out=0)
    while True:
        h = fi.read(16)
        if len(h) < 16: break
        ts, us, cl, ol = struct.unpack('<IIII', h); d = fi.read(cl); st['n_in'] += 1
        if lt == 1:
            if cl < 14: st['dropped_short'] += 1; continue
            frame, olen = mac + d[12:], ol
        else:
            if cl < 16: st['dropped_short'] += 1; continue
            frame, olen = mac + d[14:16] + d[16:], ol - 2
        if olen > MAXF or len(frame) > MAXF: st['dropped_oversize'] += 1; continue
        fo.write(struct.pack('<IIII', ts, us, len(frame), olen)); fo.write(frame)
        st['n_out'] += 1; st['bytes_out'] += len(frame)
    st['oversize_share'] = round(st['dropped_oversize'] / max(1, st['n_in']), 5)
    print(json.dumps(st))


if __name__ == '__main__':
    main()

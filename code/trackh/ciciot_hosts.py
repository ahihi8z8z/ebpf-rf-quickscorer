#!/usr/bin/env python3
"""Per CICIoT2023 capture: top flow initiators / responders (by flows and packets), to identify the
attacker addresses (not published by the dataset). python -I ciciot_hosts.py out/ciciot/*.flows"""
import socket, struct, sys, collections
import numpy as np
FLOW = np.dtype([('ts_first_us', '<u8'), ('ts_last_us', '<u8'), ('ini_ip', '<u4'), ('resp_ip', '<u4'),
                 ('ini_port', '<u2'), ('resp_port', '<u2'), ('proto', 'u1'), ('triggered', 'u1'), ('pad', '<u2'),
                 ('npkts', '<u4'), ('flow_id', '<u4')])
ip = lambda v: socket.inet_ntoa(struct.pack('<I', int(v)))
for p in sys.argv[1:]:
    f = np.fromfile(p, FLOW)
    if not len(f): continue
    print(f'== {p.split("/")[-1]}  flows={len(f)} pkts={int(f["npkts"].sum())} trig={int(f["triggered"].sum())}')
    for col in ('ini_ip', 'resp_ip'):
        u, inv = np.unique(f[col], return_inverse=True)
        pk = np.bincount(inv, weights=f['npkts']); fl = np.bincount(inv)
        o = np.argsort(-pk)[:6]
        print(f'  top {col}: ' + '; '.join(f'{ip(u[i])} {pk[i] / pk.sum():.2f}pk {fl[i]}fl' for i in o))

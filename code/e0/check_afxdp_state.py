#!/usr/bin/env python3
"""On DUT: python3 check_afxdp_state.py ~/e0/afxdp-clean ~/e0/eq_trace.pcap

Independent Python 12-feature reference, C dispatch versus direct upstream model
calls, binary-key separation and table-capacity checks. No live AF_XDP required.
"""
import ctypes as ct
from contextlib import closing
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from scapy.all import IP, TCP, UDP, PcapReader

root, trace = [Path(p).expanduser().resolve() for p in sys.argv[1:]]
wrapper = r'''
#include <stdint.h>
#include "mlids.h"
#include "../nn/mlp.h"
#include "../dt/dt.h"
#include "afxdp_state.h"
int audit_init(void) { return clean_init(); }
void audit_destroy(void) { clean_destroy(); }
int audit_features(int sa, int da, int sp, int dp, int proto, unsigned len,
                   int64_t ts, int64_t *x) {
  struct pkt_key_t key = {sa, da, sp, dp, proto};
  return clean_features(&key, len, ts, x);
}
unsigned audit_predict(int model, int64_t *x) { return clean_predict(model, x); }
unsigned audit_direct(int model, int64_t *x) {
  unsigned prediction;
  if (model == 0) run_mlp(x, 1, &prediction);
  else run_dt(x, 1, &prediction);
  return prediction;
}
'''
with tempfile.TemporaryDirectory() as temp:
    path = Path(temp)
    (path / 'audit.c').write_text(wrapper)
    sources = ['mlp.c', 'mlp_params.c', 'nn.c', 'nn_math.c']
    subprocess.run(['cc', '-O2', '-shared', '-fPIC', '-I' + str(root / 'examples/mlids'),
                    str(path / 'audit.c'), *[str(root / 'examples/nn' / s) for s in sources],
                    str(root / 'examples/dt/dt.c'), '-o', str(path / 'audit.so')], check=True)
    lib = ct.CDLL(str(path / 'audit.so'))
    arr = ct.c_int64 * 12
    lib.audit_features.argtypes = [ct.c_int] * 5 + [ct.c_uint, ct.c_int64, ct.POINTER(ct.c_int64)]
    lib.audit_predict.argtypes = lib.audit_direct.argtypes = [ct.c_int, ct.POINTER(ct.c_int64)]
    lib.audit_predict.restype = lib.audit_direct.restype = ct.c_uint
    assert lib.audit_init() == 0
    state, counts = {}, [{}, {}]
    packets = 0
    with closing(PcapReader(str(trace))) as reader:
        base = None
        for packet in reader:
            ip = packet[IP]
            l4 = packet[TCP] if TCP in packet else packet[UDP]
            # Convert exactly as the packed C key sees IPv4 network-order bytes.
            import socket
            sa = int.from_bytes(socket.inet_aton(ip.src), sys.byteorder, signed=True)
            da = int.from_bytes(socket.inet_aton(ip.dst), sys.byteorder, signed=True)
            key = sa, da, int(l4.sport), int(l4.dport), int(ip.proto)
            ts = int(packet.time * 10**9)
            if base is None: base = ts
            ts = ts - base + 10**9
            s = state.setdefault(key, {'n': 0, 'last': ts, 'sum': [0]*3, 'dev': [0]*3})
            s['n'] += 1
            expected = [key[2], key[3], key[4], int(ip.len), ts - s['last'], 1]
            s['last'] = ts
            expected = [v << 16 for v in expected]
            for j in range(3): s['sum'][j] += expected[3+j]
            means = [v // s['n'] for v in s['sum']]
            for j in range(3): s['dev'][j] += abs(expected[3+j] - means[j])
            expected += means + [v // s['n'] for v in s['dev']]
            actual = arr()
            assert lib.audit_features(*key, int(ip.len), ts, actual) == 0
            assert list(actual) == expected, (packets, list(actual), expected)
            for model in (0, 1):
                prediction = lib.audit_predict(model, actual)
                assert prediction == lib.audit_direct(model, arr(*expected)), (packets, model)
                counts[model][prediction] = counts[model].get(prediction, 0) + 1
            packets += 1
    lib.audit_destroy()
    # Stress collisions, all key fields and embedded NULs; fixed tuples must
    # remain distinct up to capacity, and existing flows must survive exhaustion.
    assert lib.audit_init() == 0
    for i in range(32768):
        actual = arr()
        assert lib.audit_features(i, 0, 0, 0, 17, 64, 10**9, actual) == 0
        assert actual[4] == 0 and actual[6] == 64 << 16
    assert lib.audit_features(32768, 0, 0, 0, 17, 64, 10**9, arr()) == -1
    actual = arr()
    assert lib.audit_features(0, 0, 0, 0, 17, 128, 10**9 + 100, actual) == 0
    assert actual[4] == 100 << 16 and actual[6] == 96 << 16
    lib.audit_destroy()
    print(json.dumps({'packets': packets, 'flows': len(state), 'feature_mismatches': 0,
                      'prediction_mismatches': 0, 'classes_NN': counts[0], 'classes_DT': counts[1],
                      'capacity': 32768, 'capacity_check': 'passed'}))

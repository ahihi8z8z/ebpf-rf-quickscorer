#!/usr/bin/env python3
"""Summarize run_smoke.sh logs -> CSV + markdown table (median [min-max] over reps).
usage: summarize.py tput_1q.log [out.csv]"""
import csv, re, statistics as st, sys
from collections import defaultdict

rows = defaultdict(lambda: defaultdict(list))
for line in open(sys.argv[1]):
    if 'variant=' not in line:
        continue
    g = lambda pat: (re.search(pat, line) or [None, None])[1]
    key = (g(r'model=(\S+)'), g(r'variant=(\S+)'))
    r = rows[key]
    r['attach'].append(g(r'attach=(\S+)'))
    r['offered_pps'].append(int(g(r'TOTAL tx pps=(\d+)') or 0))
    r['dut_rx_pps'].append(int(g(r'dut_rx_pps=(\d+)')))
    r['sink_pps'].append(int(g(r'sink_pps=(\d+)')))
    inf = [int(x) for x in (g(r'inf_per_s\(top3\)=\[([^\]]*)\]') or '').split()]
    r['inf_per_s'].append(st.median(inf) if inf else None)
    m = re.search(r'prog=\[(\S+?):([\d.]+)ns/run,cnt=\d+,xl=(\d+),jit=(\d+)', line)
    r['ns_per_pkt'].append(float(m[2]) if m else None)
    r['xlated'].append(int(m[3]) if m else None)
    r['jited'].append(int(m[4]) if m else None)
    r['trace'].append(int(g(r'trace=(\d+)') or 0))

def agg(v, fmt='{:.0f}'):
    v = [x for x in v if x is not None]
    if not v:
        return '-'
    return f"{fmt.format(st.median(v))} [{fmt.format(min(v))}-{fmt.format(max(v))}]" if len(v) > 1 else fmt.format(v[0])

order = {'xdpdrop': 0, 'filter': 1, 'dt': 2, 'nn': 3}
vorder = {'faithful': 0, 'hist': 1, 'clean_pass': 2, 'clean_drop': 3}
keys = sorted(rows, key=lambda k: (order.get(k[0], 9), vorder.get(k[1], 9)))
cols = ['model', 'variant', 'n', 'attach', 'inf_per_s', 'ns_per_pkt', 'sink_pps', 'dut_rx_pps', 'offered_pps', 'xlated', 'jited', 'trace']
out = [cols]
for k in keys:
    r = rows[k]
    out.append([k[0], k[1], len(r['attach']), r['attach'][0], agg(r['inf_per_s']), agg(r['ns_per_pkt'], '{:.1f}'),
                agg(r['sink_pps']), agg(r['dut_rx_pps']), agg(r['offered_pps']), agg(r['xlated']), agg(r['jited']),
                agg(r['trace'])])
if len(sys.argv) > 2:
    csv.writer(open(sys.argv[2], 'w', newline='')).writerows(out)
print('| ' + ' | '.join(out[0]) + ' |\n|' + '---|' * len(out[0]))
for row in out[1:]:
    print('| ' + ' | '.join(map(str, row)) + ' |')

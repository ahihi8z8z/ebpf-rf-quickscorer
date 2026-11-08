#!/usr/bin/env python3
"""Per-packet class log for E0 equivalence checks (run on qs-dut):
    python3 add_seqlog.py ~/e0/variants <variant> [<variant> ...]
For each variant V creates V_seq/: same program + BPF_ARRAY cls_seq[SEQ_MAX] of u8 class indexed by
packet arrival order; dumped to <resdir>/cls_seq.bin at exit. Inserted right after cls_hist.increment,
so the logged value is exactly what the histogram counted.
Counter is NOT atomic: valid only with ONE RX queue (all packets on one CPU, softirq, no preemption)."""
import os, shutil, sys

BASE = os.path.expanduser(sys.argv[1])
SEQ_MAX = 32768
DECL = f'BPF_ARRAY(cls_seq, u8, {SEQ_MAX});\nBPF_ARRAY(seq_ctr, u64, 1);\n'
LOG = ('{{ int _sz = 0; u64 *_sc = seq_ctr.lookup(&_sz); if (_sc) {{ u32 _si = (u32)*_sc; *_sc = _si + 1; '
       'if (_si < %d) {{ u8 _sv = (u8)({cls}); cls_seq.update(&_si, &_sv); }} }} }}\n' % SEQ_MAX)
DUMP = '''    finally:
        try:
            _n = min(b.get_table("seq_ctr")[ct.c_int(0)].value, %d)
            _s = b.get_table("cls_seq")
            with open(f"{resdir}/cls_seq.bin", "wb") as _sf:
                _sf.write(bytes(_s[ct.c_int(_i)].value for _i in range(_n)))
        except Exception as _e:
            print("cls_seq dump failed:", _e)
''' % SEQ_MAX
HOOKS = {
    ('nn-filter', 'nn_filter_xdp.py'): ('  cls_hist.increment(argmax_over_cols);\n', '  ', 'argmax_over_cols'),
    ('dt-filter', 'dt_filter_xdp.py'): ('          cls_hist.increment((u32)(*current_value));\n', '          ',
                                        '*current_value'),
}

def sub(s, old, new):
    assert s.count(old) == 1, f'expected 1 match: {old[:60]!r}'
    return s.replace(old, new)

for v in sys.argv[2:]:
    for (d, f), (hook, ind, cls) in HOOKS.items():
        src = os.path.join(BASE, v, d)
        if not os.path.isdir(src):
            continue
        out = os.path.join(BASE, v + '_seq', d)
        if os.path.exists(out):
            shutil.rmtree(out)
        shutil.copytree(src, out)
        t = open(os.path.join(src, f)).read()
        t = sub(t, 'BPF_PERCPU_ARRAY(cls_hist, u64, 8);\n', 'BPF_PERCPU_ARRAY(cls_hist, u64, 8);\n' + DECL)
        t = sub(t, hook, hook + ind + LOG.format(cls=cls))
        t = sub(t, '    finally:\n', DUMP)
        if 'import ctypes as ct' not in t:
            t = t.replace('import sys\n', 'import sys\nimport ctypes as ct\n', 1)
        open(os.path.join(out, f), 'w').write(t)
        print(v + '_seq', d)

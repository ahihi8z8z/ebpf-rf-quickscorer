#!/usr/bin/env python3
"""Generate E0 variants of Hara's in-kernel programs from the pinned faithful sources.

Run on qs-dut:  python3 make_variants.py ~/ebpf-classifier ~/e0/variants
Every patch hunk must match exactly once (asserted), so a variant never silently diverges.

Variants (inference arithmetic is never touched; bugs Q2/Q3 are kept on purpose):
  hist        faithful + per-CPU class histogram `cls_hist` (observability only)
  clean_pass  hist + B4 debug removal (NN printk, DT DEBUG_BUILD maps) + B1 mode-flag fix;
              post-inference action unchanged (XDP_PASS)
  clean_drop  clean_pass with FINAL_ACTION=XDP_DROP after inference for every model
"""
import os, shutil, sys

SRC, DST = map(os.path.expanduser, sys.argv[1:3])

def sub(s, old, new, name):
    n = s.count(old)
    assert n == 1, f"[{name}] expected 1 match, got {n}: {old[:60]!r}"
    return s.replace(old, new)

HIST_PY = '''    finally:
        try:
            _h = b.get_table("cls_hist")
            with open(f"{resdir}/cls_hist.txt", "w") as _hf:
                for _k in range(8):
                    _hf.write(f"{_k} {_h.sum(_k).value}\\n")
        except Exception as _e:
            print("cls_hist dump failed:", _e)
'''
HIST_MAP = 'BPF_PERCPU_ARRAY(cls_hist, u64, 8);\n'

def patch(model, text, variant):
    clean = variant.startswith('clean')
    action = 'XDP_DROP' if variant == 'clean_drop' else 'XDP_PASS'
    t = text
    # --- observability: class histogram (all variants) ---
    if model == 'nn':
        t = sub(t, 'BPF_HASH(dropcnt, int, u32);\n', 'BPF_HASH(dropcnt, int, u32);\n' + HIST_MAP, model)
        t = sub(t, '  bpf_trace_printk("argmax_over_cols=%d", argmax_over_cols);\n',
                '  cls_hist.increment(argmax_over_cols);\n' +
                ('' if clean else '  bpf_trace_printk("argmax_over_cols=%d", argmax_over_cols);\n'), model)
    elif model == 'dt':
        t = sub(t, 'BPF_HASH(dropcnt, int, u32);\n', 'BPF_HASH(dropcnt, int, u32);\n' + HIST_MAP, model)
        t = sub(t, '          bool is_anomaly = (bool)(*current_value);\n',
                '          bool is_anomaly = (bool)(*current_value);\n'
                '          cls_hist.increment((u32)(*current_value));\n', model)
    elif model == 'filter':
        t = sub(t, 'BPF_HASH(dropcnt, int, u32);\n', 'BPF_HASH(dropcnt, int, u32);\n' + HIST_MAP, model)
        t = sub(t, '      *vp += 1;\n      return XDP_PASS;\n',
                '      *vp += 1;\n      cls_hist.increment(0);\n      return XDP_PASS;\n', model)
    t = sub(t, '    finally:\n', HIST_PY, model)
    if not clean:
        return t
    # --- clean: remove debug work (B4), fix mode flag (B1), common final action ---
    if model == 'nn':
        t = sub(t, '  // return XDP_DROP;\n  return XDP_PASS;\n}\nint nn_xdp_drop_packet',
                '  // return XDP_DROP;\n  return FINAL_ACTION;\n}\nint nn_xdp_drop_packet', model)
        t = sub(t, 'cflags=["-w"]', f'cflags=["-w", "-DFINAL_ACTION={action}"]', model)
    elif model == 'dt':
        t = sub(t, '#define DEBUG_BUILD\n', '', model)
        t = sub(t, '          tmp.update(eth, &current_node);\n          tmp2.update(eth, &is_anomaly);\n'
                   '          tmp3.update(eth, current_value);\n', '', model)
        t = sub(t, '''          if (is_anomaly) {
            #ifdef DEBUG_BUILD
            return XDP_PASS;
            #else
            return XDP_DROP;
            #endif
          }
          return XDP_PASS;''', '          return FINAL_ACTION;', model)
        t = sub(t, '    if len(sys.argv) == 3:\n', '    if len(sys.argv) == 4:\n', model)
        t = sub(t, '    b = BPF(text=bpf_text)\n', f'    b = BPF(text=bpf_text, cflags=["-DFINAL_ACTION={action}"])\n', model)
    elif model == 'filter':
        t = sub(t, '      cls_hist.increment(0);\n      return XDP_PASS;\n',
                '      cls_hist.increment(0);\n      return FINAL_ACTION;\n', model)
        t = sub(t, '    if len(sys.argv) == 3:\n', '    if len(sys.argv) == 4:\n', model)
        t = sub(t, '    b = BPF(text=bpf_text)\n', f'    b = BPF(text=bpf_text, cflags=["-DFINAL_ACTION={action}"])\n', model)
    return t

FILES = {'nn': ('nn-filter', 'nn_filter_xdp.py'), 'dt': ('dt-filter', 'dt_filter_xdp.py'),
         'filter': ('filter', 'filter_xdp.py')}
for variant in ('hist', 'clean_pass', 'clean_drop'):
    for model, (d, f) in FILES.items():
        out = os.path.join(DST, variant, d)
        if os.path.exists(out):
            shutil.rmtree(out)
        shutil.copytree(os.path.join(SRC, d), out)        # keeps mlp_params.json / runs/ next to the script
        src = open(os.path.join(SRC, d, f)).read()
        open(os.path.join(out, f), 'w').write(patch(model, src, variant))
        print(f'{variant:10s} {model:6s} -> {out}/{f}')

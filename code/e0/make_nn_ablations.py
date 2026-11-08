#!/usr/bin/env python3
"""NN cost-attribution ablations, derived from the clean_drop NN variant (run on qs-dut):
    python3 make_nn_ablations.py ~/e0/variants
Creates ~/e0/variants/{abl_w,abl_io,abl_w_io}/nn-filter/. Arithmetic, feature extraction, layer
order, tail-call structure and final action are unchanged; only *where values are fetched/stored*:
  abl_w   weights of each layer packed in ONE map value (struct of int8[]), 1 lookup per layer per
          packet instead of 1 inlined array lookup per MAC (faithful stores int per element and reads
          the low byte as int8 -> identical values for weights in [-127,127], asserted by the loader).
  abl_io  hidden activations handed between tail-call stages in ONE per-CPU struct (1 lookup per
          stage) instead of 16 bpf_map_update_elem() + 16 percpu lookups per stage.
  abl_w_io both.
These are attribution experiments (and candidate optimizations), NOT Hara's design."""
import os, shutil, sys

BASE = os.path.expanduser(sys.argv[1])
SRC = os.path.join(BASE, 'clean_drop', 'nn-filter')

def sub(s, old, new):
    n = s.count(old)
    assert n == 1, f"expected 1 match, got {n}: {old[:70]!r}"
    return s.replace(old, new)

def patch(t, w, io):
    decl, pre1, pre2, pre3 = '', '', '', ''
    if w:
        decl += ''.join(f'struct w{n}_t {{ unsigned char w[LAYER_{n}_WEIGHT]; }};\nBPF_ARRAY(layer_{n}_wv, struct w{n}_t, 1);\n'
                        for n in (1, 2, 3))
        pre1 += 'struct w1_t *W1 = layer_1_wv.lookup(&_zero); if (!W1) return XDP_PASS;\n      '
        pre2 += 'struct w2_t *W2 = layer_2_wv.lookup(&_zero); if (!W2) return XDP_PASS;\n  '
        pre3 += 'struct w3_t *W3 = layer_3_wv.lookup(&_zero); if (!W3) return XDP_PASS;\n  '
        t = sub(t, 'weight = *(int8_t*)layer_1_weight.lookup_or_init(&_k, &_zero);', 'weight = (int8_t)W1->w[_k];')
        t = sub(t, 'weight = *(int8_t*)layer_2_weight.lookup_or_init(&_k, &_zero);', 'weight = (int8_t)W2->w[_k];')
        t = sub(t, 'weight = *(int8_t*)layer_3_weight.lookup_or_init(&_k, &_zero);', 'weight = (int8_t)W3->w[_k];')
        t = sub(t, "        map_bpf_table(layer_3_weight,  params['layer_3_weight'],  'int')\n",
                "        map_bpf_table(layer_3_weight,  params['layer_3_weight'],  'int')\n"
                "        for _n in (1, 2, 3):\n"
                "            _src = params[f'layer_{_n}_weight']\n"
                "            assert all(-128 <= _x <= 127 for _x in _src)\n"
                "            _t = b.get_table(f'layer_{_n}_wv'); _v = _t.Leaf()\n"
                "            for _i, _x in enumerate(_src):\n"
                "                _v.w[_i] = _x & 0xff\n"
                "            _t[ct.c_int(0)] = _v\n")
    if io:
        decl += ('struct act_t { int64_t v[16]; };\n'
                 'BPF_PERCPU_ARRAY(act1, struct act_t, 1);\nBPF_PERCPU_ARRAY(act2, struct act_t, 1);\n')
        pre1 += 'struct act_t *A1 = act1.lookup(&_zero); if (!A1) return XDP_PASS;\n      '
        pre2 += ('struct act_t *A1 = act1.lookup(&_zero); if (!A1) return XDP_PASS;\n  '
                 'struct act_t *A2 = act2.lookup(&_zero); if (!A2) return XDP_PASS;\n  ')
        pre3 += 'struct act_t *A2 = act2.lookup(&_zero); if (!A2) return XDP_PASS;\n  '
        t = sub(t, 'out_input.update(&_m, &out);', 'A1->v[_m & 15] = out;')
        t = sub(t, 'out = *out_input.lookup_or_init(&_m, &_zero64);', 'out = A1->v[_m & 15];')
        t = sub(t, 'out_input2.update(&_m, &out);', 'A2->v[_m & 15] = out;')
        t = sub(t, 'out = *out_input2.lookup_or_init(&_m, &_zero64);', 'out = A2->v[_m & 15];')
    t = sub(t, 'BPF_PERCPU_ARRAY(out_input2, int64_t, 16);\n', decl + 'BPF_PERCPU_ARRAY(out_input2, int64_t, 16);\n')
    t = sub(t, '      s_x = *((int*)layer_1_s_x.lookup_or_init(&_zero, &_zero));',
            '      ' + pre1 + 's_x = *((int*)layer_1_s_x.lookup_or_init(&_zero, &_zero));')
    t = sub(t, '  s_x = *((int*)layer_2_s_x.lookup_or_init(&_zero, &_zero));',
            '  ' + pre2 + 's_x = *((int*)layer_2_s_x.lookup_or_init(&_zero, &_zero));')
    t = sub(t, '  s_x = *((int*)layer_3_s_x.lookup_or_init(&_zero, &_zero));',
            '  ' + pre3 + 's_x = *((int*)layer_3_s_x.lookup_or_init(&_zero, &_zero));')
    return t

src = open(os.path.join(SRC, 'nn_filter_xdp.py')).read()
for name, w, io in (('abl_w', 1, 0), ('abl_io', 0, 1), ('abl_w_io', 1, 1)):
    out = os.path.join(BASE, name, 'nn-filter')
    if os.path.exists(out):
        shutil.rmtree(out)
    shutil.copytree(SRC, out)
    open(os.path.join(out, 'nn_filter_xdp.py'), 'w').write(patch(src, w, io))
    print(name, '->', out)

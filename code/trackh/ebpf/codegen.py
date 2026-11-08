#!/usr/bin/env python3
"""Generate RF inference code for E1 (C profiling), E2-E4 (eBPF) from one exported quantized RF
(train_e1.py models/*.npz). Every runtime implements the SAME integer semantics (the common
quantized reference, train_e1.forest_scores_q): go left iff x[f] <= thr (int32), add the reached
leaf's uint8 class scores into uint32 accumulators, predict argmax with lowest-index tie-break.

    codegen.py <model.npz> <outdir> [--grf-k K ...] [--qs-g G ...]

Writes into <outdir>:
  model.h            constants + tables (tree walk: per-node arrays; QuickScorer: per-feature
                     ascending thresholds with tree id and leaf mask; leaf score table)
  grf_k<K>.bpf.c     G-RF: Galvao-style trees as nested if/else with immediate thresholds,
                     K trees per XDP program, programs chained with bpf_tail_call (stage 0 = entry)
  qs_g<G>.bpf.c      QuickScorer, trees split into G equal-tree stages chained with tail calls;
                     G = 1 is QS-1 (single program). Bounded loops over the model tables.
  qsl_g<G>.bpf.c     same, but the per-feature threshold scan and per-tree exit-leaf loops run
                     inside bpf_loop() callbacks (data-driven, verified once per callback).
The eBPF programs read the 17 int32 features from a UDP payload (isolated-inference harness) and
write the predicted class into payload byte 68."""
import os, sys
import numpy as np

HDR = r'''// SPDX-License-Identifier: GPL-2.0
#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/udp.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>
#include "model.h"

/* isolated-inference harness: Eth + IPv4(20) + UDP + 17 x int32 features + 4 bytes result */
#define PAY_OFF (sizeof(struct ethhdr) + 20 + sizeof(struct udphdr))

#ifndef VM
#define VM 0
#endif
struct scratch { __s32 x[32]; __u32 s[NC]; __u64 v[VM + 1]; };
struct { __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY); __uint(max_entries, 1); __type(key, __u32);
         __type(value, struct scratch); } scr SEC(".maps");
struct { __uint(type, BPF_MAP_TYPE_PROG_ARRAY); __uint(max_entries, 64); __type(key, __u32);
         __type(value, __u32); } jmp SEC(".maps");

static __always_inline struct scratch *get_scr(void) { __u32 z = 0; return bpf_map_lookup_elem(&scr, &z); }

#ifdef FRONTEND
#include "frontend.h"
#define JB 1
#else
#define JB 0
#endif

static __always_inline int finish(struct xdp_md *ctx, struct scratch *S) {
    __u32 best = 0, bs = S->s[0];
#pragma unroll
    for (int c = 1; c < NC; c++) if (S->s[c] > bs) { bs = S->s[c]; best = c; }
#ifdef FRONTEND
    return fe_finish(ctx, best);
#else
    void *data = (void *)(long)ctx->data, *end = (void *)(long)ctx->data_end;
    __u8 *out = data + PAY_OFF + NF * 4;
    if ((void *)(out + 1) > end) return XDP_ABORTED;
    *out = best;
    return XDP_DROP;
#endif
}

static __always_inline struct scratch *entry(struct xdp_md *ctx) {
#ifdef FRONTEND
    struct scratch *S = get_scr();          /* features already placed by fe_main */
    if (!S) return 0;
#else
    void *data = (void *)(long)ctx->data, *end = (void *)(long)ctx->data_end;
    __s32 *f = data + PAY_OFF;
    if ((void *)(f + NF) + 1 > end) return 0;
    struct scratch *S = get_scr();
    if (!S) return 0;
#pragma unroll
    for (int i = 0; i < NF; i++) S->x[i] = f[i];
#endif
#pragma unroll
    for (int c = 0; c < NC; c++) S->s[c] = 0;
    return S;
}
'''


def load(npz):
    m = np.load(npz)
    off = m['offsets']
    trees = []
    for t in range(len(off) - 1):
        a, b = off[t], off[t + 1]
        trees.append(dict(left=m['left'][a:b], right=m['right'][a:b], feat=m['feat'][a:b],
                          thr=m['thr'][a:b], leafq=m['leafq'][a:b]))
    return trees, len(m['names'])


def leaves_inorder(t):
    """Leaf node ids left to right, and for every inner node the in-order leaf range of its left subtree."""
    order, rng = [], {}
    def rec(n):
        if t['feat'][n] < 0:
            order.append(n); return len(order) - 1, len(order) - 1
        lo, mid = rec(t['left'][n]); _, hi = rec(t['right'][n])
        rng[n] = (lo, mid)          # leaves [lo, mid] are in the left subtree
        return lo, hi
    rec(0)
    return order, rng


def model_h(trees, C, NF=17):
    T = len(trees)
    L = max(int((t['feat'] < 0).sum()) for t in trees)
    W = (L + 63) // 64
    lines = [f'#define NF {NF}', f'#define NC {C}', f'#define NT {T}', f'#define W {W}', f'#define MAXLEAVES {L}']
    # leaf score table, in-order per tree
    leaf_off, scores, qs = [0], [], []
    for ti, t in enumerate(trees):
        order, rng = leaves_inorder(t)
        for n in order: scores.append(t['leafq'][n])
        leaf_off.append(leaf_off[-1] + len(order))
        for n, (lo, mid) in rng.items():
            mask = [0xffffffffffffffff] * W
            for b in range(lo, mid + 1): mask[b // 64] &= ~(1 << (b % 64)) & 0xffffffffffffffff
            qs.append((int(t['feat'][n]), int(t['thr'][n]), ti, mask))
    scores = np.array(scores, np.uint8)
    lines.append(f'#define NLEAF {len(scores)}')
    lines.append(f'#define NNODE_QS {len(qs)}')
    return lines, leaf_off, scores, qs, W


def p2(n):
    return 1 << max(0, (int(n) - 1).bit_length())


def c_array(ctype, name, vals, per=16, qual='static const', pad2=False):
    vals = list(vals)
    if pad2: vals = vals + [0] * (p2(max(len(vals), 1)) - len(vals))
    body = ',\n'.join('  ' + ', '.join(str(v) for v in vals[i:i + per]) for i in range(0, len(vals), per))
    return f'{qual} {ctype} {name}[{max(len(vals), 1)}] = {{\n{body if vals else "  0"}\n}};\n'


def qs_tables(qs, trees, groups, NF, W, leaf_off, scores, C, qual='static const volatile'):
    """Per stage g: trees groups[g] (contiguous range); per feature ascending (thr, local tree, mask)."""
    out = []
    feat_off_all, thr_all, tid_all, mask_all = [], [], [], []
    for g, (t0, t1) in enumerate(groups):
        sel = [q for q in qs if t0 <= q[2] < t1]
        sel.sort(key=lambda q: (q[0], q[1]))
        base = len(thr_all)
        offs = []
        for f in range(NF + 1):
            offs.append(base + sum(1 for q in sel if q[0] < f))
        feat_off_all += offs
        for f_, th, ti, mk in sel:
            thr_all.append(th); tid_all.append(ti - t0); mask_all += mk
    out.append(c_array('__u32', 'qs_feat_off', feat_off_all, qual=qual))
    out.append(c_array('__s32', 'qs_thr', thr_all, qual=qual, pad2=True))
    out.append(c_array('__u16', 'qs_tree', tid_all, qual=qual, pad2=True))
    out.append(c_array('__u64', 'qs_mask', [f'{m}ULL' for m in mask_all], per=6, qual=qual, pad2=True))
    out.append(c_array('__u32', 'leaf_off', leaf_off, qual=qual, pad2=True))
    out.append(c_array('__u8', 'leaf_score', scores.reshape(-1).tolist(), per=32, qual=qual, pad2=True))
    return ''.join(out), len(thr_all)


def tree_ifelse(t, n=0, ind='    ', mem=False, fx=False):
    """fx: read the feature from the per-CPU scratch at every comparison (volatile) instead of a local copy,
    so the verifier carries no feature-range state across trees and can prune at every tree boundary."""
    if t['feat'][n] < 0:
        if mem: return ''.join(f'{ind}S->s[{c}] += {int(v)};\n' for c, v in enumerate(t['leafq'][n]) if v)
        return ''.join(f'{ind}s{c} += {int(v)};\n' for c, v in enumerate(t['leafq'][n]) if v)
    xf = f'((volatile __s32 *)S->x)[{int(t["feat"][n])}]' if fx else f'x{int(t["feat"][n])}'
    return (f'{ind}if ({xf} <= {int(t["thr"][n])}) {{\n' + tree_ifelse(t, t['left'][n], ind + '    ', mem, fx) +
            f'{ind}}} else {{\n' + tree_ifelse(t, t['right'][n], ind + '    ', mem, fx) + f'{ind}}}\n')


def gen_grf(trees, C, K, NF=17, mem=False, fx=False):
    T = len(trees); G = (T + K - 1) // K
    src = [f'#define STAGE_TREES_MAX 1\n', HDR]
    for g in range(G):
        tl = trees[g * K:(g + 1) * K]
        sec = 'xdp' if g == 0 else f'xdp'
        src.append(f'SEC("{sec}")\nint grf_stage{g}(struct xdp_md *ctx) {{\n')
        if g == 0: src.append('    struct scratch *S = entry(ctx);\n    if (!S) return XDP_ABORTED;\n')
        else: src.append('    struct scratch *S = get_scr();\n    if (!S) return XDP_ABORTED;\n')
        if not fx: src.append(''.join(f'    __s32 x{i} = S->x[{i}];\n' for i in range(NF)))
        if not mem: src.append(''.join(f'    __u32 s{c} = 0;\n' for c in range(C)))
        for t in tl: src.append(tree_ifelse(t, mem=mem, fx=fx))
        if not mem: src.append(''.join(f'    S->s[{c}] += s{c};\n' for c in range(C)))
        if g + 1 < G: src.append(f'    bpf_tail_call(ctx, &jmp, {g + 1} + JB);\n    return XDP_ABORTED;\n}}\n\n')
        else: src.append('    return finish(ctx, S);\n}\n\n')
    src.append('char LICENSE[] SEC("license") = "GPL";\n')
    return ''.join(src), G


CTZ = r'''
static const volatile __u8 debruijn64[64] = {
  0, 1, 48, 2, 57, 49, 28, 3, 61, 58, 50, 42, 38, 29, 17, 4, 62, 55, 59, 36, 53, 51, 43, 22, 45, 39, 33, 30, 24, 18, 12, 5,
  63, 47, 56, 27, 60, 41, 37, 16, 54, 35, 52, 21, 44, 32, 23, 11, 46, 26, 40, 15, 34, 20, 31, 10, 25, 14, 19, 9, 13, 8, 7, 6};
static __always_inline __u32 ctz64(__u64 v) {
    __u64 m = (v & -v) * 0x03f79d71b4cb0a89ULL;
    asm volatile("" : "+r"(m));          /* keep LLVM from folding the de Bruijn lookup into cttz (no BPF lowering) */
    return debruijn64[m >> 58];
}
'''


def gen_qs(trees, C, G, mode, tabs, NF, W, groups):
    """mode 'loop' = bounded loops, table indices masked to power-of-two table sizes;
    'bounds' = bounded loops with explicit index bound checks (a different code shape for the
    verifier, same semantics); 'bpfloop' = bpf_loop callbacks (verified once per callback)."""
    smax = max(b - a for a, b in groups)
    src = [f'#define STAGE_TREES_MAX {smax}\n', HDR, tabs, CTZ]
    src.append(f'static const volatile __u32 stage_t0[{G + 1}] = {{{", ".join(str(a) for a, _ in groups)}, {groups[-1][1]}}};\n')
    if mode == 'bounds':
        body = r'''
    __u32 t0 = stage_t0[STAGE], nt = stage_t0[STAGE + 1] - t0;
    for (__u32 i = 0; i <= VM; i++) { __u64 one = ~0ULL; asm volatile("" : "+r"(one)); S->v[i] = one; }  /* opaque: no memset */
    for (__u32 f = 0; f < NF; f++) {
        __u32 a = qs_feat_off[STAGE * (NF + 1) + f], b = qs_feat_off[STAGE * (NF + 1) + f + 1];
        __s32 xv = S->x[f];
        for (__u32 i = a; i < b && i < QS_N; i++) {
            if (qs_thr[i] >= xv) break;
            __u32 base = qs_tree[i] * W;
            for (__u32 w = 0; w < W; w++) {
                __u32 k = base + w, m = i * W + w;
                if (k <= VM && m <= QMM) S->v[k] &= qs_mask[m];
            }
        }
    }
    for (__u32 t = 0; t < nt && t < STAGE_TREES_MAX; t++) {
        __u32 leaf = 0;
        for (__u32 w = 0; w < W; w++) {
            __u32 k = t * W + w;
            __u64 v = k <= VM ? S->v[k] : 0;
            if (v) { leaf = w * 64 + ctz64(v); break; }
        }
        __u32 tt = t0 + t;
        if (tt > LOM) break;
        __u32 li = (leaf_off[tt] + leaf) * NC;
        for (__u32 c = 0; c < NC; c++) if (li + c <= LSM) S->s[c] += leaf_score[li + c];
    }
'''
    elif mode == 'loop':
        body = r'''
    __u32 t0 = stage_t0[STAGE], nt = stage_t0[STAGE + 1] - t0;
    for (__u32 i = 0; i <= VM; i++) { __u64 one = ~0ULL; asm volatile("" : "+r"(one)); S->v[i] = one; }  /* opaque: no memset */
    for (__u32 f = 0; f < NF; f++) {
        __u32 a = qs_feat_off[STAGE * (NF + 1) + f], b = qs_feat_off[STAGE * (NF + 1) + f + 1];
        __s32 xv = S->x[f];
        for (__u32 i = a; i < b && i < QS_N; i++) {
            if (qs_thr[i & QSM] >= xv) break;
            __u32 base = qs_tree[i & QSM] * W;
            for (__u32 w = 0; w < W; w++) S->v[(base + w) & VM] &= qs_mask[(i * W + w) & QMM];
        }
    }
    for (__u32 t = 0; t < nt && t < STAGE_TREES_MAX; t++) {
        __u32 leaf = 0;
        for (__u32 w = 0; w < W; w++) {
            __u64 v = S->v[(t * W + w) & VM];
            if (v) { leaf = w * 64 + ctz64(v); break; }
        }
        __u32 li = (leaf_off[(t0 + t) & LOM] + leaf) * NC;
        for (__u32 c = 0; c < NC; c++) S->s[c] += leaf_score[(li + c) & LSM];
    }
'''
    else:
        src.append(r'''
struct qctx { struct scratch *S; __u32 a, b; __s32 xv; __u32 t0; };
static long scan_cb(__u64 idx, void *p) {
    struct qctx *q = p; __u32 i = q->a + (__u32)idx;
    if (i >= q->b) return 1;
    if (qs_thr[i & QSM] >= q->xv) return 1;
    __u32 base = qs_tree[i & QSM] * W;
    struct scratch *S = q->S;
    for (__u32 w = 0; w < W; w++) S->v[(base + w) & VM] &= qs_mask[(i * W + w) & QMM];
    return 0;
}
static long leaf_cb(__u64 t, void *p) {
    struct qctx *q = p; __u32 leaf = 0;
    struct scratch *S = q->S;
    for (__u32 w = 0; w < W; w++) {
        __u64 v = S->v[((__u32)t * W + w) & VM];
        if (v) { leaf = w * 64 + ctz64(v); break; }
    }
    __u32 li = (leaf_off[(q->t0 + (__u32)t) & LOM] + leaf) * NC;
    for (__u32 c = 0; c < NC; c++) S->s[c] += leaf_score[(li + c) & LSM];
    return 0;
}
''')
        body = r'''
    __u32 t0 = stage_t0[STAGE], nt = stage_t0[STAGE + 1] - t0;
    for (__u32 i = 0; i <= VM; i++) { __u64 one = ~0ULL; asm volatile("" : "+r"(one)); S->v[i] = one; }  /* opaque: no memset */
    struct qctx q = { .S = S, .t0 = t0 };
    for (__u32 f = 0; f < NF; f++) {
        q.a = qs_feat_off[STAGE * (NF + 1) + f]; q.b = qs_feat_off[STAGE * (NF + 1) + f + 1];
        q.xv = S->x[f];
        bpf_loop(q.b - q.a, scan_cb, &q, 0);
    }
    bpf_loop(nt, leaf_cb, &q, 0);
'''
    for g in range(G):
        src.append(f'#undef STAGE\n#define STAGE {g}\nSEC("xdp")\nint qs_stage{g}(struct xdp_md *ctx) {{\n')
        src.append('    struct scratch *S = entry(ctx);\n' if g == 0 else '    struct scratch *S = get_scr();\n')
        src.append('    if (!S) return XDP_ABORTED;\n' + body)
        if g + 1 < G: src.append(f'    bpf_tail_call(ctx, &jmp, {g + 1} + JB);\n    return XDP_ABORTED;\n}}\n\n')
        else: src.append('    return finish(ctx, S);\n}\n\n')
    src.append('char LICENSE[] SEC("license") = "GPL";\n')
    return ''.join(src)


def gen_rfw(trees, C, G, NF=17, bpfloop=False):
    """Table-driven RF tree walk (data in .rodata, bounded loops over trees x depth), trees split into
    G equal-tree tail-call stages: the classic data-driven RF baseline for QuickScorer."""
    T = len(trees); groups = groups_equal(T, G)
    offs = np.cumsum([0] + [len(t['feat']) for t in trees])
    feat = np.concatenate([t['feat'] for t in trees]); thr = np.concatenate([t['thr'] for t in trees])
    left = np.concatenate([np.where(t['left'] >= 0, t['left'] + o, 0) for t, o in zip(trees, offs)])
    right = np.concatenate([np.where(t['right'] >= 0, t['right'] + o, 0) for t, o in zip(trees, offs)])
    leafq = np.concatenate([t['leafq'] for t in trees]).reshape(-1)
    D = max(int(np.ceil(np.log2(max(len(t['feat']), 2)))) for t in trees)
    depth = 0
    for t in trees:
        st = [(0, 0)]
        while st:
            n, d = st.pop(); depth = max(depth, d)
            if t['feat'][n] >= 0: st += [(t['left'][n], d + 1), (t['right'][n], d + 1)]
    N = len(feat)
    src = [f'#define STAGE_TREES_MAX 1\n#define VM 0\n#define NM {p2(N) - 1}\n#define LQM {p2(N * C) - 1}\n'
           f'#define RM {p2(T + 1) - 1}\n#define DMAX {depth}\n', HDR]
    q = 'static const volatile'
    src.append(c_array('__s16', 'tw_feat', feat.tolist(), qual=q, pad2=True))
    src.append(c_array('__s32', 'tw_thr', thr.tolist(), qual=q, pad2=True))
    src.append(c_array('__u32', 'tw_left', left.tolist(), qual=q, pad2=True))
    src.append(c_array('__u32', 'tw_right', right.tolist(), qual=q, pad2=True))
    src.append(c_array('__u32', 'tw_root', offs[:-1].tolist(), qual=q, pad2=True))
    src.append(c_array('__u8', 'tw_leafq', leafq.tolist(), per=32, qual=q, pad2=True))
    if bpfloop:
        src.append('''struct wctx { struct scratch *S; __u32 t0; };
static long walk_cb(__u64 i, void *p) {
    struct wctx *w = p; struct scratch *S = w->S;
    __u32 n = tw_root[(w->t0 + (__u32)i) & RM];
    for (__u32 d = 0; d < DMAX; d++) {
        __s32 f = tw_feat[n & NM];
        if (f < 0) break;
        n = S->x[f & 31] <= tw_thr[n & NM] ? tw_left[n & NM] : tw_right[n & NM];
    }
    __u32 li = (n & NM) * NC;
    for (__u32 c = 0; c < NC; c++) S->s[c] += tw_leafq[(li + c) & LQM];
    return 0;
}
''')
    for g, (t0, t1) in enumerate(groups):
        if bpfloop:
            src.append(f'SEC("xdp")\nint rfwl_stage{g}(struct xdp_md *ctx) {{\n')
            src.append('    struct scratch *S = entry(ctx);\n' if g == 0 else '    struct scratch *S = get_scr();\n')
            src.append('    if (!S) return XDP_ABORTED;\n')
            src.append(f'    struct wctx w = {{ .S = S, .t0 = {t0} }};\n    bpf_loop({t1 - t0}, walk_cb, &w, 0);\n')
            if g + 1 < len(groups): src.append(f'    bpf_tail_call(ctx, &jmp, {g + 1} + JB);\n    return XDP_ABORTED;\n}}\n\n')
            else: src.append('    return finish(ctx, S);\n}\n\n')
            continue
        src.append(f'SEC("xdp")\nint rfw_stage{g}(struct xdp_md *ctx) {{\n')
        src.append('    struct scratch *S = entry(ctx);\n' if g == 0 else '    struct scratch *S = get_scr();\n')
        src.append('    if (!S) return XDP_ABORTED;\n')
        src.append(f'''    for (__u32 t = {t0}; t < {t1}; t++) {{
        __u32 n = tw_root[t & RM];
        for (__u32 d = 0; d < DMAX; d++) {{
            __s32 f = tw_feat[n & NM];
            if (f < 0) break;
            n = S->x[f & 31] <= tw_thr[n & NM] ? tw_left[n & NM] : tw_right[n & NM];
        }}
        __u32 li = (n & NM) * NC;
        for (__u32 c = 0; c < NC; c++) S->s[c] += tw_leafq[(li + c) & LQM];
    }}
''')
        if g + 1 < len(groups): src.append(f'    bpf_tail_call(ctx, &jmp, {g + 1} + JB);\n    return XDP_ABORTED;\n}}\n\n')
        else: src.append('    return finish(ctx, S);\n}\n\n')
    src.append('char LICENSE[] SEC("license") = "GPL";\n')
    return ''.join(src)


def gen_null(G):
    """Null chain: harness parsing + G stages that only tail-call (no model) + argmax/finish."""
    src = ['#define STAGE_TREES_MAX 1\n', HDR]
    for g in range(G):
        src.append(f'SEC("xdp")\nint null_stage{g}(struct xdp_md *ctx) {{\n')
        src.append('    struct scratch *S = entry(ctx);\n' if g == 0 else '    struct scratch *S = get_scr();\n')
        src.append('    if (!S) return XDP_ABORTED;\n')
        if g + 1 < G: src.append(f'    bpf_tail_call(ctx, &jmp, {g + 1} + JB);\n    return XDP_ABORTED;\n}}\n\n')
        else: src.append('    return finish(ctx, S);\n}\n\n')
    src.append('char LICENSE[] SEC("license") = "GPL";\n')
    return ''.join(src)


def gen_nn(npz, stages=1, NF=17):
    """Quantized NN (train_e1.nn_quantize/nn_int semantics) as unrolled immediates. Input: the 8-bit
    log quantizer q(x) = min(4*floor(log2(x+1)) + next 2 mantissa bits, 127) computed with shifts.
    stages=1: one program; stages=3: one layer per tail-call stage (Hara's layer-wise layout), the
    activations travel in the scratch's v[] words."""
    m = np.load(npz)
    L = [(m[f'Wq{i}'].astype(np.int64), m[f'bq{i}'].astype(np.int64), m[f'M{i}'].astype(np.int64)) for i in range(3)]
    C = L[2][0].shape[0]
    H = [L[0][0].shape[0], L[1][0].shape[0]]
    hdr = [f'#define NF {NF}\n#define NC {C}\n#define W 1\n#define VM 63\n#define STAGE_TREES_MAX 1\n']
    src = [HDR.replace('#include "model.h"\n', '')]
    src.insert(0, ''.join(hdr))
    src.append(r'''
#define OPAQUE(v) asm volatile("" : "+r"(v))   /* stop LLVM from turning bit tricks into branches */
static __always_inline __u64 nz(__u64 x) { __s64 n = -(__s64)x; OPAQUE(n); return (__u64)n >> 63; }
static __always_inline __s64 logq(__s32 x) {   /* branch-free: the verifier sees one path */
    __s32 sg = x >> 31; OPAQUE(sg);
    __s64 xx = x & ~sg;
    __u64 v = (__u64)xx + 1, t = v, e = 0, sh;
    sh = nz(t >> 16) << 4; t >>= sh; e += sh;
    sh = nz(t >> 8) << 3; t >>= sh; e += sh;
    sh = nz(t >> 4) << 2; t >>= sh; e += sh;
    sh = nz(t >> 2) << 1; t >>= sh; e += sh;
    e += nz(t >> 1);
    return (__s64)(4 * e + (((v << 2) >> e) & 3));   /* <= 124 for x < 2^31 */
}
static __always_inline __s64 clamp127(__s64 h) {     /* branch-free relu + min(.,127) */
    __s64 m = h >> 63; OPAQUE(m);
    h &= ~m;
    __s64 d = 127 - h, dm = d >> 63; OPAQUE(dm);
    return h + (d & dm);
}
''')
    # activations live in the per-CPU scratch S->v[] (input 0..NF-1, hidden1 at 32, hidden2 at 48):
    # 17 + 16 + 16 int64 locals would exceed the 512-byte BPF stack after register spills
    BASE = {'a': 0, 'h': 32, 'k': 48}
    def layer(i, inp, outp, last):
        W, b, M = L[i]
        code = []
        for o in range(W.shape[0]):
            terms = ' + '.join(f'({int(W[o, j])}) * (__s64)S->v[{BASE[inp] + j}]' for j in range(W.shape[1]) if W[o, j])
            acc = f'(({terms or "0"}) + ({int(b[o])}))'
            if not last:
                code.append(f'    S->v[{BASE[outp] + o}] = (__u64)clamp127(({acc} * {int(M[o])}) >> 16);\n')
            else:
                code.append(f'    __s64 {outp}{o} = ({acc} * {int(M[o])}) >> 16;\n')
        return ''.join(code)
    def prologue(g):
        return ('    struct scratch *S = entry(ctx);\n' if g == 0 else '    struct scratch *S = get_scr();\n') + '    if (!S) return XDP_ABORTED;\n'
    def argmax_tail(outp):
        c = f'    __u32 best = 0; __s64 bv = {outp}0;\n'
        c += ''.join(f'    if ({outp}{k} > bv) {{ bv = {outp}{k}; best = {k}; }}\n' for k in range(1, C))
        c += '#pragma unroll\n    for (int c = 0; c < NC; c++) S->s[c] = 0;\n'
        c += '    if (best < NC) S->s[best] = 1;\n    return finish(ctx, S);\n'
        return c
    inq = ''.join(f'    S->v[{j}] = (__u64)logq(S->x[{j}]);\n' for j in range(NF))
    if stages == 1:
        src.append('SEC("xdp")\nint nn_stage0(struct xdp_md *ctx) {\n' + prologue(0) + inq +
                   layer(0, 'a', 'h', False) + layer(1, 'h', 'k', False) + layer(2, 'k', 'z', True) + argmax_tail('z') + '}\n')
    else:
        src.append('SEC("xdp")\nint nn_stage0(struct xdp_md *ctx) {\n' + prologue(0) + inq + layer(0, 'a', 'h', False) +
                   '    bpf_tail_call(ctx, &jmp, 1 + JB);\n    return XDP_ABORTED;\n}\n')
        src.append('SEC("xdp")\nint nn_stage1(struct xdp_md *ctx) {\n' + prologue(1) + layer(1, 'h', 'k', False) +
                   '    bpf_tail_call(ctx, &jmp, 2 + JB);\n    return XDP_ABORTED;\n}\n')
        src.append('SEC("xdp")\nint nn_stage2(struct xdp_md *ctx) {\n' + prologue(2) + layer(2, 'k', 'z', True) + argmax_tail('z') + '}\n')
    src.append('char LICENSE[] SEC("license") = "GPL";\n')
    return ''.join(src)


def groups_equal(T, G):
    b = [round(i * T / G) for i in range(G + 1)]
    return [(b[i], b[i + 1]) for i in range(G)]


def main():
    npz, out = sys.argv[1], sys.argv[2]
    args = sys.argv[3:]
    if '_NN_' in os.path.basename(npz):
        os.makedirs(out, exist_ok=True)
        for st in (1, 3):
            open(f'{out}/nn_s{st}.bpf.c', 'w').write(gen_nn(npz, st))
        return
    ks = [int(args[i + 1]) for i in range(len(args)) if args[i] == '--grf-k']
    gs = [int(args[i + 1]) for i in range(len(args)) if args[i] == '--qs-g']
    os.makedirs(out, exist_ok=True)
    trees, C = load(npz)
    NF = 17
    lines, leaf_off, scores, qs, W = model_h(trees, C, NF)
    T = len(trees)
    # userspace reference tables (tree walk + QS for G=1) in model.h
    lines.append(c_array('__s16', 'tw_feat', np.concatenate([t['feat'] for t in trees]).tolist()))
    lines.append(c_array('__s32', 'tw_thr', np.concatenate([t['thr'] for t in trees]).tolist()))
    offs = np.cumsum([0] + [len(t['feat']) for t in trees])
    lines.append(c_array('__s32', 'tw_left', np.concatenate([np.where(t['left'] >= 0, t['left'] + o, -1) for t, o in zip(trees, offs)]).tolist()))
    lines.append(c_array('__s32', 'tw_right', np.concatenate([np.where(t['right'] >= 0, t['right'] + o, -1) for t, o in zip(trees, offs)]).tolist()))
    lines.append(c_array('__u32', 'tw_root', offs[:-1].tolist()))
    lines.append(c_array('__u8', 'tw_leafq', np.concatenate([t['leafq'] for t in trees]).reshape(-1).tolist(), per=32))
    nconst = 7
    open(f'{out}/model.h', 'w').write('#pragma once\n#include <linux/types.h>\n' + '\n'.join(lines[:nconst]) + '\n')
    open(f'{out}/tw.h', 'w').write('#pragma once\n' + '\n'.join(lines[nconst:]) + '\n')
    tabs1, nq1 = qs_tables(qs, trees, [(0, T)], NF, W, leaf_off, scores, C, qual='static const')
    open(f'{out}/qs1.h', 'w').write(f'#pragma once\n#define QS_N {max(nq1, 1)}\n' + tabs1)
    nulls = [int(args[i + 1]) for i in range(len(args)) if args[i] == '--null-g']
    for G in nulls:
        open(f'{out}/null_g{G}.bpf.c', 'w').write(gen_null(G))
    for K in ks:
        s, G = gen_grf(trees, C, K, NF)
        open(f'{out}/grf_k{K}.bpf.c', 'w').write(s)
    for K in [int(args[i + 1]) for i in range(len(args)) if args[i] == '--grfm-k']:
        s, G = gen_grf(trees, C, K, NF, mem=True)
        open(f'{out}/grfm_k{K}.bpf.c', 'w').write(s)
    for K in [int(args[i + 1]) for i in range(len(args)) if args[i] == '--grfx-k']:
        s, G = gen_grf(trees, C, K, NF, fx=True)
        open(f'{out}/grfx_k{K}.bpf.c', 'w').write(s)
    for G in [int(args[i + 1]) for i in range(len(args)) if args[i] == '--rfw-g']:
        open(f'{out}/rfw_g{G}.bpf.c', 'w').write(gen_rfw(trees, C, G, NF))
        open(f'{out}/rfwl_g{G}.bpf.c', 'w').write(gen_rfw(trees, C, G, NF, bpfloop=True))
    for G in gs:
        groups = groups_equal(T, G)
        tabs, nq = qs_tables(qs, trees, groups, NF, W, leaf_off, scores, C)
        smax = max(b - a for a, b in groups)
        consts = (f'#define QS_N {max(nq, 1)}\n#define QSM {p2(max(nq, 1)) - 1}\n#define QMM {p2(max(nq * W, 1)) - 1}\n'
                  f'#define LOM {p2(len(leaf_off)) - 1}\n#define LSM {p2(len(scores) * C) - 1}\n#define VM {p2(smax * W) - 1}\n')
        for mode, pre in (('loop', 'qs'), ('bounds', 'qsb'), ('bpfloop', 'qsl')):
            open(f'{out}/{pre}_g{G}.bpf.c', 'w').write(consts + gen_qs(trees, C, G, mode, tabs, NF, W, groups))


if __name__ == '__main__':
    main()

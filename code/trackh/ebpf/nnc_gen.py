#!/usr/bin/env python3
"""Emit nnc.h for nnc.c: the quantized NN (train_e1.nn_int semantics) as C arrays.
    nnc_gen.py <NN model.npz> <outdir>"""
import sys
import numpy as np
m = np.load(sys.argv[1]); out = sys.argv[2]
L = [(m[f'Wq{i}'], m[f'bq{i}'], m[f'M{i}']) for i in range(3)]
s = ['#pragma once', f'#define NF {L[0][0].shape[1]}', f'#define H1 {L[0][0].shape[0]}', f'#define H2 {L[1][0].shape[0]}', f'#define NC {L[2][0].shape[0]}']
for i, (W, b, M) in enumerate(L):
    s.append(f'static const int32_t W{i}[{W.size}] = {{{", ".join(str(int(v)) for v in W.reshape(-1))}}};')
    s.append(f'static const int64_t B{i}[{b.size}] = {{{", ".join(str(int(v)) for v in b)}}};')
    s.append(f'static const int64_t M{i}[{M.size}] = {{{", ".join(str(int(v)) for v in M)}}};')
open(f'{out}/nnc.h', 'w').write('\n'.join(s) + '\n')

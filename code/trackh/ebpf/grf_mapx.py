#!/usr/bin/env python3
"""G-RF with feature reads from the per-CPU scratch at every comparison (volatile), so the verifier carries no
feature-range state across trees and prunes at every tree boundary (verifier cost ~linear in nodes).
    python -I grf_mapx.py <model.npz> <out dir> <trees per program K> {orig|mapx}"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import codegen, numpy as np
mp, out, K, how = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
os.makedirs(out, exist_ok=True)
# reuse codegen loader via its CLI to get model.h etc
import subprocess
subprocess.run([sys.executable, '-I', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'codegen.py'), mp, out, '--grf-k', str(K)], check=True)
src = open(f'{out}/grf_k{K}.bpf.c').read()
if how == 'mapx':   # read features from the per-CPU scratch at every comparison (no range state carried across trees)
    src = re.sub(r'    __s32 x\d+ = S->x\[\d+\];\n', '', src)
    src = re.sub(r'if \(x(\d+) <=', r'if (((volatile __s32 *)S->x)[\1] <=', src)
open(f'{out}/grfx_k{K}_{how}.bpf.c', 'w').write(src)
print(f'{out}/grfx_k{K}_{how}.bpf.c')

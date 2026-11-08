#!/usr/bin/env python3
"""On DUT: python3 make_afxdp_clean.py ~/ebpf-classifier/xsknf ~/e0/afxdp-clean

Creates a separate copy; refuses to overwrite it. Build with:
    make -o update_submodules examples/mlids/mlids
The copied dependency sources/libraries are already pinned and populated.
This repairs the architecture by moving flow extraction wholly into one worker;
it is NOT inference-semantic equivalence with the broken faithful COMBINED code.
"""
from pathlib import Path
import shutil
import sys

source, dest = [Path(p).expanduser() for p in sys.argv[1:]]
assets = Path(__file__).resolve().parent
shutil.copytree(source, dest, ignore=shutil.ignore_patterns('.git'))
app = dest / 'examples/mlids'
p = app / 'mlids_user.c'
s = p.read_text()
for line in ('#include "../common/hashmap.h"\n', '#include "../common/hashmap.c"\n',
             'struct hash_map *sessions;\n'):
    assert s.count(line) == 1
    s = s.replace(line, '')
start = s.index('static void init_sessions()')
end = s.index('static struct option long_options[]')
s = s[:start] + (assets / 'afxdp_processor.c').read_text() + '\n' + s[end:]
old = '  xsknf_start_workers();\n  init_stats();\n  init_sessions();'
assert s.count(old) == 1
s = s.replace(old, '''  if (config.workers != 1 || config.num_interfaces != 1 || config.batch_size > 255 ||
      config.working_mode != MODE_COMBINED || opt_ml_method == RF) {
    fprintf(stderr, "clean variant requires -w 1 -M COMBINED and -m NN or DT\\n");
    xsknf_cleanup();
    return EXIT_FAILURE;
  }
  if (clean_init()) { xsknf_cleanup(); return EXIT_FAILURE; }
  init_stats();
  xsknf_start_workers();
  fprintf(stderr, "CLEAN READY\\n");''')
old = '  xsknf_cleanup();\n\n  clear_maps();'
assert s.count(old) == 1
# xsknf_cleanup stops/joins workers; counters are read only after the join.
s = s.replace(old, '  xsknf_cleanup();\n  clean_report();\n  clean_destroy();')
p.write_text(s)
shutil.copyfile(assets / 'afxdp_state.h', app / 'afxdp_state.h')
shutil.copyfile(assets / 'afxdp_redirect.c', app / 'mlids_kern.c')
# Upstream exits on a temporarily full fill ring even when reserve returns 0.
# Keep every recycled UMEM address; bound retries if the consumer is stuck.
framework = dest / 'src/xsknf.c'
t = framework.read_text()
old = '''\t\tret = xsk_ring_prod__reserve(&xsk->fq, ndrop, &idx);
\t\tif (ret != ndrop) {
\t\t\t/* (0 < ret < ndrop) should never happen */
\t\t\texit_with_error(-ret);
\t\t}'''
new = '''\t\tret = xsk_ring_prod__reserve(&xsk->fq, ndrop, &idx);
        unsigned retries = 0;
        while (ret != ndrop) {
            if (stop_workers) return;
            if (++retries == 100000) exit_with_error(EAGAIN);
            clean_fill_retries++;
            recvfrom(xsk_socket__fd(xsk->xsk), NULL, 0, MSG_DONTWAIT, NULL, NULL);
            ret = xsk_ring_prod__reserve(&xsk->fq, ndrop, &idx);
        }'''
assert t.count(old) == 1
t = t.replace(old, new)
assert t.count('static int stop_workers = 0;') == 1
t = t.replace('static int stop_workers = 0;',
              'unsigned long clean_fill_retries;\nstatic int stop_workers = 0;')
framework.write_text(t)
# Copied objects predate the generated source; force rebuilding both app objects.
for name in ('mlids_user.o', 'mlids_kern.o', 'mlids'):
    (app / name).unlink(missing_ok=True)
print(dest)

/* E4 matched-model timing: load several runtime variants of the SAME RF at once and time them in
 * interleaved round-robin passes (experimental.md E4: interleaved baseline/proposed repeats).
 *   sudo ./benchmulti <X.i32> <ref.u8> <ntime> <repeat> <passes> <obj1> [obj2 ...]
 * Each pass times every object on the same ntime rows (repeat runs per row via BPF_PROG_TEST_RUN)
 * in a rotated order; per object it prints the per-pass mean ns and the pooled per-row p50/p95/p99
 * (one JSON line per object). Correctness on all rows is re-checked once per object. */
#define _GNU_SOURCE
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define NFEAT 17
static int cmpu(const void *a, const void *b) { uint64_t x = *(uint64_t *)a, y = *(uint64_t *)b; return (x > y) - (x < y); }

int main(int argc, char **argv) {
    if (argc < 7) { fprintf(stderr, "usage\n"); return 2; }
    int ntime = atoi(argv[3]), repeat = atoi(argv[4]), passes = atoi(argv[5]), nobj = argc - 6;
    FILE *fx = fopen(argv[1], "rb"), *fr = fopen(argv[2], "rb");
    fseek(fx, 0, SEEK_END); long n = ftell(fx) / (NFEAT * 4); rewind(fx);
    int32_t *X = malloc(n * NFEAT * 4); uint8_t *ref = malloc(n);
    if (fread(X, NFEAT * 4, n, fx) != (size_t)n || fread(ref, 1, n, fr) != (size_t)n) return 1;
    if (ntime > n) ntime = n;
    int fd0[64] = {0}; long bad[64] = {0};
    for (int o = 0; o < nobj; o++) {
        struct bpf_object *obj = bpf_object__open_file(argv[6 + o], NULL);
        if (!obj || bpf_object__load(obj)) { fd0[o] = -1; continue; }
        int jmp = bpf_object__find_map_fd_by_name(obj, "jmp"), k = 0; struct bpf_program *p;
        bpf_object__for_each_program(p, obj) {
            int fd = bpf_program__fd(p);
            if (k == 0) fd0[o] = fd;
            else if (jmp >= 0) { uint32_t key = k; bpf_map_update_elem(jmp, &key, &fd, BPF_ANY); }
            k++;
        }
    }
    uint8_t pkt[14 + 20 + 8 + NFEAT * 4 + 4], out[sizeof pkt];
    memset(pkt, 0, sizeof pkt); pkt[12] = 8; pkt[14] = 0x45; pkt[17] = 20 + 8 + NFEAT * 4 + 4; pkt[22] = 64; pkt[23] = 17;
    const int PO = 42;
    for (int o = 0; o < nobj; o++) {
        if (fd0[o] < 0) continue;
        for (long i = 0; i < n; i++) {
            memcpy(pkt + PO, X + i * NFEAT, NFEAT * 4);
            LIBBPF_OPTS(bpf_test_run_opts, t, .data_in = pkt, .data_size_in = sizeof pkt, .data_out = out,
                        .data_size_out = sizeof out, .repeat = 1);
            if (bpf_prog_test_run_opts(fd0[o], &t) || t.retval != 1 || out[PO + NFEAT * 4] != ref[i]) bad[o]++;
        }
    }
    uint64_t *d = calloc((size_t)nobj * passes * ntime, sizeof *d);
    for (int ps = 0; ps < passes; ps++)
        for (int j = 0; j < nobj; j++) {
            int o = (j + ps) % nobj;
            if (fd0[o] < 0) continue;
            for (int i = 0; i < ntime; i++) {
                memcpy(pkt + PO, X + (long)i * NFEAT, NFEAT * 4);
                LIBBPF_OPTS(bpf_test_run_opts, t, .data_in = pkt, .data_size_in = sizeof pkt, .repeat = repeat);
                bpf_prog_test_run_opts(fd0[o], &t);
                d[((size_t)o * passes + ps) * ntime + i] = t.duration;
            }
        }
    for (int o = 0; o < nobj; o++) {
        if (fd0[o] < 0) { printf("{\"obj\":\"%s\",\"loaded\":0}\n", argv[6 + o]); continue; }
        printf("{\"obj\":\"%s\",\"loaded\":1,\"mismatch\":%ld,\"rows\":%ld,\"pass_mean_ns\":[", argv[6 + o], bad[o], n);
        for (int ps = 0; ps < passes; ps++) {
            double m = 0; uint64_t *a = d + ((size_t)o * passes + ps) * ntime;
            for (int i = 0; i < ntime; i++) m += a[i];
            printf("%s%.1f", ps ? "," : "", m / ntime);
        }
        uint64_t *a = d + (size_t)o * passes * ntime; size_t m = (size_t)passes * ntime;
        qsort(a, m, sizeof *a, cmpu);
        printf("],\"p50\":%lu,\"p95\":%lu,\"p99\":%lu}\n", (unsigned long)a[m / 2], (unsigned long)a[(size_t)(m * 0.95)],
               (unsigned long)a[(size_t)(m * 0.99)]);
    }
    return 0;
}

/* E2/E4 harness: load one generated RF XDP object (stage programs chained by tail calls), check
 * predictions against the integer reference, time isolated inference with BPF_PROG_TEST_RUN.
 *   sudo ./bench <obj.bpf.o> <X.i32> <ref.u8> <n_time_rows> <repeat> [--perf]
 * Output: one JSON line. On load failure: {"loaded":0, "error":..., verifier log tail in <obj>.vlog}.
 * Stage programs are the object's XDP programs in section order; stage k>0 goes to jmp[k]. */
#define _GNU_SOURCE
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <linux/if_ether.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "perfc.h"

#define NFEAT 17
#define LOGSZ (64u << 20)
static char *vlog;

static double now_s(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
static int cmpu(const void *a, const void *b) { uint64_t x = *(uint64_t *)a, y = *(uint64_t *)b; return (x > y) - (x < y); }
static long parse_processed(const char *log) {
    const char *p = log, *q = NULL;
    while ((p = strstr(p, "processed "))) { q = p; p++; }
    return q ? atol(q + 10) : -1;
}

int main(int argc, char **argv) {
    if (argc < 6) { fprintf(stderr, "usage: bench obj X ref ntime repeat\n"); return 2; }
    const char *objp = argv[1];
    int ntime = atoi(argv[4]), repeat = atoi(argv[5]);
    libbpf_set_strict_mode(LIBBPF_STRICT_ALL);
    vlog = calloc(1, LOGSZ);
    struct bpf_object *obj = bpf_object__open_file(objp, NULL);
    if (!obj) { printf("{\"loaded\":0,\"error\":\"open\"}\n"); return 1; }
    struct bpf_program *prog; int nprog = 0;
    bpf_object__for_each_program(prog, obj) {
        bpf_program__set_log_level(prog, 1 | 4);           /* stats + per-insn summary off */
        bpf_program__set_log_buf(prog, vlog, LOGSZ);
        nprog++;
    }
    double t0 = now_s();
    int err = bpf_object__load(obj);
    int log_retry = 0;
    if (err == -ENOSPC) {
        /* the level-1 verifier log overflowed LOGSZ (the kernel then fails the load with ENOSPC even if
         * the program verified): reload with statistics only so the verdict is the verifier's */
        bpf_object__close(obj); log_retry = 1;
        obj = bpf_object__open_file(objp, NULL);
        bpf_object__for_each_program(prog, obj) { bpf_program__set_log_level(prog, 4); bpf_program__set_log_buf(prog, vlog, LOGSZ); }
        memset(vlog, 0, LOGSZ); t0 = now_s();
        err = bpf_object__load(obj);
    }
    double tload = now_s() - t0;
    char lp[4096]; snprintf(lp, sizeof lp, "%s.vlog", objp);
    FILE *lf = fopen(lp, "w"); if (lf) { fputs(vlog, lf); fclose(lf); }
    if (err) {
        char msg[256]; libbpf_strerror(err, msg, sizeof msg);
        for (char *c = msg; *c; c++) if (*c == '"') *c = '\'';
        printf("{\"loaded\":0,\"error\":\"%s\",\"errno\":%d,\"load_s\":%.3f,\"processed_insns_last\":%ld,\"nprog\":%d,\"log_retry\":%d}\n",
               msg, -err, tload, parse_processed(vlog), nprog, log_retry);
        return 1;
    }
    int jmp = bpf_object__find_map_fd_by_name(obj, "jmp");
    int fds[64], k = 0; uint64_t xl = 0, jl = 0, vins = 0, vins_max = 0;
    bpf_object__for_each_program(prog, obj) {
        int fd = bpf_program__fd(prog); fds[k] = fd;
        struct bpf_prog_info info = {}; uint32_t il = sizeof info;
        bpf_prog_get_info_by_fd(fd, &info, &il);
        xl += info.xlated_prog_len; jl += info.jited_prog_len; vins += info.verified_insns;
        if (info.verified_insns > vins_max) vins_max = info.verified_insns;
        if (k > 0 && jmp >= 0) { uint32_t key = k; bpf_map_update_elem(jmp, &key, &fd, BPF_ANY); }
        k++;
    }
    /* data */
    FILE *fx = fopen(argv[2], "rb"), *fr = fopen(argv[3], "rb");
    fseek(fx, 0, SEEK_END); long n = ftell(fx) / (NFEAT * 4); rewind(fx);
    int32_t *X = malloc(n * NFEAT * 4); uint8_t *ref = malloc(n);
    if (fread(X, NFEAT * 4, n, fx) != (size_t)n || fread(ref, 1, n, fr) != (size_t)n) { fprintf(stderr, "short\n"); return 1; }
    uint8_t pkt[14 + 20 + 8 + NFEAT * 4 + 4], out[sizeof pkt];
    memset(pkt, 0, sizeof pkt);
    pkt[12] = 0x08; pkt[13] = 0x00;                         /* IPv4 */
    pkt[14] = 0x45; pkt[14 + 2] = 0; pkt[14 + 3] = 20 + 8 + NFEAT * 4 + 4; pkt[14 + 8] = 64; pkt[14 + 9] = 17;
    const int PO = 14 + 20 + 8;
    long bad = 0, badret = 0;
    LIBBPF_OPTS(bpf_test_run_opts, o);
    for (long i = 0; i < n; i++) {
        memcpy(pkt + PO, X + i * NFEAT, NFEAT * 4); pkt[PO + NFEAT * 4] = 0xff;
        o.data_in = pkt; o.data_size_in = sizeof pkt; o.data_out = out; o.data_size_out = sizeof out; o.repeat = 1;
        if (bpf_prog_test_run_opts(fds[0], &o)) { badret++; continue; }
        if (o.retval != 1 /* XDP_DROP */) badret++;
        else if (out[PO + NFEAT * 4] != ref[i]) bad++;
    }
    /* timing: per-row mean ns over `repeat` runs, for the first ntime rows */
    if (ntime > n) ntime = n;
    uint64_t *d = calloc(ntime, sizeof *d);
    /* --perf: kernel-mode hardware counters around the timing loop only (E4b mechanism study) */
    int perf = argc > 6 && !strcmp(argv[6], "--perf");
    struct pc pc; if (perf) { pc_open(&pc, 1); pc_start(&pc); }
    for (int i = 0; i < ntime; i++) {
        memcpy(pkt + PO, X + (long)i * NFEAT, NFEAT * 4);
        LIBBPF_OPTS(bpf_test_run_opts, t, .data_in = pkt, .data_size_in = sizeof pkt, .repeat = repeat);
        bpf_prog_test_run_opts(fds[0], &t); d[i] = t.duration;
    }
    char pj[1024] = "";
    if (perf) { pc_stop(&pc); pc_json(pj, sizeof pj, "k_", &pc, (double)ntime * repeat); }
    qsort(d, ntime, sizeof *d, cmpu);
    double mean = 0; for (int i = 0; i < ntime; i++) mean += d[i]; mean /= ntime ? ntime : 1;
    printf("{\"loaded\":1,\"nprog\":%d,\"load_s\":%.3f,\"xlated_bytes\":%lu,\"jited_bytes\":%lu,"
           "\"verified_insns\":%lu,\"verified_insns_max_prog\":%lu,\"rows\":%ld,\"mismatch\":%ld,\"bad_run\":%ld,"
           "\"time_rows\":%d,\"repeat\":%d,\"ns_mean\":%.1f,\"ns_p50\":%lu,\"ns_p95\":%lu,\"ns_p99\":%lu,\"ns_max\":%lu%s}\n",
           nprog, tload, (unsigned long)xl, (unsigned long)jl, (unsigned long)vins, (unsigned long)vins_max, n, bad, badret,
           ntime, repeat, mean, (unsigned long)d[ntime / 2], (unsigned long)d[(int)(ntime * 0.95)],
           (unsigned long)d[(int)(ntime * 0.99)], (unsigned long)d[ntime - 1], pj);
    return 0;
}

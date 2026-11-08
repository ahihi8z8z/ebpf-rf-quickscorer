/* E4b mechanism study, userspace side. Same tables as rfc.c (codegen.py model.h/tw.h/qs1.h).
 *   cc -O2 -march=native -I<model dir> rfm.c -o rfm && ./rfm <X.i32> <ref.u8> <reps> [rowrep]
 * Runtimes (all checked bit-exactly against the integer reference):
 *   walk     table walk (as rfc.c)
 *   qs       QuickScorer (as rfc.c)
 *   qs_bpf   QuickScorer with the code shape the eBPF verifier forces on qs_g* (codegen 'loop'):
 *            every table index masked to its power-of-two size, the scan bounded by QS_N, the
 *            break on threshold inside the loop body, bitvector index masked (& VM)
 *   qs_vol   qs_bpf + bitvector accessed through a volatile pointer (every update is a real
 *            load+store and nothing is kept in registers across updates, as with map memory)
 * Work counts per row: walk steps (internal nodes visited) and QS updates (false nodes ANDed).
 * Hardware counters (user mode) per row for each runtime over one pass of all rows. */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "model.h"
#include "tw.h"
#include "qs1.h"
#include "perfc.h"

#define P2M(a) ((uint32_t)(sizeof(a) / sizeof((a)[0])) - 1)   /* codegen pads tables to powers of two */
#define VMASK 127u                                           /* >= NT*W-1 for NT*W <= 128 */
static long n_steps, n_upd;

static inline int argmax(const uint32_t *s) { int b = 0; for (int c = 1; c < NC; c++) if (s[c] > s[b]) b = c; return b; }

static int walk(const int32_t *x) {
    uint32_t s[NC] = {0};
    for (int t = 0; t < NT; t++) {
        int n = tw_root[t];
        while (tw_feat[n] >= 0) n = x[tw_feat[n]] <= tw_thr[n] ? tw_left[n] : tw_right[n];
        for (int c = 0; c < NC; c++) s[c] += tw_leafq[n * NC + c];
    }
    return argmax(s);
}
static int walk_count(const int32_t *x) {
    uint32_t s[NC] = {0};
    for (int t = 0; t < NT; t++) {
        int n = tw_root[t];
        while (tw_feat[n] >= 0) { n_steps++; n = x[tw_feat[n]] <= tw_thr[n] ? tw_left[n] : tw_right[n]; }
        for (int c = 0; c < NC; c++) s[c] += tw_leafq[n * NC + c];
    }
    return argmax(s);
}
static inline int qs_leaves(const uint64_t *v) {
    uint32_t s[NC] = {0};
    for (int t = 0; t < NT; t++) {
        int leaf = 0;
        for (int w = 0; w < W; w++) if (v[t * W + w]) { leaf = w * 64 + __builtin_ctzll(v[t * W + w]); break; }
        const uint8_t *ls = leaf_score + (size_t)(leaf_off[t] + leaf) * NC;
        for (int c = 0; c < NC; c++) s[c] += ls[c];
    }
    return argmax(s);
}
static uint64_t vbuf[NT * W > 128 ? NT * W : 128];
static int qs(const int32_t *x) {
    uint64_t *v = vbuf; memset(v, 0xff, sizeof(uint64_t) * NT * W);
    for (int f = 0; f < NF; f++) {
        int32_t xv = x[f];
        for (uint32_t i = qs_feat_off[f]; i < qs_feat_off[f + 1] && qs_thr[i] < xv; i++) {
            uint64_t *vt = v + qs_tree[i] * W; const uint64_t *m = (const uint64_t *)qs_mask + (size_t)i * W;
            for (int w = 0; w < W; w++) vt[w] &= m[w];
        }
    }
    return qs_leaves(v);
}
static int qs_count(const int32_t *x) {
    uint64_t *v = vbuf; memset(v, 0xff, sizeof(uint64_t) * NT * W);
    for (int f = 0; f < NF; f++) {
        int32_t xv = x[f];
        for (uint32_t i = qs_feat_off[f]; i < qs_feat_off[f + 1] && qs_thr[i] < xv; i++) {
            n_upd++;
            uint64_t *vt = v + qs_tree[i] * W; const uint64_t *m = (const uint64_t *)qs_mask + (size_t)i * W;
            for (int w = 0; w < W; w++) vt[w] &= m[w];
        }
    }
    return qs_leaves(v);
}
/* the eBPF 'loop' body of codegen.gen_qs, transliterated (W == 1 regime) */
static int qs_bpf(const int32_t *x) {
    uint64_t *v = vbuf;
    for (uint32_t i = 0; i <= VMASK; i++) v[i] = ~0ULL;
    for (uint32_t f = 0; f < NF; f++) {
        uint32_t a = qs_feat_off[f], b = qs_feat_off[f + 1];
        int32_t xv = x[f];
        for (uint32_t i = a; i < b && i < QS_N; i++) {
            if (qs_thr[i & P2M(qs_thr)] >= xv) break;
            uint32_t base = qs_tree[i & P2M(qs_tree)] * W;
            for (uint32_t w = 0; w < W; w++) v[(base + w) & VMASK] &= qs_mask[(i * W + w) & P2M(qs_mask)];
        }
    }
    return qs_leaves(v);
}
static int qs_vol(const int32_t *x) {
    volatile uint64_t *v = vbuf;
    for (uint32_t i = 0; i <= VMASK; i++) v[i] = ~0ULL;
    for (uint32_t f = 0; f < NF; f++) {
        uint32_t a = qs_feat_off[f], b = qs_feat_off[f + 1];
        int32_t xv = x[f];
        for (uint32_t i = a; i < b && i < QS_N; i++) {
            if (qs_thr[i & P2M(qs_thr)] >= xv) break;
            uint32_t base = qs_tree[i & P2M(qs_tree)] * W;
            for (uint32_t w = 0; w < W; w++) v[(base + w) & VMASK] &= qs_mask[(i * W + w) & P2M(qs_mask)];
        }
    }
    return qs_leaves((const uint64_t *)vbuf);
}

static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec * 1e9 + t.tv_nsec; }
static int cmpd(const void *a, const void *b) { double x = *(double *)a, y = *(double *)b; return (x > y) - (x < y); }

typedef int (*fn)(const int32_t *);
int main(int argc, char **argv) {
    if (NT * W > 128) { printf("{\"error\":\"NT*W>128 not supported by rfm\"}\n"); return 2; }
    FILE *fx = fopen(argv[1], "rb"), *fp = fopen(argv[2], "rb");
    int reps = argc > 3 ? atoi(argv[3]) : 5; if (reps > 64) reps = 64;
    int rowrep = argc > 4 ? atoi(argv[4]) : 1; if (rowrep < 1) rowrep = 1;   /* >1: each row run rowrep times in a row (BPF_PROG_TEST_RUN .repeat regime) */
    fseek(fx, 0, SEEK_END); long n = ftell(fx) / (NF * 4); rewind(fx);
    int32_t *X = malloc(n * NF * 4); uint8_t *ref = malloc(n);
    if (fread(X, 4 * NF, n, fx) != (size_t)n || fread(ref, 1, n, fp) != (size_t)n) { fprintf(stderr, "short read\n"); return 1; }
    const char *name[] = {"walk", "qs", "qs_bpf", "qs_vol"}; fn f[] = {walk, qs, qs_bpf, qs_vol};
    long bad[4] = {0};
    for (long i = 0; i < n; i++) {
        bad[0] += walk_count(X + i * NF) != ref[i]; bad[1] += qs_count(X + i * NF) != ref[i];
        bad[2] += qs_bpf(X + i * NF) != ref[i]; bad[3] += qs_vol(X + i * NF) != ref[i];
    }
    static char out[8192]; int k = snprintf(out, sizeof out, "{\"rows\":%ld,\"rowrep\":%d,\"NT\":%d,\"W\":%d,\"NC\":%d,\"walk_steps\":%.2f,\"qs_updates\":%.2f",
                                         n, rowrep, NT, W, NC, (double)n_steps / n, (double)n_upd / n);
    volatile int sink = 0;
    for (int r = 0; r < 4; r++) {
        double t[64];
        for (int p = 0; p < reps; p++) { double t0 = now(); for (long i = 0; i < n; i++) for (int q = 0; q < rowrep; q++) sink += f[r](X + i * NF); t[p] = (now() - t0) / ((double)n * rowrep); }
        qsort(t, reps, sizeof(double), cmpd);
        struct pc pc; pc_open(&pc, 0); pc_start(&pc);
        for (long i = 0; i < n; i++) for (int q = 0; q < rowrep; q++) sink += f[r](X + i * NF);
        pc_stop(&pc);
        char pre[32]; snprintf(pre, sizeof pre, "%s_", name[r]);
        k += snprintf(out + k, sizeof out - k, ",\"%s_ns\":%.2f,\"%s_mismatch\":%ld", name[r], t[reps / 2], name[r], bad[r]);
        k += pc_json(out + k, sizeof out - k, pre, &pc, (double)n * rowrep);
        for (int i = 0; i < PC_N; i++) if (pc.fd[i] >= 0) close(pc.fd[i]);
    }
    printf("%s}\n", out);
    return 0;
}

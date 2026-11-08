/* RF-C: identical quantized RF in C userspace (experimental.md §2 RF-C, E1 step 4).
 *   cc -O2 -march=native -I<model dir> rfc.c -o rfc && ./rfc <X.i32> <ref_pred.u8> [reps]
 * Two runtimes over the same tables (codegen.py): tree walk (per-node arrays) and QuickScorer
 * (per-feature ascending thresholds, leaf bitvectors, exit leaf = lowest set bit). Both must agree
 * bit-exactly with the Python integer reference (ref_pred). Prints ns/inference (median of reps
 * passes over all rows, single thread). */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "model.h"
#include "tw.h"
#include "qs1.h"

static inline int argmax(const uint32_t *s) {
    int b = 0; for (int c = 1; c < NC; c++) if (s[c] > s[b]) b = c; return b;
}
static int walk(const int32_t *x) {
    uint32_t s[NC] = {0};
    for (int t = 0; t < NT; t++) {
        int n = tw_root[t];
        while (tw_feat[n] >= 0) n = x[tw_feat[n]] <= tw_thr[n] ? tw_left[n] : tw_right[n];
        for (int c = 0; c < NC; c++) s[c] += tw_leafq[n * NC + c];
    }
    return argmax(s);
}
static int qs(const int32_t *x) {
    static uint64_t v[NT * W];
    uint32_t s[NC] = {0};
    memset(v, 0xff, sizeof v);
    for (int f = 0; f < NF; f++) {
        int32_t xv = x[f];
        for (uint32_t i = qs_feat_off[f]; i < qs_feat_off[f + 1] && qs_thr[i] < xv; i++) {
            uint64_t *vt = v + qs_tree[i] * W; const uint64_t *m = (const uint64_t *)qs_mask + (size_t)i * W;
            for (int w = 0; w < W; w++) vt[w] &= m[w];
        }
    }
    for (int t = 0; t < NT; t++) {
        int leaf = 0;
        for (int w = 0; w < W; w++) if (v[t * W + w]) { leaf = w * 64 + __builtin_ctzll(v[t * W + w]); break; }
        const uint8_t *ls = leaf_score + (size_t)(leaf_off[t] + leaf) * NC;
        for (int c = 0; c < NC; c++) s[c] += ls[c];
    }
    return argmax(s);
}
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec * 1e9 + t.tv_nsec; }
static int cmpd(const void *a, const void *b) { double x = *(double *)a, y = *(double *)b; return (x > y) - (x < y); }

int main(int argc, char **argv) {
    FILE *fx = fopen(argv[1], "rb"), *fp = fopen(argv[2], "rb");
    int reps = argc > 3 ? atoi(argv[3]) : 5;
    fseek(fx, 0, SEEK_END); long n = ftell(fx) / (NF * 4); rewind(fx);
    int32_t *X = malloc(n * NF * 4); uint8_t *ref = malloc(n);
    if (fread(X, 4 * NF, n, fx) != (size_t)n || fread(ref, 1, n, fp) != (size_t)n) { fprintf(stderr, "short read\n"); return 1; }
    long bad_w = 0, bad_q = 0;
    for (long i = 0; i < n; i++) { bad_w += walk(X + i * NF) != ref[i]; bad_q += qs(X + i * NF) != ref[i]; }
    volatile int sink = 0;
    double tw[64], tq[64];
    if (reps > 64) reps = 64;
    for (int r = 0; r < reps; r++) {
        double t0 = now(); for (long i = 0; i < n; i++) sink += walk(X + i * NF);
        double t1 = now(); for (long i = 0; i < n; i++) sink += qs(X + i * NF);
        double t2 = now(); tw[r] = (t1 - t0) / n; tq[r] = (t2 - t1) / n;
    }
    qsort(tw, reps, sizeof(double), cmpd); qsort(tq, reps, sizeof(double), cmpd);
    printf("{\"rows\": %ld, \"walk_mismatch\": %ld, \"qs_mismatch\": %ld, \"walk_ns\": %.2f, \"qs_ns\": %.2f, "
           "\"walk_ns_min\": %.2f, \"qs_ns_min\": %.2f, \"NT\": %d, \"W\": %d, \"NC\": %d}\n",
           n, bad_w, bad_q, tw[reps / 2], tq[reps / 2], tw[0], tq[0], NT, W, NC);
    return (bad_w || bad_q) ? 3 : 0;
}

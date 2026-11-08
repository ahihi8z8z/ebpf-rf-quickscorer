/* NN-C: the quantized lightweight NN in C userspace (same integer semantics as train_e1.nn_int and
 * the eBPF nn_s* programs).  cc -O2 -march=native -I<dir> nnc.c -o nnc && ./nnc X.i32 ref.u8 [reps] */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "nnc.h"
static inline int64_t logq(int32_t x) {
    uint64_t v = (uint64_t)(x < 0 ? 0 : x) + 1; int e = 63 - __builtin_clzll(v);
    return 4 * e + (int64_t)(((v << 2) >> e) & 3);
}
static inline int64_t cl(int64_t h) { return h < 0 ? 0 : h > 127 ? 127 : h; }
static int nn(const int32_t *x) {
    int64_t a[NF], h[H1], k[H2], z[NC];
    for (int j = 0; j < NF; j++) a[j] = logq(x[j]);
    for (int o = 0; o < H1; o++) { int64_t s = B0[o]; for (int j = 0; j < NF; j++) s += (int64_t)W0[o * NF + j] * a[j]; h[o] = cl((s * M0[o]) >> 16); }
    for (int o = 0; o < H2; o++) { int64_t s = B1[o]; for (int j = 0; j < H1; j++) s += (int64_t)W1[o * H1 + j] * h[j]; k[o] = cl((s * M1[o]) >> 16); }
    int best = 0;
    for (int o = 0; o < NC; o++) { int64_t s = B2[o]; for (int j = 0; j < H2; j++) s += (int64_t)W2[o * H2 + j] * k[j]; z[o] = (s * M2[o]) >> 16; if (z[o] > z[best]) best = o; }
    return best;
}
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec * 1e9 + t.tv_nsec; }
static int cmpd(const void *a, const void *b) { double x = *(double *)a, y = *(double *)b; return (x > y) - (x < y); }
int main(int argc, char **argv) {
    FILE *fx = fopen(argv[1], "rb"), *fp = fopen(argv[2], "rb"); int reps = argc > 3 ? atoi(argv[3]) : 5;
    fseek(fx, 0, SEEK_END); long n = ftell(fx) / (NF * 4); rewind(fx);
    int32_t *X = malloc(n * NF * 4); uint8_t *ref = malloc(n);
    if (fread(X, 4 * NF, n, fx) != (size_t)n || fread(ref, 1, n, fp) != (size_t)n) return 1;
    long bad = 0; for (long i = 0; i < n; i++) bad += nn(X + i * NF) != ref[i];
    volatile int sink = 0; double t[64]; if (reps > 64) reps = 64;
    for (int r = 0; r < reps; r++) { double t0 = now(); for (long i = 0; i < n; i++) sink += nn(X + i * NF); t[r] = (now() - t0) / n; }
    qsort(t, reps, sizeof(double), cmpd);
    printf("{\"rows\": %ld, \"nn_mismatch\": %ld, \"nn_ns\": %.2f, \"nn_ns_min\": %.2f}\n", n, bad, t[reps / 2], t[0]);
    return bad ? 3 : 0;
}

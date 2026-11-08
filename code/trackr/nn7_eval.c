/* Run Hara's AF_XDP 7-class MLP (xsknf/examples/nn, unmodified C) on hara_ref --dump-feat rows.
 *   nn7_eval <in.feat> <in.cls (hara_ref, marks unparsed rows)> <out.nn7> [--normalize]
 * mlids_user.c passes the raw Q16 feature vector to run_mlp() (no data_min/data_scale step);
 * --normalize applies the in-kernel binary model's normaliser (nn-filter/data.c) first, as a
 * charitable variant. Output: 1 byte per record, class index 0..6, 255 = not classified. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "mlp.h"
static const int64_t data_min[12] = {0, 0, 65536, 524288, 0, 0, 524288, 0, 4096, 0, 0, 0};
static const int64_t data_scale[12] = {1, 1, 1149, 2, 0, 65536, 11, 0, 69905, 20, 0, 135039};
int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "usage\n"); return 2; }
    int norm = argc > 4 && !strcmp(argv[4], "--normalize");
    FILE *ff = fopen(argv[1], "rb"), *fc = fopen(argv[2], "rb"), *fo = fopen(argv[3], "wb");
    if (!ff || !fc || !fo) { perror("open"); return 1; }
    int64_t x[12]; uint8_t c[2]; unsigned long long n = 0, hist[8] = {0};
    while (fread(x, sizeof x, 1, ff) == 1 && fread(c, 2, 1, fc) == 1) {
        uint8_t o = 255;
        if (c[0] != 255 || c[1] != 255) {
            if (norm) for (int k = 0; k < 12; k++) x[k] = ((x[k] - data_min[k]) * data_scale[k]) >> 16;
            unsigned int idx[1];
            run_mlp(x, 1, idx);
            o = (uint8_t)idx[0]; hist[o < 7 ? o : 7]++;
        }
        fputc(o, fo); n++;
    }
    fclose(fo);
    fprintf(stderr, "records=%llu hist=", n);
    for (int i = 0; i < 8; i++) fprintf(stderr, "%llu%c", hist[i], i < 7 ? ',' : '\n');
    return 0;
}

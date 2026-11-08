/* Validate the E5 XDP frontend (built with -DFRONTEND -DFE_TEST_TS) against flowfeat and the model
 * reference: replay a classic pcap through BPF_PROG_TEST_RUN with the capture clock, collect the
 * ring-buffer events (features + class) and write them as records for fe_compare.py.
 *   sudo ./fe_check <obj> <in.pcap> <out.events> [max_packets] */
#define _GNU_SOURCE
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct ev { uint64_t ts_first_us; uint32_t ini_ip, resp_ip; uint16_t ini_port, resp_port; uint8_t proto, cls, pad[2]; int32_t f[17]; uint32_t pad2; };
static FILE *fo; static long nev;
static int on_ev(void *ctx, void *d, size_t sz) { (void)ctx; if (sz >= sizeof(struct ev)) { fwrite(d, sizeof(struct ev), 1, fo); nev++; } return 0; }
int main(int argc, char **argv) {
    long maxp = argc > 4 ? atol(argv[4]) : 1L << 60;
    struct bpf_object *obj = bpf_object__open_file(argv[1], NULL);
    if (!obj || bpf_object__load(obj)) { fprintf(stderr, "load failed\n"); return 1; }
    int jmp = bpf_object__find_map_fd_by_name(obj, "jmp"), k = 0, fe = -1; struct bpf_program *p;
    bpf_object__for_each_program(p, obj) {
        int fd = bpf_program__fd(p);
        if (k == 0) fe = fd; else { uint32_t key = k; bpf_map_update_elem(jmp, &key, &fd, BPF_ANY); }
        k++;
    }
    int nowfd = bpf_object__find_map_fd_by_name(obj, "fe_now");
    struct ring_buffer *rb = ring_buffer__new(bpf_object__find_map_fd_by_name(obj, "fe_events"), on_ev, NULL, NULL);
    fo = fopen(argv[3], "wb");
    FILE *f = fopen(argv[2], "rb"); uint32_t gh[6];
    if (fread(gh, 4, 6, f) != 6) return 1;
    int ns = gh[0] == 0xa1b23c4d;
    uint32_t h[4]; static uint8_t buf[65536]; long np = 0;
    while (np < maxp && fread(h, 4, 4, f) == 4) {
        if (h[2] > sizeof buf || fread(buf, 1, h[2], f) != h[2]) break;
        uint64_t ts = (uint64_t)h[0] * 1000000 + (ns ? h[1] / 1000 : h[1]); uint32_t z = 0;
        bpf_map_update_elem(nowfd, &z, &ts, BPF_ANY);
        uint32_t len = h[2] < 14 ? 14 : h[2];
        LIBBPF_OPTS(bpf_test_run_opts, o, .data_in = buf, .data_size_in = len, .repeat = 1);
        bpf_prog_test_run_opts(fe, &o);
        if (++np % 4096 == 0) ring_buffer__consume(rb);
    }
    ring_buffer__consume(rb);
    int cnt = bpf_object__find_map_fd_by_name(obj, "fe_cnt"); int ncpu = libbpf_num_possible_cpus();
    uint64_t v[256], tot[16] = {0};
    for (uint32_t i = 0; i < 16; i++) { if (!bpf_map_lookup_elem(cnt, &i, v)) for (int c = 0; c < ncpu; c++) tot[i] += v[c]; }
    printf("{\"packets\":%ld,\"events\":%ld,\"cnt_pkts\":%lu,\"non_ipv4\":%lu,\"triggers\":%lu,\"unavailable\":%lu,\"ev_dropped\":%lu,\"new_flows\":%lu}\n",
           np, nev, tot[0], tot[1], tot[2], tot[3], tot[4], tot[5]);
    fclose(fo); return 0;
}

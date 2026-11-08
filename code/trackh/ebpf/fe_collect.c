/* E5 collector on the DUT: attach a frontend+model object (built with -DFRONTEND [-DFE_EVENT_FEAT])
 * to an interface in native XDP mode, fill the tail-call table, drain ring-buffer events to a file
 * until SIGINT/SIGTERM or <seconds>, then detach and print counters and softirq CPU time.
 *   sudo ./fe_collect <obj> <ifname> <events.out> <seconds> [evsize] */
#define _GNU_SOURCE
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <linux/if_link.h>
#include <net/if.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
static volatile int stop; static FILE *fo; static long nev; static size_t evsz;
static void onsig(int s) { (void)s; stop = 1; }
static int on_ev(void *c, void *d, size_t sz) { (void)c; fwrite(d, sz < evsz ? sz : evsz, 1, fo); nev++; return 0; }
static void cpu_ticks(unsigned long long *busy, unsigned long long *soft) {
    FILE *f = fopen("/proc/stat", "r"); char l[512]; *busy = *soft = 0;
    if (f && fgets(l, sizeof l, f)) {
        unsigned long long u, n, s, i, w, irq, si; sscanf(l, "cpu %llu %llu %llu %llu %llu %llu %llu", &u, &n, &s, &i, &w, &irq, &si);
        *busy = u + n + s + irq + si; *soft = si;
    }
    if (f) fclose(f);
}
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
int main(int argc, char **argv) {
    if (argc < 5) { fprintf(stderr, "usage\n"); return 2; }
    evsz = argc > 5 ? atoi(argv[5]) : 24;
    int ifindex = if_nametoindex(argv[2]); double secs = atof(argv[4]);
    struct bpf_object *obj = bpf_object__open_file(argv[1], NULL);
    if (!obj || bpf_object__load(obj)) { fprintf(stderr, "load failed\n"); return 1; }
    int jmp = bpf_object__find_map_fd_by_name(obj, "jmp"), k = 0, fe = -1; struct bpf_program *p;
    bpf_object__for_each_program(p, obj) {
        int fd = bpf_program__fd(p);
        if (k == 0) fe = fd; else { uint32_t key = k; bpf_map_update_elem(jmp, &key, &fd, BPF_ANY); }
        k++;
    }
    LIBBPF_OPTS(bpf_xdp_attach_opts, ao);
    if (bpf_xdp_attach(ifindex, fe, XDP_FLAGS_DRV_MODE, &ao)) { fprintf(stderr, "attach (native) failed\n"); return 1; }
    signal(SIGINT, onsig); signal(SIGTERM, onsig);
    fo = fopen(argv[3], "wb");
    struct ring_buffer *rb = ring_buffer__new(bpf_object__find_map_fd_by_name(obj, "fe_events"), on_ev, NULL, NULL);
    unsigned long long b0, s0, b1, s1; cpu_ticks(&b0, &s0); double t0 = now();
    printf("READY\n"); fflush(stdout);
    while (!stop && now() - t0 < secs) ring_buffer__poll(rb, 100);
    double t1 = now(); cpu_ticks(&b1, &s1);
    bpf_xdp_detach(ifindex, XDP_FLAGS_DRV_MODE, &ao);
    ring_buffer__consume(rb); fclose(fo);
    int cnt = bpf_object__find_map_fd_by_name(obj, "fe_cnt"); int ncpu = libbpf_num_possible_cpus();
    uint64_t v[256], tot[48] = {0};
    for (uint32_t i = 0; i < 48; i++) if (!bpf_map_lookup_elem(cnt, &i, v)) for (int c = 0; c < ncpu; c++) tot[i] += v[c];
    long hz = sysconf(_SC_CLK_TCK);
    printf("{\"seconds\":%.3f,\"events\":%ld,\"packets\":%lu,\"non_ipv4\":%lu,\"triggers\":%lu,\"unavailable\":%lu,"
           "\"ev_dropped\":%lu,\"new_flows\":%lu,\"cpu_busy_s\":%.2f,\"cpu_softirq_s\":%.2f,\"class_counts\":[",
           t1 - t0, nev, tot[0], tot[1], tot[2], tot[3], tot[4], tot[5], (double)(b1 - b0) / hz, (double)(s1 - s0) / hz);
    for (int c = 0; c < 16; c++) printf("%s%lu", c ? "," : "", tot[8 + c]);
    printf("]}\n");
    return 0;
}

/* Track-H feature extractor (frozen schema v1, see dataset_protocol.md).
 *   flowfeat [--n N] [--timeout-s S] <out_prefix> <in.pcap|pcapng> [more captures, in time order ...]
 * Flow = bidirectional IPv4 5-tuple (TCP/UDP ports; 0 for ICMP, other protocols and non-first
 * fragments). Initiator = source of the flow's first packet. A flow ends after S seconds without a
 * packet (default 120); the next packet starts a new flow. At the flow's N-th packet (default 8) the
 * feature vector of packets 1..N is emitted (the inference trigger); the flow is then only counted.
 * Every feature is an integer computable in XDP from O(1) per-flow state:
 *   f0 proto            f1 resp_port (dst port of packet 1)   f2 n_fwd (initiator->responder)
 *   f3 bytes_fwd        f4 bytes_bwd (IP total length)        f5 len_first
 *   f6 len_min          f7 len_max                            f8 dur_us (t_N - t_1)
 *   f9 iat_min_us       f10 iat_max_us                        f11 n_syn  f12 n_fin  f13 n_rst
 *   f14 n_psh           f15 n_ack                             f16 n_dirchg (direction switches)
 * Times are integer microseconds (XDP: bpf_ktime_get_ns() / 1000); durations saturate at 2^31-1.
 * Outputs: <prefix>.trig (one record per triggered flow), <prefix>.flows (one record per flow, at
 * its end, triggered or not, for coverage), <prefix>.stats.json. */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
typedef uint64_t u64; typedef uint32_t u32; typedef uint16_t u16; typedef uint8_t u8;

#define NF 17
#define SAT(x) ((x) > 0x7fffffffLL ? 0x7fffffff : (int32_t)(x))

struct key { u32 a, b; u16 pa, pb; u8 proto; };            /* canonical: (a,pa) <= (b,pb) */
struct flow {
    struct key k; struct flow *hnext, *prev, *next;
    u64 t_first, t_last; u32 ini_ip; u16 ini_port, resp_port; u32 npkts, id;
    int32_t f[NF]; u8 last_dir, triggered;
};
struct trig_rec {   /* 112 bytes */
    u64 ts_first_us, ts_trig_us; u32 ini_ip, resp_ip; u16 ini_port, resp_port; u8 proto, pad[3];
    u32 flow_id; int32_t f[NF]; u32 pad2[2];
};
struct flow_rec {   /* 40 bytes */
    u64 ts_first_us, ts_last_us; u32 ini_ip, resp_ip; u16 ini_port, resp_port; u8 proto, triggered;
    u16 pad; u32 npkts, flow_id;
};

_Static_assert(sizeof(struct trig_rec) == 112, "trig_rec layout");
_Static_assert(sizeof(struct flow_rec) == 40, "flow_rec layout");
static u32 N = 8; static u64 TIMEOUT = 120000000ull;
#define NB (1u << 24)
static struct flow **bucket, *head, *tail, *freel;
static u64 n_live, n_flows, n_trig, n_pkt, n_ipv4, n_nonip, n_short, n_frag;
static FILE *ftrig, *fflow;

static u32 kh(const struct key *k) {
    u64 h = ((u64)k->a * 0x9E3779B97F4A7C15ull) ^ ((u64)k->b * 0xC2B2AE3D27D4EB4Full) ^
            ((u64)k->pa << 32 | (u64)k->pb << 8 | k->proto) * 0x165667B19E3779F9ull;
    return (u32)(h >> 40) & (NB - 1);
}
static int keq(const struct key *x, const struct key *y) {
    return x->a == y->a && x->b == y->b && x->pa == y->pa && x->pb == y->pb && x->proto == y->proto;
}
static void unlink_l(struct flow *f) {
    if (f->prev) f->prev->next = f->next; else head = f->next;
    if (f->next) f->next->prev = f->prev; else tail = f->prev;
}
static void push_tail(struct flow *f) {
    f->prev = tail; f->next = NULL; if (tail) tail->next = f; else head = f; tail = f;
}
static void finish(struct flow *f) {
    struct flow_rec r = {f->t_first, f->t_last, f->ini_ip, f->ini_ip == f->k.a && f->ini_port == f->k.pa ? f->k.b : f->k.a,
                         f->ini_port, f->resp_port, f->k.proto, f->triggered, 0, f->npkts, f->id};
    fwrite(&r, sizeof r, 1, fflow);
    struct flow **pp = &bucket[kh(&f->k)];
    while (*pp != f) pp = &(*pp)->hnext;
    *pp = f->hnext; unlink_l(f); f->hnext = freel; freel = f; n_live--;
}
static void expire(u64 now) { while (head && now - head->t_last > TIMEOUT) finish(head); }

static void packet(u64 t, u32 src, u32 dst, u16 sp, u16 dp, u8 proto, u16 iplen, u8 tcpfl) {
    expire(t);
    struct key k;
    if (src < dst || (src == dst && sp <= dp)) k = (struct key){src, dst, sp, dp, proto};
    else k = (struct key){dst, src, dp, sp, proto};
    u32 h = kh(&k); struct flow *f = bucket[h];
    while (f && !keq(&f->k, &k)) f = f->hnext;
    if (!f) {
        if (freel) { f = freel; freel = f->hnext; } else f = malloc(sizeof *f);
        memset(f, 0, sizeof *f); f->k = k; f->hnext = bucket[h]; bucket[h] = f; n_live++;
        f->t_first = t; f->ini_ip = src; f->ini_port = sp; f->resp_port = dp; f->id = (u32)n_flows++;
        f->f[0] = proto; f->f[1] = dp; f->f[5] = iplen; f->f[6] = iplen; f->f[7] = iplen;
        f->f[9] = 0x7fffffff;
    } else unlink_l(f);
    push_tail(f);
    u8 dir = !(src == f->ini_ip && sp == f->ini_port);     /* 0 = from initiator */
    if (f->npkts && src == dst && sp == dp) dir = 0;        /* degenerate self-flow */
    if (f->npkts < N) {
        if (dir == 0) { f->f[2]++; f->f[3] += iplen; } else f->f[4] += iplen;
        if (iplen < f->f[6]) f->f[6] = iplen;
        if (iplen > f->f[7]) f->f[7] = iplen;
        if (f->npkts) {
            int64_t iat = (int64_t)(t - f->t_last);
            if (iat < f->f[9]) f->f[9] = SAT(iat);
            if (iat > f->f[10]) f->f[10] = SAT(iat);
            if (dir != f->last_dir) f->f[16]++;
        }
        f->f[11] += !!(tcpfl & 0x02); f->f[12] += !!(tcpfl & 0x01); f->f[13] += !!(tcpfl & 0x04);
        f->f[14] += !!(tcpfl & 0x08); f->f[15] += !!(tcpfl & 0x10);
        f->f[8] = SAT((int64_t)(t - f->t_first));
    }
    f->npkts++; f->t_last = t; f->last_dir = dir;
    if (f->npkts == N) {
        struct trig_rec r; memset(&r, 0, sizeof r);
        r.ts_first_us = f->t_first; r.ts_trig_us = t; r.ini_ip = f->ini_ip;
        r.resp_ip = f->ini_ip == k.a && f->ini_port == k.pa ? k.b : k.a;
        r.ini_port = f->ini_port; r.resp_port = f->resp_port; r.proto = proto; r.flow_id = f->id;
        memcpy(r.f, f->f, sizeof r.f);
        if (N == 1) r.f[9] = 0;
        fwrite(&r, sizeof r, 1, ftrig); f->triggered = 1; n_trig++;
    }
}

/* ---- capture reader: little-endian pcap (ns/us; DLT 1 Ethernet, 113 SLL, 101/12 raw IPv4) and
 * pcapng (SHB/IDB/EPB, if_tsresol). */
static const u8 *M; static size_t OFF, END; static int NG, LT; static u64 MUL;
static u64 ng_div[64]; static int ng_lt[64], ng_nif, cur_lt;
static int open_capture(void) {
    u32 magic = *(const u32 *)M;
    if (magic == 0xa1b2c3d4 || magic == 0xa1b23c4d) {
        MUL = magic == 0xa1b2c3d4 ? 1000 : 1; NG = 0; OFF = 24; LT = *(const u32 *)(M + 20); return 0;
    }
    if (magic == 0x0a0d0d0a && *(const u32 *)(M + 8) == 0x1a2b3c4d) { NG = 1; OFF = 0; ng_nif = 0; return 0; }
    fprintf(stderr, "unsupported capture magic %08x\n", magic); return -1;
}
static int next_pkt(u64 *ts_ns, const u8 **data, size_t *caplen) {
    if (!NG) {
        if (OFF + 16 > END) return 0;
        const u32 *h = (const u32 *)(M + OFF);
        *ts_ns = (u64)h[0] * 1000000000ull + (u64)h[1] * MUL;
        *caplen = h[2]; *data = M + OFF + 16; OFF += 16 + h[2]; cur_lt = LT;
        return OFF <= END;
    }
    while (OFF + 12 <= END) {
        u32 type = *(const u32 *)(M + OFF), len = *(const u32 *)(M + OFF + 4);
        const u8 *b = M + OFF;
        if (len < 12 || OFF + len > END) return 0;
        OFF += len;
        if (type == 0x0a0d0d0a) { ng_nif = 0; continue; }
        if (type == 1) {
            u64 div = 1000;
            for (size_t o = 16; o + 4 <= len - 4;) {
                u16 code = *(const u16 *)(b + o), olen = *(const u16 *)(b + o + 2);
                if (!code) break;
                if (code == 9 && olen >= 1) {
                    u8 r = b[o + 4]; u64 per = 1;
                    if (r & 0x80) { fprintf(stderr, "binary tsresol unsupported\n"); exit(1); }
                    for (int i = 0; i < r; i++) per *= 10;
                    div = per >= 1000000000ull ? 1 : 1000000000ull / per;
                }
                o += 4 + ((olen + 3) & ~3u);
            }
            if (ng_nif < 64) { ng_lt[ng_nif] = *(const u16 *)(b + 8); ng_div[ng_nif++] = div; }
            continue;
        }
        if (type == 6) {
            u32 ifid = *(const u32 *)(b + 8);
            u64 t = (u64)*(const u32 *)(b + 12) << 32 | *(const u32 *)(b + 16);
            *ts_ns = t * (ifid < 64 ? ng_div[ifid] : 1000); cur_lt = ifid < 64 ? ng_lt[ifid] : 1;
            *caplen = *(const u32 *)(b + 20); *data = b + 28;
            return 1;
        }
    }
    return 0;
}

static void parse(u64 ts_ns, const u8 *d, size_t cl) {
    n_pkt++;
    size_t o; u16 et;
    if (cur_lt == 1) {
        if (cl < 14) goto nonip;
        et = d[12] << 8 | d[13]; o = 14;
        while ((et == 0x8100 || et == 0x88a8) && cl >= o + 4) { et = d[o + 2] << 8 | d[o + 3]; o += 4; }
    } else if (cur_lt == 113) {
        if (cl < 16) goto nonip;
        et = d[14] << 8 | d[15]; o = 16;
    } else if (cur_lt == 101 || cur_lt == 12 || cur_lt == 228) { et = 0x0800; o = 0; }
    else goto nonip;
    if (et != 0x0800 || cl < o + 20 || (d[o] >> 4) != 4) goto nonip;
    const u8 *ip = d + o; u32 ihl = (ip[0] & 15) * 4;
    if (ihl < 20) goto nonip;
    n_ipv4++;
    u16 iplen = ip[2] << 8 | ip[3]; u8 proto = ip[9];
    u32 src, dst; memcpy(&src, ip + 12, 4); memcpy(&dst, ip + 16, 4);   /* network byte order */
    u16 frag = (ip[6] << 8 | ip[7]) & 0x1fff;
    u16 sp = 0, dp = 0; u8 fl = 0;
    if (frag) n_frag++;
    else if ((proto == 6 || proto == 17) && cl >= o + ihl + 4) {
        sp = ip[ihl] << 8 | ip[ihl + 1]; dp = ip[ihl + 2] << 8 | ip[ihl + 3];
        if (proto == 6 && cl >= o + ihl + 14) fl = ip[ihl + 13];
    }
    packet(ts_ns / 1000, src, dst, sp, dp, proto, iplen, fl);
    return;
nonip:
    n_nonip++;
}

int main(int argc, char **argv) {
    int i = 1;
    for (; i < argc && argv[i][0] == '-' && argv[i][1] == '-'; i += 2) {
        if (!strcmp(argv[i], "--n")) N = atoi(argv[i + 1]);
        else if (!strcmp(argv[i], "--timeout-s")) TIMEOUT = strtoull(argv[i + 1], 0, 10) * 1000000ull;
        else { fprintf(stderr, "bad option %s\n", argv[i]); return 2; }
    }
    if (argc - i < 2) { fprintf(stderr, "usage: flowfeat [--n N] [--timeout-s S] out_prefix capture...\n"); return 2; }
    const char *pre = argv[i++];
    char p[4096];
    snprintf(p, sizeof p, "%s.trig", pre); ftrig = fopen(p, "wb");
    snprintf(p, sizeof p, "%s.flows", pre); fflow = fopen(p, "wb");
    if (!ftrig || !fflow) { perror("open out"); return 1; }
    bucket = calloc(NB, sizeof *bucket);
    u64 last_ts = 0, n_backwards = 0;
    for (; i < argc; i++) {
        int fd = open(argv[i], O_RDONLY); struct stat st;
        if (fd < 0 || fstat(fd, &st)) { perror(argv[i]); return 1; }
        /* large sequential reads instead of mmap page faults: far fewer seeks on a shared HDD */
        END = st.st_size;
        uint8_t *buf = malloc(END ? END : 1);
        if (!buf) { perror("malloc"); return 1; }
        for (size_t got = 0; got < END;) {
            ssize_t r = read(fd, buf + got, END - got > (64u << 20) ? (64u << 20) : END - got);
            if (r <= 0) { perror("read"); return 1; }
            got += r;
        }
        M = buf;
        if (open_capture()) return 1;
        u64 ts; const u8 *d; size_t cl;
        while (next_pkt(&ts, &d, &cl)) {
            /* captures are processed in arrival order; a slightly earlier timestamp (capture
             * reordering) is clamped so that per-flow times never go backwards */
            if (ts < last_ts) { n_backwards++; ts = last_ts; }
            last_ts = ts;
            parse(ts, d, cl);
        }
        free((void *)M); close(fd);
        fprintf(stderr, "%s done: pkts=%llu flows=%llu trig=%llu live=%llu\n", argv[i],
                (unsigned long long)n_pkt, (unsigned long long)n_flows, (unsigned long long)n_trig,
                (unsigned long long)n_live);
    }
    while (head) { if (!head->triggered) n_short++; finish(head); }
    fclose(ftrig); fclose(fflow);
    snprintf(p, sizeof p, "%s.stats.json", pre);
    FILE *s = fopen(p, "w");
    fprintf(s, "{\"n\": %u, \"timeout_us\": %llu, \"packets\": %llu, \"ipv4\": %llu, \"non_ipv4\": %llu, "
               "\"ipv4_nonfirst_fragments\": %llu, \"flows\": %llu, \"triggered\": %llu, "
               "\"ts_clamped_backwards\": %llu}\n", N, (unsigned long long)TIMEOUT,
            (unsigned long long)n_pkt, (unsigned long long)n_ipv4, (unsigned long long)n_nonip,
            (unsigned long long)n_frag, (unsigned long long)n_flows, (unsigned long long)n_trig,
            (unsigned long long)n_backwards);
    fclose(s);
    return 0;
}

/* Offline reference of Hara's in-kernel XDP DT and NN (oakeshott/ebpf-classifier @d2466660).
 *
 * The per-packet parsing, session state, feature arithmetic, DT walk and NN fixed-point code
 * are transcribed from dt-filter/dt_filter_xdp.py and nn-filter/nn_filter_xdp.py with the
 * same C integer types; build with -fwrapv so signed wrap matches BPF two's-complement ALU.
 * Validated packet-by-packet against BPF_PROG_TEST_RUN of the real programs (e0/sequence).
 *
 * usage: hara_ref <in.pcap|in.pcapng> <out_prefix> [--key dir|bidir] [--iat-div D] [--lru N]
 *   --key dir    kernel behaviour: directional 5-tuple session key (direction feature == 1)
 *   --key bidir  paper-intended: one session per bidirectional 5-tuple; direction = packet
 *                sport equals the session's first-packet sport (same expression as the kernel)
 *   --iat-div D  IAT feature = (ts - last_ts) / D  (kernel: ns, D=1; D=1000 -> us)
 *   --dump-feat  also write <prefix>.feat: 12 x int64 DT features (Q16) per pcap record (zeros if unparsed)
 *   --lru N      exact LRU session table of N entries (kernel map size is 1024; 0 = unbounded)
 * outputs: <prefix>.cls  2 bytes per pcap record: dt class, nn class (255 = not classified)
 *          <prefix>.meta 32 bytes per pcap record (struct meta, incl. tail padding): u64 ts_us, u32 saddr, u32 daddr (network
 *                        order), u16 sport, u16 dport, u8 proto, u8 parsed, u16 ip_len, u32 pad
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include "params.h"

#define MAX(a,b) (((a)>(b))?(a):(b))
#define INT8_MAX_VALUE 127
#define FXP_VALUE 16
#define ROUND_CONST (1 << (FXP_VALUE - 1))
#define INPUT_DIM 12
#define H1 16
#define H2 16
#define OUTPUT_DIM 2
#define TREE_LEAF -1
#define TREE_UNDEFINED -2
#define MAX_TREE_DEPTH 20
#define NUM_FEATURES 12

typedef uint32_t u32; typedef uint64_t u64;

struct pkt_key_t { u32 protocol, saddr, daddr, sport, dport; };
struct nn_leaf_t { u32 num_packets; u64 last_packet_timestamp; u32 sport, dport; u64 features[6]; };
struct dt_leaf_t { u64 num_packets, last_packet_timestamp, saddr, daddr, sport, dport; u64 features[6]; };

struct ent {
    struct pkt_key_t k; struct nn_leaf_t nn; struct dt_leaf_t dt;
    struct ent *hnext, *prev, *next;
};
#define NBUCKET (1u << 22)
static struct ent *bucket[NBUCKET];
static struct ent *lru_head, *lru_tail;
static u64 n_ent, cap_ent, n_evict;

static u32 khash(const struct pkt_key_t *k) {
    u64 h = 1469598103934665603ull;
    const u32 *w = (const u32 *)k;
    for (int i = 0; i < 5; i++) { h ^= w[i]; h *= 1099511628211ull; }
    return (u32)(h ^ (h >> 29)) & (NBUCKET - 1);
}
static void lru_unlink(struct ent *e) {
    if (e->prev) e->prev->next = e->next; else lru_head = e->next;
    if (e->next) e->next->prev = e->prev; else lru_tail = e->prev;
}
static void lru_front(struct ent *e) {
    e->prev = NULL; e->next = lru_head;
    if (lru_head) lru_head->prev = e; else lru_tail = e;
    lru_head = e;
}
static struct ent *lookup(const struct pkt_key_t *k) {
    for (struct ent *e = bucket[khash(k)]; e; e = e->hnext)
        if (!memcmp(&e->k, k, sizeof *k)) {
            if (cap_ent) { lru_unlink(e); lru_front(e); }
            return e;
        }
    return NULL;
}
static void evict_tail(void) {
    struct ent *e = lru_tail, **pp = &bucket[khash(&e->k)];
    while (*pp != e) pp = &(*pp)->hnext;
    *pp = e->hnext;
    lru_unlink(e); free(e); n_ent--; n_evict++;
}
static struct ent *insert(const struct pkt_key_t *k) {
    if (cap_ent && n_ent >= cap_ent) evict_tail();
    struct ent *e = calloc(1, sizeof *e);
    if (!e) { perror("calloc"); exit(1); }
    e->k = *k; u32 h = khash(k); e->hnext = bucket[h]; bucket[h] = e;
    lru_front(e); n_ent++;
    return e;
}

static FILE *ffeat;      /* --dump-feat: 12 x int64 DT feature vector (Q16) per pcap record */
static u64 wrap_cnt[3];   /* packets whose quantized activation left [-127,127] before the int8 cast */

/* quantize() as written in the kernel (identical code in nn_xdp_drop_packet, nn1, nn2) */
static void quantize(const int64_t *x, int8_t *x_q, int n, int s_x, int s_x_inv, int layer) {
    int rounded_value, tensor_int, tensor_frac, scale_factor_int, scale_factor_frac;
    int wrapped = 0;
    scale_factor_int = (s_x + ROUND_CONST) >> FXP_VALUE;
    scale_factor_frac = s_x - (scale_factor_int << FXP_VALUE);
    for (int m = 0; m < n; m++) {
        tensor_int = (x[m] + ROUND_CONST) >> FXP_VALUE;
        if (tensor_int > INT8_MAX_VALUE*s_x_inv) {
            x_q[m] = (int8_t)INT8_MAX_VALUE;
        } else if (tensor_int < -INT8_MAX_VALUE*s_x_inv) {
            x_q[m] = -(int8_t)INT8_MAX_VALUE;
        } else {
            tensor_frac = x[m] - (tensor_int << FXP_VALUE);
            rounded_value = tensor_int*scale_factor_frac + scale_factor_int*tensor_frac;
            rounded_value += (tensor_frac*scale_factor_frac + ROUND_CONST) >> FXP_VALUE;
            rounded_value = ((rounded_value + ROUND_CONST) >> FXP_VALUE) + tensor_int*scale_factor_int;
            if (rounded_value > 127 || rounded_value < -128) wrapped = 1;
            x_q[m] = (int8_t)rounded_value;
        }
    }
    wrap_cnt[layer] += wrapped;
}

/* mat_mult + dequantize_per_row (+ relu if relu) as in the kernel */
static void linear(const int8_t *x_q, int nin, int nout, const int *w, const int *s_w_inv,
                   int s_x_inv, int relu, int64_t *y) {
    for (int m = 0; m < nout; m++) {
        int accumulator = 0, out_value;
        for (int k = 0; k < nin; k++) {
            int8_t weight = (int8_t)(w[k*nout + m] & 0xff);  /* *(int8_t*) of an int map value */
            accumulator += x_q[k] * weight;
        }
        out_value = s_w_inv[m];
        out_value *= s_x_inv;
        int64_t out = (int64_t)accumulator;
        if (out_value > (1 << FXP_VALUE)) out *= ((out_value + ROUND_CONST) >> FXP_VALUE);
        else out = (out_value*out + ROUND_CONST) >> FXP_VALUE;
        if (relu) out = MAX(out, 0);
        y[m] = out;
    }
}

static int nn_classify(struct nn_leaf_t *pkt_leaf, const struct pkt_key_t *pkt_key, int64_t ts,
                       u32 protocol, u32 tot_len, int64_t iat_div) {
    int64_t x[INPUT_DIM] = {0};
    pkt_leaf->num_packets += 1;
    x[0] = pkt_leaf->sport;
    x[1] = pkt_leaf->dport;
    x[2] = protocol;
    x[3] = tot_len;
    x[4] = 0;
    if (pkt_leaf->last_packet_timestamp > 0) x[4] = (ts - pkt_leaf->last_packet_timestamp) / iat_div;
    pkt_leaf->last_packet_timestamp = ts;
    x[5] = pkt_key->sport == x[0];
    for (int i = 0; i < 6; i++) x[i] <<= FXP_VALUE;
    pkt_leaf->features[0] += x[3];
    pkt_leaf->features[1] += x[4];
    pkt_leaf->features[2] += x[5];
    x[6] = pkt_leaf->features[0]/pkt_leaf->num_packets;
    x[7] = pkt_leaf->features[1]/pkt_leaf->num_packets;
    x[8] = pkt_leaf->features[2]/pkt_leaf->num_packets;
    pkt_leaf->features[3] += llabs(x[3] - x[6]);
    pkt_leaf->features[4] += llabs(x[4] - x[7]);
    pkt_leaf->features[5] += llabs(x[5] - x[8]);
    x[9]  = pkt_leaf->features[3]/pkt_leaf->num_packets;
    x[10] = pkt_leaf->features[4]/pkt_leaf->num_packets;
    x[11] = pkt_leaf->features[5]/pkt_leaf->num_packets;
    for (int k = 0; k < INPUT_DIM; k++)
        x[k] = ((x[k] - P_data_min[k]) * P_data_scale[k]) >> FXP_VALUE;

    int8_t q0[INPUT_DIM], q1[H1], q2[H2];
    int64_t h1[H1], h2[H2], o[OUTPUT_DIM];
    quantize(x, q0, INPUT_DIM, P_layer_1_s_x[0], P_layer_1_s_x_inv[0], 0);
    linear(q0, INPUT_DIM, H1, P_layer_1_weight, P_layer_1_s_w_inv, P_layer_1_s_x_inv[0], 1, h1);
    quantize(h1, q1, H1, P_layer_2_s_x[0], P_layer_2_s_x_inv[0], 1);
    linear(q1, H1, H2, P_layer_2_weight, P_layer_2_s_w_inv, P_layer_2_s_x_inv[0], 1, h2);
    quantize(h2, q2, H2, P_layer_3_s_x[0], P_layer_3_s_x_inv[0], 2);
    linear(q2, H2, OUTPUT_DIM, P_layer_3_weight, P_layer_3_s_w_inv, P_layer_3_s_x_inv[0], 0, o);
    unsigned int argmax_over_cols = 0;
    int rounded_value = 0;                 /* int in the kernel: out is truncated on assignment */
    for (int m = 0; m < OUTPUT_DIM; m++)
        if (o[m] > rounded_value) { rounded_value = o[m]; argmax_over_cols = m; }
    return argmax_over_cols;
}

static int dt_classify(struct dt_leaf_t *pkt_leaf, const struct pkt_key_t *pkt_key, int64_t ts,
                       u32 proto, u32 len, int64_t iat_div) {
    pkt_leaf->num_packets += 1;
    int64_t sport = pkt_leaf->sport;
    int64_t dport = pkt_leaf->dport;
    int64_t protocol = proto;
    int64_t tot_len = len;
    int64_t interval_time = 0;
    if (pkt_leaf->last_packet_timestamp > 0) interval_time = (ts - pkt_leaf->last_packet_timestamp) / iat_div;
    pkt_leaf->last_packet_timestamp = ts;
    int64_t direction = pkt_key->sport == sport;
    sport <<= FXP_VALUE; dport <<= FXP_VALUE; protocol <<= FXP_VALUE;
    tot_len <<= FXP_VALUE; interval_time <<= FXP_VALUE; direction <<= FXP_VALUE;
    pkt_leaf->features[0] += tot_len;
    pkt_leaf->features[1] += interval_time;
    pkt_leaf->features[2] += direction;
    int64_t avg_tot_len       = pkt_leaf->features[0]/pkt_leaf->num_packets;
    int64_t avg_interval_time = pkt_leaf->features[1]/pkt_leaf->num_packets;
    int64_t avg_direction     = pkt_leaf->features[2]/pkt_leaf->num_packets;
    pkt_leaf->features[3] += llabs(tot_len - avg_tot_len);
    pkt_leaf->features[4] += llabs(interval_time - avg_interval_time);
    pkt_leaf->features[5] += llabs(direction - avg_direction);
    int64_t avg_dev_tot_len       = pkt_leaf->features[3]/pkt_leaf->num_packets;
    int64_t avg_dev_interval_time = pkt_leaf->features[4]/pkt_leaf->num_packets;
    int64_t avg_dev_direction     = pkt_leaf->features[5]/pkt_leaf->num_packets;
    int64_t feat[NUM_FEATURES] = {sport, dport, protocol, tot_len, interval_time, direction,
        avg_tot_len, avg_interval_time, avg_direction, avg_dev_tot_len, avg_dev_interval_time,
        avg_dev_direction};
    if (ffeat) fwrite(feat, sizeof feat, 1, ffeat);
    int current_node = 0;
    for (int i = 0; i < MAX_TREE_DEPTH; i++) {
        if (current_node < 0 || current_node >= DT_NODES) break;     /* map lookup miss */
        int64_t l = DT_childrenLeft[current_node], f = DT_feature[current_node];
        if (l == TREE_LEAF || f == TREE_UNDEFINED) break;
        if (f >= 0 && f < NUM_FEATURES) {
            int64_t v = feat[f];
            if (v) current_node = (int)(v <= DT_threshold[current_node] ? l : DT_childrenRight[current_node]);
        }
    }
    if (current_node < 0 || current_node >= DT_NODES) return 255;
    int64_t cv = DT_value[current_node];
    return (cv == 0 || cv == 1) ? (int)cv : 255;
}


/* Minimal reader for little-endian classic pcap and pcapng (SHB/IDB/EPB; one or more Ethernet
 * interfaces; if_tsresol honoured). next_pkt() returns 0 at end of file. */
static const uint8_t *M; static size_t OFF, END; static int NG; static u64 MUL;
static u64 ng_div[64]; static int ng_nif;
static int open_capture(void) {
    u32 magic = *(const u32 *)M;
    if (magic == 0xa1b2c3d4 || magic == 0xa1b23c4d) {
        MUL = magic == 0xa1b2c3d4 ? 1000 : 1; NG = 0; OFF = 24;
        if (*(const u32 *)(M + 20) != 1) { fprintf(stderr, "need Ethernet linktype\n"); return -1; }
        return 0;
    }
    if (magic == 0x0a0d0d0a && *(const u32 *)(M + 8) == 0x1a2b3c4d) { NG = 1; OFF = 0; return 0; }
    fprintf(stderr, "need little-endian pcap or pcapng\n"); return -1;
}
static int next_pkt(u64 *ts_ns, const uint8_t **data, size_t *caplen) {
    if (!NG) {
        if (OFF + 16 > END) return 0;
        const u32 *h = (const u32 *)(M + OFF);
        *ts_ns = (u64)h[0] * 1000000000ull + (u64)h[1] * MUL;
        *caplen = h[2]; *data = M + OFF + 16; OFF += 16 + h[2];
        return OFF <= END;
    }
    while (OFF + 12 <= END) {
        u32 type = *(const u32 *)(M + OFF), len = *(const u32 *)(M + OFF + 4);
        const uint8_t *b = M + OFF;
        if (len < 12 || OFF + len > END) return 0;
        OFF += len;
        if (type == 0x0a0d0d0a) { ng_nif = 0; continue; }
        if (type == 1) {                                   /* IDB */
            if (*(const uint16_t *)(b + 8) != 1) { fprintf(stderr, "non-Ethernet IDB\n"); exit(1); }
            u64 div = 1000;                                /* default resolution 10^-6 s */
            for (size_t o = 16; o + 4 <= len - 4;) {
                uint16_t code = *(const uint16_t *)(b + o), olen = *(const uint16_t *)(b + o + 2);
                if (!code) break;
                if (code == 9 && olen >= 1) {
                    uint8_t r = b[o + 4];
                    if (r & 0x80) { fprintf(stderr, "binary tsresol unsupported\n"); exit(1); }
                    u64 per = 1; for (int i = 0; i < r; i++) per *= 10;   /* ticks per second */
                    div = per >= 1000000000ull ? 0 : 1000000000ull / per;
                    if (per > 1000000000ull) { fprintf(stderr, "tsresol > ns unsupported\n"); exit(1); }
                    if (!div) div = 1;
                }
                o += 4 + ((olen + 3) & ~3u);
            }
            if (ng_nif < 64) ng_div[ng_nif++] = div;
            continue;
        }
        if (type == 6) {                                   /* EPB */
            u32 ifid = *(const u32 *)(b + 8);
            u64 t = (u64)*(const u32 *)(b + 12) << 32 | *(const u32 *)(b + 16);
            *ts_ns = t * (ifid < 64 ? ng_div[ifid] : 1000);
            *caplen = *(const u32 *)(b + 20); *data = b + 28;
            return 1;
        }
        if (type == 3) { fprintf(stderr, "simple packet block unsupported\n"); exit(1); }
    }
    return 0;
}

struct meta { u64 ts_us; u32 saddr, daddr; uint16_t sport, dport; uint8_t proto, parsed; uint16_t ip_len; u32 pad; };

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s in.pcap out_prefix [--key dir|bidir] [--iat-div D] [--lru N]\n", argv[0]); return 2; }
    int bidir = 0, dump = 0; int64_t iat_div = 1;
    for (int i = 3; i < argc; i++) {
        if (!strcmp(argv[i], "--key") && i + 1 < argc) bidir = !strcmp(argv[++i], "bidir");
        else if (!strcmp(argv[i], "--iat-div") && i + 1 < argc) iat_div = atoll(argv[++i]);
        else if (!strcmp(argv[i], "--dump-feat")) dump = 1;
        else if (!strcmp(argv[i], "--lru") && i + 1 < argc) cap_ent = strtoull(argv[++i], 0, 10);
        else { fprintf(stderr, "bad arg %s\n", argv[i]); return 2; }
    }
    int fd = open(argv[1], O_RDONLY); struct stat st;
    if (fd < 0 || fstat(fd, &st)) { perror(argv[1]); return 1; }
    const uint8_t *m = mmap(0, st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (m == MAP_FAILED) { perror("mmap"); return 1; }
    madvise((void *)m, st.st_size, MADV_SEQUENTIAL);
    M = m; END = st.st_size;
    if (open_capture()) return 1;
    char path[4096];
    snprintf(path, sizeof path, "%s.cls", argv[2]); FILE *fc = fopen(path, "wb");
    snprintf(path, sizeof path, "%s.meta", argv[2]); FILE *fm = fopen(path, "wb");
    if (dump) { snprintf(path, sizeof path, "%s.feat", argv[2]); ffeat = fopen(path, "wb"); }
    if (!fc || !fm || (dump && !ffeat)) { perror("output"); return 1; }
    u64 nrec = 0, nparsed = 0, base = 0, ts_abs; const uint8_t *d; size_t caplen;
    while (next_pkt(&ts_abs, &d, &caplen)) {
        if (!nrec) base = ts_abs;
        nrec++;
        int64_t ts = (int64_t)(ts_abs - base) + 1000000000ll;   /* same clock as check_sequence.py */
        struct meta mt = { ts_abs / 1000, 0, 0, 0, 0, 0, 0, 0, 0 };
        uint8_t cls[2] = {255, 255};
        /* XDP parse: eth (no VLAN), IPv4, fixed 20-byte IP header (th = iph + 1), TCP/UDP */
        if (caplen >= 14 && d[12] == 0x08 && d[13] == 0x00 && caplen >= 34) {
            u32 proto = d[23];
            size_t l4need = proto == 6 ? 20 : 8;
            if ((proto == 6 || proto == 17) && caplen >= 34 + l4need) {
                struct pkt_key_t k = {0};
                k.protocol = proto;
                memcpy(&k.saddr, d + 26, 4); memcpy(&k.daddr, d + 30, 4);
                k.sport = d[34] << 8 | d[35]; k.dport = d[36] << 8 | d[37];
                u32 tot_len = d[16] << 8 | d[17];
                mt.saddr = k.saddr; mt.daddr = k.daddr; mt.sport = k.sport; mt.dport = k.dport;
                mt.proto = proto; mt.parsed = 1; mt.ip_len = tot_len;
                struct pkt_key_t sk = k;     /* session key */
                if (bidir && ((u64)k.saddr << 16 | k.sport) > ((u64)k.daddr << 16 | k.dport)) {
                    sk.saddr = k.daddr; sk.daddr = k.saddr; sk.sport = k.dport; sk.dport = k.sport;
                }
                struct ent *e = lookup(&sk);
                if (!e) {
                    e = insert(&sk);
                    e->nn.sport = k.sport; e->nn.dport = k.dport; e->nn.last_packet_timestamp = ts;
                    e->dt.sport = k.sport; e->dt.dport = k.dport; e->dt.saddr = k.saddr;
                    e->dt.daddr = k.daddr; e->dt.last_packet_timestamp = ts;
                }
                cls[0] = dt_classify(&e->dt, &k, ts, proto, tot_len, iat_div);
                cls[1] = nn_classify(&e->nn, &k, ts, proto, tot_len, iat_div);
                nparsed++;
            }
        }
        if (ffeat && cls[0] == 255 && !mt.parsed) { int64_t z[NUM_FEATURES] = {0}; fwrite(z, sizeof z, 1, ffeat); }
        fwrite(cls, 1, 2, fc); fwrite(&mt, sizeof mt, 1, fm);
    }
    fclose(fc); fclose(fm); if (ffeat) fclose(ffeat);
    fprintf(stderr, "records=%llu classified=%llu sessions=%llu evictions=%llu "
            "int8_wrap_pkts(l1,l2,l3)=%llu,%llu,%llu key=%s iat_div=%lld lru=%llu\n",
            (unsigned long long)nrec, (unsigned long long)nparsed, (unsigned long long)n_ent,
            (unsigned long long)n_evict, (unsigned long long)wrap_cnt[0],
            (unsigned long long)wrap_cnt[1], (unsigned long long)wrap_cnt[2],
            bidir ? "bidir" : "dir", (long long)iat_div, (unsigned long long)cap_ent);
    return 0;
}

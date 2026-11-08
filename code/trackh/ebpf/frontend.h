/* E5 native XDP frontend: Track-H schema v1 (dataset_protocol.md §1) computed online.
 * Included by generated model objects compiled with -DFRONTEND. The first program in the object
 * (fe_main) parses each packet, updates the flow's O(1) state in an LRU hash and, at the flow's N-th
 * packet, copies the 17 features into the per-CPU scratch and tail-calls the model (jmp[1]). The
 * model's last stage calls finish(): class counters + a ring-buffer event (flow, class) for labelled
 * replay. Every packet gets the same final action (FE_ACTION) whether or not it triggered inference;
 * a missing model / failed tail call is counted as "inference unavailable" (fail-open: FE_ACTION). */
#ifndef FE_N
#define FE_N 8
#endif
#ifndef FE_TIMEOUT_US
#define FE_TIMEOUT_US 120000000ULL
#endif
#ifndef FE_FLOWS
#define FE_FLOWS 262144
#endif
#ifndef FE_ACTION
#define FE_ACTION XDP_DROP
#endif

struct fe_key { __u32 a, b; __u16 pa, pb; __u8 proto, pad[3]; };
struct fe_flow {
    __u64 t_first, t_last; __u32 ini_ip; __u16 ini_port, resp_port; __u32 npkts;
    __s32 f[17]; __u8 last_dir, pad[3];
};
struct fe_event { __u64 ts_first_us; __u32 ini_ip, resp_ip; __u16 ini_port, resp_port; __u8 proto, cls, pad[2];
#if defined(FE_TEST_TS) || defined(FE_EVENT_FEAT)
    __s32 f[17]; __u32 pad2;
#endif
};
#ifdef FE_TEST_TS
/* test-only clock: the harness writes each packet's capture timestamp (us) before running it */
struct { __uint(type, BPF_MAP_TYPE_ARRAY); __uint(max_entries, 1); __type(key, __u32); __type(value, __u64); } fe_now SEC(".maps");
#endif
struct { __uint(type, BPF_MAP_TYPE_LRU_HASH); __uint(max_entries, FE_FLOWS); __type(key, struct fe_key);
         __type(value, struct fe_flow); } fe_flows SEC(".maps");
struct { __uint(type, BPF_MAP_TYPE_RINGBUF); __uint(max_entries, 1 << 24); } fe_events SEC(".maps");
/* counters: 0 packets, 1 non-IPv4, 2 triggers, 3 inference unavailable (tail call failed),
 * 4 events dropped (ring full), 5 new flows, 8.. 8+NC class counts */
struct { __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY); __uint(max_entries, 64); __type(key, __u32);
         __type(value, __u64); } fe_cnt SEC(".maps");
struct fe_ctx { struct fe_event ev; };
struct { __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY); __uint(max_entries, 1); __type(key, __u32);
         __type(value, struct fe_ctx); } fe_scr SEC(".maps");

static __always_inline void fe_inc(__u32 k) { __u64 *c = bpf_map_lookup_elem(&fe_cnt, &k); if (c) (*c)++; }

#define SAT32(x) ((x) > 0x7fffffffLL ? 0x7fffffff : (__s32)(x))

SEC("xdp")
int fe_main(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data, *end = (void *)(long)ctx->data_end;
    fe_inc(0);
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > end) return FE_ACTION;
    __u16 et = eth->h_proto; void *p = eth + 1;
#pragma unroll
    for (int i = 0; i < 2; i++) {
        if (et == bpf_htons(0x8100) || et == bpf_htons(0x88a8)) {
            if (p + 4 > end) return FE_ACTION;
            et = *(__u16 *)(p + 2); p += 4;
        }
    }
    struct iphdr *ip = p;
    if (et != bpf_htons(ETH_P_IP) || (void *)(ip + 1) > end || ip->version != 4 || ip->ihl < 5) { fe_inc(1); return FE_ACTION; }
    __u32 ihl = ip->ihl * 4;
    __u16 iplen = bpf_ntohs(ip->tot_len); __u8 proto = ip->protocol;
    __u32 src = ip->saddr, dst = ip->daddr;
    __u16 sp = 0, dp = 0; __u8 fl = 0;
    if (!(bpf_ntohs(ip->frag_off) & 0x1fff) && (proto == 6 || proto == 17)) {
        __u8 *l4 = (void *)ip + (ihl & 0x3c);
        if ((void *)(l4 + 4) <= end) {
            sp = (l4[0] << 8) | l4[1]; dp = (l4[2] << 8) | l4[3];
            if (proto == 6 && (void *)(l4 + 14) <= end) fl = l4[13];
        }
    }
#ifdef FE_TEST_TS
    __u32 zt = 0; __u64 *tp = bpf_map_lookup_elem(&fe_now, &zt);
    __u64 now = tp ? *tp : 0;
#else
    __u64 now = bpf_ktime_get_ns() / 1000;
#endif
    struct fe_key k = {};
    if (src < dst || (src == dst && sp <= dp)) { k.a = src; k.b = dst; k.pa = sp; k.pb = dp; }
    else { k.a = dst; k.b = src; k.pa = dp; k.pb = sp; }
    k.proto = proto;
    struct fe_flow *f = bpf_map_lookup_elem(&fe_flows, &k);
    if (!f || now - f->t_last > FE_TIMEOUT_US) {
        struct fe_flow z = {};
        z.t_first = now; z.t_last = now; z.ini_ip = src; z.ini_port = sp; z.resp_port = dp;
        z.f[0] = proto; z.f[1] = dp; z.f[5] = iplen; z.f[6] = iplen; z.f[7] = iplen; z.f[9] = 0x7fffffff;
        bpf_map_update_elem(&fe_flows, &k, &z, BPF_ANY);
        f = bpf_map_lookup_elem(&fe_flows, &k);
        if (!f) return FE_ACTION;
        fe_inc(5);
    }
    __u8 dir = !(src == f->ini_ip && sp == f->ini_port);
    if (f->npkts && src == dst && sp == dp) dir = 0;
    if (f->npkts < FE_N) {
        if (dir == 0) { f->f[2]++; f->f[3] += iplen; } else f->f[4] += iplen;
        if (iplen < f->f[6]) f->f[6] = iplen;
        if (iplen > f->f[7]) f->f[7] = iplen;
        if (f->npkts) {
            __s64 iat = (__s64)(now - f->t_last);
            if (iat < f->f[9]) f->f[9] = SAT32(iat);
            if (iat > f->f[10]) f->f[10] = SAT32(iat);
            if (dir != f->last_dir) f->f[16]++;
        }
        f->f[11] += !!(fl & 0x02); f->f[12] += !!(fl & 0x01); f->f[13] += !!(fl & 0x04);
        f->f[14] += !!(fl & 0x08); f->f[15] += !!(fl & 0x10);
        f->f[8] = SAT32((__s64)(now - f->t_first));
    }
    f->npkts++; f->t_last = now; f->last_dir = dir;
    if (f->npkts != FE_N) return FE_ACTION;
    fe_inc(2);
    __u32 z0 = 0;
    struct scratch *S = bpf_map_lookup_elem(&scr, &z0);
    struct fe_ctx *E = bpf_map_lookup_elem(&fe_scr, &z0);
    if (!S || !E) return FE_ACTION;
#pragma unroll
    for (int i = 0; i < 17; i++) S->x[i] = f->f[i];
    E->ev.ts_first_us = f->t_first; E->ev.ini_ip = f->ini_ip; E->ev.ini_port = f->ini_port;
    E->ev.resp_ip = f->ini_ip == k.a && f->ini_port == k.pa ? k.b : k.a; E->ev.resp_port = f->resp_port;
    E->ev.proto = proto;
#if defined(FE_TEST_TS) || defined(FE_EVENT_FEAT)
#pragma unroll
    for (int i = 0; i < 17; i++) E->ev.f[i] = f->f[i];
#endif
    bpf_tail_call(ctx, &jmp, 1);
    fe_inc(3);                          /* inference unavailable: fail open */
    return FE_ACTION;
}

static __always_inline int fe_finish(struct xdp_md *ctx, __u32 cls) {
    __u32 z0 = 0;
    struct fe_ctx *E = bpf_map_lookup_elem(&fe_scr, &z0);
    fe_inc(8 + (cls & 31));
    if (E) {
        E->ev.cls = cls;
        if (bpf_ringbuf_output(&fe_events, &E->ev, sizeof E->ev, 0)) fe_inc(4);
    }
    return FE_ACTION;
}

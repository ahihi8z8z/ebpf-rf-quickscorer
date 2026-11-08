/* E0 repaired architecture: redirect only; the one userspace worker owns all
 * features and flow state. No per-packet printk or shared session map. */
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

struct {
  __uint(type, BPF_MAP_TYPE_XSKMAP);
  __uint(key_size, sizeof(int));
  __uint(value_size, sizeof(int));
  __uint(max_entries, 32);
} xsks SEC(".maps");

SEC("xdp")
int handle_xdp(struct xdp_md *ctx) {
  return bpf_redirect_map(&xsks, ctx->rx_queue_index, XDP_PASS);
}

char _license[] SEC("license") = "GPL";

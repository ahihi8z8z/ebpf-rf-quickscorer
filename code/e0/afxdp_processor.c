/* Inserted into a separate copy of mlids_user.c by make_afxdp_clean.py. */
#include "afxdp_state.h"

static uint64_t clean_packets, clean_inferences, clean_rejected, clean_unavailable;
static uint64_t clean_classes[7];
extern unsigned long clean_fill_retries;

int xsknf_packet_processor(void *pkt, unsigned len, unsigned ingress_ifindex)
{
  (void)ingress_ifindex;
  clean_packets++;
  if (len < sizeof(struct ethhdr) + sizeof(struct iphdr)) goto rejected;
  struct ethhdr *eth = pkt;
  struct iphdr *ip = (struct iphdr *)(eth + 1);
  /* The faithful parser assumes a 20-byte unfragmented IPv4 header. Make that
   * assumption explicit rather than treating options/fragments as TCP/UDP. */
  if (eth->h_proto != htons(ETH_P_IP) || ip->version != 4 || ip->ihl != 5 ||
      (ntohs(ip->frag_off) & 0x3fff)) goto rejected;
  unsigned iplen = ntohs(ip->tot_len);
  if (iplen < sizeof(*ip) || sizeof(*eth) + iplen > len) goto rejected;
  struct pkt_key_t key = {0};
  key.saddr = ip->saddr; key.daddr = ip->daddr; key.protocol = ip->protocol;
  unsigned l4len = iplen - sizeof(*ip);
  if (ip->protocol == IPPROTO_TCP) {
    if (l4len < sizeof(struct tcphdr)) goto rejected;
    struct tcphdr *tcp = (struct tcphdr *)(ip + 1);
    key.sport = ntohs(tcp->source); key.dport = ntohs(tcp->dest);
  } else if (ip->protocol == IPPROTO_UDP) {
    if (l4len < sizeof(struct udphdr)) goto rejected;
    struct udphdr *udp = (struct udphdr *)(ip + 1);
    key.sport = ntohs(udp->source); key.dport = ntohs(udp->dest);
  } else goto rejected;
  int64_t x[NUM_FEATURES] = {0};
  if (clean_features(&key, iplen, get_nsecs(), x)) {
    clean_unavailable++;
    return -1;
  }
  unsigned prediction = clean_predict(opt_ml_method, x);
  if (prediction >= 7) abort();
  clean_classes[prediction]++;
  clean_inferences++;
  return -1; /* Common drop action for every model. */
rejected:
  clean_rejected++;
  return -1;
}

static void clean_report(void) {
  fprintf(stderr, "CLEAN packets=%lu inferences=%lu rejected=%lu unavailable=%lu flows=%u classes=",
          clean_packets, clean_inferences, clean_rejected, clean_unavailable, clean_used);
  for (unsigned i = 0; i < 7; i++) fprintf(stderr, "%s%lu", i ? "," : "", clean_classes[i]);
  fprintf(stderr, "\n");
  fprintf(stderr, "CLEAN fill_retries=%lu\n", clean_fill_retries);
}

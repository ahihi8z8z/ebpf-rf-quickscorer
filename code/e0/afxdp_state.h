/* E0 repaired userspace-owned flow state. Single worker, no eviction/timeout.
 * Keeps the author's directional key and feature/inference arithmetic; does not
 * normalize the AF_XDP NN inputs (the original AF_XDP path does not either).
 * Capacity failures are explicit. This is an extension, not faithful Hara code.
 */
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

#define CLEAN_SLOTS 65536u
#define CLEAN_MAX_FLOWS 32768u

struct clean_slot {
  struct pkt_key_t key;
  struct pkt_leaf_t value;
  unsigned occupied;
};
static struct clean_slot *clean_slots;
static unsigned clean_used;

static int clean_init(void) {
  clean_used = 0;
  clean_slots = calloc(CLEAN_SLOTS, sizeof(*clean_slots));
  return clean_slots ? 0 : -1;
}

static void clean_destroy(void) {
  free(clean_slots);
  clean_slots = NULL;
  clean_used = 0;
}

static struct pkt_leaf_t *clean_lookup(const struct pkt_key_t *key, int64_t ts) {
  const unsigned char *bytes = (const unsigned char *)key;
  uint32_t hash = 2166136261u;
  for (unsigned i = 0; i < sizeof(*key); i++)
    hash = (hash ^ bytes[i]) * 16777619u;
  for (unsigned probe = 0; probe < CLEAN_SLOTS; probe++) {
    struct clean_slot *s = &clean_slots[(hash + probe) & (CLEAN_SLOTS - 1)];
    if (s->occupied) {
      if (!memcmp(&s->key, key, sizeof(*key))) return &s->value;
    } else {
      if (clean_used == CLEAN_MAX_FLOWS) return NULL;
      s->occupied = 1;
      s->key = *key;
      s->value.sport = key->sport;
      s->value.dport = key->dport;
      s->value.last_packet_timestamp = ts;
      clean_used++;
      return &s->value;
    }
  }
  return NULL;
}

static int clean_features(const struct pkt_key_t *key, unsigned length,
                          int64_t ts, int64_t x[NUM_FEATURES]) {
  struct pkt_leaf_t *s = clean_lookup(key, ts);
  if (!s) return -1;
  s->num_packets++;
  x[0] = s->sport;
  x[1] = s->dport;
  x[2] = key->protocol;
  x[3] = length;
  x[4] = s->last_packet_timestamp > 0 ? ts - s->last_packet_timestamp : 0;
  s->last_packet_timestamp = ts;
  x[5] = key->sport == x[0];
  for (unsigned i = 0; i < 6; i++) x[i] <<= FIXED_POINT_DIGITS;
  s->features0 += x[3]; s->features1 += x[4]; s->features2 += x[5];
  x[6] = s->features0 / s->num_packets;
  x[7] = s->features1 / s->num_packets;
  x[8] = s->features2 / s->num_packets;
  s->features3 += llabs(x[3] - x[6]);
  s->features4 += llabs(x[4] - x[7]);
  s->features5 += llabs(x[5] - x[8]);
  x[9] = s->features3 / s->num_packets;
  x[10] = s->features4 / s->num_packets;
  x[11] = s->features5 / s->num_packets;
  return 0;
}

static unsigned clean_predict(int method, int64_t x[NUM_FEATURES]) {
  unsigned prediction = 0;
  switch (method) {
    case 0: run_mlp(x, 1, &prediction); break;
    case 1: run_dt(x, 1, &prediction); break;
    default: abort(); /* The shipped RF is invalid; do not run it. */
  }
  return prediction;
}

#!/usr/bin/env python3
"""Synthetic equivalence trace for E0 (NOT dataset traffic): diverse 5-tuples, protocols, sizes,
well-known and ephemeral ports, interleaved flows -> exercises many DT/NN branches.
usage: python3 gen_trace.py out.pcap [flows=400] [pkts_per_flow=40] [seed=1]"""
import random, sys
from scapy.all import Ether, IP, TCP, UDP, Raw, wrpcap

out = sys.argv[1]
F = int(sys.argv[2]) if len(sys.argv) > 2 else 400
P = int(sys.argv[3]) if len(sys.argv) > 3 else 40
rng = random.Random(int(sys.argv[4]) if len(sys.argv) > 4 else 1)
DST_MAC, SRC_MAC = "52:54:00:51:a0:51", "52:54:00:51:a0:52"   # qs-dut data0 <- qs-tg data0
WELL_KNOWN = [21, 22, 23, 25, 53, 80, 123, 139, 443, 445, 3389, 8080]

flows = []
for i in range(F):
    tcp = rng.random() < 0.7
    sport = rng.choice(WELL_KNOWN) if rng.random() < 0.2 else rng.randint(1024, 65535)
    dport = rng.choice(WELL_KNOWN) if rng.random() < 0.7 else rng.randint(1, 65535)
    style = rng.choice(["small", "large", "mixed"])
    flows.append((tcp, f"10.50.{1 + i // 250}.{1 + i % 250}", sport, dport, style))

pkts, remaining = [], [P] * F
while any(remaining):
    i = rng.choice([k for k in range(F) if remaining[k]])
    remaining[i] -= 1
    tcp, src, sport, dport, style = flows[i]
    n = {"small": rng.randint(0, 40), "large": rng.randint(900, 1400), "mixed": rng.randint(0, 1400)}[style]
    l4 = TCP(sport=sport, dport=dport, flags=rng.choice(["S", "A", "PA", "FA", "R"])) if tcp \
        else UDP(sport=sport, dport=dport)
    pkts.append(Ether(dst=DST_MAC, src=SRC_MAC) / IP(src=src, dst="10.51.0.2", ttl=64) / l4 / Raw(b"x" * n))
wrpcap(out, pkts)
print(f"wrote {len(pkts)} packets, {F} flows -> {out}")

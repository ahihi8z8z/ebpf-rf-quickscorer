#!/usr/bin/env bash
# Run inside a VM:  sudo bash provision.sh dut|tg     (idempotent)
set -euo pipefail
ROLE=${1:?usage: provision.sh dut|tg}
export DEBIAN_FRONTEND=noninteractive
KV=$(uname -r)

COMMON="build-essential git make cmake pkg-config ethtool iproute2 tcpdump jq htop numactl
  python3-pip python3-venv python3-numpy python3-scapy linux-tools-$KV linux-tools-common
  linux-headers-$KV linux-modules-extra-$KV msr-tools cpufrequtils"
# DUT: eBPF/XDP build + Hara (BCC) + Galvao/libbpf + userspace RF reference
DUT="clang llvm lld libbpf-dev libxdp-dev xdp-tools libelf-dev zlib1g-dev libpcap-dev
  gcc-multilib bpfcc-tools python3-bpfcc libbpfcc-dev bpftrace python3-sklearn python3-pandas"
# TG: packet generators, PCAP replay, capture/counting
TG="tcpreplay netsniff-ng iperf3 hping3 tshark libpcap-dev clang llvm libbpf-dev libxdp-dev xdp-tools python3-pandas"

apt-get update -q
case $ROLE in
  dut) apt-get install -y -q $COMMON $DUT ;;
  tg)  echo "wireshark-common wireshark-common/install-setuid boolean false" | debconf-set-selections
       apt-get install -y -q $COMMON $TG
       modprobe pktgen && echo pktgen > /etc/modules-load.d/pktgen.conf ;;
  *) echo "bad role"; exit 1 ;;
esac

# Measurement hygiene on the data NICs: no GRO/offload surprises, all queues enabled.
for n in data0 data1; do
  ip link show $n >/dev/null 2>&1 || continue
  ethtool -K $n gro off 2>/dev/null || true
done
echo "provision[$ROLE] done: clang=$(clang --version 2>/dev/null | head -1) bpftool=$(bpftool version 2>/dev/null | head -1)"

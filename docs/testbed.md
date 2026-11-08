# QuickScorer eBPF/XDP VM testbed (on fil100)

```
                         LAN 192.168.101.0/24 (macvtap on fil100:eno1) — ssh from server3
                 qs-dut 192.168.101.51 (mgmt0)          qs-tg 192.168.101.52 (mgmt0)
                 8 vCPU (host cores 2-9), 16 GB         6 vCPU (host cores 10-15), 8 GB

  qs-tg data0 10.50.0.2 ──[ qs-a / virbr-qsa ]── data0 10.50.0.1  qs-dut
                                                   │  XDP classifier (native mode) + REDIRECT/forward
  qs-tg data1 10.51.0.2 ──[ qs-b / virbr-qsb ]── data1 10.51.0.1  qs-dut
  (netns "rx" = sink)
```

- Ubuntu 24.04, kernel 6.8. Login `haipt` (SSH key, or the VM password given via `VM_PASS`); passwordless sudo.
- Data NICs: virtio-net + vhost, 8 queue pairs, guest csum/TSO/ECN/UFO off, so native XDP
  (`xdpdrv`), XDP_TX and XDP_REDIRECT all work.
- The data links are isolated L2 bridges: no host IP, no DHCP, and bridge netfilter is off.
- TG `data1` lives in netns `rx` (systemd `qs-rx-netns.service`), so TG→DUT→TG traffic really
  crosses the DUT. On the DUT, `ip_forward=1` and `kernel.bpf_stats_enabled=1`.
- DUT tools: clang/llvm 18, libbpf, libxdp/xdp-tools, bpftool 7.4, BCC (`python3-bpfcc`), bpftrace, perf,
  scikit-learn/pandas.
- TG tools: pktgen (kernel module), tcpreplay, trafgen (netsniff-ng), iperf3, hping3, tshark, scapy, xdp-tools.

## Files
| path | where it runs |
| --- | --- |
| `lab.env` | shared settings (IPs, MACs, sizes, cpusets) |
| `host/create_lab.sh` | fil100, `sudo` — idempotent. Rerun after a fil100 reboot (it reapplies bridge nf_call=0) |
| `host/destroy_lab.sh` | fil100, `sudo` — removes only qs-* VMs, their disks and the qs-a/qs-b networks |
| `guest/provision.sh dut\|tg` | inside each VM, `sudo` — installs the toolchain |
| `guest/pktgen_tx.sh [sec] [size] [threads] [flows]` | qs-tg, `sudo` — UDP load from data0 toward the DUT |

Staged copy on fil100: `~/qs-lab` (VM disks are in `/var/lib/libvirt/images/qs/`).

## Smoke tests (verified 2026-11-03)
```bash
# kernel forwarding path
ssh haipt@192.168.101.52 'ping -c3 10.51.0.2'
# native XDP redirect data0 -> data1 on the DUT, with load from TG
ssh haipt@192.168.101.51 'sudo xdp-bench redirect -m native data0 data1'
ssh haipt@192.168.101.52 'sudo bash pktgen_tx.sh 10 64 4 1024'
ssh haipt@192.168.101.52 'sudo ip netns exec rx ip -s link show data1'   # sink counters
```
Baseline: about 0.5 Mpps of 64B packets through XDP_REDIRECT, with 0 driver errors.

## Caveats for the measurements (experimental.md E4/E5)
- The data path is virtio + vhost over a Linux bridge, so absolute pps is bounded by host vhost threads,
  not by the NIC. Compare variants on the same testbed, interleave the runs, and never quote this
  absolute pps as NIC line rate.
- vCPUs are pinned to a disjoint *set* of host cores per VM, not 1:1. The existing mtd-dut and
  mtd-attacker VMs float over all 20 cores and can add noise, so check `virsh list` before a run.
- Inside the VM, the guest cannot fix CPU governor or frequency. Record the host's settings (fil100) for each run.
- AF_XDP (H-NN-AFXDP) on virtio works only in copy mode, so report it as such.
- fil100 itself has no working DNS. The VMs use 8.8.8.8 and 1.1.1.1 directly and do have internet access.

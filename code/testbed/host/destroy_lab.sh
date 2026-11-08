#!/usr/bin/env bash
# Run ON fil100 as root. Removes ONLY the qs-* VMs, their disks and the qs-a/qs-b networks.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./lab.env
for vm in "$DUT_NAME" "$TG_NAME"; do
  virsh dominfo "$vm" >/dev/null 2>&1 || continue
  virsh destroy "$vm" 2>/dev/null || true
  virsh undefine "$vm" --nvram 2>/dev/null || virsh undefine "$vm"
  rm -rf "${IMG_DIR:?}/$vm"
done
for net in "$NET_A" "$NET_B"; do
  virsh net-info "$net" >/dev/null 2>&1 || continue
  virsh net-destroy "$net" 2>/dev/null || true
  virsh net-undefine "$net"
done
virsh list --all

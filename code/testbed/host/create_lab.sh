#!/usr/bin/env bash
# Run ON fil100 as root (sudo) from the staged lab dir (~/qs-lab). Idempotent.
# Creates two isolated L2 data links and two cloud-init VMs (DUT + TG) with LAN mgmt IPs via macvtap.
#
#   TG.data0 (10.50.0.2) ---[qs-a / virbr-qsa]--- DUT.data0 (10.50.0.1)
#                                                   |  XDP classifier + redirect/forward
#   TG.data1 (10.51.0.2, netns rx) --[qs-b / virbr-qsb]--- DUT.data1 (10.51.0.1)
set -euo pipefail
cd "$(dirname "$0")/.."
source ./lab.env
PUBKEYS="$(cat ./host/authorized_keys)"   # create this file with your own public key(s); not shipped

mkdir -p "$IMG_DIR"
[ -f "$IMG_DIR/$BASE_IMG" ] || install -m 0644 "images/$BASE_IMG" "$IMG_DIR/$BASE_IMG"

make_net() {
  local net=$1 br=$2
  if ! virsh net-info "$net" >/dev/null 2>&1; then
    cat > /tmp/$net.xml <<EOF
<network>
  <name>$net</name>
  <bridge name='$br' stp='off' delay='0'/>
</network>
EOF
    virsh net-define /tmp/$net.xml
    virsh net-autostart "$net"
  fi
  virsh net-info "$net" | grep -q 'Active:.*yes' || virsh net-start "$net"
  # fil100 has br_netfilter loaded: keep iptables out of the data path; no MAC learning delay.
  ip link set "$br" type bridge nf_call_iptables 0 nf_call_ip6tables 0 nf_call_arptables 0 2>/dev/null || true
}
make_net "$NET_A" "$BR_A"
make_net "$NET_B" "$BR_B"

make_vm() {
  local name=$1 ip=$2 vcpus=$3 cpuset=$4 ram=$5 mac_m=$6 mac_0=$7 mac_1=$8 role=$9
  if virsh dominfo "$name" >/dev/null 2>&1; then echo "[$name] exists, skipping"; return; fi
  local d="$IMG_DIR/$name"; mkdir -p "$d"

  cat > "$d/meta-data" <<EOF
instance-id: $name-001
local-hostname: $name
EOF

  local extra_files="" net_d0="" net_d1="" extra_cmds=""
  if [ "$role" = dut ]; then
    net_d0="    addresses: [$DUT_D0_IP/24]"
    net_d1="    addresses: [$DUT_D1_IP/24]"
    extra_files="  - path: /etc/sysctl.d/60-qs.conf
    content: |
      net.ipv4.ip_forward=1
      net.ipv4.conf.all.rp_filter=0
      net.ipv4.conf.default.rp_filter=0
      kernel.bpf_stats_enabled=1"
  else
    net_d0="    addresses: [$TG_D0_IP/24]
    routes: [{to: 10.51.0.0/24, via: $DUT_D0_IP}]"
    net_d1="    dhcp4: false"
    # data1 lives in netns "rx" so TG->DUT->TG traffic really crosses the DUT
    extra_files="  - path: /usr/local/sbin/qs-rx-netns.sh
    permissions: '0755'
    content: |
      #!/bin/sh
      set -e
      ip netns add rx 2>/dev/null || true
      ip link show data1 >/dev/null 2>&1 && ip link set data1 netns rx
      ip -n rx link set lo up
      ip -n rx addr replace $TG_D1_IP/24 dev data1
      ip -n rx link set data1 up
      ip -n rx route replace default via $DUT_D1_IP
  - path: /etc/systemd/system/qs-rx-netns.service
    content: |
      [Unit]
      Description=Move data1 into netns rx (QS testbed sink)
      After=systemd-networkd.service network-online.target
      Wants=network-online.target
      [Service]
      Type=oneshot
      RemainAfterExit=yes
      ExecStart=/usr/local/sbin/qs-rx-netns.sh
      [Install]
      WantedBy=multi-user.target"
    extra_cmds="  - systemctl daemon-reload
  - systemctl enable --now qs-rx-netns.service"
  fi

  cat > "$d/user-data" <<EOF
#cloud-config
hostname: $name
manage_etc_hosts: true
ssh_pwauth: true
disable_root: false
users:
  - name: $VM_USER
    groups: [sudo, adm]
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: false
    ssh_authorized_keys:
$(echo "$PUBKEYS" | sed 's/^/      - /')
chpasswd:
  expire: false
  users:
    - {name: $VM_USER, password: "$VM_PASS", type: text}
    - {name: root, password: "$VM_PASS", type: text}
write_files:
  - path: /etc/ssh/sshd_config.d/60-lab.conf
    content: |
      PasswordAuthentication yes
      UseDNS no
$extra_files
runcmd:
  - systemctl restart ssh
  - timedatectl set-timezone Asia/Ho_Chi_Minh
  - sysctl --system
$extra_cmds
EOF

  cat > "$d/network-config" <<EOF
version: 2
ethernets:
  mgmt0:
    match: {macaddress: "$mac_m"}
    set-name: mgmt0
    addresses: [$ip/$LAN_PREFIX]
    routes: [{to: default, via: $LAN_GW}]
    nameservers: {addresses: [$DNS1, $DNS2]}
  data0:
    match: {macaddress: "$mac_0"}
    set-name: data0
    optional: true
    mtu: 1500
$net_d0
  data1:
    match: {macaddress: "$mac_1"}
    set-name: data1
    optional: true
    mtu: 1500
$net_d1
EOF

  genisoimage -quiet -output "$d/seed.iso" -volid cidata -joliet -rock \
    "$d/user-data" "$d/meta-data" "$d/network-config"
  qemu-img create -q -f qcow2 -F qcow2 -b "$IMG_DIR/$BASE_IMG" "$d/disk.qcow2" "${DISK_GB}G"

  virt-install --name "$name" --memory "$ram" --vcpus "$vcpus,cpuset=$cpuset" --cpu host-passthrough \
    --os-variant ubuntu20.04 --import \
    --disk path="$d/disk.qcow2",bus=virtio \
    --disk path="$d/seed.iso",device=cdrom \
    --network type=direct,source="$HV_IFACE",source_mode=bridge,model=virtio,mac="$mac_m" \
    --network network="$NET_A",model=virtio,mac="$mac_0" \
    --network network="$NET_B",model=virtio,mac="$mac_1" \
    --graphics none --console pty,target_type=serial --noautoconsole \
    --print-xml > "$d/domain.xml"

  # Data NICs: vhost, multiqueue, guest offloads off (required for native XDP on virtio_net).
  python3 - "$d/domain.xml" "$NET_A" "$NET_B" "$DATA_QUEUES" <<'PY'
import sys, xml.etree.ElementTree as ET
path, na, nb, q = sys.argv[1:]
t = ET.parse(path)
n = 0
for itf in t.getroot().iter('interface'):
    src = itf.find('source')
    if itf.get('type') == 'network' and src is not None and src.get('network') in (na, nb):
        drv = itf.find('driver')
        if drv is None:
            drv = ET.SubElement(itf, 'driver')
        drv.set('name', 'vhost'); drv.set('queues', q)
        g = ET.SubElement(drv, 'guest')
        for k in ('csum', 'tso4', 'tso6', 'ecn', 'ufo'):
            g.set(k, 'off')
        n += 1
assert n == 2, n
t.write(path)
PY
  virsh define "$d/domain.xml"
  virsh start "$name"
  virsh autostart "$name"
  echo "[$name] created -> $ip"
}

make_vm "$DUT_NAME" "$DUT_IP" "$DUT_VCPUS" "$DUT_CPUSET" "$DUT_RAM_MB" "$DUT_MAC_MGMT" "$DUT_MAC_D0" "$DUT_MAC_D1" dut
make_vm "$TG_NAME"  "$TG_IP"  "$TG_VCPUS"  "$TG_CPUSET"  "$TG_RAM_MB"  "$TG_MAC_MGMT"  "$TG_MAC_D0"  "$TG_MAC_D1"  tg

virsh list --all

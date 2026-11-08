#!/usr/bin/env bash
# From server3: six-thread offered-load pilot, single queue; restore prior queues.
set -euo pipefail
cd "$(dirname "$0")/.."
DUT=haipt@192.168.101.51
if ssh -n "$DUT" 'ip -d link show data0' | grep -q 'xdp '; then
  echo 'DUT already has XDP attached' >&2
  exit 1
fi
queues=$(ssh -n "$DUT" 'sudo ethtool -l data0' | awk '/Current hardware settings:/{cur=1} cur && /Combined:/{print $2}')
trap 'ssh -n "$DUT" "sudo ethtool -L data0 combined $queues"' EXIT
ssh -n "$DUT" 'sudo ethtool -L data0 combined 1'
for model in filter dt; do
  VARIANT=clean_drop bash e0/run_smoke.sh "$model" -D 8 64 1024 6
done

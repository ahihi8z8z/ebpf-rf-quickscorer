#!/usr/bin/env bash
# Waits for each mirror PCAP to download and verify (fetch.log "OK <file>"), runs run_day.sh on it,
# then aggregates all five days and runs the learnability control.
set -uo pipefail
cd "$(dirname "$0")"
C="data/csv/TrafficLabelling "
declare -A F=([monday]=Monday-WorkingHours.pcap [tuesday]=Tuesday-WorkingHours.pcap
              [thursday]=Thursday-WorkingHours.pcap [friday]=Friday-WorkingHours.pcap)
declare -A CSVS=(
 [monday]="$C/Monday-WorkingHours.pcap_ISCX.csv"
 [tuesday]="$C/Tuesday-WorkingHours.pcap_ISCX.csv"
 [thursday]="$C/Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv|$C/Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv"
 [friday]="$C/Friday-WorkingHours-Morning.pcap_ISCX.csv|$C/Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv|$C/Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv")
left="monday tuesday thursday friday"
while [ -n "$left" ]; do
  for d in $left; do
    f=${F[$d]}
    if grep -q "^OK $f" data/cicids2017/fetch.log; then
      IFS='|' read -ra cs <<< "${CSVS[$d]}"
      ./run_day.sh "$d" "data/cicids2017/$f" "${cs[@]}" > out/run_day_$d.log 2>&1
      tail -1 out/run_day_$d.log
      left=$(echo $left | tr ' ' '\n' | grep -vx "$d" | tr '\n' ' ' | sed 's/ *$//')
    elif grep -q "MISMATCH $f\|FAIL $f" data/cicids2017/fetch.log; then
      echo "DOWNLOAD-PROBLEM $f"; left=$(echo $left | tr ' ' '\n' | grep -vx "$d" | tr '\n' ' ' | sed 's/ *$//')
    fi
  done
  [ -n "$left" ] && sleep 30
done
DAYS=$(for d in monday tuesday wednesday thursday friday; do [ -f out/days/$d.lab.json ] && echo -n "$d "; done)
python3 aggregate.py out/days $DAYS > out/trackr_all.md && echo AGG-OK
${PY:-python3} control_all.py out/days $DAYS > out/control_all.md && echo CTRL-OK
echo ALL-DAYS-DONE $DAYS

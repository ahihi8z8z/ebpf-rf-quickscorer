#!/usr/bin/env python3
"""From server3: replay smoke + interleaved load tests of repaired AF_XDP.

usage: python3 e0/run_afxdp_clean.py [--reps 3] [--seconds 10] [--threads 4]
Logs complete application and generator output, attach mode, counters and timing.
One RX queue, CPU1 worker (RX on CPU0); restores initial queue count on exit.
"""
import argparse
import json
from pathlib import Path
import re
import shlex
import statistics
import subprocess
import time

DUT = 'haipt@192.168.101.51'
TG = 'haipt@192.168.101.52'
OUT = Path(__file__).resolve().parent / 'afxdp_clean_runs'


def ssh(host, command):
    return subprocess.check_output(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
                                    host, command], text=True)


def one(model, kind, rep, seconds, threads):
    name = f'{kind}_{model}_{rep}'
    logfile = OUT / (name + '.log')
    limit = seconds + 10
    command = (f'cd ~/e0/afxdp-clean && sudo timeout -s INT -k 5 {limit} '
               f'taskset -c 1 stdbuf -oL ./examples/mlids/mlids '
               f'-i data0:c -M COMBINED -w 1 -- -m {shlex.quote(model)}')
    with logfile.open('w') as log:
        app = subprocess.Popen(['ssh', DUT, command], stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 8
        while 'CLEAN READY' not in logfile.read_text():
            if app.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError(f'{name}: app did not become ready; see {logfile}')
            time.sleep(.2)
        mode = ssh(DUT, 'ip -d link show data0')
        start = time.monotonic()
        if kind == 'replay':
            tx = ssh(TG, 'sudo tcpreplay -q -i data0 --pps=5000 eq_trace.pcap 2>&1')
        else:
            tx = ssh(TG, f'sudo bash pktgen_tx.sh {seconds} 64 {threads} 1024')
        elapsed = time.monotonic() - start
        # Bounded timeout provides cleanup even if the local runner is interrupted.
        rc = app.wait(timeout=limit + 8)
    (OUT / (name + '_tx.log')).write_text(tx)
    text = logfile.read_text()
    stats = re.search(r'CLEAN packets=(\d+) inferences=(\d+) rejected=(\d+) '
                      r'unavailable=(\d+) flows=(\d+) classes=([\d,]+)', text)
    if not stats or rc not in (0, 124):
        raise RuntimeError(f'{name}: missing clean shutdown counters rc={rc}')
    row = dict(zip(('packets', 'inferences', 'rejected', 'unavailable', 'flows'),
                   map(int, stats.groups()[:5])))
    row.update(model=model, workload=kind, rep=rep, threads=threads, traffic_elapsed=elapsed,
               classes=list(map(int, stats[6].split(','))), attach_native='xdp ' in mode,
               inference_per_generation_second=row['inferences'] / elapsed)
    # Every nonzero TOTAL interval is retained; do not select the top three.
    rates = [int(v.replace(',', '')) for v in re.findall(r'TOTAL\s+pps[^\n]*\nrx\s+([\d,]+)', text)]
    row['rx_interval_pps'] = rates
    row['fill_retries'] = int(re.search(r'CLEAN fill_retries=(\d+)', text)[1])
    row['rx_nonzero_median_pps'] = statistics.median([v for v in rates if v]) if any(rates) else 0
    offer = re.search(r'TOTAL tx pps=(\d+)', tx)
    row['offered_pps'] = int(offer[1]) if offer else None
    assert sum(row['classes']) == row['inferences']
    assert row['unavailable'] == 0
    assert row['attach_native'], mode
    if kind == 'replay':
        assert row['inferences'] == 16000 and row['flows'] == 400, row
    assert 'xdp ' not in ssh(DUT, 'ip -d link show data0'), 'attachment remains'
    print(json.dumps(row), flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reps', type=int, default=3)
    parser.add_argument('--seconds', type=int, default=10)
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    assert 'xdp ' not in ssh(DUT, 'ip -d link show data0'), 'DUT already has XDP attached'
    channels = ssh(DUT, 'sudo ethtool -l data0')
    current = channels.split('Current hardware settings:')[1]
    queues = int(re.search(r'Combined:\s+(\d+)', current)[1])
    rows = []
    try:
        ssh(DUT, 'sudo ethtool -L data0 combined 1')
        for model in ('NN', 'DT'):
            rows.append(one(model, 'replay', 1, 5, args.threads))
        for rep in range(1, args.reps + 1):
            for model in ('NN', 'DT'):
                rows.append(one(model, 'load', rep, args.seconds, args.threads))
    finally:
        (OUT / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
        ssh(DUT, f'sudo ethtool -L data0 combined {queues}')


if __name__ == '__main__':
    main()

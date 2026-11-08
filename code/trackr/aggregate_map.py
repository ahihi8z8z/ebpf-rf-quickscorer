"""CIC-IDS2017 label -> paper 7-class index (0 Botnet, 1 Brute force, 2 DoS, 3 Infiltration,
4 Normal, 5 Portscan, 6 Web attack); -1 = no stated class (Heartbleed)."""


def map7(c):
    if c == 'BENIGN': return 4
    if c == 'Bot': return 0
    if c in ('FTP-Patator', 'SSH-Patator'): return 1
    if c.startswith('DoS') or c == 'DDoS': return 2
    if c == 'Infiltration': return 3
    if c == 'PortScan': return 5
    if c.startswith('Web Attack'): return 6
    return -1                                   # Heartbleed

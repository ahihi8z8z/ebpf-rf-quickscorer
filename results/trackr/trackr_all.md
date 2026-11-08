## Labelled packets per CIC label (all processed days)

| label | packets |
|---|---|
| BENIGN | 51489452 |
| DoS Hulk | 2246753 |
| DDoS | 1265915 |
| PortScan | 321489 |
| SSH-Patator | 163311 |
| FTP-Patator | 111562 |
| DoS GoldenEye | 104606 |
| Infiltration | 59754 |
| Heartbleed | 49296 |
| DoS slowloris | 47609 |
| DoS Slowhttptest | 39630 |
| Web Attack - Brute Force | 30249 |
| Bot | 12853 |
| Web Attack - XSS | 9347 |
| Web Attack - Sql Injection | 126 |

Days: monday, tuesday, wednesday, thursday, friday. Heartbleed packets excluded from 7-class scoring: 49296.

## Binary, pooled over days (paper Table II: DT acc 0.977 / F1 0.954; NN 0.975 / 0.952)

| features / state | model | packets | acc | precision | recall | F1 | FPR |
|---|---|---|---|---|---|---|---|
| kernel semantics, unbounded table | DT | 55951952 | 0.718 | 0.178 | 0.701 | 0.284 | 0.280 |
| kernel semantics, unbounded table | NN | 55951952 | 0.649 | 0.119 | 0.531 | 0.195 | 0.340 |
| kernel semantics, LRU 1024 (deployed) | DT | 55951952 | 0.721 | 0.144 | 0.506 | 0.224 | 0.260 |
| kernel semantics, LRU 1024 (deployed) | NN | 55951952 | 0.661 | 0.124 | 0.536 | 0.201 | 0.329 |
| bidirectional sessions | DT | 55951952 | 0.483 | 0.119 | 0.853 | 0.208 | 0.549 |
| bidirectional sessions | NN | 55951952 | 0.585 | 0.124 | 0.693 | 0.210 | 0.424 |

## Binary per day (kernel semantics, unbounded)

| day | model | packets | acc | F1 | FPR | attack share |
|---|---|---|---|---|---|---|
| monday | DT | 11625464 | 0.717 | 0.000 | 0.283 | 0.000 |
| monday | NN | 11625464 | 0.645 | 0.000 | 0.355 | 0.000 |
| tuesday | DT | 11468939 | 0.697 | 0.054 | 0.294 | 0.024 |
| tuesday | NN | 11468939 | 0.648 | 0.051 | 0.346 | 0.024 |
| wednesday | DT | 13704886 | 0.711 | 0.493 | 0.303 | 0.182 |
| wednesday | NN | 13704886 | 0.636 | 0.353 | 0.345 | 0.182 |
| thursday | DT | 9238843 | 0.758 | 0.021 | 0.237 | 0.011 |
| thursday | NN | 9238843 | 0.676 | 0.028 | 0.322 | 0.011 |
| friday | DT | 9913820 | 0.717 | 0.436 | 0.275 | 0.161 |
| friday | NN | 9913820 | 0.651 | 0.332 | 0.328 | 0.161 |

## AF_XDP 7-class NN, pooled (paper Table III: NN accuracy 0.974)

| variant | packets | accuracy | macro recall | recall Botnet | recall Brute force | recall DoS | recall Infiltration | recall Normal | recall Portscan | recall Web attack |
|---|---|---|---|---|---|---|---|---|---|---|
| dir, no normalisation (as shipped) | 55902656 | 0.355 | 0.171 | 0.022 | 0.027 | 0.634 | 0.158 | 0.340 | 0.000 | 0.015 |
| dir, binary normaliser | 55902656 | 0.711 | 0.187 | 0.000 | 0.000 | 0.577 | 0.000 | 0.730 | 0.000 | 0.000 |
| bidir, no normalisation | 55902656 | 0.272 | 0.205 | 0.017 | 0.062 | 0.859 | 0.249 | 0.232 | 0.019 | 0.000 |
| bidir, binary normaliser | 55902656 | 0.767 | 0.352 | 0.317 | 0.134 | 0.691 | 0.058 | 0.779 | 0.486 | 0.000 |

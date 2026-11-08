
### out/nn7_dir_raw.nn7

| true \ pred | Botnet | BruteForce | DoS | Infiltration | Normal | Portscan | WebAttack |
|---|---|---|---|---|---|---|---|
| BENIGN | 0.020 | 0.023 | 0.321 | 0.225 | 0.399 | 0.002 | 0.010 |
| DoS GoldenEye | 0.005 | 0.009 | 0.660 | 0.186 | 0.120 | 0.004 | 0.015 |
| DoS Hulk | 0.008 | 0.012 | 0.600 | 0.201 | 0.159 | 0.004 | 0.017 |
| DoS Slowhttptest | 0.001 | 0.005 | 0.857 | 0.063 | 0.067 | 0.001 | 0.006 |
| DoS slowloris | 0.001 | 0.025 | 0.786 | 0.116 | 0.061 | 0.000 | 0.011 |
| Heartbleed | 0.010 | 0.007 | 0.000 | 0.235 | 0.747 | 0.000 | 0.000 |

binary (pred != Normal): acc 0.478 precision 0.236 recall 0.835 F1 0.367 FPR 0.601; 7-class accuracy on Wednesday (BENIGN->Normal, DoS*->DoS): 0.437 (Heartbleed excluded)

### out/nn7_dir_norm.nn7

| true \ pred | Botnet | BruteForce | DoS | Infiltration | Normal | Portscan | WebAttack |
|---|---|---|---|---|---|---|---|
| BENIGN | 0.000 | 0.000 | 0.283 | 0.000 | 0.716 | 0.000 | 0.000 |
| DoS GoldenEye | 0.000 | 0.000 | 0.629 | 0.000 | 0.371 | 0.000 | 0.000 |
| DoS Hulk | 0.000 | 0.000 | 0.555 | 0.000 | 0.445 | 0.000 | 0.000 |
| DoS Slowhttptest | 0.000 | 0.000 | 0.823 | 0.000 | 0.177 | 0.000 | 0.000 |
| DoS slowloris | 0.000 | 0.000 | 0.782 | 0.000 | 0.218 | 0.000 | 0.000 |
| Heartbleed | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |

binary (pred != Normal): acc 0.687 precision 0.303 recall 0.556 F1 0.392 FPR 0.284; 7-class accuracy on Wednesday (BENIGN->Normal, DoS*->DoS): 0.690 (Heartbleed excluded)

### out/nn7_bidir_raw.nn7

| true \ pred | Botnet | BruteForce | DoS | Infiltration | Normal | Portscan | WebAttack |
|---|---|---|---|---|---|---|---|
| BENIGN | 0.016 | 0.015 | 0.518 | 0.229 | 0.219 | 0.002 | 0.001 |
| DoS GoldenEye | 0.000 | 0.024 | 0.839 | 0.083 | 0.050 | 0.004 | 0.000 |
| DoS Hulk | 0.000 | 0.030 | 0.842 | 0.068 | 0.057 | 0.002 | 0.001 |
| DoS Slowhttptest | 0.000 | 0.005 | 0.946 | 0.025 | 0.020 | 0.003 | 0.000 |
| DoS slowloris | 0.000 | 0.029 | 0.908 | 0.021 | 0.041 | 0.001 | 0.000 |
| Heartbleed | 0.014 | 0.004 | 0.003 | 0.279 | 0.699 | 0.000 | 0.000 |

binary (pred != Normal): acc 0.348 precision 0.209 recall 0.931 F1 0.341 FPR 0.781; 7-class accuracy on Wednesday (BENIGN->Normal, DoS*->DoS): 0.330 (Heartbleed excluded)

### out/nn7_bidir_norm.nn7

| true \ pred | Botnet | BruteForce | DoS | Infiltration | Normal | Portscan | WebAttack |
|---|---|---|---|---|---|---|---|
| BENIGN | 0.000 | 0.000 | 0.217 | 0.001 | 0.767 | 0.015 | 0.000 |
| DoS GoldenEye | 0.000 | 0.000 | 0.826 | 0.000 | 0.174 | 0.000 | 0.000 |
| DoS Hulk | 0.000 | 0.000 | 0.705 | 0.003 | 0.289 | 0.003 | 0.000 |
| DoS Slowhttptest | 0.000 | 0.000 | 0.724 | 0.010 | 0.242 | 0.025 | 0.000 |
| DoS slowloris | 0.000 | 0.000 | 0.616 | 0.010 | 0.367 | 0.008 | 0.000 |
| Heartbleed | 0.000 | 0.000 | 0.592 | 0.000 | 0.408 | 0.000 | 0.000 |

binary (pred != Normal): acc 0.757 precision 0.404 recall 0.712 F1 0.515 FPR 0.233; 7-class accuracy on Wednesday (BENIGN->Normal, DoS*->DoS): 0.756 (Heartbleed excluded)

# E4b mechanism table (model-only cost per inference, medians of 3 passes)

eBPF cycles = (variant − null) ns × 2.195 GHz; C cycles counted. Units of work: walk steps / QS updates per row.


## d1_binary_RF_T64L64_s0 — cold_repeat1

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| eBPF | grf_k4 | G-RF | 662 | 2557 | 1452 | 1.76 | 5.6 | 3.2 | 18.7 |
| eBPF | grfm_k4 | G-RF-mem | 729 | 2493 | 1600 | 1.56 | 5.5 | 3.5 | 18.6 |
| eBPF | rfwl_g2 | RF-walk-bpfloop | 4254 | 19873 | 9338 | 2.13 | 43.7 | 20.5 | 87.3 |
| eBPF | qs_g1 | QS-mask | 4411 | 45581 | 9683 | 4.71 | 27.3 | 5.8 | 17.0 |
| eBPF | qs_g2 | QS-mask | 4788 | 46338 | 10510 | 4.41 | 27.7 | 6.3 | 29.2 |
| eBPF | qsb_g1 | QS-bounds | 6307 | 51181 | 13844 | 3.70 | 30.6 | 8.3 | 17.5 |
| eBPF | qsl_g1 | QS-bpfloop | 9720 | 95490 | 21335 | 4.48 | 57.2 | 12.8 | 19.2 |

## d1_binary_RF_T64L64_s0 — cold_rowrep1

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | qs | C-qs | 2006 | 16314 | 5372 | 3.04 | 9.8 | 3.2 | 16.4 |
| C | qs_vol | C-qs_vol | 2278 | 24882 | 6092 | 4.08 | 14.9 | 3.6 | 15.3 |
| C | walk | C-walk | 2328 | 4883 | 6159 | 0.79 | 10.7 | 13.6 | 81.8 |
| C | qs_bpf | C-qs_bpf | 2854 | 21290 | 7618 | 2.79 | 12.7 | 4.6 | 15.8 |

## d1_binary_RF_T64L64_s0 — cold_rowrep1_novec

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | qs | C-qs | 2042 | 16328 | 5468 | 2.99 | 9.8 | 3.3 | 15.5 |
| C | walk | C-walk | 2137 | 4818 | 5753 | 0.84 | 10.6 | 12.7 | 79.9 |
| C | qs_bpf | C-qs_bpf | 2840 | 21289 | 7601 | 2.80 | 12.7 | 4.6 | 15.0 |
| C | qs_vol | C-qs_vol | 4089 | 24881 | 10936 | 2.28 | 14.9 | 6.5 | 15.3 |

## d1_binary_RF_T64L64_s0 — warm_repeat200

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| eBPF | grf_k4 | G-RF | 687 | 2568 | 1508 | 1.70 | 5.6 | 3.3 | 0.4 |
| eBPF | grfm_k4 | G-RF-mem | 732 | 2510 | 1607 | 1.56 | 5.5 | 3.5 | 0.5 |
| eBPF | rfwl_g2 | RF-walk-bpfloop | 4770 | 19888 | 10471 | 1.90 | 43.8 | 23.0 | 4.4 |
| eBPF | qs_g1 | QS-mask | 5599 | 45588 | 12290 | 3.71 | 27.3 | 7.4 | 15.0 |
| eBPF | qs_g2 | QS-mask | 6220 | 46342 | 13654 | 3.39 | 27.7 | 8.2 | 20.9 |
| eBPF | qsb_g1 | QS-bounds | 7254 | 51182 | 15922 | 3.21 | 30.6 | 9.5 | 17.6 |
| eBPF | qsl_g1 | QS-bpfloop | 12777 | 95487 | 28045 | 3.40 | 57.2 | 16.8 | 17.9 |

## d1_binary_RF_T64L64_s0 — warm_rowrep200

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | walk | C-walk | 1161 | 4885 | 3126 | 1.56 | 10.7 | 6.9 | 1.9 |
| C | qs | C-qs | 1986 | 16306 | 5309 | 3.07 | 9.8 | 3.2 | 14.7 |
| C | qs_vol | C-qs_vol | 2250 | 24871 | 6014 | 4.14 | 14.9 | 3.6 | 13.0 |
| C | qs_bpf | C-qs_bpf | 2808 | 21280 | 7557 | 2.82 | 12.7 | 4.5 | 12.2 |

## d1_multiclass_RF_T128L64_s0 — cold_repeat1

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| eBPF | grf_k4 | G-RF | 1866 | 5669 | 4096 | 1.38 | 6.3 | 4.5 | 45.0 |
| eBPF | grfm_k4 | G-RF-mem | 1979 | 4961 | 4344 | 1.14 | 5.5 | 4.8 | 44.1 |
| eBPF | rfw_g2 | RF-walk-table | 9459 | 37639 | 20762 | 1.81 | 41.6 | 22.9 | 236.9 |
| eBPF | rfwl_g1 | RF-walk-bpfloop | 11164 | 39912 | 24505 | 1.63 | 44.1 | 27.1 | 323.0 |
| eBPF | qs_g8 | QS-mask | 11172 | 101305 | 24523 | 4.13 | 29.6 | 7.2 | 111.7 |
| eBPF | qsb_g2 | QS-bounds | 11748 | 109319 | 25788 | 4.24 | 31.9 | 7.5 | 33.7 |
| eBPF | qsl_g1 | QS-bpfloop | 21146 | 198595 | 46415 | 4.28 | 58.0 | 13.6 | 23.0 |

## d1_multiclass_RF_T128L64_s0 — cold_rowrep1

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | qs | C-qs | 4373 | 37026 | 11693 | 3.17 | 10.8 | 3.4 | 16.9 |
| C | qs_vol | C-qs_vol | 4881 | 54315 | 12973 | 4.19 | 15.9 | 3.8 | 15.9 |
| C | walk | C-walk | 5975 | 11907 | 16035 | 0.74 | 13.2 | 17.7 | 252.9 |
| C | qs_bpf | C-qs_bpf | 6082 | 47220 | 16263 | 2.90 | 13.8 | 4.8 | 17.3 |

## d1_multiclass_RF_T128L64_s0 — cold_rowrep1_novec

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | qs | C-qs | 4489 | 38322 | 11989 | 3.20 | 11.2 | 3.5 | 17.1 |
| C | qs_bpf | C-qs_bpf | 4906 | 48500 | 13088 | 3.71 | 14.2 | 3.8 | 17.4 |
| C | walk | C-walk | 6881 | 13317 | 18311 | 0.73 | 14.7 | 20.2 | 285.4 |
| C | qs_vol | C-qs_vol | 8656 | 55597 | 23167 | 2.40 | 16.2 | 6.8 | 17.1 |

## d1_multiclass_RF_T128L64_s0 — warm_repeat200

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| eBPF | grf_k4 | G-RF | 1725 | 5676 | 3787 | 1.50 | 6.3 | 4.2 | 1.0 |
| eBPF | grfm_k4 | G-RF-mem | 1750 | 4963 | 3841 | 1.29 | 5.5 | 4.2 | 1.1 |
| eBPF | rfwl_g1 | RF-walk-bpfloop | 8991 | 39958 | 19735 | 2.02 | 44.2 | 21.8 | 26.2 |
| eBPF | rfw_g2 | RF-walk-table | 9734 | 37692 | 21365 | 1.76 | 41.7 | 23.6 | 18.8 |
| eBPF | qs_g8 | QS-mask | 17707 | 101312 | 38867 | 2.61 | 29.6 | 11.4 | 41.0 |
| eBPF | qsb_g2 | QS-bounds | 18846 | 109332 | 41367 | 2.64 | 31.9 | 12.1 | 32.7 |
| eBPF | qsl_g1 | QS-bpfloop | 34395 | 198612 | 75497 | 2.63 | 58.0 | 22.1 | 21.1 |

## d1_multiclass_RF_T128L64_s0 — warm_rowrep200

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | walk | C-walk | 3083 | 11915 | 8229 | 1.45 | 13.2 | 9.1 | 9.4 |
| C | qs | C-qs | 4591 | 37010 | 12267 | 3.02 | 10.8 | 3.6 | 16.7 |
| C | qs_bpf | C-qs_bpf | 5063 | 47199 | 13544 | 3.48 | 13.8 | 4.0 | 16.4 |
| C | qs_vol | C-qs_vol | 6274 | 54292 | 16969 | 3.20 | 15.9 | 5.0 | 16.8 |

## d1_multiclass_RF_T64D6_s0 — cold_repeat1

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| eBPF | grf_k8 | G-RF | 533 | 2012 | 1169 | 1.72 | 5.4 | 3.1 | 14.9 |
| eBPF | grfm_k4 | G-RF-mem | 607 | 2361 | 1332 | 1.77 | 6.3 | 3.6 | 15.3 |
| eBPF | rfw_g4 | RF-walk-table | 3343 | 15934 | 7338 | 2.17 | 42.6 | 19.6 | 39.5 |
| eBPF | rfwl_g2 | RF-walk-bpfloop | 3422 | 15775 | 7510 | 2.10 | 42.1 | 20.1 | 39.4 |
| eBPF | qs_g1 | QS-mask | 3572 | 36238 | 7840 | 4.62 | 30.2 | 6.5 | 14.6 |
| eBPF | qs_g2 | QS-mask | 3885 | 36801 | 8527 | 4.32 | 30.7 | 7.1 | 25.8 |
| eBPF | qsb_g4 | QS-bounds | 4994 | 41433 | 10962 | 3.78 | 34.6 | 9.1 | 51.9 |
| eBPF | qsl_g2 | QS-bpfloop | 9319 | 73986 | 20455 | 3.62 | 61.7 | 17.1 | 31.9 |

## d1_multiclass_RF_T64D6_s0 — cold_rowrep1

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | qs | C-qs | 1699 | 14089 | 4539 | 3.10 | 11.8 | 3.8 | 15.9 |
| C | qs_vol | C-qs_vol | 1915 | 20297 | 5111 | 3.97 | 16.9 | 4.3 | 15.4 |
| C | walk | C-walk | 2028 | 5443 | 5406 | 1.01 | 14.5 | 14.4 | 60.0 |
| C | qs_bpf | C-qs_bpf | 2344 | 17650 | 6274 | 2.81 | 14.7 | 5.2 | 15.3 |

## d1_multiclass_RF_T64D6_s0 — cold_rowrep1_novec

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | qs | C-qs | 1745 | 14761 | 4603 | 3.21 | 12.3 | 3.8 | 15.2 |
| C | qs_bpf | C-qs_bpf | 1917 | 18290 | 5105 | 3.58 | 15.3 | 4.3 | 15.5 |
| C | walk | C-walk | 1982 | 6148 | 5308 | 1.16 | 16.4 | 14.2 | 58.3 |
| C | qs_vol | C-qs_vol | 3300 | 20938 | 8771 | 2.39 | 17.5 | 7.3 | 15.7 |

## d1_multiclass_RF_T64D6_s0 — warm_repeat200

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| eBPF | grf_k8 | G-RF | 528 | 2030 | 1158 | 1.75 | 5.4 | 3.1 | 0.4 |
| eBPF | grfm_k4 | G-RF-mem | 688 | 2367 | 1510 | 1.57 | 6.3 | 4.0 | 0.4 |
| eBPF | rfwl_g2 | RF-walk-bpfloop | 3630 | 15781 | 7967 | 1.98 | 42.1 | 21.3 | 1.3 |
| eBPF | rfw_g4 | RF-walk-table | 3989 | 15946 | 8756 | 1.82 | 42.6 | 23.4 | 1.2 |
| eBPF | qs_g2 | QS-mask | 5067 | 36811 | 11123 | 3.31 | 30.7 | 9.3 | 16.2 |
| eBPF | qs_g1 | QS-mask | 5268 | 36243 | 11563 | 3.13 | 30.2 | 9.6 | 11.9 |
| eBPF | qsb_g4 | QS-bounds | 6152 | 41462 | 13503 | 3.07 | 34.6 | 11.3 | 25.3 |
| eBPF | qsl_g2 | QS-bpfloop | 13308 | 74027 | 29211 | 2.53 | 61.8 | 24.4 | 31.3 |

## d1_multiclass_RF_T64D6_s0 — warm_rowrep200

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | walk | C-walk | 1206 | 5443 | 3225 | 1.69 | 14.5 | 8.6 | 1.9 |
| C | qs | C-qs | 1798 | 14089 | 4818 | 2.92 | 11.8 | 4.0 | 13.7 |
| C | qs_bpf | C-qs_bpf | 1994 | 17651 | 5345 | 3.30 | 14.7 | 4.5 | 12.5 |
| C | qs_vol | C-qs_vol | 2469 | 20298 | 6608 | 3.07 | 16.9 | 5.5 | 13.0 |

## d1_multiclass_RF_T64L64_s0 — cold_repeat1

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| eBPF | grf_k4 | G-RF | 711 | 2849 | 1562 | 1.82 | 6.3 | 3.4 | 16.7 |
| eBPF | grfm_k4 | G-RF-mem | 836 | 2473 | 1836 | 1.35 | 5.5 | 4.1 | 16.8 |
| eBPF | rfw_g4 | RF-walk-table | 3662 | 18210 | 8038 | 2.27 | 40.2 | 17.8 | 51.3 |
| eBPF | qs_g1 | QS-mask | 4446 | 49084 | 9759 | 5.03 | 28.7 | 5.7 | 17.0 |
| eBPF | rfwl_g1 | RF-walk-bpfloop | 4629 | 19979 | 10160 | 1.97 | 44.1 | 22.4 | 103.5 |
| eBPF | qs_g2 | QS-mask | 5167 | 49665 | 11341 | 4.38 | 29.0 | 6.6 | 29.8 |
| eBPF | qsb_g8 | QS-bounds | 7424 | 57880 | 16295 | 3.55 | 33.8 | 9.5 | 105.7 |
| eBPF | qsl_g1 | QS-bpfloop | 11434 | 99964 | 25099 | 3.98 | 58.4 | 14.7 | 17.9 |

## d1_multiclass_RF_T64L64_s0 — cold_rowrep1

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | qs | C-qs | 2275 | 18712 | 6078 | 3.08 | 10.9 | 3.5 | 16.6 |
| C | walk | C-walk | 2472 | 5991 | 6630 | 0.90 | 13.2 | 14.6 | 76.7 |
| C | qs_vol | C-qs_vol | 2555 | 27488 | 6825 | 4.03 | 16.1 | 4.0 | 16.1 |
| C | qs_bpf | C-qs_bpf | 3157 | 23814 | 8455 | 2.82 | 13.9 | 4.9 | 16.5 |

## d1_multiclass_RF_T64L64_s0 — cold_rowrep1_novec

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | qs | C-qs | 2294 | 19384 | 6121 | 3.17 | 11.3 | 3.6 | 15.6 |
| C | walk | C-walk | 2447 | 6696 | 6567 | 1.02 | 14.8 | 14.5 | 74.1 |
| C | qs_bpf | C-qs_bpf | 2554 | 24454 | 6819 | 3.59 | 14.3 | 4.0 | 16.7 |
| C | qs_vol | C-qs_vol | 4454 | 28129 | 13667 | 2.06 | 16.4 | 8.0 | 16.6 |

## d1_multiclass_RF_T64L64_s0 — warm_repeat200

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| eBPF | grfm_k4 | G-RF-mem | 656 | 2495 | 1439 | 1.73 | 5.5 | 3.2 | 0.4 |
| eBPF | grf_k4 | G-RF | 804 | 2869 | 1765 | 1.63 | 6.3 | 3.9 | 0.5 |
| eBPF | rfw_g4 | RF-walk-table | 4172 | 18252 | 9159 | 1.99 | 40.3 | 20.2 | 2.3 |
| eBPF | rfwl_g1 | RF-walk-bpfloop | 4734 | 20012 | 10391 | 1.93 | 44.2 | 23.0 | 4.0 |
| eBPF | qs_g2 | QS-mask | 7043 | 49661 | 15460 | 3.21 | 29.0 | 9.0 | 20.8 |
| eBPF | qs_g1 | QS-mask | 7291 | 49088 | 16004 | 3.07 | 28.7 | 9.3 | 14.9 |
| eBPF | qsb_g8 | QS-bounds | 8910 | 57879 | 19559 | 2.96 | 33.8 | 11.4 | 25.9 |
| eBPF | qsl_g1 | QS-bpfloop | 16071 | 99943 | 35276 | 2.83 | 58.4 | 20.6 | 17.8 |

## d1_multiclass_RF_T64L64_s0 — warm_rowrep200

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | walk | C-walk | 1445 | 5995 | 3870 | 1.55 | 13.2 | 8.5 | 2.1 |
| C | qs | C-qs | 2370 | 18701 | 6329 | 2.95 | 10.9 | 3.7 | 15.2 |
| C | qs_bpf | C-qs_bpf | 2643 | 23800 | 7069 | 3.37 | 13.9 | 4.1 | 14.5 |
| C | qs_vol | C-qs_vol | 3256 | 27473 | 8716 | 3.15 | 16.0 | 5.1 | 14.4 |

## d2_multiclass_RF_T64L64_s0 — cold_repeat1

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| eBPF | grf_k32 | G-RF | 362 | 1074 | 794 | 1.35 | 5.8 | 4.3 | 5.4 |
| eBPF | grfm_k4 | G-RF-mem | 448 | 1642 | 983 | 1.67 | 8.9 | 5.3 | 5.7 |
| eBPF | rfwl_g2 | RF-walk-bpfloop | 1964 | 11486 | 4310 | 2.66 | 62.4 | 23.4 | 19.8 |
| eBPF | qs_g8 | QS-mask | 7402 | 62922 | 16248 | 3.87 | 31.8 | 8.2 | 55.8 |
| eBPF | qsb_g4 | QS-bounds | 7668 | 65970 | 16831 | 3.92 | 33.3 | 8.5 | 44.4 |
| eBPF | qsl_g1 | QS-bpfloop | 13964 | 117160 | 30652 | 3.82 | 59.2 | 15.5 | 16.9 |

## d2_multiclass_RF_T64L64_s0 — cold_rowrep1

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | walk | C-walk | 1110 | 5680 | 2925 | 1.94 | 30.8 | 15.9 | 18.7 |
| C | qs | C-qs | 2903 | 22688 | 7765 | 2.92 | 11.5 | 3.9 | 13.8 |
| C | qs_bpf | C-qs_bpf | 3223 | 28596 | 8614 | 3.32 | 14.4 | 4.3 | 14.2 |
| C | qs_vol | C-qs_vol | 3950 | 32809 | 10568 | 3.10 | 16.6 | 5.3 | 13.7 |

## d2_multiclass_RF_T64L64_s0 — cold_rowrep1_novec

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | walk | C-walk | 1164 | 6896 | 3108 | 2.22 | 37.4 | 16.9 | 19.0 |
| C | qs | C-qs | 2716 | 23872 | 7249 | 3.29 | 12.1 | 3.7 | 13.2 |
| C | qs_bpf | C-qs_bpf | 3730 | 29748 | 9967 | 2.98 | 15.0 | 5.0 | 13.8 |
| C | qs_vol | C-qs_vol | 3778 | 33961 | 10117 | 3.36 | 17.1 | 5.1 | 15.2 |

## d2_multiclass_RF_T64L64_s0 — warm_repeat200

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| eBPF | grf_k32 | G-RF | 294 | 1095 | 645 | 1.70 | 5.9 | 3.5 | 0.2 |
| eBPF | grfm_k4 | G-RF-mem | 461 | 1666 | 1013 | 1.64 | 9.0 | 5.5 | 0.2 |
| eBPF | rfwl_g2 | RF-walk-bpfloop | 2503 | 11581 | 5493 | 2.11 | 62.9 | 29.8 | 0.9 |
| eBPF | qs_g8 | QS-mask | 11517 | 63013 | 25280 | 2.49 | 31.8 | 12.8 | 13.6 |
| eBPF | qsb_g4 | QS-bounds | 12833 | 66075 | 28169 | 2.35 | 33.4 | 14.2 | 39.5 |
| eBPF | qsl_g1 | QS-bpfloop | 18057 | 117354 | 39636 | 2.96 | 59.3 | 20.0 | 15.0 |

## d2_multiclass_RF_T64L64_s0 — warm_rowrep200

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | walk | C-walk | 868 | 5697 | 2318 | 2.46 | 30.9 | 12.6 | 0.5 |
| C | qs | C-qs | 2893 | 22712 | 7740 | 2.93 | 11.5 | 3.9 | 13.0 |
| C | qs_bpf | C-qs_bpf | 3212 | 28628 | 8597 | 3.33 | 14.5 | 4.3 | 12.9 |
| C | qs_vol | C-qs_vol | 3941 | 32847 | 10549 | 3.11 | 16.6 | 5.3 | 12.0 |

## d3_binary_RF_T64L64_s0 — cold_repeat1

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| eBPF | grf_k8 | G-RF | 476 | 1591 | 1044 | 1.52 | 5.8 | 3.8 | 16.2 |
| eBPF | grfm_k4 | G-RF-mem | 582 | 2032 | 1278 | 1.59 | 7.4 | 4.7 | 16.5 |
| eBPF | rfwl_g4 | RF-walk-bpfloop | 2634 | 13377 | 5782 | 2.31 | 48.9 | 21.1 | 47.7 |
| eBPF | qsb_g1 | QS-bounds | 4988 | 52505 | 10948 | 4.80 | 30.5 | 6.4 | 14.9 |
| eBPF | qs_g4 | QS-mask | 5103 | 48610 | 11201 | 4.34 | 28.3 | 6.5 | 36.2 |
| eBPF | qsl_g1 | QS-bpfloop | 12627 | 98071 | 27716 | 3.54 | 57.1 | 16.1 | 16.3 |

## d3_binary_RF_T64L64_s0 — cold_rowrep1

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | walk | C-walk | 1278 | 3437 | 3420 | 1.00 | 12.6 | 12.5 | 47.5 |
| C | qs | C-qs | 1949 | 16744 | 5210 | 3.21 | 9.7 | 3.0 | 11.6 |
| C | qs_vol | C-qs_vol | 2244 | 25550 | 6007 | 4.25 | 14.9 | 3.5 | 10.5 |
| C | qs_bpf | C-qs_bpf | 2859 | 21862 | 7650 | 2.86 | 12.7 | 4.5 | 11.2 |

## d3_binary_RF_T64L64_s0 — cold_rowrep1_novec

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | walk | C-walk | 1196 | 3372 | 3215 | 1.05 | 12.3 | 11.7 | 47.6 |
| C | qs | C-qs | 1993 | 16758 | 5323 | 3.15 | 9.7 | 3.1 | 11.6 |
| C | qs_bpf | C-qs_bpf | 2847 | 21861 | 7618 | 2.87 | 12.7 | 4.4 | 10.3 |
| C | qs_vol | C-qs_vol | 4151 | 25549 | 11101 | 2.30 | 14.9 | 6.5 | 11.1 |

## d3_binary_RF_T64L64_s0 — warm_repeat200

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| eBPF | grf_k8 | G-RF | 442 | 1599 | 971 | 1.65 | 5.8 | 3.5 | 0.2 |
| eBPF | grfm_k4 | G-RF-mem | 540 | 2036 | 1186 | 1.72 | 7.4 | 4.3 | 0.3 |
| eBPF | rfwl_g4 | RF-walk-bpfloop | 2522 | 13400 | 5536 | 2.42 | 49.0 | 20.2 | 1.3 |
| eBPF | qsb_g1 | QS-bounds | 5721 | 52579 | 12558 | 4.19 | 30.6 | 7.3 | 13.1 |
| eBPF | qs_g4 | QS-mask | 7370 | 48670 | 16176 | 3.01 | 28.3 | 9.4 | 24.0 |
| eBPF | qsl_g1 | QS-bpfloop | 12606 | 98176 | 27671 | 3.55 | 57.1 | 16.1 | 14.8 |

## d3_binary_RF_T64L64_s0 — warm_rowrep200

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | walk | C-walk | 634 | 3440 | 1695 | 2.03 | 12.6 | 6.2 | 0.9 |
| C | qs | C-qs | 1985 | 16757 | 5313 | 3.15 | 9.7 | 3.1 | 11.1 |
| C | qs_vol | C-qs_vol | 2299 | 25572 | 6171 | 4.14 | 14.9 | 3.6 | 11.7 |
| C | qs_bpf | C-qs_bpf | 2863 | 21880 | 7676 | 2.85 | 12.7 | 4.5 | 9.0 |

## d3_multiclass_RF_T128L64_s0 — cold_repeat1

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| eBPF | grf_k16 | G-RF | 2300 | 4123 | 5050 | 0.82 | 5.7 | 7.0 | 59.6 |
| eBPF | grfm_k4 | G-RF-mem | 2737 | 5031 | 6008 | 0.84 | 7.0 | 8.4 | 60.1 |
| eBPF | rfw_g2 | RF-walk-table | 8680 | 34049 | 19053 | 1.79 | 47.5 | 26.6 | 242.8 |
| eBPF | rfwl_g4 | RF-walk-bpfloop | 9000 | 35930 | 19754 | 1.82 | 50.1 | 27.5 | 233.8 |
| eBPF | qs_g2 | QS-mask | 10432 | 103296 | 22897 | 4.51 | 28.7 | 6.4 | 23.7 |
| eBPF | qsb_g2 | QS-bounds | 10996 | 116904 | 24137 | 4.84 | 32.5 | 6.7 | 28.4 |
| eBPF | qsl_g8 | QS-bpfloop | 26090 | 217048 | 57268 | 3.79 | 60.3 | 15.9 | 95.9 |

## d3_multiclass_RF_T128L64_s0 — cold_rowrep1

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | qs | C-qs | 4170 | 35953 | 11153 | 3.22 | 10.0 | 3.1 | 15.1 |
| C | qs_vol | C-qs_vol | 4683 | 54125 | 12546 | 4.31 | 15.0 | 3.5 | 13.2 |
| C | walk | C-walk | 4946 | 8564 | 13237 | 0.65 | 11.9 | 18.5 | 233.4 |
| C | qs_bpf | C-qs_bpf | 6009 | 46675 | 16065 | 2.91 | 13.0 | 4.5 | 14.4 |

## d3_multiclass_RF_T128L64_s0 — cold_rowrep1_novec

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | qs | C-qs | 4825 | 42894 | 12922 | 3.32 | 11.9 | 3.6 | 15.1 |
| C | qs_vol | C-qs_vol | 5349 | 61037 | 14309 | 4.27 | 17.0 | 4.0 | 14.3 |
| C | walk | C-walk | 6452 | 14973 | 17231 | 0.87 | 20.9 | 24.0 | 262.1 |
| C | qs_bpf | C-qs_bpf | 6624 | 53585 | 18391 | 2.91 | 14.9 | 5.1 | 14.2 |

## d3_multiclass_RF_T128L64_s0 — warm_repeat200

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| eBPF | grf_k16 | G-RF | 1681 | 4158 | 3690 | 1.13 | 5.8 | 5.1 | 1.0 |
| eBPF | grfm_k4 | G-RF-mem | 2304 | 5069 | 5057 | 1.00 | 7.1 | 7.1 | 1.1 |
| eBPF | rfw_g2 | RF-walk-table | 8536 | 34371 | 18737 | 1.83 | 47.9 | 26.1 | 7.7 |
| eBPF | rfwl_g4 | RF-walk-bpfloop | 9119 | 36249 | 20016 | 1.81 | 50.5 | 27.9 | 8.3 |
| eBPF | qs_g2 | QS-mask | 15047 | 103361 | 33029 | 3.13 | 28.7 | 9.2 | 24.3 |
| eBPF | qsb_g2 | QS-bounds | 18766 | 116990 | 41192 | 2.84 | 32.5 | 11.4 | 27.1 |
| eBPF | qsl_g8 | QS-bpfloop | 34014 | 217151 | 74661 | 2.91 | 60.3 | 20.7 | 81.7 |

## d3_multiclass_RF_T128L64_s0 — warm_rowrep200

| side | variant | family | ns | instr | cycles | IPC | instr/work | cyc/work | br-miss |
|---|---|---|---|---|---|---|---|---|---|
| C | walk | C-walk | 2065 | 8622 | 5508 | 1.57 | 12.0 | 7.7 | 5.6 |
| C | qs | C-qs | 4147 | 35955 | 11082 | 3.24 | 10.0 | 3.1 | 13.0 |
| C | qs_bpf | C-qs_bpf | 4697 | 46678 | 12517 | 3.73 | 13.0 | 3.5 | 14.0 |
| C | qs_vol | C-qs_vol | 6019 | 54129 | 16112 | 3.36 | 15.0 | 4.5 | 13.7 |

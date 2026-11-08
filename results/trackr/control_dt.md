
### out/featdir.feat  (13704886 labelled packets, attack share 0.182)

| feature | observed min | observed max | NN-normaliser min | NN-normaliser max | share above norm. max |
|---|---|---|---|---|---|
| sport | 21 | 6.554e+04 | 0 | 6.554e+04 | 0.0000 |
| dport | 21 | 6.554e+04 | 0 | 6.554e+04 | 0.0000 |
| proto | 6 | 17 | 1 | 58.04 | 0.0000 |
| len | 40 | 2.486e+04 | 8 | 3.278e+04 | 0.0000 |
| iat | 0 | 3.008e+13 | 0 | inf | 0.0000 |
| dir | 1 | 1 | 0 | 1 | 0.0000 |
| avg_len | 40 | 5812 | 8 | 5966 | 0.0000 |
| avg_iat | 0 | 9.921e+12 | 0 | inf | 0.0000 |
| avg_dir | 1 | 1 | 0.0625 | 1 | 0.0000 |
| mad_len | 0 | 3825 | 0 | 3277 | 0.0000 |
| mad_iat | 0 | 6.82e+12 | 0 | inf | 0.0000 |
| mad_dir | 0 | 0 | 0 | 0.4853 | 0.0000 |

| seed | test acc | test F1 (attack) | top features |
|---|---|---|---|
| 0 | 0.9849 | 0.9568 | mad_iat, proto, mad_len, sport |
| 1 | 0.9848 | 0.9566 | mad_iat, proto, mad_len, sport |
| 2 | 0.9850 | 0.9571 | mad_iat, proto, mad_len, sport |

### out/featbidir.feat  (13704886 labelled packets, attack share 0.182)

| feature | observed min | observed max | NN-normaliser min | NN-normaliser max | share above norm. max |
|---|---|---|---|---|---|
| sport | 42 | 6.554e+04 | 0 | 6.554e+04 | 0.0000 |
| dport | 21 | 6.518e+04 | 0 | 6.554e+04 | 0.0000 |
| proto | 6 | 17 | 1 | 58.04 | 0.0000 |
| len | 40 | 2.486e+04 | 8 | 3.278e+04 | 0.0000 |
| iat | -1.4e+04 | 3.008e+13 | 0 | inf | 0.0000 |
| dir | 0 | 1 | 0 | 1 | 0.0000 |
| avg_len | 40 | 2677 | 8 | 5966 | 0.0000 |
| avg_iat | 0 | 1.407e+14 | 0 | inf | 0.0000 |
| avg_dir | 0.1064 | 1 | 0.0625 | 1 | 0.0000 |
| mad_len | 0 | 2794 | 0 | 3277 | 0.0000 |
| mad_iat | 0 | 7.037e+13 | 0 | inf | 0.0000 |
| mad_dir | 0 | 0.4993 | 0 | 0.4853 | 0.4213 |

| seed | test acc | test F1 (attack) | top features |
|---|---|---|---|
| 0 | 0.9911 | 0.9749 | mad_iat, proto, mad_len, dport |
| 1 | 0.9910 | 0.9747 | mad_iat, proto, mad_len, dport |
| 2 | 0.9911 | 0.9750 | mad_iat, proto, mad_len, dport |

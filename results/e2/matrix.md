| dataset/task | T | D | G-RF | G-RF-mem | G-RF-x | QS-mask | QS-bounds | QS-bpfloop | RF-walk-table | RF-walk-bpfloop |
|---|---|---|---|---|---|---|---|---|---|---|
| d1/binary | 16 | 4 | 0.22 µs (grf_k16) | 0.24 µs (grfm_k16) | 0.27 µs (grfx_k16) | 0.69 µs (qs_g1) | 0.86 µs (qsb_g1) | 1.55 µs (qsl_g2) | 0.52 µs (rfw_g2) | 0.63 µs (rfwl_g2) |
| d1/binary | 16 | 6 | 0.32 µs (grf_k4) | 0.30 µs (grfm_k8) | 0.31 µs (grfx_k16) | 1.85 µs (qs_g2) | 1.99 µs (qsb_g1) | 3.57 µs (qsl_g1) | 0.95 µs (rfw_g4) | 0.96 µs (rfwl_g8) |
| d1/binary | 16 | 8 | 0.34 µs (grf_k4) | 0.36 µs (grfm_k4) | 0.37 µs (grfx_k16) | 4.18 µs (qs_g4) | 4.68 µs (qsb_g2) | 7.35 µs (qsl_g2) | 1.21 µs (rfw_g4) | 0.85 µs (rfwl_g4) |
| d1/binary | 256 | 4 | 2.79 µs (grf_k8) | 2.83 µs (grfm_k8) | 2.75 µs (grfx_k64) | 7.24 µs (qs_g2) | 11.11 µs (qsb_g2) | 15.14 µs (qsl_g2) | 7.13 µs (rfw_g8) | 10.14 µs (rfwl_g1) |
| d1/binary | 256 | 6 | ✗ | ✗ | 3.12 µs (grfx_k128) | 25.35 µs (qs_g8) | 14.57 µs (qsb_g1) | 35.28 µs (qsl_g1) | 11.90 µs (rfw_g4) | 10.92 µs (rfwl_g2) |
| d1/binary | 256 | 8 | ✗ | ✗ | 4.06 µs (grfx_k64) | 87.16 µs (qs_g8) | 58.46 µs (qsb_g4) | 104.60 µs (qsl_g1) | 16.24 µs (rfw_g2) | 16.33 µs (rfwl_g2) |
| d1/binary | 64 | 4 | 0.51 µs (grf_k32) | 0.76 µs (grfm_k8) | 0.52 µs (grfx_k16) | 2.25 µs (qs_g2) | 2.54 µs (qsb_g2) | 4.46 µs (qsl_g1) | 1.90 µs (rfw_g4) | 2.35 µs (rfwl_g4) |
| d1/binary | 64 | 6 | 1.04 µs (grf_k4) | 1.13 µs (grfm_k4) | 0.59 µs (grfx_k64) | 5.13 µs (qs_g1) | 4.79 µs (qsb_g1) | 7.60 µs (qsl_g1) | 3.94 µs (rfw_g2) | 3.10 µs (rfwl_g2) |
| d1/binary | 64 | 8 | 1.16 µs (grf_k4) | 1.18 µs (grfm_k4) | 0.47 µs (grfx_k64) | 18.26 µs (qs_g2) | 13.03 µs (qsb_g2) | 35.61 µs (qsl_g1) | 4.24 µs (rfw_g4) | 4.39 µs (rfwl_g8) |
| d1/multiclass | 16 | 4 | 0.28 µs (grf_k8) | 0.31 µs (grfm_k8) | 0.17 µs (grfx_k16) | 1.11 µs (qs_g1) | 1.32 µs (qsb_g1) | 1.85 µs (qsl_g1) | 0.80 µs (rfw_g2) | 0.80 µs (rfwl_g1) |
| d1/multiclass | 16 | 6 | 0.33 µs (grf_k8) | 0.31 µs (grfm_k16) | 0.20 µs (grfx_k8) | 1.74 µs (qs_g1) | 2.12 µs (qsb_g1) | 3.29 µs (qsl_g1) | 1.11 µs (rfw_g2) | 1.29 µs (rfwl_g2) |
| d1/multiclass | 16 | 8 | 0.42 µs (grf_k4) | 0.45 µs (grfm_k4) | 0.25 µs (grfx_k16) | 3.44 µs (qs_g4) | 4.79 µs (qsb_g1) | 7.33 µs (qsl_g4) | 1.27 µs (rfw_g2) | 1.37 µs (rfwl_g4) |
| d1/multiclass | 256 | 4 | 3.28 µs (grf_k8) | 3.31 µs (grfm_k8) | 2.06 µs (grfx_k64) | 7.99 µs (qs_g8) | 8.24 µs (qsb_g1) | 16.13 µs (qsl_g2) | 6.60 µs (rfw_g8) | 8.38 µs (rfwl_g2) |
| d1/multiclass | 256 | 6 | ✗ | ✗ | 2.18 µs (grfx_k256) | 15.66 µs (qs_g1) | 20.94 µs (qsb_g1) | 40.35 µs (qsl_g8) | 13.21 µs (rfw_g2) | 15.54 µs (rfwl_g4) |
| d1/multiclass | 256 | 8 | ✗ | ✗ | 3.18 µs (grfx_k64) | 84.59 µs (qs_g4) | 51.82 µs (qsb_g4) | 110.27 µs (qsl_g1) | 19.52 µs (rfw_g4) | 17.97 µs (rfwl_g2) |
| d1/multiclass | 64 | 4 | 0.67 µs (grf_k16) | 0.75 µs (grfm_k8) | 0.41 µs (grfx_k32) | 2.54 µs (qs_g2) | 2.82 µs (qsb_g2) | 4.24 µs (qsl_g2) | 2.09 µs (rfw_g4) | 2.18 µs (rfwl_g4) |
| d1/multiclass | 64 | 6 | 0.89 µs (grf_k8) | 1.12 µs (grfm_k4) | 0.60 µs (grfx_k64) | 4.87 µs (qs_g1) | 6.06 µs (qsb_g4) | 10.49 µs (qsl_g2) | 3.92 µs (rfw_g4) | 4.00 µs (rfwl_g2) |
| d1/multiclass | 64 | 8 | 1.24 µs (grf_k4) | 1.18 µs (grfm_k4) | 0.79 µs (grfx_k64) | 23.56 µs (qs_g2) | 16.83 µs (qsb_g4) | 33.91 µs (qsl_g4) | 4.07 µs (rfw_g2) | 4.49 µs (rfwl_g4) |
| d1/binary | 128 | 8 | 2.20 µs (grf_k4) | 3.03 µs (grfm_k4) | 2.01 µs (grfx_k64) | 36.69 µs (qs_g4) | 22.92 µs (qsb_g2) | 58.77 µs (qsl_g8) | 7.16 µs (rfw_g8) | 7.62 µs (rfwl_g4) |
| d1/binary | 16 | 10 | 0.33 µs (grf_k16) | 0.44 µs (grfm_k4) | 0.42 µs (grfx_k4) | 7.25 µs (qs_g1) | 12.09 µs (qsb_g4) | 13.04 µs (qsl_g4) | 1.70 µs (rfw_g8) | 1.56 µs (rfwl_g2) |
| d1/binary | 16 | 12 | 0.45 µs (grf_k4) | 0.42 µs (grfm_k4) | 0.43 µs (grfx_k16) | ✗ | 12.99 µs (qsb_g8) | 33.79 µs (qsl_g1) | 2.06 µs (rfw_g8) | 1.74 µs (rfwl_g4) |
| d1/binary | 64 | 10 | 1.32 µs (grf_k4) | 1.41 µs (grfm_k4) | 1.03 µs (grfx_k64) | ✗ | ✗ | 40.38 µs (qsl_g2) | ✗ | 5.09 µs (rfwl_g4) |
| d1/binary | 64 | 12 | 1.11 µs (grf_k4) | 1.51 µs (grfm_k4) | 1.10 µs (grfx_k64) | ✗ | 49.08 µs (qsb_g2) | 123.24 µs (qsl_g4) | ✗ | 5.51 µs (rfwl_g8) |
| d1/multiclass | 16 | 10 | 0.32 µs (grf_k8) | 0.40 µs (grfm_k4) | 0.34 µs (grfx_k4) | 18.05 µs (qs_g8) | 11.47 µs (qsb_g2) | 21.29 µs (qsl_g2) | 1.65 µs (rfw_g2) | 1.67 µs (rfwl_g1) |
| d1/multiclass | 16 | 12 | 0.33 µs (grf_k16) | 0.42 µs (grfm_k4) | 0.34 µs (grfx_k4) | ✗ | 20.00 µs (qsb_g2) | 34.43 µs (qsl_g4) | ✗ | 1.69 µs (rfwl_g1) |
| d1/multiclass | 64 | 10 | 1.03 µs (grf_k16) | 1.41 µs (grfm_k4) | 0.72 µs (grfx_k64) | 64.10 µs (qs_g4) | 28.88 µs (qsb_g1) | 78.16 µs (qsl_g4) | 6.39 µs (rfw_g8) | 6.17 µs (rfwl_g1) |
| d1/multiclass | 64 | 12 | 1.66 µs (grf_k4) | 1.80 µs (grfm_k4) | 0.82 µs (grfx_k64) | ✗ | 58.30 µs (qsb_g2) | 134.68 µs (qsl_g2) | ✗ | 7.65 µs (rfwl_g8) |
| d3/binary | 32 | 8 | 0.62 µs (grf_k4) | 0.65 µs (grfm_k4) | 0.44 µs (grfx_k8) | 17.71 µs (qs_g8) | 11.63 µs (qsb_g1) | 29.29 µs (qsl_g2) | 1.96 µs (rfw_g2) | 2.24 µs (rfwl_g1) |
| d3/binary | 64 | 12 | 1.93 µs (grf_k2) | 2.31 µs (grfm_k2) | 1.00 µs (grfx_k16) | ✗ | ✗ | 526.59 µs (qsl_g8) | ✗ | 5.60 µs (rfwl_g4) |
| d3/multiclass | 16 | 12 | 0.54 µs (grf_k4) | 0.28 µs (grfm_k16) | 0.25 µs (grfx_k16) | ✗ | ✗ | 485.79 µs (qsl_g8) | 1.77 µs (rfw_g8) | 1.77 µs (rfwl_g1) |
| d3/multiclass | 16 | 4 | 0.17 µs (grf_k16) | 0.22 µs (grfm_k8) | 0.23 µs (grfx_k16) | 1.04 µs (qs_g1) | 1.31 µs (qsb_g1) | 1.93 µs (qsl_g4) | 0.72 µs (rfw_g8) | 0.61 µs (rfwl_g8) |
| d3/multiclass | 16 | 8 | 0.24 µs (grf_k16) | 0.33 µs (grfm_k4) | 0.24 µs (grfx_k4) | 11.32 µs (qs_g4) | 19.69 µs (qsb_g8) | 13.46 µs (qsl_g1) | 1.19 µs (rfw_g2) | 1.23 µs (rfwl_g1) |
| d3/multiclass | 256 | 8 | 8.97 µs (grf_k16) | ✗ | 6.98 µs (grfx_k128) | ✗ | ✗ | 158.94 µs (qsl_g2) | 16.32 µs (rfw_g8) | 20.69 µs (rfwl_g1) |
| d3/multiclass | 32 | 12 | 1.21 µs (grf_k4) | 1.37 µs (grfm_k2) | 0.95 µs (grfx_k32) | ✗ | ✗ | 944.99 µs (qsl_g2) | ✗ | 3.72 µs (rfwl_g1) |
| d3/multiclass | 32 | 8 | 0.60 µs (grf_k16) | 0.82 µs (grfm_k4) | 0.59 µs (grfx_k16) | 18.35 µs (qs_g4) | 21.45 µs (qsb_g4) | 21.68 µs (qsl_g4) | 2.59 µs (rfw_g8) | 2.26 µs (rfwl_g2) |
| d3/multiclass | 64 | 8 | 1.47 µs (grf_k16) | 2.10 µs (grfm_k4) | 1.00 µs (grfx_k64) | ✗ | 48.71 µs (qsb_g8) | 45.37 µs (qsl_g2) | 5.34 µs (rfw_g2) | 4.91 µs (rfwl_g8) |
| d2/binary | 128 | 8 | 2.27 µs (grf_k4) | 2.38 µs (grfm_k4) | 1.46 µs (grfx_k128) | 21.60 µs (qs_g8) | ✗ | 32.58 µs (qsl_g4) | 6.38 µs (rfw_g8) | 7.18 µs (rfwl_g2) |
| d2/binary | 16 | 12 | 0.38 µs (grf_k4) | 0.38 µs (grfm_k4) | 0.27 µs (grfx_k16) | 22.51 µs (qs_g1) | 9.93 µs (qsb_g4) | 22.19 µs (qsl_g2) | 1.28 µs (rfw_g8) | 1.25 µs (rfwl_g1) |
| d2/multiclass | 128 | 8 | 3.03 µs (grf_k4) | 2.23 µs (grfm_k4) | 1.83 µs (grfx_k64) | 50.84 µs (qs_g8) | 38.63 µs (qsb_g8) | 68.83 µs (qsl_g1) | 8.46 µs (rfw_g8) | 9.95 µs (rfwl_g2) |
| d2/multiclass | 16 | 8 | 0.38 µs (grf_k8) | 0.38 µs (grfm_k4) | 0.28 µs (grfx_k8) | 7.41 µs (qs_g1) | 4.94 µs (qsb_g4) | 10.91 µs (qsl_g1) | 1.43 µs (rfw_g4) | 1.42 µs (rfwl_g1) |
| d2/multiclass | 32 | 12 | 0.61 µs (grf_k16) | 0.95 µs (grfm_k2) | 0.29 µs (grfx_k16) | ✗ | ✗ | 164.29 µs (qsl_g1) | ✗ | 2.77 µs (rfwl_g4) |
| d1/binary | 128 | 0 | 2.35 µs (grf_k4) | 2.17 µs (grfm_k4) | 2.08 µs (grfx_k64) | 16.23 µs (qs_g8) | 10.02 µs (qsb_g2) | 25.02 µs (qsl_g4) | ✗ | 6.97 µs (rfwl_g4) |
| d1/binary | 256 | 0 | ✗ | ✗ | 3.12 µs (grfx_k256) | 25.32 µs (qs_g1) | 20.52 µs (qsb_g2) | 43.67 µs (qsl_g1) | ✗ | 16.00 µs (rfwl_g8) |
| d1/binary | 512 | 0 | ✗ | ✗ | 7.39 µs (grfx_k512) | 46.74 µs (qs_g2) | 45.42 µs (qsb_g2) | 91.37 µs (qsl_g2) | ✗ | 41.73 µs (rfwl_g2) |
| d1/binary | 64 | 0 | 1.04 µs (grf_k4) | 1.18 µs (grfm_k4) | 0.69 µs (grfx_k32) | 5.34 µs (qs_g1) | 6.35 µs (qsb_g1) | 14.58 µs (qsl_g1) | ✗ | 4.79 µs (rfwl_g2) |
| d1/multiclass | 128 | 0 | 2.19 µs (grf_k4) | 2.79 µs (grfm_k4) | 1.45 µs (grfx_k128) | 15.86 µs (qs_g8) | 14.34 µs (qsb_g2) | 27.99 µs (qsl_g1) | 7.73 µs (rfw_g2) | 8.29 µs (rfwl_g1) |
| d1/multiclass | 256 | 0 | ✗ | ✗ | 3.14 µs (grfx_k128) | 29.41 µs (qs_g1) | 22.46 µs (qsb_g2) | 51.85 µs (qsl_g2) | 15.61 µs (rfw_g2) | 18.20 µs (rfwl_g2) |
| d1/multiclass | 512 | 0 | ✗ | ✗ | 7.88 µs (grfx_k256) | ✗ | 47.28 µs (qsb_g4) | 84.21 µs (qsl_g1) | 33.86 µs (rfw_g4) | 40.67 µs (rfwl_g8) |
| d1/multiclass | 64 | 0 | 1.19 µs (grf_k4) | 1.20 µs (grfm_k4) | 0.68 µs (grfx_k16) | 6.57 µs (qs_g1) | 8.47 µs (qsb_g8) | 15.91 µs (qsl_g1) | 3.72 µs (rfw_g4) | 4.65 µs (rfwl_g1) |
| d3/binary | 128 | 0 | 1.70 µs (grf_k4) | 1.88 µs (grfm_k4) | 0.81 µs (grfx_k128) | 11.51 µs (qs_g8) | 13.43 µs (qsb_g1) | 27.98 µs (qsl_g1) | ✗ | 5.05 µs (rfwl_g2) |
| d3/binary | 256 | 0 | ✗ | ✗ | 2.33 µs (grfx_k128) | 34.70 µs (qs_g1) | 28.92 µs (qsb_g4) | 56.45 µs (qsl_g8) | ✗ | 11.06 µs (rfwl_g1) |
| d3/binary | 512 | 0 | ✗ | ✗ | 5.55 µs (grfx_k256) | ✗ | 50.87 µs (qsb_g2) | 90.21 µs (qsl_g4) | ✗ | 23.41 µs (rfwl_g1) |
| d3/binary | 64 | 0 | 0.69 µs (grf_k8) | 0.94 µs (grfm_k4) | 0.41 µs (grfx_k64) | 5.47 µs (qs_g4) | 6.15 µs (qsb_g1) | 18.30 µs (qsl_g1) | ✗ | 3.09 µs (rfwl_g4) |
| d3/multiclass | 128 | 0 | 2.23 µs (grf_k16) | 2.46 µs (grfm_k4) | 1.51 µs (grfx_k64) | 14.26 µs (qs_g2) | 14.78 µs (qsb_g2) | 29.61 µs (qsl_g8) | 6.33 µs (rfw_g2) | 7.49 µs (rfwl_g4) |
| d3/multiclass | 256 | 0 | 4.12 µs (grf_k16) | ✗ | 4.21 µs (grfx_k128) | 35.45 µs (qs_g1) | 26.64 µs (qsb_g4) | 54.39 µs (qsl_g1) | 14.09 µs (rfw_g4) | 17.39 µs (rfwl_g8) |
| d3/multiclass | 512 | 0 | ✗ | ✗ | 8.92 µs (grfx_k256) | 49.56 µs (qs_g2) | 63.80 µs (qsb_g8) | 104.57 µs (qsl_g8) | 40.40 µs (rfw_g8) | 34.99 µs (rfwl_g4) |
| d3/multiclass | 64 | 0 | 1.17 µs (grf_k8) | 1.26 µs (grfm_k4) | 0.71 µs (grfx_k64) | 7.69 µs (qs_g1) | 6.59 µs (qsb_g2) | 13.45 µs (qsl_g2) | 3.53 µs (rfw_g8) | 3.43 µs (rfwl_g4) |
| d2/binary | 128 | 0 | 1.25 µs (grf_k8) | 1.72 µs (grfm_k4) | 0.86 µs (grfx_k32) | 11.12 µs (qs_g1) | 12.87 µs (qsb_g8) | 24.35 µs (qsl_g1) | ✗ | 4.21 µs (rfwl_g1) |
| d2/binary | 256 | 0 | 2.39 µs (grf_k8) | ✗ | 1.65 µs (grfx_k128) | 27.42 µs (qs_g1) | 17.86 µs (qsb_g2) | 43.83 µs (qsl_g2) | ✗ | 8.60 µs (rfwl_g1) |
| d2/binary | 512 | 0 | ✗ | ✗ | 4.03 µs (grfx_k512) | ✗ | 47.34 µs (qsb_g4) | 89.96 µs (qsl_g4) | ✗ | 18.05 µs (rfwl_g4) |
| d2/binary | 64 | 0 | 0.44 µs (grf_k64) | 0.97 µs (grfm_k4) | 0.52 µs (grfx_k32) | 6.85 µs (qs_g2) | 5.70 µs (qsb_g2) | 11.60 µs (qsl_g2) | ✗ | 2.27 µs (rfwl_g4) |
| d2/multiclass | 128 | 0 | 1.31 µs (grf_k16) | 1.84 µs (grfm_k4) | 0.74 µs (grfx_k64) | 16.51 µs (qs_g1) | 18.03 µs (qsb_g4) | 30.91 µs (qsl_g1) | ✗ | 4.90 µs (rfwl_g8) |
| d2/multiclass | 256 | 0 | 3.42 µs (grf_k8) | ✗ | 1.84 µs (grfx_k128) | ✗ | 29.80 µs (qsb_g8) | 60.15 µs (qsl_g1) | ✗ | 7.99 µs (rfwl_g1) |
| d2/multiclass | 512 | 0 | ✗ | ✗ | 5.92 µs (grfx_k512) | 59.23 µs (qs_g2) | 63.80 µs (qsb_g8) | 113.11 µs (qsl_g1) | ✗ | 17.39 µs (rfwl_g2) |
| d2/multiclass | 64 | 0 | 0.54 µs (grf_k32) | 0.90 µs (grfm_k4) | 0.39 µs (grfx_k16) | 10.18 µs (qs_g8) | 13.74 µs (qsb_g4) | 16.28 µs (qsl_g1) | ✗ | 2.43 µs (rfwl_g2) |

# Vocabulary seeding test

Seed V = submitted single-agent runs; D = submitted 3-agent debate runs; N = no seed. Held-out = post-fix session runs. Values: pass a / pass b.

| domain | seed | coverage | seed canon/tech | new canon/tech | stab v1 | stab d3 | Δ debate | repro a~b |
|---|---|---|---|---|---|---|---|---|
| microelectronics | V | 0.19 / 0.19 | 11 / 11 | 0 / 0 | 0.839 / 0.833 | 0.787 / 0.765 | -0.049 / -0.046 | 0.96 |
| microelectronics | D | 0.22 / 0.22 | 10 / 10 | 0 / 0 | 0.833 / 0.857 | 0.671 / 0.667 | -0.143 / -0.154 | 0.93 |
| microelectronics | N | 0.00 / 0.00 | 0 / 0 | 12 / 12 | 0.667 / 0.667 | 0.625 / 0.600 | -0.051 / -0.036 | 0.95 |
| biotech | V | 0.15 / 0.15 | 11 / 11 | 0 / 0 | 0.833 / 0.833 | 0.699 / 0.704 | -0.097 / -0.073 | 0.95 |
| biotech | D | 0.17 / 0.17 | 9 / 9 | 0 / 0 | 0.857 / 0.857 | 0.750 / 0.750 | -0.118 / -0.119 | 0.95 |
| biotech | N | 0.00 / 0.00 | 0 / 0 | 12 / 11 | 0.625 / 0.667 | 0.595 / 0.567 | -0.030 / -0.067 | 0.95 |
| pharma | V | 0.14 / 0.14 | 11 / 11 | 0 / 0 | 0.833 / 0.833 | 0.750 / 0.750 | -0.101 / -0.108 | 0.92 |
| pharma | D | 0.17 / 0.17 | 9 / 9 | 0 / 0 | 0.833 / 0.833 | 0.714 / 0.714 | -0.122 / -0.143 | 0.92 |
| pharma | N | 0.00 / 0.00 | 0 / 0 | 12 / 11 | 0.646 / 0.667 | 0.598 / 0.571 | -0.084 / -0.096 | 0.95 |

## Paired per-tech tests on held-out stability (median of per-tech difference, Wilcoxon p)

| domain | runs | D − V (a) | D − V (b) | V − N (a) | V − N (b) | D − N (a) | D − N (b) |
|---|---|---|---|---|---|---|---|
| microelectronics | v1 | +0.000 p=0.097 | +0.000 p=0.72 | +0.174 p=4e-10 | +0.216 p=1.3e-09 | +0.187 p=1.9e-08 | +0.195 p=5.6e-10 |
| microelectronics | d3 | -0.053 p=0.0001 | -0.049 p=0.00034 | +0.133 p=2.2e-09 | +0.161 p=2.8e-09 | +0.066 p=0.0015 | +0.067 p=0.00014 |
| biotech | v1 | +0.029 p=0.00071 | +0.000 p=0.096 | +0.200 p=2.4e-09 | +0.167 p=2.7e-10 | +0.244 p=1.9e-10 | +0.218 p=2.6e-10 |
| biotech | d3 | +0.025 p=0.11 | +0.000 p=0.69 | +0.079 p=6.4e-07 | +0.100 p=5.2e-07 | +0.118 p=4.8e-08 | +0.083 p=3.5e-09 |
| pharma | v1 | +0.000 p=0.12 | +0.000 p=0.28 | +0.177 p=7.7e-10 | +0.149 p=6.3e-09 | +0.190 p=1.5e-09 | +0.165 p=2.2e-08 |
| pharma | d3 | +0.000 p=0.78 | +0.000 p=0.66 | +0.132 p=1.4e-09 | +0.104 p=3.8e-09 | +0.101 p=5.5e-09 | +0.083 p=8.2e-09 |

## Cross-seed agreement on held-out names (pair-F1, median per tech)

- V vs D, pass a: 0.78 (n=180)
- V vs D, pass b: 0.76 (n=180)

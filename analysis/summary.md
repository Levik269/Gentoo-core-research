# kbench — computed summary

## 1. Controlled comparison (turbo OFF, fixed base frequency)

Median of 7 measured iterations. **Bold** = fastest for that test.

| test | unit | 6.18 vanilla | zen 7.2.7 | Arch 7.0.3 | winner (margin) |
|------|------|---:|---:|---:|---|
| sched_context | bogo_ops_s ↑ | 52,782 | 52,674 | **59,866** | Arch 7.0.3 (+13.4%) |
| sched_switch | bogo_ops_s ↑ | **5,197,917** | 4,466,560 | 4,588,882 | 6.18 vanilla (+13.3%) |
| ipc_pipe | bogo_ops_s ↑ | 10,856,546 | **14,374,799** | 9,488,391 | zen 7.2.7 (+32.4%) |
| futex | bogo_ops_s ↑ | **1,061,703** | 843,919 | 989,263 | 6.18 vanilla (+7.3%) |
| syscall | bogo_ops_s ↑ | 959 | 977 | **1,001** | Arch 7.0.3 (+2.4%) |
| memcpy | bogo_ops_s ↑ | **3,059** | 3,058 | 2,863 | 6.18 vanilla (+0.0%) |
| sysbench_cpu | events_s ↑ | **9,900** | 9,886 | 9,783 | 6.18 vanilla (+0.1%) |
| sysbench_threads | avg_latency_ms ↓ | 2.35 | **2.33** | 2.56 | zen 7.2.7 (+0.9%) |
| sysbench_memory | MiB_s ↑ | **79,415** | 76,042 | 75,755 | 6.18 vanilla (+4.4%) |

## 2. Turbo-boost effect (how much turbo inflated each result)

Positive = the turbo-ON run beat the fixed-frequency run. Direction respects higher/lower-is-better.

| test | Arch turbo gain | zen turbo gain |
|------|---:|---:|
| sched_context | +52% | +24% |
| sched_switch | +40% | +13% |
| ipc_pipe | +38% | +5% |
| futex | +58% | +40% |
| syscall | -32% | -32% |
| memcpy | +41% | +14% |
| sysbench_cpu | +62% | +35% |
| sysbench_threads | +37% | -9% |
| sysbench_memory | +75% | +73% |

## 3. How turbo flips the verdict (Arch vs zen)

zen-vs-Arch advantage (+ = zen faster). Compare default (turbo on) to controlled.

| test | default (turbo on) | controlled (turbo off) | flipped? |
|------|---:|---:|:---:|
| sched_context | -28% | -12% |  |
| sched_switch | -22% | -3% |  |
| ipc_pipe | +15% | +51% |  |
| futex | -24% | -15% |  |
| syscall | -2% | -2% |  |
| memcpy | -14% | +7% | yes |
| sysbench_cpu | -16% | +1% | yes |
| sysbench_threads | -58% | +9% | yes |
| sysbench_memory | -1% | +0% | yes |

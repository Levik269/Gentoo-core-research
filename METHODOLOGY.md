# Methodology & full analysis

Detailed companion to the [README](README.md). Covers the kernels, the benchmark
suite, how measurements were controlled, the full results, the analysis, and the
threats to validity.

Hardware: Acer Predator Helios Neo 16 (PHN16-71) · Intel Core i5-13500HX
(14C/20T, Raptor Lake) · 16 GB DDR5 · dual-boot Arch / Gentoo.

---

## 1. Motivation

"I built a custom kernel, is it faster?" is easy to ask and easy to answer badly.
A laptop CPU spends most of a benchmark deciding how hard to boost, so two kernels
can post very different numbers for reasons that have nothing to do with the kernel.
This project measures the kernel-owned parts of the system (the scheduler, context
switching, IPC, syscalls, synchronisation, memory) and then **controls the one
variable that usually dominates laptop benchmarks: turbo boost.**

## 2. Kernels under test

| label | kernel | source / tuning | preemption | compiler |
|-------|--------|-----------------|-----------|----------|
| **Arch 7.0.3** | `7.0.3-arch1-2` | distro stock `linux`, generic `-O2` | `PREEMPT` (full) | gcc 16.1.1 |
| **zen 7.2.7** | `7.2.7-zen1` | Gentoo `zen-sources`, `ZEN_INTERACTIVE`, trimmed config | `PREEMPT` (full) | gcc 15.2.1 |
| **6.18 vanilla** | `6.18.35-gentoo-r1` | Gentoo `gentoo-sources`, hand-rolled config | `PREEMPT_VOLUNTARY` | gcc 15.2.1 |

**All three kernels are built for generic `x86-64`, not `-march=native`.**
I verified this in the shipped configs: every one has
`# CONFIG_X86_NATIVE_CPU is not set`. (A Gentoo `make.conf` `CFLAGS` does *not*
propagate to a manual kernel `make`; `-march=native` would only apply if passed
explicitly as `KCFLAGS`, which was not done here.) So the kernels share one ISA
baseline, which is actually cleaner for isolating the kernel — but it also means
any `-march`-based explanation is invalid (see §6.3).

The userspace **binaries** are the same *versions* everywhere (stress-ng 0.21.04,
sysbench 1.0.20), but **not the same builds**: on Gentoo they are compiled from
source against a from-source glibc, on Arch they are the distro's prebuilt
packages. That difference is a known confound for any userspace-heavy stressor
(see §6.3 and §7). Kernel configs are in [`configs/`](configs/).

Note also the **preemption model differs**: 6.18 ships `PREEMPT_VOLUNTARY`, while
zen 7.2.7 and Arch use full `PREEMPT`. This matters for the controlled 6.18-vs-zen
comparison (see §6.2).

## 3. Benchmarks (kernel-centric)

| test | tool | what it stresses |
|------|------|------------------|
| `sched_context` | stress-ng | context-switch throughput |
| `sched_switch` | stress-ng | scheduler switch rate |
| `ipc_pipe` | stress-ng | pipe IPC throughput |
| `futex` | stress-ng | futex / synchronisation |
| `syscall` | stress-ng | syscall entry/exit overhead |
| `memcpy` | stress-ng | memory copy (sensitive to `-march`) |
| `sysbench_cpu` | sysbench | prime compute (frequency-bound control) |
| `sysbench_threads` | sysbench | thread scheduling **latency** (lower = better) |
| `sysbench_memory` | sysbench | memory bandwidth |

Pure userspace throughput (e.g. `openssl speed`) is deliberately excluded: it would
mostly measure the three different libc/toolchain builds, not the kernel.

## 4. Measurement protocol

Everything is driven by [`tools/kbench.sh`](tools/kbench.sh). For every test:

- **governor → `performance`** on all 20 logical CPUs (restored on exit).
- **2 warm-up iterations discarded, then 7 measured** — warm-up absorbs the
  turbo transient on a cold CPU, which otherwise inflates the first runs.
- **cool-down between every iteration** to a package-temperature target, read
  from `coretemp` via `lm_sensors`, so each run starts from an equal thermal state.
- **median + sample stddev + min/max** over the 7 measured runs. Median is robust;
  stddev reports spread. A one-off mis-parsed stress-ng row is rejected by an
  outlier guard (>10× the running median).
- Run from a **bare TTY** (no desktop/compositor) on every kernel.

The **controlled (`-ctl`) regime** adds:

- **turbo boost disabled** (`intel_pstate/no_turbo`), so the CPU is pinned to its
  base frequency and the comparison is clock-for-clock;
- cool target 50 °C, 10 s runs, and the **package temperature logged after each
  run** (the `dT` in the logs) to confirm no in-run thermal throttling
  (observed dT ≤ +11 °C, nowhere near the ~100 °C throttle point).

Raw per-run numbers, environment capture and full transcripts are in
[`results/`](results/) (`*.csv`, `*.env`, `*.log`).

## 5. Full results

### 5.1 Controlled — turbo off, clock-for-clock

Median of 7 runs. **Bold** = fastest for that test. Relative σ was ≤ 4 % on every
cell and < 1 % on most (turbo-off makes the machine extremely repeatable).

| test | unit | 6.18 vanilla | zen 7.2.7 | Arch 7.0.3 | winner (margin) |
|------|------|---:|---:|---:|---|
| sched_context | bogo-ops/s ↑ | 52,782 | 52,674 | **59,866** | Arch (+13 %) |
| sched_switch | bogo-ops/s ↑ | **5,197,917** | 4,466,560 | 4,588,882 | 6.18 (+13 %) |
| ipc_pipe | bogo-ops/s ↑ | 10,856,546 | **14,374,799** | 9,488,391 | zen (+32 %) |
| futex | bogo-ops/s ↑ | **1,061,703** | 843,919 | 989,263 | 6.18 (+7 %) |
| syscall | bogo-ops/s ↑ | 959 | 977 | **1,001** | Arch (+2 %) |
| memcpy | bogo-ops/s ↑ | **3,059** | 3,058 | 2,863 | Gentoo ×2 (+7 % vs Arch) |
| sysbench_cpu | events/s ↑ | **9,900** | 9,886 | 9,783 | tie (+0–1 %) |
| sysbench_threads | ms latency ↓ | 2.35 | **2.33** | 2.56 | Gentoo ×2 (−9 % vs Arch) |
| sysbench_memory | MiB/s ↑ | **79,415** | 76,042 | 75,755 | 6.18 (+4 %) |

No kernel wins across the board. The spread of winners is the result.

### 5.2 The turbo effect

With turbo **on**, the same hardware reports 38–75 % higher throughput on most
tests — and Arch boosts harder than the Gentoo zen build almost everywhere.

![turbo effect](figures/fig2_turbo_effect.png)

### 5.3 Turbo flips the verdict

The headline comparison (zen vs Arch) changes sign on **four of nine tests** once
turbo is removed. `sysbench_threads` swings from Arch **+58 %** ahead to zen
**+9 %** ahead; `memcpy` and `sysbench_cpu` likewise flip to Gentoo.

![turbo flips](figures/fig3_turbo_flips.png)

## 6. Analysis

**1. Most of the "stock Arch is faster" story was turbo, not the kernel.**
At a fixed base clock the kernels are within a few percent on compute and memory,
and the large gaps collapse (`sched_switch` from +22 % to +3 %; `sched_context`
from +39 % to +13 %).

**2. `zen` loses scheduler/sync throughput — but the cause is confounded.**
Comparing `zen` 7.2.7 against vanilla 6.18 (same distro, same gcc 15.2.1, both
turbo-off), `zen` **loses** `sched_switch` (−14 %) and `futex` (−20 %) but **wins**
`ipc_pipe` (+32 %). It is tempting to credit `ZEN_INTERACTIVE`, but **this pair is
not a clean A/B**: the two kernels also differ in *preemption model* — 6.18 is
`PREEMPT_VOLUNTARY`, zen is full `PREEMPT`. Full preemption adds scheduling points
that reduce context-switch and lock throughput under a 20-thread load, which is
*exactly* where zen loses (`sched_switch`, `futex`). So preemption is at least as
plausible an explanation as the zen patch set, and the two are not separated by
this experiment. Either way the pattern reads as a latency-oriented configuration
trading throughput, not a kernel that is simply "slower". Isolating `ZEN_INTERACTIVE`
from the preemption model would need a build that holds preemption fixed (see §9).

**3. The `memcpy` gap is a userspace artifact, not the kernel.** Both Gentoo builds
(3,058–3,059) beat Arch (2,863) in `memcpy` by ~7 %. My first reading blamed
`-march=native` — but the configs show no kernel is built with it (§2), and more
importantly stress-ng's `memcpy` stressor copies in **user space** via libc
`memcpy(3)`; the kernel is barely involved. The gap therefore almost certainly
comes from the userspace build difference — Gentoo's from-source glibc and stress-ng
versus Arch's prebuilt binaries — i.e. precisely the toolchain/userspace confound
this study tried to exclude (§3, §7). It is kept here as an honest example of that
confound leaking in, not as a kernel result.

**4. A counter-intuitive but repeatable syscall inversion.** On all kernels `syscall`
throughput is *higher* with turbo off (~1000 vs ~665–680). Under a 20-thread load,
per-core turbo frequency jitter appears to hurt a tight, uniform syscall stream more
than the lower-but-steady base clock does.

**5. Thermals, as a side observation.** The Gentoo builds idle/recover cooler than
stock Arch, and 6.18 would not drop below ~53 °C at idle where 7.2/Arch reach 50 °C
(see Limitations). On this chassis the EC fan curve and hardware thermal throttle
keep the CPU well inside spec regardless of distro.

## 7. Limitations & threats to validity

Stated plainly, because they bound the conclusions:

- **Preemption model is not held constant.** 6.18 is `PREEMPT_VOLUNTARY`; zen and
  Arch are full `PREEMPT`. This confounds the controlled 6.18-vs-zen comparison on
  exactly the scheduler/synchronisation tests where they differ most
  (`sched_switch`, `futex`), so that pair does **not** cleanly isolate the zen patch
  set. See §6.2.
- **Userspace builds differ even at equal versions.** stress-ng and sysbench are the
  same versions everywhere but Gentoo compiles them (and glibc) from source while
  Arch uses prebuilt packages. Any stressor that spends its time in user space
  (notably `memcpy`, see §6.3) measures that difference, not the kernel. This is the
  confound the design tried to avoid, and it partially leaks in.
- **Compiler is not held constant.** Arch kernel is built with gcc 16.1.1, both
  Gentoo kernels with gcc 15.2.1. Part of any Arch-vs-Gentoo difference may be the
  newer compiler.
- **No `-march=native`.** Despite the original intent, all three kernels are generic
  `x86-64` (`# CONFIG_X86_NATIVE_CPU is not set` in every config); `make.conf`
  `CFLAGS` do not reach a manual kernel `make`. This removes an ISA confound between
  kernels but also invalidates any `-march`-based explanation.
- **Kernel version is confounded with tuning** in the Arch-vs-zen pair (7.0.3 vs
  7.2.7); the 6.18-vs-zen pair still spans 6.18→7.2 on top of the preemption/patch
  differences above.
- **One machine, one chassis.** No claim generalises beyond this i5-13500HX laptop.
- **Idle-floor asymmetry.** 6.18 could not reach the 50 °C cool target (idle floor
  ~53 °C); its `-ctl` iterations start ~3 °C warmer. With turbo off the frequency is
  fixed, so the effect on throughput is negligible, but it is a real asymmetry.
- **No default (turbo-on) run for 6.18** — the turbo-effect analysis is shown only
  for the two kernels where both regimes were measured (Arch, zen).
- bogo-ops are stress-ng's internal unit, meaningful for *relative* comparison on
  identical binaries, not as an absolute figure of merit.

## 8. Reproduce

```bash
# deps (Arch example)
sudo pacman -S stress-ng sysbench lm_sensors cpupower
sudo sensors-detect --auto

# from a bare TTY, as root:
./tools/kbench.sh <label>            # default regime (turbo on)
# controlled regime: the script disables turbo and tightens thermals itself
# (see DISABLE_TURBO / COOL_TARGET at the top of tools/kbench.sh)

# analysis + figures
python3 tools/analyze.py            # writes analysis/
python3 tools/plot.py               # writes figures/
```

## 9. What I'd do next

- **Hold preemption constant** — rebuild 6.18 with full `PREEMPT` (or zen with
  `PREEMPT_VOLUNTARY`) so the 6.18-vs-zen pair isolates the zen patch set instead of
  conflating it with the preemption model (§6.2).
- **Hold the userspace build constant** — run the *same* stress-ng/sysbench binaries
  on all three kernels (e.g. a static build, or the same distro's packages) to remove
  the glibc/toolchain confound behind the `memcpy` gap (§6.3).
- Hold gcc constant (rebuild Arch's kernel under gcc 15, or all three under 16).
- Add a `zen`-debloated build (drop tracing/debug from the config) to test whether the
  remaining `sched_switch`/`futex` cost is `ZEN_INTERACTIVE` or removable debug blot.
- Pin IRQs and isolate CPUs for the latency tests; add `schbench`/`cyclictest` for a
  proper tail-latency view, where a desktop-tuned kernel should actually shine.

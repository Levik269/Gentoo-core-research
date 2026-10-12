# Gentoo core research — a controlled Linux kernel micro-benchmark

**Question:** when one Linux kernel looks "faster" than another on a laptop, how
much of that is the kernel — and how much is just turbo boost?

**Answer:** on this machine, mostly turbo. Disabling it erased most of the gap and
**flipped the winner on four of nine tests.**

Hardware: Intel Core i5-13500HX (Raptor Lake, 14C/20T) · dual-boot Arch / Gentoo.
Three kernels, nine kernel-level micro-benchmarks, two power regimes.

| kernel | build |
|--------|-------|
| **Arch 7.0.3** | stock `linux`, generic `-O2`, gcc 16 |
| **Gentoo zen 7.2.7** | `zen-sources`, `-march=native`, `ZEN_INTERACTIVE`, gcc 15 |
| **Gentoo vanilla 6.18** | `gentoo-sources`, `-march=native`, hand-rolled config, gcc 15 |

## Key result

With turbo boost **off** and the CPU pinned to its base clock, no kernel wins
outright — each is fastest at a *different* class of work:

![controlled comparison](figures/fig1_controlled_3way.png)

- **zen 7.2.7** dominates pipe IPC (**+32 %**), ties on compute.
- **vanilla 6.18** leads context-switch, futex and memory bandwidth.
- **stock Arch** leads raw scheduler-context and syscall micro-tests.
- `-march=native` shows up in `memcpy`: both Gentoo builds beat Arch by ~7 %.

## The catch: turbo boost was doing the talking

Leave turbo **on** and Arch looks 19–39 % faster across the board. That advantage
is mostly boost behaviour, not the kernel — and it reverses the verdict on four
tests once removed (threads swings from Arch +58 % to zen +9 %).

![turbo flips the verdict](figures/fig3_turbo_flips.png)

## Read more

- **[METHODOLOGY.md](METHODOLOGY.md)** — kernels, benchmark suite, measurement
  protocol, full results tables, analysis, and threats to validity.
- **[results/](results/)** — raw per-run data (`*.csv`, `*.env`, `*.log`).
- **[configs/](configs/)** — the three kernel `.config` files.
- **[analysis/](analysis/)** — computed summary and derived tables.
- **[tools/](tools/)** — the benchmark runner and analysis scripts.

## Reproduce (short version)

```bash
sudo pacman -S stress-ng sysbench lm_sensors cpupower   # Arch
sudo ./tools/kbench.sh <label>        # from a bare TTY, as root
python3 tools/analyze.py && python3 tools/plot.py
```

Full steps and the controlled-regime details are in
[METHODOLOGY.md §8](METHODOLOGY.md#8-reproduce).

---

*Benchmarks and analysis by Leo Skachkov (github.com/Levik269). MIT licensed.
Data is raw and included; corrections welcome.*

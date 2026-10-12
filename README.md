# Gentoo core research — a controlled Linux kernel micro-benchmark

One of the main questions in the linux community is what works faster and uses the resources of the machine efficiently? This small research goal is the measure of three kernels on one machine across nine kernel-level micro-benchmarks.
The main finding: with turbo on, stock Arch looks 19–39 % faster across the board. With turbo off and the CPU pinned to its base clock, that gap mostly vanishes and the winner flips on four of nine tests. No kernel wins outright — each is fastest at a different class of work. Here is the main graph with main details. More in methodology file.

Hardware: Intel Core i5-13500HX (Raptor Lake, 14C/20T), DDR5 16GB · dual-boot Arch / Gentoo.

Three kernels, nine kernel-level micro-benchmarks, two power regimes.

![controlled comparison](figures/fig1_controlled_3way.png)

---

*Benchmarks and analysis by Leo Skachkov (github.com/Levik269). MIT licensed.
Data is raw and included; corrections welcome.*

#!/usr/bin/env python3
"""
analyze.py — load all kbench CSVs, compute cross-kernel deltas and the turbo
effect, and emit machine- and human-readable summaries used to build the README.

Outputs (to analysis/):
  matrix_controlled.csv   median per test x kernel (turbo off) + % vs best
  turbo_effect.csv        per test, (turbo_on / turbo_off - 1) for Arch and zen
  summary.md              ready-to-read tables for the README
"""
import csv, os
from pathlib import Path

RES = Path("results")
OUT = Path("analysis"); OUT.mkdir(exist_ok=True)

# label -> file
RUNS = {
    "arch_default":  "arch-linux-7.0.3.csv",
    "arch_ctl":      "arch-linux-7.0.3-ctl.csv",
    "zen_default":   "gentoo-zen-7.2.7.csv",
    "zen_ctl":       "gentoo-zen-7.2.7-ctl.csv",
    "g618_ctl":      "gentoo-vanilla-6.18-ctl.csv",
}

TESTS = ["sched_context","sched_switch","ipc_pipe","futex","syscall",
         "memcpy","sysbench_cpu","sysbench_threads","sysbench_memory"]
UNIT  = {}
HIB   = {}  # higher is better

def load(fn):
    d = {}
    with open(RES/fn) as f:
        for r in csv.DictReader(f):
            t = r["test"]
            d[t] = dict(median=float(r["median"]), stddev=float(r["stddev"]),
                        unit=r["unit"], hib=r["higher_is_better"].strip()=="1")
            UNIT[t] = r["unit"]; HIB[t] = d[t]["hib"]
    return d

data = {k: load(v) for k,v in RUNS.items()}

def better(a, b, hib):
    """relative advantage of a over b as a %, sign = a is better."""
    if b == 0: return float("nan")
    raw = (a-b)/b*100.0
    return raw if hib else -raw

# ---------- controlled 3-way matrix (turbo off) ----------
ctl = {"g618_ctl":"6.18 vanilla", "zen_ctl":"zen 7.2.7", "arch_ctl":"Arch 7.0.3"}
with open(OUT/"matrix_controlled.csv","w",newline="") as f:
    w = csv.writer(f)
    w.writerow(["test","unit","higher_better","6.18","zen_7.2.7","arch_7.0.3",
                "winner","margin_%_over_2nd"])
    for t in TESTS:
        vals = {lbl: data[k][t]["median"] for k,lbl in ctl.items()}
        hib = HIB[t]
        # winner = best by hib
        ordered = sorted(vals.items(), key=lambda kv: kv[1], reverse=hib)
        win_lbl, win_val = ordered[0]
        second_val = ordered[1][1]
        margin = abs(better(win_val, second_val, hib))
        w.writerow([t, UNIT[t], "yes" if hib else "no",
                    f"{vals['6.18 vanilla']:.2f}", f"{vals['zen 7.2.7']:.2f}",
                    f"{vals['Arch 7.0.3']:.2f}", win_lbl, f"{margin:.1f}"])

# ---------- turbo effect (default vs ctl) for arch and zen ----------
with open(OUT/"turbo_effect.csv","w",newline="") as f:
    w = csv.writer(f)
    w.writerow(["test","unit","higher_better",
                "arch_turbo_gain_%","zen_turbo_gain_%"])
    for t in TESTS:
        hib = HIB[t]
        # turbo "gain" = how much the ON run beats the OFF run, respecting hib
        a = better(data["arch_default"][t]["median"], data["arch_ctl"][t]["median"], hib)
        z = better(data["zen_default"][t]["median"],  data["zen_ctl"][t]["median"],  hib)
        w.writerow([t, UNIT[t], "yes" if hib else "no", f"{a:.1f}", f"{z:.1f}"])

# ---------- default-vs-default head-to-head (arch vs zen, turbo on) & controlled ----------
def head2head(ka, kz):
    rows = []
    for t in TESTS:
        hib = HIB[t]
        d = better(data[kz][t]["median"], data[ka][t]["median"], hib)  # zen vs arch
        rows.append((t, d))
    return rows

# ---------- summary.md ----------
def fmt(v):
    return f"{v:,.0f}" if v>=100 else f"{v:g}"

lines = []
lines.append("# kbench — computed summary\n")
lines.append("## 1. Controlled comparison (turbo OFF, fixed base frequency)\n")
lines.append("Median of 7 measured iterations. **Bold** = fastest for that test.\n")
lines.append("| test | unit | 6.18 vanilla | zen 7.2.7 | Arch 7.0.3 | winner (margin) |")
lines.append("|------|------|---:|---:|---:|---|")
for t in TESTS:
    hib = HIB[t]
    vals = {"6.18 vanilla":data["g618_ctl"][t]["median"],
            "zen 7.2.7":data["zen_ctl"][t]["median"],
            "Arch 7.0.3":data["arch_ctl"][t]["median"]}
    ordered = sorted(vals.items(), key=lambda kv: kv[1], reverse=hib)
    win = ordered[0][0]; margin = abs(better(ordered[0][1], ordered[1][1], hib))
    cells = {}
    for lbl,v in vals.items():
        cells[lbl] = f"**{fmt(v)}**" if lbl==win else fmt(v)
    arrow = "↑" if hib else "↓"
    lines.append(f"| {t} | {UNIT[t]} {arrow} | {cells['6.18 vanilla']} | "
                 f"{cells['zen 7.2.7']} | {cells['Arch 7.0.3']} | {win} (+{margin:.1f}%) |")

lines.append("\n## 2. Turbo-boost effect (how much turbo inflated each result)\n")
lines.append("Positive = the turbo-ON run beat the fixed-frequency run. Direction respects higher/lower-is-better.\n")
lines.append("| test | Arch turbo gain | zen turbo gain |")
lines.append("|------|---:|---:|")
for t in TESTS:
    hib=HIB[t]
    a = better(data["arch_default"][t]["median"], data["arch_ctl"][t]["median"], hib)
    z = better(data["zen_default"][t]["median"],  data["zen_ctl"][t]["median"],  hib)
    lines.append(f"| {t} | {a:+.0f}% | {z:+.0f}% |")

lines.append("\n## 3. How turbo flips the verdict (Arch vs zen)\n")
lines.append("zen-vs-Arch advantage (+ = zen faster). Compare default (turbo on) to controlled.\n")
lines.append("| test | default (turbo on) | controlled (turbo off) | flipped? |")
lines.append("|------|---:|---:|:---:|")
for t in TESTS:
    hib=HIB[t]
    d_on  = better(data["zen_default"][t]["median"], data["arch_default"][t]["median"], hib)
    d_off = better(data["zen_ctl"][t]["median"],     data["arch_ctl"][t]["median"],     hib)
    flip = "yes" if (d_on>0) != (d_off>0) else ""
    lines.append(f"| {t} | {d_on:+.0f}% | {d_off:+.0f}% | {flip} |")

(OUT/"summary.md").write_text("\n".join(lines)+"\n")
print("\n".join(lines))
print(f"\n[written] {OUT}/summary.md  {OUT}/matrix_controlled.csv  {OUT}/turbo_effect.csv")

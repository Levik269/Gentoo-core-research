#!/usr/bin/env python3
"""
plot.py — render the figures used in the README from the kbench CSVs in results/.

Figures (to figures/):
  fig1_controlled_3way.png   3 kernels side by side per test (turbo OFF), stddev bars
  fig2_turbo_effect.png      how much turbo inflated each test, Arch vs zen
  fig3_turbo_flips.png       zen-vs-Arch advantage, turbo-on vs turbo-off (shows sign flips)

Pure matplotlib + stdlib. Normalises each test to its own scale so very
different magnitudes still read on one page (fig1 uses per-test normalisation).
"""
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RES = Path("results"); FIG = Path("figures"); FIG.mkdir(exist_ok=True)

TESTS = ["sched_context","sched_switch","ipc_pipe","futex","syscall",
         "memcpy","sysbench_cpu","sysbench_threads","sysbench_memory"]
PRETTY = {"sched_context":"sched\ncontext","sched_switch":"sched\nswitch",
          "ipc_pipe":"ipc\npipe","futex":"futex","syscall":"syscall",
          "memcpy":"memcpy","sysbench_cpu":"sysbench\ncpu",
          "sysbench_threads":"threads\n(latency)","sysbench_memory":"memory"}

def load(fn):
    d={}
    with open(RES/fn) as f:
        for r in csv.DictReader(f):
            d[r["test"]]=dict(median=float(r["median"]),stddev=float(r["stddev"]),
                              hib=r["higher_is_better"].strip()=="1",unit=r["unit"])
    return d

arch_d = load("arch-linux-7.0.3.csv");      arch_c = load("arch-linux-7.0.3-ctl.csv")
zen_d  = load("gentoo-zen-7.2.7.csv");       zen_c  = load("gentoo-zen-7.2.7-ctl.csv")
g618_c = load("gentoo-vanilla-6.18-ctl.csv")

C_618  = "#2E7D32"   # green   (vanilla 6.18)
C_ZEN  = "#1565C0"   # blue    (zen 7.2.7)
C_ARCH = "#E65100"   # orange  (arch 7.0.3)

def rel_sigma(d,t):
    m=d[t]["median"]; return d[t]["stddev"]/m if m else 0

# ---------- FIG 1: controlled 3-way, per-test normalised to the best = 1.0 ----------
def fig1():
    fig,ax=plt.subplots(figsize=(13,5.5))
    x=np.arange(len(TESTS)); w=0.26
    series=[("6.18 vanilla",g618_c,C_618,-w),("zen 7.2.7",zen_c,C_ZEN,0.0),
            ("Arch 7.0.3",arch_c,C_ARCH,w)]
    # normalise each test so the best kernel = 1.0 (respecting hib)
    norm={}
    for t in TESTS:
        hib=g618_c[t]["hib"]
        vals=[g618_c[t]["median"],zen_c[t]["median"],arch_c[t]["median"]]
        base=max(vals) if hib else min(vals)
        norm[t]=base
    for lbl,d,col,off in series:
        ys=[]; es=[]
        for t in TESTS:
            hib=d[t]["hib"]; base=norm[t]
            # express as performance ratio where 1.0 = best (for latency invert)
            if hib: y=d[t]["median"]/base
            else:   y=base/d[t]["median"]
            ys.append(y); es.append(y*rel_sigma(d,t))
        ax.bar(x+off,ys,w,yerr=es,capsize=3,label=lbl,color=col,
               error_kw=dict(ecolor="#333",lw=.8))
    ax.set_xticks(x); ax.set_xticklabels([PRETTY[t] for t in TESTS],fontsize=8)
    ax.set_ylabel("performance relative to best kernel\n(1.0 = fastest, higher = better)")
    ax.set_title("Controlled kernel comparison — turbo OFF, fixed base frequency, governor=performance\n"
                 "i5-13500HX · stress-ng 0.21.04 / sysbench 1.0.20 · 7 measured runs (2 warmup discarded)",
                 fontsize=10)
    ax.set_ylim(0,1.08); ax.axhline(1.0,ls=":",c="#999",lw=.8)
    ax.legend(loc="lower right",fontsize=9,ncol=3); ax.grid(axis="y",ls=":",alpha=.4)
    fig.tight_layout(); fig.savefig(FIG/"fig1_controlled_3way.png",dpi=140); plt.close(fig)

# ---------- FIG 2: turbo inflation per test, Arch vs zen ----------
def better(a,b,hib):
    if b==0: return float("nan")
    raw=(a-b)/b*100.0; return raw if hib else -raw
def fig2():
    fig,ax=plt.subplots(figsize=(13,5))
    x=np.arange(len(TESTS)); w=0.38
    ag=[better(arch_d[t]["median"],arch_c[t]["median"],arch_d[t]["hib"]) for t in TESTS]
    zg=[better(zen_d[t]["median"], zen_c[t]["median"], zen_d[t]["hib"])  for t in TESTS]
    ax.bar(x-w/2,ag,w,label="Arch 7.0.3",color=C_ARCH)
    ax.bar(x+w/2,zg,w,label="Gentoo zen 7.2.7",color=C_ZEN)
    ax.set_xticks(x); ax.set_xticklabels([PRETTY[t] for t in TESTS],fontsize=8)
    ax.set_ylabel("turbo boost gain (%)\npositive = turbo-ON beats fixed frequency")
    ax.set_title("How much turbo boost inflated each benchmark\n"
                 "Arch boosts harder than the Gentoo zen build on almost every test",fontsize=10)
    ax.axhline(0,c="#333",lw=.8); ax.legend(fontsize=9); ax.grid(axis="y",ls=":",alpha=.4)
    for i,v in enumerate(ag): ax.text(i-w/2,v+(1 if v>=0 else -3),f"{v:+.0f}",ha="center",fontsize=7)
    for i,v in enumerate(zg): ax.text(i+w/2,v+(1 if v>=0 else -3),f"{v:+.0f}",ha="center",fontsize=7)
    fig.tight_layout(); fig.savefig(FIG/"fig2_turbo_effect.png",dpi=140); plt.close(fig)

# ---------- FIG 3: zen-vs-Arch advantage, turbo-on vs off (sign flips) ----------
def fig3():
    fig,ax=plt.subplots(figsize=(13,5))
    x=np.arange(len(TESTS)); w=0.38
    on =[better(zen_d[t]["median"],arch_d[t]["median"],zen_d[t]["hib"]) for t in TESTS]
    off=[better(zen_c[t]["median"],arch_c[t]["median"],zen_c[t]["hib"]) for t in TESTS]
    ax.bar(x-w/2,on, w,label="turbo ON (default)",color="#B0BEC5")
    ax.bar(x+w/2,off,w,label="turbo OFF (controlled)",color=C_ZEN)
    ax.set_xticks(x); ax.set_xticklabels([PRETTY[t] for t in TESTS],fontsize=8)
    ax.set_ylabel("zen 7.2.7 advantage over Arch (%)\n+ = zen faster,  − = Arch faster")
    ax.set_title("Turbo flips the verdict: zen vs Arch, before and after disabling turbo\n"
                 "memcpy, sysbench_cpu, threads and memory all change sign once turbo is removed",fontsize=10)
    ax.axhline(0,c="#333",lw=.8); ax.legend(fontsize=9); ax.grid(axis="y",ls=":",alpha=.4)
    fig.tight_layout(); fig.savefig(FIG/"fig3_turbo_flips.png",dpi=140); plt.close(fig)

fig1(); fig2(); fig3()
print("wrote figures/fig1_controlled_3way.png, fig2_turbo_effect.png, fig3_turbo_flips.png")

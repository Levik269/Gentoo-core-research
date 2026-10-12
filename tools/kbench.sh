#!/usr/bin/env bash
# kbench.sh v4 — kernel-centric cross-distro benchmark runner (controlled thermals)
#   v4 adds: turbo disabled, fixed base freq, COOL_TARGET=50C, 10s runs,
#            post-run temperature logged (shows in-run throttling as dT).
#   v5: COOL_TIMEOUT lowered to 60s so kernels whose idle floor sits above
#       50C (e.g. 6.18) don't waste 90s per iteration waiting. Measurement
#       logic unchanged; a run may simply start a few C warmer (noted in README).
# Runs the SAME suite on Arch and Gentoo; discards warmup; writes everything to disk.
# Focus: scheduler, context-switch, syscall, IPC, futex, memory — things the KERNEL owns.
#
# Usage:   sudo ./kbench.sh <label>
#   e.g.   sudo ./kbench.sh gentoo-zen-7.2.7
#          sudo ./kbench.sh arch-linux-6.x
#
# Writes (all under results/):
#   <label>.csv       machine-readable: median,stddev,min,max,raw
#   <label>.md        ready-to-paste markdown table for the README
#   <label>.env       environment (kernel, cpu, tool versions) for reproducibility
#   <label>.log       full console transcript of the run (every iteration)
#
# Requires: stress-ng, sysbench, lm-sensors (sensors); cpupower recommended.

set -u

# ---------- config ----------
WARMUP=2                     # discarded warmup iterations per test
RUNS=7                       # MEASURED repetitions per test
COOL_TARGET=50               # °C: start each iteration from a cold, equal baseline
COOL_TIMEOUT=60              # s : stop waiting after this (v5: was 240; avoids long idle-floor waits)
TEST_DURATION=10             # s : shorter run -> less in-run heating
DISABLE_TURBO=1              # 1 = disable turbo/boost for fixed-frequency comparison
SYSBENCH_THREADS=$(nproc)
SENSORS_KEY="Package id 0"   # grep key for package temp
# ----------------------------

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo $0 <label>" >&2; exit 1
fi
LABEL="${1:-}"
[[ -z "$LABEL" ]] && { echo "Usage: sudo $0 <label>" >&2; exit 1; }

mkdir -p results
CSV="results/${LABEL}.csv"
MD="results/${LABEL}.md"
ENVF="results/${LABEL}.env"
LOG="results/${LABEL}.log"

# Mirror ALL stdout/stderr to the log file as well as the screen.
exec > >(tee "$LOG") 2>&1

# ---------- environment capture ----------
{
  echo "label=$LABEL"
  echo "date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "kernel=$(uname -r)"
  echo "arch=$(uname -m)"
  echo "cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | sed 's/^ //')"
  echo "nproc=$(nproc)"
  echo "stress_ng=$(stress-ng --version 2>/dev/null | head -1)"
  echo "sysbench=$(sysbench --version 2>/dev/null)"
  echo "gcc=$(gcc --version 2>/dev/null | head -1)"
  echo "governor_before=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)"
  echo "protocol=warmup:${WARMUP} measured:${RUNS} cool_target:${COOL_TARGET}C duration:${TEST_DURATION}s turbo_disabled:${DISABLE_TURBO}"
} > "$ENVF"
echo "== environment -> $ENVF =="; cat "$ENVF"; echo

# ---------- governor ----------
OLD_GOV=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)
set_gov () {
  local g="$1"
  if command -v cpupower >/dev/null 2>&1; then cpupower frequency-set -g "$g" >/dev/null 2>&1
  else for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo "$g" > "$f" 2>/dev/null; done
  fi
}
restore_gov () { [[ -n "${OLD_GOV:-}" ]] && set_gov "$OLD_GOV"; }

# ---------- turbo / boost control ----------
TURBO_PATH=""; TURBO_OLD=""; TURBO_KIND=""
turbo_detect () {
  if [[ -f /sys/devices/system/cpu/intel_pstate/no_turbo ]]; then
    TURBO_PATH=/sys/devices/system/cpu/intel_pstate/no_turbo; TURBO_KIND="no_turbo"
  elif [[ -f /sys/devices/system/cpu/cpufreq/boost ]]; then
    TURBO_PATH=/sys/devices/system/cpu/cpufreq/boost; TURBO_KIND="boost"
  fi
}
turbo_off () {
  turbo_detect; [[ -z "$TURBO_PATH" ]] && { echo "   (turbo knob not found; skipping)"; return; }
  TURBO_OLD=$(cat "$TURBO_PATH" 2>/dev/null)
  # no_turbo: 1 disables turbo.  boost: 0 disables boost.
  if [[ "$TURBO_KIND" == "no_turbo" ]]; then echo 1 > "$TURBO_PATH" 2>/dev/null
  else echo 0 > "$TURBO_PATH" 2>/dev/null; fi
  echo "   turbo disabled via $TURBO_PATH ($TURBO_KIND, was $TURBO_OLD)"
}
turbo_restore () {
  [[ -z "$TURBO_PATH" || -z "$TURBO_OLD" ]] && return
  echo "$TURBO_OLD" > "$TURBO_PATH" 2>/dev/null
}
trap 'restore_gov; turbo_restore' EXIT
echo "== governor: performance (was: $OLD_GOV) =="
set_gov performance
echo "   now: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)"
if [[ "${DISABLE_TURBO:-0}" == "1" ]]; then echo "== disabling turbo =="; turbo_off; fi
echo

# ---------- temp + cooling ----------
pkg_temp () {
  local t
  t=$(sensors 2>/dev/null | grep -i "$SENSORS_KEY" | grep -oE '\+[0-9]+\.[0-9]+' | head -1 | tr -d '+')
  [[ -z "$t" ]] && t=$(sensors 2>/dev/null | grep -iE '^Core ' | grep -oE '\+[0-9]+\.[0-9]+' | sort -rn | head -1 | tr -d '+')
  [[ -z "$t" ]] && { echo 0; return; }
  printf '%.0f' "$t"
}
cool_down () {
  local waited=0 t; t=$(pkg_temp)
  while (( t > COOL_TARGET )) && (( waited < COOL_TIMEOUT )); do
    printf "\r   cooling: %d°C > %d°C (%ds)   " "$t" "$COOL_TARGET" "$waited"
    sleep 3; waited=$((waited+3)); t=$(pkg_temp)
  done
  printf "\r   temp %d°C - ok%*s\n" "$t" 20 ""
}

# ---------- stats: median,stddev,min,max from stdin ----------
stats () {
  awk '
  { v[NR]=$1; s+=$1 }
  END{
    n=NR; if(n==0){print "NA,NA,NA,NA"; exit}
    for(i=1;i<=n;i++) for(j=i+1;j<=n;j++) if(v[j]<v[i]){t=v[i];v[i]=v[j];v[j]=t}
    if(n%2) med=v[(n+1)/2]; else med=(v[n/2]+v[n/2+1])/2
    mean=s/n; ss=0; for(i=1;i<=n;i++){d=v[i]-mean; ss+=d*d}
    sd=(n>1)? sqrt(ss/(n-1)) : 0
    printf "%.3f,%.3f,%.3f,%.3f", med, sd, v[1], v[n]
  }'
}

# ---------- metric extractors ----------
sng_bogo_realtime () {
  # Parse the --metrics row robustly: anchor on 'stress-ng: metrc: [pid]',
  # the stressor name is token 4, and bogo-ops/s (real time) is name+5.
  # Guards against the earlier bug where a mis-aligned column yielded
  # 'bogo ops total' (~6-digit) instead of 'bogo ops/s' (~hundreds).
  stress-ng "--$1" 0 --timeout "${TEST_DURATION}s" --metrics 2>/dev/null \
    | awk -v s="$1" '
        /^stress-ng: metrc: \[[0-9]+\]/ {
          if ($4 == s) { print $(4+5); exit }
        }'
}
sb_cpu () {
  sysbench cpu --cpu-max-prime=20000 --threads="$SYSBENCH_THREADS" --time="$TEST_DURATION" run 2>/dev/null \
    | awk '/events per second/{print $4; exit}'
}
sb_threads_lat () {
  sysbench threads --threads="$SYSBENCH_THREADS" --thread-yields=1000 --thread-locks=8 --time="$TEST_DURATION" run 2>/dev/null \
    | awk '/avg:/{print $2; exit}'
}
sb_mem () {
  sysbench memory --memory-block-size=1M --memory-total-size=100G --threads="$SYSBENCH_THREADS" --time="$TEST_DURATION" run 2>/dev/null \
    | awk '/transferred/{gsub(/[()]/,""); print $(NF-1); exit}'
}

# ---------- outlier guard ----------
# Reject a measurement that is wildly off the running median (>10x or <0.1x).
# Protects the stats from a single mis-parsed stress-ng row (see syscall bug).
median_of () { printf '%s\n' "$@" | sort -n | awk '{a[NR]=$1} END{ if(NR%2) print a[(NR+1)/2]; else print (a[NR/2]+a[NR/2+1])/2 }'; }
is_sane () {  # $1=value  $2..=existing values ; echo 1 if sane/no-baseline, else 0
  local v="$1"; shift
  [[ $# -lt 2 ]] && { echo 1; return; }   # need a baseline of >=2 to judge
  local m; m=$(median_of "$@")
  awk -v v="$v" -v m="$m" 'BEGIN{ if(m<=0){print 1; exit} r=v/m; print (r>10 || r<0.1)?0:1 }'
}

# ---------- test registry: name|unit|higher_is_better|fn ----------
declare -a TESTS=(
  "sched_context|bogo_ops_s|1|sng_bogo_realtime context"
  "sched_switch|bogo_ops_s|1|sng_bogo_realtime switch"
  "ipc_pipe|bogo_ops_s|1|sng_bogo_realtime pipe"
  "futex|bogo_ops_s|1|sng_bogo_realtime futex"
  "syscall|bogo_ops_s|1|sng_bogo_realtime syscall"
  "memcpy|bogo_ops_s|1|sng_bogo_realtime memcpy"
  "sysbench_cpu|events_s|1|sb_cpu"
  "sysbench_threads|avg_latency_ms|0|sb_threads_lat"
  "sysbench_memory|MiB_s|1|sb_mem"
)

# ---------- run ----------
echo "test,unit,higher_is_better,median,stddev,min,max,n,raw_measured" > "$CSV"
echo "== suite: ${WARMUP} warmup (discarded) + ${RUNS} measured  x ${#TESTS[@]} tests =="; echo

for entry in "${TESTS[@]}"; do
  IFS='|' read -r name unit hib fn <<< "$entry"
  echo "---- $name ($unit) ----"

  # warmup (not recorded)
  for ((w=1; w<=WARMUP; w++)); do
    cool_down
    printf "   warmup %d/%d ... " "$w" "$WARMUP"
    wv=$(eval "$fn"); echo "${wv:-NA} (discarded)"
  done

  # measured
  vals=()
  for ((r=1; r<=RUNS; r++)); do
    cool_down
    t_pre=$(pkg_temp)
    printf "   run %d/%d ... " "$r" "$RUNS"
    val=$(eval "$fn"); [[ -z "$val" ]] && val="NA"
    t_post=$(pkg_temp); dT=$((t_post - t_pre))
    if [[ "$val" != "NA" ]]; then
      if [[ "$(is_sane "$val" "${vals[@]}")" == "1" ]]; then
        echo "$val $unit   [${t_pre}->${t_post}°C, dT=+${dT}]"; vals+=("$val")
      else
        echo "$val $unit  [rejected outlier; ${t_pre}->${t_post}°C]"
      fi
    else
      echo "NA"
    fi
  done

  if ((${#vals[@]})); then st=$(printf '%s\n' "${vals[@]}" | stats); else st="NA,NA,NA,NA"; fi
  raw=$(IFS=';'; echo "${vals[*]}")
  echo "$name,$unit,$hib,$st,${#vals[@]},$raw" >> "$CSV"
  echo "   => median,stddev,min,max = $st"; echo
done

# ---------- markdown table ----------
{
  echo "# kbench results: $LABEL"
  echo
  echo "- kernel: \`$(uname -r)\`  |  cpu: $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | sed 's/^ //')  |  nproc: $(nproc)"
  echo "- stress-ng: $(stress-ng --version 2>/dev/null | head -1 | sed 's/, [0-9].*//')  |  sysbench: $(sysbench --version)"
  echo "- protocol: ${WARMUP} warmup discarded + ${RUNS} measured, governor=performance, turbo=${DISABLE_TURBO:+disabled}, cool<=${COOL_TARGET}°C, ${TEST_DURATION}s runs"
  echo
  echo "| test | unit | higher better | median | stddev | min | max | rel.σ |"
  echo "|------|------|:---:|---:|---:|---:|---:|---:|"
  tail -n +2 "$CSV" | while IFS=, read -r name unit hib med sd mn mx n raw; do
    rel=$(awk -v m="$med" -v s="$sd" 'BEGIN{ if(m+0>0) printf "%.1f%%", 100*s/m; else print "NA"}')
    hibm=$([[ "$hib" == "1" ]] && echo "yes" || echo "no (lower=better)")
    echo "| $name | $unit | $hibm | $med | $sd | $mn | $mx | $rel |"
  done
} > "$MD"

echo "== done =="
echo "   csv : $CSV"
echo "   md  : $MD   (paste into README)"
echo "   env : $ENVF"
echo "   log : $LOG  (full transcript)"
echo
echo "---- markdown preview ----"
cat "$MD"

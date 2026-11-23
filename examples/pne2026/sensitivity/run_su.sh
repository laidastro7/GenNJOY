#!/usr/bin/env bash
# =============================================================================
# Complete S/U chain of the Mosteller pin cell (restartable).
#
#   bash run_su.sh pilot [JOBS] [THREADS] [LIMIT]   check on a laptop (weak settings,
#                                                   a sample of the tasks)
#   bash run_su.sh full  [JOBS] [THREADS]           production (100000 x 2000)
#
# JOBS OpenMC calculations run at the same time, each with THREADS threads
# (JOBS x THREADS = number of cores, e.g. 8 x 10 on 80 cores, 3 x 4 on 12 cores).
# Stop at any time (Ctrl-C) and run the same command again: finished tasks are kept.
# =============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
PRESET="${1:-pilot}"
JOBS="${2:-1}"
THREADS="${3:-$(nproc)}"
LIMIT="${4:-0}"
command -v openmc >/dev/null || { echo "openmc not found in PATH"; exit 1; }
[ -f library_600K/cross_sections.xml ] || { echo "library_600K/ missing: run prepare_600K.sh first"; exit 1; }
[ -d covariance_600K/csv ] || { echo "covariance_600K/csv missing: run prepare_600K.sh first"; exit 1; }
export OMP_PROC_BIND="${OMP_PROC_BIND:-false}"

{
echo "=== S/U run, preset $PRESET, $JOBS jobs x $THREADS threads — $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "host: $(hostname)   CPUs: $(nproc)"
lscpu | grep -E "Model name" || true
echo "OpenMC: $(openmc --version | head -1)   Python API: $(python3 -c 'import openmc; print(openmc.__version__)')"
} | tee -a "run_su_${PRESET}.log"

# 1. reference run with the fine-group flux (screening, flux figure)
if [ ! -f results/reference_tallies.h5 ] || [ "$(python3 -c "import h5py;print(h5py.File('results/reference_tallies.h5','r').attrs['preset'])")" != "$PRESET" ]; then
  python3 su_run.py reference --preset "$PRESET" --threads $((JOBS * THREADS)) | tee -a "run_su_${PRESET}.log"
  python3 su_tasks.py | tee -a "run_su_${PRESET}.log"
fi
[ -f tasks.csv ] || python3 su_tasks.py | tee -a "run_su_${PRESET}.log"

# 2. OpenMC calculations
if [ "$PRESET" = "pilot" ] && [ "$LIMIT" = "0" ]; then
  # pilot: references, whole-range perturbations and a sample of groups
  python3 su_run.py run --preset pilot --jobs "$JOBS" --threads "$THREADS" --only "ref_|zero|Gall|G2[0-4]_" \
      | tee -a "run_su_${PRESET}.log"
else
  python3 su_run.py run --preset "$PRESET" --jobs "$JOBS" --threads "$THREADS" --limit "$LIMIT" \
      | tee -a "run_su_${PRESET}.log"
fi

# 3. analysis
python3 su_analyze.py --preset "$PRESET" | tee -a "run_su_${PRESET}.log"
echo "results: $HERE/results/analysis_$PRESET/"

#!/usr/bin/env bash
# =============================================================================
# S/U campaign of the GenNJOY article — the only command to run.
#
#   bash run_campaign.sh          production run (100 000 particles x 2000 batches)
#   bash run_campaign.sh test     quick check of the installation (~5-15 min)
#
# Recommended for the production run (keeps running after logging out):
#   nohup bash run_campaign.sh > campaign.out 2>&1 &
#   tail -f campaign.out
#
# If the run stops for any reason, run the same command again: it continues
# from the last finished calculation and adds up the total time.
# =============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

# activate the conda environment of README.md if OpenMC is not available yet
if ! command -v openmc >/dev/null 2>&1; then
  for c in "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/miniforge3" "$HOME/mambaforge" /opt/conda; do
    [ -f "$c/etc/profile.d/conda.sh" ] && source "$c/etc/profile.d/conda.sh" && break
  done
  command -v conda >/dev/null 2>&1 && conda activate gennjoy-pne2026 2>/dev/null
fi

if [ "${1:-}" = "test" ]; then
  export PRESET=pilot SU_RESULTS="$HERE/results_test" SU_WORK="$HERE/work_test" LIMIT="${LIMIT:-60}"
  echo "TEST MODE: $LIMIT short calculations in results_test/ (the values are not meaningful)"
else
  export PRESET="${PRESET:-full}"
fi
export OMP_PROC_BIND="${OMP_PROC_BIND:-false}"
python3 -u campaign.py

#!/usr/bin/env bash
# =============================================================================
#  GenNJOY S/U calculations — Mosteller pin cell — THE ONLY COMMAND TO RUN
#
#     bash START_HERE.sh            install (if needed) and start / continue the campaign
#     bash START_HERE.sh test       quick check of the installation (5-15 min)
#     bash START_HERE.sh status     show the progress of a running campaign
#     bash START_HERE.sh stop       stop the campaign (continue later with: bash START_HERE.sh)
#
#  1. uses OpenMC 0.15.0 if available; otherwise the one installed without internet
#     by install_openmc_offline.sh (in ~/openmc-0.15.0 or $OPENMC_ENV); otherwise an
#     installed newer OpenMC (with a warning); otherwise creates the conda environment "gennjoy-pne2026"
#     from environment.yml (and installs Miniforge in ~/miniforge3 if conda is absent)
#  2. starts the campaign in the background (it continues if you close the terminal
#     or log out) and shows its progress; Ctrl-C only stops the display
#  3. run the same command again after any interruption: the campaign continues
#     from the last finished calculation
#  At the end: send back the file SU_results_*.tar.gz written in
#  examples/pne2026/sensitivity/
# =============================================================================
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SU="$ROOT/examples/pne2026/sensitivity"
ENV_NAME="gennjoy-pne2026"
MODE="${1:-run}"
OUT="$SU/campaign.out"
PIDFILE="$SU/campaign.pid"

say() { echo "[START_HERE] $*"; }

# OpenMC >= 0.15.0 with the executable and the Python API of the same version
openmc_ok() {
  command -v openmc >/dev/null 2>&1 || return 1
  local ve vp
  ve="$(openmc --version 2>/dev/null | sed -n 's/OpenMC version *//p' | grep -o '^[0-9]*\.[0-9]*\.[0-9]*')"
  vp="$(python3 -c 'import openmc; print(openmc.__version__)' 2>/dev/null | grep -o '^[0-9]*\.[0-9]*\.[0-9]*')"
  [ -n "$ve" ] && [ "$ve" = "$vp" ] || return 1
  [ "$(printf '%s\n0.15.0\n' "$ve" | sort -V | head -1)" = "0.15.0" ] || return 1
  python3 -c 'import numpy, h5py, pandas, matplotlib' 2>/dev/null || return 1
}

find_conda() {
  command -v conda >/dev/null 2>&1 && { source "$(conda info --base)/etc/profile.d/conda.sh"; return 0; }
  for c in "$HOME/miniforge3" "$HOME/mambaforge" "$HOME/miniconda3" "$HOME/anaconda3" /opt/conda /opt/miniforge3; do
    if [ -f "$c/etc/profile.d/conda.sh" ]; then source "$c/etc/profile.d/conda.sh"; return 0; fi
  done
  return 1
}

running() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

show_progress() {
  trap 'echo; say "display stopped; the campaign continues in the background. Progress again: bash START_HERE.sh status"; exit 0' INT
  say "progress of the campaign (Ctrl-C stops only this display; the calculations continue):"
  say "log: $OUT"
  echo
  tail -n 25 -f "$OUT" --pid="$(cat "$PIDFILE" 2>/dev/null || echo 1)" 2>/dev/null || tail -n 25 "$OUT"
}

# ---------------------------------------------------------------- status
if [ "$MODE" = "status" ]; then
  if running; then show_progress; else
    say "no campaign is running."
    [ -f "$OUT" ] && { say "last lines of $OUT:"; tail -n 15 "$OUT"; }
  fi
  exit 0
fi

# ---------------------------------------------------------------- stop
if [ "$MODE" = "stop" ]; then
  if running; then
    pid="$(cat "$PIDFILE")"
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid"
    for i in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
    say "campaign stopped. Continue later with:  bash START_HERE.sh"
    tail -n 3 "$OUT"
  else
    say "no campaign is running."
  fi
  exit 0
fi

# ---------------------------------------------------------------- already finished?
if [ "$MODE" = "run" ] && [ -f "$SU/FINISHED.txt" ] && ! grep -q "did not finish" "$SU/FINISHED.txt"; then
  say "the campaign is already finished; nothing to run."
  cat "$SU/FINISHED.txt"
  exit 0
fi

# ---------------------------------------------------------------- already running?
if running; then
  say "the campaign is already running (process $(cat "$PIDFILE"))."
  show_progress
  exit 0
fi

# ---------------------------------------------------------------- software
# OpenMC 0.15.0 installed without internet with install_openmc_offline.sh
# (separate package OpenMC_0.15.0_offline); default folder ~/openmc-0.15.0
OFFLINE_DIR=""
for d in "${OPENMC_ENV:-}" "$HOME/openmc-0.15.0" "$ROOT/openmc-0.15.0-env"; do
  [ -n "$d" ] && [ -f "$d/bin/activate" ] && [ -x "$d/bin/openmc" ] && { OFFLINE_DIR="$d"; break; }
done

exact_0150() { [ "$(openmc --version 2>/dev/null | sed -n 's/OpenMC version *//p')" = "0.15.0" ]; }

use_offline_env() {
  [ -n "$OFFLINE_DIR" ] || return 1
  set +u     # activation scripts use unset variables
  # shellcheck disable=SC1091
  source "$OFFLINE_DIR/bin/activate"
  openmc_ok
}

if openmc_ok && exact_0150; then
  say "OpenMC 0.15.0 found in the current environment."
elif use_offline_env; then
  say "using OpenMC installed in $OFFLINE_DIR: $(openmc --version | head -1)"
elif openmc_ok; then
  v="$(openmc --version | sed -n 's/OpenMC version *//p')"
  say "WARNING: OpenMC $v found (newer than 0.15.0, the version used for the article)."
  say "         The campaign will run with it; the version is recorded with the results."
else
  set +u     # conda activation scripts use unset variables
  if ! find_conda; then
    say "conda not found: installing Miniforge in $HOME/miniforge3 (no administrator rights needed)"
    inst="/tmp/Miniforge3-$$.sh"
    url="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-$(uname -m).sh"
    if command -v curl >/dev/null; then curl -fsSL -o "$inst" "$url"; else wget -q -O "$inst" "$url"; fi \
      || { say "download of Miniforge failed (no internet?). Install OpenMC 0.15.0 without internet with"
           say "install_openmc_offline.sh (package OpenMC_0.15.0_offline), then run this script again."; exit 1; }
    bash "$inst" -b -p "$HOME/miniforge3" >/dev/null && rm -f "$inst"
    source "$HOME/miniforge3/etc/profile.d/conda.sh"
  fi
  if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    conda activate "$ENV_NAME"
    if ! openmc_ok; then
      say "updating the environment $ENV_NAME to OpenMC 0.15.0 (environment.yml)"
      conda env update -n "$ENV_NAME" -f "$ROOT/environment.yml" --prune || exit 1
      conda activate "$ENV_NAME"
    fi
  else
    say "creating the conda environment $ENV_NAME (OpenMC 0.15.0), this takes a few minutes"
    if command -v mamba >/dev/null; then mamba env create -f "$ROOT/environment.yml" || exit 1
    else conda env create -f "$ROOT/environment.yml" || exit 1; fi
    conda activate "$ENV_NAME"
  fi
  openmc_ok || { say "OpenMC >= 0.15.0 is still not available in $ENV_NAME; stopping"; exit 1; }
  say "environment $ENV_NAME active: $(openmc --version | head -1)"
fi

cd "$SU"
chmod +x run_campaign.sh

# ---------------------------------------------------------------- test (foreground)
if [ "$MODE" = "test" ]; then
  bash run_campaign.sh test
  say "test finished. Start the campaign with:  bash START_HERE.sh"
  exit 0
fi

# ---------------------------------------------------------------- campaign (background)
say "starting the campaign in the background (it keeps running after the terminal is closed)"
{ echo; echo "########## START_HERE $(date '+%Y-%m-%d %H:%M:%S') ##########"; } >> "$OUT"
setsid nohup bash run_campaign.sh >> "$OUT" 2>&1 < /dev/null &
echo $! > "$PIDFILE"
sleep 3
show_progress
echo
if running; then
  say "display stopped; the campaign continues. See the progress again with:  bash START_HERE.sh status"
else
  say "the campaign has stopped. If it is not finished, run  bash START_HERE.sh  again to continue."
  ls "$SU"/SU_results_*.tar.gz 2>/dev/null && say "results to send back: $(ls "$SU"/SU_results_*.tar.gz | tail -1)"
fi

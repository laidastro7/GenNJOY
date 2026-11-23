#!/usr/bin/env bash
# =============================================================================
# Nuclear data of the S/U study, prepared with GenNJOY (run once, ~10-15 min):
#   1. incident-neutron and S(alpha,beta) data at 600 K (options 4, 5, 6)
#      -> library_600K/
#   2. covariance matrices, SCALE-44 groups (option 8)
#      -> covariance_600K/
#
#     cd examples/pne2026/sensitivity
#     bash prepare_600K.sh
#
# GenNJOY writes its outputs in the data/ folder of the package. To leave the
# library already there untouched (e.g. the 294 K ICSBEP library), the processing
# is done in a temporary copy of the package code (_gennjoy_600K/), whose data
# folders point to the ENDF/B-VIII.1 files of the installed package.
# Override the ENDF folders with NEUTRON_DATA=... THERMAL_DATA=...
# =============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
NEUTRON_DATA="${NEUTRON_DATA:-$REPO/gennjoy/data/incident_neutron_endf}"
THERMAL_DATA="${THERMAL_DATA:-$REPO/gennjoy/data/thermal_scattering_endf}"
CPUS="${CPUS:-$(nproc)}"
command -v njoy >/dev/null || { echo "njoy not found in PATH"; exit 1; }
command -v openmc >/dev/null || { echo "openmc not found in PATH"; exit 1; }

TMP="$HERE/_gennjoy_600K"
rm -rf "$TMP"
mkdir -p "$TMP/gennjoy/data" "$TMP/gennjoy/inputs"
cp "$REPO"/gennjoy/*.py "$REPO"/gennjoy/*.json "$TMP/gennjoy/" 2>/dev/null || cp "$REPO"/gennjoy/*.py "$TMP/gennjoy/"
ln -s "$NEUTRON_DATA" "$TMP/gennjoy/data/incident_neutron_endf"
ln -s "$THERMAL_DATA" "$TMP/gennjoy/data/thermal_scattering_endf"
PKG="$TMP/gennjoy"
LOG="$HERE/prepare_600K.log"
: > "$LOG"

echo "[1/4] NJOY, incident neutrons at 600 K ($CPUS CPUs)" | tee -a "$LOG"
printf '\n%s\n%s\n\n' "$NEUTRON_DATA" "$CPUS" | python3 "$PKG/run_neutron_processing.py" \
    "$HERE/inputs/neutron_process_batch_600K.i" >> "$LOG" 2>&1
echo "[2/4] NJOY, H in H2O at 600 K" | tee -a "$LOG"
printf '\n%s\n%s\n%s\n\n' "$NEUTRON_DATA" "$THERMAL_DATA" "$CPUS" | python3 "$PKG/run_tsl_processing.py" \
    "$HERE/inputs/tsl_process_batch_600K.i" >> "$LOG" 2>&1
echo "[3/4] ACE -> HDF5" | tee -a "$LOG"
printf '\n\n' | python3 "$PKG/compile_openmc_library.py" >> "$LOG" 2>&1
rm -rf "$HERE/library_600K"
cp -r "$PKG/data/hdf5_library" "$HERE/library_600K"
echo "      $(ls "$HERE/library_600K"/*.h5 | wc -l) HDF5 files in library_600K/ (expected 12)" | tee -a "$LOG"

echo "[4/4] covariance matrices (MF33, MF31, MF35; SCALE-44)" | tee -a "$LOG"
( cd "$HERE" && python3 process_covariances.py --endf "$NEUTRON_DATA" --cpus "$CPUS" ) >> "$LOG" 2>&1
echo "      $(ls "$HERE/covariance_600K/csv"/*.csv | wc -l) covariance CSV files in covariance_600K/csv/" | tee -a "$LOG"
grep -i -E "error|fail" "$LOG" | sort | uniq -c | head -20 || true
rm -rf "$TMP"
echo "done (log: $LOG)"

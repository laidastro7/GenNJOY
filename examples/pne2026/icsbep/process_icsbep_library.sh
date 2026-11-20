#!/usr/bin/env bash
# =============================================================================
# Timed processing of the ENDF/B-VIII.1 library used for the 324 ICSBEP cases
#
#     cd examples/pne2026/icsbep
#     bash process_icsbep_library.sh
#
# All GenNJOY prompts are answered automatically: NJOY command from PATH,
# the nuclear-data paths below, all CPU cores, tolerance 0.001.
# Results: timing_report_<date>.txt and logs_<date>/ in this folder.
# =============================================================================

# ---------------- Nuclear data (ENDF/B-VIII.1) ----------------
# Default: the package data folders filled by GenNJOY option 1.
# Override with:  NEUTRON_DATA=/path THERMAL_DATA=/path bash process_icsbep_library.sh

# ---------------- Batch files (in this folder) ----------------
HERE="$(cd "$(dirname "$0")" && pwd)"
NEUTRON_BATCH="$HERE/neutron_process_batch_324.i"
TSL_BATCH="$HERE/tsl_process_batch_324.i"

set -u
STAMP="$(date +%Y%m%d_%H%M)"
REPORT="$HERE/timing_report_${STAMP}.txt"
LOGDIR="$HERE/logs_${STAMP}"
mkdir -p "$LOGDIR"
log() { echo "$*" | tee -a "$REPORT"; }

# Locate the installed gennjoy package (scripts are run from it)
PKG="$(python3 -c 'import gennjoy, os; print(os.path.dirname(os.path.abspath(gennjoy.__file__)))' 2>/dev/null)"
if [ -z "$PKG" ] || [ ! -f "$PKG/run_neutron_processing.py" ]; then
  echo "Cannot locate the installed gennjoy package (python3 -c 'import gennjoy' failed)."
  exit 1
fi
NEUTRON_DATA="${NEUTRON_DATA:-$PKG/data/incident_neutron_endf}"
THERMAL_DATA="${THERMAL_DATA:-$PKG/data/thermal_scattering_endf}"

# ---------------- System information ----------------
log "=== GenNJOY timing report — $(date '+%Y-%m-%d %H:%M:%S %Z') ==="
grep -qi microsoft /proc/version && log "Environment: WSL ($(uname -r))" || log "Environment: native Linux ($(uname -r))"
log "OS: $(grep PRETTY_NAME /etc/os-release | cut -d= -f2)"
log ""
log "--- Hardware ---"
lscpu | grep -E "Model name|^CPU\(s\)|Thread\(s\) per core|Core\(s\) per socket|Socket\(s\)|CPU max MHz" | tee -a "$REPORT"
log "Logical CPUs available (nproc): $(nproc)"
log "CPUs used by GenNJOY: ${CPUS:-all (default)}"
free -h | head -2 | tee -a "$REPORT"
log ""
log "--- Software ---"
log "Python: $(python3 --version 2>&1)"
log "OpenMC (Python API): $(python3 -c 'import openmc; print(openmc.__version__)' 2>&1)"
log "NJOY executable: $(command -v njoy || echo 'njoy NOT FOUND in PATH')"
echo "stop" | njoy 2>&1 | grep -i -m3 -E "njoy|version" | tee -a "$REPORT"
log "gennjoy package: $PKG"
log "GenNJOY git commit: $(git -C "$PKG/.." rev-parse --short HEAD 2>/dev/null) ($(git -C "$PKG/.." describe --tags 2>/dev/null))"
log "GenNJOY uncommitted changes: $(git -C "$PKG/.." status --porcelain 2>/dev/null | wc -l) file(s)"
log ""
log "--- Data and inputs ---"
log "Neutron data: $NEUTRON_DATA  (filesystem: $(df -T "$NEUTRON_DATA" | awk 'NR==2{print $2}'))"
log "Thermal data: $THERMAL_DATA"
log "Neutron jobs: $(grep -c element_n "$NEUTRON_BATCH")   TSL jobs: $(grep -c element_t "$TSL_BATCH")"

# Check that all ENDF files exist
missing=0
for f in $(grep -o "element_n *= *[^ ]*" "$NEUTRON_BATCH" "$TSL_BATCH" | sed 's/.*= *//' | sort -u); do
  [ -f "$NEUTRON_DATA/$f" ] || { log "MISSING neutron file: $f"; missing=1; }
done
for f in $(grep -o "element_t *= *[^ ]*" "$TSL_BATCH" | sed 's/.*= *//' | sort -u); do
  [ -f "$THERMAL_DATA/$f" ] || { log "MISSING thermal file: $f"; missing=1; }
done
[ "$missing" -eq 0 ] && log "All ENDF files found." || { log "Stopping: missing ENDF files."; exit 1; }
log ""

# ---------------- Timed runs ----------------
run_step () {   # $1 label, $2 answers (one per line), $3... command
  local label="$1" answers="$2"; shift 2
  log "--- $label ---"
  local t0=$(date +%s)
  printf '%s' "$answers" | "$@" > "$LOGDIR/${label%% (*}.log" 2>&1
  local rc=$? t1=$(date +%s)
  local dt=$((t1 - t0))
  log "Exit code: $rc"
  log "Wall-clock time: ${dt} s ($(printf '%02dh:%02dm:%02ds' $((dt/3600)) $((dt%3600/60)) $((dt%60))))"
  log ""
}

# Prompt order — neutron: NJOY cmd, neutron data path, CPUs, tolerance
run_step "neutron (option 4)" $'\n'"$NEUTRON_DATA"$'\n'"${CPUS:-}"$'\n\n' \
  python3 "$PKG/run_neutron_processing.py" "$NEUTRON_BATCH"

# Prompt order — TSL: NJOY cmd, neutron data path, thermal data path, CPUs, tolerance
run_step "tsl (option 5)" $'\n'"$NEUTRON_DATA"$'\n'"$THERMAL_DATA"$'\n'"${CPUS:-}"$'\n\n' \
  python3 "$PKG/run_tsl_processing.py" "$TSL_BATCH"

# Prompt order — HDF5 conversion: neutron ACE path, thermal ACE path (package defaults)
run_step "hdf5 (option 6)" $'\n\n' \
  python3 "$PKG/compile_openmc_library.py"

# ---------------- Outputs ----------------
log "--- Outputs (in $PKG/data) ---"
log "Incident neutron ACE files: $(ls "$PKG/data/incident_neutron_ace" 2>/dev/null | grep -v -c xsdir)"
log "Thermal scattering ACE files: $(ls "$PKG/data/thermal_scattering_ace" 2>/dev/null | grep -v -c xsdir)"
log "HDF5 files: $(ls "$PKG/data/hdf5_library/"*.h5 2>/dev/null | wc -l)"
log "Error/failure lines in logs:"
grep -h -i -E "error|failed" "$LOGDIR"/*.log | sort | uniq -c | head -30 | tee -a "$REPORT"
log ""
log "Report: $REPORT"
log "Logs:   $LOGDIR"

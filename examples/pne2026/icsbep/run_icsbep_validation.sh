#!/usr/bin/env bash
# =============================================================================
# ICSBEP validation of GenNJOY: GenNJOY library vs independent reference library
# on all 394 mit-crpg ICSBEP OpenMC models (ENDF/B-VIII.1, NJOY2016.78).
#
#     cd examples/pne2026/icsbep
#     bash run_icsbep_validation.sh pilot      # 1) 12 representative cases, both libraries: timing check
#     bash run_icsbep_validation.sh all        # 2) every step below (restartable)
#
# Steps (each one can also be called alone):
#     clone      mit-crpg/benchmarks at commit ba41bee, C0 -> C12+C13  -> ./benchmarks
#     gennjoy    GenNJOY processing of the 394-case library (process_icsbep_library.sh) -> ./lib_GenNJOY
#     reference  OpenMC's openmc.data.njoy on the same ENDF files       -> ./lib_reference
#     runs       OpenMC runs of the 394 cases with both libraries        -> results_*.csv
#     ch2        reference library with NJOY/ACE c_H_in_CH2, rerun of the 16 CH2 cases
#     analyze    tables S1–S4, statistics, figures                       -> ./analysis
# =============================================================================
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

NJOY="$(command -v njoy)"
THREADS="${THREADS:-$(nproc)}"

# OpenMC run control, identical for every case and both libraries
PARTICLES="${PARTICLES:-10000}"
BATCHES="${BATCHES:-350}"
INACTIVE="${INACTIVE:-50}"
SEED="${SEED:-1}"
RUNOPT="--particles $PARTICLES --batches $BATCHES --inactive $INACTIVE --seed $SEED --threads $THREADS"

PKG="$(python3 -c 'import gennjoy, os; print(os.path.dirname(os.path.abspath(gennjoy.__file__)))')"
# ENDF/B-VIII.1 files: package data folders filled by GenNJOY option 1 (override with NEUTRON_DATA=... THERMAL_DATA=...)
NEUTRON_DATA="${NEUTRON_DATA:-$PKG/data/incident_neutron_endf}"
THERMAL_DATA="${THERMAL_DATA:-$PKG/data/thermal_scattering_endf}"

step_clone () {
  [ -d benchmarks/.git ] || git clone https://github.com/mit-crpg/benchmarks.git benchmarks
  git -C benchmarks checkout -q ba41bee && echo "benchmarks at $(git -C benchmarks rev-parse --short HEAD)"
  # ENDF/B-VIII.1 has no elemental carbon: C0 -> C12 + C13 (natural abundance)
  python3 convert_C0.py benchmarks/icsbep
}

step_gennjoy () {
  NEUTRON_BATCH="$HERE/neutron_process_batch_394.i" TSL_BATCH="$HERE/tsl_process_batch_394.i" \
    bash "$HERE/process_icsbep_library.sh"
  rm -rf lib_GenNJOY && cp -r "$PKG/data/hdf5_library" lib_GenNJOY
  python3 - <<'EOF'
import openmc.data, glob, os
lib = openmc.data.DataLibrary()
for f in sorted(glob.glob('lib_GenNJOY/*.h5')):
    lib.register_file(f)
lib.export_to_xml('lib_GenNJOY/cross_sections.xml')
print(len(lib), 'tables in lib_GenNJOY')
EOF
}

step_reference () {
  python3 build_reference_library.py --neutron-batch neutron_process_batch_394.i \
    --tsl-batch tsl_process_batch_394.i --neutron-dir "$NEUTRON_DATA" \
    --thermal-dir "$THERMAL_DATA" --out lib_reference --njoy "$NJOY" --jobs "$THREADS" \
    2>&1 | tee build_reference.log
}

run_lib () {   # $1 label, $2 library dir, $3 case list, $4 output csv
  python3 run_icsbep_suite.py --benchmarks benchmarks/icsbep --cases "$3" \
    --cross-sections "$2/cross_sections.xml" --label "$1" --out "$4" $RUNOPT
}

step_pilot () {
  run_lib GenNJOY   lib_GenNJOY   pilot_cases.txt pilot_GenNJOY.csv
  run_lib Reference lib_reference pilot_cases.txt pilot_Reference.csv
  python3 - <<'EOF'
import csv
r = list(csv.DictReader(open('pilot_GenNJOY.csv')))
t = sum(float(x['wall_time_s']) for x in r)
print(f'Pilot: {len(r)} cases, {t/60:.1f} min for one library;'
      f' about {t/len(r)*394/3600:.1f} h per library for 394 cases with these settings')
for x in r:
    print(f"  {x['case']:40s} sigma = {float(x['sigma_keff'])*1e5:5.1f} pcm  {float(x['wall_time_s']):7.0f} s")
EOF
}

step_runs () {
  run_lib GenNJOY   lib_GenNJOY   case_list_394.txt results_GenNJOY.csv
  run_lib Reference lib_reference case_list_394.txt results_Reference.csv
}

# H in CH2: OpenMC's use_endf_data=True takes the ENDF/B-VIII.1 incoherent elastic
# bound cross section SB without dividing it by the number of principal atoms
# (natom = 2), i.e. twice the NJOY/ACE value. Second reference library in which
# only c_H_in_CH2 is replaced by OpenMC's own NJOY/ACE data (use_endf_data=False).
step_ch2 () {
  [ -d lib_reference_ace ] || cp -r lib_reference lib_reference_ace
  python3 build_reference_library.py --neutron-batch neutron_process_batch_394.i \
    --tsl-batch tsl_process_batch_394.i --neutron-dir "$NEUTRON_DATA" \
    --thermal-dir "$THERMAL_DATA" --out lib_reference_ace --njoy "$NJOY" \
    --tsl-elastic ace --only tsl-HinCH2.endf
  run_lib Reference lib_reference_ace ch2_cases.txt results_Reference_CH2ace.csv
}

step_analyze () {
  B="results_Reference.csv"
  [ -f results_Reference_CH2ace.csv ] && B="$B results_Reference_CH2ace.csv"
  python3 analyze_icsbep.py --catalog case_catalog_394.csv --a results_GenNJOY.csv \
    --b $B --label-a GenNJOY --label-b Reference --out analysis
  # as built by OpenMC defaults (kept for the response to the reviewer)
  python3 analyze_icsbep.py --catalog case_catalog_394.csv --a results_GenNJOY.csv \
    --b results_Reference.csv --label-a GenNJOY --label-b Reference --out analysis_endf_elastic
}

case "${1:-}" in
  clone|gennjoy|reference|runs|ch2|analyze) "step_$1" ;;
  pilot) step_clone; [ -f lib_GenNJOY/cross_sections.xml ] || step_gennjoy
         [ -f lib_reference/cross_sections.xml ] || step_reference; step_pilot ;;
  all)   step_clone; [ -f lib_GenNJOY/cross_sections.xml ] || step_gennjoy
         [ -f lib_reference/cross_sections.xml ] || step_reference; step_runs; step_analyze ;;
  *) sed -n '2,17p' "$0" ;;
esac

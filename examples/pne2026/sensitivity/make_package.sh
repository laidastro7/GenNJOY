#!/usr/bin/env bash
# =============================================================================
# Self-contained package of the S/U calculations, for another machine.
#
#     bash make_package.sh            -> SU_Mosteller_package_<date>.tar.gz
#
# Contents: the gennjoy perturbation code, this folder's scripts and inputs,
# library_600K/ (HDF5, ~125 MB), covariance_600K/csv/ and README_PACKAGE.md.
# Nothing from results/ or work/ is included.
# =============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
[ -f "$HERE/library_600K/cross_sections.xml" ] || { echo "library_600K/ missing (prepare_600K.sh)"; exit 1; }
[ -d "$HERE/covariance_600K/csv" ] || { echo "covariance_600K/csv missing (prepare_600K.sh)"; exit 1; }

NAME="SU_Mosteller_package_$(date +%Y%m%d)"
STAGE="$(mktemp -d)/$NAME"
S="$STAGE/examples/pne2026/sensitivity"
mkdir -p "$STAGE/gennjoy" "$S"
for f in __init__.py perturbation.py fission_perturbation.py; do cp "$REPO/gennjoy/$f" "$STAGE/gennjoy/"; done
cp "$HERE"/su_common.py "$HERE"/su_tasks.py "$HERE"/su_run.py "$HERE"/su_analyze.py "$HERE"/run_su.sh \
   "$HERE"/campaign.py "$HERE"/run_campaign.sh "$S/"
# OpenMC version of the machine that prepared the data (checked by campaign.py)
command -v openmc >/dev/null || { echo "openmc not found in PATH"; exit 1; }
{ echo "version = $(openmc --version | sed -n 's/OpenMC version *//p')"
  echo "git_sha = $(openmc --version | sed -n 's/Git SHA1: *//p')"
  echo "python_api = $(python3 -c 'import openmc; print(openmc.__version__)')"; } > "$S/EXPECTED_OPENMC.txt"
grep -q "version = 0.15.0" "$S/EXPECTED_OPENMC.txt" || { echo "OpenMC on this machine is not 0.15.0"; cat "$S/EXPECTED_OPENMC.txt"; exit 1; }
cp "$HERE/README_PACKAGE.md" "$STAGE/README.md"
cp "$HERE/START_HERE.sh" "$STAGE/START_HERE.sh" && chmod +x "$STAGE/START_HERE.sh"
cp "$HERE/environment_su.yml" "$STAGE/environment.yml"
cp -r "$HERE/inputs" "$S/"
cp -r "$HERE/library_600K" "$S/"
mkdir -p "$S/covariance_600K"
cp -r "$HERE/covariance_600K/csv" "$S/covariance_600K/"
( cd "$REPO" && git rev-parse --short HEAD 2>/dev/null || echo unknown ) > "$STAGE/GENNJOY_COMMIT.txt"
( cd "$S/library_600K" && sha256sum *.h5 > SHA256SUMS )
tar -C "$(dirname "$STAGE")" -czf "$HERE/$NAME.tar.gz" "$NAME"
rm -rf "$(dirname "$STAGE")"
ls -lh "$HERE/$NAME.tar.gz"

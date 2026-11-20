#!/usr/bin/env python3
"""
Check that every ENDF file listed in the GenNJOY batch files exists
in the GenNJOY data directories (after Option 1: Download ENDF library).

Usage (from the gennjoy package directory, i.e. the folder containing data/ and inputs/):
    python3 check_endf_files.py inputs/neutron_process_batch.i inputs/tsl_process_batch.i
"""
import re
import sys
from pathlib import Path

NEUTRON_DIR = Path("data/incident_neutron_endf")
THERMAL_DIR = Path("data/thermal_scattering_endf")


def main():
    missing = []
    checked = 0
    for batch in sys.argv[1:]:
        for line in Path(batch).read_text().splitlines():
            for key, folder in (("element_n", NEUTRON_DIR), ("element_t", THERMAL_DIR)):
                m = re.search(rf"{key}\s*=\s*(\S+)", line)
                if m:
                    checked += 1
                    if not (folder / m.group(1)).exists():
                        missing.append(f"{folder / m.group(1)}  (from {batch})")
    print(f"Checked {checked} entries")
    if missing:
        print(f"MISSING {len(missing)} file(s):")
        for f in sorted(set(missing)):
            print("  ", f)
        sys.exit(1)
    print("All ENDF files found.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Replace natural carbon (C0) by C12 + C13 in the OpenMC ICSBEP models
of the mit-crpg/benchmarks repository.

ENDF/B-VIII.0 and VIII.1 provide no elemental carbon evaluation (C0);
it provides C12 and C13 instead. The OpenMC models in mit-crpg/benchmarks
still use C0 (all as atom fractions, ao=...), so they cannot run with an
ENDF/B-VIII.x library without this conversion.

Atom fractions (IUPAC natural abundance): C12 = 0.9893, C13 = 0.0107.

Usage:
    python3 convert_C0.py <path/to/benchmarks/icsbep>

Each modified materials.xml is first saved as materials.xml.orig_C0.
"""
import sys
import re
from pathlib import Path

ABUND = {"C12": 0.9893, "C13": 0.0107}
PATTERN = re.compile(r'^(\s*)<nuclide\s+ao="([^"]+)"\s+name="C0"\s*/>\s*$')


def convert(path: Path) -> int:
    lines = path.read_text().splitlines(keepends=True)
    out, n = [], 0
    for line in lines:
        m = PATTERN.match(line)
        if m:
            indent, ao = m.group(1), float(m.group(2))
            for nuc, frac in ABUND.items():
                out.append(f'{indent}<nuclide ao="{ao * frac:.10e}" name="{nuc}" />\n')
            n += 1
        else:
            if 'name="C0"' in line:
                raise ValueError(f"Unrecognised C0 entry in {path}: {line.strip()}")
            out.append(line)
    if n:
        backup = path.with_name("materials.xml.orig_C0")
        if not backup.exists():
            backup.write_text("".join(lines))
        path.write_text("".join(out))
    return n


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    files = sorted(root.glob("*/openmc/**/materials.xml"))
    total_files = total_entries = 0
    for f in files:
        n = convert(f)
        if n:
            total_files += 1
            total_entries += n
    print(f"Scanned {len(files)} materials.xml files")
    print(f"Converted {total_entries} C0 entries in {total_files} files")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Independent reference library for the ICSBEP comparison (Reviewer 1, comment 3).

The library is built with OpenMC's own NJOY interface (openmc.data.njoy:
IncidentNeutron.from_njoy -> make_ace, ThermalScattering.from_njoy ->
make_ace_thermal), i.e. without any GenNJOY code, from the same ENDF/B-VIII.1
files, the same NJOY2016 executable, the same temperatures and the same
reconstruction/broadening tolerance as the GenNJOY library. The nuclide and
TSL lists are read from the GenNJOY batch files, so both libraries contain
exactly the same materials.

Usage
-----
    python build_reference_library.py \
        --neutron-batch neutron_process_batch_394.i \
        --tsl-batch tsl_process_batch_394.i \
        --neutron-dir /path/incident_neutron_endf \
        --thermal-dir /path/thermal_scattering_endf \
        --out reference_library --njoy njoy --jobs 12

Output: <out>/*.h5, <out>/cross_sections.xml, <out>/build_times.csv
"""
import argparse
import csv
import os
import re
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import openmc.data
import openmc.data.thermal

# ENDF/B-VIII.1 identifies the two BeO evaluations as 'Be_BeO' and 'O_BeO',
# names that OpenMC 0.15.0 does not map to its standard table names yet.
# Only the name lookup is extended; the data are processed unchanged.
openmc.data.thermal._THERMAL_NAMES['c_Be_in_BeO'] += ('be_beo',)
openmc.data.thermal._THERMAL_NAMES['c_O_in_BeO'] += ('o_beo',)


def parse_batch(path):
    """Read a GenNJOY batch file.

    Neutron batch: one line per job, ``element_n = X  name = Y  temperatures = T``.
    TSL batch: an ``element_n = X`` line followed by
    ``element_t = Z  name = Y  temperatures = T``.
    """
    pat = re.compile(r'(element_n|element_t|name|temperatures)\s*=\s*(.+?)'
                     r'(?=\s+(?:element_n|element_t|name|temperatures)\s*=|$)')
    jobs = []
    for line in open(path):
        kv = dict(pat.findall(line.split('#')[0].strip()))
        if not kv:
            continue
        if 'element_t' in kv and jobs and 'element_t' not in jobs[-1]:
            jobs[-1].update(kv)
        else:
            jobs.append(kv)
    for j in jobs:
        j['temperatures'] = [float(t) for t in j['temperatures'].replace(',', ' ').split()]
    return jobs


def run_neutron(endf, temps, out, njoy, error):
    t0 = time.time()
    data = openmc.data.IncidentNeutron.from_njoy(endf, temperatures=temps, error=error,
                                                 njoy_exec=njoy)
    h5 = os.path.join(out, f'{data.name}.h5')
    data.export_to_hdf5(h5, 'w')
    return h5, time.time() - t0


def run_tsl(endf_n, endf_t, temps, out, njoy, error, use_endf=True):
    t0 = time.time()
    data = openmc.data.ThermalScattering.from_njoy(endf_n, endf_t, temperatures=temps,
                                                   error=error, njoy_exec=njoy,
                                                   use_endf_data=use_endf)
    h5 = os.path.join(out, f'{data.name}.h5')
    data.export_to_hdf5(h5, 'w')
    return h5, time.time() - t0


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--neutron-batch', required=True)
    p.add_argument('--tsl-batch', required=True)
    p.add_argument('--neutron-dir', required=True)
    p.add_argument('--thermal-dir', required=True)
    p.add_argument('--out', default='reference_library')
    p.add_argument('--njoy', default='njoy')
    p.add_argument('--error', type=float, default=0.001)
    p.add_argument('--jobs', type=int, default=os.cpu_count())
    p.add_argument('--tsl-elastic', choices=['endf', 'ace'], default='endf',
                   help="incoherent elastic TSL data: 'endf' = OpenMC default "
                        "(use_endf_data=True, replaces the ACE data by the ENDF "
                        "MF7/MT2 parameters), 'ace' = keep the NJOY/ACE data")
    p.add_argument('--only', nargs='+', default=None,
                   help='process only these ENDF files (e.g. to redo failed jobs); '
                        'existing HDF5 files are kept')
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)

    tasks, missing = [], []
    for j in parse_batch(a.neutron_batch):
        f = os.path.join(a.neutron_dir, j['element_n'])
        if not os.path.isfile(f):
            missing.append(f)
            continue
        tasks.append(('neutron', j['element_n'], os.path.getsize(f),
                      (run_neutron, f, j['temperatures'], a.out, a.njoy, a.error)))
    for j in parse_batch(a.tsl_batch):
        fn = os.path.join(a.neutron_dir, j['element_n'])
        ft = os.path.join(a.thermal_dir, j['element_t'])
        if not (os.path.isfile(fn) and os.path.isfile(ft)):
            missing.append(ft)
            continue
        tasks.append(('tsl', j['element_t'], os.path.getsize(ft),
                      (run_tsl, fn, ft, j['temperatures'], a.out, a.njoy, a.error,
                       a.tsl_elastic == 'endf')))
    if a.only:
        tasks = [t for t in tasks if t[1] in a.only]
    # longest (largest file) first, as in GenNJOY
    tasks.sort(key=lambda t: -t[2])
    for f in missing:
        print('MISSING ENDF file (skipped):', f)
    print(f'{len(tasks)} jobs on {a.jobs} workers')

    t0 = time.time()
    rows, failed = [], []
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        futs = {ex.submit(t[3][0], *t[3][1:]): t for t in tasks}
        for fut in as_completed(futs):
            kind, name = futs[fut][:2]
            try:
                h5, dt = fut.result()
                rows.append((kind, name, os.path.basename(h5), f'{dt:.1f}'))
                print(f'  ok   {name:40s} {dt:8.1f} s')
            except Exception as e:  # keep going, report at the end
                failed.append((kind, name, repr(e)))
                print(f'  FAIL {name}: {e!r}')
    wall = time.time() - t0

    lib = openmc.data.DataLibrary()
    for f in sorted(os.listdir(a.out)):
        if f.endswith('.h5'):
            lib.register_file(os.path.join(a.out, f))
    lib.export_to_xml(os.path.join(a.out, 'cross_sections.xml'))

    times = 'build_times.csv' if not a.only else 'build_times_rerun.csv'
    with open(os.path.join(a.out, times), 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['kind', 'endf_file', 'hdf5', 'time_s'])
        w.writerows(sorted(rows))
        w.writerow(['total_wall', '', '', f'{wall:.1f}'])
    print(f'Done: {len(rows)} ok, {len(failed)} failed, wall time {wall/60:.1f} min')
    for f in failed:
        print('FAILED:', *f)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Run the mit-crpg ICSBEP OpenMC models with a given cross_sections.xml
(Reviewer 1, comment 3).

Every case is run with the same OpenMC settings (particles, batches,
inactive batches, seed), so that two libraries (GenNJOY and the independent
reference library) are compared on identical models and settings. The model
geometry, materials and source are taken unchanged from the mit-crpg
repository; only the run-control parameters are overwritten. The script can
be stopped and restarted: cases already in the output CSV are skipped.

Usage
-----
    python run_icsbep_suite.py --benchmarks /path/benchmarks/icsbep \
        --cases case_list_394.txt --cross-sections /path/cross_sections.xml \
        --label GenNJOY --out results_GenNJOY.csv --threads 12
"""
import argparse
import csv
import os
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

import openmc

FIELDS = ['case', 'library', 'keff', 'sigma_keff', 'particles', 'batches',
          'inactive', 'seed', 'wall_time_s', 'status']


def model_dir(bm, case):
    p = case.strip('/').split('/', 1)
    return os.path.join(bm, p[0], 'openmc', *(p[1:] if len(p) > 1 else []))


def set_child(root, tag, value):
    el = root.find(tag)
    if el is None:
        el = ET.SubElement(root, tag)
    el.text = str(value)


def prepare(src, dst, a):
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    for f in ('geometry.xml', 'materials.xml', 'settings.xml', 'tallies.xml'):
        if os.path.isfile(os.path.join(src, f)):
            shutil.copy(os.path.join(src, f), dst)
    tree = ET.parse(os.path.join(dst, 'settings.xml'))
    root = tree.getroot()
    # older mit-crpg models keep run control inside an <eigenvalue> element,
    # which OpenMC reads in preference to top-level values: set it there too
    for parent in [root] + root.findall('eigenvalue'):
        set_child(parent, 'particles', a.particles)
        set_child(parent, 'batches', a.batches)
        set_child(parent, 'inactive', a.inactive)
    set_child(root, 'seed', a.seed)
    # no tallies, no intermediate state points, no source file: k_eff only
    for tag in ('state_point', 'source_point', 'output'):
        for el in root.findall(tag):
            root.remove(el)
    out = ET.SubElement(root, 'output')
    ET.SubElement(out, 'tallies').text = 'false'
    tree.write(os.path.join(dst, 'settings.xml'))
    if os.path.isfile(os.path.join(dst, 'tallies.xml')):
        os.remove(os.path.join(dst, 'tallies.xml'))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--benchmarks', required=True, help='path to benchmarks/icsbep')
    p.add_argument('--cases', required=True, help='one mit-crpg case per line')
    p.add_argument('--cross-sections', required=True)
    p.add_argument('--label', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--workdir', default=None)
    p.add_argument('--particles', type=int, default=20000)
    p.add_argument('--batches', type=int, default=350)
    p.add_argument('--inactive', type=int, default=50)
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--threads', type=int, default=os.cpu_count())
    p.add_argument('--keep', action='store_true', help='keep run directories')
    a = p.parse_args()

    xs = os.path.abspath(a.cross_sections)
    work = os.path.abspath(a.workdir or f'runs_{a.label}')
    os.makedirs(work, exist_ok=True)
    cases = [l.split('#')[0].strip().replace('./', '').replace('/openmc', '')
             for l in open(a.cases)]
    cases = [c for c in cases if c]

    done = set()
    if os.path.isfile(a.out):
        done = {r['case'] for r in csv.DictReader(open(a.out)) if r['status'] == 'ok'}
    new = not os.path.isfile(a.out)
    fh = open(a.out, 'a', newline='')
    w = csv.DictWriter(fh, fieldnames=FIELDS)
    if new:
        w.writeheader()

    env = dict(os.environ, OPENMC_CROSS_SECTIONS=xs)
    todo = [c for c in cases if c not in done]
    print(f'{len(cases)} cases, {len(done)} already done, {len(todo)} to run '
          f'with {a.label} ({xs})')
    for i, c in enumerate(todo, 1):
        run = os.path.join(work, c.replace('/', '__'))
        prepare(model_dir(a.benchmarks, c), run, a)
        t0 = time.time()
        r = subprocess.run(['openmc', '-s', str(a.threads)], cwd=run, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        dt = time.time() - t0
        row = dict(case=c, library=a.label, particles=a.particles, batches=a.batches,
                   inactive=a.inactive, seed=a.seed, wall_time_s=f'{dt:.1f}')
        sp = os.path.join(run, f'statepoint.{a.batches}.h5')
        if r.returncode == 0 and os.path.isfile(sp):
            with openmc.StatePoint(sp) as s:
                k = s.keff
            row.update(keff=f'{k.n:.6f}', sigma_keff=f'{k.s:.6f}', status='ok')
            if not a.keep:
                shutil.rmtree(run)
        else:
            open(os.path.join(run, 'openmc.log'), 'w').write(r.stdout)
            row.update(keff='', sigma_keff='', status=f'failed (rc={r.returncode})')
        w.writerow(row)
        fh.flush()
        print(f'[{i}/{len(todo)}] {c:45s} {row["keff"]:>9s} +/- {row["sigma_keff"]:>8s}'
              f'  {dt:7.0f} s  {row["status"]}')
    fh.close()


if __name__ == '__main__':
    main()

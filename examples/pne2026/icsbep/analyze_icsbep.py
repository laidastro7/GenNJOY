#!/usr/bin/env python3
"""
Analysis of the ICSBEP results for Reviewer 1, comments 3 and 7.

Inputs
  case_catalog_394.csv     model list, status, benchmark values (k_bench, sigma_bench)
                           and LANL MCNP ENDF/B-VIII.1 results published by NNDC
  results_<A>.csv          output of run_icsbep_suite.py for library A (GenNJOY)
  results_<B>.csv          same for library B (independent reference library)

Outputs (in --out)
  Supplementary_ICSBEP.xlsx  sheets: README, S1_per_case, S2_C-E_by_category,
                             S3_library_difference, S4_processing_options
  S1_per_case.csv, S2_stats_by_category.csv, S3_library_difference.csv
  fig_CE_by_case.png, fig_library_difference.png

Definitions (all differences in pcm = 1e-5 in k)
  statistics set models that ran, have a benchmark k_eff, and are not an
                 alternative model of an experiment already included
  C - E          calculated minus benchmark k_eff
  sigma_tot      sqrt(sigma_bench^2 + sigma_MC^2);  z = (C - E) / sigma_tot
  mean, SD       arithmetic mean and standard deviation of (C - E)
  MAD            mean absolute deviation, mean |C - E|
  RMS            sqrt(mean (C - E)^2)
  chi2/N         mean z^2
  Delta          k_A - k_B (same model, same settings, same seed);
                 sigma_Delta = sqrt(sigma_A^2 + sigma_B^2) (conservative: the
                 positive correlation due to the common seed is ignored)
"""
import argparse
import csv
import math
import os
from collections import OrderedDict, defaultdict

PCM = 1e5


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return math.nan


def read_results(path):
    return {r['case']: r for r in csv.DictReader(open(path)) if r['status'] == 'ok'}


def stats(d, z):
    n = len(d)
    if n == 0:
        return OrderedDict(N=0)
    mean = sum(d) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in d) / (n - 1)) if n > 1 else math.nan
    srt = sorted(d)
    med = srt[n // 2] if n % 2 else 0.5 * (srt[n // 2 - 1] + srt[n // 2])
    return OrderedDict(
        N=n, mean_pcm=round(mean, 1), SD_pcm=round(sd, 1),
        SEM_pcm=round(sd / math.sqrt(n), 1) if n > 1 else math.nan,
        median_pcm=round(med, 1), MAD_pcm=round(sum(abs(x) for x in d) / n, 1),
        RMS_pcm=round(math.sqrt(sum(x * x for x in d) / n), 1),
        min_pcm=round(srt[0], 1), max_pcm=round(srt[-1], 1),
        chi2_per_N=round(sum(x * x for x in z) / n, 2),
        frac_within_1sigma=round(sum(abs(x) <= 1 for x in z) / n, 3),
        frac_within_2sigma=round(sum(abs(x) <= 2 for x in z) / n, 3),
        frac_within_3sigma=round(sum(abs(x) <= 3 for x in z) / n, 3))


PROCESSING_OPTIONS = [
    # step, GenNJOY v1.0.1, OpenMC openmc.data.njoy (reference)
    ('NJOY executable', 'NJOY2016.78', 'same executable'),
    ('ENDF files', 'ENDF/B-VIII.1 (NNDC, Aug. 2024)', 'identical files'),
    ('Temperature', '293.6 K (Be-metal and graphite TSL: 296 K)', 'identical'),
    ('RECONR', 'err = 0.001', 'err = 0.001'),
    ('BROADR', 'errthn = 0.001', 'errthn = 0.001'),
    ('HEATR', 'two runs (local = 1 and 0), total KERMA (MT301) only',
     'two runs (local = 1 and 0), partial KERMAs 302 318 402 444'),
    ('GASPR', 'yes', 'yes'),
    ('UNRESR', 'yes (if URR present), 10 background cross sections', 'not run'),
    ('PURR', 'if URR present: 20 bins, 64 ladders, 10 background cross sections',
     'always: 20 bins, 64 ladders, 1 background cross section (infinite dilution)'),
    ('THERMR (TSL)', 'one run (bound), nbin = 20 equiprobable cosines, MT221/MT222; '
     'iin, icoh, natom, emax read from MF7', 'free gas (nbin = 12, MT221) + bound (nbin = 16, MT222/MT223); '
     'natom, emax from MF7'),
    ('ACER (neutron)', 'iopt = 1, newfor = 1 (0 as automatic fallback), iopp = 1, ismooth = 1',
     'iopt = 1, newfor = 1, iopp = 1, ismooth = 1'),
    ('ACER (TSL)', 'nbint = 64, iwt = 2, elastic type from LTHR', 'nbint = 64, iwt = 2, elastic type from LTHR'),
    ('ACE to HDF5', 'openmc-ace-to-hdf5 (IncidentNeutron / ThermalScattering.from_ace)',
     'IncidentNeutron.from_njoy / ThermalScattering.from_njoy (also store 0 K elastic and fission energy '
     'release; incoherent elastic TSL data taken directly from ENDF)'),
]


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--catalog', default='case_catalog_394.csv')
    p.add_argument('--a', required=True, help='results CSV of library A (GenNJOY)')
    p.add_argument('--b', required=True, nargs='+',
                   help='results CSV(s) of library B (reference); for a case present '
                        'in several files the last file wins')
    p.add_argument('--label-a', default='GenNJOY')
    p.add_argument('--label-b', default='Reference')
    p.add_argument('--out', default='analysis')
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)

    cat = list(csv.DictReader(open(a.catalog)))
    ra, rb = read_results(a.a), {}
    for f in a.b:
        rb.update(read_results(f))
    LA, LB = a.label_a, a.label_b

    s1 = []
    for c in cat:
        r = OrderedDict((k, c[k]) for k in (
            'case', 'evaluation', 'icsbep_case', 'category', 'model_variant',
            'extra_data_needed', 'k_bench', 'sigma_bench',
            'bench_source', 'nndc_name', 'C_LANL_VIII1', 'uC_LANL_VIII1'))
        E, uE = fnum(c['k_bench']), fnum(c['sigma_bench'])
        for lab, res in ((LA, ra), (LB, rb)):
            x = res.get(c['case'])
            k, s = (fnum(x['keff']), fnum(x['sigma_keff'])) if x else (math.nan, math.nan)
            r[f'k_{lab}'], r[f'sigma_{lab}'] = k, s
            r[f'C-E_{lab}_pcm'] = round((k - E) * PCM, 1) if not math.isnan(k - E) else ''
            st = math.sqrt(uE ** 2 + s ** 2) if not math.isnan(uE) else math.nan
            r[f'z_{lab}'] = round((k - E) / st, 2) if st and not math.isnan(k - E + st) else ''
        kA, sA, kB, sB = r[f'k_{LA}'], r[f'sigma_{LA}'], r[f'k_{LB}'], r[f'sigma_{LB}']
        if not math.isnan(kA - kB):
            sd = math.hypot(sA, sB)
            r['Delta_pcm'] = round((kA - kB) * PCM, 1)
            r['sigma_Delta_pcm'] = round(sd * PCM, 1)
            r['z_Delta'] = round((kA - kB) / sd, 2)
        else:
            r['Delta_pcm'] = r['sigma_Delta_pcm'] = r['z_Delta'] = ''
        v = c['model_variant']
        r['in_CE_statistics'] = int(not math.isnan(E) and not math.isnan(r[f'k_{LA}'])
                                    and not v.startswith(('alternative', 'obsolete')))
        cl = fnum(c['C_LANL_VIII1'])
        r[f'k_{LA}-C_LANL_pcm'] = round((kA - cl) * PCM, 1) if not math.isnan(kA - cl) else ''
        s1.append(r)

    # S2: C-E statistics by category and overall, for each library
    s2 = []
    groups = defaultdict(list)
    for r in s1:
        groups[r['category']].append(r)
    subsets = (('statistics set', lambda r: r['in_CE_statistics'] == 1),)
    for sub, keep in subsets:
        for lab in (LA, LB):
            for g in sorted(groups) + ['ALL']:
                rows = [r for r in (s1 if g == 'ALL' else groups[g]) if keep(r)]
                if not rows:
                    continue
                d = [r[f'C-E_{lab}_pcm'] for r in rows if r[f'C-E_{lab}_pcm'] != '']
                z = [r[f'z_{lab}'] for r in rows if r[f'z_{lab}'] != '']
                s2.append(OrderedDict(subset=sub, library=lab, category=g, **stats(d, z)))

    # S3: library difference A - B
    s3 = []
    for g in sorted(groups) + ['ALL']:
        rows = s1 if g == 'ALL' else groups[g]
        d = [r['Delta_pcm'] for r in rows if r['Delta_pcm'] != '']
        z = [r['z_Delta'] for r in rows if r['z_Delta'] != '']
        st = stats(d, z)
        if st['N'] > 1:
            st['t_mean_vs_0'] = round(st['mean_pcm'] / st['SEM_pcm'], 2) if st['SEM_pcm'] else ''
            st['n_abs_z_gt_3'] = sum(abs(x) > 3 for x in z)
        s3.append(OrderedDict(category=g, **st))

    def write_csv(name, rows):
        with open(os.path.join(a.out, name), 'w', newline='') as f:
            keys = list(OrderedDict.fromkeys(k for r in rows for k in r))
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)

    write_csv('S1_per_case.csv', s1)
    write_csv('S2_stats_by_category.csv', s2)
    write_csv('S3_library_difference.csv', s3)

    try:
        import openpyxl
        from openpyxl.styles import Font
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'README'
        for line in __doc__.strip().splitlines():
            ws.append([line])
        for title, rows in (('S1_per_case', s1), ('S2_C-E_by_category', s2),
                            ('S3_library_difference', s3)):
            ws = wb.create_sheet(title)
            keys = list(OrderedDict.fromkeys(k for r in rows for k in r))
            ws.append(keys)
            for c in ws[1]:
                c.font = Font(bold=True)
            for r in rows:
                ws.append([('' if isinstance(r.get(k), float) and math.isnan(r.get(k))
                            else r.get(k, '')) for k in keys])
            ws.freeze_panes = 'B2'
        ws = wb.create_sheet('S4_processing_options')
        ws.append(['Step', LA, LB])
        for c in ws[1]:
            c.font = Font(bold=True)
        for row in PROCESSING_OPTIONS:
            ws.append(list(row))
        wb.save(os.path.join(a.out, 'Supplementary_ICSBEP.xlsx'))
    except ImportError:
        print('openpyxl not installed: CSV files only')

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        rows = [r for r in s1 if r[f'C-E_{LA}_pcm'] != '']
        x = range(len(rows))
        fig, ax = plt.subplots(figsize=(14, 4.5))
        ue = [fnum(r['sigma_bench']) * PCM for r in rows]
        ax.fill_between(x, [-u for u in ue], ue, step='mid', color='0.85', label='Benchmark uncertainty (1σ)')
        for lab, m in ((LA, 'o'), (LB, 'x')):
            ax.errorbar(x, [r[f'C-E_{lab}_pcm'] if r[f'C-E_{lab}_pcm'] != '' else math.nan for r in rows],
                        yerr=[fnum(r[f'sigma_{lab}']) * PCM for r in rows], fmt=m, ms=3, lw=0.6, label=lab)
        ax.axhline(0, color='k', lw=0.6)
        ax.set_ylabel('C − E (pcm)')
        ax.set_xlabel('Case index (ordered as in Table S1)')
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(os.path.join(a.out, 'fig_CE_by_case.png'), dpi=200)

        z = [r['z_Delta'] for r in s1 if r['z_Delta'] != '']
        if z:
            fig, ax = plt.subplots(figsize=(5, 3.5))
            ax.hist(z, bins=30, density=True, alpha=0.7, label=f'{LA} − {LB}')
            t = [i / 20 for i in range(-100, 101)]
            ax.plot(t, [math.exp(-u * u / 2) / math.sqrt(2 * math.pi) for u in t], 'k', lw=1, label='N(0,1)')
            ax.set_xlabel('Δk / σ_Δ')
            ax.legend(fontsize=8)
            fig.tight_layout()
            fig.savefig(os.path.join(a.out, 'fig_library_difference.png'), dpi=200)
    except ImportError:
        print('matplotlib not installed: no figures')

    allA = [r for r in s2 if r['library'] == LA and r['category'] == 'ALL'
            and r['subset'] == 'statistics set'][0]
    allD = s3[-1]
    print(f'{LA} C-E over {allA["N"]} cases: mean {allA.get("mean_pcm")} pcm, '
          f'SD {allA.get("SD_pcm")}, MAD {allA.get("MAD_pcm")}, RMS {allA.get("RMS_pcm")}, '
          f'chi2/N {allA.get("chi2_per_N")}')
    print(f'{LA} - {LB} over {allD["N"]} cases: mean {allD.get("mean_pcm")} pcm '
          f'(t = {allD.get("t_mean_vs_0")}), SD {allD.get("SD_pcm")}, '
          f'max |Delta| {max(abs(allD.get("min_pcm", 0)), abs(allD.get("max_pcm", 0)))} pcm, '
          f'chi2/N {allD.get("chi2_per_N")}, |z|>3: {allD.get("n_abs_z_gt_3")}')


if __name__ == '__main__':
    main()

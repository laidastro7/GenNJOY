#!/usr/bin/env python3
"""
Figure 9 of the GenNJOY manuscript: C - E for the ICSBEP models of the statistical set.

Input : analysis/S1_per_case.csv (written by analyze_icsbep.py)
Output: fig9_CE_by_case.tif (600 dpi, LZW-compressed TIFF) and fig9_CE_by_case.png

Usage:
    python3 plot_fig9.py [path/to/S1_per_case.csv] [--dpi 600] [--out fig9_CE_by_case]
"""
import argparse
import csv
import math
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BLUE, ORANGE, INK, MUTED = '#2a78d6', '#eb6834', '#1f1f1e', '#8a8a85'
SHORT = {'HEU-MET-FAST': 'HMF', 'HEU-MET-INTER': 'HMI', 'HEU-SOL-THERM': 'HST', 'HEU-COMP-INTER': 'HCI',
         'IEU-MET-FAST': 'IMF', 'IEU-COMP-FAST': 'ICF', 'LEU-COMP-THERM': 'LCT', 'LEU-SOL-THERM': 'LST',
         'MIX-COMP-FAST': 'MCF', 'MIX-COMP-THERM': 'MCT', 'MIX-MET-FAST': 'MMF', 'MIX-MET-INTER': 'MMI',
         'PU-COMP-INTER': 'PCI', 'PU-MET-FAST': 'PMF', 'PU-MET-INTER': 'PMI', 'PU-SOL-THERM': 'PST',
         'SPEC-MET-FAST': 'SMF', 'U233-COMP-THERM': 'UCT', 'U233-MET-FAST': 'UMF',
         'U233-SOL-INTER': 'USI', 'U233-SOL-THERM': 'UST'}
MIN_LABELLED = 5          # categories with fewer models are not labelled


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return math.nan


def sort_key(case):
    series = case.split('/')[0]
    rest = case[len(series):]
    return series, [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', rest)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('csv', nargs='?', default='analysis/S1_per_case.csv')
    p.add_argument('--dpi', type=int, default=600)
    p.add_argument('--out', default='fig9_CE_by_case')
    a = p.parse_args()

    plt.rcParams.update({'font.family': 'DejaVu Serif', 'font.size': 9,
                         'axes.edgecolor': MUTED, 'axes.linewidth': 0.6,
                         'xtick.color': INK, 'ytick.color': INK, 'axes.labelcolor': INK})

    rows = [r for r in csv.DictReader(open(a.csv)) if r['in_CE_statistics'] == '1']
    rows.sort(key=lambda r: sort_key(r['case']))
    n = len(rows)
    x = list(range(n))
    ce_g = [num(r['C-E_GenNJOY_pcm']) for r in rows]
    ce_r = [num(r['C-E_Reference_pcm']) for r in rows]
    sig = []                                           # combined 1-sigma: sqrt(u_E^2 + sigma_MC^2)
    for r in rows:
        ue = num(r['sigma_bench'])
        ue = 0.0 if math.isnan(ue) else ue
        sig.append(math.hypot(ue, num(r['sigma_GenNJOY'])) * 1e5)

    fig, ax = plt.subplots(figsize=(7.1, 3.4))
    ax.axhline(0, color=INK, lw=0.6, zorder=1)
    ax.errorbar(x, ce_g, yerr=sig, fmt='o', ms=2.6, color=BLUE, ecolor='#9ec5f4',
                elinewidth=0.6, capsize=0, zorder=3, label='GenNJOY (bars: combined 1σ)')
    ax.plot(x, ce_r, 'x', ms=2.6, mew=0.6, color=ORANGE, zorder=4,
            label='Independent reference library')

    # category separators and labels
    ymin, ymax = -2000, 2600
    cats = [r['category'] for r in rows]
    bounds = [0] + [i for i in range(1, n) if cats[i] != cats[i - 1]] + [n]
    for lo, hi in zip(bounds[:-1], bounds[1:]):
        if lo > 0:
            ax.axvline(lo - 0.5, color='#d6d6d2', lw=0.5, zorder=0)
        if hi - lo >= MIN_LABELLED:
            ax.text((lo + hi - 1) / 2, ymax * 0.93, SHORT.get(cats[lo], cats[lo]),
                    ha='center', va='top', fontsize=6.5, color=MUTED, rotation=90)

    ax.set_xlim(-1, n)
    ax.set_ylim(ymin, ymax)
    ax.set_ylabel('C − E (pcm)')
    ax.set_xlabel(f'Benchmark model (N = {n}), grouped by category')
    ax.grid(axis='y', color='#ececea', lw=0.5)
    ax.set_axisbelow(True)
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(loc='lower right', fontsize=7, frameon=False)
    fig.tight_layout()

    fig.savefig(a.out + '.tif', dpi=a.dpi, format='tiff', pil_kwargs={'compression': 'tiff_lzw'})
    fig.savefig(a.out + '.png', dpi=a.dpi)
    print(f'{n} models -> {a.out}.tif and {a.out}.png at {a.dpi} dpi')


if __name__ == '__main__':
    main()

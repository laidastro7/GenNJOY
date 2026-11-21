#!/usr/bin/env python3
"""
Figures 10 and 11 of the GenNJOY manuscript: GenNJOY library vs independent reference library.

  Fig. 10: distribution of Delta_k / sigma_Delta for all calculated models, with N(0,1).
  Fig. 11: Delta_k for the models that contain polyethylene, reference library built with
           the default options of openmc.data.njoy (crosses) and with the NJOY incoherent
           elastic data of hydrogen in polyethylene (circles).

Inputs : analysis/S1_per_case.csv                (reference library with NJOY CH2 data)
         analysis_endf_elastic/S1_per_case.csv   (reference library, OpenMC default options)
         ch2_cases.txt                           (models that contain polyethylene)
Outputs: fig10_library_difference.tif/.png and fig11_polyethylene.tif/.png (600 dpi)

Usage:
    python3 plot_fig10_11.py [--a analysis/S1_per_case.csv] [--b analysis_endf_elastic/S1_per_case.csv]
                             [--ch2 ch2_cases.txt] [--dpi 600]
"""
import argparse
import csv
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BLUE, ORANGE, INK, MUTED = '#2a78d6', '#eb6834', '#1f1f1e', '#8a8a85'
ABBR = [('heu-met-fast', 'HMF'), ('pu-met-fast', 'PMF'), ('ieu-met-fast', 'IMF'),
        ('u233-comp-therm', 'UCT'), ('/case-', '-'), ('/c-', '-'), ('/', '-')]


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return math.nan


def save(fig, name, dpi):
    fig.savefig(name + '.tif', dpi=dpi, format='tiff', pil_kwargs={'compression': 'tiff_lzw'})
    fig.savefig(name + '.png', dpi=dpi)
    print(f'-> {name}.tif and {name}.png at {dpi} dpi')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--a', default='analysis/S1_per_case.csv')
    p.add_argument('--b', default='analysis_endf_elastic/S1_per_case.csv')
    p.add_argument('--ch2', default='ch2_cases.txt')
    p.add_argument('--dpi', type=int, default=600)
    a = p.parse_args()
    plt.rcParams.update({'font.family': 'DejaVu Serif', 'font.size': 9,
                         'axes.edgecolor': MUTED, 'axes.linewidth': 0.6,
                         'xtick.color': INK, 'ytick.color': INK, 'axes.labelcolor': INK})

    A = {r['case']: r for r in csv.DictReader(open(a.a))}
    B = {r['case']: r for r in csv.DictReader(open(a.b))}

    # ---------------- Figure 10 ----------------
    z = [num(r['z_Delta']) for r in A.values() if r['z_Delta'] != '']
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    ax.hist(z, bins=[i / 4 for i in range(-16, 17)], density=True, color=BLUE, alpha=0.85,
            edgecolor='white', linewidth=0.6, label=f'{len(z)} models')
    t = [i / 50 for i in range(-200, 201)]
    ax.plot(t, [math.exp(-u * u / 2) / math.sqrt(2 * math.pi) for u in t], color=INK, lw=1,
            label='N(0, 1)')
    ax.set_xlim(-4, 4)
    ax.set_xlabel('Δk / σ$_Δ$')
    ax.set_ylabel('Probability density')
    ax.spines[['top', 'right']].set_visible(False)
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=7.5, frameon=False, loc='upper left')
    fig.tight_layout()
    save(fig, 'fig10_library_difference', a.dpi)
    plt.close(fig)

    # ---------------- Figure 11 ----------------
    cases = [c.strip() for c in open(a.ch2) if c.strip()]
    def label(c):
        for s, r in ABBR:
            c = c.replace(s, r)
        return c
    cases.sort(key=label)
    x = list(range(len(cases)))
    fig, ax = plt.subplots(figsize=(7.1, 3.2))
    for S, col, mk, name in ((B, ORANGE, 'x', 'GenNJOY − reference built with OpenMC default options (ENDF incoherent elastic data)'),
                             (A, BLUE, 'o', 'GenNJOY − reference built with the NJOY incoherent elastic data')):
        y = [num(S[c]['Delta_pcm']) for c in cases]
        e = [num(S[c]['sigma_Delta_pcm']) for c in cases]
        ax.errorbar(x, y, yerr=e, fmt=mk, ms=3.4, mew=0.9, color=col, ecolor=col,
                    elinewidth=0.7, capsize=0, label=name)
    ax.axhline(0, color=INK, lw=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels([label(c) for c in cases], rotation=90, fontsize=7)
    ax.set_xlim(-0.7, len(cases) - 0.3)
    ax.set_ylim(-300, 700)
    ax.set_ylabel('Δk = GenNJOY − reference (pcm)')
    ax.grid(axis='y', color='#ececea', lw=0.5)
    ax.set_axisbelow(True)
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(fontsize=7, frameon=False, loc='upper center', bbox_to_anchor=(0.5, 1.13), ncol=1)
    fig.tight_layout()
    save(fig, 'fig11_polyethylene', a.dpi)
    plt.close(fig)


if __name__ == '__main__':
    main()

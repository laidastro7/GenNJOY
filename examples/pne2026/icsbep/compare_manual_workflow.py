#!/usr/bin/env python3
"""
Compare the time needed to produce the ICSBEP library with GenNJOY and with a
manual, one-nuclide-at-a-time NJOY2016 workflow.

Manual workflow assumed:
  * the user writes one NJOY2016 input deck per nuclide (MAT number, URR check,
    temperatures, sigma-zero grid, ACER options) and per thermal-scattering
    evaluation (MAT numbers, number of principal atoms, maximum energy,
    elastic type), using a template;
  * the decks are run one after the other on one core (serial NJOY time,
    measured with GenNJOY on one core: CPUS=1);
  * the ACE files are then converted to HDF5 (same conversion time as GenNJOY).
Deck-preparation times are assumptions, given as low / typical / high values.

Usage:
  python3 compare_manual_workflow.py timing_report_parallel.txt timing_report_serial.txt
"""
import re
import sys

N_NEUTRON, N_TSL = 158, 6
DECK_MIN_NEUTRON = {"low": 5.0, "typical": 10.0, "high": 20.0}   # minutes per nuclide
DECK_MIN_TSL = {"low": 10.0, "typical": 20.0, "high": 30.0}      # minutes per TSL evaluation
GENNJOY_HANDS_ON_MIN = 5.0   # edit/copy the batch files and answer the CLI prompts


def step_times(report):
    txt = open(report, encoding="utf-8").read()
    out = {}
    for key in ("neutron", "tsl", "hdf5"):
        m = re.search(r"--- " + key + r"[^\n]*---\n(?:[^\n]*\n)*?Wall-clock time: (\d+) s", txt)
        out[key] = int(m.group(1)) if m else None
    cpu = re.search(r"Logical CPUs available \(nproc\): (\d+)", txt)
    out["cpus"] = int(cpu.group(1)) if cpu else None
    return out


def hm(seconds):
    h, m = divmod(int(round(seconds / 60.0)), 60)
    return f"{h} h {m:02d} min"


def main():
    par, ser = step_times(sys.argv[1]), step_times(sys.argv[2])
    g_wall = par["neutron"] + par["tsl"] + par["hdf5"]
    njoy_serial = ser["neutron"] + ser["tsl"]
    print(f"GenNJOY, {par['cpus']} logical cores")
    print(f"  wall-clock time      : {hm(g_wall)}  (neutron {hm(par['neutron'])}, TSL {par['tsl']} s, HDF5 {par['hdf5']} s)")
    print(f"  hands-on time        : about {GENNJOY_HANDS_ON_MIN:.0f} min")
    print(f"NJOY2016 run one nuclide at a time (measured on 1 core): {hm(njoy_serial)}")
    print()
    print("| Deck preparation | Manual deck writing | Manual total (decks + serial NJOY + HDF5) | Ratio to GenNJOY wall time |")
    print("|---|---|---|---|")
    for case in ("low", "typical", "high"):
        decks = 60.0 * (N_NEUTRON * DECK_MIN_NEUTRON[case] + N_TSL * DECK_MIN_TSL[case])
        total = decks + njoy_serial + par["hdf5"]
        print(f"| {case} ({DECK_MIN_NEUTRON[case]:.0f} min/nuclide, {DECK_MIN_TSL[case]:.0f} min/TSL) | {hm(decks)} | {hm(total)} | {total / g_wall:.0f} |")


if __name__ == "__main__":
    main()

"""
Run the OpenMC calculations of the S/U study.

    python su_run.py reference --preset full --threads 80
        unperturbed run with fine-group flux tallies (needed by su_tasks.py)

    python su_run.py run --preset full --jobs 8 --threads 10 [--limit N] [--only REGEX]
        runs every task of tasks.csv that is not yet in results/results_<preset>.csv
        (restartable: stop it at any time and run the same command again)

Each perturbed task writes the perturbed HDF5 file(s) with gennjoy.perturbation,
checks them (verification report in results/reports/), runs OpenMC with its own
seed, records k and its standard deviation, and deletes the perturbed files.
"""
import argparse
import csv
import json
import multiprocessing as mp
import os
import re
import shutil
import socket
import subprocess
import sys
import time

import numpy as np

import su_common as C

sys.path.insert(0, str(C.HERE.parents[2]))
from gennjoy import perturbation as P   # noqa: E402

FIELDS = ["task_id", "kind", "nuclide", "mt", "group", "eps", "seed", "keff", "keff_std",
          "preset", "particles", "batches", "inactive", "threads", "t_library_s", "t_openmc_s",
          "verification", "status", "host", "date"]


def _die_with_parent():
    """OpenMC is stopped when the Python process that launched it stops (Linux)."""
    try:
        import ctypes
        import signal
        ctypes.CDLL("libc.so.6").prctl(1, signal.SIGTERM)   # PR_SET_PDEATHSIG
    except Exception:
        pass


def run_openmc(wd, threads, log):
    with open(log, "w") as f:
        r = subprocess.run(["openmc", "-s", str(threads)], cwd=wd, stdout=f, stderr=subprocess.STDOUT,
                           preexec_fn=_die_with_parent)
    return r.returncode


def do_task(args):
    task, preset, threads = args
    p = C.PRESETS[preset]
    tid = task["task_id"]
    wd = C.WORK_DIR / tid
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)
    row = {k: task.get(k, "") for k in ("task_id", "kind", "nuclide", "mt", "group", "eps", "seed")}
    row.update(preset=preset, threads=threads, host=socket.gethostname(),
               date=time.strftime("%Y-%m-%d %H:%M:%S"), **p)
    xml = C.LIBRARY_XML
    t0 = time.time()
    try:
        if task["kind"] != "ref":
            rep = P.write_perturbed_library(C.LIBRARY_XML, wd / "lib", task["nuclide"], int(task["mt"]),
                                            float(task["e_low"]), float(task["e_high"]), float(task["eps"]),
                                            couple_thermal=True, verify=True)
            rdir = C.RESULTS_DIR / "reports"
            rdir.mkdir(parents=True, exist_ok=True)
            with open(rdir / f"{tid}.json", "w") as f:
                json.dump(rep, f, indent=1, default=float)
            ok = rep["verification"]["ok"] and all(t["verification"]["ok"] for t in rep["thermal"])
            row["verification"] = "ok" if ok else "FAILED"
            if not rep.get("changed", True):
                row["verification"] += " (no data changed)"
            if not ok:   # never run OpenMC with data that failed the verification
                row["status"] = "verification_failed"
                return row
            xml = wd / "lib" / "cross_sections.xml"
        row["t_library_s"] = round(time.time() - t0, 1)
        # OpenMC 0.15 can stop on rare numerical events ("Did not sample any nuclide
        # during collision"); the calculation is then repeated with another seed
        seed = int(task["seed"])
        t1 = time.time()
        for attempt in range(3):
            model = C.build_model(xml, p["particles"], p["batches"], p["inactive"], seed)
            model.export_to_xml(wd)
            rc = run_openmc(wd, threads, wd / "openmc.log")
            sp = wd / f"statepoint.{p['batches']}.h5"
            if rc == 0 and sp.exists():
                break
            tail = (wd / "openmc.log").read_text(errors="ignore").splitlines()[-3:]
            (C.RESULTS_DIR / "errors").mkdir(parents=True, exist_ok=True)
            (C.RESULTS_DIR / "errors" / f"{tid}_seed{seed}.log").write_text("\n".join(tail))
            seed = C.seed_for(f"{tid}#retry{attempt + 1}")
            row["verification"] = (row.get("verification") or "") + f"; OpenMC error, rerun with seed {seed}"
        row["seed"] = seed
        row["t_openmc_s"] = round(time.time() - t1, 1)
        if rc != 0 or not sp.exists():
            row["status"] = f"openmc_error_rc{rc}"
            tail = (wd / "openmc.log").read_text(errors="ignore").splitlines()[-15:]
            (C.RESULTS_DIR / "errors").mkdir(parents=True, exist_ok=True)
            (C.RESULTS_DIR / "errors" / f"{tid}.log").write_text("\n".join(tail))
            return row
        row["keff"], row["keff_std"] = C.read_keff(sp)
        row["status"] = "ok"
        shutil.rmtree(wd, ignore_errors=True)
    except Exception as e:  # keep the work folder for inspection
        row["status"] = f"error: {type(e).__name__}: {e}"[:200]
    return row


def cmd_reference(a):
    p = C.PRESETS[a.preset]
    wd = C.WORK_DIR / "reference_tallies"
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)
    import su_tasks
    edges = su_tasks.fine_bins()
    model = C.build_model(C.LIBRARY_XML, p["particles"], p["batches"], p["inactive"],
                          C.seed_for("reference_tallies"), tallies=True, n_flux_bins=1)
    # replace the energy filter by the fine bins aligned with the SCALE-44 groups
    import openmc
    t = model.tallies[0]
    t.filters[1] = openmc.EnergyFilter(edges)
    model.export_to_xml(wd)
    t0 = time.time()
    rc = run_openmc(wd, a.threads, wd / "openmc.log")
    if rc != 0:
        sys.exit(f"OpenMC failed, see {wd / 'openmc.log'}")
    import h5py
    with openmc.StatePoint(wd / f"statepoint.{p['batches']}.h5") as sp:
        tf = sp.get_tally(name="flux_fine")
        ta = sp.get_tally(name="absorption")
        flux = tf.mean.reshape(3, len(edges) - 1)
        flux_sd = tf.std_dev.reshape(3, len(edges) - 1)
        absorption = float(ta.mean.ravel()[0])
        nufission = float(ta.mean.ravel()[1])
        k = sp.keff
    C.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with h5py.File(C.RESULTS_DIR / "reference_tallies.h5", "w") as f:
        f["flux"] = flux
        f["flux_std"] = flux_sd
        f["energy_edges"] = edges
        f["absorption"] = absorption
        f["nu_fission"] = nufission
        f["keff"] = [k.nominal_value, k.std_dev]
        f.attrs["preset"] = a.preset
        f.attrs["cells"] = "fuel,clad,moderator"
    print(f"reference: k = {k.nominal_value:.5f} +/- {k.std_dev:.5f}  ({time.time() - t0:.0f} s)"
          f" -> {C.RESULTS_DIR / 'reference_tallies.h5'}")
    shutil.rmtree(wd, ignore_errors=True)


def cmd_run(a):
    tasks = list(csv.DictReader(open(C.HERE / "tasks.csv")))
    out = C.RESULTS_DIR / f"results_{a.preset}.csv"
    done = set()
    if out.exists():
        done = {r["task_id"] for r in csv.DictReader(open(out)) if r["status"] == "ok"}
    order = {"ref": 0, "zero": 1, "integral": 2, "linearity": 3, "group": 4}
    todo = [t for t in tasks if t["task_id"] not in done]
    if a.only:
        todo = [t for t in todo if re.search(a.only, t["task_id"])]
    todo.sort(key=lambda t: order[t["kind"]])
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(tasks)} tasks, {len(done)} done, {len(todo)} to run now "
          f"({a.jobs} jobs x {a.threads} threads, preset {a.preset})", flush=True)
    if not todo:
        return
    C.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    new = not out.exists()
    t0 = time.time()
    with open(out, "a", newline="") as f, mp.Pool(a.jobs) as pool:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, row in enumerate(pool.imap_unordered(do_task, [(t, a.preset, a.threads) for t in todo]), 1):
            w.writerow({k: row.get(k, "") for k in FIELDS})
            f.flush()
            el = time.time() - t0
            eta = el / i * (len(todo) - i)
            k = f"{row['keff']:.5f} +/- {row['keff_std']:.5f}" if row.get("status") == "ok" else row.get("status")
            print(f"[{i}/{len(todo)}] {row['task_id']}: {k}  ver={row.get('verification', '')}  "
                  f"lib {row.get('t_library_s', '')} s, openmc {row.get('t_openmc_s', '')} s  "
                  f"| elapsed {el / 3600:.2f} h, remaining ~{eta / 3600:.2f} h", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reference")
    r.add_argument("--preset", default="pilot", choices=list(C.PRESETS))
    r.add_argument("--threads", type=int, default=os.cpu_count())
    r.set_defaults(func=cmd_reference)
    s = sub.add_parser("run")
    s.add_argument("--preset", default="pilot", choices=list(C.PRESETS))
    s.add_argument("--jobs", type=int, default=1)
    s.add_argument("--threads", type=int, default=os.cpu_count())
    s.add_argument("--limit", type=int, default=0)
    s.add_argument("--only", default="")
    s.set_defaults(func=cmd_run)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()

"""
Dynamic load balancing of independent NJOY jobs.

Jobs are sorted by decreasing estimated cost ("longest processing time first")
and distributed through a shared queue: each worker takes the next job as soon
as it finishes the previous one. The most expensive evaluations therefore start
first, and the small ones fill the remaining gaps at the end of the run, which
minimises the total wall-clock time for a given number of CPUs.

The cost of a job is estimated from the wall-clock times measured in previous
runs (stored in data/processing_times.json); for a job that has never been run,
it is estimated from the size of the ENDF file(s) and the number of temperatures.
"""
import json
import os
import time
import traceback
from multiprocessing import Process, Queue
from pathlib import Path

HISTORY_FILE = Path(__file__).resolve().parent / "data" / "processing_times.json"


# ----------------------------------------------------------------------------
# cost estimates
# ----------------------------------------------------------------------------
def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_history(new_times):
    """Merge newly measured times {key: seconds} into the history file."""
    if not new_times:
        return
    hist = load_history()
    hist.update(new_times)
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = HISTORY_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(hist, f, indent=1, sort_keys=True)
        os.replace(tmp, HISTORY_FILE)
    except Exception:
        pass


def file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def endf_cost(path, ntemps=1):
    """Rough NJOY processing time (s) of an incident-neutron ENDF file.

    Uses the MF1/MT451 directory (number of records per section) and the
    presence of unresolved-resonance parameters (LRU=2). The resonance
    reconstruction (MF2) and the unresolved-resonance treatment dominate the
    cost of heavy nuclides, the total file size that of light ones. The
    coefficients were fitted to NJOY2016 timings and only need to give the
    right ordering of the jobs.
    """
    n_total = n_mf2 = 0
    urr = False
    try:
        with open(path, "r", errors="ignore") as f:
            line = f.readline()
            while line and line[70:75].replace(" ", "") != "1451":   # skip the tape identification (TPID)
                line = f.readline()
            head = [line] + [f.readline() for _ in range(3)]       # HEAD and three CONT records
            nwd = int(head[3][44:55]); nxc = int(head[3][55:66])
            for _ in range(nwd):
                f.readline()
            for _ in range(nxc):
                line = f.readline()
                mf = int(line[22:33]); nc = int(line[44:55])
                n_total += nc
                if mf == 2:
                    n_mf2 += nc
            for line in f:                     # scan up to the end of MF2 for LRU=2
                mf = line[70:72].strip()
                if mf == "2" and line[72:75].strip() == "151" and line[22:33].strip() == "2" and "." in line[0:11]:
                    urr = True
                    break
                if mf.isdigit() and int(mf) > 2:
                    break
    except Exception:
        return file_size(path) / 2.0e5 * max(1, ntemps)
    cost = 2.0 + 1.0e-5 * n_total + 0.04 * n_mf2 + (0.08 * n_mf2 if urr else 0.0)
    return cost * max(1, ntemps)


def estimate(key, fallback, history):
    """Measured time (s) from a previous run if available, otherwise the fallback estimate (s)."""
    if key in history:
        return float(history[key])
    return float(fallback)


# ----------------------------------------------------------------------------
# dynamic scheduler
# ----------------------------------------------------------------------------
def _worker_loop(task_q, result_q, func):
    while True:
        item = task_q.get()
        if item is None:
            break
        idx, key, job = item
        t0 = time.time()
        try:
            func(job)
        except Exception:
            traceback.print_exc()
        result_q.put((key, time.time() - t0))


def run_dynamic(jobs, func, n_workers, cost_and_key, logger=None):
    """Run func(job) for every job on n_workers processes, longest jobs first.

    cost_and_key(job) -> (estimated_cost, history_key)
    Returns the measured wall-clock time of each job {history_key: seconds}.
    """
    history = load_history()
    scored = []
    for i, job in enumerate(jobs):
        try:
            cost, key = cost_and_key(job, history)
        except Exception:
            cost, key = 0.0, f"job{i}"
        scored.append((cost, i, key, job))
    scored.sort(key=lambda t: (-t[0], t[1]))

    n_workers = max(1, min(int(n_workers), len(scored)))
    if logger:
        known = sum(1 for _, _, k, _ in scored if k in history)
        logger(f"Scheduling {len(scored)} jobs on {n_workers} workers, longest first "
               f"({known} with measured times from previous runs).")

    task_q, result_q = Queue(), Queue()
    for cost, i, key, job in scored:
        task_q.put((i, key, job))
    for _ in range(n_workers):
        task_q.put(None)

    procs = [Process(target=_worker_loop, args=(task_q, result_q, func)) for _ in range(n_workers)]
    for p in procs:
        p.start()

    measured = {}
    for _ in range(len(scored)):
        key, dt = result_q.get()
        measured[key] = round(dt, 2)
    for p in procs:
        p.join()

    save_history(measured)
    return measured

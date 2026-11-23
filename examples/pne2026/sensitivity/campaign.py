"""
Complete S/U campaign in one command (see run_campaign.sh).

  1. checks: OpenMC version (executable and Python API) against EXPECTED_OPENMC.txt,
     Python packages, library checksums, free disk space
  2. records the machine and software configuration (results/machine/)
  3. smoke test (one short OpenMC run) and throughput measurement
  4. reference run with flux tallies and list of tasks (first session only)
  5. all OpenMC calculations, restartable; progress, elapsed time and remaining
     time printed after every calculation; wall time accumulated over sessions
  6. analysis and an archive of the results to send back

Environment variables (optional): PRESET (full), JOBS, THREADS, SU_SKIP_CHECKSUM=1,
newer OpenMC versions are accepted with a warning.
"""
import csv
import datetime as dt
import hashlib
import json
import multiprocessing as mp
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import su_common as C

HERE = C.HERE
RES = C.RESULTS_DIR
MACHINE = RES / "machine"
SESSIONS = RES / "campaign_sessions.json"
LOG = RES / "campaign.log"


# ----------------------------------------------------------------------------
# output helpers
# ----------------------------------------------------------------------------
def log(msg=""):
    line = msg
    print(line, flush=True)
    RES.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def hms(s):
    s = int(max(s, 0))
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return (f"{d}d " if d else "") + f"{h:02d}h{m:02d}m{s:02d}s"


def run(cmd):
    try:
        return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True,
                              timeout=120).stdout.strip()
    except Exception as e:
        return f"(unavailable: {e})"


def die(msg):
    log("")
    log("STOP: " + msg)
    sys.exit(1)


# ----------------------------------------------------------------------------
# 1. checks
# ----------------------------------------------------------------------------
def openmc_info():
    exe = shutil.which("openmc")
    if exe is None:
        die("the 'openmc' executable is not in PATH (activate the conda environment, "
            "see README.md)")
    out = run([exe, "--version"])
    ver = re.search(r"OpenMC version\s+(\S+)", out)
    sha = re.search(r"Git SHA1:\s+(\S+)", out)
    try:
        import openmc
        pyver, pyfile = openmc.__version__, openmc.__file__
    except ImportError:
        die("the OpenMC Python API cannot be imported (activate the conda environment)")
    return dict(executable=exe, version=ver.group(1) if ver else "?", git_sha=sha.group(1) if sha else "?",
                python_api_version=pyver, python_api_file=pyfile, build_info=out)


def check_openmc(info):
    exp_file = HERE / "EXPECTED_OPENMC.txt"
    expected = {}
    if exp_file.exists():
        for line in exp_file.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                expected[k.strip()] = v.strip()
    want = expected.get("version", "0.15.0")
    log(f"  OpenMC executable : {info['version']}  (git {info['git_sha'][:12]})  {info['executable']}")
    log(f"  OpenMC Python API : {info['python_api_version']}")
    log(f"  required          : {want}" + (f"  (git {expected['git_sha'][:12]} on the machine that "
                                         "prepared the data)" if "git_sha" in expected else ""))
    def vt(v):
        m = re.match(r"(\d+)\.(\d+)\.(\d+)", v)
        return tuple(int(x) for x in m.groups()) if m else None
    ve, vp, vw = vt(info["version"]), vt(info["python_api_version"]), vt(want)
    if ve is None or vp is None:
        die("cannot read the OpenMC version")
    if ve != vp:
        die(f"the OpenMC executable ({info['version']}) and Python API ({info['python_api_version']}) "
            "have different versions; use one consistent installation (environment.yml)")
    if ve < vw:
        die(f"OpenMC {info['version']} is older than {want}; install {want} with environment.yml (README.md)")
    if ve > vw:
        log("")
        log("  " + "!" * 74)
        log(f"  WARNING: OpenMC {info['version']} is newer than {want}, the version used for the data and")
        log("  for all other results of the article. The campaign runs anyway. Every perturbed")
        log("  file is still verified and the zero-perturbation tests check that the data")
        log("  are read correctly; the version is recorded in results/machine/ and must be")
        log("  reported with the results.")
        log("  " + "!" * 74)
        log("")
    elif "git_sha" in expected and expected["git_sha"] != info["git_sha"]:
        log(f"  note: same version, different build (git {info['git_sha'][:12]}); recorded in results/machine/")
    log("  OpenMC version: OK" if ve == vw else f"  OpenMC version: {info['version']} accepted (newer)")


def check_python():
    missing = []
    for mod in ("numpy", "h5py", "pandas", "matplotlib"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        die("missing Python packages: " + ", ".join(missing))
    log("  Python packages: OK" + ("" if _has("openpyxl") else "  (openpyxl absent: no .xlsx, CSV only)"))


def _has(mod):
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def check_library():
    lib = C.LIBRARY_XML.parent
    if not C.LIBRARY_XML.exists():
        die(f"{C.LIBRARY_XML} not found")
    if not (C.COVARIANCE_DIR / "csv").exists():
        die(f"{C.COVARIANCE_DIR / 'csv'} not found")
    sums = lib / "SHA256SUMS"
    if sums.exists() and os.environ.get("SU_SKIP_CHECKSUM") != "1":
        bad = []
        for line in sums.read_text().splitlines():
            h, name = line.split()
            with open(lib / name, "rb") as f:
                if hashlib.sha256(f.read()).hexdigest() != h:
                    bad.append(name)
        if bad:
            die("library files differ from SHA256SUMS: " + ", ".join(bad))
        log(f"  nuclear data library: {len(sums.read_text().splitlines())} files, checksums OK")
    free = shutil.disk_usage(HERE).free / 1e9
    if free < 5:
        die(f"only {free:.1f} GB free on the disk of {HERE} (5 GB needed)")
    log(f"  free disk space: {free:.0f} GB")


# ----------------------------------------------------------------------------
# 2. machine information
# ----------------------------------------------------------------------------
def physical_cores():
    out = run("lscpu -p=core,socket")
    pairs = {l for l in out.splitlines() if l and not l.startswith("#")}
    return len(pairs) or os.cpu_count()


def machine_info(oinfo):
    import numpy
    import h5py
    info = dict(
        date=dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        hostname=socket.gethostname(),
        os=run("grep PRETTY_NAME /etc/os-release | cut -d= -f2").strip('"'),
        kernel=platform.release(),
        wsl="microsoft" in run("cat /proc/version").lower(),
        cpu_model=run("lscpu | grep 'Model name' | head -1 | cut -d: -f2").strip(),
        logical_cpus=os.cpu_count(),
        physical_cores=physical_cores(),
        sockets=run("lscpu | grep '^Socket(s)' | cut -d: -f2").strip(),
        threads_per_core=run("lscpu | grep 'Thread(s) per core' | cut -d: -f2").strip(),
        cpu_max_mhz=run("lscpu | grep 'CPU max MHz' | cut -d: -f2").strip(),
        numa_nodes=run("lscpu | grep 'NUMA node(s)' | cut -d: -f2").strip(),
        memory_total_gb=round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9, 1),
        python=sys.version.split()[0],
        numpy=numpy.__version__,
        h5py=h5py.__version__,
        hdf5=h5py.version.hdf5_version,
        openmc=oinfo,
        conda_env=os.environ.get("CONDA_DEFAULT_ENV", ""),
        omp_env={k: v for k, v in os.environ.items() if k.startswith("OMP_")},
        gennjoy_commit=(HERE.parents[2] / "GENNJOY_COMMIT.txt").read_text().strip()
        if (HERE.parents[2] / "GENNJOY_COMMIT.txt").exists() else run(["git", "-C", str(HERE), "rev-parse", "--short", "HEAD"]),
    )
    return info


def save_machine_info(info, session_id):
    MACHINE.mkdir(parents=True, exist_ok=True)
    with open(MACHINE / f"machine_{session_id}.json", "w") as f:
        json.dump(info, f, indent=1)
    raw = MACHINE / f"system_{session_id}.txt"
    with open(raw, "w") as f:
        for title, cmd in [("lscpu", "lscpu"), ("free -h", "free -h"), ("uname -a", "uname -a"),
                           ("os-release", "cat /etc/os-release"), ("df -h .", f"df -h {HERE}"),
                           ("openmc --version", "openmc --version"), ("ulimit -a", "bash -c 'ulimit -a'"),
                           ("conda list", "conda list 2>/dev/null")]:
            f.write(f"===== {title} =====\n{run(cmd)}\n\n")


# ----------------------------------------------------------------------------
# sessions (total wall time over interruptions)
# ----------------------------------------------------------------------------
def load_sessions():
    if SESSIONS.exists():
        return json.loads(SESSIONS.read_text())
    return []


def save_sessions(s):
    RES.mkdir(parents=True, exist_ok=True)
    SESSIONS.write_text(json.dumps(s, indent=1))


# ----------------------------------------------------------------------------
# tasks
# ----------------------------------------------------------------------------
def results_file(preset):
    return RES / f"results_{preset}.csv"


def done_tasks(preset):
    f = results_file(preset)
    if not f.exists():
        return set(), []
    rows = [r for r in csv.DictReader(open(f))]
    return {r["task_id"] for r in rows if r["status"] == "ok"}, rows


def smoke_test(threads):
    """Short unperturbed run: checks the chain and measures the throughput."""
    import su_run
    wd = C.WORK_DIR / "smoke"
    shutil.rmtree(wd, ignore_errors=True)
    wd.mkdir(parents=True)
    p = dict(particles=5000, batches=30, inactive=10)
    model = C.build_model(C.LIBRARY_XML, p["particles"], p["batches"], p["inactive"], 12345)
    model.export_to_xml(wd)
    t0 = time.time()
    rc = su_run.run_openmc(wd, threads, wd / "openmc.log")
    dtm = time.time() - t0
    sp = wd / f"statepoint.{p['batches']}.h5"
    if rc != 0 or not sp.exists():
        die(f"the smoke test failed (OpenMC return code {rc}); see {wd / 'openmc.log'}")
    k, s = C.read_keff(sp)
    rate = p["particles"] * p["batches"] / (dtm * threads)
    shutil.rmtree(wd, ignore_errors=True)
    # a test perturbation (written, verified, not run)
    from gennjoy import perturbation as P
    rep = P.write_perturbed_library(C.LIBRARY_XML, wd / "lib", "U238", 102, 6.0, 10.0, 0.1)
    ok = rep["verification"]["ok"]
    shutil.rmtree(wd, ignore_errors=True)
    if not ok:
        die("the verification of a test perturbation failed")
    return k, s, rate, dtm


def _worker_init():
    # Ctrl-C and kill are handled by the main process, which stops the workers
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)


# ----------------------------------------------------------------------------
# main loop
# ----------------------------------------------------------------------------
def main():
    preset = os.environ.get("PRESET", "full")
    if preset not in C.PRESETS:
        die(f"unknown PRESET {preset}")
    session_id = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    t_start = time.time()
    log("=" * 78)
    log(f" GenNJOY S/U campaign — Mosteller pin cell — session {session_id} — preset '{preset}' "
        f"({C.PRESETS[preset]['particles']} particles x {C.PRESETS[preset]['batches']} batches)")
    log("=" * 78)

    log("[1/6] Checks")
    oinfo = openmc_info()
    check_openmc(oinfo)
    check_python()
    check_library()

    log("[2/6] Machine and software configuration")
    info = machine_info(oinfo)
    save_machine_info(info, session_id)
    pc = info["physical_cores"]
    jobs = int(os.environ.get("JOBS", 0)) or max(1, round(pc / 10))
    threads = int(os.environ.get("THREADS", 0)) or max(1, pc // jobs)
    log(f"  {info['cpu_model']} | {pc} physical cores ({info['logical_cpus']} logical) | "
        f"{info['memory_total_gb']} GB RAM | {info['os']}")
    log(f"  parallelism: {jobs} OpenMC calculations at a time x {threads} threads "
        f"(change with JOBS=.. THREADS=..)")
    log(f"  saved in {MACHINE.relative_to(HERE)}/")

    log("[3/6] Smoke test")
    k, s, rate, dtm = smoke_test(jobs * threads)
    log(f"  k = {k:.4f} +/- {s:.4f} in {dtm:.0f} s; {rate:,.0f} histories per second per thread; "
        "test perturbation verified")

    sessions = load_sessions()
    sessions.append(dict(id=session_id, host=info["hostname"], start=info["date"], end=None,
                         wall_s=0.0, jobs=jobs, threads=threads, preset=preset,
                         tasks_done=0, status="running", smoke_rate=rate))
    save_sessions(sessions)

    def close_session(status, n_done):
        sessions[-1].update(end=dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                            wall_s=round(time.time() - t_start, 1), tasks_done=n_done, status=status)
        save_sessions(sessions)

    log("[4/6] Reference run and list of tasks")
    import su_run
    import su_tasks
    ref = RES / "reference_tallies.h5"
    need_ref = True
    if ref.exists():
        import h5py
        with h5py.File(ref, "r") as f:
            need_ref = f.attrs.get("preset") != preset
    if need_ref:
        class A:
            pass
        a = A()
        a.preset, a.threads = preset, jobs * threads
        t0 = time.time()
        su_run.cmd_reference(a)
        log(f"  reference run done in {hms(time.time() - t0)}")
        su_tasks.main()
    elif not (HERE / "tasks.csv").exists():
        su_tasks.main()
    else:
        log("  already done (previous session)")
    tasks = list(csv.DictReader(open(HERE / "tasks.csv")))

    log("[5/6] OpenMC calculations")
    done, rows = done_tasks(preset)
    order = {"ref": 0, "zero": 1, "integral": 2, "linearity": 3, "group": 4}
    todo = sorted([t for t in tasks if t["task_id"] not in done], key=lambda t: order[t["kind"]])
    if int(os.environ.get("LIMIT", 0)):
        todo = todo[:int(os.environ["LIMIT"])]
        tasks = [t for t in tasks if t["task_id"] in done or t in todo]
    ntot = len(tasks)
    p = C.PRESETS[preset]
    per_task_est = p["particles"] * p["batches"] / (rate * threads) + 6.0
    prev_wall = sum(x["wall_s"] for x in sessions[:-1])
    log(f"  {ntot} calculations: {len(done)} done in previous sessions, {len(todo)} to run")
    log(f"  first estimate: {hms(per_task_est)} per calculation -> about "
        f"{hms(per_task_est * len(todo) / jobs)} for the remaining ones")
    log(f"  wall time of previous sessions: {hms(prev_wall)}")
    log("  (stop with Ctrl-C at any time; run the same command again to continue)")

    if todo:
        out = results_file(preset)
        new = not out.exists()
        t_loop = time.time()
        n = 0
        interrupted = False

        pool = mp.Pool(jobs, initializer=_worker_init)

        def handler(signum, frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, handler)
        try:
            with open(out, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=su_run.FIELDS)
                if new:
                    w.writeheader()
                for row in pool.imap_unordered(su_run.do_task, [(t, preset, threads) for t in todo]):
                    w.writerow({k: row.get(k, "") for k in su_run.FIELDS})
                    f.flush()
                    n += 1
                    ndone = len(done) + n
                    el = time.time() - t_loop
                    # remaining time: measured rate of this session (after 2 tasks per job),
                    # otherwise the smoke-test estimate
                    if n >= 2 * jobs:
                        remaining = el / n * (len(todo) - n)
                    else:
                        remaining = per_task_est * (len(todo) - n) / jobs
                    eta = dt.datetime.now() + dt.timedelta(seconds=remaining)
                    status = (f"k={float(row['keff']):.5f}+/-{float(row['keff_std']):.5f}"
                              if row.get("status") == "ok" else f"!! {row.get('status')}")
                    ver = row.get("verification", "")
                    if ver and ver != "ok":
                        status += f" !! verification {ver}"
                    bar = "#" * int(30 * ndone / ntot)
                    log(f"[{bar:<30}] {ndone}/{ntot} {100 * ndone / ntot:5.1f}% | {row['task_id']:<24} {status}"
                        f" | session {hms(time.time() - t_start)} | total {hms(prev_wall + time.time() - t_start)}"
                        f" | remaining ~{hms(remaining)} (end ~{eta:%a %d %b %H:%M})")
                    if n % 10 == 0:
                        close_session("running", n)
        except KeyboardInterrupt:
            interrupted = True
            pool.terminate()
            pool.join()
            log("")
            log(f"  interrupted: {n} calculations finished in this session.")
            log("  >>> STOPPED. To continue, run:  bash START_HERE.sh   (nothing is lost)")
            log("  >>> توقف الحساب. للمتابعة شغّل الأمر نفسه:  bash START_HERE.sh")
        else:
            pool.close()
            pool.join()
            shutil.rmtree(C.WORK_DIR, ignore_errors=True)
        if interrupted:
            close_session("interrupted", n)
            log(f"  total wall time so far: {hms(prev_wall + time.time() - t_start)}")
            sys.exit(130)
    else:
        n = 0

    done, rows = done_tasks(preset)
    failed = [t["task_id"] for t in tasks if t["task_id"] not in done]
    if failed:
        log(f"  {len(failed)} calculations did not finish correctly ({', '.join(failed[:5])}...). "
            "Run the same command again to retry them; see results/errors/.")

    log("[6/6] Archive of the results")
    # Only the raw results are sent back (k of every calculation, verification
    # reports, reference flux, machine description, logs); the analysis, tables and
    # figures are made afterwards on the machine of the authors (su_analyze.py).
    close_session("completed" if not failed else "completed_with_failures", n)
    total = sum(x["wall_s"] for x in sessions)
    core_h = sum(float(r["t_openmc_s"] or 0) * int(r["threads"] or 0) for r in rows if r["status"] == "ok") / 3600
    summary = dict(preset=preset, calculations=len(tasks), finished=len(done), failed=len(failed),
                   sessions=len(sessions), total_wall_time_s=round(total), total_wall_time=hms(total),
                   openmc_core_hours=round(core_h, 1), machine=info["cpu_model"],
                   physical_cores=pc, jobs=jobs, threads=threads)
    (RES / "campaign_summary.json").write_text(json.dumps(summary, indent=1))
    archive = HERE / f"SU_results_{info['hostname']}_{session_id}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(RES, arcname="results",
                filter=lambda ti: None if ("/work" in ti.name or "/analysis_" in ti.name) else ti)
        for extra in (HERE / "tasks.csv",):
            if extra.exists():
                tar.add(extra, arcname=extra.name)
    # final message for the person who ran the campaign (also in FINISHED.txt)
    size = archive.stat().st_size / 1e6
    # zero-perturbation tests: k must be identical to ref_00 (same seed)
    zero_ok = None
    try:
        kz = {r["task_id"]: float(r["keff"]) for r in rows if r["status"] == "ok"}
        zt = [t["task_id"] for t in tasks if t["kind"] == "zero" and t["task_id"] in kz]
        if "ref_00" in kz and zt:
            zero_ok = all(abs(kz[t] - kz["ref_00"]) < 1e-9 for t in zt)
    except Exception:
        pass
    newer = oinfo["version"] != "0.15.0"
    L = ["",
         "=" * 78,
         "   CAMPAIGN FINISHED                                     انتهت الحسابات",
         "=" * 78,
         f"   Calculations finished : {len(done)} / {len(tasks)}" + (f"   ({len(failed)} failed)" if failed else ""),
         f"   Total time            : {hms(total)}  ({len(sessions)} session(s), {core_h:,.0f} core-hours)",
         f"   Machine               : {info['cpu_model']}, {pc} cores",
         f"   OpenMC                : {oinfo['version']}" + ("   (newer than 0.15.0: recorded with the results)" if newer else ""),
         ""]
    if failed:
        L += ["   Some calculations did not finish correctly. Please run again:",
              "        bash START_HERE.sh",
              "   (only the missing calculations are run), then send the file below.",
              "   بعض الحسابات لم تكتمل: أعد تشغيل الأمر نفسه ثم أرسل الملف",
              ""]
    if zero_ok is False:
        L += ["   WARNING: the zero-perturbation test failed with this OpenMC version.",
              "   Send the file anyway and mention this message.", ""]
    L += ["   >>> PLEASE SEND THIS FILE TO Dr. Mohamed Laid YAHIAOUI <<<",
          "   >>>         أرسل هذا الملف إلى د. محمد العيد يحياوي          <<<",
          "",
          f"       {archive}",
          f"       ({size:.2f} MB: results, machine description, logs)",
          "",
          "   Nothing else is needed. The folder can be deleted afterwards.",
          "   لا حاجة لأي شيء آخر، ويمكن حذف المجلد بعد إرسال الملف.",
          "=" * 78, ""]
    if preset != "full":
        L = ["", "=" * 78,
             "   TEST FINISHED: the installation works.        انتهى الاختبار: التثبيت سليم",
             "", "   Now start the real campaign with:      bash START_HERE.sh",
             "   الآن ابدأ الحسابات الحقيقية بالأمر:      bash START_HERE.sh",
             "   (the test results are not needed and are not sent)", "=" * 78, ""]
        archive.unlink(missing_ok=True)
    for line in L:
        log(line)
    if preset == "full":
        (HERE / "FINISHED.txt").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()

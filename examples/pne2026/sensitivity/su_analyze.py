"""
Sensitivities, their Monte Carlo uncertainties, and the nuclear-data uncertainty of k.

    python su_analyze.py --preset full

Inputs : tasks.csv, results/results_<preset>.csv, results/screening.csv,
         results/reference_tallies.h5, covariance_600K/csv/*.csv
Outputs: results/analysis_<preset>/  (CSV tables, su_summary.xlsx, figures PNG + TIFF)

Definitions
  k0                 mean of the N_REFERENCE unperturbed runs (independent seeds)
  S                  (k+ - k-) / (2 eps k0), central difference, k+- with sigma -> sigma(1 +- eps)
  sigma_S            sqrt(s+^2 + s-^2) / (2 eps k0)   (independent seeds)
  curvature          (k+ + k- - 2 k0) / (2 eps^2 k0)  (second-order term, linearity check)
  var(k)/k^2         sum over blocks of S_a^T C_ab S_b (relative covariances C, sandwich rule)
  bias               E[S^T C S] = s^T C s + tr(C Sigma_S): the noise term tr(C Sigma_S) is
                     subtracted for the diagonal blocks (Sigma_S diagonal, independent runs)
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

import su_common as C


# ----------------------------------------------------------------------------
# data loading
# ----------------------------------------------------------------------------
def load(preset):
    tasks = {r["task_id"]: r for r in csv.DictReader(open(C.HERE / "tasks.csv"))}
    res = {}
    f = C.RESULTS_DIR / f"results_{preset}.csv"
    for r in csv.DictReader(open(f)):
        if r["status"] == "ok":
            res[r["task_id"]] = (float(r["keff"]), float(r["keff_std"]), r)
    scr = list(csv.DictReader(open(C.RESULTS_DIR / "screening.csv")))
    return tasks, res, scr


def reference(tasks, res):
    ks = np.array([res[t][0] for t in tasks if tasks[t]["kind"] == "ref" and t in res])
    ss = np.array([res[t][1] for t in tasks if tasks[t]["kind"] == "ref" and t in res])
    if len(ks) == 0:
        raise SystemExit("no reference run finished")
    w = 1 / ss**2
    k0 = float(np.sum(w * ks) / np.sum(w))
    out = dict(n=len(ks), k0=k0, k0_std=float(1 / np.sqrt(np.sum(w))),
               mean_reported_std=float(ss.mean()),
               sample_std=float(ks.std(ddof=1)) if len(ks) > 1 else float("nan"))
    out["ratio_sample_to_reported"] = out["sample_std"] / out["mean_reported_std"]
    return out


def pairs(tasks, res, k0):
    """Central differences for every (nuclide, mt, group, |eps|) with both signs."""
    by = {}
    for tid, t in tasks.items():
        if t["kind"] in ("ref", "zero") or tid not in res:
            continue
        e = float(t["eps"])
        key = (t["nuclide"], int(t["mt"]), t["group"], abs(e))
        by.setdefault(key, {})["p" if e > 0 else "m"] = (res[tid][0], res[tid][1], t["kind"])
    out = {}
    for key, d in by.items():
        if "p" not in d or "m" not in d:
            continue
        (kp, sp, kind), (km, sm, _) = d["p"], d["m"]
        e = key[3]
        S = (kp - km) / (2 * e * k0)
        sS = np.sqrt(sp**2 + sm**2) / (2 * e * k0)
        curv = (kp + km - 2 * k0) / (2 * e**2 * k0)
        out[key] = dict(S=S, sS=sS, kplus=kp, kminus=km, curvature=curv, kind=kind)
    return out


# ----------------------------------------------------------------------------
# covariance data
# ----------------------------------------------------------------------------
def read_cov(nuc, pmt_a, pmt_b, ng):
    """Relative covariance block between pseudo-MTs a and b of nuclide nuc (None if absent)."""
    d = C.COVARIANCE_DIR / "csv"
    (mfa, mta), (mfb, mtb) = C.COVARIANCE_ID[pmt_a], C.COVARIANCE_ID[pmt_b]
    if mfa != mfb:
        return None
    for (x, y, tr) in ((mta, mtb, False), (mtb, mta, True)):
        f = d / f"{nuc}_MF{mfa}_MT{x}_MT{y}.csv"
        if f.exists():
            m = np.loadtxt(f, delimiter=",", ndmin=2)
            if m.shape != (ng, ng):
                raise ValueError(f"{f}: shape {m.shape}, expected {(ng, ng)}")
            return m.T if tr else m
    return None


def clean_block(m, da, db):
    """Limit the correlations of a relative covariance block to |rho| <= 1.

    ERRORR can return isolated elements with |rho| > 1 (e.g. where the cross
    section or the spectrum is almost zero). Returns (cleaned block, list of
    (i, j, rho, value)) of the modified elements (1-based groups).
    """
    da, db = np.clip(da, 0, None), np.clip(db, 0, None)
    lim = np.sqrt(np.outer(da, db))
    bad = np.abs(m) > lim * (1 + 1e-6)
    out = np.where(bad, np.sign(m) * lim, m)
    lst = []
    for i, j in zip(*np.nonzero(bad)):
        rho = m[i, j] / lim[i, j] if lim[i, j] > 0 else np.inf
        lst.append((int(i) + 1, int(j) + 1, float(rho), float(m[i, j])))
    return out, lst


def check_cov_groups(ng):
    bfiles = sorted((C.COVARIANCE_DIR / "csv").glob("*_group_bounds_eV.csv"))
    g = C.group_bounds()
    for b in bfiles:
        v = np.loadtxt(b, delimiter=",")
        if len(v) != ng + 1 or not np.allclose(np.sort(v), g, rtol=1e-4):
            raise SystemExit(f"{b}: group boundaries differ from {C.GROUPS_FILE}")
    return len(bfiles)


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="pilot")
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args()
    out = C.RESULTS_DIR / f"analysis_{a.preset}"
    out.mkdir(parents=True, exist_ok=True)

    tasks, res, scr = load(a.preset)
    ref = reference(tasks, res)
    k0 = ref["k0"]
    P = pairs(tasks, res, k0)
    bounds = C.group_bounds()
    ng = len(bounds) - 1
    status = {(r["nuclide"], int(r["mt"]), int(r["group"])): r["status"] for r in scr}

    # ---------------- group-wise sensitivity vectors ----------------
    sens = {}      # (nuc, mt) -> (S[ng], sS[ng], status[ng])
    rows = []
    missing = 0
    for nuc, mts in C.REACTIONS.items():
        for mt in mts:
            S, sS, st = np.zeros(ng), np.zeros(ng), []
            for g in range(1, ng + 1):
                s = status.get((nuc, mt, g), "zero")
                key = (nuc, mt, str(g), C.EPS_GROUP)
                if s == "computed":
                    if key in P:
                        S[g - 1], sS[g - 1] = P[key]["S"], P[key]["sS"]
                    else:
                        s = "missing"
                        missing += 1
                st.append(s)
                rows.append([nuc, mt, C.LABELS[mt], g, f"{bounds[g - 1]:.5e}", f"{bounds[g]:.5e}",
                             f"{S[g - 1]:.6e}", f"{sS[g - 1]:.3e}", s])
            sens[(nuc, mt)] = (S, sS, st)
    write_csv(out / "sensitivity_groupwise.csv",
              ["nuclide", "mt", "reaction", "group", "e_low_eV", "e_high_eV", "S", "sigma_S", "status"], rows)

    # ---------------- integral sensitivities and sum check ----------------
    irows = []
    integral = {}
    for nuc, mts in C.REACTIONS.items():
        for mt in mts:
            S, sS, st = sens[(nuc, mt)]
            key = (nuc, mt, "all", C.EPS_INTEGRAL)
            si = P.get(key)
            integral[(nuc, mt)] = si
            ssum, ssum_s = S.sum(), np.sqrt((sS**2).sum())
            if si:
                z = (si["S"] - ssum) / np.hypot(si["sS"], ssum_s)
                irows.append([nuc, mt, C.LABELS[mt], f"{si['S']:.5f}", f"{si['sS']:.5f}",
                              f"{ssum:.5f}", f"{ssum_s:.5f}", f"{z:.2f}", st.count("computed")])
            else:
                irows.append([nuc, mt, C.LABELS[mt], "", "", f"{ssum:.5f}", f"{ssum_s:.5f}", "", ""])
    write_csv(out / "sensitivity_integral.csv",
              ["nuclide", "mt", "reaction", "S_whole_range", "sigma", "sum_of_groups", "sigma_sum",
               "z_difference", "groups_computed"], irows)

    # ---------------- linearity ----------------
    lrows = []
    for (nuc, mt, g, e), d in sorted(P.items()):
        if d["kind"] != "linearity" and not (g == "all" and e == C.EPS_INTEGRAL) and not (
                g != "all" and e == C.EPS_GROUP and any(c[0] == nuc and c[1] == mt and c[2] not in (None,) for c in C.LINEARITY_CASES)):
            continue
        lrows.append([nuc, mt, C.LABELS[mt], g, e, f"{d['S']:.5f}", f"{d['sS']:.5f}",
                      f"{d['curvature']:.4f}", f"{d['kplus']:.6f}", f"{d['kminus']:.6f}"])
    write_csv(out / "linearity.csv",
              ["nuclide", "mt", "reaction", "group", "eps", "S", "sigma_S", "curvature", "k_plus", "k_minus"], lrows)

    # ---------------- uncertainty (sandwich rule) ----------------
    have_cov = (C.COVARIANCE_DIR / "csv").exists()
    urows, crow, total_var, total_bias, total_var_raw = [], [], 0.0, 0.0, 0.0
    if have_cov:
        nb = check_cov_groups(ng)
        blocks = []
        clipped_rows = []
        total_var_raw = 0.0
        for nuc, mts in C.REACTIONS.items():
            mts = [m for m in mts if m in C.COVARIANCE_ID]
            selfcov = {m: read_cov(nuc, m, m, ng) for m in mts}
            # PSD check of the joint matrix of this nuclide, on the computed groups
            comp = {m: np.array([s == "computed" for s in sens[(nuc, m)][2]]) for m in mts}
            for i, ma in enumerate(mts):
                for mb in mts[i:]:
                    raw = read_cov(nuc, ma, mb, ng)
                    if raw is None:
                        if ma == mb:
                            crow.append([nuc, ma, C.LABELS[ma], "no covariance data", "", "", ""])
                        continue
                    cab, clip = clean_block(raw, np.diag(selfcov[ma]), np.diag(selfcov[mb]))
                    for (gi, gj, rho, val) in clip:
                        clipped_rows.append([nuc, ma, mb, gi, gj, f"{rho:.4g}", f"{val:.4e}",
                                             "yes" if comp[ma][gi - 1] and comp[mb][gj - 1] else "no"])
                    Sa, sSa, _ = sens[(nuc, ma)]
                    Sb, sSb, _ = sens[(nuc, mb)]
                    fac = 1 if ma == mb else 2
                    v = float(Sa @ cab @ Sb) * fac
                    total_var_raw += float(Sa @ raw @ Sb) * fac
                    if ma == mb:
                        bias = float(np.sum(np.diag(cab) * sSa**2))
                        sv = 2 * np.sqrt(float((cab @ Sa) @ (sSa**2 * (cab @ Sa))))
                        cm = comp[ma]
                        sub = cab[np.ix_(cm, cm)] if cm.any() else np.zeros((1, 1))
                        ev = np.linalg.eigvalsh(0.5 * (sub + sub.T))
                        rsd = np.sqrt(np.clip(np.diag(sub), 0, None))
                        crow.append([nuc, ma, C.LABELS[ma], f"{rsd.max():.4f}", f"{ev.min():.3e}",
                                     f"{ev.max():.3e}", len(clip)])
                    else:
                        bias = 0.0
                        sv = 2 * np.sqrt(float((cab @ Sb) @ (sSa**2 * (cab @ Sb)) +
                                               (cab.T @ Sa) @ (sSb**2 * (cab.T @ Sa))))
                    vc = v - bias
                    total_var += v
                    total_bias += bias
                    blocks.append((nuc, ma, mb, v, bias, vc, sv))
        write_csv(out / "covariance_clipped_elements.csv",
                  ["nuclide", "mt_a", "mt_b", "group_a", "group_b", "rho_raw", "value_raw",
                   "both_groups_computed"], clipped_rows)
        for nuc, ma, mb, v, bias, vc, sv in blocks:
            name = C.LABELS[ma] if ma == mb else f"{C.LABELS[ma]} / {C.LABELS[mb]}"
            urows.append([nuc, ma, mb, name, f"{v:.4e}", f"{bias:.3e}", f"{vc:.4e}",
                          f"{np.sign(vc) * np.sqrt(abs(vc)) * 1e5:.1f}", f"{sv:.3e}"])
        totc = total_var - total_bias
        urows.append(["TOTAL", "", "", "", f"{total_var:.4e}", f"{total_bias:.3e}", f"{totc:.4e}",
                      f"{np.sqrt(max(totc, 0)) * 1e5:.1f}", ""])
        write_csv(out / "uncertainty_contributions.csv",
                  ["nuclide", "mt_a", "mt_b", "reaction(s)", "variance_rel", "noise_bias",
                   "variance_corrected", "contribution_pcm_signed", "sigma_variance_MC"], urows)
        write_csv(out / "covariance_checks.csv",
                  ["nuclide", "mt", "reaction", "max_rel_std_dev_computed_groups", "min_eigenvalue",
                   "max_eigenvalue", "elements_clipped_to_abs_rho_1"], crow)

    if have_cov:
        summary_raw = dict(total_uncertainty_pcm_without_clipping=float(np.sqrt(max(total_var_raw - total_bias, 0)) * 1e5))
    else:
        summary_raw = {}
    zero = {}
    if "ref_00" in res:
        for tid, t in tasks.items():
            if t["kind"] == "zero" and tid in res:
                zero[tid] = res[tid][0] - res["ref_00"][0]
    summary = dict(preset=a.preset, reference=ref, missing_group_tasks=missing, **summary_raw,
                   zero_perturbation_k_minus_ref00=zero,
                   zero_perturbation_ok=(all(abs(v) < 1e-9 for v in zero.values()) if zero else None),
                   total_relative_variance=total_var, noise_bias=total_bias,
                   total_uncertainty_pcm=float(np.sqrt(max(total_var - total_bias, 0)) * 1e5) if have_cov else None)
    # throughput and duration of a full campaign
    rates = []
    for tid, (_, _, row) in res.items():
        try:
            rates.append(int(row["particles"]) * int(row["batches"]) /
                         (float(row["t_openmc_s"]) * int(row["threads"])))
        except (KeyError, ValueError, ZeroDivisionError):
            pass
    if rates:
        rate = float(np.median(rates))
        full = C.PRESETS["full"]
        hist = full["particles"] * full["batches"] * len(tasks)
        summary["histories_per_second_per_thread"] = round(rate)
        summary["full_campaign_estimate_hours"] = {f"{n}_threads": round(hist / (rate * n) / 3600, 1)
                                                   for n in (12, 40, 80)}
    with open(out / "summary.json", "w") as f:
        json.dump(summary, f, indent=1)
    write_xlsx(out)
    print(json.dumps(summary, indent=1))
    if zero and not summary["zero_perturbation_ok"]:
        print("WARNING: a zero perturbation changed k: the perturbed files are not read exactly like the "
              "original ones by this OpenMC version (see zero_perturbation_k_minus_ref00)")
    if not a.no_figures:
        figures(out, sens, integral, P, bounds, urows if have_cov else [], ref)


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def write_xlsx(out):
    try:
        import pandas as pd
        with pd.ExcelWriter(out / "su_summary.xlsx") as xw:
            for name in ("sensitivity_integral", "uncertainty_contributions", "linearity",
                         "covariance_checks", "sensitivity_groupwise"):
                f = out / f"{name}.csv"
                if f.exists():
                    pd.read_csv(f).to_excel(xw, sheet_name=name[:31], index=False)
    except Exception as e:  # openpyxl missing etc.
        print(f"(xlsx not written: {e})")


# ----------------------------------------------------------------------------
# figures
# ----------------------------------------------------------------------------
def save(fig, path):
    fig.savefig(path.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(path.with_suffix(".tiff"), dpi=600, bbox_inches="tight", pil_kwargs={"compression": "tiff_lzw"})


def figures(out, sens, integral, P, bounds, urows, ref):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import h5py
    plt.rcParams.update({"font.family": "serif", "font.size": 10})
    du = np.log(bounds[1:] / bounds[:-1])
    pretty = {"U235": r"$^{235}$U", "U238": r"$^{238}$U", "O16": r"$^{16}$O", "H1": r"$^{1}$H"}

    # flux spectrum
    rf = C.RESULTS_DIR / "reference_tallies.h5"
    if rf.exists():
        with h5py.File(rf, "r") as f:
            flux, edges = f["flux"][()], f["energy_edges"][()]
        lu = np.log(edges[1:] / edges[:-1])
        fig, ax = plt.subplots(figsize=(6.5, 4))
        for i, (name, c) in enumerate([("fuel", "#c0392b"), ("moderator", "#2471a3")]):
            j = 0 if name == "fuel" else 2
            ax.step(edges[:-1], flux[j] / lu / (flux[j] / lu).max(), where="post", color=c, lw=1, label=name)
        ax.set_xscale("log")
        ax.set_xlabel("Energy (eV)")
        ax.set_ylabel("Flux per unit lethargy (normalised)")
        ax.legend(frameon=False)
        save(fig, out / "fig_flux_spectrum")
        plt.close(fig)

    # sensitivity profiles (2x2)
    cases = [("H1", 2), ("H1", 102), ("U235", 18), ("U238", 102)]
    fig, axs = plt.subplots(2, 2, figsize=(9, 6.5), sharex=True)
    for ax, (nuc, mt) in zip(axs.ravel(), cases):
        S, sS, _ = sens[(nuc, mt)]
        y, e = S / du, sS / du
        ax.step(bounds, np.r_[y, y[-1]], where="post", color="#1f4e79", lw=1)
        xc = np.sqrt(bounds[1:] * bounds[:-1])
        ax.errorbar(xc, y, yerr=e, fmt="none", ecolor="#7f7f7f", elinewidth=0.8, capsize=0)
        ax.axhline(0, color="k", lw=0.5)
        ax.set_xscale("log")
        ax.set_title(f"{pretty[nuc]} {C.LABELS[mt]}", fontsize=10)
        ax.set_ylabel("S per unit lethargy")
    for ax in axs[1]:
        ax.set_xlabel("Energy (eV)")
    fig.tight_layout()
    save(fig, out / "fig_sensitivity_profiles")
    plt.close(fig)

    # integral sensitivities
    keys = [k for k in integral if integral[k] is not None]
    if keys:
        fig, ax = plt.subplots(figsize=(8, 4))
        x = np.arange(len(keys))
        si = np.array([integral[k]["S"] for k in keys])
        se = np.array([integral[k]["sS"] for k in keys])
        ss = np.array([sens[k][0].sum() for k in keys])
        ax.bar(x, si, yerr=se, color="#5b9bd5", edgecolor="k", lw=0.5, capsize=2, label="whole energy range")
        ax.plot(x, ss, "o", ms=4, color="#c0392b", label="sum of group sensitivities")
        ax.axhline(0, color="k", lw=0.5)
        ax.set_xticks(x)
        ax.set_xticklabels([f"{pretty[n]} {C.LABELS[m]}" for n, m in keys], rotation=60, ha="right")
        ax.set_ylabel("Sensitivity coefficient (%/%)")
        ax.legend(frameon=False)
        save(fig, out / "fig_integral_sensitivities")
        plt.close(fig)

    # uncertainty contributions
    rows = [r for r in urows if r[0] != "TOTAL"]
    if rows:
        fig, ax = plt.subplots(figsize=(8, 4))
        lab = [f"{pretty[r[0]]} {r[3]}" for r in rows]
        val = np.array([float(r[7]) for r in rows])
        order = np.argsort(-np.abs(val))
        ax.bar(np.arange(len(val)), val[order], color=["#c0392b" if v < 0 else "#2e86c1" for v in val[order]],
               edgecolor="k", lw=0.5)
        ax.set_xticks(np.arange(len(val)))
        ax.set_xticklabels([lab[i] for i in order], rotation=70, ha="right", fontsize=8)
        ax.set_ylabel("Contribution to the uncertainty of k (pcm)")
        tot = [r for r in urows if r[0] == "TOTAL"][0][7]
        ax.set_title(f"Total: {tot} pcm (negative bars: negative covariance terms)", fontsize=9)
        save(fig, out / "fig_uncertainty_contributions")
        plt.close(fig)

    # linearity
    lin = {}
    for (nuc, mt, g, e), d in P.items():
        if any(c[0] == nuc and c[1] == mt for c in C.LINEARITY_CASES) and (d["kind"] == "linearity" or
                                                                         (g == "all" and e == C.EPS_INTEGRAL)):
            lin.setdefault((nuc, mt, g), []).append((e, d["S"], d["sS"]))
    if lin:
        n = len(lin)
        fig, axs = plt.subplots(1, n, figsize=(2.6 * n, 2.8))
        for ax, (key, v) in zip(np.atleast_1d(axs), sorted(lin.items())):
            v.sort()
            e, s, se = map(np.array, zip(*v))
            ax.errorbar(e * 100, s, yerr=se, fmt="o-", ms=3, lw=0.8)
            ax.set_xscale("log")
            ax.set_xlabel("perturbation (%)")
            g = "all energies" if key[2] == "all" else f"group {key[2]}"
            ax.set_title(f"{pretty[key[0]]} {C.LABELS[key[1]]}\n{g}", fontsize=8)
        np.atleast_1d(axs)[0].set_ylabel("S")
        fig.tight_layout()
        save(fig, out / "fig_linearity")
        plt.close(fig)


if __name__ == "__main__":
    main()

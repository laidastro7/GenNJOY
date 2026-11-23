"""
Build the list of OpenMC calculations (tasks.csv) of the S/U study.

    python su_tasks.py            # needs results/reference_tallies.h5 (python su_run.py reference)

A task is one OpenMC calculation:
  ref_NN                                   unperturbed, independent seed
  <nuclide>_MT<mt>_G<gg|all>_<p|m><eps%>   reaction mt of nuclide scaled by (1 +/- eps)
                                           on group gg (SCALE-44, 1 = lowest energy)
                                           or on the whole energy range (all)

Groups in which the perturbed data are zero are not computed (S = 0 exactly).
Groups whose reaction rate, estimated from the fine-group flux of the reference
run and unshielded group-averaged cross sections, is below SCREEN_LIMIT times
the absorption rate are not computed either (listed as 'screened' in
results/screening.csv). The unshielded estimate is larger than the true rate in
resonances, so the screening is conservative.
"""
import csv
import sys

import numpy as np

import su_common as C

sys.path.insert(0, str(C.HERE.parents[2]))          # repository root (gennjoy package)
from gennjoy import perturbation as P             # noqa: E402
from gennjoy import fission_perturbation as fp    # noqa: E402

SUB = 40   # fine bins per SCALE-44 group in the reference flux tally


def fine_bins():
    g = C.group_bounds()
    edges = [g[0]]
    for lo, hi in zip(g[:-1], g[1:]):
        edges += list(np.logspace(np.log10(lo), np.log10(hi), SUB + 1)[1:])
    return np.array(edges)


def load_library():
    import openmc.data
    lib = openmc.data.DataLibrary.from_xml(str(C.LIBRARY_XML))
    out = {}
    for e in lib.libraries:
        if e["type"] == "neutron":
            p = e["path"] if e["path"].startswith("/") else str(C.LIBRARY_XML.parent / e["path"])
            out[e["materials"][0]] = p
    return out


def rate_function(nuc, mt, T):
    """x -> summed cross section (barn) of the reaction(s) perturbed for mt (nu*sigma_f for nu)."""
    if mt in fp.NU_MTS:
        rx = fp.fission_reactions(nuc)
        def f(x):
            sf = sum(np.interp(x, r.xs[T].x, r.xs[T].y, left=0, right=0) for r in rx)
            _, _, tot = fp._nu_functions(nuc)
            nu = tot(x) if tot is not None else fp._nu_functions(nuc)[0](x)
            return nu * sf
        return f
    comps = P.components(nuc, mt)
    def f(x):
        return sum(np.interp(x, nuc.reactions[c].xs[T].x, nuc.reactions[c].xs[T].y, left=0, right=0)
                   for c in comps)
    return f


def chi_fraction(nuc, bounds):
    """Group fractions of the prompt fission spectrum (thermal incident energy)."""
    tabs = fp._chi_tables(nuc)
    if not tabs:
        return None
    t = tabs[0].energy_out[0]
    x, p = np.asarray(t.x, float), np.asarray(t.p, float)
    c = fp._tabular_cdf(x, p, 1 if t.interpolation == "histogram" else 2)
    return np.diff(np.interp(bounds, x, c / c[-1]))


def screening(ref_h5):
    """R_g / A for every (nuclide, mt, group): array dict and status dict."""
    import h5py
    import openmc
    import openmc.data
    bounds = C.group_bounds()
    edges = fine_bins()
    model = C.build_model(C.LIBRARY_XML, 10, 10, 5, 1)
    cells = [c for c in model.geometry.get_all_cells().values() if c.name in ("fuel", "clad", "moderator")]
    cells.sort(key=lambda c: ["fuel", "clad", "moderator"].index(c.name))
    with h5py.File(ref_h5, "r") as f:
        flux = f["flux"][()]            # (3, nbins)
        absorption = float(f["absorption"][()])
    paths = load_library()
    out_ratio, out_status = {}, {}
    xg = np.sqrt(edges[:-1] * edges[1:])
    for nucname, mts in C.REACTIONS.items():
        nuc = openmc.data.IncidentNeutron.from_hdf5(paths[nucname])
        T = list(nuc.energy)[0]
        dens = [c.fill.get_nuclide_atom_densities().get(nucname, 0.0) for c in cells]
        for mt in mts:
            if mt == fp.CHI_MT:
                frac = chi_fraction(nuc, bounds)
                out_ratio[(nucname, mt)] = frac
                out_status[(nucname, mt)] = ["computed" if v > C.SCREEN_LIMIT else "screened" for v in frac]
                continue
            f = rate_function(nuc, mt, T)
            # average cross section in every fine bin (11 log-spaced points)
            sub = np.exp(np.linspace(np.log(edges[:-1]), np.log(edges[1:]), 11))
            sig = f(sub).mean(axis=0)
            rate = sum(d * flux[i] * sig for i, d in enumerate(dens))
            rg = np.add.reduceat(rate, np.arange(0, len(rate), SUB)) / absorption
            # zero data in the group?
            nonzero = []
            for lo, hi in zip(bounds[:-1], bounds[1:]):
                xx = np.exp(np.linspace(np.log(lo), np.log(hi), 2001))
                nonzero.append(bool(np.any(f(xx) > 0)))
            out_ratio[(nucname, mt)] = rg
            out_status[(nucname, mt)] = [("zero" if not nz else ("computed" if r > C.SCREEN_LIMIT else "screened"))
                                         for nz, r in zip(nonzero, rg)]
    return out_ratio, out_status


def task_id(nuc, mt, g, eps):
    gs = "all" if g is None else f"{g:02d}"
    sign = "p" if eps > 0 else "m"
    return f"{nuc}_MT{mt}_G{gs}_{sign}{abs(eps) * 100:g}"


def main():
    ref_h5 = C.RESULTS_DIR / "reference_tallies.h5"
    if not ref_h5.exists():
        sys.exit(f"{ref_h5} not found: run 'python su_run.py reference' first")
    bounds = C.group_bounds()
    ratio, status = screening(ref_h5)

    rows, seen = [], set()

    def add(kind, nuc, mt, g, eps):
        tid = task_id(nuc, mt, g, eps) if kind != "ref" else nuc
        if tid in seen:
            return
        seen.add(tid)
        lo, hi = (bounds[0], bounds[-1]) if g is None else (bounds[g - 1], bounds[g])
        rows.append(dict(task_id=tid, kind=kind, nuclide=nuc if kind != "ref" else "", mt=mt or "",
                         group="all" if g is None else g, e_low=f"{lo:.6e}", e_high=f"{hi:.6e}",
                         eps=eps, seed=C.seed_for(tid)))

    for i in range(C.N_REFERENCE):
        add("ref", f"ref_{i:02d}", None, None, 0.0)
    # zero perturbations (eps = 0, same seed as ref_00): the grid refinement and the
    # rewriting of the files must leave k unchanged
    for nuc, mt, g in C.ZERO_TESTS:
        tid = f"{nuc}_MT{mt}_G{g:02d}_zero"
        seen.add(tid)
        rows.append(dict(task_id=tid, kind="zero", nuclide=nuc, mt=mt, group=g,
                         e_low=f"{bounds[g - 1]:.6e}", e_high=f"{bounds[g]:.6e}", eps=0.0,
                         seed=C.seed_for("ref_00")))
    for nuc, mts in C.REACTIONS.items():
        for mt in mts:
            for s in (1, -1):
                add("integral", nuc, mt, None, s * C.EPS_INTEGRAL)
    for nuc, mt, g in C.LINEARITY_CASES:
        if g == "max":
            g = int(np.argmax(np.abs(ratio[(nuc, mt)]))) + 1
        for e in C.EPS_LINEARITY:
            for s in (1, -1):
                add("linearity", nuc, mt, g, s * e)
    for nuc, mts in C.REACTIONS.items():
        for mt in mts:
            for g in range(1, len(bounds)):
                if status[(nuc, mt)][g - 1] != "computed":
                    continue
                for s in (1, -1):
                    add("group", nuc, mt, g, s * C.EPS_GROUP)

    C.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(C.HERE / "tasks.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(C.RESULTS_DIR / "screening.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["nuclide", "mt", "group", "e_low", "e_high", "rate_over_absorption", "status"])
        for (nuc, mt), r in ratio.items():
            for g in range(1, len(bounds)):
                w.writerow([nuc, mt, g, f"{bounds[g - 1]:.6e}", f"{bounds[g]:.6e}", f"{r[g - 1]:.4e}",
                            status[(nuc, mt)][g - 1]])
    kinds = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print(f"tasks.csv: {len(rows)} OpenMC calculations " + ", ".join(f"{k}: {v}" for k, v in kinds.items()))
    for (nuc, mt), st in status.items():
        n = {s: st.count(s) for s in ("computed", "screened", "zero")}
        print(f"  {nuc:5s} MT={mt:<5d} groups computed {n['computed']:2d}, screened {n['screened']:2d}, zero {n['zero']:2d}")


if __name__ == "__main__":
    main()

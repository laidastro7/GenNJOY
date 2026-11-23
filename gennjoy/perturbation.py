"""
Group-wise perturbation of OpenMC HDF5 nuclear data (core of GenNJOY option 7).

A perturbation multiplies one "reaction" of one nuclide by (1 + f) on the energy
group [E_low, E_high] and leaves every other datum unchanged. It is applied to
the data that OpenMC actually uses in transport:

* Reactions. OpenMC builds the total, absorption and fission cross sections at
  run time from the NON-redundant reactions stored in the HDF5 file; redundant
  sums (MT=1, 3, 4, 27, 101, ...) are either not written or only used for
  special purposes (MT=4 enters the total cross section in the unresolved
  resonance range through the inelastic competition term). A requested MT is
  therefore expanded into its non-redundant components with the ENDF summation
  rules (e.g. MT=4 -> MT=51-91, MT=18 -> MT=18 or MT=19/20/21/38), the
  components are scaled, and every redundant sum present in the file is updated
  with the same absolute change, so that all sum rules still hold.

* Exact group boundaries. OpenMC interpolates cross sections linearly between
  the points of the nuclide energy grid. Points are inserted in the grid at
  E_low, E_low(1+eps), E_high(1-eps) and E_high (eps = 1e-6), with values
  obtained by linear interpolation, so the unperturbed data are unchanged, and
  only the values strictly inside the group are scaled. The perturbation is
  then a step on [E_low, E_high] for every reaction, at every temperature in
  the file (and for the 0 K elastic data when present).

* Unresolved resonance range. When the probability tables are factors
  (multiply_smooth = 1, the NJOY/PURR default for LSSF = 1) the perturbation of
  the smooth cross sections propagates automatically. When the tables hold
  absolute values, the elastic, fission or capture columns are scaled at the
  table energies that lie inside the group (the table energy grid is coarse, so
  the step is not exact there; a warning is returned).

* Fission neutron data. nu (MT=452/455/456) and the prompt fission spectrum
  (pseudo MT=1018) are handled by fission_perturbation.py; the total nu used
  by OpenMC to create fission sites (the 'total_nu' data set) is kept equal to
  prompt + delayed.

* Thermal scattering. Below the upper energy of an S(alpha,beta) table, OpenMC
  replaces the free-atom elastic cross section of the bound nuclide by the
  thermal elastic + inelastic cross sections of the table. A perturbation of
  MT=2 of such a nuclide is therefore also applied to the thermal scattering
  cross sections on the part of the group below the table upper energy
  (option couple_thermal=True).

Derived quantities that do not affect the neutron transport (heating MT=301,
damage MT=444, gas production MT=203-207, photon production) are not changed.
"""
from pathlib import Path
import json
import os

import numpy as np

try:
    from gennjoy import fission_perturbation as fp
except ImportError:  # running as a script from the package folder
    import fission_perturbation as fp

EPS = 1.0e-6

# ENDF summation rules (same as openmc.data.endf.SUM_RULES)
SUM_RULES = {1: [2, 3],
             3: [4, 5, 11, 16, 17, 22, 23, 24, 25, 27, 28, 29, 30, 32, 33, 34, 35,
                 36, 37, 41, 42, 44, 45, 152, 153, 154, 156, 157, 158, 159, 160,
                 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172,
                 173, 174, 175, 176, 177, 178, 179, 180, 181, 183, 184, 185,
                 186, 187, 188, 189, 190, 194, 195, 196, 198, 199, 200],
             4: list(range(50, 92)),
             16: list(range(875, 892)),
             18: [19, 20, 21, 38],
             27: [18, 101],
             101: [102, 103, 104, 105, 106, 107, 108, 109, 111, 112, 113, 114,
                   115, 116, 117, 155, 182, 191, 192, 193, 197],
             103: list(range(600, 650)),
             104: list(range(650, 700)),
             105: list(range(700, 750)),
             106: list(range(750, 800)),
             107: list(range(800, 850))}

REACTION_LABELS = {2: "elastic", 4: "inelastic", 16: "(n,2n)", 18: "fission",
                   102: "(n,gamma)", 103: "(n,p)", 104: "(n,d)", 105: "(n,t)",
                   106: "(n,3He)", 107: "(n,alpha)", 452: "nu-total", 455: "nu-delayed",
                   456: "nu-prompt", 1018: "chi-prompt"}

NO_TRANSPORT_EFFECT = {203, 204, 205, 206, 207, 301, 444, 901}


# ---------------------------------------------------------------------------
# reaction bookkeeping
# ---------------------------------------------------------------------------
def components(nuc, mt):
    """Non-redundant reactions of `nuc` that make up `mt` (what OpenMC samples)."""
    rx = nuc.reactions.get(mt)
    if rx is not None and not rx.redundant:
        return [mt]
    out = []
    for m in SUM_RULES.get(mt, []):
        out += components(nuc, m)
    return sorted(set(out))


def redundant_present(nuc):
    """Redundant reactions stored in the file that have a summation rule."""
    return [mt for mt, rx in nuc.reactions.items()
            if rx.redundant and mt in SUM_RULES and mt not in NO_TRANSPORT_EFFECT]


def perturbable_mts(nuc):
    """MTs (and pseudo-MTs) that can be perturbed, with the reactions they act on."""
    out = {}
    for mt in sorted(nuc.reactions):
        if mt in NO_TRANSPORT_EFFECT:
            continue
        comps = components(nuc, mt)
        if comps:
            out[mt] = comps
    for mt in fp.available_fission_mts(nuc):
        out[mt] = [mt]
    return out


# ---------------------------------------------------------------------------
# grid refinement
# ---------------------------------------------------------------------------
def boundary_points(e_low, e_high):
    return np.array([e_low, e_low * (1.0 + EPS), e_high * (1.0 - EPS), e_high])


def _new_points(grid, pts):
    pts = np.asarray([p for p in pts if grid[0] < p < grid[-1]], dtype=float)
    if pts.size == 0:
        return pts
    i = np.clip(np.searchsorted(grid, pts), 1, len(grid) - 1)
    near = np.minimum(np.abs(grid[i] - pts), np.abs(grid[i - 1] - pts)) <= 1e-14 * pts
    return np.unique(pts[~near])


def refine_energy_grid(nuc, temperature, pts):
    """Insert `pts` in the energy grid of `temperature` and re-tabulate every reaction.

    The new points are inserted between existing grid points (repeated energies,
    if any, are kept); the cross sections at the new points are obtained by linear
    interpolation, as OpenMC does in transport, so the data are unchanged.
    """
    import openmc.data
    grid = np.asarray(nuc.energy[temperature], dtype=float)
    new = _new_points(grid, pts)
    if new.size == 0:
        return 0
    pos = np.searchsorted(grid, new, side="right")
    g2 = np.insert(grid, pos, new)
    nuc.energy[temperature] = g2
    for rx in nuc.reactions.values():
        xs = rx.xs.get(temperature)
        if xs is None or not isinstance(xs, openmc.data.Tabulated1D):
            continue
        x = np.asarray(xs.x, dtype=float)
        y = np.asarray(xs.y, dtype=float)
        thr_old = getattr(xs, "_threshold_idx", len(grid) - len(x))
        thr = int(thr_old + np.sum(pos <= thr_old))
        sel = pos > thr_old                     # points inserted above the threshold
        p_loc = np.searchsorted(x, new[sel], side="right")
        if np.all(np.diff(x) > 0):
            yv = np.interp(new[sel], x, y)
        else:   # repeated energies: interpolate on the segment to the right of them
            j = np.clip(p_loc - 1, 0, len(x) - 2)
            yv = y[j] + (new[sel] - x[j]) / (x[j + 1] - x[j]) * (y[j + 1] - y[j])
        xn = np.insert(x, p_loc, new[sel])
        yn = np.insert(y, p_loc, yv)
        if not np.array_equal(xn, g2[thr:]):
            raise RuntimeError(f"MT={rx.mt}: cross section grid does not match the energy grid")
        t = openmc.data.Tabulated1D(xn, yn)
        t._threshold_idx = thr
        rx.xs[temperature] = t
    return int(new.size)


def _inside(x, e_low, e_high):
    return (x > e_low * (1.0 + 0.5 * EPS)) & (x < e_high * (1.0 - 0.5 * EPS))


# ---------------------------------------------------------------------------
# perturbation of incident-neutron data
# ---------------------------------------------------------------------------
def perturb_nuclide(nuc, mt, e_low, e_high, fraction):
    """Perturb reaction `mt` of `nuc` (openmc.data.IncidentNeutron) in place.

    Returns a dict describing what was changed.
    """
    report = {"nuclide": nuc.name, "mt": int(mt), "e_low": float(e_low), "e_high": float(e_high),
              "fraction": float(fraction), "warnings": []}

    if mt in fp.NU_MTS or mt == fp.CHI_MT:
        changed = fp.perturb_fission_quantity(nuc, mt, e_low, e_high, fraction)
        report.update(targets=[int(mt)], redundant_updated=[], changed=bool(changed),
                      inserted_points={})
        return report

    comps = components(nuc, mt)
    if not comps:
        raise ValueError(f"{nuc.name}: MT={mt} has no non-redundant component in the file")
    if mt in NO_TRANSPORT_EFFECT:
        raise ValueError(f"MT={mt} does not affect neutron transport")
    report["targets"] = comps

    pts = boundary_points(e_low, e_high)
    temps = [T for T in nuc.energy]
    report["inserted_points"] = {T: refine_energy_grid(nuc, T, pts) for T in temps}

    changed = False
    deltas = {}
    for T in temps:
        grid = nuc.energy[T]
        mask_grid = _inside(grid, e_low, e_high)
        deltas[T] = {}
        for c in comps:
            xs = nuc.reactions[c].xs.get(T)
            if xs is None:
                continue
            thr = getattr(xs, "_threshold_idx", 0)
            m = mask_grid[thr:]
            if not np.any(m & (xs.y != 0.0)):
                continue
            d = np.zeros_like(grid)
            d[thr:][m] = xs.y[m] * fraction
            y = np.array(xs.y, dtype=float)
            y[m] *= (1.0 + fraction)
            xs.y = y
            deltas[T][c] = d
            changed = True

    # keep redundant sums consistent (same absolute change as their components)
    updated = []
    for r in redundant_present(nuc):
        rcomps = set(components(nuc, r))
        for T in temps:
            ds = [d for c, d in deltas[T].items() if c in rcomps]
            if not ds:
                continue
            dsum = np.sum(ds, axis=0)
            xs = nuc.reactions[r].xs.get(T)
            if xs is None:
                continue
            thr = getattr(xs, "_threshold_idx", 0)
            xs.y = np.asarray(xs.y, dtype=float) + dsum[thr:]
            if r not in updated:
                updated.append(r)
    report["redundant_updated"] = updated

    # unresolved resonance probability tables
    col = {2: 2, 18: 3, 19: 3, 20: 3, 21: 3, 38: 3, 102: 4}
    for T, urr in nuc.urr.items():
        if urr.multiply_smooth:
            continue
        cols = sorted({col[c] for c in comps if c in col})
        if not cols:
            continue
        e = np.asarray(urr.energy)
        m = _inside(e, e_low, e_high)
        if np.any(m):
            for k in cols:
                urr.table[m, k, :] *= (1.0 + fraction)
            report["warnings"].append(
                f"URR tables at {T} hold absolute values: scaled at {int(m.sum())} table energies "
                "(the step is not exact between table energies)")
            changed = True

    report["changed"] = bool(changed)
    return report


# ---------------------------------------------------------------------------
# thermal scattering
# ---------------------------------------------------------------------------
def perturb_thermal(tsl, e_low, e_high, fraction):
    """Scale the thermal elastic and inelastic cross sections of `tsl` on the group."""
    import openmc.data
    e_hi = min(e_high, tsl.energy_max)
    report = {"name": tsl.name, "e_low": float(e_low), "e_high": float(e_hi), "parts": [], "warnings": []}
    if e_low >= tsl.energy_max:
        return report
    pts = boundary_points(e_low, e_hi) if e_hi < tsl.energy_max else boundary_points(e_low, e_hi)[:2]
    for kind in ("elastic", "inelastic"):
        reac = getattr(tsl, kind, None)
        if reac is None:
            continue
        for T, xs in reac.xs.items():
            if isinstance(xs, openmc.data.Tabulated1D):
                x = np.asarray(xs.x, dtype=float)
                y = np.asarray(xs.y, dtype=float)
                new = _new_points(x, pts)
                if new.size:
                    p_loc = np.searchsorted(x, new, side="right")
                    if np.all(np.diff(x) > 0):
                        yv = np.interp(new, x, y)
                    else:
                        j = np.clip(p_loc - 1, 0, len(x) - 2)
                        yv = y[j] + (new - x[j]) / (x[j + 1] - x[j]) * (y[j + 1] - y[j])
                    x, y = np.insert(x, p_loc, new), np.insert(y, p_loc, yv)
                hi = e_hi if e_hi < tsl.energy_max else np.inf
                m = (x > e_low * (1.0 + 0.5 * EPS)) & (x < hi * (1.0 - 0.5 * EPS))
                y = y.copy()
                y[m] *= (1.0 + fraction)
                reac.xs[T] = openmc.data.Tabulated1D(x, y)
                report["parts"].append(f"{kind}/{T}")
            else:
                report["warnings"].append(
                    f"{kind}/{T}: {type(xs).__name__} cannot be perturbed on a partial group; left unchanged")
    return report


def thermal_tables_for(lib, nuclide):
    """Thermal libraries of a DataLibrary that apply to `nuclide`."""
    import h5py
    out = []
    for entry in lib.libraries:
        if entry["type"] != "thermal":
            continue
        with h5py.File(entry["path"], "r") as f:
            g = f[list(f.keys())[0]]
            nucs = [n.decode() if isinstance(n, bytes) else str(n) for n in g.attrs.get("nuclides", [])]
            emax = float(g.attrs["energy_max"])
        if nuclide in nucs:
            out.append((entry, emax))
    return out


# ---------------------------------------------------------------------------
# library writer
# ---------------------------------------------------------------------------
def write_perturbed_library(cross_sections_xml, out_dir, nuclide, mt, e_low, e_high, fraction,
                            couple_thermal=True, verify=True):
    """Write the perturbed nuclide (and thermal tables) and a cross_sections.xml in out_dir.

    All unperturbed entries point to the original files (absolute paths).
    Returns a report dict (also written to out_dir/perturbation_report.json).
    """
    import openmc.data
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    xml = Path(cross_sections_xml).resolve()
    lib = openmc.data.DataLibrary.from_xml(str(xml))
    for entry in lib.libraries:
        p = Path(entry["path"])
        if not p.is_absolute():
            entry["path"] = str((xml.parent / p).resolve())

    entry = next((e for e in lib.libraries if e["type"] == "neutron" and nuclide in e["materials"]), None)
    if entry is None:
        raise KeyError(f"{nuclide} not found in {xml}")
    orig_path = entry["path"]
    nuc = openmc.data.IncidentNeutron.from_hdf5(orig_path)
    report = perturb_nuclide(nuc, mt, e_low, e_high, fraction)
    new_path = out_dir / f"{nuclide}.h5"
    if new_path.exists():
        new_path.unlink()
    nuc.export_to_hdf5(str(new_path), mode="w")
    entry["path"] = str(new_path)
    report["files"] = {nuclide: str(new_path)}

    report["thermal"] = []
    if couple_thermal and mt == 2:
        for tentry, emax in thermal_tables_for(lib, nuclide):
            if e_low >= emax:
                continue
            tsl = openmc.data.ThermalScattering.from_hdf5(tentry["path"])
            trep = perturb_thermal(tsl, e_low, e_high, fraction)
            tpath = out_dir / f"{tsl.name}.h5"
            if tpath.exists():
                tpath.unlink()
            tsl.export_to_hdf5(str(tpath), mode="w")
            trep["original"] = tentry["path"]
            tentry["path"] = str(tpath)
            report["thermal"].append(trep)
            report["files"][tsl.name] = str(tpath)

    lib.export_to_xml(str(out_dir / "cross_sections.xml"))

    if verify:
        report["verification"] = verify_perturbation(orig_path, str(new_path), report)
        for trep in report["thermal"]:
            trep["verification"] = verify_thermal(trep["original"], report["files"][trep["name"]],
                                                  trep["e_low"], trep["e_high"], fraction)
    with open(out_dir / "perturbation_report.json", "w") as f:
        json.dump(report, f, indent=1, default=float)
    return report


# ---------------------------------------------------------------------------
# verification
# ---------------------------------------------------------------------------
def _eval(xs, x):
    return np.interp(x, xs.x, xs.y, left=0.0, right=0.0)


def _openmc_total(nuc, T, grid):
    tot = np.zeros_like(grid)
    for mt, rx in nuc.reactions.items():
        if rx.redundant or T not in rx.xs:
            continue
        tot += _eval(rx.xs[T], grid)
    return tot


def verify_perturbation(orig_path, pert_path, report, rtol=1e-9):
    """Check a perturbed incident-neutron file against the original one.

    For every temperature and every reaction, the ratio perturbed/original is
    evaluated on the union of both energy grids:
      * targeted reactions: 1 + f strictly inside the group, 1 outside;
      * redundant sums: equal to the original plus the change of their components;
      * all other reactions, nu, chi, URR tables: unchanged (unless targeted).
    The relative change of the total cross section rebuilt as OpenMC does
    (sum of the non-redundant reactions) is also returned.
    """
    import openmc.data
    o = openmc.data.IncidentNeutron.from_hdf5(orig_path)
    p = openmc.data.IncidentNeutron.from_hdf5(pert_path)
    mt, f = report["mt"], report["fraction"]
    e_low, e_high = report["e_low"], report["e_high"]
    res = {"ok": True, "checks": []}

    def fail(msg):
        res["ok"] = False
        res["checks"].append("FAIL " + msg)

    if mt in fp.NU_MTS or mt == fp.CHI_MT:
        res["checks"] += fp.verify_fission_quantity(o, p, mt, e_low, e_high, f)
        res["ok"] = not any(c.startswith("FAIL") for c in res["checks"])
        return res

    targets = set(report["targets"])
    red = set(report.get("redundant_updated", []))
    for T in o.energy:
        grid = np.union1d(o.energy[T], p.energy[T])
        inside = _inside(grid, e_low, e_high)
        outside = (grid <= e_low) | (grid >= e_high)
        for r in sorted(set(o.reactions) | set(p.reactions)):
            if r not in o.reactions or r not in p.reactions:
                fail(f"{T} MT={r} missing in one file")
                continue
            if T not in o.reactions[r].xs:
                continue
            yo = _eval(o.reactions[r].xs[T], grid)
            yp = _eval(p.reactions[r].xs[T], grid)
            if r in targets:
                nz = inside & (yo > 0)
                err_in = np.max(np.abs(yp[nz] / yo[nz] - (1 + f))) if nz.any() else 0.0
                err_out = np.max(np.abs(yp[outside] - yo[outside]) / np.maximum(yo[outside], 1e-300)) \
                    if outside.any() else 0.0
                if err_in > rtol or err_out > rtol:
                    fail(f"{T} MT={r}: max|ratio-(1+f)| inside={err_in:.2e}, max rel. change outside={err_out:.2e}")
                else:
                    res["checks"].append(f"ok {T} MT={r}: ratio 1+f inside ({int(nz.sum())} points), unchanged outside")
            elif r in red:
                comps = [c for c in components(o, r) if c in targets]
                d = sum(_eval(p.reactions[c].xs[T], grid) - _eval(o.reactions[c].xs[T], grid) for c in comps)
                err = np.max(np.abs(yp - yo - d) / np.maximum(np.abs(yo), 1e-300))
                if err > 1e-8:
                    fail(f"{T} redundant MT={r}: change differs from the sum of its components ({err:.2e})")
                else:
                    res["checks"].append(f"ok {T} redundant MT={r} updated with its components")
            else:
                err = np.max(np.abs(yp - yo))
                if err != 0.0:
                    fail(f"{T} MT={r} changed although not targeted (max abs diff {err:.3e})")
        res["checks"].append(f"ok {T}: all non-targeted reactions bit-identical on the union grid")

        # total as rebuilt by OpenMC
        to, tp = _openmc_total(o, T, grid), _openmc_total(p, T, grid)
        nz = inside & (to > 0)
        if nz.any():
            rel = (tp[nz] - to[nz]) / to[nz]
            res.setdefault("total_change", {})[T] = [float(rel.min()), float(rel.max())]
        # URR
        if T in o.urr:
            same = np.array_equal(o.urr[T].table, p.urr[T].table)
            res["checks"].append(f"ok {T} URR tables {'unchanged' if same else 'scaled (absolute tables)'}"
                                 f" (multiply_smooth={int(o.urr[T].multiply_smooth)})")
    # nu and chi untouched
    for c in fp.verify_fission_unchanged(o, p):
        if c.startswith("FAIL"):
            res["ok"] = False
        res["checks"].append(c)
    return res


def verify_thermal(orig_path, pert_path, e_low, e_high, fraction, rtol=1e-9):
    import openmc.data
    o = openmc.data.ThermalScattering.from_hdf5(orig_path)
    p = openmc.data.ThermalScattering.from_hdf5(pert_path)
    res = {"ok": True, "checks": []}
    for kind in ("elastic", "inelastic"):
        ro, rp = getattr(o, kind, None), getattr(p, kind, None)
        if ro is None:
            continue
        for T in ro.xs:
            xo, xp = ro.xs[T], rp.xs[T]
            if not isinstance(xo, openmc.data.Tabulated1D):
                continue
            grid = np.union1d(xo.x, xp.x)
            yo, yp = _eval(xo, grid), _eval(xp, grid)
            hi = e_high if e_high < o.energy_max else np.inf
            inside = (grid > e_low * (1 + 0.5 * EPS)) & (grid < hi * (1 - 0.5 * EPS)) & (yo > 0)
            outside = (grid <= e_low) | (grid >= hi)
            ei = np.max(np.abs(yp[inside] / yo[inside] - (1 + fraction))) if inside.any() else 0.0
            eo = np.max(np.abs(yp[outside] - yo[outside])) if outside.any() else 0.0
            if ei > rtol or eo != 0.0:
                res["ok"] = False
                res["checks"].append(f"FAIL {kind}/{T}: inside {ei:.2e}, outside {eo:.2e}")
            else:
                res["checks"].append(f"ok {kind}/{T}: ratio 1+f below {min(e_high, o.energy_max):.4g} eV, unchanged elsewhere")
    return res


def group_bounds_from_file(path):
    """Read ascending group boundaries (eV) from a groups.i-like file."""
    vals = sorted(float(v) for v in Path(path).read_text().replace(",", " ").split())
    return np.array(vals)

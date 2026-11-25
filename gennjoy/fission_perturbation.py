"""
Group-wise perturbation of fission neutron multiplicities (nu) and of the
prompt fission neutron spectrum (chi) in OpenMC HDF5 incident-neutron data.

Identifiers follow the ENDF convention used for covariance data:
    MT=452  total nu      (prompt + delayed neutron yields)
    MT=455  delayed nu    (all delayed-neutron precursor groups, same factor)
    MT=456  prompt nu
    MT=1018 prompt fission neutron spectrum chi (outgoing energy), as in FRENDY

nu is perturbed as a function of the INCIDENT neutron energy.
chi is perturbed as a function of the OUTGOING neutron energy, for every
incident energy, and is renormalised to unity afterwards (constrained
perturbation, consistent with the normalisation of ENDF MF35 covariances).

To make the perturbation an exact step on [E_low, E_high], points are inserted
at the group boundaries and just inside them before the values inside the
group are scaled; the original interpolation law is used to evaluate the
inserted points, so the unperturbed function is unchanged.
"""
import numpy as np

NU_MTS = {452: "Total nu (prompt + delayed)", 455: "Delayed nu", 456: "Prompt nu"}
CHI_MT = 1018
CHI_NAME = "Prompt fission spectrum (chi)"
FISSION_MTS = (18, 19, 20, 21, 38)
_EPS = 1.0e-6   # relative offset of the points inserted just inside the group


def fission_reactions(nuc):
    """Non-redundant fission reactions carrying neutron products (MT=18 or partials)."""
    rxs = []
    for mt in FISSION_MTS:
        rx = nuc.reactions.get(mt)
        if rx is None:
            continue
        if any(p.particle == "neutron" for p in rx.products):
            rxs.append(rx)
    # If MT=18 is present together with partial fission reactions, OpenMC uses
    # the non-redundant ones; perturb every reaction that has neutron products.
    return rxs


def available_fission_mts(nuc):
    """Pseudo-MTs that can be perturbed for this nuclide."""
    rxs = fission_reactions(nuc)
    if not rxs:
        return []
    modes = {p.emission_mode for rx in rxs for p in rx.products if p.particle == "neutron"}
    out = []
    if modes & {"prompt", "delayed", "total"}:
        out.append(452)
    if "delayed" in modes:
        out.append(455)
    if "prompt" in modes:
        out.append(456)
        out.append(CHI_MT)
    return out


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _evaluate(f, x):
    """Evaluate a yield function like OpenMC does in transport.

    openmc.data.Tabulated1D.__call__ replaces every value within a relative
    distance of 1e-5 of the first and last abscissae by the end values
    (np.isclose with its default rtol); this would hide the points inserted
    just inside a group that starts or ends at the end of the table, so the
    interpolation is done here explicitly.
    """
    import openmc.data
    x = np.atleast_1d(np.asarray(x, dtype=float))
    if not isinstance(f, openmc.data.Tabulated1D):
        return np.asarray(f(x), dtype=float)
    fx, fy = np.asarray(f.x, dtype=float), np.asarray(f.y, dtype=float)
    y = np.zeros_like(x)
    idx = np.clip(np.searchsorted(fx, x, side="right") - 1, 0, len(fx) - 2)
    for k in range(len(f.breakpoints)):
        i_begin = f.breakpoints[k - 1] - 1 if k > 0 else 0
        i_end = f.breakpoints[k] - 1
        c = (idx >= i_begin) & (idx < i_end)
        xk, xi, xi1 = x[c], fx[idx[c]], fx[idx[c] + 1]
        yi, yi1 = fy[idx[c]], fy[idx[c] + 1]
        law = f.interpolation[k]
        if law == 1:
            y[c] = yi
        elif law == 2:
            y[c] = yi + (xk - xi) / (xi1 - xi) * (yi1 - yi)
        elif law == 3:
            y[c] = yi + np.log(xk / xi) / np.log(xi1 / xi) * (yi1 - yi)
        elif law == 4:
            y[c] = yi * np.exp((xk - xi) / (xi1 - xi) * np.log(yi1 / yi))
        elif law == 5:
            y[c] = yi * np.exp(np.log(xk / xi) / np.log(xi1 / xi) * np.log(yi1 / yi))
    y[x <= fx[0]] = fy[0]
    y[x >= fx[-1]] = fy[-1]
    return y


def _boundary_points(e_low, e_high):
    return [e_low, e_low * (1.0 + _EPS), e_high * (1.0 - _EPS), e_high]


def _refine_tabulated1d(f, extra):
    """Return a Tabulated1D equal to f with extra x points inserted.

    Repeated abscissae (discontinuities, e.g. nu of U-238 at 5.5 MeV) are kept:
    the new points are inserted between existing points, never merged with them.
    """
    import openmc.data
    x = np.asarray(f.x, dtype=float)
    y = np.asarray(f.y, dtype=float)
    extra = np.array(sorted(e for e in extra if x[0] < e < x[-1]
                            and not np.any(np.isclose(x, e, rtol=1e-12, atol=0.0))))
    if extra.size == 0:
        return openmc.data.Tabulated1D(x.copy(), y.copy(), list(f.breakpoints), list(f.interpolation))
    pos = np.searchsorted(x, extra, side="right")
    yn_new = _evaluate(f, extra)
    xn = np.insert(x, pos, extra)
    yn = np.insert(y, pos, yn_new)
    # breakpoint k (1-based index of the last point of region k) moves by the number
    # of points inserted before it
    bps = [int(b + np.sum(pos < b)) for b in f.breakpoints]
    return openmc.data.Tabulated1D(xn, yn, bps, list(f.interpolation))


def _scale_tabulated1d(f, e_low, e_high, factor):
    """Scale f by `factor` on [e_low, e_high]; returns (new_function, changed)."""
    import openmc.data
    if isinstance(f, openmc.data.Polynomial):
        # convert a polynomial nu(E) to a fine tabulation (log-spaced, 1e-5 eV - 30 MeV)
        grid = np.logspace(-5, np.log10(3.0e7), 2000)
        f = openmc.data.Tabulated1D(grid, f(grid), [len(grid)], [2])
    if not isinstance(f, openmc.data.Tabulated1D):
        raise TypeError(f"Unsupported yield type: {type(f).__name__}")
    g = _refine_tabulated1d(f, _boundary_points(e_low, e_high))
    # a group that starts/ends at the end of the table also covers the energies
    # beyond it (OpenMC returns the end value there): the end point is scaled too
    gx = np.asarray(g.x, dtype=float)
    lo = (gx > e_low) | (e_low <= gx[0] * (1 + 1e-12))
    hi = (gx < e_high) | (e_high >= gx[-1] * (1 - 1e-12))
    mask = lo & hi
    if not np.any(mask):
        return f, False
    y = np.asarray(g.y, dtype=float)
    y[mask] *= factor
    g.y = y
    return g, True


def _tabular_integral(x, p, interp):
    if interp == 1:   # histogram
        return float(np.sum(p[:-1] * np.diff(x)))
    return float(np.sum(0.5 * (p[1:] + p[:-1]) * np.diff(x)))


def _tabular_cdf(x, p, interp):
    c = np.zeros_like(p)
    if interp == 1:
        c[1:] = np.cumsum(p[:-1] * np.diff(x))
    else:
        c[1:] = np.cumsum(0.5 * (p[1:] + p[:-1]) * np.diff(x))
    return c


def _perturb_tabular_spectrum(t, e_low, e_high, factor):
    """Constrained perturbation of one outgoing-energy Tabular distribution."""
    import openmc.stats
    x = np.asarray(t.x, dtype=float)
    p = np.asarray(t.p, dtype=float)
    interp = {"histogram": 1, "linear-linear": 2}.get(t.interpolation, 0)
    if interp not in (1, 2):
        raise ValueError(f"Unsupported outgoing-energy interpolation {interp}")
    extra = [e for e in _boundary_points(e_low, e_high)
             if x[0] < e < x[-1] and not np.any(np.isclose(x, e, rtol=1e-12, atol=0.0))]
    if extra:
        xn = np.sort(np.concatenate([x, extra]))
        if interp == 2:
            pn = np.interp(xn, x, p)
        else:   # histogram: value of the bin on the left
            pn = p[np.clip(np.searchsorted(x, xn, side="right") - 1, 0, len(p) - 1)]
        idx = np.searchsorted(xn, x)
        pn[idx] = p
        x, p = xn, pn
    mask = (x > e_low) & (x < e_high) if interp == 2 else (x >= e_low) & (x < e_high)
    if e_low <= x[0] * (1 + 1e-12):
        mask[0] = True
    if e_high >= x[-1] * (1 - 1e-12) and interp == 2:
        mask[-1] = True
    if not np.any(mask):
        return t, False
    p = p.copy()
    p[mask] *= factor
    norm = _tabular_integral(x, p, interp)
    p /= norm
    c = _tabular_cdf(x, p, interp)
    new = openmc.stats.Tabular(x, p, interpolation="histogram" if interp == 1 else "linear-linear",
                               ignore_negative=True)
    new.c = c
    return new, True


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------
def _yield_snapshot(nuc):
    """Copies of the neutron yield functions of every fission reaction (prompt, delayed, total)."""
    import copy
    snap = []
    for rx in fission_reactions(nuc):
        snap.append(([copy.deepcopy(p.yield_) for p in rx.products],
                     [copy.deepcopy(p.yield_) for p in rx.derived_products]))
    return snap


def _as_tabulated(f):
    import openmc.data
    if isinstance(f, openmc.data.Polynomial):
        grid = np.logspace(-5, np.log10(3.0e7), 2000)
        return openmc.data.Tabulated1D(grid, f(grid), [len(grid)], [2])
    return f


def _update_total_nu(nuc, snap, mt, e_low, e_high, fraction):
    """Keep the total nu used by OpenMC (data set 'total_nu') equal to prompt + delayed.

    For MT=452 the total is scaled like its components. For MT=455/456 the
    absolute change of the perturbed component(s) is added to the total on a
    grid that contains the boundary points and all component points of the group.
    """
    import openmc.data
    for rx, (old_prod, old_der) in zip(fission_reactions(nuc), snap):
        for k, dp in enumerate(rx.derived_products):
            if dp.particle != "neutron":
                continue
            if mt == 452:
                new, _ = _scale_tabulated1d(dp.yield_, e_low, e_high, 1.0 + fraction)
                dp.yield_ = new
                continue
            tot = _as_tabulated(old_der[k])
            pts = [np.asarray(tot.x, dtype=float), np.array(_boundary_points(e_low, e_high))]
            changed = []
            for i, p in enumerate(rx.products):
                if p.particle != "neutron":
                    continue
                if p.yield_ is not old_prod[i] and not _same_function(p.yield_, old_prod[i]):
                    changed.append((old_prod[i], p.yield_))
                    x = np.asarray(_as_tabulated(p.yield_).x, dtype=float)
                    pts.append(x[(x >= e_low) & (x <= e_high)])
            if not changed:
                continue
            grid = np.unique(np.concatenate(pts))
            vals = _evaluate(tot, grid)
            for o, n in changed:
                vals = vals + (_evaluate(n, grid) - _evaluate(o, grid))
            dp.yield_ = openmc.data.Tabulated1D(grid, vals, [len(grid)], [2])


def _same_function(a, b):
    try:
        xa, xb = np.asarray(a.x), np.asarray(b.x)
        return xa.shape == xb.shape and np.array_equal(xa, xb) and np.array_equal(np.asarray(a.y), np.asarray(b.y))
    except AttributeError:
        return False


def perturb_nu(nuc, mt, e_low, e_high, fraction):
    """Perturb nu (MT=452/455/456) on the incident-energy group [e_low, e_high]."""
    if mt not in NU_MTS:
        raise ValueError(mt)
    modes = {452: ("prompt", "delayed", "total"), 455: ("delayed",), 456: ("prompt", "total")}[mt]
    if mt == 456:
        # 'total' products only exist when prompt/delayed are not separated;
        # in that case prompt nu cannot be isolated
        has_prompt = any(p.emission_mode == "prompt" for rx in fission_reactions(nuc) for p in rx.products)
        modes = ("prompt",) if has_prompt else ()
    snap = _yield_snapshot(nuc)
    changed = False
    for rx in fission_reactions(nuc):
        for prod in rx.products:
            if prod.particle != "neutron" or prod.emission_mode not in modes:
                continue
            new_yield, ch = _scale_tabulated1d(prod.yield_, e_low, e_high, 1.0 + fraction)
            if ch:
                prod.yield_ = new_yield
                changed = True
    if changed:
        _update_total_nu(nuc, snap, mt, e_low, e_high, fraction)
    return changed


def perturb_chi(nuc, e_low, e_high, fraction):
    """Constrained perturbation of the prompt fission spectrum on the outgoing-energy group."""
    import openmc.data
    changed = False
    for rx in fission_reactions(nuc):
        for prod in rx.products:
            if prod.particle != "neutron" or prod.emission_mode != "prompt":
                continue
            for dist in prod.distribution:
                energy = getattr(dist, "energy", None)
                if energy is None:
                    continue
                if not isinstance(energy, openmc.data.ContinuousTabular):
                    raise TypeError("Prompt fission spectrum is not tabulated "
                                    f"({type(energy).__name__}); convert it before perturbing.")
                for i, t in enumerate(energy.energy_out):
                    new_t, ch = _perturb_tabular_spectrum(t, e_low, e_high, 1.0 + fraction)
                    if ch:
                        energy.energy_out[i] = new_t
                        changed = True
    return changed


def perturb_fission_quantity(nuc, mt, e_low, e_high, fraction):
    if mt == CHI_MT:
        return perturb_chi(nuc, e_low, e_high, fraction)
    return perturb_nu(nuc, mt, e_low, e_high, fraction)


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------
def _nu_functions(nuc):
    """(prompt, [delayed...], total) yield functions of the first fission reaction."""
    rx = fission_reactions(nuc)[0]
    prompt = [p.yield_ for p in rx.products if p.particle == "neutron" and p.emission_mode in ("prompt", "total")]
    delayed = [p.yield_ for p in rx.products if p.particle == "neutron" and p.emission_mode == "delayed"]
    total = [p.yield_ for p in rx.derived_products if p.particle == "neutron"]
    return prompt[0], delayed, (total[0] if total else None)


def _nu_grid(*funcs, e_low=None, e_high=None):
    pts = [np.logspace(-5, np.log10(2.0e7), 4000)]
    for f in funcs:
        if f is not None and hasattr(f, "x"):
            pts.append(np.asarray(f.x, dtype=float))
    if e_low is not None:
        pts.append(np.array(_boundary_points(e_low, e_high)))
    g = np.unique(np.concatenate(pts))
    return g[(g >= 1e-5) & (g <= 2.0e7)]


def verify_fission_quantity(o, p, mt, e_low, e_high, f, rtol=1e-9):
    checks = []
    if mt == CHI_MT:
        return _verify_chi(o, p, e_low, e_high, f)
    po, do_, to = _nu_functions(o)
    pp, dp_, tp = _nu_functions(p)
    g = _nu_grid(po, to, pp, tp, *do_, *dp_, e_low=e_low, e_high=e_high)
    xs0 = [np.asarray(f.x, dtype=float) for f in (po, *do_) if hasattr(f, "x")]
    x_first = min(x[0] for x in xs0) if xs0 else -np.inf
    x_last = max(x[-1] for x in xs0) if xs0 else np.inf
    lo_open = e_low <= x_first * (1 + 1e-12)
    hi_open = e_high >= x_last * (1 - 1e-12)
    inside = ((g > e_low * (1 + 0.5 * _EPS)) | lo_open) & ((g < e_high * (1 - 0.5 * _EPS)) | hi_open)
    outside = ((g <= e_low) & ~lo_open) | ((g >= e_high) & ~hi_open)
    sel = {452: ("prompt", "delayed"), 455: ("delayed",), 456: ("prompt",)}[mt]

    def ratio_check(name, a, b, perturbed):
        ya, yb = _evaluate(a, g), _evaluate(b, g)
        nz = inside & (ya > 0)
        if perturbed:
            ei = np.max(np.abs(yb[nz] / ya[nz] - (1 + f))) if nz.any() else 0.0
        else:
            ei = np.max(np.abs(yb[nz] / ya[nz] - 1)) if nz.any() else 0.0
        eo = np.max(np.abs(yb[outside] - ya[outside]) / np.maximum(ya[outside], 1e-300))
        ok = ei <= rtol and eo <= rtol
        checks.append(("ok " if ok else "FAIL ") + f"{name}: ratio {'1+f' if perturbed else '1'} inside "
                      f"(max dev {ei:.1e}), unchanged outside (max {eo:.1e})")

    ratio_check("prompt nu", po, pp, "prompt" in sel)
    for i, (a, b) in enumerate(zip(do_, dp_)):
        ratio_check(f"delayed nu group {i + 1}", a, b, "delayed" in sel)
    if to is not None:
        # total nu used by OpenMC = prompt + delayed, before and after
        def closure(pr, de, to_):
            s = _evaluate(pr, g) + sum(_evaluate(d, g) for d in de)
            return np.max(np.abs(_evaluate(to_, g) - s) / s)
        c0, c1 = closure(po, do_, to), closure(pp, dp_, tp)
        ok = c1 <= max(10 * c0, 1e-6)
        checks.append(("ok " if ok else "FAIL ") + f"total nu = prompt + delayed: max rel. deviation "
                      f"{c0:.1e} (original), {c1:.1e} (perturbed)")
        if mt == 452:
            ratio_check("total nu (OpenMC 'total_nu')", to, tp, True)
        else:
            yt0, yt1 = _evaluate(to, g), _evaluate(tp, g)
            checks.append(f"info total nu change inside the group: {np.max(np.abs(yt1[inside] / yt0[inside] - 1)):.3e} (relative)")
    return checks


def _chi_tables(nuc):
    import openmc.data
    out = []
    for rx in fission_reactions(nuc):
        for prod in rx.products:
            if prod.particle == "neutron" and prod.emission_mode == "prompt":
                for d in prod.distribution:
                    e = getattr(d, "energy", None)
                    if isinstance(e, openmc.data.ContinuousTabular):
                        out.append(e)
    return out


def _verify_chi(o, p, e_low, e_high, f):
    checks = []
    for eo_, ep_ in zip(_chi_tables(o), _chi_tables(p)):
        worst_norm, worst_shape = 0.0, 0.0
        for to, tp in zip(eo_.energy_out, ep_.energy_out):
            x = np.asarray(tp.x, float)
            pp = np.asarray(tp.p, float)
            interp = 1 if tp.interpolation == "histogram" else 2
            worst_norm = max(worst_norm, abs(_tabular_integral(x, pp, interp) - 1.0))
            po = np.interp(x, np.asarray(to.x, float), np.asarray(to.p, float))
            ins = (x > e_low * (1 + 0.5 * _EPS)) & (x < e_high * (1 - 0.5 * _EPS)) & (po > 0)
            out = ((x < e_low) | (x > e_high)) & (po > 0)
            if ins.any() and out.any():
                r_in = pp[ins] / po[ins]
                r_out = pp[out] / po[out]
                worst_shape = max(worst_shape, abs(np.median(r_in) / np.median(r_out) - (1 + f)),
                                  np.ptp(r_out) / np.median(r_out))
        ok = worst_norm < 1e-10 and worst_shape < 1e-6
        checks.append(("ok " if ok else "FAIL ") + f"chi: normalisation error {worst_norm:.1e}, "
                      f"ratio inside/outside - (1+f) and spread outside {worst_shape:.1e}")
    return checks


def verify_fission_unchanged(o, p):
    if not fission_reactions(o):
        return []
    po, do_, to = _nu_functions(o)
    pp, dp_, tp = _nu_functions(p)
    g = _nu_grid(po, to)
    same = np.array_equal(_evaluate(po, g), _evaluate(pp, g))
    if to is not None:
        same = same and np.array_equal(_evaluate(to, g), _evaluate(tp, g))
    return [("ok " if same else "FAIL ") + "nu (prompt and total) unchanged"]

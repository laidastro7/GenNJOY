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
def _boundary_points(e_low, e_high):
    return [e_low, e_low * (1.0 + _EPS), e_high * (1.0 - _EPS), e_high]


def _refine_tabulated1d(f, extra):
    """Return a Tabulated1D equal to f with extra x points inserted."""
    import openmc.data
    x = np.asarray(f.x, dtype=float)
    extra = np.array([e for e in extra if x[0] < e < x[-1] and not np.any(np.isclose(x, e, rtol=1e-12, atol=0.0))])
    if extra.size == 0:
        return openmc.data.Tabulated1D(x.copy(), np.asarray(f.y, dtype=float).copy(),
                                       list(f.breakpoints), list(f.interpolation))
    xn = np.sort(np.concatenate([x, extra]))
    yn = np.asarray(f(xn), dtype=float)
    # keep the original values exactly at the original points
    idx = np.searchsorted(xn, x)
    yn[idx] = f.y
    # map interpolation-region ends to the new grid
    bps = [int(np.searchsorted(xn, x[b - 1]) + 1) for b in f.breakpoints]
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
    mask = (g.x > e_low) & (g.x < e_high)
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
    changed = False
    for rx in fission_reactions(nuc):
        for prod in rx.products:
            if prod.particle != "neutron" or prod.emission_mode not in modes:
                continue
            new_yield, ch = _scale_tabulated1d(prod.yield_, e_low, e_high, 1.0 + fraction)
            if ch:
                prod.yield_ = new_yield
                changed = True
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

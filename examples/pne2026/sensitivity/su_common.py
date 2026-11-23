"""
Common settings of the sensitivity/uncertainty (S/U) study of the Mosteller pin cell
(Yahiaoui et al., Progress in Nuclear Energy 2026, Section III.C).

Everything that defines the study is in this file: model, run presets, energy
groups, nuclide-reaction pairs, perturbation sizes.
"""
from pathlib import Path
import hashlib
import os

import numpy as np

HERE = Path(__file__).resolve().parent

# ----------------------------------------------------------------------------
# Paths (can be overridden with environment variables)
# ----------------------------------------------------------------------------
LIBRARY_XML = Path(os.environ.get("SU_LIBRARY", HERE / "library_600K" / "cross_sections.xml"))
COVARIANCE_DIR = Path(os.environ.get("SU_COVARIANCE", HERE / "covariance_600K"))
WORK_DIR = Path(os.environ.get("SU_WORK", HERE / "work"))
RESULTS_DIR = Path(os.environ.get("SU_RESULTS", HERE / "results"))

# ----------------------------------------------------------------------------
# Energy groups: SCALE 44-group structure (eV, ascending), as used for S/U
# analyses with TSUNAMI and the SCALE covariance library.
# ----------------------------------------------------------------------------
GROUPS_FILE = HERE / "inputs" / "groups_scale44.i"


def group_bounds():
    vals = sorted(float(v) for v in GROUPS_FILE.read_text().split())
    return np.array(vals)


# ----------------------------------------------------------------------------
# Nuclide-reaction pairs. MT=4 means all inelastic levels (MT=51-91, the
# redundant MT=4 being kept consistent), MT=18 the fission reactions used by
# OpenMC, MT=452 total nu, MT=1018 the prompt fission spectrum (constrained,
# outgoing energy). MT=2 of H1 includes the S(alpha,beta) data below the upper
# energy of c_H_in_H2O.
# ----------------------------------------------------------------------------
REACTIONS = {
    "U235": [2, 4, 18, 102, 452, 1018],
    "U238": [2, 4, 16, 18, 102, 452],
    "O16":  [2, 4, 102, 107],
    "H1":   [2, 102],
}
LABELS = {2: "elastic", 4: "inelastic", 16: "(n,2n)", 18: "fission", 102: "(n,gamma)",
          107: "(n,alpha)", 452: "nu-bar", 1018: "chi"}

# Covariance block for each pseudo-MT: (MF, MT) in the ERRORR output
COVARIANCE_ID = {2: (33, 2), 4: (33, 4), 16: (33, 16), 18: (33, 18), 102: (33, 102),
                 107: (33, 107), 452: (31, 452), 1018: (35, 18)}

# ----------------------------------------------------------------------------
# Perturbation sizes (relative). Central differences with +eps and -eps.
# ----------------------------------------------------------------------------
EPS_GROUP = 0.10                         # group-wise sensitivities
EPS_INTEGRAL = 0.02                      # whole energy range
EPS_LINEARITY = [0.01, 0.02, 0.05, 0.10, 0.20]
# Linearity study: (nuclide, mt, group index or None for the whole range)
LINEARITY_CASES = [("U235", 18, None), ("U238", 102, None), ("H1", 2, None), ("U235", 452, None),
                   ("U235", 18, "max"), ("U238", 102, "max")]
ZERO_TESTS = [("U238", 102, 30), ("H1", 2, 10), ("U235", 452, 15)]
N_REFERENCE = 10                         # unperturbed runs with independent seeds

# Screening: a group is not computed (S set to 0) when the reaction rate of the
# perturbed reaction(s) in that group, from the unshielded estimate below, is
# smaller than SCREEN_LIMIT times the total absorption rate of the cell.
SCREEN_LIMIT = 1.0e-6

# ----------------------------------------------------------------------------
# Run presets
# ----------------------------------------------------------------------------
PRESETS = {
    # check of the scripts on a laptop (k uncertainty of a few hundred pcm)
    "pilot": dict(particles=2000, batches=60, inactive=20),
    # production runs (k uncertainty about 6-7 pcm)
    "full": dict(particles=100000, batches=2000, inactive=50),
}


def seed_for(task_id):
    """Independent, reproducible seed for every task."""
    return 1 + int(hashlib.sha256(task_id.encode()).hexdigest(), 16) % (2**31 - 2)


# ----------------------------------------------------------------------------
# Mosteller pin cell (hot zero power, 600 K), same model as doppler/mosteller_doppler.py
# ----------------------------------------------------------------------------
ENRICHMENT = 3.1 / 100.0
PITCH = 1.26678
TEMPERATURE = 600.0


def build_model(cross_sections, particles, batches, inactive, seed, tallies=False, n_flux_bins=0):
    import openmc
    uo2 = openmc.Material(name="UO2")
    uo2.add_nuclide("U235", ENRICHMENT)
    uo2.add_nuclide("U238", 1.0 - ENRICHMENT)
    uo2.add_nuclide("O16", 2.0)
    uo2.set_density("g/cm3", 10.399)
    uo2.temperature = TEMPERATURE

    clad = openmc.Material(name="Cladding")
    for iso, frac in [("Zr90", 0.5145), ("Zr91", 0.1122), ("Zr92", 0.1715),
                      ("Zr94", 0.1738), ("Zr96", 0.0280)]:
        clad.add_nuclide(iso, frac)
    clad.set_density("g/cm3", 6.55)
    clad.temperature = TEMPERATURE

    water = openmc.Material(name="Borated water")
    water.add_nuclide("H1", 2.0)
    water.add_nuclide("O16", 1.0)
    water.add_nuclide("B10", 0.0014 * 0.199)
    water.add_nuclide("B11", 0.0014 * 0.801)
    water.set_density("g/cm3", 0.71)
    water.add_s_alpha_beta("c_H_in_H2O")
    water.temperature = TEMPERATURE

    materials = openmc.Materials([uo2, clad, water])
    materials.cross_sections = str(cross_sections)

    fuel_or = openmc.ZCylinder(r=0.39398)
    clad_ir = openmc.ZCylinder(r=0.40226)
    clad_or = openmc.ZCylinder(r=0.45972)
    box = openmc.model.RectangularPrism(PITCH, PITCH, boundary_type="reflective")
    fuel = openmc.Cell(name="fuel", fill=uo2, region=-fuel_or)
    gap = openmc.Cell(name="gap", fill=None, region=+fuel_or & -clad_ir)
    cladc = openmc.Cell(name="clad", fill=clad, region=+clad_ir & -clad_or)
    mod = openmc.Cell(name="moderator", fill=water, region=+clad_or & -box)
    geometry = openmc.Geometry([fuel, gap, cladc, mod])

    settings = openmc.Settings()
    settings.particles = int(particles)
    settings.batches = int(batches)
    settings.inactive = int(inactive)
    settings.seed = int(seed)
    settings.output = {"tallies": False, "summary": False}
    lower = (-PITCH / 2, -PITCH / 2, -1.0)
    upper = (PITCH / 2, PITCH / 2, 1.0)
    settings.source = openmc.IndependentSource(space=openmc.stats.Box(lower, upper),
                                               constraints={"fissionable": True})

    model = openmc.Model(geometry=geometry, materials=materials, settings=settings)
    if tallies:
        cells = openmc.CellFilter([fuel, cladc, mod])
        efine = openmc.EnergyFilter(np.logspace(-5, np.log10(2.0e7), n_flux_bins + 1))
        t = openmc.Tally(name="flux_fine")
        t.filters = [cells, efine]
        t.scores = ["flux"]
        t2 = openmc.Tally(name="absorption")
        t2.scores = ["absorption", "nu-fission"]
        model.tallies = openmc.Tallies([t, t2])
    return model


def read_keff(statepoint):
    """k_combined (mean, std) from a statepoint without loading the whole file."""
    import h5py
    with h5py.File(statepoint, "r") as f:
        k = f["k_combined"][()]
    return float(k[0]), float(k[1])

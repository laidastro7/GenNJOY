# Inputs for the results of Yahiaoui et al., Progress in Nuclear Energy (2026)

This folder contains everything needed to reproduce the results reported in the article
with GenNJOY release **vX.Y.Z** (archived at https://doi.org/10.5281/zenodo.XXXXXXX).

| Item | Version used |
|---|---|
| GenNJOY | vX.Y.Z (commit `xxxxxxx`) |
| NJOY2016 | 2016.78 (3 Feb 2025) |
| OpenMC (executable and Python API) | 0.15.0 (git 84fb85977f46) |
| Python | 3.10.20 |
| Ghostscript (`ps2pdf`) | 10.02.1 |
| Nuclear data | ENDF/B-VIII.0 (Brown et al., Nucl. Data Sheets 148 (2018) 1), neutron and thermal-scattering sublibraries as distributed by NNDC (DIST-FEB18), downloaded with GenNJOY option 1 |
| ICSBEP OpenMC models | mit-crpg/benchmarks, commit `ba41bee5` (17 Sep 2025), folder `icsbep` |
| Operating system | Ubuntu 24.04 LTS under WSL2 |

Install the environment with `conda env create -f environment.yml`, activate it, then install
GenNJOY from the archived release with `pip install -e .` at the repository root, and download
ENDF/B-VIII.0 with option 1 of the `gennjoy` command.

## 1. ICSBEP validation (`icsbep/`)
* `neutron_process_batch_324.i`, `tsl_process_batch_324.i`: the 158 nuclides (293.6 K) and six
  thermal-scattering evaluations needed by the 324 cases.
* `process_icsbep_library.sh`: runs GenNJOY options 4, 5, and 6 non-interactively with these batch
  files and records the hardware, software versions, and wall-clock times.
* `case_list_324_openmc.txt`: the 324 cases used (paths in mit-crpg/benchmarks/icsbep);
  `excluded_70.txt`: the 70 cases of that repository that were not used.
* `convert_C0.py`: ENDF/B-VIII.0 has no natural-carbon evaluation; this script replaces `C0` in the
  OpenMC models by C12 (0.9893) and C13 (0.0107) atom fractions. Apply it to a copy of the models.
* `check_endf_files.py`: checks that all ENDF files listed in the batch files are present.

## 2. Doppler coefficient (`doppler/`)
* `neutron_process_batch_doppler.i`, `tsl_process_batch_doppler.i`: fuel nuclides at 22 temperatures
  (550-650 K and 850-950 K in 10 K steps) and the other nuclides at 600 K.
* `mosteller_doppler.py`: OpenMC model of the Mosteller pin cell, the 22 calculations, and the
  two-point and least-squares Doppler coefficients.

## 3. Covariance processing (`covariance/`)
* `covariance_process_batch.i`, `groups.i` (70 groups), `flux.i` (OpenMC pin-cell spectrum used as
  weighting function): inputs of GenNJOY option 8 (MF33, MF31, and MF35; efmean = 0.0253 eV).

## 4. Sensitivity and uncertainty (`sensitivity/`)
* Scripts that run the OpenMC calculations with the perturbed libraries produced by GenNJOY
  option 7 and combine the sensitivities with the covariance matrices (sandwich rule).

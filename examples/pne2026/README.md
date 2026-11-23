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
| Nuclear data | ENDF/B-VIII.1 (Nobre et al., Nucl. Data Sheets 210 (2026) 1), neutron and thermal-scattering sublibraries as distributed by NNDC, downloaded with GenNJOY option 1 |
| ICSBEP OpenMC models | mit-crpg/benchmarks, commit `ba41bee5` (17 Sep 2025), folder `icsbep` |
| Operating system | Ubuntu 24.04 LTS under WSL2 |

Install the environment with `conda env create -f environment.yml`, activate it, then install
GenNJOY from the archived release with `pip install -e .` at the repository root, and download
ENDF/B-VIII.1 with option 1 of the `gennjoy` command.

## 1. ICSBEP validation (`icsbep/`)
* `neutron_process_batch_394.i`, `tsl_process_batch_394.i`: the 161 nuclides (293.6 K) and seven
  thermal-scattering evaluations needed by the 394 OpenMC models of mit-crpg/benchmarks (ENDF/B-VIII.1
  file names).
* `process_icsbep_library.sh`: runs GenNJOY options 4, 5, and 6 non-interactively with these batch
  files and records the hardware, software versions, and wall-clock times.
* `build_reference_library.py`: builds the independent reference library from the same ENDF files with
  the NJOY interface of OpenMC (`openmc.data.njoy`), without any GenNJOY code. `--tsl-elastic ace` keeps
  the NJOY incoherent elastic data (used for hydrogen in polyethylene, see the article).
* `run_icsbep_suite.py`: runs a list of models with a given `cross_sections.xml` and identical run
  settings (particles, batches, seed); restartable.
* `analyze_icsbep.py`: per-model results and statistics (Supplementary Tables S1–S4).
* `plot_fig9.py`, `plot_fig10_11.py`: Figures 9, 10, and 11 of the article (TIFF and PNG, 600 dpi).
* `run_icsbep_validation.sh`: runs the complete chain (clone of the models at commit `ba41bee`,
  C0 conversion, both libraries, OpenMC runs, analysis); `bash run_icsbep_validation.sh pilot` runs
  12 representative models first to estimate the computing time.
* `case_catalog_394.csv`: the 394 models with their status, benchmark value and its source;
  `case_list_394.txt`, `pilot_cases.txt`, `ch2_cases.txt` (models that contain polyethylene).
* `convert_C0.py`: ENDF/B-VIII.1 has no natural-carbon evaluation; this script replaces `C0` in the
  OpenMC models by C12 (0.9893) and C13 (0.0107) atom fractions.
* `check_endf_files.py`: checks that all ENDF files listed in the batch files are present.
* `compare_manual_workflow.py`: comparison of the GenNJOY processing time with a sequential workflow.

## 2. Doppler coefficient (`doppler/`)
* `neutron_process_batch_doppler.i`, `tsl_process_batch_doppler.i`: fuel nuclides at 22 temperatures
  (550-650 K and 850-950 K in 10 K steps) and the other nuclides at 600 K.
* `mosteller_doppler.py`: OpenMC model of the Mosteller pin cell, the 22 calculations, and the
  two-point and least-squares Doppler coefficients.

## 3. Covariance processing (`covariance/`)
* `covariance_process_batch.i`, `groups.i` (70 groups), `flux.i` (OpenMC pin-cell spectrum used as
  weighting function): inputs of GenNJOY option 8 (MF33, MF31, and MF35; efmean = 0.0253 eV) used in
  the first version of the article. The revised sensitivity/uncertainty study uses the inputs of
  `sensitivity/` (SCALE 44-group structure).

## 4. Sensitivity and uncertainty (`sensitivity/`)
Mosteller pin cell at 600 K, ENDF/B-VIII.1, direct perturbations of the HDF5 data with
`gennjoy/perturbation.py` (GenNJOY option 7), central differences, sandwich rule.
* `prepare_600K.sh`: processes the library at 600 K (GenNJOY options 4, 5, 6, in a temporary copy of the
  package so that the library already in `gennjoy/data/` is not touched) and the covariance matrices
  (`process_covariances.py`, option 8: SCALE-44 groups, pin-cell spectrum as weighting function, MF33
  with all cross-reaction blocks, MF31, MF35).
* `su_common.py`: model, groups, nuclide-reaction pairs, perturbation sizes, run settings.
* `su_tasks.py`: list of the 1057 OpenMC calculations (10 references with independent seeds, 3
  zero-perturbation tests, whole-range perturbations, linearity study, group-wise perturbations of
  +/-10 %); groups with no data or negligible reaction rates are not computed.
* `su_run.py`: one calculation (perturbed files written and verified, OpenMC run, k recorded).
* `campaign.py`, `run_campaign.sh`, `START_HERE.sh`: the complete campaign in one command
  (OpenMC version check, machine record, restartable runs with progress and remaining time,
  archive of the raw results); `make_package.sh` builds a self-contained package for another machine.
* `su_analyze.py`: sensitivities and their Monte Carlo uncertainties, linearity and sum checks,
  uncertainty of k (sandwich rule with cross-reaction covariances, noise-bias correction), tables
  and figures.
* `plot_covariances.py`: NJOY COVR/VIEWR plots of the covariance matrices.

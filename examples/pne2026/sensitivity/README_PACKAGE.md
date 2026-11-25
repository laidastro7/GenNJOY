# Sensitivity / uncertainty calculations — Mosteller pin cell (OpenMC)

This package contains everything needed for the OpenMC calculations of the
sensitivity and uncertainty study of the GenNJOY article (Progress in Nuclear Energy,
revision 1): the ENDF/B-VIII.1 library at 600 K processed with GenNJOY (HDF5, with
SHA-256 checksums), the covariance matrices (CSV), the perturbation code and the
scripts. Neither NJOY nor GenNJOY has to be installed.

## Run — one command

    bash START_HERE.sh

That is all. The script

* uses the OpenMC already installed if its version is **0.15.0 or newer** (a newer version
  is accepted with a warning: the article used 0.15.0); otherwise it creates the conda
  environment `gennjoy-pne2026` with OpenMC 0.15.0 from `environment.yml` (and installs
  Miniforge in `~/miniforge3` if conda is absent);
* checks the library checksums, records the configuration of the machine (CPU, cores,
  memory, OS, OpenMC build, packages) in `results/machine/`, runs a short test calculation;
* runs the 1057 calculations (100 000 particles x 2000 batches, 50 inactive, independent
  seeds) **in the background** — closing the terminal or logging out does not stop them —
  and shows the progress: bar, percentage, k, session time, total time over all sessions,
  remaining time and expected end date. Ctrl-C only stops the display;
* at the end analyses the results and writes `SU_results_<host>_<date>.tar.gz`.

**Without internet.** Install OpenMC 0.15.0 first with the separate package
`OpenMC_0.15.0_offline` (`bash install_openmc_offline.sh`, installs in `~/openmc-0.15.0`);
`START_HERE.sh` then finds and uses that installation by itself.

Other commands:

    bash START_HERE.sh status     # show the progress again
    bash START_HERE.sh stop       # stop the calculations
    bash START_HERE.sh test       # optional: ~25 calculations of every kind with very few particles
                                  # (a few minutes), results in results_test/, nothing to send

**Interruptions.** After any stop (reboot, power cut, `stop`), run `bash START_HERE.sh` again:
the finished calculations are kept, the run continues from there, and the wall time of all
sessions is added up.

By default all logical CPUs are used, one calculation per 10 of them (8 calculations x 10
threads on a machine with 40 cores / 80 threads); to change it:
`JOBS=4 THREADS=20 bash START_HERE.sh`. Disk space: about 1-2 GB.

## What to send back

The file `examples/pne2026/sensitivity/SU_results_<host>_<date>.tar.gz` (a few MB).
If the run cannot be finished, send the folder `examples/pne2026/sensitivity/results/`.

## Contents

| File | Role |
|---|---|
| `START_HERE.sh` | the only command |
| `examples/pne2026/sensitivity/campaign.py`, `run_campaign.sh` | checks, machine record, runs, analysis, archive |
| `.../su_common.py` | model (Mosteller pin cell, 600 K), SCALE-44 groups, reactions, perturbation sizes, run settings |
| `.../su_tasks.py`, `su_run.py`, `su_analyze.py` | list of calculations, one calculation, analysis |
| `.../library_600K/` | ENDF/B-VIII.1 at 600 K, HDF5 written by GenNJOY, `SHA256SUMS` |
| `.../covariance_600K/csv/` | relative covariance matrices (NJOY ERRORR via GenNJOY), SCALE-44 groups |
| `.../EXPECTED_OPENMC.txt` | OpenMC version and build used to prepare the data |
| `gennjoy/` | perturbation of the HDF5 data and its verification |

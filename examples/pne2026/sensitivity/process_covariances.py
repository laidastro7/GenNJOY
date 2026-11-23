"""
Multigroup covariance matrices of the S/U study (GenNJOY option 8, run without prompts).

    python process_covariances.py [--endf DIR] [--cpus N]

ENDF/B-VIII.1 files of U235, U238, O16, H1 (inputs/covariance_process_batch_600K.i),
600 K, SCALE-44 groups (inputs/groups_scale44.i), weighting function = neutron
spectrum of the pin cell (inputs/flux_pincell.i, iwt = 1), relative covariances
(irelco = 1). MF33 (all reactions and all cross-reaction blocks given in the
evaluation), MF31 (nu-bar) and MF35 (prompt fission spectrum, efmean = 0.0253 eV,
the incident energy of the thermal fissions that dominate in the pin cell).

Output: covariance_600K/ (NJOY outputs) and covariance_600K/csv/ (one CSV per block).
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

import su_common as C

sys.path.insert(0, str(C.HERE.parents[2]))
from gennjoy import run_covariance_processing as R   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endf", default=str(C.HERE.parents[2] / "gennjoy" / "data" / "incident_neutron_endf"))
    ap.add_argument("--cpus", type=int, default=os.cpu_count())
    ap.add_argument("--njoy", default=shutil.which("njoy") or "njoy")
    a = ap.parse_args()

    R.Config.ENDF_DIR = Path(a.endf)
    R.Config.OUTPUT_COV = C.COVARIANCE_DIR
    R.Config.OUTPUT_PLOTS = C.COVARIANCE_DIR / "plots"
    R.Logger.LOG_FILE = C.COVARIANCE_DIR / "covariance_processing.log"
    C.COVARIANCE_DIR.mkdir(parents=True, exist_ok=True)

    batch = C.HERE / "inputs" / "covariance_process_batch_600K.i"
    groups = (C.HERE / "inputs" / "groups_scale44.i").read_text()
    flux = (C.HERE / "inputs" / "flux_pincell.i").read_text()
    jobs = R.parse_covariance_batch(batch)
    mts = {}
    for job in jobs:
        avail = R.get_covariance_mts(R.Config.ENDF_DIR / job["element_n"])
        mts[job["name"]] = [m for m in (2, 4, 16, 18, 102, 107) if m in avail] or [2, 102]
    proc = R.CovarianceProcessor(batch, a.njoy, a.cpus, ign_val=1, iwt_val=1, groups_text=groups,
                                 flux_text=flux, generate_plots=False, job_mts_dict=mts,
                                 do_nu_chi=True, efmean=0.0253)
    proc.execute()
    n = len(list((C.COVARIANCE_DIR / "csv").glob("*.csv")))
    print(f"{n} CSV files in {C.COVARIANCE_DIR / 'csv'}")


if __name__ == "__main__":
    main()

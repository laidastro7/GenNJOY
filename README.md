<div align="center">
<pre>
         ____            _   _     _  ___ __   __
        / ___| ___ _ __ | \ | |   | |/ _ \ \ / /
       | |  _ / _ \ '_ \|  \| |_  | | | | \ V / 
       | |_| |  __/ | | | |\  | |_| | |_| || |  
        \____|\___|_| |_|_| \_|\___/ \___/ |_|  
</pre>
</div>

# GenNJOY ⚛️
### Automated Nuclear Data Processing Framework (NJOY + OpenMC)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![NJOY](https://img.shields.io/badge/NJOY-2016-red)](https://github.com/njoy/NJOY2016)
[![OpenMC](https://img.shields.io/badge/OpenMC-Compatible-green)](https://docs.openmc.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

**GenNJOY** is an advanced software framework written in Python designed to automate complex nuclear data processing workflows. The system seamlessly bridges raw nuclear data libraries (ENDF) with the **NJOY** processing code, and subsequently converts the outputs into HDF5 format ready for **OpenMC** Monte Carlo simulations. It also supports exact perturbations and covariance matrix generation for sensitivity and uncertainty analysis.

---

## 🚀 Key Features

* **📦 Library Management:** Automated fetching and organization of raw nuclear data libraries (ENDF/B-VII.1, VIII.0 and VIII.1) for both Incident Neutrons and Thermal Scattering Laws (TSL).
* **⚙️ Input Generation:** Intelligent generation of NJOY input decks for isotopes and thermal scattering materials, handling complex parameter definitions automatically.
* **⚡ Parallel Processing:** Full utilization of multi-core CPU architectures to accelerate NJOY execution batches.
* **🔄 Automated Conversion:** Seamless conversion of generated ACE files into OpenMC-compatible HDF5 libraries.
* **🎯 Exact Group-wise Perturbation:** Create perturbed HDF5 libraries for sensitivity analysis: reaction cross sections, fission neutron multiplicities (total, prompt, delayed nu; MT 452/456/455) and the prompt fission spectrum (MT 1018, renormalised). The perturbation acts on the data that OpenMC uses in transport: redundant reactions are expanded into their non-redundant components (e.g. MT=4 → MT=51–91) and the redundant sums kept consistent, points are inserted at the group boundaries so that the change is an exact step at every temperature, the total nu used to create fission sites is kept equal to prompt + delayed, unresolved-resonance probability tables are handled, and a perturbation of MT=2 is also applied to the S(alpha,beta) data of the bound nuclide. Every perturbed file is checked against the original one (JSON report).
* **📊 Covariance Processing:** Multigroup covariance matrices for cross sections (MF33), nu (MF31) and fission spectra (MF35) with ERRORR, CSV export, and correlation plots (PDF/PS) with COVR/VIEWR.
* **🗂️ xsdir Management:** Automatic merging and updating of `xsdir` files to ensure data consistency across the pipeline.
* **🛠️ Interactive CLI:** A user-friendly Command Line Interface (CLI) that eliminates the need for manual script handling.

---

## 📋 Prerequisites

Before installing GenNJOY, ensure the following requirements are met on your system:

1.  **Python 3.8+**
2.  **NJOY2016:**
    * The NJOY2016 source code must be compiled and installed.
    * Ensure the `njoy` executable is accessible in your system PATH, or be ready to provide its path during runtime.
3.  **OpenMC:**
    * Required for converting ACE to HDF5 and for executing exact perturbations.
    * [OpenMC Installation Guide](https://docs.openmc.org/en/stable/quickinstall.html)
4.  **Ghostscript (`ps2pdf`) [Optional but Recommended]:**
    * Required by the Covariance module to automatically convert NJOY Viewr PostScript plots into readable PDFs.
    * *Ubuntu/Debian:* `sudo apt install ghostscript`
    * *macOS:* `brew install ghostscript`

---

## 💾 Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/laidastro7/GenNJOY
    cd GenNJOY
    ```

2.  **Install the Package:**
    ```bash
    pip install -e .
    ```
    *This command installs the package along with all dependencies listed in `pyproject.toml` and `setup.py`.*

---

## 🖥️ Usage

Once installed, you can run the tool from anywhere in your terminal using the command:

```bash
gennjoy
 ```
**Typical Workflow:**
* Option [1]: Download raw nuclear data libraries (ENDF). Data will be stored in the internal data/ directory.
* Option [2] & [3]: Generate NJOY input decks based on the downloaded files.
* Option [4] & [5]: Execute NJOY processing (Generates ACE files and updates xsdir).
* Option [6]: Convert the generated ACE libraries into an HDF5 library for OpenMC.
* Option [7]: Create Perturbed HDF5 Libraries by specifying the isotope, the reaction MTs and the perturbation percentage; one perturbed library is written per energy group of `inputs/groups.i` (sub-folder with the perturbed HDF5 file(s), a `cross_sections.xml` and the verification report).
* Option [8]: Generate Covariance Matrices and cross-section correlation plots.

### Perturbations from Python (no prompts)
The perturbation used by option 7 is also available as a function, e.g. for scripted
sensitivity studies:

```python
from gennjoy.perturbation import write_perturbed_library

# U-238 radiative capture +10 % between 6 and 10 eV
report = write_perturbed_library("hdf5_library/cross_sections.xml", "pert_U238_102",
                                 "U238", 102, 6.0, 10.0, 0.10)
print(report["verification"]["ok"])   # every reaction checked against the original file
# then run OpenMC with pert_U238_102/cross_sections.xml
```

A complete sensitivity/uncertainty study built on it (Mosteller pin cell, central differences,
sandwich rule with the covariance matrices of option 8) is in
[`examples/pne2026/sensitivity`](examples/pne2026/sensitivity).

## 📂 Project Structure
```bash
GenNJOY/
├── gennjoy/                         # Package Source Code
│   ├── __init__.py                  # Package Initialization & Versioning
│   ├── cli.py                       # Main Entry Point (CLI) and Menu System
│   ├── compile_openmc_library.py    # Converts generated ACE files to OpenMC HDF5 format
│   ├── fetch_endf_library.py        # Automates downloading and organizing ENDF libraries
│   ├── generate_neutron_input.py    # Generates NJOY input decks for incident neutron data
│   ├── generate_tsl_input.py        # Generates NJOY input decks for thermal scattering data
│   ├── njoy_execution_engine.py     # Core engine wrapper for executing NJOY commands
│   ├── perturb_hdf5.py              # Option 7: interactive creation of perturbed HDF5 libraries
│   ├── perturbation.py              # Exact group-wise perturbation of HDF5 data and its verification
│   ├── fission_perturbation.py      # Group-wise perturbation of nu (MT 452/455/456) and chi (MT 1018)
│   ├── errorr_reader.py             # Reader/CSV export of ERRORR covariance output (MF31/33/35)
│   ├── run_covariance_processing.py # Multi-core covariance matrix processing & plotting
│   ├── run_neutron_processing.py    # Orchestrates incident neutron data processing
│   ├── run_tsl_processing.py        # Orchestrates thermal scattering processing
│   ├── scheduling.py                # Longest-first dynamic scheduling of the NJOY jobs
│   ├── temperature_index.json       # Database for TSL temperature mappings
│   ├── xsdir_mcnp5                  # MCNP5 xsdir Template used for merging
│   ├── data/                        # Processed Data Storage
│   │   ├── incident_neutron_ace/
│   │   ├── incident_neutron_endf/
│   │   ├── thermal_scattering_ace/
│   │   ├── thermal_scattering_endf/
│   │   ├── hdf5_library/
│   │   ├── hdf5_perturbed_library/  # Output of option 7 (one sub-folder per MT and group)
│   │   ├── covariance_matrices/     # Generated .coverx files
│   │   ├── covariance_plots/        # Generated PDF/PS correlation plots
│   │   └── njoy_input_decks/
│   └── inputs/                      # Control files (groups.i, flux.i, inventories)
├── pyproject.toml                   # Modern Build Configuration
├── setup.py                         # Setup Script for package definition
├── requirements.txt                 # List of Python Dependencies
├── MANIFEST.in                      # Package Data Configuration
├── .gitignore                       # Git Ignore Rules
├── CITATION.cff                     # Citation metadata (software release and DOI)
├── examples/pne2026/                # Inputs and scripts for the results of the PNE article
├── LICENSE                          # GNU General Public License v3.0
└── README.md                        # Project Documentation
```
## 🤝 Contributing
Contributions are welcome! If you have suggestions for improvements or new features:

* Fork the Project.
* Create your Feature Branch (git checkout -b feature/AmazingFeature).
* Commit your Changes (git commit -m 'Add some AmazingFeature').
* Push to the Branch (git push origin feature/AmazingFeature).
* Open a Pull Request.

## 📌 Versions and reproducibility
The results of Yahiaoui et al., *Progress in Nuclear Energy* (2026), were obtained with GenNJOY **vX.Y.Z**
(archived on Zenodo: https://doi.org/10.5281/zenodo.XXXXXXX), NJOY2016.78, OpenMC 0.15.0, Python 3.10
and ENDF/B-VIII.1. The inputs and scripts are in [`examples/pne2026`](examples/pne2026).
Every release is tagged (`git tag`) and archived on Zenodo; please cite the release you used (see `CITATION.cff`).

## 👨‍🔬 Authors
Dr. Mohamed Laid YAHIAOUI - Lead Developer - [GitHub Profile](https://github.com/laidastro7)

📧 Email: m.yahiaoui@univ-batna2.dz

## 📄 License
GenNJOY is distributed under the GNU General Public License, version 3 (GPL-3.0-only); see the LICENSE file for the full text.

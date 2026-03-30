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
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

**GenNJOY** is an advanced software framework written in Python designed to automate complex nuclear data processing workflows. The system seamlessly bridges raw nuclear data libraries (ENDF) with the **NJOY** processing code, and subsequently converts the outputs into HDF5 format ready for **OpenMC** Monte Carlo simulations. It also supports exact perturbations and covariance matrix generation for sensitivity and uncertainty analysis.

---

## 🚀 Key Features

* **📦 Library Management:** Automated fetching and organization of raw nuclear data libraries (ENDF/B-VIII.0) for both Incident Neutrons and Thermal Scattering Laws (TSL).
* **⚙️ Input Generation:** Intelligent generation of NJOY input decks for isotopes and thermal scattering materials, handling complex parameter definitions automatically.
* **⚡ Parallel Processing:** Full utilization of multi-core CPU architectures to accelerate NJOY execution batches.
* **🔄 Automated Conversion:** Seamless conversion of generated ACE files into OpenMC-compatible HDF5 libraries.
* **🎯 Exact Perturbation [NEW]:** Create exact perturbed HDF5 cross-section libraries for sensitivity analysis.
* **📊 Covariance Processing [NEW]:** Automated generation of multi-group covariance matrices (`.coverx`) and visual correlation plots (PDF/PS) using ERRORR and COVR modules.
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
* Option [7]: Create Perturbed HDF5 Libraries by manually specifying isotopes, reaction MTs, and perturbation percentages.
* Option [8]: Generate Covariance Matrices and cross-section correlation plots.

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
│   ├── perturb_hdf5.py              # Exact HDF5 cross-section perturbation module
│   ├── run_covariance_processing.py # Multi-core covariance matrix processing & plotting
│   ├── run_neutron_processing.py    # Orchestrates incident neutron data processing
│   ├── run_tsl_processing.py        # Orchestrates thermal scattering processing
│   ├── temperature_index.json       # Database for TSL temperature mappings
│   ├── xsdir_mcnp5                  # MCNP5 xsdir Template used for merging
│   ├── data/                        # Processed Data Storage
│   │   ├── incident_neutron_ace/
│   │   ├── incident_neutron_endf/
│   │   ├── thermal_scattering_ace/
│   │   ├── thermal_scattering_endf/
│   │   ├── hdf5_library/
│   │   ├── hdf5_perturbed_library/  # Output for exact perturbations
│   │   ├── covariance_matrices/     # Generated .coverx files
│   │   ├── covariance_plots/        # Generated PDF/PS correlation plots
│   │   └── njoy_input_decks/
│   └── inputs/                      # Control files (groups.i, flux.i, inventories)
├── pyproject.toml                   # Modern Build Configuration
├── setup.py                         # Setup Script for package definition
├── requirements.txt                 # List of Python Dependencies
├── MANIFEST.in                      # Package Data Configuration
├── .gitignore                       # Git Ignore Rules
├── LICENSE                          # Project License (MIT)
└── README.md                        # Project Documentation
```
## 🤝 Contributing
Contributions are welcome! If you have suggestions for improvements or new features:

* Fork the Project.
* Create your Feature Branch (git checkout -b feature/AmazingFeature).
* Commit your Changes (git commit -m 'Add some AmazingFeature').
* Push to the Branch (git push origin feature/AmazingFeature).
* Open a Pull Request.

## 👨‍🔬 Authors
Dr. Mohamed Laid YAHIAOUI - Lead Developer - [GitHub Profile](https://github.com/laidastro7)

📧 Email: mohamedlaid.yahiaoui@univ-jijel.dz

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.

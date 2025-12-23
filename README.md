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

**GenNJOY** is an advanced software framework written in Python designed to automate complex nuclear data processing workflows. The system seamlessly bridges raw nuclear data libraries (ENDF) with the **NJOY** processing code, and subsequently converts the outputs into HDF5 format ready for **OpenMC** Monte Carlo simulations.

---

## 🚀 Key Features

* **📦 Library Management:** Automated fetching and organization of raw nuclear data libraries (ENDF/B-VIII.0, VIII.1) for both Incident Neutrons and Thermal Scattering Laws (TSL).
* **⚙️ Input Generation:** Intelligent generation of NJOY input decks for isotopes and thermal scattering materials, handling complex parameter definitions automatically.
* **⚡ Parallel Processing:** Full utilization of multi-core CPU architectures to accelerate NJOY execution batches.
* **🔄 Automated Conversion:** Seamless conversion of generated ACE files into OpenMC-compatible HDF5 libraries.
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
    * OpenMC must be installed.
    * [OpenMC Installation Guide](https://docs.openmc.org/en/stable/quickinstall.html)

---

## 💾 Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/laidastro7/GenNJOY
    cd GenNJOY
    ```

2.  **Install the Package :**
   
    ```bash
    pip install .
    ```
    *This command installs the package along with all dependencies listed in `requirements.txt`.*

---

## 🖥️ Usage

Once installed, you can run the tool from anywhere in your terminal using the command:

```bash
gennjoy

```

The interactive main menu will appear:

### Typical Workflow:

1. **Option [1]:** Download raw nuclear data libraries (ENDF). Data will be stored in `gennjoy/data`.
2. **Option [2] & [3]:** Generate NJOY input decks based on the downloaded files.
3. **Option [4] & [5]:** Execute NJOY processing.
* You will be prompted to specify the number of CPU cores and the `njoy` path.
* This step generates ACE files and updates the `xsdir`.


4. **Option [6]:** Convert the generated ACE libraries into an HDF5 library for OpenMC.

---

## 📂 Project Structure

```text
GenNJOY/
├── gennjoy/                 # Package Source Code
│   ├── __init__.py          # Package Initialization & Versioning
│   ├── cli.py               # Main Entry Point (CLI) and Menu System
│   ├── compile_openmc_library.py  # Converts generated ACE files to OpenMC HDF5 format
│   ├── fetch_endf_library.py      # Automates downloading and organizing ENDF libraries
│   ├── generate_neutron_input.py  # Generates NJOY input decks for incident neutron data
│   ├── generate_tsl_input.py      # Generates NJOY input decks for thermal scattering data
│   ├── njoy_execution_engine.py   # Core engine wrapper for executing NJOY commands
│   ├── run_neutron_processing.py  # Orchestrates incident neutron data processing
│   ├── run_tsl_processing.py      # Orchestrates thermal scattering processing
│   ├── temperature_index.json     # Database for TSL temperature mappings
│   ├── xsdir_mcnp5          # MCNP5 xsdir Template used for merging
│   ├── data/                # Data Storage (ENDF, ACE, HDF5)
│   └── inputs/              # Generated Input Decks (Control files)
├── pyproject.toml           # Modern Build Configuration
├── setup.py                 # Legacy Setup Script for backward compatibility
├── requirements.txt         # List of Python Dependencies
├── MANIFEST.in              # Package Data Configuration (includes non-code files)
├── .gitignore               # Git Ignore Rules
├── LICENSE                  # Project License (MIT)
└── README.md                # Project Documentation
```
---

## 🤝 Contributing

Contributions are welcome! If you have suggestions for improvements or new features:

1. Fork the Project.
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`).
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the Branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

## 👨‍🔬 Authors

* **Dr. Mohamed Laid YAHIAOUI** - *Lead Developer* - [GitHub Profile](https://github.com/laidastro7)
  * 📧 Email: mohamedlaid.yahiaoui@univ-jijel.dz

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](https://github.com/laidastro7/GenNJOY/blob/main/LICENSE) file for details.

```

```

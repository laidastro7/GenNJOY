<div align="center">
<pre>
         ____            _   _     _  ___ __   __
        / ___| ___ _ __ | \ | |   | |/ _ \\ \ / /
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
    * OpenMC library and the `openmc-ace-to-hdf5` tool must be installed.
    * [OpenMC Installation Guide](https://docs.openmc.org/en/stable/quickinstall.html)

---

## 💾 Installation

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/yourusername/GenNJOY.git](https://github.com/yourusername/GenNJOY.git)
    cd GenNJOY
    ```

2.  **Install the Package (Editable Mode):**
    It is recommended to use a virtual environment.
    ```bash
    pip install -e .
    ```
    *This command installs the package along with all dependencies listed in `requirements.txt`.*

---

## 🖥️ Usage

Once installed, you can run the tool from anywhere in your terminal using the command:

```bash
gennjoy


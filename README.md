```markdown
# GenNJOY: Automated NJOY Processing Tool

[![License: GPL](https://img.shields.io/badge/License-GPL-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.x-yellow.svg)](https://www.python.org/)
[![OpenMC](https://img.shields.io/badge/OpenMC-Compatible-green.svg)](https://docs.openmc.org/)

**GenNJOY** is a comprehensive Python-based automation tool designed to simplify the interaction with **NJOY2016** for nuclear data processing. It streamlines the workflow of generating inputs, executing NJOY, and converting data for use with Monte Carlo codes like **OpenMC**.

Designed for researchers and nuclear engineers, GenNJOY automates tedious tasks and leverages multi-CPU parallel processing to significantly reduce computation time.

## 🚀 Key Features

* **Automated Data Retrieval**: Download Incident and Thermal Neutron Data (ENDF/B-VIII.0).
* **Input Generation**: Automatically create NJOY input files for:
    * Incident neutron data.
    * Thermal neutron scattering data (TSL).
* **Parallel Execution**: Execute NJOY on multiple CPUs to speed up processing.
* **Format Conversion**: Convert ACE library files directly to HDF5 format for OpenMC compatibility.
* **User-Friendly CLI**: Simple command-line interface to manage the entire workflow.

## 📋 Prerequisites

Before using GenNJOY, ensure you have the following installed:

1.  **Python 3.x**
2.  **NJOY2016**: [Download from GitHub](https://github.com/njoy/NJOY2016)
3.  **OpenMC**: [Installation Guide](https://docs.openmc.org/en/stable/)
4.  Git

## 🛠️ Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/laidastro7/GenNJOY.git](https://github.com/laidastro7/GenNJOY.git)
    cd GenNJOY
    ```

2.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Verify NJOY path:**
    Ensure your NJOY executable is accessible or placed in the `njoy_bin/` directory as structured in the project.

## 💻 Usage

Run the main program from the terminal:

```bash
python GenNJOY.py

```

### Interactive Menu Options

Once launched, follow the on-screen prompts to select an operation:

* **Download Data**: Fetches ENDF-B-VIII.0 incident and thermal data.
* **Generate Inputs (Incident)**: Creates input files for incident neutron processing.
* **Generate Inputs (Thermal)**: Creates input files for thermal scattering logic.
* **Execute NJOY (Incident)**: Runs NJOY processing for incident data using the generated inputs.
* **Execute NJOY (Thermal)**: Runs NJOY processing for thermal data.
* **Convert to HDF5**: Converts resulting ACE files into OpenMC-compatible HDF5 files.
* **Exit**: Closes the application.

## 📂 Project Structure

```text
GenNJOY/
├── GenNJOY.py             # Main application entry point
├── src/                   # Source scripts for logic processing
│   ├── download_data.py   # Data downloader
│   ├── gen_input_n.py     # Incident input generator
│   ├── gen_njoy_n.py      # NJOY execution wrapper (Incident)
│   ├── gen_input_tsl.py   # Thermal input generator
│   ├── gen_njoy_tsl.py    # NJOY execution wrapper (Thermal)
│   └── conversion_ace_hdf5.py # ACE to HDF5 converter
├── njoy_bin/              # NJOY executables and libraries
├── data/                  # Data storage (Evaluations, ACE, HDF5)
├── inputs/                # Configuration files for the scripts
└── requirements.txt       # Python dependencies

```

## 🤝 Contributing

Contributions are welcome! Please fork the repository and create a pull request for any features, bug fixes, or documentation improvements.

## 📄 License

This project is licensed under the GPL License - see the `LICENSE` file for details.

## 👥 Authors

* **Mohamed Laid YAHIAOUI** - *Lead Developer* - [mohamedlaid.yahiaoui@univ-jijel.dz](mailto:mohamedlaid.yahiaoui@univ-jijel.dz)
* **Aissa BOURENANE**

```

```

import os
from pathlib import Path

# This code dynamically determines the path to the gennjoy folder wherever it is on your computer
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Direct environment variables to read from the project's internal data folder
os.environ.setdefault("GENNJOY_ENDF_DATA", str(DATA_DIR / "incident_neutron_endf"))
os.environ.setdefault("GENNJOY_ENDF_DATA_NEUTRON", str(DATA_DIR / "incident_neutron_endf"))
os.environ.setdefault("GENNJOY_ENDF_DATA_THERMAL", str(DATA_DIR / "thermal_scattering_endf"))
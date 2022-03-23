"""Configuration file for the library."""
import logging
import numpy as np

LOG_LEVEL = "INFO"

# Define Data Path
CORE_DATA_PATH = "data"
LOG_PATH = "logs/"
IMPORT_DATA_PATH = f"{CORE_DATA_PATH}/import_data"
OUTPUT_FOLDER = f"{CORE_DATA_PATH}/output_data"
PKL_FOLDER = f"{CORE_DATA_PATH}/pkl_data"
PKL_DATA_IMPORTS = f"{PKL_FOLDER}/imported_data"
PKL_DATA_INTERMEDIATE = f"{PKL_FOLDER}/intermediate_data"
PKL_DATA_FINAL = f"{PKL_FOLDER}/final_data"
SOLVER_INPUT_DATA_PATH = f"{CORE_DATA_PATH}/solver_input_data"

# Log formatter
LOG_FORMATTER = logging.Formatter(
    "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)

# STANDARDISED SOLVER
SOLVER_INPUT_TABLES = [
    "technology_switches",
    "emissions",
    "initial_state",
    "technology_characteristics",
    "demand",
]

START_YEAR = 2020
END_YEAR = 2050
MODEL_YEARS = np.arange(START_YEAR, END_YEAR + 1)

# Emissions
GHGS = [
    "co2",
    # "ch4",
    # "n2o"
]

EMISSION_SCOPES = ["scope1", "scope2", "scope3_upstream", "scope3_downstream"]


FOLDERS_TO_CHECK_IN_ORDER = [
    # Top level folders
    CORE_DATA_PATH,
    LOG_PATH,
    # Second level folders
    IMPORT_DATA_PATH,
    PKL_FOLDER,
    OUTPUT_FOLDER,
    # Third level folders
    PKL_DATA_IMPORTS,
    PKL_DATA_INTERMEDIATE,
    PKL_DATA_FINAL,
]

PE_MODEL_FILENAME_DICT = {
    "power": "Power Model.xlsx",
    "ccus": "CCUS Model.xlsx",
    "hydrogen": "H2 Model.xlsx",
}

PE_MODEL_SHEETNAME_DICT = {
    "power": ["GridPrice", "GridEmissions", "RESPrice"],
    "ccus": ["Transport", "Storage"],
    "hydrogen": ["Prices", "Emissions"],
}

MPP_COLOR_LIST = [
    "#A0522D",
    "#7F6000",
    "#1E3B63",
    "#9DB1CF",
    "#FFC000",
    "#59A270",
    "#BCDAC6",
    "#E76B67",
    "#A5A5A5",
    "#F2F2F2",
]

NEW_COUNTRY_COL_LIST = [
    "country_code",
    "country",
    "official_name",
    "m49_code",
    "region",
    "continent",
    "wsa_region",
    "rmi_region",
]

NEW_COUNTRY_COL_LIST = [
    "country_code",
    "country",
    "official_name",
    "m49_code",
    "region",
    "continent",
    "wsa_region",
    "rmi_region",
]

FILES_TO_REFRESH = []

EU_COUNTRIES = [
    "AUT",
    "BEL",
    "BGR",
    "CYP",
    "CZE",
    "DEU",
    "DNK",
    "ESP",
    "EST",
    "FIN",
    "FRA",
    "GRC",
    "HRV",
    "HUN",
    "IRL",
    "ITA",
    "LTU",
    "LUX",
    "LVA",
    "MLT",
    "NLD",
    "POL",
    "PRT",
    "ROU",
    "SVK",
    "SVN",
    "SWE",
]

CARBON_BUDGET_REF = {
    "aluminium": 11,
    "cement": 42,
    "chemicals": 32,
    "steel": 56,
    "aviation": 17,
    "shipping": 16,
    "trucking": 36,
}

# TODO: Add more decomissioning rates
DECOMMISSION_RATES = {
    "PDH": 0.1,
}

# Scope of the model run - to be specified
MODEL_SCOPE = "Global"

# Override plant parameters; unit t/year
ASSUMED_PLANT_CAPACITY = 3000

PATHWAYS = [
    "bau",
    "fa",
    "lc",
]

# Sensitivities: low fossil prices, constrained CCS, BAU demand, low demand
SENSITIVITIES = [
    "def",
]

# Sectors
SECTOR = "chemicals" #"aluminium, steel, ..."

# Product
PRODUCTS = {
    "chemicals": "Ammonia",        
}

RUN_PARALLEL = False

run_config = {
    # "IMPORT_DATA",
    # "CALCULATE_VARIABLES",
    # "MAKE_RANKINGS",
    "SIMULATE_PATHWAY",
    # "CALCULATE_OUTPUTS",
    # "EXPORT_OUTPUTS",
    # "PLOT_AVAILABILITIES"
    # "MERGE_OUTPUTS"
}
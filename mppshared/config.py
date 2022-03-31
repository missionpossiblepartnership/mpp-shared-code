"""Configuration file for the library."""
import logging
import numpy as np

### LOGGER ####
LOG_LEVEL = "INFO"
LOG_FORMATTER = logging.Formatter(
    "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)


### DATA IMPORT AND EXPORT
CORE_DATA_PATH = "data"
LOG_PATH = "logs/"
IMPORT_DATA_PATH = f"{CORE_DATA_PATH}/import_data"
OUTPUT_FOLDER = f"{CORE_DATA_PATH}/output_data"
PKL_FOLDER = f"{CORE_DATA_PATH}/pkl_data"
PKL_DATA_IMPORTS = f"{PKL_FOLDER}/imported_data"
PKL_DATA_INTERMEDIATE = f"{PKL_FOLDER}/intermediate_data"
PKL_DATA_FINAL = f"{PKL_FOLDER}/final_data"
SOLVER_INPUT_DATA_PATH = f"{CORE_DATA_PATH}/solver_input_data"


# Naming of solver input tables
SOLVER_INPUT_TABLES = [
    "technology_switches",
    "emissions",
    "initial_state",
    "technology_characteristics",
    "demand",
]

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

### MODEL DECISION PARAMETERS ###
START_YEAR = 2020
END_YEAR = 2050
MODEL_YEARS = np.arange(START_YEAR, END_YEAR + 1)

# Emissions
GHGS = [
    "co2",
    # "ch4",
    # "n2o"
]

# Emission scopes included in data analysis
EMISSION_SCOPES = ["scope1", "scope2", "scope3_upstream", "scope3_downstream"]

# Emission scopes included in weighting when ranking technology transitions
EMISSION_SCOPES_RANKING = ["scope1", "scope2", "scope3_upstream", "scope3_downstream"]

# Capacity utilisation factor thresholds
# TODO: make sector-specific with dictionary
CUF_LOWER_THRESHOLD = 0.6
CUF_UPPER_THRESHOLD = 0.95

# TODO: Add more decomissioning rates
DECOMMISSION_RATES = {
    "PDH": 0.1,
}

# Scope of the model run - to be specified
MODEL_SCOPE = ["Global"]

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

### SECTOR-SPECIFIC PARAMETERS ###
# Sectors for which the model can be run
SECTOR = "chemicals"  # "aluminium, steel, ..."

# Products produced by each sector
PRODUCTS = {
    "chemicals": ["Ammonia"],
}

### RUN CONFIGURATION ###

RUN_PARALLEL = False

run_config = {
    "IMPORT_DATA",
    "CALCULATE_VARIABLES",
    "APPLY_IMPLICIT_FORCING",
    "MAKE_RANKINGS",
    "SIMULATE_PATHWAY",
    # "CALCULATE_OUTPUTS",
    # "EXPORT_OUTPUTS",
    # "PLOT_AVAILABILITIES"
    # "MERGE_OUTPUTS"
}
### RANKING ###
NUMBER_OF_BINS_RANKING = 10

"""
Configuration to use for ranking
For each rank type (newbuild, retrofit, decommission), and each scenario,
the dict items represent the weights assigned for the ranking.
For example:
"newbuild": {
    "me": {
        "type_of_tech_destination": "max",
        "tco": "min",
        "emissions_scope_1_2_delta": "min",
        "emissions_scope_3_upstream_delta": "min",
    }
indicates that for the newbuild rank, in the most_economic scenario, we favor building:
1. Higher tech type (i.e. more advanced tech)
2. Lower levelized cost of chemical
3. Lower scope 1/2 emissions
4. Lower scope 3 emissions
in that order!
"""

RANKING_CONFIG = {
    "greenfield": {
        "bau": {
            "tco": 1.0,
            "emissions": 0.0,
        },
        "fa": {
            "tco": 0.0,
            "emissions": 1.0,
        },
        "lc": {
            "tco": 0.8,
            "emissions": 0.2,
        },
    },
    "brownfield": {
        "bau": {
            "tco": 1.0,
            "emissions": 0.0,
        },
        "fa": {
            "tco": 0.0,
            "emissions": 1.0,
        },
        "lc": {
            "tco": 0.8,
            "emissions": 0.2,
        },
    },
    "decommission": {
        "bau": {
            "tco": 1,
            "emissions": 0,
        },
        "fa": {
            "tco": 0.0,
            "emissions": 1.0,
        },
        "lc": {
            "tco": 0.8,
            "emissions": 0.2,
        },
    },
}

### CONSTRAINTS ###

# TODO: placeholder for external input
REGIONAL_PRODUCTION_SHARE = {
    "Africa": 0.3,
    "China": 0.3,
    "Europe": 0.3,
    "India": 0.3,
    "Latin America": 0.3,
    "Middle East": 0.3,
    "North America": 0.3,
    "Oceania": 0.3,
    "Russia": 0.3,
}

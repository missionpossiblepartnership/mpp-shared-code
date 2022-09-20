"""Configuration file for the library."""
import logging

import numpy as np

### LOGGER ####
LOG_LEVEL = "DEBUG"
LOG_FORMATTER = logging.Formatter(
    "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)

### SECTOR CHOICE ###

EMISSION_SCOPES_DEFAULT = [
    "scope1",
    "scope2",
]

### DATA IMPORT AND EXPORT
CORE_DATA_PATH = "data"
LOG_PATH = "logs/"
SOLVER_INPUT_DATA_PATH = f"{CORE_DATA_PATH}/solver_input_data"


# Naming of solver input tables
SOLVER_INPUT_TABLES = [
    "technology_switches",
    "emissions",
    "initial_state",
    "technology_characteristics",
    "demand",
]

# Capacity utilisation factor thresholds
CUF_LOWER_THRESHOLD = 0.6
CUF_UPPER_THRESHOLD = 0.95
COST_METRIC_CUF_ADJUSTMENT = {
    "ammonia": "mc",  # marginal cost of production
    "aluminium": "lcox",  # levelized cost of production
    "cement": "lcox",  # levelized cost of production
}

# Scope of the model run - to be specified
MODEL_SCOPE = "Global"

### SECTOR-SPECIFIC PARAMETERS ###

# Products produced by each sector
PRODUCTS = {
    "ammonia": ["Ammonia", "Ammonium nitrate", "Urea"],
    "aluminium": ["Aluminium"],
    "cement": ["Clinker"],
}


MAP_LOW_COST_POWER_REGIONS = {
    "ammonia": {
        "Middle East": "Saudi Arabia",
        "Africa": "Namibia",
        "Oceania": "Australia",
        "Latin America": "Brazil",
    },
    "aluminium": None,
    "cement": None,
}


SECTORAL_CARBON_BUDGETS = {
    "aluminium": 11,
    # "cement": 42,
    "ammonia": 32,
    # "steel": 56,
    # "aviation": 17,
    # "shipping": 16,
    # "trucking": 36,
}

residual_share = 0.05
emissions_chemicals_2020 = 0.62  # Gt CO2 (scope 1 and 2)

HYDRO_TECHNOLOGY_BAN = {"aluminium": True, "ammonia": False, "cement": False}

### OUTPUTS PROCESSING ###

# Ratios for calculating electrolysis capacity
H2_PER_AMMONIA = 0.176471
AMMONIA_PER_UREA = 0.565724
AMMONIA_PER_AMMONIUM_NITRATE = 0.425534

# the below is needed after code refactoring!
IDX_TECH_RANKING_COLUMNS = [
    "product",
    "year",
    "region",
    "technology_origin",
    "technology_destination",
    "switch_type",
]

# index for emissivity data
IDX_EMISSIVITY = ["product", "year", "region", "technology"]

# index for technology characteristics
IDX_TECH_CHARACTERISTICS = ["product", "year", "region", "technology"]

# Renaming of columns to follow naming convention
MAP_COLUMN_NAMES = {
    "Unit": "unit",
    "Product": "product",
    "Technology": "technology_destination",
    "Technology origin": "technology_origin",
    "Renovation from": "technology_origin",
    "Region": "region",
    "Metric": "metric",
    "Scope": "scope",
    "Cost classification": "cost_classification",
    "Emissivity type": "emissivity_type",
}

# GHG conversion factors from any GHG to CO2e (structure required for conversion to dataframe!)
GHG_CONVERSION = {
    "emissivity_co2": 1.0,
    "emissivity_ch4": 29.8,
}

# technology classifications
TECH_CLASSIFICATIONS = {
    "initial": "Initial",
    "transition": "Transition",
    "end-state": "End-state",
}

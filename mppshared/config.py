"""Configuration file for the library."""
import logging
from pickle import FALSE

import numpy as np

### LOGGER ####
LOG_LEVEL = "DEBUG"
LOG_FORMATTER = logging.Formatter(
    "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)

### SECTOR CHOICE ###
SECTOR = "ammonia"
# SECTOR = "aluminium"
PATHWAYS = [
    "bau",
    # "fa",
    # "lc",
    # "cc",
]

SCOPES_CO2_COST = [
    "scope1",
    "scope2",
]

### RUN CONFIGURATION ###

RUN_PARALLEL = False

APPLY_CARBON_COST = True

run_config = {
    "IMPORT_DATA",
    "CALCULATE_VARIABLES",
    "APPLY_IMPLICIT_FORCING",
    "MAKE_RANKINGS",
    "SIMULATE_PATHWAY",
    "CALCULATE_OUTPUTS",
    "CREATE_DEBUGGING_OUTPUTS",
    # "EXPORT_OUTPUTS",
    # "PLOT_AVAILABILITIES"
    # "MERGE_OUTPUTS"
}

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


### MODEL DECISION PARAMETERS ###
START_YEAR = 2020
END_YEAR = 2050
MODEL_YEARS = np.arange(START_YEAR, END_YEAR + 1)

# (Artificial) investment cycles after which plants can be rebuilt and decommissioned
INVESTMENT_CYCLES = {
    "ammonia": 20,  # years
    "aluminium": 10,
}

# Emissions
GHGS = [
    "co2",
]  # "ch4", "n2o"]

# Emission scopes included in data analysis
EMISSION_SCOPES = ["scope1", "scope2", "scope3_upstream", "scope3_downstream"]

# Capacity utilisation factor thresholds
# TODO: make sector-specific with dictionary
CUF_LOWER_THRESHOLD = 0.6
CUF_UPPER_THRESHOLD = 0.95
COST_METRIC_CUF_ADJUSTMENT = {
    "ammonia": "mc",  # marginal cost of production
    "aluminium": "lcox",  # levelized cost of production
}

# TODO: Add more decomissioning rates
DECOMMISSION_RATES = {
    "PDH": 0.1,
}

# Scope of the model run - to be specified
MODEL_SCOPE = "Global"

# Override asset parameters; annual production capacity in Mt/year
ASSUMED_ANNUAL_PRODUCTION_CAPACITY = 1


# Sensitivities: low fossil prices, constrained CCS, BAU demand, low demand
ALL_SENSITIVITIES = [
    "def",
    "Carbon Price_0.2",
    "Carbon Price_-0.2",
    "Coal Price_0.2",
    "Coal Price_-0.2",
    "Grid and PPA Prices_0.2",
    "Grid and PPA Prices_-0.2",
    "Hydrogen Price_0.2",
    "Hydrogen Price_-0.2",
    "Natural Gas Price_0.2",
    "Natural Gas Price_-0.2",
]
SENSITIVITIES = {
    "bau": ["def"],  # ALL_SENSITIVITIES,
    # "cc": ["def"],  # ALL_SENSITIVITIES,
    # "fa": ["def"],
    # "lc": ALL_SENSITIVITIES,
}
### SECTOR-SPECIFIC PARAMETERS ###

# Products produced by each sector
PRODUCTS = {
    "ammonia": ["Ammonia", "Ammonium nitrate", "Urea"],
    "aluminium": ["Aluminium"],
}

OUTPUT_WRITE_PATH = {
    "ammonia": "C:/Users/JohannesWuellenweber/SYSTEMIQ Ltd/MPP Materials - 1. Ammonia/01_Work Programme/3_Data/4_Model results/Current model outputs",
    # "aluminium": f"/mnt/c/Users/LuisNatera/SYSTEMIQ Ltd/MPP Materials - Aluminum/04_WS1 - Sector Transition Strategy/04_Model/Model_Outputs/Latest_Runs/{PRODUCTS['aluminium'][0]}",
    "aluminium": "aluminium/data/outputs",
}
# Specify whether sector uses region-specific or asset-specific data for initial asset stack
INITIAL_ASSET_DATA_LEVEL = {"ammonia": "regional", "aluminium": "individual_assets"}

### RANKING ###
NUMBER_OF_BINS_RANKING = {"ammonia": 50, "aluminium": 50}
COST_METRIC_RELATIVE_UNCERTAINTY = {"ammonia": 0.1, "aluminium": 0.1}

# GHGs and Emission scopes included in weighting when ranking technology transitions
GHGS_RANKING = {"ammonia": ["co2"], "aluminium": ["co2"]}
EMISSION_SCOPES_RANKING = {
    "ammonia": ["scope1", "scope2"],
    "aluminium": ["scope1", "scope2", "scope3_upstream", "scope3_downstream"],
}

# Cost metric for ranking
RANKING_COST_METRIC = {"ammonia": "lcox", "aluminium": "tco"}

# Methodology for binning can be "uncertainty", "uncertainty_bins" or "histogram"
BIN_METHODOLOGY = {"ammonia": "uncertainty_bins", "aluminium": "histogram"}

TRANSITION_TYPES = [
    "decommission",
    "greenfield",
    "brownfield_renovation",
    "brownfield_newbuild",
]

# TODO: add decommission for chemicals
RANK_TYPES = {
    "ammonia": ["decommission", "greenfield", "brownfield"],
    "aluminium": ["decommission", "greenfield", "brownfield"],
}

MAP_LOW_COST_POWER_REGIONS = {
    "ammonia": {
        "Middle East": "Saudi Arabia",
        "Africa": "Namibia",
        "Oceania": "Australia",
        "Latin America": "Brazil",
    },
    "aluminium": None,
}

# Carbon cost parameters

INITIAL_CARBON_COST = 50
FINAL_CARBON_COST = 250

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
lc_weight_cost = 1.0
lc_weight_emissions = 0.0
fa_weight_cost = 0.0
fa_weight_emissions = 1.0
RANKING_CONFIG = {
    "ammonia": {
        "greenfield": {
            "bau": {
                "cost": 1.0,
                "emissions": 0.0,
            },
            "fa": {
                "cost": fa_weight_cost,
                "emissions": fa_weight_emissions,
            },
            "lc": {
                "cost": lc_weight_cost,
                "emissions": lc_weight_emissions,
            },
        },
        "brownfield": {
            "bau": {
                "cost": 1.0,
                "emissions": 0.0,
            },
            "fa": {
                "cost": fa_weight_cost,
                "emissions": fa_weight_emissions,
            },
            "lc": {
                "cost": lc_weight_cost,
                "emissions": lc_weight_emissions,
            },
        },
        "decommission": {
            "bau": {
                "cost": 1,
                "emissions": 0,
            },
            "fa": {
                "cost": fa_weight_cost,
                "emissions": fa_weight_emissions,
            },
            "lc": {
                "cost": lc_weight_cost,
                "emissions": lc_weight_emissions,
            },
        },
    },
    "aluminium": {
        "greenfield": {
            "bau": {
                "cost": 1.0,
                "emissions": 0.0,
            },
            "fa": {
                "cost": 0.0,
                "emissions": 1.0,
            },
            "lc": {
                "cost": lc_weight_cost,
                "emissions": lc_weight_emissions,
            },
            "cc": {
                "cost": 1.0,
                "emissions": 0.0,
            },
        },
        "brownfield": {
            "bau": {
                "cost": 1.0,
                "emissions": 0.0,
            },
            "fa": {
                "cost": 0.0,
                "emissions": 1.0,
            },
            "lc": {
                "cost": lc_weight_cost,
                "emissions": lc_weight_emissions,
            },
            "cc": {
                "cost": 1.0,
                "emissions": 0.0,
            },
        },
        "decommission": {
            "bau": {
                "cost": 1,
                "emissions": 0,
            },
            "fa": {
                "cost": 0.0,
                "emissions": 1.0,
            },
            "lc": {
                "cost": lc_weight_cost,
                "emissions": lc_weight_emissions,
            },
            "cc": {
                "cost": 1.0,
                "emissions": 0.0,
            },
        },
    },
}

### CONSTRAINTS ###

# Technology ramp-up parameters
TECHNOLOGY_RAMP_UP_CONSTRAINTS = {
    "ammonia": {
        "maximum_asset_additions": 10,
        "maximum_capacity_growth_rate": 0.7,
        "years_rampup_phase": 5,
    },
    "aluminium": {
        "maximum_asset_additions": 6,  # 10
        "maximum_capacity_growth_rate": 0.5,  # 0.25
        "years_rampup_phase": 8,  # 5
    },
}

# Year from which newbuild capacity has to fulfill the 2050 emissions constraint
YEAR_2050_EMISSIONS_CONSTRAINT = {"ammonia": 2050, "aluminium": 2050}

# Share of assets renovated annually (limits number of brownfield transitions)
ANNUAL_RENOVATION_SHARE = {"ammonia": 0.05, "aluminium": 0.2}

# Regions with and without geological storage (salt caverns)
REGIONS_SALT_CAVERN_AVAILABILITY = {
    "ammonia": {
        "Africa": "yes",  # suggest no
        "China": "yes",  # suggest no
        "Europe": "yes",
        "India": "no",
        "Latin America": "yes",  # suggest no
        "Middle East": "yes",
        "North America": "yes",
        "Oceania": "yes",
        "Russia": "yes",
        "Rest of Asia": "yes",
    }
}

# Share of demand in each region that needs to be fulfilled by production in that region
REGIONAL_PRODUCTION_SHARES = {
    "ammonia": {
        "Africa": 0.4,
        "China": 0.4,
        "Europe": 0.4,
        "India": 0.4,
        "Latin America": 0.4,
        "Middle East": 0.4,
        "North America": 0.4,
        "Oceania": 0.4,
        "Russia": 0.4,
        "Rest of Asia": 0.4,
    },
    "aluminium": {
        "China - North": 0.3,
        "China - North West": 0.3,
        "China - North East": 0.3,
        "China - Central": 0.3,
        "China - South": 0.3,
        "China - East": 0.3,
        "Rest of Asia": 0.3,
        "North America": 0.3,
        "Russia": 0.3,
        "Rest of Europe": 0.3,
        "Middle East": 0.3,
        "Africa": 0.3,
        "South America": 0.3,
        "Oceania": 0.3,
        "Canada": 0.3,
        "Scandinavia": 0.3,
        "US": 0.3,
    },
}


# Sectoral carbon budget (scope 1 and 2 CO2 emissions, in GtCO2)
# Carbon budget sector CSV flag, if True reads in the specific carbon budget for the sector in a CSV
CARBON_BUDGET_SECTOR_CSV = {
    "aluminium": True,
    # "cement": False,
    "ammonia": False,
    # "steel": False,
    # "aviation": False,
    # "shipping": False,
    # "trucking": False,
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

SECTORAL_PATHWAYS = {
    "ammonia": {
        "emissions_start": emissions_chemicals_2020,
        "emissions_end": residual_share * emissions_chemicals_2020,
        "action_start": 2023,
    },
    "aluminium": {
        "emissions_start": emissions_chemicals_2020,
        "emissions_end": residual_share * emissions_chemicals_2020,
        "action_start": 2023,
    },
}

# Year from which newbuild capacity must have transition or end-state technology
TECHNOLOGY_MORATORIUM = {
    "ammonia": 2020,
    "aluminium": 2030,
}
# Control for how many years is allowed to use transition technologies once the moratorium is enable
TRANSITIONAL_PERIOD_YEARS = {"ammonia": 30, "aluminium": 20}

# Regional ban of technologies (sector-specific)
REGIONAL_TECHNOLOGY_BAN = {
    "ammonia": {
        "China": [
            "Natural Gas SMR + ammonia synthesis",
            "Natural Gas ATR + CCS + ammonia synthesis",
            "Oversized ATR + CCS",
            "Natural Gas SMR + CCS (process emissions only) + ammonia synthesis",
            "Natural Gas SMR + CCS + ammonia synthesis",
            "Electrolyser + SMR + ammonia synthesis",
            "GHR + CCS + ammonia synthesis",
            "ESMR Gas + CCS + ammonia synthesis",
        ]
    },
    "aluminium": None,
}

HYDRO_TECHNOLOGY_BAN = {"aluminium": True, "ammonia": False}

### OUTPUTS PROCESSING ###

# Ratios for calculating electrolysis capacity
H2_PER_AMMONIA = 0.176471
AMMONIA_PER_UREA = 0.565724
AMMONIA_PER_AMMONIUM_NITRATE = 0.425534

# Global Warming Potentials for calculating CO2e
GWP = {
    "GWP-20": {"co2": 1, "ch4": 82.5, "n2o": 273},
    "GWP-100": {"co2": 1, "ch4": 29.8, "n2o": 273},
}

"""Configuration of the MPP Ammonia model."""
import logging
import numpy as np

### RUN CONFIGURATION ###
LOG_LEVEL = "DEBUG"
LOG_FORMATTER = logging.Formatter(
    "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)
RUN_PARALLEL = False
run_config = {
    # These steps can only be run sequentially (run_parallel = False)
    "IMPORT_DATA",
    "CALCULATE_VARIABLES",
    "SOLVER_INPUT",
    # These steps can optionally be run in parallel (run_parallel = False) for several carbon costs, pathways and sensitivities
    "APPLY_IMPLICIT_FORCING",
    "MAKE_RANKINGS",
    "SIMULATE_PATHWAY",
    "CALCULATE_OUTPUTS",
    "CALCULATE_DEBUGGING_OUTPUTS",
}  # comment lines to adjust run configuration

### OVERARCHING MODEL PARAMETERS ###
SECTOR = "ammonia"
MODEL_SCOPE = "Global"
INITIAL_ASSET_DATA_LEVEL = "regional"
START_YEAR = 2020
END_YEAR = 2050
MODEL_YEARS = np.arange(START_YEAR, END_YEAR + 1)
PRODUCTS = ["Ammonia", "Ammonium nitrate", "Urea"]

### PATHWAYS, SENSITIVITIES AND CARBON COSTS ###
PATHWAYS = [
    # "lc",
    # "fa",
    "bau",
]

SENSITIVITIES = [
    "def",
    # "ng_partial",
    # "ng_high",
    # "ng_low",
]

CARBON_COSTS = [
    0,
    # 50,
    # 100,
    # 150,
    # 200,
    # 250,
]

# Map each carbon cost to a year in which the final carbon cost is reached
END_YEAR_MAP = {0: 2025, 50: 2030, 100: 2035, 150: 2040, 200: 2045, 250: 2050}

### DATA IMPORT AND PREPROCESSING ###
# Data paths
CORE_DATA_PATH = "ammonia/data/"
PREPROCESS_DATA_PATH = f"{CORE_DATA_PATH}/preprocess"
LOG_PATH = "logs/"
IMPORT_DATA_PATH = CORE_DATA_PATH
INTERMEDIATE_DATA_PATH = f"{CORE_DATA_PATH}/intermediate_data"
SOLVER_INPUT_FOLDER = "solver_input_tables"
RAW_IMPORTS_FOLDER = "imports_raw"
PROCESSED_IMPORTS_FOLDER = "imports_processed"
CALCULATE_FOLDER = "calculate_variables"


# List of input sheets in Business Cases.xlsx (do not change order)
INPUT_SHEETS = [
    "Shared inputs - prices",
    "Shared inputs - emissions",
    "Business case OPEX & CAPEX",
    "Region CAPEX mapping",
    "Technology switching table",
    "Electrolyser CFs",
]

# Column ranges in Excel
EXCEL_COLUMN_RANGES = {
    "Business case OPEX & CAPEX": "B:AT",
    "Shared inputs - prices": "B:AR",
    "Shared inputs - emissions": "B:AT",
    "Region CAPEX mapping": "B:Z",
    "Technology switching table": "B:AA",
    "Electrolyser CFs": "B:AQ",
}

# Renaming of columns to follow naming convention
MAP_COLUMN_NAMES = {
    "Unit": "unit",
    "Product": "product",
    "Technology": "technology_destination",
    "Region": "region",
    "Metric": "name",
    "Scope": "scope",
    "Renovation from": "technology_origin",
    "Origin Technology": "technology_origin",
    "Low/High/Standard": "cost_classification",
    "Emissivity type": "emissivity_type",
    "Scenario": "scenario",
}

# Order of columns
COLUMN_ORDER = ["product", "technology", "year", "region"]

# Names of DataFrames created from imported data, indexed by sheet name in Business Cases.xlsx
INPUT_METRICS = {
    "Business case OPEX & CAPEX": [
        "capex",
        "opex_fixed",
        "wacc",
        "capacity_factor",
        "lifetime",
        "trl_current",
        "expected_maturity",
        "classification",
        "inputs_material",
        "inputs_energy",
        "h2_storage",
        "capture_rates",
    ],
    "Shared inputs - prices": ["prices"],
    "Shared inputs - emissions": [
        "emission_factors_co2",
        "emission_factors_n2o",
        "emission_factors_ch4",
    ],
    "Electrolyser CFs": [
        "electrolyser_cfs",
        "electrolyser_proportions",
        "electrolyser_efficiencies",
    ],
}

# DataFrames are extracted based on columns ["Metric type", "Metric"] in Business Cases.xlsx
MAP_EXCEL_NAMES = {
    "capex": ["Capex", None],
    "opex_fixed": ["Opex", "Fixed Opex"],
    "wacc": ["WACC", "Real WACC"],
    "capacity_factor": ["CF", "Capacity factor"],
    "lifetime": ["Lifetime", "Lifetime"],
    "trl_current": ["TRL", "Current TRL"],
    "expected_maturity": ["TRL", "Expected maturity (TRL>=8)"],
    "classification": ["Classification", "Technology classification"],
    "inputs_material": ["Raw material", None],
    "inputs_energy": ["Energy", None],
    "h2_storage": ["H2 storage", None],
    "prices": ["Commodity prices", None],
    "emission_factors_co2": ["CO2 Emissivity", None],
    "emission_factors_n2o": ["N2O Emissivity", None],
    "emission_factors_ch4": ["CH4 Emissivity", None],
    "capture_rates": ["CCS", None],
    "electrolyser_cfs": ["Capacity factor", "Electrolyser capacity factor"],
    "electrolyser_proportions": [
        "Proportion of H2 produced via electrolysis",
        "Proportion of H2 produced via electrolysis",
    ],
    "electrolyser_efficiencies": ["Efficiency", "Electrolyser efficiency"],
}

# Columns to use from Business Cases.xlsx for each DataFrame in addition to MODEL_YEARS
standard_cols = ["Product", "Technology", "Region", "Unit"]
emission_cols = [
    "Product",
    "Region",
    "Scope",
    "Scenario",
    "Emissivity type",
    "Unit",
    "Metric",
]
MAP_FIELDS_TO_DF_NAME = {
    "capex": standard_cols + ["Renovation from", "Low/High/Standard", "Metric"],
    "opex_fixed": standard_cols + ["Low/High/Standard"],
    "wacc": standard_cols,
    "capacity_factor": standard_cols,
    "lifetime": standard_cols,
    "trl_current": standard_cols,
    "expected_maturity": standard_cols,
    "classification": standard_cols,
    "inputs_material": standard_cols + ["Metric"],
    "inputs_energy": standard_cols + ["Metric"],
    "h2_storage": standard_cols + ["Metric"],
    "prices": ["Product", "Region", "Unit", "Metric"],
    "emission_factors_co2": emission_cols,
    "emission_factors_n2o": emission_cols,
    "emission_factors_ch4": emission_cols,
    "capture_rates": standard_cols + ["Metric"],
    "electrolyser_cfs": standard_cols + ["Metric"],
    "electrolyser_proportions": standard_cols + ["Metric"],
    "electrolyser_efficiencies": standard_cols + ["Metric"],
}

# Metric names for reformatting to long format
METRIC_NAMES = {
    "capex": "switching_capex",
    "opex_fixed": "opex_fixed",
    "wacc": "wacc",
    "capacity_factor": "capacity_factor",
    "lifetime": "lifetime",
    "trl_current": "trl_current",
    "expected_maturity": "expected_maturity",
    "classification": "classification",
    "inputs_material": "input_material",
    "inputs_energy": "input_energy",
    "h2_storage": "h2_storage",
    "prices": "price",
    "emission_factors_co2": "emission_factor_co2",
    "emission_factors_n2o": "emission_factor_n2o",
    "emission_factors_ch4": "emission_factor_ch4",
    "capture_rates": "capture_rate",
    "electrolyser_cfs": "electrolyser_capacity_factor",
    "electrolyser_proportions": "electrolyser_hydrogen_proportion",
    "electrolyser_efficiencies": "electrolyser_efficiency",
}

# Types of switches
SWITCH_TYPES = [
    "brownfield_renovation",
    "brownfield_rebuild",
    "greenfield",
    "decommission",
]

MAP_SWITCH_TYPES_TO_CAPEX = {
    "greenfield": "Greenfield Capex",
    "brownfield_rebuild": "Greenfield Capex",  # assumed identical
    "brownfield_renovation": "Renovation Capex",
    "decommission": "Decommission Capex",  # assumed zero
}

# Map Low-cost power regions to overall regions
LCPR_MAP = {
    "Latin America": "Brazil",
    "Middle East": "Saudi Arabia",
    "Africa": "Namibia",
    "Oceania": "Australia",
}

# Common index for pivot table concatenation
COMMON_INDEX = ["product", "technology_destination", "year", "region"]

# Cost DataFrame MultiIndex
COST_DF_INDEX = [
    "product",
    "technology_destination",
    "year",
    "region",
    "technology_origin",
    "type",
]

### CALCULATION OF COST AND EMISSION METRICS ###
# Decide whether CO2 emission from urea production are allocated to scope 1 or scope 3 downstream
UREA_CO2_EMISSIONS_TO_SCOPE1 = True

# Year from which DAC is mandatory for fossil-based urea production
UREA_YEAR_MANDATORY_DAC = 2050

# Set whether DAC should be priced or not
INCLUDE_DAC_IN_COST = True

# Naming of CCS cost components
CCS_COST_COMPONENTS = ["CCS - Transport", "CCS - Storage"]

# Cost components for showing LCOX and TCO composition
COST_COMPONENTS = [
    "energy_electricity",
    "energy_non_electricity",
    "raw_material_total",
    "h2_storage_total",
    "ccs",
    "opex_fixed",
    "switch_capex",
    "total",
]

GROUPING_COLS_FOR_NPV = [
    "product",
    "technology_origin",
    "region",
    "switch_type",
    "technology_destination",
]

SCOPES_CO2_COST = ["scope1", "scope2", "scope3_upstream"]

GHGS = ["co2", "n2o", "ch4"]

### ARCHETYPE PLANT ASSUMPTIONS ###
# Ratios for calculating electrolysis capacity
H2_PER_AMMONIA = 0.176471
AMMONIA_PER_UREA = 0.565724
AMMONIA_PER_AMMONIUM_NITRATE = 0.425534

# Archetypal plant capacities
ammonia_typical_plant_capacity_Mt = (2000 * 365) / 1e6

ASSUMED_ANNUAL_PRODUCTION_CAPACITY_MT = {
    "Ammonia": ammonia_typical_plant_capacity_Mt,
    "Urea": ammonia_typical_plant_capacity_Mt / AMMONIA_PER_UREA,
    "Ammonium nitrate": ammonia_typical_plant_capacity_Mt
    / AMMONIA_PER_AMMONIUM_NITRATE,
    "Aluminium": 1,
}

STANDARD_CUF = 0.95
STANDARD_LIFETIME = 30  # years
STANDARD_WACC = 0.08

### RANKING OF TECHNOLOGY SWITCHES ###
RANKING_COST_METRIC = "lcox"
COST_METRIC_RELATIVE_UNCERTAINTY = 0.05
GHGS_RANKING = ["co2"]
EMISSION_SCOPES_RANKING = ["scope1", "scope2", "scope3_upstream"]

# Emission scopes included in data analysis
EMISSION_SCOPES = ["scope1", "scope2", "scope3_upstream", "scope3_downstream"]

# List to define the columns that the ranking will groupby and create a separate ranking for
UNCERTAINTY_RANKING_GROUPS = ["year"]

TRANSITION_TYPES = [
    "decommission",
    "greenfield",
    "brownfield_renovation",
    "brownfield_newbuild",
]

RANK_TYPES = ["decommission", "greenfield", "brownfield"]

# Ranking configuration depends on type of technology switch and pathway
lc_weight_cost = 0.8
lc_weight_emissions = 1 - lc_weight_cost
fa_weight_cost = 0.01
fa_weight_emissions = 1 - fa_weight_cost
RANKING_CONFIG = {
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
}

### CONSTRAINTS ###
# Integrate current project pipeline or not
BUILD_CURRENT_PROJECT_PIPELINE = True

# Delays for brownfield transitions to make the model more realistic
BROWNFIELD_RENOVATION_START_YEAR = 2025  # means retrofit plants come online in 2026
BROWNFIELD_REBUILD_START_YEAR = 2027  # means rebuild plants come online in 2028

TECHNOLOGIES_NOT_FOR_SOLVER = ["Waste to ammonia", "Waste Water to ammonium nitrate"]

REGIONAL_PRODUCTION_SHARES = {
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
}

MAP_LOW_COST_POWER_REGIONS = {
    "Middle East": "Saudi Arabia",
    "Africa": "Namibia",
    "Oceania": "Australia",
    "Latin America": "Brazil",
}

# Regions where geological H2 storage is not allowed because no salt caverns are available
REGIONS_SALT_CAVERN_AVAILABILITY = {
    "Africa": "yes",
    "China": "yes",
    "Europe": "yes",
    "India": "no",
    "Latin America": "yes",
    "Middle East": "yes",
    "North America": "yes",
    "Oceania": "yes",
    "Russia": "yes",
    "Rest of Asia": "yes",
}

# List of regions
REGIONS = [
    "Africa",
    "China",
    "Europe",
    "India",
    "Latin America",
    "Middle East",
    "North America",
    "Oceania",
    "Russia",
    "Rest of Asia",
    "Brazil",
    "Australia",
    "Namibia",
    "Saudi Arabia",
]

# Maximum share of global demand that can be supplied by one region
MAXIMUM_GLOBAL_DEMAND_SHARE_ONE_REGION = 0.3

# For less mature technologies, limit the technology's share in global demand
TECHNOLOGIES_MAXIMUM_GLOBAL_DEMAND_SHARE = [
    "Biomass Gasification + ammonia synthesis",
    "Biomass Digestion + ammonia synthesis",
    "Methane Pyrolysis + ammonia synthesis",
]
MAXIMUM_GLOBAL_DEMAND_SHARE = {
    2020: 0.02,
    2021: 0.02,
    2022: 0.02,
    2023: 0.02,
    2024: 0.02,
    2025: 0.02,
    2026: 0.02,
    2027: 0.02,
    2028: 0.02,
    2029: 0.02,
    2030: 0.02,
    2031: 0.02,
    2032: 0.02,
    2033: 0.02,
    2034: 0.02,
    2035: 0.02,
    2036: 0.02,
    2037: 0.02,
    2038: 0.02,
    2039: 0.02,
    2040: 0.02,
    2041: 1,
    2042: 1,
    2043: 1,
    2044: 1,
    2045: 1,
    2046: 1,
    2047: 1,
    2048: 1,
    2049: 1,
    2050: 1,
}

# Year from which newbuild capacity must have transition or end-state technology
TECHNOLOGY_MORATORIUM = 2050

# Duration for which transition technologies are still allowed after the technology moratorium comes into force
TRANSITIONAL_PERIOD_YEARS = 30

SET_CO2_STORAGE_CONSTRAINT = True
CO2_STORAGE_CONSTRAINT_CUMULATIVE = False
CUF_LOWER_THRESHOLD = 0.5
CUF_UPPER_THRESHOLD = 0.95
INVESTMENT_CYCLE = 20  # years

CONSTRAINTS_TO_APPLY = {
    "bau": ["co2_storage_constraint"],
    "lc": [
        "co2_storage_constraint",
        "electrolysis_capacity_addition_constraint",
        "demand_share_constraint",
    ],
    "fa": ["co2_storage_constraint"],
}

# Share of assets renovated annually (limits number of brownfield transitions)
ANNUAL_RENOVATION_SHARE = 0.05

# Increase in cost metric required to enact a brownfield renovation or brownfield rebuild transition
COST_METRIC_DECREASE_BROWNFIELD = 0.05

# Regional ban of technologies (sector-specific)
REGIONAL_TECHNOLOGY_BAN = {
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
}

### OUTPUTS PROCESSING ###
# Demand driver circularity in pathway or not
CIRCULARITY_IN_DEMAND = {"bau": False, "fa": True, "lc": False}

# Global Warming Potentials for calculating CO2e
GWP = {
    "GWP-20": {"co2": 1, "ch4": 82.5, "n2o": 273},
    "GWP-100": {"co2": 1, "ch4": 29.8, "n2o": 273},
}

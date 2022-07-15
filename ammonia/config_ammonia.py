"""Configuration of the MPP Ammonia model."""
import logging

import numpy as np

SECTOR = "ammonia"

INITIAL_ASSET_DATA_LEVEL = "regional"

### RUN CONFIRGUATION ###
LOG_LEVEL = "DEBUG"
LOG_FORMATTER = logging.Formatter(
    "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)
RUN_PARALLEL = False
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
START_YEAR = 2020
END_YEAR = 2050
MODEL_YEARS = np.arange(START_YEAR, END_YEAR + 1)
PRODUCTS = ["Ammonia", "Ammonium nitrate", "Urea"]
# Override asset parameters; annual production capacity in Mt/year
ASSUMED_ANNUAL_PRODUCTION_CAPACITY = 1

### PATHWAYS, SENSITIVITIES AND CARBON COSTS ###
PATHWAYS = [
    "lc",
    # "fa",
    # "bau",
]

SENSITIVITIES = [
    "def",
    # "ng_partial",
    # "ng_high",
    # "ng_low",
]

CARBON_COSTS = [
    0,
    50,
    100,
    150,
    200,
    250,
]


### STANDARD ASSUMPTIONS FOR AMMOINA PLANTS ###
STANDARD_CUF = 0.95
STANDARD_LIFETIME = 30  # years
STANDARD_WACC = 0.08

### EMISSIONS CALCULATIONS ###
GHGS = ["co2", "n2o", "ch4"]

### COST CALCULATIONS ###
GROUPING_COLS_FOR_NPV = [
    "product",
    "technology_origin",
    "region",
    "switch_type",
    "technology_destination",
]

SCOPES_CO2_COST = ["scope1", "scope2", "scope3_upstream"]

### CONSTRAINTS ON POSSIBLE TECHNOLOGY SWITCHES ###

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

# Year from which newbuild capacity must have transition or end-state technology
TECHNOLOGY_MORATORIUM = 2020

# Duration for which transition technologies are still allowed after the technology moratorium comes into force
TRANSITIONAL_PERIOD_YEARS = 30

### RANKING OF TECHNOLOGY SWITCHES ###
RANKING_COST_METRIC = "lcox"
COST_METRIC_RELATIVE_UNCERTAINTY = 0.05
GHGS_RANKING = ["co2"]
EMISSION_SCOPES_RANKING = ["scope1", "scope2", "scope3_upstream"]

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
CUF_LOWER_THRESHOLD = 0.5
CUF_UPPER_THRESHOLD = 0.95
INVESTMENT_CYCLE = 20  # years
# Technology ramp-up parameters
TECHNOLOGY_RAMP_UP_CONSTRAINT = {
    "maximum_asset_additions": 10,
    "maximum_capacity_growth_rate": 0.7,
    "years_rampup_phase": 5,
}

CARBON_BUDGET_SECTOR_CSV = False
residual_share = 0.05
emissions_2020 = 0.62  # Gt CO2 (scope 1 and 2)

SECTORAL_CARBON_PATHWAY = {
    "emissions_start": emissions_2020,
    "emissions_end": residual_share * emissions_2020,
    "action_start": 2023,
}

"""Configuration of the MPP Ammonia model."""
import logging
import numpy as np

SECTOR = "ammonia"

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
PRODUCTS = ["Ammonia", "Ammonium nitrate", "Urea"]

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

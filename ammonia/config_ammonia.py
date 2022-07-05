"""Configuration of the MPP Ammonia model."""
import logging
import numpy as np

### LOGGER ###
LOG_LEVEL = "INFO"
LOG_FORMATTER = logging.Formatter(
    "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)

### SECTOR CHOICE ###
SECTOR = "ammonia"
# SECTOR = "aluminium"
PATHWAYS = [
    "lc",
    # "fa",
    # "bau",
]

# Sensitivities
SENSITIVITIES = [
    "def",
    # "ng_partial",
    # "ng_high",
    # "ng_low",
]

# Carbon price (for sensitivity analysis): needs to be run for 1 USD/tCO2 to create carbon_cost_addition.csv, then used for subsequent runs by multiplying accordingly

CARBON_COSTS = [
    # 0,
    50,
    100,
    150,
    200,
    250,
]
# CARBON_COSTS = [0]


# Scopes in CO2 price optimization
SCOPES_CO2_COST = [
    "scope1",
    "scope2",
    "scope3_upstream",
    # "scope3_downstream"
]

START_YEAR = 2020
END_YEAR = 2050
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

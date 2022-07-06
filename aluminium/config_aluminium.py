import numpy as np

SECTOR = "aluminium"

PATHWAYS = [
    "bau",
    "fa",
    "lc",
    "cc",
]

SCOPES_CO2_COST = [
    "scope1",
    "scope2",
]

### RUN CONFIGURATION ###

RUN_PARALLEL = False
APPLY_CARBON_COST = True

### MODEL DECISION PARAMETERS ###
START_YEAR = 2020
END_YEAR = 2050
MODEL_YEARS = np.arange(START_YEAR, END_YEAR + 1)

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

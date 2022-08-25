import numpy as np

SECTOR = "cement"
PRODUCTS = ["Clinker"]

SCOPES_CO2_COST = [
    "scope1",
    "scope2",
]

### RUN CONFIGURATION ###
run_config = {
    "IMPORT_DATA",
    "CALCULATE_VARIABLES",
    "APPLY_IMPLICIT_FORCING",
    "MAKE_RANKINGS",
    "SIMULATE_PATHWAY",
    "CALCULATE_OUTPUTS",
    # "CREATE_DEBUGGING_OUTPUTS",
    # "EXPORT_OUTPUTS",
    # "PLOT_AVAILABILITIES"
    # "MERGE_OUTPUTS"
}
RUN_PARALLEL = False
LOG_LEVEL = "DEBUG"
MODEL_SCOPE = "Global"
COMPUTE_LCOX = False

### MODEL DECISION PARAMETERS ###
START_YEAR = 2020
END_YEAR = 2050
MODEL_YEARS = np.arange(START_YEAR, END_YEAR + 1)

PATHWAYS_SENSITIVITIES = {
    # "bau": ["def"],  # ALL_SENSITIVITIES,
    # "fa": ["def"],
    "lc": ["def"],  # ALL_SENSITIVITIES,
}

PATHWAYS_WITH_TECHNOLOGY_MORATORIUM = ["lc"]

# carbon cost scenarios: carbon cost in USD as key and the year in which the carbon cost stops growing as value
CARBON_COST_SCENARIOS = {0: 2025, 50: 2030, 100: 2035, 150: 2040, 200: 2045, 250: 2050}
INVESTMENT_CYCLE = 10  # years
CAPACITY_UTILISATION_FACTOR = 0.913
COST_METRIC_CUF_ADJUSTMENT = None

# Share of assets renovated annually (limits number of brownfield transitions)
MAX_ANNUAL_RENOVATION_SHARE = 0.2


### initial asset stack ###
# Specify whether sector uses region-specific or asset-specific data for initial asset stack
INITIAL_ASSET_DATA_LEVEL = "individual_assets"

# Override asset parameters; annual production capacity in Mt/year
ASSUMED_ANNUAL_PRODUCTION_CAPACITY = 6000 * 365 * 1e-6

# Year from which newbuild capacity must have transition or end-state technology
TECHNOLOGY_MORATORIUM = 2035
# Control for how many years is allowed to use transition technologies once the moratorium is enabled
TRANSITIONAL_PERIOD_YEARS = 20
# Emission scopes included in ranking
EMISSION_SCOPES = ["scope1", "scope2", "scope3_upstream"]
# Emissions
GHGS = ["co2", "ch4", "co2e"]

REGIONS = [
    "China",
    "Rest of Asia",
    "North America",
    "Russia",
    "Europe",
    "India",
    "Middle East",
    "Africa",
    "Latin America",
    "Oceania",
]

# list of technologies
LIST_TECHNOLOGIES = [
    "Dry kiln reference plant",
    "Dry kiln coal",
    "Dry kiln natural gas",
    "Dry kiln alternative fuels 43%",
    "Dry kiln alternative fuels 90%",
    "Dry kiln coal + post combustion + storage",
    "Dry kiln natural gas + post combustion + storage",
    "Dry kiln alternative fuels + post combustion + storage",
    "Dry kiln coal + oxyfuel + storage",
    "Dry kiln natural gas + oxyfuel + storage",
    "Dry kiln alternative fuels + oxyfuel + storage",
    "Dry kiln coal + direct separation + storage",
    "Dry kiln natural gas + direct separation + storage",
    "Dry kiln alternative fuels + direct separation + storage",
    "Dry kiln coal + post combustion + usage",
    "Dry kiln natural gas + post combustion + usage",
    "Dry kiln alternative fuels + post combustion + usage",
    "Dry kiln coal + oxyfuel + usage",
    "Dry kiln natural gas + oxyfuel + usage",
    "Dry kiln alternative fuels + oxyfuel + usage",
    "Dry kiln coal + direct separation + usage",
    "Dry kiln natural gas + direct separation + usage",
    "Dry kiln alternative fuels + direct separation + usage",
]

### RANKING OF TECHNOLOGY SWITCHES ###
RANKING_COST_METRIC = "lcox"
BIN_METHODOLOGY = "uncertainty"  # options: "histogram" or "uncertainty"
COST_METRIC_RELATIVE_UNCERTAINTY = 0.2
# number of bins (only for histogram ranking)
NUMBER_OF_BINS_RANKING = 50
# GHGs considered in the ranking
GHGS_RANKING = ["co2e"]
# emission scopes considered in the ranking
EMISSION_SCOPES_RANKING = EMISSION_SCOPES
# list to define the columns that the ranking will groupby and create a separate ranking for
UNCERTAINTY_RANKING_GROUPS = ["year", "region", "opex_context"]

TRANSITION_TYPES = {
    "greenfield": "Greenfield",
    "brownfield_rebuild": "Brownfield rebuild",
    "brownfield_renovation": "Brownfield renovation",
    "decommission": "Decommission",
}

RANK_TYPES = ["decommission", "greenfield", "brownfield"]

# set of cost classifications
COST_CLASSIFICATIONS = {"low": "Low", "standard": "Standard", "high": "High"}

CARBON_BUDGET_SECTOR_CSV = False
CARBON_BUDGET_SHAPE = "linear"  # options: todo
# carbon budget 2020 - 2050 in Gt
# todo: why is this not being used?
SECTORAL_CARBON_BUDGETS = {
    "cement": 42,
}

residual_share = 0.05
emissions_2020 = 2.4  # Gt CO2 (scopes 1 and 2)
SECTORAL_CARBON_PATHWAY = {
    "emissions_start": emissions_2020,
    "emissions_end": residual_share * emissions_2020,
    "action_start": 2023,
}

# Ranking configuration depends on type of technology switch and pathway
lc_weight_cost = 1.0
lc_weight_emissions = 0.0
fa_weight_cost = 0.0
fa_weight_emissions = 1.0
RANKING_CONFIG = {
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
    },
}

### CONSTRAINTS ###
# todo: when this is set to None, it causes troubles...
YEAR_2050_EMISSIONS_CONSTRAINT = 2060
# Technology ramp-up parameters (on technology-level, only applies to transition and end-state techs!)
TECHNOLOGY_RAMP_UP_CONSTRAINT = {
    "maximum_asset_additions": 1000,  # set high such that is deactivated
    "maximum_capacity_growth_rate": 0.05,
    "years_rampup_phase": 10,
}
CONSTRAINTS_TO_APPLY = {
    "bau": [
        "rampup_constraint",
        # "regional_constraint",
        "natural_gas_constraint",
        "alternative_fuel_constraint",
    ],
    "fa": [
        # "emissions_constraint",
        "rampup_constraint",
        # "regional_constraint",
        "natural_gas_constraint",
        "alternative_fuel_constraint",
    ],
    "lc": [
        "emissions_constraint",
        "rampup_constraint",
        # "regional_constraint",
        "natural_gas_constraint",
        "alternative_fuel_constraint",
    ],
}
REGIONAL_PRODUCTION_SHARES = {
    "Africa": 1.0,
    "China": 1.0,
    "India": 1.0,
    "Europe": 1.0,
    "Latin America": 1.0,
    "Middle East": 1.0,
    "North America": 1.0,
    "Oceania": 1.0,
    "Rest of Asia": 1.0,
    "Russia": 1.0,
}
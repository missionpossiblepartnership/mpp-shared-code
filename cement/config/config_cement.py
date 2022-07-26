import numpy as np

SECTOR = "cement"
LOG_LEVEL = "DEBUG"
MODEL_SCOPE = "Global"

PATHWAYS = [
    "bau",
    "fa",
    "lc",
]

PATHWAYS_WITH_TECHNOLOGY_MORATORIUM = ["lc"]
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
    "CREATE_DEBUGGING_OUTPUTS",
    # "EXPORT_OUTPUTS",
    # "PLOT_AVAILABILITIES"
    # "MERGE_OUTPUTS"
}
RUN_PARALLEL = False
APPLY_CARBON_COST = True

### MODEL DECISION PARAMETERS ###
START_YEAR = 2020
END_YEAR = 2050
MODEL_YEARS = np.arange(START_YEAR, END_YEAR + 1)

# Sensitivities: low fossil prices, constrained CCS, BAU demand, low demand
ALL_SENSITIVITIES = [
    "def",
]
SENSITIVITIES = {
    # "bau": ["def"],  # ALL_SENSITIVITIES,
    # "fa": ["def"],
    "lc": ["def"]  # ALL_SENSITIVITIES,
}
INVESTMENT_CYCLE = 10  # years
CUF_LOWER_THRESHOLD = 0.6
CUF_UPPER_THRESHOLD = 0.95
COST_METRIC_CUF_ADJUSTMENT = None
# Products produced by each sector
PRODUCTS = ["Clinker"]

# Share of assets renovated annually (limits number of brownfield transitions)
ANNUAL_RENOVATION_SHARE = 0.2
# Specify whether sector uses region-specific or asset-specific data for initial asset stack
INITIAL_ASSET_DATA_LEVEL = "individual_assets"

# Override asset parameters; annual production capacity in Mt/year
ASSUMED_ANNUAL_PRODUCTION_CAPACITY = 1

# Year from which newbuild capacity must have transition or end-state technology
TECHNOLOGY_MORATORIUM = 2030
# Control for how many years is allowed to use transition technologies once the moratorium is enable
TRANSITIONAL_PERIOD_YEARS = 20
# Emission scopes included in data analysis
EMISSION_SCOPES = ["scope_1", "scope_2", "scope_3_upstream"]
# Emissions
GHGS = ["co2e"]

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
    "Dry kiln coal",
    "Dry kiln natural gas",
    "Dry kiln alternative fuels",
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
COST_METRIC_RELATIVE_UNCERTAINTY = 0.05
NUMBER_OF_BINS_RANKING = 50
GHGS_RANKING = ["co2e"]
EMISSION_SCOPES_RANKING = ["scope_1", "scope_2", "scope_3_upstream"]

TRANSITION_TYPES = {
    "greenfield": "Greenfield",
    "brownfield_rebuild": "Brownfield rebuild",
    "brownfield_renovation": "Brownfield renovation",
    "decommission": "Decommission",
}

RANK_TYPES = ["decommission", "greenfield", "brownfield"]

# set of cost classifications
COST_CLASSIFICATIONS = {"low": "Low", "standard": "Standard", "high": "High"}

CARBON_BUDGET_SECTOR_CSV = True
CARBON_BUDGET_SHAPE = "linear"  # options: todo

residual_share = 0.05
emissions_2020 = 0.62  # Gt CO2 (scope 1 and 2)
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
# Technology ramp-up parameters
TECHNOLOGY_RAMP_UP_CONSTRAINT = {
    "maximum_asset_additions": 6,  # 10
    "maximum_capacity_growth_rate": 0.5,  # 0.25
    "years_rampup_phase": 8,  # 5
}
CONSTRAINTS_TO_APPLY = {
    "bau": [None],
    "cc": [None],
    "lc": [None],
    "fa": [None],
}

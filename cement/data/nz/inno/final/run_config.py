import numpy as np

SECTOR = "cement"
PRODUCTS = ["Clinker"]

### RUN CONFIGURATION ###
run_config = {
    # MAIN MODEL #
    "IMPORT_DATA",
    "CALCULATE_VARIABLES",
    "APPLY_IMPLICIT_FORCING",
    "MAKE_RANKINGS",
    "SIMULATE_PATHWAY",
    "CALCULATE_OUTPUTS",

    # ARCHETYPE EXPLORER #
    "AE_IMPORT_DATA",
    "AE_CALCULATE_VARIABLES",
    "AE_APPLY_IMPLICIT_FORCING",
}
RUN_PARALLEL = False
LOG_LEVEL = "DEBUG"
MODEL_SCOPE = "Global"
COMPUTE_LCOX = True
# define CCU/S OPEX context dimensions.
#   IMPORTANT: Don't forget to add "opex_context" to UNCERTAINTY_RANKING_GROUPS if more than one dimension!
CCUS_CONTEXT = ["high_low"]

### MODEL DECISION PARAMETERS ###
START_YEAR = 2020
END_YEAR = 2050
MODEL_YEARS = np.arange(START_YEAR, END_YEAR + 1)

PATHWAYS_SENSITIVITIES = {
    # "bau": ["def"],
    # "fa": ["def"],
    # "lc": ["def"],
    # "nz": ["nz", "inno"],
    "nz": ["inno"],
    # "custom": ["decelerated"],
    # "archetype": ["000000"],
}

PATHWAYS_WITH_CARBON_COST = ["lc", "nz", "custom"]
PATHWAYS_WITH_TECHNOLOGY_MORATORIUM = ["lc", "nz"]

PATHWAY_DEMAND_SCENARIO_MAPPING = {
    "bau": "bau",
    "fa": "gcca-early",
    "lc": "gcca",
    "nz": "gcca",
    "custom": "gcca-late",
}

# carbon cost sensitivities: define carbon cost in USD/t CO2 for different sensitivities
CARBON_COST_SENSITIVITIES = {
    "low": {
        "trajectory": "linear",
        "initial_carbon_cost": 0,
        "final_carbon_cost": 30,
        "start_year": 2023,
        "end_year": 2050,
    },
    "def": {
        "trajectory": "linear",
        "initial_carbon_cost": 0,
        "final_carbon_cost": 100,
        "start_year": 2023,
        "end_year": 2050,
    },
    "high": {
        "trajectory": "linear",
        "initial_carbon_cost": 0,
        "final_carbon_cost": 210,
        "start_year": 2023,
        "end_year": 2050,
    },
    "decelerated": {
        "trajectory": "linear",
        "initial_carbon_cost": 0,
        "final_carbon_cost": 100,
        "start_year": 2030,
        "end_year": 2050,
    },
    "nz": {
        "trajectory": "linear",
        "initial_carbon_cost": 40,
        "final_carbon_cost": 100,
        "start_year": 2025,
        "end_year": 2050,
    },
    "inno": {
        "trajectory": "linear",
        "initial_carbon_cost": 40,
        "final_carbon_cost": 100,
        "start_year": 2025,
        "end_year": 2050,
    },
}
CARBON_COST_SCOPES = ["scope1", "scope2"]

INVESTMENT_CYCLE = 10  # years
CAPACITY_UTILISATION_FACTOR = 1.0
COST_METRIC_CUF_ADJUSTMENT = None

# Share of assets renovated annually (limits number of brownfield transitions)
MAX_ANNUAL_RENOVATION_SHARE = {
    "bau": 1.0,
    "fa": 1.0,
    "lc": 1.0,
    "nz": 1.0,
    "custom": 1.0,
}


### initial asset stack ###
# Specify whether sector uses region-specific or asset-specific data for initial asset stack
INITIAL_ASSET_DATA_LEVEL = "individual_assets"

# Override asset parameters; annual production capacity in Mt/year
ASSUMED_ANNUAL_PRODUCTION_CAPACITY = 2.0

# Year from which newbuild capacity must have transition or end-state technology
TECHNOLOGY_MORATORIUM = 2035
# Control for how many years is allowed to use transition technologies once the moratorium is enabled (irrelevant for
#   cement)
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
INNO_TECHS = [
    "Electric kiln + direct separation",
    "Dry kiln + Hydrogen + direct separation",
]
MATURE_TECHS = [
    "Dry kiln reference plant",
    "Dry kiln coal",
    "Dry kiln natural gas",
    "Dry kiln alternative fuels 43%",
    "Dry kiln alternative fuels 90%",
    "Dry kiln coal + post combustion + storage",
    "Dry kiln natural gas + post combustion + storage",
    "Dry kiln alternative fuels (43%) + post combustion + storage",
    "Dry kiln alternative fuels (90%) + post combustion + storage",
    "Dry kiln coal + oxyfuel + storage",
    "Dry kiln natural gas + oxyfuel + storage",
    "Dry kiln alternative fuels (43%) + oxyfuel + storage",
    "Dry kiln alternative fuels (90%) + oxyfuel + storage",
    "Dry kiln coal + direct separation + storage",
    "Dry kiln natural gas + direct separation + storage",
    "Dry kiln alternative fuels (43%) + direct separation + storage",
    "Dry kiln alternative fuels (90%) + direct separation + storage",
]
MATURE_CCU_TECHS = [
    "Dry kiln coal + post combustion + usage",
    "Dry kiln natural gas + post combustion + usage",
    "Dry kiln alternative fuels (43%) + post combustion + usage",
    "Dry kiln alternative fuels (90%) + post combustion + usage",
    "Dry kiln coal + oxyfuel + usage",
    "Dry kiln natural gas + oxyfuel + usage",
    "Dry kiln alternative fuels (43%) + oxyfuel + usage",
    "Dry kiln alternative fuels (90%) + oxyfuel + usage",
    "Dry kiln coal + direct separation + usage",
    "Dry kiln natural gas + direct separation + usage",
    "Dry kiln alternative fuels (43%) + direct separation + usage",
    "Dry kiln alternative fuels (90%) + direct separation + usage",
]
LIST_TECHNOLOGIES = {
    "low": MATURE_TECHS,
    "def": MATURE_TECHS,
    "high": MATURE_TECHS,
    "decelerated": MATURE_TECHS,
    "nz": MATURE_TECHS,
    "inno": (MATURE_TECHS + INNO_TECHS),
}
ALL_TECHNOLOGIES = MATURE_TECHS + MATURE_CCU_TECHS + INNO_TECHS

### RANKING OF TECHNOLOGY SWITCHES ###
RANKING_COST_METRIC = "lcox"
BIN_METHODOLOGY = "uncertainty"  # options: "histogram" or "uncertainty"
COST_METRIC_RELATIVE_UNCERTAINTY = 0.1
# number of bins (only for histogram ranking)
NUMBER_OF_BINS_RANKING = 50
# GHGs considered in the ranking
GHGS_RANKING = ["co2e"]
# emission scopes considered in the ranking
EMISSION_SCOPES_RANKING = EMISSION_SCOPES
# list to define the columns that the ranking will groupby and create a separate ranking for
UNCERTAINTY_RANKING_GROUPS = ["year", "region"]

TRANSITION_TYPES = {
    "greenfield": "Greenfield",
    "brownfield_rebuild": "Brownfield rebuild",
    "brownfield_renovation": "Brownfield renovation",
    "decommission": "Decommission",
}

RANK_TYPES = ["decommission", "greenfield", "brownfield"]

# set the switch types that will update an assets commissioning year
SWITCH_TYPES_UPDATE_YEAR_COMMISSIONED = ["brownfield_renovation", "brownfield_rebuild"]

# define regions that can have switches to natural gas
REGIONS_NATURAL_GAS = [
    "North America",
    "Russia",
    "Middle East",
    "Africa",
    "Latin America",
]

# set of cost classifications
COST_CLASSIFICATIONS = {"low": "Low", "standard": "Standard", "high": "High"}

CARBON_BUDGET_SECTOR_CSV = False
CARBON_BUDGET_SHAPE = "cement"  # linear, cement
# carbon budget 2020 - 2050 in Gt
SECTORAL_CARBON_BUDGETS = {
    "cement": 48.925,  # == 51.5 * 0.95 # todo: adjust when we have latest numbers from ECRA
}

emissions_2020 = 2.8  # Gt CO2 (scopes 1 and 2)
SECTORAL_CARBON_PATHWAY = {
    "emissions_start": emissions_2020,
    "emissions_end": 0.06 * 3.85 * 0.9,  # recarbonation GCCA roadmap
    "action_start": 2022,
}
RECARBONATION_SHARE = 0.105  # [t CO2 / t Clk]

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
        "nz": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "custom": {
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
        "nz": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "custom": {
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
        "nz": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "custom": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
    },
}

### CONSTRAINTS ###
# Technology ramp-up parameters (on global technology-level)
#   cf. technology_rampup.py for a documentation of different curve types
TECHNOLOGY_RAMP_UP_CURVE_TYPE = {  # "exponential" or "rayleigh"
    "bau": "exponential",
    "fa": "exponential",
    "lc": "exponential",
    "nz": "rayleigh",
    "custom": "exponential",
}
# define tech classifications to which ramp up applies to
RAMP_UP_TECH_CLASSIFICATIONS = ["initial", "end-state"]
TECHNOLOGY_RAMP_UP_CONSTRAINT = {
    "bau": {
        "init_maximum_asset_additions": 15,
        "maximum_asset_growth_rate": 0.01,
        "years_rampup_phase": 30,
    },
    "fa": {
        "init_maximum_asset_additions": 3,
        "maximum_asset_growth_rate": 0.05,
        "years_rampup_phase": 30,
    },
    "lc": {
        "init_maximum_asset_additions": 10,
        "maximum_asset_growth_rate": 0.05,
        "years_rampup_phase": 30,
    },
    "nz": {
        "init_maximum_asset_additions": 3,
        "maximum_asset_growth_rate": 3.25,
        "years_rampup_phase": 30,
    },
    "custom": {
        "init_maximum_asset_additions": 5,
        "maximum_asset_growth_rate": 0.05,
        "years_rampup_phase": 30,
    },
}
# CO2 storage constraint
SET_CO2_STORAGE_CONSTRAINT = True
CO2_STORAGE_CONSTRAINT_TYPE = "total_cumulative"  # "annual_cumulative", "annual_addition", "total_cumulative", or None

# define the market entry of alternative fuels 90% and CCU/S techs
MARKET_ENTRY_AF_90 = 2025
MARKET_ENTRY_CCUS = 2025

# define whether constraints shall only checked regionally (if applicable) to reduce runtime
CONSTRAINTS_REGIONAL_CHECK = True

# define which constraints will be applied for every pathway
CONSTRAINTS_TO_APPLY = {
    "bau": [
        "rampup_constraint",
        # "regional_constraint",
        "biomass_constraint",
        # "co2_storage_constraint",
    ],
    "fa": [
        # "emissions_constraint",
        "rampup_constraint",
        # "regional_constraint",
        "biomass_constraint",
        "co2_storage_constraint",
    ],
    "lc": [
        # "emissions_constraint",
        "rampup_constraint",
        # "regional_constraint",
        "biomass_constraint",
        "co2_storage_constraint",
    ],
    "nz": [
        # "emissions_constraint",
        "rampup_constraint",
        # "regional_constraint",
        "biomass_constraint",
        "co2_storage_constraint",
    ],
    "custom": [
        # "emissions_constraint",
        "rampup_constraint",
        # "regional_constraint",
        "biomass_constraint",
        "co2_storage_constraint",
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

### Unit conversions ###
# Coal: GJ to t
COAL_GJ_T = 0.034120842375357
# Natural gas: GJ to billion cubic meter
NATURAL_GAS_GJ_BCM = 1 / (38.2 * 1e6)
# Electricity: GJ to TWh
ELECTRICITY_GJ_TWH = 1 / (3.6 * 1e6)
# Hydrogen: GJ to t
HYDROGEN_GJ_T = 1 / 119.988

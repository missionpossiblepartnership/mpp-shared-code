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
COMPUTE_LCOX = False
# define CCU/S OPEX context dimensions.
#   IMPORTANT: Don't forget to add "opex_context" to UNCERTAINTY_RANKING_GROUPS if more than one dimension!
CCUS_CONTEXT = ["high_low"]

### MODEL DECISION PARAMETERS ###
START_YEAR = 2020
END_YEAR = 2050
MODEL_YEARS = np.arange(START_YEAR, END_YEAR + 1)

PATHWAYS_SENSITIVITIES = {

    # MAIN MODEL #
    # "bau": ["def"],
    # "fa": ["def"],
    # "lc": ["def"],
    # "nz": ["nz"],
    # "nz": ["inno"],
    # "custom": ["decelerated"],

    # MAIN MODEL NZ SENSITIVITIES #
    # "nz": ["fossil-low", "fossil-high", "elec-low", "elec-high", "af-low", "af-high", "nz"],
    # "nz-scm-what-if": ["nz"],
    # "nz-scm-stretch": ["nz"],
    # "nz-binder-what-if": ["nz"],
    # "nz-binder-stretch": ["nz"],
    # "nz-gcca-early": ["nz"],
    # "nz-gcca-late": ["nz"],
    # "nz-low-ramp": ["nz"],
    # "nz-high-ramp": ["nz"],

    # SET1
    # "nz-gcca-early": ["nz"],
    # "nz-gcca-late": ["nz"],

    # "fa": ["def"],
    # "custom": ["decelerated"],
    # "nz-scm-what-if": ["nz"],
    # "nz-gcca-early": ["nz"],
    # "nz-gcca-late": ["nz"],

    # ARCHETYPE EXPLORER #
    "archetype": ["000000", "000001"],
    # "archetype": ["000000"],
}

PATHWAYS_WITH_CARBON_COST = [
    "lc", "nz", "custom",
    "nz-scm-what-if", "nz-scm-stretch",
    "nz-binder-what-if", "nz-binder-stretch",
    "nz-gcca-early", "nz-gcca-late",
    "nz-low-ramp", "nz-high-ramp",
    "nz-bio-recarb",
]
PATHWAYS_WITH_TECHNOLOGY_MORATORIUM = [
    "lc", "nz",
    "nz-scm-what-if", "nz-scm-stretch",
    "nz-binder-what-if", "nz-binder-stretch",
    "nz-gcca-early", "nz-gcca-late",
    "nz-low-ramp", "nz-high-ramp",
    "nz-bio-recarb",
]

PATHWAY_DEMAND_SCENARIO_MAPPING = {

    # MAIN MODEL #
    "bau": "bau",
    "fa": "gcca-early",
    "lc": "gcca",
    "nz": "gcca",
    "custom": "gcca-late",

    # SENSITIVITY RUNS #
    "nz-scm-what-if": "scm-what-if",
    "nz-scm-stretch": "scm-stretch",
    "nz-binder-what-if": "binder-what-if",
    "nz-binder-stretch": "binder-stretch",
    "nz-gcca-early": "gcca-early",
    "nz-gcca-late": "gcca-late",
    "nz-low-ramp": "gcca",
    "nz-high-ramp": "gcca",
    "nz-bio-recarb": "gcca",
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

    # SENSITIVITY RUNS #
    "fossil-low": {
        "trajectory": "linear",
        "initial_carbon_cost": 40,
        "final_carbon_cost": 100,
        "start_year": 2025,
        "end_year": 2050,
    },
    "fossil-high": {
        "trajectory": "linear",
        "initial_carbon_cost": 40,
        "final_carbon_cost": 100,
        "start_year": 2025,
        "end_year": 2050,
    },
    "elec-low": {
        "trajectory": "linear",
        "initial_carbon_cost": 40,
        "final_carbon_cost": 100,
        "start_year": 2025,
        "end_year": 2050,
    },
    "elec-high": {
        "trajectory": "linear",
        "initial_carbon_cost": 40,
        "final_carbon_cost": 100,
        "start_year": 2025,
        "end_year": 2050,
    },
    "af-low": {
        "trajectory": "linear",
        "initial_carbon_cost": 40,
        "final_carbon_cost": 100,
        "start_year": 2025,
        "end_year": 2050,
    },
    "af-high": {
        "trajectory": "linear",
        "initial_carbon_cost": 40,
        "final_carbon_cost": 100,
        "start_year": 2025,
        "end_year": 2050,
    },
}
CARBON_COST_SCOPES = ["scope1", "scope2"]

# power price sensitivities (first list element: metrics it applies to; second list element: percentage change)
POWER_PRICE_SENSITIVITIES = {
    "fossil-low": ["Coal|Natural gas", -0.2],
    "fossil-high": ["Coal|Natural gas", 0.2],
    "elec-low": ["Electricity", -0.2],
    "elec-high": ["Electricity", 0.2],
    "af-low": ["Biomass|Hydrogen|Waste", -0.2],
    "af-high": ["Biomass|Hydrogen|Waste", 0.2],
}

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

    # SENSITIVITY RUNS #
    "nz-scm-what-if": 1.0,
    "nz-scm-stretch": 1.0,
    "nz-binder-what-if": 1.0,
    "nz-binder-stretch": 1.0,
    "nz-gcca-early": 1.0,
    "nz-gcca-late": 1.0,
    "nz-low-ramp": 1.0,
    "nz-high-ramp": 1.0,
    "nz-bio-recarb": 1.0,
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

    # sensitivity runs
    "fossil-low": MATURE_TECHS,
    "fossil-high": MATURE_TECHS,
    "elec-low": MATURE_TECHS,
    "elec-high": MATURE_TECHS,
    "af-low": MATURE_TECHS,
    "af-high": MATURE_TECHS,
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

        # sensitivity runs #
        "nz-scm-what-if": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-scm-stretch": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-binder-what-if": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-binder-stretch": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-gcca-early": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-gcca-late": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-low-ramp": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-high-ramp": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-bio-recarb": {
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

        # sensitivity runs #
        "nz-scm-what-if": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-scm-stretch": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-binder-what-if": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-binder-stretch": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-gcca-early": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-gcca-late": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-low-ramp": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-high-ramp": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-bio-recarb": {
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

        # sensitivity runs #
        "nz-scm-what-if": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-scm-stretch": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-binder-what-if": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-binder-stretch": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-gcca-early": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-gcca-late": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-low-ramp": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-high-ramp": {
            "cost": lc_weight_cost,
            "emissions": lc_weight_emissions,
        },
        "nz-bio-recarb": {
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

    # SENSITIVITY RUNS #
    "nz-scm-what-if": "rayleigh",
    "nz-scm-stretch": "rayleigh",
    "nz-binder-what-if": "rayleigh",
    "nz-binder-stretch": "rayleigh",
    "nz-gcca-early": "rayleigh",
    "nz-gcca-late": "rayleigh",
    "nz-low-ramp": "rayleigh",
    "nz-high-ramp": "rayleigh",
    "nz-bio-recarb": "rayleigh",
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
        "init_maximum_asset_additions": 4.25,
        "maximum_asset_growth_rate": 3,
        "years_rampup_phase": 30,
    },
    "custom": {
        "init_maximum_asset_additions": 5,
        "maximum_asset_growth_rate": 0.05,
        "years_rampup_phase": 30,
    },

    # SENSITIVITY RUNS #
    "nz-scm-what-if": {
        "init_maximum_asset_additions": 4.25,
        "maximum_asset_growth_rate": 3,
        "years_rampup_phase": 30,
    },
    "nz-scm-stretch": {
        "init_maximum_asset_additions": 4.25,
        "maximum_asset_growth_rate": 3,
        "years_rampup_phase": 30,
    },
    "nz-binder-what-if": {
        "init_maximum_asset_additions": 4.25,
        "maximum_asset_growth_rate": 3,
        "years_rampup_phase": 30,
    },
    "nz-binder-stretch": {
        "init_maximum_asset_additions": 4.25,
        "maximum_asset_growth_rate": 3,
        "years_rampup_phase": 30,
    },
    "nz-gcca-early": {
        "init_maximum_asset_additions": 4.25,
        "maximum_asset_growth_rate": 3,
        "years_rampup_phase": 30,
    },
    "nz-gcca-late": {
        "init_maximum_asset_additions": 4.25,
        "maximum_asset_growth_rate": 3,
        "years_rampup_phase": 30,
    },
    "nz-low-ramp": {
        "init_maximum_asset_additions": 3.5,
        "maximum_asset_growth_rate": 3,
        "years_rampup_phase": 30,
    },
    "nz-high-ramp": {
        "init_maximum_asset_additions": 5,
        "maximum_asset_growth_rate": 3.25,
        "years_rampup_phase": 30,
    },
    "nz-bio-recarb": {
        "init_maximum_asset_additions": 3.25,
        "maximum_asset_growth_rate": 3,
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

    # sensitivity runs #
    "nz-scm-what-if": [
        # "emissions_constraint",
        "rampup_constraint",
        # "regional_constraint",
        "biomass_constraint",
        "co2_storage_constraint",
    ],
    "nz-scm-stretch": [
        # "emissions_constraint",
        "rampup_constraint",
        # "regional_constraint",
        "biomass_constraint",
        "co2_storage_constraint",
    ],
    "nz-binder-what-if": [
        # "emissions_constraint",
        "rampup_constraint",
        # "regional_constraint",
        "biomass_constraint",
        "co2_storage_constraint",
    ],
    "nz-binder-stretch": [
        # "emissions_constraint",
        "rampup_constraint",
        # "regional_constraint",
        "biomass_constraint",
        "co2_storage_constraint",
    ],
    "nz-gcca-early": [
        # "emissions_constraint",
        "rampup_constraint",
        # "regional_constraint",
        "biomass_constraint",
        "co2_storage_constraint",
    ],
    "nz-gcca-late": [
        # "emissions_constraint",
        "rampup_constraint",
        # "regional_constraint",
        "biomass_constraint",
        "co2_storage_constraint",
    ],
    "nz-low-ramp": [
        # "emissions_constraint",
        "rampup_constraint",
        # "regional_constraint",
        "biomass_constraint",
        "co2_storage_constraint",
    ],
    "nz-high-ramp": [
        # "emissions_constraint",
        "rampup_constraint",
        # "regional_constraint",
        "biomass_constraint",
        "co2_storage_constraint",
    ],
    "nz-bio-recarb": [
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

# Unit conversions #
# Coal: GJ to t
COAL_GJ_T = 0.034120842375357
# Natural gas: GJ to billion cubic meter
NATURAL_GAS_GJ_BCM = 1 / (38.2 * 1e6)
# Electricity: GJ to TWh
ELECTRICITY_GJ_TWH = 1 / (3.6 * 1e6)
# Hydrogen: GJ to t
HYDROGEN_GJ_T = 1 / 119.988

# Gross biomass emission factor [tCO2/GJ] #
GROSS_BIO_EMISSION_FACTOR = 0.1

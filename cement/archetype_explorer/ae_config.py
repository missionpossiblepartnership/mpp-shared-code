""" config file for archetype explorer """

from cement.config.config_cement import (
    MATURE_TECHS,
    INNO_TECHS,
)


""" general """

AE_COMPUTE_LCOX = True
AE_LIST_TECHNOLOGIES = MATURE_TECHS + INNO_TECHS
AE_YEARS = (2020, 2030, 2040, 2050)

""" sensitivities """

AE_SENSITIVITY_MAPPING = {
    "000000": {
        "carbon_cost": "med",
        "elec_price": "low",
        "fossil_price": "high",
        "af_price": "low",
        "capex": "high",
        "capture_rate": "low",
    },
    "000001": {
        "carbon_cost": "med",
        "elec_price": "med",
        "fossil_price": "high",
        "af_price": "low",
        "capex": "high",
        "capture_rate": "low",
    },
    "000002": {
        "carbon_cost": "med",
        "elec_price": "high",
        "fossil_price": "high",
        "af_price": "low",
        "capex": "high",
        "capture_rate": "low",
    },
}

AE_CARBON_COST = {
    "None": None,
    "low": {
        "trajectory": "linear",
        "initial_carbon_cost": 0,
        "final_carbon_cost": 100,
        "start_year": 2030,
        "end_year": 2050,
    },
    "med": {
        "trajectory": "linear",
        "initial_carbon_cost": 40,
        "final_carbon_cost": 100,
        "start_year": 2025,
        "end_year": 2050,
    },
    "high": {
        "trajectory": "linear",
        "initial_carbon_cost": 0,
        "final_carbon_cost": 210,
        "start_year": 2023,
        "end_year": 2050,
    },
}

price_low = -0.2
price_med = 0
price_high = 0.2

ELEC_PRICE = {
    "low": price_low,
    "med": price_med,
    "high": price_high,
}

# gas and coal
FOSSIL_PRICE = {
    "low": price_low,
    "med": price_med,
    "high": price_high,
}

# biomass, waste, and hydrogen
AF_PRICE = {
    "low": price_low,
    "med": price_med,
    "high": price_high,
}

CAPEX = {
    "low": price_low,
    "med": price_med,
    "high": price_high,
}

CAPTURE_RATE = {
    "low": 0.90,
    "med": 0.95,
    "high": 0.99,
}


""" mappings to split / rename technologies """

DEF_CAPTURE_RATE = CAPTURE_RATE["med"]
TECH_ORIGIN_NAME_MAP = {
    "Dry kiln coal": "Dry kiln coal",
    "Dry kiln natural gas": "Dry kiln natural gas",
    "Dry kiln alternative fuels 43%": "Dry kiln alternative fuels (medium share)",
    "Dry kiln alternative fuels 90%": "Dry kiln alternative fuels (high share)",
    "Dry kiln coal + post combustion + storage": f"Dry kiln coal + post combustion ({DEF_CAPTURE_RATE * 100}% capture rate)",
    "Dry kiln natural gas + post combustion + storage": f"Dry kiln natural gas + post combustion ({DEF_CAPTURE_RATE * 100}% capture rate)",
    "Dry kiln alternative fuels (43%) + post combustion + storage": f"Dry kiln alternative fuels (medium share) + post combustion ({DEF_CAPTURE_RATE * 100}% capture rate)",
    "Dry kiln alternative fuels (90%) + post combustion + storage": f"Dry kiln alternative fuels (high share) + post combustion ({DEF_CAPTURE_RATE * 100}% capture rate)",
    "Dry kiln coal + oxyfuel + storage": f"Dry kiln coal + oxyfuel ({DEF_CAPTURE_RATE * 100}% capture rate)",
    "Dry kiln natural gas + oxyfuel + storage": f"Dry kiln natural gas + oxyfuel ({DEF_CAPTURE_RATE * 100}% capture rate)",
    "Dry kiln alternative fuels (43%) + oxyfuel + storage": f"Dry kiln alternative fuels (medium share) + oxyfuel ({DEF_CAPTURE_RATE * 100}% capture rate)",
    "Dry kiln alternative fuels (90%) + oxyfuel + storage": f"Dry kiln alternative fuels (high share) + oxyfuel ({DEF_CAPTURE_RATE * 100}% capture rate)",
    "Dry kiln coal + direct separation + storage": f"Dry kiln coal + direct separation ({DEF_CAPTURE_RATE * 100}% capture rate)",
    "Dry kiln natural gas + direct separation + storage": f"Dry kiln natural gas + direct separation ({DEF_CAPTURE_RATE * 100}% capture rate)",
    "Dry kiln alternative fuels (43%) + direct separation + storage": f"Dry kiln alternative fuels (medium share) + direct separation ({DEF_CAPTURE_RATE * 100}% capture rate)",
    "Dry kiln alternative fuels (90%) + direct separation + storage": f"Dry kiln alternative fuels (high share) + direct separation ({DEF_CAPTURE_RATE * 100}% capture rate)",
    "Electric kiln + direct separation": f"Electric kiln + direct separation ({DEF_CAPTURE_RATE * 100}% capture rate)",
    "Dry kiln + Hydrogen + direct separation": f"Dry kiln + Hydrogen + direct separation ({DEF_CAPTURE_RATE * 100}% capture rate)",
}

TECH_DESTINATION_NAME_MAP = {
    "Dry kiln coal": "Dry kiln coal",
    "Dry kiln natural gas": "Dry kiln natural gas",
    "Dry kiln alternative fuels 43%": "Dry kiln alternative fuels (medium share)",
    "Dry kiln alternative fuels 90%": "Dry kiln alternative fuels (high share)",
    "Dry kiln coal + post combustion + storage": f"Dry kiln coal + post combustion",
    "Dry kiln natural gas + post combustion + storage": f"Dry kiln natural gas + post combustion",
    "Dry kiln alternative fuels (43%) + post combustion + storage": f"Dry kiln alternative fuels (medium share) + post combustion",
    "Dry kiln alternative fuels (90%) + post combustion + storage": f"Dry kiln alternative fuels (high share) + post combustion",
    "Dry kiln coal + oxyfuel + storage": f"Dry kiln coal + oxyfuel",
    "Dry kiln natural gas + oxyfuel + storage": f"Dry kiln natural gas + oxyfuel",
    "Dry kiln alternative fuels (43%) + oxyfuel + storage": f"Dry kiln alternative fuels (medium share) + oxyfuel",
    "Dry kiln alternative fuels (90%) + oxyfuel + storage": f"Dry kiln alternative fuels (high share) + oxyfuel",
    "Dry kiln coal + direct separation + storage": f"Dry kiln coal + direct separation",
    "Dry kiln natural gas + direct separation + storage": f"Dry kiln natural gas + direct separation",
    "Dry kiln alternative fuels (43%) + direct separation + storage": f"Dry kiln alternative fuels (medium share) + direct separation",
    "Dry kiln alternative fuels (90%) + direct separation + storage": f"Dry kiln alternative fuels (high share) + direct separation",
    "Electric kiln + direct separation": f"Electric kiln + direct separation",
    "Dry kiln + Hydrogen + direct separation": f"Dry kiln + Hydrogen + direct separation",
}

TECH_SPLIT_MAP = {
    "Dry kiln coal": "Coal, -",
    "Dry kiln natural gas": "Natural Gas, -",
    "Dry kiln alternative fuels 43%": "Alternative fuels (medium share), -",
    "Dry kiln alternative fuels 90%": "Alternative fuels (high share), -",
    "Dry kiln coal + post combustion + storage": "Coal, Post combustion",
    "Dry kiln natural gas + post combustion + storage": "Natural Gas, Post combustion",
    "Dry kiln alternative fuels (43%) + post combustion + storage": "Alternative fuels (medium share), Post combustion",
    "Dry kiln alternative fuels (90%) + post combustion + storage": "Alternative fuels (high share), Post combustion",
    "Dry kiln coal + oxyfuel + storage": "Coal, Oxyfuel",
    "Dry kiln natural gas + oxyfuel + storage": "Natural Gas, Oxyfuel",
    "Dry kiln alternative fuels (43%) + oxyfuel + storage": "Alternative fuels (medium share), Oxyfuel",
    "Dry kiln alternative fuels (90%) + oxyfuel + storage": "Alternative fuels (high share), Oxyfuel",
    "Dry kiln coal + direct separation + storage": "Coal, Direct separation",
    "Dry kiln natural gas + direct separation + storage": "Natural Gas, Direct separation",
    "Dry kiln alternative fuels (43%) + direct separation + storage": "Alternative fuels (medium share), Direct separation",
    "Dry kiln alternative fuels (90%) + direct separation + storage": "Alternative fuels (high share), Direct separation",
    "Electric kiln + direct separation": "Electricity, Direct separation",
    "Dry kiln + Hydrogen + direct separation": "Hydrogen, Direct separation",
}

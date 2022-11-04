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

""" config file for archetype explorer """

from cement.config.config_cement import (
    MATURE_TECHS,
    INNO_TECHS,
)


""" general """

AE_COMPUTE_LCOX = False
AE_LIST_TECHNOLOGIES = MATURE_TECHS + INNO_TECHS

""" sensitivities """

AE_SENSITIVITY_MAPPING = {
    "000000": {
        "carbon_cost": "med",
        "elec_price": "med",
        "fossil_price": "med",
        "af_price": "med",
        "capex": "med",
        "capture_rate": "med",
    }
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

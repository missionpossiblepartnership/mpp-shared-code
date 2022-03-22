""" Rank technology switches."""
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)


def get_rank_config(rank_type: str, pathway: str):
    """
    Configuration to use for ranking
    For each rank type (new_build, retrofit, decommission), and each scenario,
    the dict items represent what to rank on, and in which order.
    For example:
    "new_build": {
        "me": {
            "type_of_tech_destination": "max",
            "lcox": "min",
            "emissions_scope_1_2_delta": "min",
            "emissions_scope_3_upstream_delta": "min",
        }
    indicates that for the new_build rank, in the most_economic scenario, we favor building:
    1. Higher tech type (i.e. more advanced tech)
    2. Lower levelized cost of chemical
    3. Lower scope 1/2 emissions
    4. Lower scope 3 emissions
    in that order!
    """

    config = {
        "new_build": {
            "bau": {
                "lcox": "min",
                "emissions_scope_1_2_delta": "min",
                "emissions_scope_3_upstream_delta": "min",
            },
        },
        "retrofit": {
            "bau": {
                "lcox": "min",
                "emissions_scope_1_2_delta": "max",
                "emissions_scope_3_upstream_delta": "max",
            },
        },
        "decommission": {
            "bau": {
                "lcox": "min",
                "emissions_scope_1_2_delta": "max",
                "emissions_scope_3_upstream_delta": "max",
            },
        },
    }

    return config[rank_type][pathway]

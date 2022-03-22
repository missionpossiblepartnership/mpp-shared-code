""" Rank technology switches."""
import pandas as pd

from mppshared.utility.utils import get_logger

logger = get_logger(__name__)


def get_rank_config(rank_type: str, pathway: str):
    """
    Configuration to use for ranking
    For each rank type (new_build, retrofit, decommission), and each scenario,
    the dict items represent the weights assigned for the ranking.
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
                "lcox": 0.5,
                "emissions_scope_1_2_delta": 0.25,
                "emissions_scope_3_upstream_delta": 0.25,
            },
        },
        "retrofit": {
            "bau": {
                "lcox": 0.5,
                "emissions_scope_1_2_delta": 0.25,
                "emissions_scope_3_upstream_delta": 0.25,
            },
        },
        "decommission": {
            "bau": {
                "lcox": 0.5,
                "delta_co2_scope1": 0.125,
                "delta_co2_scope2": 0.125,
                "delta_co2_scope3_upstream": 0.125,
                "delta_co2_scope3_downstream": 0.125,
            },
            "fa": {
                "lcox": 0.0,
                "delta_co2_scope1": 0.25,
                "delta_co2_scope2": 0.25,
                "delta_co2_scope3_upstream": 0.25,
                "delta_co2_scope3_downstream": 0.25,
            },
        },
    }

    return config[rank_type][pathway]


def rank_technology(df_ranking, rank_type, pathway, sensitivity):
    """Rank the technologies based on the ranking config.

    Args:
        df_ranking:
        rank_type:
        sensitivity:
    """
    logger.info(f"Making ranking for {rank_type}")
    # Get the config for the rank type
    config = get_rank_config(rank_type, pathway)
    # Get the weights for the rank type
    # Decomission ranking, what is the most expensive and pollutant technology
    # to decommission?
    holder = []
    df_ranking.fillna(0, inplace=True)
    for year in range(2020, 2051):
        df = df_ranking[
            (df_ranking["switch_type"] == "Decommission") & (df_ranking["year"] == year)
        ].copy()
        df[f"{rank_type}_{pathway}_score"] = (
            (df["lcox"] * config["lcox"])
            + (df["delta_co2_scope1"] * config["delta_co2_scope1"])
            + (df["delta_co2_scope2"] * config["delta_co2_scope2"])
            + (df["delta_co2_scope3_upstream"] + config["delta_co2_scope3_upstream"])
            + (
                df["delta_co2_scope3_downstream"]
                + config["delta_co2_scope3_downstream"]
            )
        )
        # Get the ranking for the rank type
        df[f"{rank_type}_{pathway}_ranking"] = df[f"{rank_type}_{pathway}_score"].rank(
            ascending=False
        )
        holder.append(df)
    df_rank = pd.concat(holder)

    return df_rank


def create_ranking(df_ranking, sensitivity, pathway):
    """Create the ranking for all the possible rank types and scenarios.

    Args:
        df_ranking:
    """
    for rank_type in ["decommission"]:  # ["new_build", "retrofit", "decommission"]:
        df_rank = rank_technology(df_ranking, rank_type, pathway, sensitivity)
        df_rank.to_csv(f"{rank_type}_{pathway}.csv", index=False)

""" Rank technology switches."""
import numpy as np
import pandas as pd

from mppshared.config import NUMBER_OF_BINS_RANKING
from mppshared.import_data.intermediate_data import IntermediateDataImporter
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
            "tco": "min",
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
                "tco": 1.0,
                "emissions": 0.0,
            },
            "fa": {
                "tco": 0.0,
                "emissions": 1.0,
            },
            "lc": {
                "tco": 0.8,
                "emissions": 0.2,
            },
        },
        "retrofit": {
            "bau": {
                "tco": 0.5,
                "emissions": 0.5,
            },
            "fa": {
                "tco": 0.0,
                "emissions": 1.0,
            },
            "lc": {
                "tco": 0.8,
                "emissions": 0.2,
            },
        },
        "decommission": {
            "bau": {
                "tco": 1,
                "emissions": 0,
            },
            "fa": {
                "tco": 0.0,
                "emissions": 1.0,
            },
            "lc": {
                "tco": 0.8,
                "emissions": 0.2,
            },
        },
    }

    return config[rank_type][pathway]


def bin_ranking(rank_array: np.array, n_bins: int = NUMBER_OF_BINS_RANKING) -> np.array:
    """
    Bin the ranking, i.e. values that are close together end up in the same bin
    Args:
        rank_array: The array with values we want to rank
        n_bins: the number of bins we want to
    Returns:
        array with binned values
    """
    _, bins = np.histogram(rank_array, bins=n_bins)
    return np.digitize(rank_array, bins=bins)


def _add_binned_rankings(
    df_rank: pd.DataFrame,
    rank_type: str,
    pathway: str,
    n_bins: int = NUMBER_OF_BINS_RANKING,
) -> pd.DataFrame:
    """Add binned values for the possible ranking columns"""
    df_rank[f"{rank_type}_{pathway}_score_binned"] = bin_ranking(
        df_rank[f"{rank_type}_{pathway}_score"], n_bins=n_bins
    )

    return df_rank


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
    for switch_type in [
        "decomission",
        "brownfield_newbuild",
        "brwonfield_greenfield",
        "greenfield",
    ]:
        df = df_ranking[(df_ranking["switch_type"] == switch_type)].copy()
        # Normalize the tco and sum of emissions delta
        df["tco_normalized"] = df["tco"] / df["tco"].max()
        df["sum_emissions_delta"] = (
            df["delta_co2_scope1"]
            + df["delta_co2_scope2"]
            + df["delta_co2_scope3_downstream"]
            + df["delta_co2_scope3_upstream"]
        )
        df["sum_emissions_delta_normalized"] = (
            df["sum_emissions_delta"] / df["sum_emissions_delta"].max()
        )
        df[f"{rank_type}_{pathway}_score"] = (
            df["sum_emissions_delta_normalized"] * config["emissions"]
        ) + (df["tco_normalized"] * config["tco"])
        df_rank = df.groupby(["year"]).apply(_add_binned_rankings, rank_type, pathway)
        # Get the ranking for the rank type
        df[f"{rank_type}_{pathway}_ranking"] = df[f"{rank_type}_{pathway}_score"].rank(
            ascending=False
        )
        holder.append(df)
    df_rank = pd.concat(holder)
    return df_rank


def make_rankings(pathway, sensitivity, sector, product):
    """Create the ranking for all the possible rank types and scenarios.

    Args:
        df_ranking:
    """
    importer = IntermediateDataImporter(
        pathway=pathway, sensitivity=sensitivity, sector=sector, product=product
    )
    df_ranking = importer.get_technologies_to_rank()
    for rank_type in ["decommission"]:  # ["new_build", "retrofit", "decommission"]:
        df_rank = rank_technology(df_ranking, rank_type, pathway, sensitivity)
        df_rank.to_csv(f"{rank_type}_{pathway}.csv", index=False)

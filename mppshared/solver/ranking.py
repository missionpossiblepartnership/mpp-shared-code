""" Rank technology switches."""
import sys

import numpy as np
import pandas as pd

from mppshared.config import (
    GHGS_RANKING,
    NUMBER_OF_BINS_RANKING,
    PRODUCTS,
    EMISSION_SCOPES_RANKING,
    RANKING_CONFIG,
    RANK_TYPES,
)
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)


def get_rank_config(rank_type: str, pathway: str):
    """Filter ranking configuration in config.py"""

    return RANKING_CONFIG[rank_type][pathway]


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


def rank_technology(
    df_ranking: pd.DataFrame,
    rank_type: str,
    pathway: str,
    sensitivity: str,
    product: str,
) -> pd.DataFrame:
    """Rank the technologies based on the ranking config.

    Args:
        df_ranking: DataFrame with cost and emissions data used to rank each technology transition
        rank_type: must be in RANK_TYPES
        pathway:
        sensitivity:
        product:

    Returns:
        Ranking table with column "rank" where minimum value corresponds to best technology transition
    """

    # Filter ranking table for desired product
    df_ranking = df_ranking.loc[df_ranking["product"] == product]

    logger.info(f"Making ranking for {rank_type} and product {product}")

    # Get the config for the rank type
    config = get_rank_config(rank_type, pathway)

    # Filter ranking table for the type of technology transition
    df_ranking.fillna(0, inplace=True)
    if rank_type == "brownfield":
        df = df_ranking[df_ranking["switch_type"].str.contains("brownfield")].copy()
    elif rank_type == "decommission":
        df = df_ranking[(df_ranking["switch_type"] == "decommission")].copy()
    elif rank_type == "greenfield":
        df = df_ranking[(df_ranking["switch_type"] == "greenfield")].copy()

    # Normalize TCO
    df["tco_normalized"] = 1 - (df["tco"] - df["tco"].min()) / (
        df["tco"].max() - df["tco"].min()
    )

    # Sum emission reductions for all scopes included in optimization. Add 1 to avoid division by 0 in normalization
    col_list = [
        f"delta_{ghg}_{scope}"
        for scope in EMISSION_SCOPES_RANKING
        for ghg in GHGS_RANKING
    ]
    df["sum_emissions_delta"] = 1 + (df[col_list].sum(axis=1))

    # Normalize the sum of emission reductions
    df["sum_emissions_delta_normalized"] = 1 - (
        df["sum_emissions_delta"] - df["sum_emissions_delta"].min()
    ) / (df["sum_emissions_delta"].max() - df["sum_emissions_delta"].min())
    df.fillna(0, inplace=True)

    # Calculate scores
    df[f"{rank_type}_{pathway}_score"] = (
        df["sum_emissions_delta_normalized"] * config["emissions"]
    ) + (df["tco_normalized"] * config["tco"])
    df_rank = df.groupby(["year"]).apply(_add_binned_rankings, rank_type, pathway)

    # Calculate final rank for the transition type
    df_rank["rank"] = df_rank[f"{rank_type}_{pathway}_score"].rank(ascending=False)

    return df_rank


def make_rankings(pathway: str, sensitivity: str, sector: str):
    """Create the ranking for all the possible rank types and scenarios.

    Args:
        df_ranking:
    """
    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS[sector],
    )

    # Make the ranking separately for each product and each type of technology transition
    df_ranking = importer.get_technologies_to_rank()
    for product in PRODUCTS[sector]:
        for rank_type in RANK_TYPES:

            # Create ranking table
            df_rank = rank_technology(
                df_ranking, rank_type, pathway, sensitivity, product
            )

            # Save ranking table as csv
            importer.export_data(
                df=df_rank,
                filename=f"{rank_type}_rank.csv",
                export_dir=f"ranking/{product}",
                index=False,
            )

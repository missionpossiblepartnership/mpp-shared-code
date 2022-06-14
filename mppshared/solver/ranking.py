""" Rank technology switches."""
import sys

import numpy as np
import pandas as pd

from mppshared.config import (
    BIN_METHODOLOGY,
    COST_METRIC_RELATIVE_UNCERTAINTY,
    EMISSION_SCOPES_RANKING,
    GHGS_RANKING,
    NUMBER_OF_BINS_RANKING,
    PRODUCTS,
    RANK_TYPES,
    RANKING_CONFIG,
    RANKING_COST_METRIC,
)
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)


def get_rank_config(rank_type: str, pathway: str, sector: str) -> dict:
    """Filter ranking configuration in config.py"""
    logger.debug("Getting configuration for ranking")

    return RANKING_CONFIG[sector][rank_type][pathway]


def bin_ranking(rank_array: np.array, n_bins: int = NUMBER_OF_BINS_RANKING) -> np.array:
    """
    Bin the ranking, i.e. values that are close together end up in the same bin
    Args:
        rank_array: The array with values we want to rank
        n_bins: the number of bins we want to
    Returns:
        array with binned values
    """
    logger.debug("making bin ranks")
    _, bins = np.histogram(rank_array, bins=n_bins)
    digitized = np.digitize(rank_array, bins=bins)
    return digitized


def _add_binned_rankings(
    df_rank: pd.DataFrame, rank_type: str, pathway: str, n_bins: int
) -> pd.DataFrame:
    """Add binned values for the possible ranking columns"""
    logger.debug("Adding binned values")
    df_rank[f"{rank_type}_{pathway}_score_binned"] = bin_ranking(
        df_rank[f"{rank_type}_{pathway}_score"], n_bins=n_bins
    )

    return df_rank


def rank_technology_histogram(
    df_ranking: pd.DataFrame,
    rank_type: str,
    pathway: str,
    sector: str,
    cost_metric: str,
    n_bins: str,
) -> pd.DataFrame:
    """Rank the technologies based on the ranking config.

    Args:
        df_ranking: DataFrame with cost and emissions data used to rank each technology transition
        rank_type: must be in RANK_TYPES
        pathway:
        sector:
        product:

    Returns:
        Ranking table with column "rank" where minimum value corresponds to best technology transition
    """
    logger.info(f"Making ranking for {rank_type}")

    # Filter ranking table for desired product and ranking type
    df = get_ranking_table(df_ranking=df_ranking, rank_type=rank_type)

    # Get the config for the rank type
    config = get_rank_config(rank_type=rank_type, pathway=pathway, sector=sector)

    # Normalize cost metric
    logger.debug(f"Normalizing {cost_metric}")
    df[f"{cost_metric}_normalized"] = 1 - (df[cost_metric] - df[cost_metric].min()) / (
        df[cost_metric].max() - df[cost_metric].min()
    )

    # Sum emission reductions for all scopes included in optimization. Add 1 to avoid division by 0 in normalization
    col_list = [
        f"delta_{ghg}_{scope}"
        for scope in EMISSION_SCOPES_RANKING[sector]
        for ghg in GHGS_RANKING[sector]
    ]
    logger.debug("Summing emissions delta")
    df["sum_emissions_delta"] = 1 + (df[col_list].sum(axis=1))

    # Normalize the sum of emission reductions
    logger.debug("Normalization of emissions reductions")
    df["sum_emissions_delta_normalized"] = 1 - (
        df["sum_emissions_delta"].max() - df["sum_emissions_delta"]
    ) / (df["sum_emissions_delta"].max() - df["sum_emissions_delta"].min())
    df.fillna(0, inplace=True)

    # Calculate scores
    logger.debug("Calculating scores")
    df[f"{rank_type}_{pathway}_score"] = (
        df["sum_emissions_delta_normalized"] * config["emissions"]
    ) + (df[f"{cost_metric}_normalized"] * config["cost"])
    logger.debug("Adding binned rankings")

    # Bin the rank scores
    df_rank = df.groupby(["year"]).apply(
        _add_binned_rankings, rank_type, pathway, n_bins
    )
    # df_rank = df

    # Calculate final rank for the transition type
    logger.debug("Calculating final rank")
    df_rank["rank"] = df_rank[f"{rank_type}_{pathway}_score"].rank(ascending=False)

    return df_rank


def rank_technology_uncertainty_bins(
    df_ranking: pd.DataFrame,
    rank_type: str,
    pathway: str,
    sector: str,
    cost_metric: str,
):
    """Create technology binned according to histogram methodology with number of bins from cost metric uncertainty."""

    logger.info(f"Making ranking for {rank_type}")

    # Filter ranking table for desired product and ranking type
    df = get_ranking_table(df_ranking=df_ranking, rank_type=rank_type)

    # Get the config for the rank type
    config = get_rank_config(rank_type=rank_type, pathway=pathway, sector=sector)

    # Apply ranking year-by-year
    df = df.groupby(["year"]).apply(
        _create_ranking_uncertainty_bins,
        sector,
        cost_metric,
        COST_METRIC_RELATIVE_UNCERTAINTY[sector],
        config,
        pathway,
    )

    return df


def _create_ranking_uncertainty_bins(
    df: pd.DataFrame,
    sector: str,
    cost_metric: str,
    cost_uncertainty: float,
    config: dict,
    pathway: str,
):

    # Normalize cost metric
    logger.debug(f"Normalizing {cost_metric}")
    df["cost_normalized"] = (df[cost_metric] - df[cost_metric].min()) / (
        df[cost_metric].max() - df[cost_metric].min()
    )

    # Sum emission reductions for all scopes included in optimization. Add 1 to avoid division by 0 in normalization
    col_list = [
        f"delta_{ghg}_{scope}"
        for scope in EMISSION_SCOPES_RANKING[sector]
        for ghg in GHGS_RANKING[sector]
    ]
    logger.debug("Summing emissions delta")
    df["sum_emissions_delta"] = df[col_list].sum(axis=1)

    # Normalize the sum of emission reductions (assumes that emissions have no uncertainty): 1 corresponds to lowest reduction, 0 to highest reduction
    # Reverse sign so that emissions reduction is destination - origin technology (smallest value is best)
    df["sum_emissions_delta"] = -df["sum_emissions_delta"]
    df["emissions_delta_normalized"] = (
        df["sum_emissions_delta"] - df["sum_emissions_delta"].min()
    ) / (df["sum_emissions_delta"].max() - df["sum_emissions_delta"].min())
    df.fillna(0, inplace=True)

    # Rank is based on weighting of the normalized cost and emission metrics
    df["rank_raw"] = (
        df["cost_normalized"] * config["cost"]
        + df["emissions_delta_normalized"] * config["emissions"]
    )

    if pathway in ["lc", "bau"]:
        # Calculate number of bins
        bin_interval = cost_uncertainty * df[cost_metric].min()
        bin_range = df[cost_metric].max() - df[cost_metric].min()

        if (bin_range != 0) & (bin_interval != 0):
            n_bins = int(bin_range / bin_interval)

            # Bin the rank scores
            _, bins = np.histogram(df["rank_raw"], bins=n_bins)
            df["rank"] = np.digitize(df["rank_raw"], bins=bins)
        else:
            # All rank scores are 0, so all ranks are 0
            df["rank"] = df["rank_raw"]
    elif pathway == "fa":
        n_bins = int(len(df))
        _, bins = np.histogram(df["rank_raw"], bins=n_bins)
        df["rank"] = np.digitize(df["rank_raw"], bins=sorted(df["rank_raw"]))

    return df


def rank_technology_relative_uncertainty(
    df_ranking: pd.DataFrame,
    rank_type: str,
    pathway: str,
    sector: str,
    cost_metric: str,
) -> pd.DataFrame:

    logger.info(f"Making ranking for {rank_type}")

    # Filter ranking table for desired product and ranking type
    df = get_ranking_table(df_ranking=df_ranking, rank_type=rank_type)

    # Get the config for the rank type
    config = get_rank_config(rank_type, pathway, sector)

    # Perform ranking methodology for each year
    df_rank = df.groupby(["year"]).apply(
        _create_ranking_uncertainty,
        sector=sector,
        cost_metric=cost_metric,
        cost_uncertainty=COST_METRIC_RELATIVE_UNCERTAINTY[sector],
        config=config,
        pathway=pathway,
    )

    return df_rank


def _create_ranking_uncertainty(
    df: pd.DataFrame,
    sector: str,
    cost_metric: str,
    cost_uncertainty: float,
    config: dict,
    pathway: str,
) -> pd.DataFrame:
    """Create ranking based on relative cost uncertainty for a DataFrame."""

    # Create cost bins
    rank_array = np.array(df[cost_metric])
    cost_bins = create_uncertainty_bins(
        array=rank_array,
        relative_uncertainty=cost_uncertainty,
    )

    # Normalize cost metric: 1 corresponds to highest cost, 0 to lowest cost across the entire table
    df["cost_digitized"] = np.digitize(rank_array, bins=cost_bins)
    df["cost_normalized"] = (df["cost_digitized"] - df["cost_digitized"].min()) / (
        df["cost_digitized"].max() - df["cost_digitized"].min()
    )

    # Sum emission reductions (emissions of origin technology - destination technology) for all scopes included in optimization
    col_list = [
        f"delta_{ghg}_{scope}"
        for scope in EMISSION_SCOPES_RANKING[sector]
        for ghg in GHGS_RANKING[sector]
    ]
    logger.debug("Summing emissions delta")
    df["sum_emissions_delta"] = df[col_list].sum(axis=1)

    # Normalize the sum of emission reductions (assumes that emissions have no uncertainty): 1 corresponds to lowest reduction, 0 to highest reduction
    # Reverse sign so that emissions reduction is destination - origin technology (smallest value is best)
    df["sum_emissions_delta"] = -df["sum_emissions_delta"]
    df["emissions_delta_normalized"] = (
        df["sum_emissions_delta"] - df["sum_emissions_delta"].min()
    ) / (df["sum_emissions_delta"].max() - df["sum_emissions_delta"].min())
    df.fillna(0, inplace=True)

    # Rank is based on weighting of the normalized cost and emission metrics
    df["rank"] = (
        df["cost_normalized"] * config["cost"]
        + df["emissions_delta_normalized"] * config["emissions"]
    )

    return df


def create_uncertainty_bins(array: np.array, relative_uncertainty: float) -> list:
    """Create bins for a metric based on its relative uncertainty."""

    min_metric = array.min()
    max_metric = array.max()

    # Minimum cost is starting point of lowest cost range
    bins = [min_metric, min_metric * (1 + relative_uncertainty)]

    # While the bins are lower than the maximum cost metric, continue creating bins based on the relative uncertainty
    while max(bins) < max_metric:
        startpoint = bins[-1]
        endpoint = startpoint * (1 + relative_uncertainty)
        bins.append(endpoint)

    return bins


def get_ranking_table(df_ranking: pd.DataFrame, rank_type: str) -> pd.DataFrame:

    # Filter ranking table for the type of technology transition
    df_ranking.fillna(0, inplace=True)
    logger.debug("Applying filter for ranking type")
    if rank_type == "brownfield":
        df = df_ranking[df_ranking["switch_type"].str.contains("brownfield")].copy()
    elif rank_type == "decommission":
        df = df_ranking[df_ranking["switch_type"] == "decommission"].copy()
    elif rank_type == "greenfield":
        df = df_ranking[(df_ranking["switch_type"].str.contains("greenfield"))].copy()

    return df


def make_rankings(
    pathway: str, sensitivity: str, sector: str, carbon_cost: CarbonCostTrajectory
):
    """Create the ranking for all the possible rank types and scenarios.

    Args:
        df_ranking:
    """
    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS[sector],
        carbon_cost=carbon_cost,
    )

    # Make the ranking separately for each type of technology transition (all products together)
    df_ranking = importer.get_technologies_to_rank()
    for rank_type in RANK_TYPES[sector]:
        # Create ranking table
        if BIN_METHODOLOGY[sector] == "histogram":
            df_rank = rank_technology_histogram(
                df_ranking=df_ranking,
                rank_type=rank_type,
                pathway=pathway,
                sector=sector,
                cost_metric=RANKING_COST_METRIC[sector],
                n_bins=NUMBER_OF_BINS_RANKING[sector],
            )
        elif BIN_METHODOLOGY[sector] == "uncertainty":
            df_rank = rank_technology_relative_uncertainty(
                df_ranking=df_ranking,
                rank_type=rank_type,
                pathway=pathway,
                sector=sector,
                cost_metric=RANKING_COST_METRIC[sector],
            )
        elif BIN_METHODOLOGY[sector] == "uncertainty_bins":
            df_rank = rank_technology_uncertainty_bins(
                df_ranking=df_ranking,
                rank_type=rank_type,
                pathway=pathway,
                sector=sector,
                cost_metric=RANKING_COST_METRIC[sector],
            )

        # TODO: remove this workaround
        # product = "Ammonia"
        # df_rank = df_rank.loc[df_rank["product"] == "Ammonia"]

        # Save ranking table as csv
        importer.export_data(
            df=df_rank,
            filename=f"{rank_type}_rank.csv",
            export_dir=f"ranking",
            index=False,
        )

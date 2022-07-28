"""Functions to create the ranking of technology switches"""
import numpy as np
import pandas as pd

from mppshared.utility.utils import get_logger

logger = get_logger(__name__)


def bin_ranking(rank_array: np.array, n_bins: int) -> np.array:
    """
    Bin the ranking, i.e. values that are close together end up in the same bin
    Args:
        rank_array: array with values to rank
        n_bins: the number of bins desire
    Returns:
        array with binned values
    """
    logger.debug("making bin ranks")
    _, bins = np.histogram(rank_array, bins=n_bins)
    digitized = np.digitize(rank_array, bins=bins)
    return digitized


def _add_binned_rankings(
    df_rank: pd.DataFrame, rank_type: str, pathway_name: str, n_bins: int
) -> pd.DataFrame:
    """Add binned values for the possible ranking columns"""
    logger.debug("Adding binned values")
    df_rank[f"{rank_type}_{pathway_name}_score_binned"] = bin_ranking(
        df_rank[f"{rank_type}_{pathway_name}_score"], n_bins=n_bins
    )

    return df_rank


def rank_technology_histogram(
    df_ranking: pd.DataFrame,
    rank_type: str,
    pathway_name: str,
    cost_metric: str,
    n_bins: int,
    ranking_config: dict,
    emission_scopes_ranking: list,
    ghgs_ranking: list,
) -> pd.DataFrame:
    """Rank technology switches based on the ranking config using the histogram methodology.

    Args:
        df_ranking: DataFrame with cost and emissions data used to rank each technology switch
        rank_type: either of "decommission", "brownfield" or "greenfield"
        pathway_name: name of the pathway for which to create the ranking
        cost_metric: use this cost metric for the cost part of the ranking
        n_bins: number of bins for binning the rank scores using a histogram
        ranking_config: weights of cost and emissions for the ranking, keys are "cost" and "emissions"
        emission_scopes_ranking: use these emission scopes for the emission part of the ranking
        ghgs_ranking: use these GHGS for the emission part of the ranking

    Returns:
        Ranking table with column "rank" where minimum value corresponds to best technology switch
    """
    logger.info(f"Making ranking for {rank_type}")

    # Filter ranking table for desired product and ranking type
    df = get_ranking_table(df_ranking=df_ranking, rank_type=rank_type)

    # Normalize cost metric
    logger.debug(f"Normalizing {cost_metric}")
    df[f"{cost_metric}_normalized"] = 1 - (df[cost_metric] - df[cost_metric].min()) / (
        df[cost_metric].max() - df[cost_metric].min()
    )

    # Sum emission reductions for all scopes included in optimization. Add 1 to avoid division by 0 in normalization
    col_list = [
        f"delta_{ghg}_{scope}"
        for scope in emission_scopes_ranking
        for ghg in ghgs_ranking
    ]
    logger.debug("Summing emissions delta")
    df["sum_emissions_delta"] = df[col_list].sum(axis=1)
    df["sum_emissions_delta"] = df["sum_emissions_delta"].apply(
        lambda x: x if x > 0 else (0.01 if x == 0 else 0.000001)
    )

    # Normalize the sum of emission reductions
    logger.debug("Normalization of emissions reductions")
    df["sum_emissions_delta_normalized"] = 1 - (
        df["sum_emissions_delta"].max() - df["sum_emissions_delta"]
    ) / (df["sum_emissions_delta"].max() - df["sum_emissions_delta"].min())
    df.fillna(0, inplace=True)

    # Calculate rank scores
    logger.debug("Calculating rank scores")
    if pathway_name == "lc":
        df[f"{cost_metric}_adjusted_by_emissions"] = (
            df[f"{cost_metric}"] / df["sum_emissions_delta"]
        )
        df[f"{cost_metric}_adjusted_by_emissions_normalized"] = 1 - (
            df[f"{cost_metric}_adjusted_by_emissions"].max()
            - df[f"{cost_metric}_adjusted_by_emissions"]
        ) / (
            df[f"{cost_metric}_adjusted_by_emissions"].max()
            - df[f"{cost_metric}_adjusted_by_emissions"].min()
        )
        df.fillna(0, inplace=True)
        df[f"{rank_type}_{pathway_name}_score"] = df[
            f"{cost_metric}_adjusted_by_emissions_normalized"
        ]
        df_rank = df
        logger.debug("Calculating final rank")
        df_rank["rank"] = df_rank[f"{rank_type}_{pathway_name}_score"].rank(
            ascending=True
        )

    else:
        df[f"{rank_type}_{pathway_name}_score"] = (
            df["sum_emissions_delta_normalized"] * ranking_config["emissions"]
        ) + (df[f"{cost_metric}_normalized"] * ranking_config["cost"])
        logger.debug("Adding binned rankings")

        # Bin the rank scores
        df_rank = df.groupby(["year"]).apply(
            _add_binned_rankings, rank_type, pathway_name, n_bins
        )

        # Calculate final rank for the transition type
        logger.debug("Calculating final rank")
        df_rank["rank"] = df_rank[f"{rank_type}_{pathway_name}_score"].rank(
            ascending=False
        )

    return df_rank


def rank_technology_uncertainty_bins(
    df_ranking: pd.DataFrame,
    rank_type: str,
    pathway_name: str,
    cost_metric: str,
    cost_metric_relative_uncertainty: float,
    ranking_config: dict,
    emission_scopes_ranking: list,
    ghgs_ranking: list,
    ranking_groups: list,
) -> pd.DataFrame:
    """Create technology binned according to histogram methodology with number of bins from cost metric uncertainty.

    Args:
        df_ranking (pd.DataFrame): table with technology switches
        rank_type (str): either of "decommission", "brownfield", "greenfield"
        pathway_name (str): pathway for which to create the ranking, either of "lc", "bau", "fa"
        cost_metric (str): cost metric used for the ranking
        cost_metric_relative_uncertainty (str):
        ranking_config (dict): weights for cost and emissions, keys are "cost" and "emissions"
        emission_scopes_ranking: use these emission scopes for the emission part of the ranking
        ghgs_ranking: use these GHGS for the emission part of the ranking
        ranking_groups: this list defines the columns that will be grouped and get their own ranking

    Returns:
        pd.DataFrame: table with technology switches where minimum value in column "rank" corresponds to highest ranked
            technology switch
    """

    logger.info(f"Making ranking for {rank_type}")

    # Filter ranking table for desired product and ranking type
    df = get_ranking_table(df_ranking=df_ranking, rank_type=rank_type)

    # Apply ranking year-by-year
    df = df.groupby(ranking_groups).apply(
        _create_ranking_uncertainty_bins,
        cost_metric,
        cost_metric_relative_uncertainty,
        ranking_config,
        pathway_name,
        emission_scopes_ranking,
        ghgs_ranking,
    )
    logger.info(f"Ranking for {rank_type} done")

    return df


def _create_ranking_uncertainty_bins(
    df: pd.DataFrame,
    cost_metric: str,
    cost_metric_relative_uncertainty: float,
    ranking_config: dict,
    pathway_name: str,
    emission_scopes_ranking: list,
    ghgs_ranking: list,
):
    """Calculate rank scores using a histogram-based binning methodology where the number of bins is derived from the
    relative uncertainty of the cost metric."""

    # Normalize cost metric
    logger.debug(f"Normalizing {cost_metric}")
    df["cost_normalized"] = (df[cost_metric] - df[cost_metric].min()) / (
        df[cost_metric].max() - df[cost_metric].min()
    )

    # Sum emission reductions for all scopes included in optimization. Add 1 to avoid division by 0 in normalization
    col_list = [
        f"delta_{ghg}_{scope}"
        for scope in emission_scopes_ranking
        for ghg in ghgs_ranking
    ]
    logger.debug("Summing emissions delta")
    df["sum_emissions_delta"] = df[col_list].sum(axis=1)

    # Normalize the sum of emission reductions (assumes that emissions have no uncertainty): 1 corresponds to lowest
    #   reduction, 0 to highest reduction
    # Reverse sign so that emissions reduction is destination - origin technology (smallest value is best)
    df["sum_emissions_delta"] = -df["sum_emissions_delta"]
    df["emissions_delta_normalized"] = (
        df["sum_emissions_delta"] - df["sum_emissions_delta"].min()
    ) / (df["sum_emissions_delta"].max() - df["sum_emissions_delta"].min())
    df.fillna(0, inplace=True)

    # Rank is based on weighting of the normalized cost and emission metrics
    df["rank_raw"] = (
        df["cost_normalized"] * ranking_config["cost"]
        + df["emissions_delta_normalized"] * ranking_config["emissions"]
    )

    if pathway_name in ["lc", "bau"]:
        # Calculate number of bins
        # get the minimum value of the cost metric and add the required positive value to move all the values to
        #   positive numbers
        # This is a hack to make the code work if we have negative values (multiplied by 2 to avoid a bin_interval of 0)
        if df[cost_metric].min() < 0:
            df[f"{cost_metric}_positive"] = df[cost_metric] + 2 * abs(df[cost_metric].min())
            bin_interval = (
                cost_metric_relative_uncertainty * df[f"{cost_metric}_positive"].min()
            )
        else:
            bin_interval = cost_metric_relative_uncertainty * df[cost_metric].min()
        bin_range = df[cost_metric].max() - df[cost_metric].min()

        if (bin_range != 0) & (bin_interval != 0):
            n_bins = int(bin_range / bin_interval)

            # Bin the rank scores
            _, bins = np.histogram(df["rank_raw"], bins=n_bins)
            df["rank"] = np.digitize(df["rank_raw"], bins=bins)
        else:
            # All rank scores are 0, so all ranks are 0
            df["rank"] = df["rank_raw"]
    elif pathway_name == "fa":
        n_bins = int(len(df))
        _, bins = np.histogram(df["rank_raw"], bins=n_bins)
        df["rank"] = np.digitize(df["rank_raw"], bins=sorted(df["rank_raw"]))

    return df


def get_ranking_table(df_ranking: pd.DataFrame, rank_type: str) -> pd.DataFrame:
    """Get the ranking table filtered for a specific type of technology switch

    Args:
        df_ranking (pd.DataFrame): describes technology switches to be used for ranking, contains column "switch_type"
        rank_type (str): either of "brownfield", "decommission", "greenfield"

    Returns:
        pd.DataFrame: table with technology switches for the desired rank type
    """
    df_ranking.fillna(0, inplace=True)
    logger.debug("Applying filter for ranking type")
    if rank_type == "brownfield":
        df = df_ranking[df_ranking["switch_type"].str.contains("brownfield")].copy()
    elif rank_type == "decommission":
        df = df_ranking[df_ranking["switch_type"] == "decommission"].copy()
    elif rank_type == "greenfield":
        df = df_ranking[(df_ranking["switch_type"].str.contains("greenfield"))].copy()

    return df

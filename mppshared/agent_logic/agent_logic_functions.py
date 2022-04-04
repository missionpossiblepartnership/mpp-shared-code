""" Additional functions required for the agent logic, e.g. demand balances. """

import pandas as pd
import numpy as np
from operator import methodcaller

from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.models.asset import Asset, AssetStack
from mppshared.config import (
    ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
    CUF_LOWER_THRESHOLD,
    CUF_UPPER_THRESHOLD,
    MODEL_SCOPE,
    LOG_LEVEL,
)
from mppshared.utility.utils import get_logger

logger = logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def select_best_transition(df_rank: pd.DataFrame) -> dict:
    """Based on the ranking, select the best transition

    Args:
        df_rank: contains column "rank" with ranking for each technology transition (minimum rank = optimal technology transition)

    Returns:
        The highest ranking technology transition

    """
    # Best transition has minimum rank
    return (
        df_rank[df_rank["rank"] == df_rank["rank"].min()]
        .sample(n=1)
        .to_dict(orient="records")
    )[0]


def adjust_capacity_utilisation(
    pathway: SimulationPathway, product: str, year: int
) -> SimulationPathway:
    """Adjust capacity utilisation of each asset within predefined thresholds to balance demand and production as much as possible in the given year.

    Args:
        pathway: pathway with AssetStack and demand data for the specified year
        product:
        year:

    Returns:
        pathway with updated capacity factor for each Asset in the AssetStack of the given year
    """
    # Get demand and production in that year
    demand = pathway.get_demand(product=product, year=year, region=MODEL_SCOPE)
    stack = pathway.get_stack(year=year)
    production = stack.get_annual_production_volume(product)

    # If demand exceeds production, increase capacity utilisation of each asset to make production deficit as small as possible, starting at the asset with lowest LCOX
    if demand > production:
        logger.info(
            "Increasing capacity utilisation of assets to minimise production deficit"
        )
        pathway = increase_cuf_of_assets(
            pathway=pathway, demand=demand, product=product, year=year
        )

    # If production exceeds demand, decrease capacity utilisation of each asset to make production surplus as small as possible, starting at asset with highest LCOX
    elif production > demand:
        logger.info(
            "Decreasing capacity utilisation of assets to minimise production surplus"
        )
        pathway = decrease_cuf_of_assets(
            pathway=pathway, demand=demand, product=product, year=year
        )

    production = stack.get_annual_production_volume(product)
    return pathway


def increase_cuf_of_assets(
    pathway: SimulationPathway, demand: float, product: str, year: int
) -> SimulationPathway:
    """Increase CUF of assets to minimise the production deficit."""

    # Get AssetStack for the given year
    stack = pathway.get_stack(year)

    # Identify all assets that produce below CUF threshold and sort list so asset with lowest LCOX is first
    assets_below_cuf_threshold = list(
        filter(lambda asset: asset.cuf < CUF_UPPER_THRESHOLD, stack.assets)
    )
    assets_below_cuf_threshold = sort_assets_lcox(
        assets_below_cuf_threshold, pathway, year
    )

    # Increase CUF of assets to upper threshold in order of ascending LCOX until production meets demand or no assets left for CUF increase
    while demand > stack.get_annual_production_volume(product):

        if not assets_below_cuf_threshold:
            break

        # Increase CUF of asset with lowest LCOX to upper threshold and remove from list
        asset = assets_below_cuf_threshold[0]
        logger.debug(f"Increase CUF of {str(asset)}")
        asset.cuf = CUF_UPPER_THRESHOLD
        assets_below_cuf_threshold.pop(0)

    return pathway


def decrease_cuf_of_assets(
    pathway: SimulationPathway, demand: float, product: str, year: int
) -> SimulationPathway:
    """Decrease CUF of assets to minimise the production surplus."""

    # Get AssetStack for the given year
    stack = pathway.get_stack(year)

    # Identify all assets that produce above CUF threshold and sort list so asset with highest LCOX is first
    assets_above_cuf_threshold = list(
        filter(lambda asset: asset.cuf < CUF_UPPER_THRESHOLD, stack.assets)
    )
    assets_above_cuf_threshold = sort_assets_lcox(
        assets_above_cuf_threshold, pathway, year, descending=True
    )

    # Decrease CUF of assets to lower threshold in order of descending LCOX until production meets demand or no assets left for CUF decrease
    while stack.get_annual_production_volume(product) > demand:

        if not assets_above_cuf_threshold:
            break

        # Increase CUF of asset with lowest LCOX to upper threshold and remove from list
        asset = assets_above_cuf_threshold[0]
        logger.debug(f"Decrease CUF of {str(asset)}")
        asset.cuf = CUF_UPPER_THRESHOLD
        assets_above_cuf_threshold.pop(0)

    return pathway


def sort_assets_lcox(
    assets: list, pathway: SimulationPathway, year: int, descending=False
):
    """Sort list of assets according to LCOX in the specified year in ascending order"""
    return sorted(
        assets,
        key=methodcaller("get_lcox", df_cost=pathway.df_cost, year=year),
        reverse=descending,
    )

""" Logic for technology transitions of type decommission (remove Asset from AssetStack)."""

import random

import pandas as pd
from mppshared.agent_logic.agent_logic_functions import (
    remove_transition,
    select_best_transition,
)
from mppshared.config import LOG_LEVEL
from mppshared.models.asset import Asset, AssetStack
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def get_best_asset_to_decommission(
    stack: AssetStack,
    df_rank: pd.DataFrame,
    product: str,
    year: int,
    cuf_lower_threshold: float,
    minimum_decommission_age: int,
) -> Asset:
    """Get best asset to decommission according to decommission ranking. Choose randomly if several assets have the same
    decommission ranking. Does not check whether removing the asset hurts any constraints.

    Args:
        stack:
        df_rank:
        product:
        year:
        cuf_lower_threshold:
        minimum_decommission_age:

    Returns:
        Asset to be decommissioned

    """
    # Get all assets eligible for decommissioning
    candidates = stack.get_assets_eligible_for_decommission(
        year=year,
        product=product,
        cuf_lower_threshold=cuf_lower_threshold,
        minimum_decommission_age=minimum_decommission_age,
    )
    # If no more assets to decommission, raise ValueError
    if not candidates:
        raise ValueError

    # Select best asset to decommission from the list of candidates
    logger.debug(f"Candidates for decommissioning: {len(candidates)}")

    best_candidates: list[Asset] = []
    while not best_candidates:

        best_transition = select_best_transition(df_rank)

        best_candidates = list(
            filter(
                lambda asset: (asset.technology == best_transition["technology_origin"])
                & (asset.region == best_transition["region"])
                & (asset.product == best_transition["product"]),
                candidates,
            )
        )

        # Remove best transition from ranking table
        df_rank = remove_transition(df_rank, best_transition)

    # If several candidates for best transition, choose randomly
    best_asset_to_decommission = random.choice(best_candidates)

    return best_asset_to_decommission


def get_best_asset_to_decommission_cement(
    stack: AssetStack,
    df_rank_region: pd.DataFrame,
    product: str,
    region: str,
    year: int,
) -> Asset:
    """Get best asset to decommission according to decommission ranking. Choose randomly if several assets have the same
    decommission ranking. Does not check whether removing the asset hurts any constraints.

    Args:
        stack:
        df_rank_region:
        product:
        region:
        year:

    Returns:
        Asset to be decommissioned

    """
    # Get all assets eligible for decommissioning
    candidates = stack.get_assets_eligible_for_decommission_cement(
        product=product, region=region, year=year
    )
    # If no more assets to decommission, raise ValueError
    if not candidates:
        raise ValueError

    # Select best asset to decommission from the list of candidates
    logger.debug(f"Candidates for decommissioning: {len(candidates)}")

    best_candidates: list[Asset] = []
    while not best_candidates:

        best_transition = select_best_transition(df_rank_region)

        best_candidates = list(
            filter(
                lambda asset: (asset.technology == best_transition["technology_origin"])
                & (asset.region == best_transition["region"])
                & (asset.product == best_transition["product"]),
                candidates,
            )
        )

        # Remove best transition from ranking table
        df_rank_region = remove_transition(
            df_rank=df_rank_region, transition=best_transition
        )

    # If several candidates for best transition, choose randomly
    best_asset_to_decommission = random.choice(best_candidates)

    return best_asset_to_decommission

""" Logic for technology transitions of type decommission (remove Asset from AssetStack)."""

from copy import deepcopy
from operator import methodcaller

import numpy as np
import pandas as pd
import random

from mppshared.agent_logic.agent_logic_functions import (
    remove_transition,
    select_best_transition,
)
from mppshared.config import LOG_LEVEL, MODEL_SCOPE
from mppshared.models.asset import Asset, AssetStack
from mppshared.models.constraints import check_constraints
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def decommission(pathway: SimulationPathway, year: int) -> SimulationPathway:
    """Apply decommission transition to eligible Assets in the AssetStack.

    Args:
        pathway: decarbonization pathway that describes the composition of the AssetStack in every year of the model horizon
        year: current year in which technology transitions are enacted

    Returns:
        Updated decarbonization pathway with the updated AssetStack in the subsequent year according to the decommission transitions enacted
    """

    for product in pathway.products:
        logger.info(f"Running decommission logic for {product}")
        # Current stack is for calculating production, next year's stack is updated with each decommissioning
        old_stack = pathway.get_stack(year=year)
        new_stack = pathway.get_stack(year=year + 1)

        # Get demand balance (demand - production)
        demand = pathway.get_demand(product, year, MODEL_SCOPE)
        production = old_stack.get_annual_production_volume(product)

        # Get ranking table for decommissioning
        df_rank = pathway.get_ranking(year=year, rank_type="decommission")
        df_rank = df_rank.loc[df_rank["product"] == product]

        # TODO: Decommission until one asset short of balance between demand and production
        surplus = production - demand
        logger.debug(
            f"Year: {year} Production: {production}, Demand: {demand}, Surplus: {surplus}"
        )
        while surplus > 0:

            # Identify asset to be decommissioned
            try:
                asset_to_remove = select_asset_to_decommission(
                    pathway=pathway,
                    stack=new_stack,
                    df_rank=df_rank,
                    product=product,
                    year=year,
                )

            except ValueError:
                logger.info("--No more assets to decommission")
                break

            logger.debug(
                f"--Removing asset with technology {asset_to_remove.technology} in region {asset_to_remove.region}, annual production {asset_to_remove.get_annual_production_volume()} and UUID {asset_to_remove.uuid}"
            )

            new_stack.remove(asset_to_remove)

            surplus -= asset_to_remove.get_annual_production_volume()

            pathway.transitions.add(
                transition_type="decommission", year=year, origin=asset_to_remove
            )

    return pathway


def select_asset_to_decommission(
    pathway: SimulationPathway,
    stack: AssetStack,
    df_rank: pd.DataFrame,
    product: str,
    year: int,
) -> Asset:
    """Select asset to decommission according to decommission ranking. Choose randomly if several assets have the same decommission ranking.

    Args:
        stack:
        df_rank:
        df_tech:

    Returns:
        Asset to be decommissioned

    """
    # Get all assets eligible for decommissioning
    candidates = stack.get_assets_eligible_for_decommission(
        year=year, sector=pathway.sector
    )
    logger.debug(f"Candidates for decommissioning: {len(candidates)}")

    while candidates:
        # Find assets can undergo the best transition. If there are no assets for the best transition, continue searching with the next-best transition
        best_candidates = []
        while not best_candidates:
            # Choose the best transition, i.e. highest decommission rank (filter )
            best_transition = select_best_transition(df_rank)

            best_candidates = list(
                filter(
                    lambda asset: (
                        asset.technology == best_transition["technology_origin"]
                    )
                    & (asset.region == best_transition["region"])
                    & (asset.product == best_transition["product"]),
                    candidates,
                )
            )

            # Remove best transition from ranking table
            df_rank = remove_transition(df_rank, best_transition)

        # If several candidates for best transition, choose randomly
        asset_to_remove = random.choice(best_candidates)

        # Remove asset tentatively (needs deepcopy to provide changes to original stack)
        tentative_stack = deepcopy(stack)
        tentative_stack.remove(asset_to_remove)

        # Check constraints with tentative new stack
        no_constraint_hurt = check_constraints(
            pathway=pathway,
            stack=tentative_stack,
            year=year,
            transition_type="decommission",
        )

        if no_constraint_hurt:
            return asset_to_remove

        # If constraint is hurt, remove asset from list of candidates and try again
        candidates.remove(asset_to_remove)

    # If no more assets to decommission, raise ValueError
    if not candidates:
        raise ValueError

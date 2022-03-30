""" Logic for technology transitions of type decommission (remove Asset from AssetStack)."""

from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.models.plant import PlantStack, Plant
from mppshared.agent_logic.agent_logic_functions import get_demand_balance

import pandas as pd
import logging

logger = logging.getLogger(__name__)
logger.setLevel("INFO")


def decommission(
    pathway: SimulationPathway, product: str, year: int
) -> SimulationPathway:
    """Apply decommission transition to eligible Assets in the AssetStack.

    Args:
        pathway: decarbonization pathway that describes the composition of the AssetStack in every year of the model horizon
        year: current year in which technology transitions are enacted
        product: product for which technology transitions are enacted

    Returns:
        Updated decarbonization pathway with the updated AssetStack in the subsequent year according to the decommission transitions enacted
    """
    # Current stack is for calculating production and selecting assets that can be decommissioned, next year's stack is updated with each decommissioning
    old_stack = pathway.get_stack(year=year)
    new_stack = pathway.get_stack(year=year + 1)

    # Get demand balance (demand - production)
    region = "Global"
    demand = pathway.get_demand(product, year, region)
    production = old_stack.get_annual_production(product)

    # Get ranking table for decommissioning
    df_rank = pathway.get_ranking(year=year, product=product, rank_type="decommission")

    # TODO: Decommission until one plant short of balance between demand and production
    surplus = production - demand
    while surplus > 0:

        # Identify asset to be decommissioned
        try:
            asset_to_remove = select_asset_to_decommission(
                stack=old_stack, df_rank=df_rank, product=product
            )

        except ValueError:
            logger.info("No more plants to decommission")
            break

        # TODO: check constraint that regional production satisfies given share of regional demand

        logger.info("Removing plant with technology %s", asset_to_remove.technology)

        # If the constraint is not hurt, remove the asset from next year's stack
        new_stack.remove(asset_to_remove)

        surplus -= asset_to_remove.get_annual_production(product)

        # TODO: implement logging of the asset transition
        pathway.transitions.add(
            transition_type="decommission", year=year, origin=asset_to_remove
        )

    return pathway


def select_asset_to_decommission(
    stack: PlantStack, df_rank: pd.DataFrame, product: str
) -> Plant:
    """Select asset to decommission according to decommission ranking. Choose randomly if several assets have the same decommission ranking.

    Args:
        stack:
        df_rank:
        df_tech:

    Returns:
        Plant to be decommissioned

    """
    # Get all assets eligible for decommissioning
    candidates = stack.get_assets_eligible_for_decommission()

    # Choose the best transition, i.e. highest decommission rank
    best_transition = select_best_transition(df_rank)

    # TODO: If several assets can undergo the best transition, choose the one with the smallest annual production capacity
    return candidates[0]


def select_best_transition(df_rank):
    """Based on the ranking, select the best transition

    Args:
        df_rank:

    Returns:
        The highest ranking technology transition

    """
    return (
        df_rank[df_rank["rank"] == df_rank["rank"].max()]
        .sample(n=1)
        .to_dict(orient="records")
    )[0]

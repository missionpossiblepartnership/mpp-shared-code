""" Logic for technology transitions of type decommission (remove Asset from AssetStack)."""

from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.models.plant import PlantStack, Plant
from mppshared.models.constraints import check_constraints
from mppshared.utility.utils import get_logger
from mppshared.config import LOG_LEVEL


import pandas as pd
import numpy as np
from operator import methodcaller
from copy import deepcopy
import logging

logger = logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


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
    # Current stack is for calculating production, next year's stack is updated with each decommissioning
    old_stack = pathway.get_stack(year=year)
    new_stack = pathway.get_stack(year=year + 1)

    #! Development only: force some assets to be decommissioned
    for i in np.arange(0, 5):
        new_stack.plants[i].capacity_factor = 0.5

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
                pathway=pathway,
                stack=new_stack,
                df_rank=df_rank,
                product=product,
                year=year,
            )

        except ValueError:
            logger.info("No more plants to decommission")
            break

        logger.info(
            f"Removing plant with technology {asset_to_remove.technology} in region {asset_to_remove.region}, annual production {asset_to_remove.get_annual_production(product)} and UUID {asset_to_remove.uuid}"
        )

        new_stack.remove(asset_to_remove)

        surplus -= asset_to_remove.get_annual_production(product)

        # TODO: implement logging of the asset transition
        # pathway.transitions.add(
        #     transition_type="decommission", year=year, origin=asset_to_remove
        # )

    return pathway


def select_asset_to_decommission(
    pathway: SimulationPathway,
    stack: PlantStack,
    df_rank: pd.DataFrame,
    product: str,
    year: int,
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

    # If no more assets to decommission, raise ValueError
    if not candidates:
        raise ValueError

    # Find assets can undergo the best transition. If there are no assets for the best transition, continue searching with the next-best transition
    best_candidates = []
    while not best_candidates:
        # Choose the best transition, i.e. highest decommission rank
        best_transition = select_best_transition(df_rank)

        best_candidates = list(
            filter(
                lambda plant: (plant.technology == best_transition["technology_origin"])
                & (plant.region == best_transition["region"])
                & (plant.product == best_transition["product"]),
                candidates,
            )
        )

        # Remove best transition from ranking table
        df_rank = remove_transition(df_rank, best_transition)

    # If several candidates for best transition, choose asset with lowest annual production
    # TODO: What happens if several assets have same annual production?
    asset_to_remove = min(
        best_candidates, key=methodcaller("get_annual_production", product)
    )

    # Remove asset tentatively (needs deepcopy to provide changes to original stack)
    tentative_stack = deepcopy(stack)
    tentative_stack.remove(asset_to_remove)

    # Check constraints with tentative new stack
    no_constraint_hurt = True
    # no_constraint_hurt = check_constraints(pathway, tentative_stack, product, year)

    if no_constraint_hurt:
        return asset_to_remove


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


def remove_transition(df_rank: pd.DataFrame, transition: dict) -> pd.DataFrame:
    """Filter transition from ranking table.

    Args:
        df_rank: table with ranking of technology switches
        transition: row from the ranking table

    Returns:
        ranking table with the row corresponding to the transition removed
    """
    return df_rank.loc[
        ~(df_rank[list(transition)] == pd.Series(transition)).all(axis=1)
    ]

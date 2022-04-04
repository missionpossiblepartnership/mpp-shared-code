""" Logic for technology transitions of type greenfield (add new Asset to AssetStack."""

from multiprocessing.sharedctypes import Value
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.models.asset import AssetStack, Asset, make_new_asset
from mppshared.agent_logic.agent_logic_functions import (
    select_best_transition,
    remove_transition,
)
from mppshared.models.constraints import check_constraints
from mppshared.utility.utils import get_logger
from mppshared.config import LOG_LEVEL, MODEL_SCOPE, ASSUMED_ANNUAL_PRODUCTION_CAPACITY


import pandas as pd
import numpy as np
from operator import methodcaller
from copy import deepcopy

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def greenfield(
    pathway: SimulationPathway, product: str, year: int
) -> SimulationPathway:
    """Apply greenfield transition and add new Assets to the AssetStack.

    Args:
        pathway: decarbonization pathway that describes the composition of the AssetStack in every year of the model horizon
        year: current year in which technology transitions are enacted
        product: product for which technology transitions are enacted

    Returns:
        Updated decarbonization pathway with the updated AssetStack in the subsequent year according to the greenfield transitions enacted
    """
    # Next year's stack is updated with each decommissioning
    new_stack = pathway.get_stack(year=year + 1)

    # Get process data
    df_process_data = pathway.get_all_process_data(product=product, year=year)

    # Get ranking table for greenfield transitions
    df_rank = pathway.get_ranking(product=product, year=year, rank_type="greenfield")

    # Get demand and production
    demand = pathway.get_demand(product=product, year=year, region=MODEL_SCOPE)
    production = new_stack.get_annual_production_volume(product)  #! Development only

    # Build new assets while demand exceeds production
    # TODO: Decommission until one asset short of balance between demand and production
    while demand > new_stack.get_annual_production_volume(product):

        # Identify asset for greenfield transition
        try:
            new_asset = select_asset_for_greenfield(
                pathway=pathway,
                stack=new_stack,
                df_rank=df_rank,
                product=product,
                year=year,
            )
        except ValueError:
            logger.info("No more assets for greenfield transition within constraints")
            break

        # Enact greenfield transition and add to TransitionRegistry
        logger.debug(
            f"Building new asset with technology {new_asset.technology} in region {new_asset.region}, annual production {new_asset.get_annual_production_volume()} and UUID {new_asset.uuid}"
        )

        new_stack.append(new_asset)
        pathway.transitions.add(
            transition_type="greenfield", year=year, destination=new_asset
        )

    production = new_stack.get_annual_production_volume(product)  #! Development only
    return pathway


def select_asset_for_greenfield(
    pathway: SimulationPathway,
    stack: AssetStack,
    df_rank: pd.DataFrame,
    product: str,
    year: int,
) -> Asset:
    """Select asset for newbuild (greenfield transition)

    Args:
        pathway:
        stack:
        df_rank:
        product:
        year

    Returns:
        Asset for greenfield transition

    """
    while not df_rank.empty:
        # Create new asset based on best transition in ranking table
        asset_transition = select_best_transition(
            df_rank=df_rank,
        )

        new_asset = make_new_asset(
            asset_transition=asset_transition,
            df_technology_characteristics=pathway.df_technology_characteristics,
            year=year,
        )

        # Tentatively update the stack and check constraints
        tentative_stack = deepcopy(stack)
        tentative_stack.append(new_asset)

        no_constraint_hurt = check_constraints(
            pathway=pathway, stack=tentative_stack, product=product, year=year
        )

        # Asset can be created if no constraint hurt
        if no_constraint_hurt:
            return new_asset

        # If constraint hurt, remove best transition from ranking table and try again
        df_rank = remove_transition(df_rank, asset_transition)

    # If ranking table empty, no greenfield construction possible
    raise ValueError

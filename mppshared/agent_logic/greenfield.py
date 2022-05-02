""" Logic for technology transitions of type greenfield (add new Asset to AssetStack."""

from copy import deepcopy
from importlib.resources import path
from multiprocessing.sharedctypes import Value
from operator import methodcaller

import numpy as np
import pandas as pd

from mppshared.agent_logic.agent_logic_functions import (
    remove_transition,
    select_best_transition,
)
from mppshared.config import ASSUMED_ANNUAL_PRODUCTION_CAPACITY, LOG_LEVEL, MODEL_SCOPE
from mppshared.models.asset import Asset, AssetStack, make_new_asset
from mppshared.models.constraints import (
    check_constraints,
    get_regional_production_constraint_table,
)
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.utility.utils import get_logger

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
    logger.info(f"Starting greenfield transition logic for year {year}")
    # Next year's stack is updated with each decommissioning
    new_stack = pathway.get_stack(year=year + 1)

    # Get ranking table for greenfield transitions
    df_rank = pathway.get_ranking(product=product, year=year, rank_type="greenfield")

    # Get demand and production
    demand = pathway.get_demand(product=product, year=year, region=MODEL_SCOPE)
    production = new_stack.get_annual_production_volume(product)  #! Development only

    # STEP ONE: BUILD NEW CAPACITY BY REGION
    # First, build new capacity in each region to make sure that the regional production constraint is met even if regional demand increases
    df_regional_production = get_regional_production_constraint_table(
        pathway=pathway, stack=new_stack, product=product, year=year
    )

    # For each region with a production deficit, build new capacity until production meets required minimum
    for (index, row) in df_regional_production.loc[
        df_regional_production["check"] == False
    ].iterrows():
        deficit = (
            row["annual_production_volume_minimum"] - row["annual_production_volume"]
        )
        number_new_assets = np.ceil(deficit / ASSUMED_ANNUAL_PRODUCTION_CAPACITY)
        df_rank_region = df_rank.loc[df_rank["region"] == row["region"]]

        # Build the required number of assets to meet the minimum production volume
        while number_new_assets >= 1:
            try:
                new_asset = select_asset_for_greenfield(
                    pathway=pathway,
                    stack=new_stack,
                    df_rank=df_rank_region,
                    product=product,
                    year=year,
                )
                enact_greenfield_transition(
                    pathway=pathway, stack=new_stack, new_asset=new_asset, year=year
                )
                number_new_assets -= 1
            except ValueError:
                logger.info(
                    "No more assets for greenfield transition within constraints"
                )
                break

    # STEP TWO: BUILD NEW CAPACITY GLOBALLY
    # Build new assets while demand exceeds production
    production = new_stack.get_annual_production_volume(product)  #! Development only
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

        # Enact greenfield transition
        logger.debug(
            f"Building new asset with technology {new_asset.technology} in region {new_asset.region}, annual production {new_asset.get_annual_production_volume()} and UUID {new_asset.uuid}"
        )
        enact_greenfield_transition(
            pathway=pathway, stack=new_stack, new_asset=new_asset, year=year
        )
        
    production = new_stack.get_annual_production_volume(product)  #! Development only
    return pathway


def enact_greenfield_transition(
    pathway: SimulationPathway, stack: AssetStack, new_asset: Asset, year: int
):
    """Append new asset to stack and add entry to logger and TransitionRegistry."""

    # Enact greenfield transition and add to TransitionRegistry
    logger.debug(
        f"Building new asset with technology {new_asset.technology} in region {new_asset.region}, annual production {new_asset.get_annual_production_volume()} and UUID {new_asset.uuid}"
    )

    stack.append(new_asset)
    pathway.transitions.add(
        transition_type="greenfield", year=year, destination=new_asset
    )


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
        if pathway.pathway != "BAU":
            no_constraint_hurt = check_constraints(
                pathway=pathway,
                stack=tentative_stack,
                product=product,
                year=year,
                transition_type="greenfield",
            )
        else:
            no_constraint_hurt = True

        # Asset can be created if no constraint hurt
        if no_constraint_hurt:
            return new_asset

        # If constraint hurt, remove best transition from ranking table and try again
        df_rank = remove_transition(df_rank, asset_transition)

    # If ranking table empty, no greenfield construction possible
    raise ValueError

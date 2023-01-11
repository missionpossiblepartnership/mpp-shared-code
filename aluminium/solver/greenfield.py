""" Logic for technology transitions of type greenfield (add new Asset to AssetStack."""
import sys
from copy import deepcopy
from importlib.resources import path
from multiprocessing.sharedctypes import Value
from operator import methodcaller

import numpy as np
import pandas as pd
from aluminium.config_aluminium import (
    ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
    CUF_UPPER_THRESHOLD,
    LOG_LEVEL,
    MODEL_SCOPE,
)
from mppshared.agent_logic.greenfield import (
    enact_greenfield_transition,
    get_region_rank_filter,
    select_asset_for_greenfield,
)
from mppshared.models.asset import Asset, AssetStack, make_new_asset
from mppshared.models.constraints import (
    check_constraints,
    get_regional_production_constraint_table,
    hydro_constraints,
)
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def greenfield(pathway: SimulationPathway, year: int) -> SimulationPathway:
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
    df_ranking = pathway.get_ranking(year=year, rank_type="greenfield")

    # Hydro constrain for new-builds in aluminium
    df_ranking = hydro_constraints(df_ranking, pathway.sector)

    # Greenfield for each product sequentially
    for product in pathway.products:
        df_rank = df_ranking.loc[df_ranking["product"] == product]
        # Get demand and production
        demand = pathway.get_demand(product=product, year=year, region=MODEL_SCOPE)
        production = new_stack.get_annual_production_volume(
            product
        )  #! Development only

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
                row["annual_production_volume_minimum"]
                - row["annual_production_volume"]
            )
            number_new_assets = np.ceil(
                deficit / (ASSUMED_ANNUAL_PRODUCTION_CAPACITY * CUF_UPPER_THRESHOLD)
            )
            region_rank_filter = get_region_rank_filter(
                region=row["region"], sector=pathway.sector
            )
            df_rank_region = df_rank.loc[df_rank["region"].isin(region_rank_filter)]

            # Build the required number of assets to meet the minimum production volume
            while number_new_assets >= 1:
                try:
                    new_asset = select_asset_for_greenfield(
                        pathway=pathway,
                        stack=new_stack,
                        df_rank=df_rank_region,
                        product=product,
                        year=year,
                        annual_production_capacity=ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
                        cuf=CUF_UPPER_THRESHOLD,
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
        production = new_stack.get_annual_production_volume(
            product
        )  #! Development only
        while demand > production:

            # Identify asset for greenfield transition
            try:
                new_asset = select_asset_for_greenfield(
                    pathway=pathway,
                    stack=new_stack,
                    df_rank=df_rank,
                    product=product,
                    year=year,
                    annual_production_capacity=ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
                    cuf=CUF_UPPER_THRESHOLD,
                )
            except ValueError:
                logger.info(
                    "No more assets for greenfield transition within constraints"
                )
                break

            # Enact greenfield transition
            logger.debug(
                f"Building new asset with technology {new_asset.technology} in region {new_asset.region}, annual production {new_asset.get_annual_production_volume()} and UUID {new_asset.uuid}"
            )
            enact_greenfield_transition(
                pathway=pathway, stack=new_stack, new_asset=new_asset, year=year
            )
            production = new_stack.get_annual_production_volume(
                product
            )  #! Development only
    return pathway

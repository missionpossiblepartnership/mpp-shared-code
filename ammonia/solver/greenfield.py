""" Logic for technology transitions of type greenfield (add new Asset to AssetStack."""

from copy import deepcopy
from importlib.resources import path
from multiprocessing.sharedctypes import Value
from operator import methodcaller

import numpy as np
import pandas as pd

from ammonia.config_ammonia import (ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
                                    ASSUMED_ANNUAL_PRODUCTION_CAPACITY_MT,
                                    BUILD_CURRENT_PROJECT_PIPELINE, LOG_LEVEL,
                                    MAP_LOW_COST_POWER_REGIONS,
                                    MAXIMUM_GLOBAL_DEMAND_SHARE_ONE_REGION,
                                    MODEL_SCOPE, REGIONAL_TECHNOLOGY_BAN,
                                    REGIONS)
from mppshared.agent_logic.agent_logic_functions import (
    apply_regional_technology_ban,
    remove_all_transitions_with_destination_technology, remove_transition,
    select_best_transition)
from mppshared.models.asset import (Asset, AssetStack, make_new_asset,
                                    make_new_asset_project_pipeline)
from mppshared.models.constraints import (
    check_constraints, get_regional_production_constraint_table)
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.solver.implicit_forcing import apply_regional_technology_ban
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
    current_stack = pathway.get_stack(year)
    new_stack = pathway.get_stack(year=year + 1)

    # Get ranking table for greenfield transitions
    df_ranking = pathway.get_ranking(year=year, rank_type="greenfield")

    # Apply regional technology bans
    df_ranking = apply_regional_technology_ban(
        df_ranking, REGIONAL_TECHNOLOGY_BAN[pathway.sector]
    )

    # Greenfield for each product sequentially
    for product in pathway.products:
        df_rank = df_ranking.loc[df_ranking["product"] == product]

        # Build current project pipeline if desired
        if BUILD_CURRENT_PROJECT_PIPELINE:

            #! Development only
            demand = pathway.get_demand(
                product=product, year=year + 1, region=MODEL_SCOPE
            )
            production = new_stack.get_annual_production_volume(product)
            # Format current project pipeline for this year
            df_pipeline = pathway.importer.get_project_pipeline()
            df_pipeline = df_pipeline.melt(
                id_vars=["region", "product", "technology"],
                var_name="year",
                value_name="production_capacity_addition",
            )
            df_pipeline["year"] = df_pipeline["year"].astype(int)
            df_pipeline = df_pipeline.loc[df_pipeline["year"] == year]
            df_pipeline = df_pipeline.loc[df_pipeline["product"] == product]

            # Build new capacity in the regions where production capacity is added
            build_regions = df_pipeline.loc[
                df_pipeline["production_capacity_addition"] > 0, "region"
            ].unique()
            for region in build_regions:
                df_pipeline_region = df_pipeline.loc[df_pipeline["region"] == region]

                # Filter newbuild technologies
                build_techs = df_pipeline_region.loc[
                    df_pipeline_region["production_capacity_addition"] > 0, "technology"
                ].unique()
                for tech in build_techs:
                    df_asset = df_pipeline_region.loc[
                        df_pipeline_region["technology"] == tech
                    ]

                new_asset = make_new_asset_project_pipeline(
                    region=region,
                    product=df_asset["product"].item(),
                    annual_production_capacity_mt=df_asset[
                        "production_capacity_addition"
                    ].item(),
                    technology=df_asset["technology"].item(),
                    df_technology_characteristics=pathway.df_technology_characteristics,
                    year=year,
                )

                enact_greenfield_transition(
                    pathway=pathway,
                    stack=new_stack,
                    new_asset=new_asset,
                    year=year,
                    project_pipeline=True,
                )

        if pathway.sector == "chemicals":
            df_rank = apply_greenfield_filters_chemicals(
                df_rank, pathway, year, product
            )

        # Get demand (for next year) and production (in current year)
        demand = pathway.get_demand(product=product, year=year + 1, region=MODEL_SCOPE)
        production = new_stack.get_annual_production_volume(
            product
        )  #! Development only

        # Create DataFrame of maximum plant additions in each region
        df_region_demand = create_dataframe_check_regional_share_global_demand(
            demand=demand,
            production=production,
            product=product,
            pathway=pathway,
            current_stack=current_stack,
        )

        # STEP ONE: BUILD NEW CAPACITY BY REGION
        # First, build new capacity in each region to make sure that the regional production constraint is met even if regional demand increases
        df_regional_production = get_regional_production_constraint_table(
            pathway=pathway, stack=new_stack, product=product, year=year
        )

        # For each region with a production deficit, build new capacity until production meets required minimum
        for (_, row) in df_regional_production.loc[
            df_regional_production["check"] == False
        ].iterrows():
            deficit = (
                row["annual_production_volume_minimum"]
                - row["annual_production_volume"]
            )
            number_new_assets = int(
                np.ceil(deficit / ASSUMED_ANNUAL_PRODUCTION_CAPACITY_MT[product])
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
                        year=year,
                        df_region_demand=df_region_demand,
                    )
                    enact_greenfield_transition(
                        pathway=pathway,
                        stack=new_stack,
                        new_asset=new_asset,
                        year=year,
                    )
                    number_new_assets -= 1

                    # Add one plant to regional supply constraint DataFrame
                    df_region_demand.loc[
                        new_asset.region, "region_newbuild_additions"
                    ] += 1
                except ValueError:
                    logger.info(
                        "No more assets for greenfield transition within constraints"
                    )
                    break

        # STEP TWO: BUILD NEW CAPACITY GLOBALLY
        # Build new assets while demand exceeds production
        production = new_stack.get_annual_production_volume(product)

        while demand > new_stack.get_annual_production_volume(product):

            # Identify asset for greenfield transition
            try:
                new_asset = select_asset_for_greenfield(
                    pathway=pathway,
                    stack=new_stack,
                    df_rank=df_rank,
                    year=year,
                    df_region_demand=df_region_demand,
                )
            except ValueError:
                logger.info(
                    "No more assets for greenfield transition within constraints"
                )
                break

            # Enact greenfield transition
            enact_greenfield_transition(
                pathway=pathway, stack=new_stack, new_asset=new_asset, year=year
            )

            # Add one plant to regional supply constraint DataFrame
            df_region_demand.loc[new_asset.region, "region_newbuild_additions"] += 1

        production = new_stack.get_annual_production_volume(
            product
        )  #! Development only
        deficit = production - demand
        pass
    return pathway

""" Logic for technology transitions of type greenfield (add new Asset to AssetStack."""
import sys
from copy import deepcopy

import numpy as np
import pandas as pd

from mppshared.agent_logic.agent_logic_functions import (
    remove_all_transitions_with_destination_technology, remove_transition,
    select_best_transition)
from mppshared.config import (ASSUMED_ANNUAL_PRODUCTION_CAPACITY, LOG_LEVEL,
                              MAP_LOW_COST_POWER_REGIONS, MODEL_SCOPE)
from mppshared.models.asset import Asset, AssetStack, make_new_asset
from mppshared.models.constraints import (
    get_regional_production_constraint_table, hydro_constraints)
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def greenfield_default(pathway: SimulationPathway, year: int) -> SimulationPathway:
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
        logger.debug(
            f"Demand: {demand}, production: {production}, difference {demand - production}"
        )

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
            number_new_assets = np.ceil(deficit / ASSUMED_ANNUAL_PRODUCTION_CAPACITY)
            region_rank_filter = get_region_rank_filter(
                region=row["region"], sector=pathway.sector
            )
            df_rank_region = df_rank.loc[df_rank["region"].isin(region_rank_filter)]

            # Build the required number of assets to meet the minimum production volume
            while number_new_assets >= 1:
                logger.debug(
                    f"Building {number_new_assets} to meet the regional demand"
                )
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
        production = new_stack.get_annual_production_volume(
            product
        )  #! Development only
        while round(demand, 2) > round(production, 2):
            logger.debug(
                f"Demand ({demand}), higher than production ({production}), difference: {demand - production}"
            )

            # Identify asset for greenfield transition
            try:
                new_asset = select_asset_for_greenfield(
                    pathway=pathway,
                    stack=new_stack,
                    df_rank=df_rank,
                    product=product,
                    year=year,
                )
                logger.debug(
                    f"Tentative new asset with technology {new_asset.technology} in region {new_asset.region}, annual production {new_asset.get_annual_production_volume()} and UUID {new_asset.uuid}"
                )
                # Enact greenfield transition
                # logger.debug(
                #     f"Building new asset with technology {new_asset.technology} in region {new_asset.region}, annual production {new_asset.get_annual_production_volume()} and UUID {new_asset.uuid}"
                # )
                enact_greenfield_transition(
                    pathway=pathway, stack=new_stack, new_asset=new_asset, year=year
                )
                production = new_stack.get_annual_production_volume(
                    product
                )  #! Development only
            except ValueError:
                logger.info(
                    "No more assets for greenfield transition within constraints"
                )
                break
    return pathway


def enact_greenfield_transition(
    pathway: SimulationPathway,
    stack: AssetStack,
    new_asset: Asset,
    year: int,
    project_pipeline=False,
):
    """Append new asset to stack and add entry to logger and TransitionRegistry."""

    # Enact greenfield transition and add to TransitionRegistry
    logger.debug(
        f"Building new asset with technology {new_asset.technology} in region {new_asset.region}, annual production {new_asset.get_annual_production_volume()} and UUID {new_asset.uuid}. From project pipeline: {project_pipeline}"
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
    annual_production_capacity: float,
    cuf: float,
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
            annual_production_capacity=annual_production_capacity,
            cuf=cuf,
            emission_scopes=pathway.emission_scopes,
            cuf_lower_threshold=pathway.cuf_lower_threshold,
            ghgs=pathway.ghgs,
        )
        new_asset.greenfield = True

        # Tentatively update the stack and check constraints
        tentative_stack = deepcopy(stack)
        tentative_stack.append(new_asset)

        # TODO: Remove comment after modifying constraints to work with all the sectors/pathways
        # TODO: Remove hardcoded dictionary to use the one from the constraints
        dict_constraints = {
            "emissions_constraint": True,
            "rampup_constraint": True,
            "flag_residual": False,
        }
        # dict_constraints = check_constraints(
        #     pathway=pathway,
        #     stack=tentative_stack,
        #     year=year,
        #     transition_type="greenfield",
        # )

        # Asset can be created if no constraint hurt
        if (dict_constraints["emissions_constraint"] == True) & (
            dict_constraints["rampup_constraint"] == True
        ):
            return new_asset

        # If annual emissions constraint hurt, remove best transition from ranking table and try again
        if dict_constraints["emissions_constraint"] == False:
            df_rank = remove_transition(df_rank, asset_transition)

        # If residual emissions constraint hurt, remove all transitions with CCS (i.e. with residual emissions)
        elif (dict_constraints["emissions_constraint"] == False) & (
            dict_constraints["flag_residual"] == True
        ):
            df_rank = df_rank.loc[
                ~(df_rank["technology_destination"].str.contains("CCS"))
            ]

        # If only technology ramp-up constraint hurt, remove all transitions with that destination technology from the ranking table
        elif dict_constraints["rampup_constraint"] == False:
            df_rank = remove_all_transitions_with_destination_technology(
                df_rank, asset_transition["technology_destination"]
            )

    # If ranking table empty, no greenfield construction possible
    raise ValueError


def get_region_rank_filter(region: str, sector: str) -> list:
    """Return list of (sub)regions if the sector has low-cost power regions mapped to the overall regions"""
    if MAP_LOW_COST_POWER_REGIONS[sector]:
        if region in MAP_LOW_COST_POWER_REGIONS[sector].keys():
            return [region, MAP_LOW_COST_POWER_REGIONS[sector][region]]
    return [region]


def create_dataframe_check_regional_share_global_demand(
    demand: float,
    production: float,
    product: str,
    pathway: SimulationPathway,
    current_stack: AssetStack,
    assumed_annual_production_capacity_mt: dict,
    regions: list,
    maximum_global_demand_share_one_region: float,
) -> pd.DataFrame:
    """Create DataFrame that shows maximum plant additions in each region such that the constraint that each region can supply a maximum share of new demand is fulfilled."""

    global_required_plant_additions = np.ceil(
        (demand - production) / assumed_annual_production_capacity_mt[product]
    )
    global_plants_newbuild = current_stack.get_number_of_assets(
        status="greenfield_status"
    )
    df_region_demand = pd.DataFrame(
        index=regions,
        data={
            "global_plants_newbuild_proposed": global_plants_newbuild
            + global_required_plant_additions
        },
    )
    for region in regions:
        df_region_demand.loc[
            region, "region_plants_newbuild"
        ] = current_stack.get_number_of_assets(
            region=region, status="greenfield_status"
        )

    df_region_demand["region_max_plants_newbuild"] = np.ceil(
        maximum_global_demand_share_one_region
        * df_region_demand["global_plants_newbuild_proposed"]
        - df_region_demand["region_plants_newbuild"]
    )

    df_region_demand["region_newbuild_additions"] = 0

    return df_region_demand

""" Logic for technology transitions of type greenfield (add new Asset to AssetStack."""

from copy import deepcopy
from importlib.resources import path
from multiprocessing.sharedctypes import Value
from operator import methodcaller

import numpy as np
import pandas as pd

from mppshared.agent_logic.agent_logic_functions import (
    remove_all_transitions_with_destination_technology,
    remove_transition,
    select_best_transition,
    apply_regional_technology_ban,
)
from mppshared.config import (
    ASSUMED_ANNUAL_PRODUCTION_CAPACITY_MT,
    LOG_LEVEL,
    MAP_LOW_COST_POWER_REGIONS,
    MAXIMUM_GLOBAL_DEMAND_SHARE_ONE_REGION,
    MODEL_SCOPE,
    REGIONAL_TECHNOLOGY_BAN,
    REGIONS,
)
from mppshared.models.asset import Asset, AssetStack, make_new_asset
from mppshared.models.constraints import (
    check_constraints,
    get_regional_production_constraint_table,
)
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

        if pathway.sector == "chemicals":
            df_rank = apply_greenfield_filters_chemicals(
                df_rank, pathway, year, product
            )

        # Get demand and production
        demand = pathway.get_demand(product=product, year=year, region=MODEL_SCOPE)
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
    return pathway


def create_dataframe_check_regional_share_global_demand(
    demand: float,
    production: float,
    product: str,
    pathway: SimulationPathway,
    current_stack: AssetStack,
) -> pd.DataFrame:
    """Create DataFrame that shows maximum plant additions in each region such that the constraint that each region can supply a maximum share of new demand is fulfilled."""

    global_required_plant_additions = np.ceil(
        (demand - production) / ASSUMED_ANNUAL_PRODUCTION_CAPACITY_MT[product]
    )
    global_plants_newbuild = current_stack.get_number_of_assets(
        status="greenfield_status"
    )
    df_region_demand = pd.DataFrame(
        index=REGIONS[pathway.sector],
        data={
            "global_plants_newbuild_proposed": global_plants_newbuild
            + global_required_plant_additions
        },
    )
    for region in REGIONS[pathway.sector]:
        df_region_demand.loc[
            region, "region_plants_newbuild"
        ] = current_stack.get_number_of_assets(
            region=region, status="greenfield_status"
        )

    df_region_demand["region_max_plants_newbuild"] = np.ceil(
        MAXIMUM_GLOBAL_DEMAND_SHARE_ONE_REGION[pathway.sector]
        * df_region_demand["global_plants_newbuild_proposed"]
        - df_region_demand["region_plants_newbuild"]
    )

    df_region_demand["region_newbuild_additions"] = 0

    return df_region_demand


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
    year: int,
    df_region_demand: pd.DataFrame,
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
        # Check if regional supply constraint is met
        regional_supply_constraint_hurt = (
            df_region_demand.loc[
                asset_transition["region"], "region_newbuild_additions"
            ]
            >= df_region_demand.loc[
                asset_transition["region"], "region_max_plants_newbuild"
            ]
        )
        if regional_supply_constraint_hurt == True:
            df_rank = df_rank.loc[df_rank["region"] != asset_transition["region"]]
            logger.debug(
                f"Region {asset_transition['region']} already supplies {MAXIMUM_GLOBAL_DEMAND_SHARE_ONE_REGION[pathway.sector]*100} % of global demand."
            )

        else:
            new_asset = make_new_asset(
                asset_transition=asset_transition,
                df_technology_characteristics=pathway.df_technology_characteristics,
                year=year,
            )
            new_asset.greenfield = True

            # Tentatively update the stack and check constraints
            tentative_stack = deepcopy(stack)
            tentative_stack.append(new_asset)
            dict_constraints = check_constraints(
                pathway=pathway,
                stack=tentative_stack,
                year=year,
                transition_type="greenfield",
            )

            # Asset can be created if no constraint hurt
            if all(constraint == True for constraint in dict_constraints.values()):
                return new_asset

            # If annual emissions constraint hurt, remove best transition from ranking table and try again
            if dict_constraints["emissions_constraint"] == False:
                df_rank = remove_transition(df_rank, asset_transition)

            # If residual emissions constraint hurt, remove all transitions with CCS (i.e. with residual emissions)
            # elif (dict_constraints["emissions_constraint"] == False) & (
            #     dict_constraints["flag_residual"] == True
            # ):
            #     df_rank = df_rank.loc[
            #         ~(df_rank["technology_destination"].str.contains("CCS"))
            #     ]

            # If only technology ramp-up constraint or CO2 storage constraint is hurt, remove all transitions with that destination technology from the ranking table
            elif (dict_constraints["rampup_constraint"] == False) | (
                dict_constraints["co2_storage_constraint"] == False
            ):
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


def apply_greenfield_filters_chemicals(
    df_rank: pd.DataFrame, pathway: SimulationPathway, year: int, product: str
) -> pd.DataFrame:
    """For chemicals, new ammonia demand can only be supplied by transition and end-state technologies,
    while new urea and ammonium nitrate demand can also be supplied by initial technologies"""
    if product == "Ammonia":
        filter = df_rank["technology_classification"] == "initial"
        df_rank = df_rank.loc[~filter]
        return df_rank
    return df_rank

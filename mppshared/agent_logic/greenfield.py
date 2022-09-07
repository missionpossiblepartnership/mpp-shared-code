""" Logic for technology transitions of type greenfield (add new Asset to AssetStack."""

import sys
from copy import deepcopy

import numpy as np
import pandas as pd

from mppshared.agent_logic.agent_logic_functions import (
    remove_all_transitions_with_destination_technology,
    remove_techs_in_region_by_tech_substr,
    remove_transition,
    select_best_transition,
)
from mppshared.config import (
    ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
    CUF_UPPER_THRESHOLD,
    LOG_LEVEL,
    MAP_LOW_COST_POWER_REGIONS,
    MODEL_SCOPE,
)
from mppshared.models.asset import Asset, AssetStack, make_new_asset
from mppshared.models.constraints import (
    check_alternative_fuel_constraint,
    check_constraints,
    check_natural_gas_constraint,
    check_co2_storage_constraint,
)
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def greenfield_default(pathway: SimulationPathway, year: int) -> SimulationPathway:
    """Apply greenfield transition and add new Assets to the AssetStack.
    Args:
        pathway: decarbonization pathway that describes the composition of the AssetStack in every year of the model
            horizon
        year: current year in which technology transitions are enacted
    Returns:
        Updated decarbonization pathway with the updated AssetStack in the subsequent year according to the greenfield
            transitions enacted
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
                    annual_production_capacity=ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
                    cuf=CUF_UPPER_THRESHOLD,
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
        f"{year}: Building new asset in {new_asset.region} (technology: {new_asset.technology}, annual production: "
        f"{new_asset.get_annual_production_volume()}, UUID: {new_asset.uuid}). "
        f"From project pipeline: {project_pipeline}"
    )

    stack.append(new_asset)
    pathway.transitions.add(
        transition_type="greenfield", year=year, destination=new_asset
    )


def select_asset_for_greenfield(
    pathway: SimulationPathway,
    stack: AssetStack,
    product: str,
    df_rank: pd.DataFrame,
    year: int,
    annual_production_capacity: float,
    cuf: float,
    df_region_demand: pd.DataFrame = None,
    region_global_demand_share: float = None,
    return_df_rank: bool = False,
    constraints_regional_check: bool = False,
):
    """Select asset for newbuild (greenfield transition)
    Args:
        pathway:
        stack:
        product:
        df_rank:
        year:
        annual_production_capacity:
        cuf:
        df_region_demand (optional): df to check whether the regional supply constraint is met
        region_global_demand_share (optional): df to check whether the regional supply constraint is met
        return_df_rank: function returns updated df_rank if True
        constraints_regional_check: set True if constraints shall only be checked regionally (if applicable)
    Returns:
        Asset for greenfield transition
    """
    while not df_rank.empty:
        # Create new asset based on best transition in ranking table
        asset_transition = select_best_transition(
            df_rank=df_rank,
        )

        # Check constraint on regional supply (if desired)
        if df_region_demand is not None:
            # Check if regional supply constraint is met
            regional_supply_constraint_hurt = (
                df_region_demand.loc[
                    asset_transition["region"], "region_newbuild_additions"
                ]
                >= df_region_demand.loc[
                    asset_transition["region"], "region_max_plants_newbuild"
                ]
            )
            
            # Remove greenfield switches in that region if regional supply constraint hurt
            if regional_supply_constraint_hurt:
                df_rank = df_rank.loc[df_rank["region"] != asset_transition["region"]]
                logger.debug(
                    f"Region {asset_transition['region']} already supplies {region_global_demand_share * 100} % of "
                    f"global demand."
                )

                # move to next iteration
                continue
                
        # Make new asset and check the constraints
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
        logger.debug(
            f"{year}: Attempting to build asset in {new_asset.region} (technology: {new_asset.technology})"
        )
        tentative_stack = deepcopy(stack)
        tentative_stack.append(new_asset)

        dict_constraints = check_constraints(
            pathway=pathway,
            stack=tentative_stack,
            year=year,
            transition_type="greenfield",
            product=product,
            region=new_asset.region if constraints_regional_check else None,
        )

        # Ensure that newbuild capacity from project pipeline does not lead to erroneous constraint violation
        if "CCS" not in asset_transition["technology_destination"]:
            dict_constraints["co2_storage_constraint"] = True
        if "Electrolyser" not in asset_transition["technology_destination"]:
            dict_constraints["electrolysis_capacity_addition_constraint"] = True

        # Asset can be created if no constraint hurt
        if all(
                [
                    dict_constraints[k]
                    for k in dict_constraints.keys()
                    if k in pathway.constraints_to_apply and k != "regional_constraint"
                ]
        ):
            logger.debug(f"{year}: All constraints fulfilled.")
            if return_df_rank:
                return new_asset, df_rank
            else:
                return new_asset
        else:
            # EMISSIONS
            if "emissions_constraint" in pathway.constraints_to_apply:
                if (
                        not dict_constraints["emissions_constraint"]
                        and not dict_constraints["flag_residual"]
                ):
                    # remove best transition from ranking table and try again
                    logger.debug(
                        f"Handle emissions constraint: removing destination technology"
                    )
                    df_rank = remove_all_transitions_with_destination_technology(
                        df_rank=df_rank,
                        technology_destination=asset_transition[
                            "technology_destination"
                        ],
                    )
                if (
                        not dict_constraints["emissions_constraint"]
                        and dict_constraints["flag_residual"]
                ):
                    logger.debug(
                        f"Handle (residual) emissions constraint: removing all transitions with CCS"
                    )
                    # remove all transitions with CCS (i.e. with residual emissions)
                    df_rank = df_rank.loc[
                        ~(df_rank["technology_destination"].str.contains("CCS"))
                    ]

            # ELECTROLYSIS CAPACITY ADDITION
            if (
                "electrolysis_capacity_addition_constraint"
                in pathway.constraints_to_apply
            ):
                if not dict_constraints[
                    "electrolysis_capacity_addition_constraint"
                ]:
                    # Remove all transitions with that destination technology from the ranking table
                    logger.debug(
                        f"Handle electrolysis capacity addition constraint: removing destination technology"
                    )
                    logger.debug(
                        f"Handle (residual) emissions constraint: removing all transitions with CCS"
                    )
                    # remove all transitions with CCS (i.e. with residual emissions)
                    df_rank = df_rank.loc[
                        ~(df_rank["technology_destination"].str.contains("CCS"))
                    ]
                    
            # RAMPUP
            if "rampup_constraint" in pathway.constraints_to_apply:
                if not dict_constraints["rampup_constraint"]:
                    # remove all transitions with that destination technology from the ranking table
                    logger.debug(
                        f"Handle ramp up constraint: removing destination technology"
                    )
                    df_rank = remove_all_transitions_with_destination_technology(
                        df_rank=df_rank,
                        technology_destination=asset_transition[
                            "technology_destination"
                        ],
                    )

            # CO2 STORAGE
            if "co2_storage_constraint" in pathway.constraints_to_apply:
                if not dict_constraints["co2_storage_constraint"]:
                    # "total_cumulative" requires regional approach
                    if pathway.co2_storage_constraint_type == "total_cumulative":
                        if constraints_regional_check:
                            # remove destination technology in exceeding region from ranking
                            logger.debug(
                                f"Handle CO2 storage constraint: removing destination technology "
                                f"in {new_asset.region}"
                            )
                            df_rank = remove_all_transitions_with_destination_technology(
                                df_rank=df_rank,
                                technology_destination=asset_transition[
                                    "technology_destination"
                                ],
                                region=new_asset.region,
                            )
                        else:
                            # get regions where CO2 storage constraint is exceeded
                            dict_co2_storage_exceedance = (
                                check_co2_storage_constraint(
                                    pathway=pathway,
                                    product=product,
                                    stack=tentative_stack,
                                    year=year,
                                    transition_type="greenfield",
                                    return_dict=True,
                                )
                            )
                            exceeding_regions = [
                                k
                                for k in dict_co2_storage_exceedance.keys()
                                if not dict_co2_storage_exceedance[k]
                            ]
                            # check if regions other than the tentatively updated asset's region exceed the constraint
                            if exceeding_regions != [new_asset.region]:
                                sys.exit(
                                    f"{year}: Regions other than the tentatively updated asset's region exceed the CO2 "
                                    "storage constraint!"
                                )
                            else:
                                # remove destination technology in exceeding region from ranking
                                logger.debug(
                                    f"Handle CO2 storage constraint: removing destination technology "
                                    f"in {new_asset.region}"
                                )
                                df_rank = remove_all_transitions_with_destination_technology(
                                    df_rank=df_rank,
                                    technology_destination=asset_transition[
                                        "technology_destination"
                                    ],
                                    region=new_asset.region,
                                )
                    # co2_storage_constraint_type other than total_cumulative are global
                    else:
                        # Remove all transitions with that destination technology from the ranking table
                        logger.debug(
                            f"Handle CO2 storage constraint: removing destination technology"
                        )
                        df_rank = remove_all_transitions_with_destination_technology(
                            df_rank, asset_transition["technology_destination"]
                        )

            # GLOBAL DEMAND SHARE
            if "demand_share_constraint" in pathway.constraints_to_apply:
                if not dict_constraints["demand_share_constraint"]:
                    # Remove all transitions with that destination technology from the ranking table
                    logger.debug(
                        f"Handle global demand share constraint: removing destination technology"
                    )
                    df_rank = remove_all_transitions_with_destination_technology(
                        df_rank, asset_transition["technology_destination"]
                    )

            # REGIONAL PRODUCTION
            if "regional_constraint" in pathway.constraints_to_apply:
                if not dict_constraints["regional_constraint"]:
                    # todo
                    logger.critical(
                        f"WARNING: Regional production constraint not fulfilled in {year}."
                    )

            # ALTERNATIVE FUEL
            if "alternative_fuel_constraint" in pathway.constraints_to_apply:
                if not dict_constraints["alternative_fuel_constraint"]:
                    if constraints_regional_check:
                        # remove exceeding region from ranking
                        logger.debug(
                            f"Handle alternative fuels constraint: removing all alternative fuels "
                            f"technologies in {new_asset.region}"
                        )
                        df_rank = remove_techs_in_region_by_tech_substr(
                            df_rank=df_rank,
                            region=new_asset.region,
                            tech_substr="alternative fuels",
                        )
                    else:
                        # get regions where alternative fuel is exceeded
                        dict_alternative_fuel_exceedance = (
                            check_alternative_fuel_constraint(
                                pathway=pathway,
                                product=product,
                                stack=tentative_stack,
                                year=year,
                                transition_type="greenfield",
                                return_dict=True,
                            )
                        )
                        exceeding_regions = [
                            k
                            for k in dict_alternative_fuel_exceedance.keys()
                            if not dict_alternative_fuel_exceedance[k]
                        ]
                        # check if regions other than the tentatively updated asset's region exceed the
                        #   constraint
                        if exceeding_regions != [new_asset.region]:
                            logger.critical(
                                f"{year}: Regions other than the tentatively updated asset's region exceed the alternative "
                                "fuel constraint!"
                            )
                        else:
                            # remove exceeding region from ranking
                            logger.debug(
                                f"Handle alternative fuels constraint: removing all alternative fuels "
                                f"technologies in {new_asset.region}"
                            )
                            df_rank = remove_techs_in_region_by_tech_substr(
                                df_rank=df_rank,
                                region=new_asset.region,
                                tech_substr="alternative fuels",
                            )

    # If ranking table empty, no greenfield construction possible
    raise ValueError


def get_region_rank_filter(region: str, sector: str) -> list:
    """Return list of (sub)regions if the sector has low-cost power regions mapped to the overall regions"""
    if MAP_LOW_COST_POWER_REGIONS[sector]:
        if region in MAP_LOW_COST_POWER_REGIONS[sector].keys():  # type: ignore
            return [region, MAP_LOW_COST_POWER_REGIONS[sector][region]]  # type: ignore
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
    """Create DataFrame that shows maximum plant additions in each region such that the constraint that each region can
    supply a maximum share of new demand is fulfilled."""

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

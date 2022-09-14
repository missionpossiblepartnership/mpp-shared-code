""" Logic for technology transitions of type brownfield rebuild and brownfield renovation."""
import random
import sys
from copy import deepcopy

import numpy as np
import pandas as pd

from cement.config.config_cement import (
    LOG_LEVEL,
    PRODUCTS,
    CONSTRAINTS_REGIONAL_CHECK,
    SWITCH_TYPES_UPDATE_YEAR_COMMISSIONED,
)
from mppshared.agent_logic.agent_logic_functions import (
    remove_all_transitions_with_destination_technology,
    remove_all_transitions_with_origin_destination_technology,
    remove_transition,
    select_best_transition,
    get_constraints_to_apply,
)
from mppshared.models.constraints import (
    check_biomass_constraint,
    check_constraints,
    check_co2_storage_constraint,
)
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.models.asset import AssetStack
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def brownfield(pathway: SimulationPathway, year: int) -> SimulationPathway:
    """Apply brownfield rebuild or brownfield renovation transition to eligible Assets in the AssetStack.

    Args:
        pathway: decarbonization pathway that describes the composition of the AssetStack in every year of the model
            horizon
        year: current year in which technology transitions are enacted

    Returns:
        Updated decarbonization pathway with the updated AssetStack in the subsequent year according to the brownfield
            transitions enacted
    """
    logger.debug(f"{year}: Starting brownfield transition logic")

    # Get ranking table for brownfield transition (renovation & rebuild)
    df_rank = pathway.get_ranking(year=year, rank_type="brownfield")
    df_rank_renovation = df_rank.copy().loc[
        (df_rank["switch_type"] == "brownfield_renovation"), :
    ]
    df_rank_rebuild = df_rank.copy().loc[
        (df_rank["switch_type"] == "brownfield_rebuild"), :
    ]

    # Get assets eligible for brownfield transitions
    candidates_renovation = pathway.get_stack(
        year=year
    ).get_assets_eligible_for_brownfield_cement_renovation(year=year)
    candidates_rebuild = pathway.get_stack(
        year=year
    ).get_assets_eligible_for_brownfield_cement_rebuild(year=year)

    # enact transitions
    logger.info("Start brownfield renovation transitions")
    pathway = _enact_brownfield_transition(
        pathway=pathway,
        year=year,
        df_rank=df_rank_renovation,
        candidates=candidates_renovation,
    )
    logger.info("Start brownfield rebuild transitions")
    pathway = _enact_brownfield_transition(
        pathway=pathway,
        year=year,
        df_rank=df_rank_rebuild,
        candidates=candidates_rebuild,
    )

    return pathway


def _enact_brownfield_transition(
    pathway: SimulationPathway, year: int, df_rank: pd.DataFrame, candidates: list
):

    # asset stack is changed by the brownfield transitions
    stack = pathway.get_stack(year=year)

    # Get the emissions, used for the LC scenario
    emissions_limit = pathway.carbon_budget.get_annual_emissions_limit(year)
    # unit emissions_limit: [Gt CO2]

    # Track number of assets that undergo transition
    n_assets_transitioned = 0
    n_assets_transitioned_incl_same_tech = 0
    maximum_n_assets_transitioned = np.floor(
        pathway.annual_renovation_share * stack.get_number_of_assets()
    )
    logger.debug(
        f"{year}: {len(candidates)} eligible assets (max. transitions: {maximum_n_assets_transitioned})"
    )

    # Enact brownfield transitions while there are still candidates
    while (candidates != []) & (n_assets_transitioned <= maximum_n_assets_transitioned):

        # Find the best transition and assets candidates, that can undergo this transition. If there are no assets that
        #   can undergo the best transition, go for the next best transition
        candidates_best_transition = []
        while len(candidates_best_transition) == 0:
            # If no more transitions available, break and return pathway
            if df_rank.empty:
                logger.debug("No more brownfield transitions available")
                return pathway

            # If LC pathway, check carbon budget and exit if brownfield transitions already fulfil the constraint (this
            #   minimises the investment by reducing the number of switches)
            if pathway.pathway_name == "lc":
                dict_stack_emissions = stack.calculate_emissions_stack(
                    year=year,
                    df_emissions=pathway.emissions,
                    technology_classification=None,
                )
                # Compare scope 1 and 2 CO2 emissions to the allowed limit in that year
                co2_scope1_2 = (
                    dict_stack_emissions["co2_scope1"]
                    + dict_stack_emissions["co2_scope2"]
                ) / 1e3  # Gt CO2
                if np.round(co2_scope1_2, 2) <= np.round(emissions_limit, 2):
                    logger.debug(
                        f"Emissions lower than budget: {np.round(co2_scope1_2,2)} <= {np.round(emissions_limit,2)}. "
                        f"No brownfield switches to minimize cost in lowest cost pathway"
                    )
                    return pathway

            # Find the best transition (i.e., highest brownfield rank)
            best_transition = select_best_transition(df_rank)
            candidates_best_transition = list(
                filter(
                    # todo: add filter for OPEX context
                    lambda asset: (
                        asset.technology == best_transition["technology_origin"]
                    )
                    & (asset.region == best_transition["region"])
                    & (asset.product == best_transition["product"]),
                    candidates,
                )
            )
            new_technology = best_transition["technology_destination"]
            switch_type = best_transition["switch_type"]
            region_best_transition = best_transition["region"]
            origin_technology = best_transition["technology_origin"]
            # Remove best transition from ranking table if there are no candidates left for it
            if len(candidates_best_transition) == 0:
                logger.debug(
                    f"No assets available for best transition ({region_best_transition}; {switch_type}; "
                    f"{origin_technology} -> {new_technology})"
                )
                df_rank = remove_transition(df_rank, best_transition)

        # If several candidates for best transition, choose asset for transition randomly
        asset_to_update = random.choice(candidates_best_transition)

        # Update asset tentatively (needs deepcopy to provide changes to original stack)
        tentative_stack = deepcopy(stack)
        assert (origin_technology == asset_to_update.technology) & (
            asset_to_update.region == best_transition["region"]
        )
        logger.debug(
            f"{year}: Tentatively transitioning asset in {asset_to_update.region} "
            f"from {origin_technology} to {new_technology} "
            f"(annual production: {asset_to_update.get_annual_production_volume()}, UUID: {asset_to_update.uuid})"
        )
        tentative_stack.update_asset(
            year=year,
            asset_to_update=deepcopy(asset_to_update),
            new_technology=new_technology,
            new_classification=best_transition["technology_classification"],
            asset_lifetime=best_transition["technology_lifetime"],
            switch_type=switch_type,
            origin_technology=origin_technology,
            update_year_commission=False,
        )

        # Check constraints with tentative new stack
        constraints_to_apply = get_constraints_to_apply(
            pathway_constraints_to_apply=pathway.constraints_to_apply,
            origin_technology=origin_technology,
            destination_technology=new_technology,
        )
        dict_constraints = check_constraints(
            pathway=pathway,
            stack=tentative_stack,
            year=year,
            transition_type="brownfield",
            product=PRODUCTS[0],
            constraints_to_apply=constraints_to_apply,
            region=asset_to_update.region if CONSTRAINTS_REGIONAL_CHECK else None,
        )
        # If no constraint is hurt, execute the brownfield transition
        if all(
            [
                dict_constraints[k]
                for k in dict_constraints.keys()
                if k in pathway.constraints_to_apply and k != "regional_constraint"
            ]
        ) | (origin_technology == new_technology):
            logger.debug(
                f"{year}: All constraints fulfilled. "
                f"Updating asset in {asset_to_update.region} from {origin_technology} to {new_technology} "
                f"(annual production: {asset_to_update.get_annual_production_volume()}, UUID: {asset_to_update.uuid})"
            )
            # Update asset stack
            stack.update_asset(
                year=year,
                asset_to_update=deepcopy(asset_to_update),
                new_technology=new_technology,
                new_classification=best_transition["technology_classification"],
                asset_lifetime=best_transition["technology_lifetime"],
                switch_type=switch_type,
                origin_technology=origin_technology,
                update_year_commission=(
                    switch_type in SWITCH_TYPES_UPDATE_YEAR_COMMISSIONED
                ),
            )
            # Remove asset from candidates
            candidates.remove(asset_to_update)
            # Only count the transition if the technology is not the same
            if origin_technology != new_technology:
                n_assets_transitioned += 1
            n_assets_transitioned_incl_same_tech += 1

        # if not all constraints are fulfilled
        else:

            # EMISSIONS
            if "emissions_constraint" in constraints_to_apply:
                if not dict_constraints["emissions_constraint"]:
                    # check if the switch reduces the total emissions
                    dict_stack_emissions = stack.calculate_emissions_stack(
                        year=year,
                        df_emissions=pathway.emissions,
                        technology_classification=None,
                    )
                    dict_tentative_stack_emissions = (
                        tentative_stack.calculate_emissions_stack(
                            year=year,
                            df_emissions=pathway.emissions,
                            technology_classification=None,
                        )
                    )
                    co2_scope1_2_emissions_stack = (
                        dict_stack_emissions["co2_scope1"]
                        + dict_stack_emissions["co2_scope2"]
                    ) / 1e3
                    co2_scope1_2_emissions_tentative_stack = (
                        dict_tentative_stack_emissions["co2_scope1"]
                        + dict_tentative_stack_emissions["co2_scope2"]
                    ) / 1e3
                    if (
                        co2_scope1_2_emissions_tentative_stack
                        < co2_scope1_2_emissions_stack
                    ):
                        if all(
                            [
                                dict_constraints[k]
                                for k in dict_constraints.keys()
                                if k in pathway.constraints_to_apply
                                and k
                                not in ["regional_constraint", "emissions_constraint"]
                            ]
                        ):
                            # allow brownfield transition since it reduces overall emissions
                            logger.debug(
                                f"{year}: All constraints besides emissions constraint fulfilled and "
                                f"transition reduces total emissions. "
                                f"Updating asset in {asset_to_update.region} from {origin_technology} to "
                                f"{new_technology}. "
                                f"(annual production: {asset_to_update.get_annual_production_volume()}, UUID: "
                                f"{asset_to_update.uuid}"
                            )
                            # Update asset stack
                            stack.update_asset(
                                year=year,
                                asset_to_update=asset_to_update,
                                new_technology=new_technology,
                                new_classification=best_transition[
                                    "technology_classification"
                                ],
                                asset_lifetime=best_transition["technology_lifetime"],
                                switch_type=switch_type,
                                origin_technology=origin_technology,
                                update_year_commission=(
                                    switch_type in SWITCH_TYPES_UPDATE_YEAR_COMMISSIONED
                                ),
                            )
                            # Remove asset from candidates
                            candidates.remove(asset_to_update)
                            # Only count the transition if the technology is not the same
                            if origin_technology != new_technology:
                                n_assets_transitioned += 1
                            n_assets_transitioned_incl_same_tech += 1
                    else:
                        # remove destination technology from ranking
                        logger.debug(
                            f"Handle emissions constraint: removing origin - destination technology"
                        )
                        if origin_technology != new_technology:
                            df_rank = remove_all_transitions_with_origin_destination_technology(
                                df_rank=df_rank,
                                transition=best_transition,
                            )

            # RAMPUP
            if "rampup_constraint" in constraints_to_apply:
                if not dict_constraints["rampup_constraint"]:
                    # remove destination technology from ranking
                    logger.debug(
                        f"Handle ramp up constraint: removing destination technology"
                    )
                    df_rank = remove_all_transitions_with_destination_technology(
                        df_rank=df_rank,
                        technology_destination=best_transition[
                            "technology_destination"
                        ],
                    )

            # BIOMASS
            if "biomass_constraint" in constraints_to_apply:
                if not dict_constraints["biomass_constraint"]:
                    # remove all transitions with that destination technology from the ranking table
                    logger.debug(
                        f"Handle biomass constraint: removing destination technology"
                    )
                    df_rank = remove_all_transitions_with_destination_technology(
                        df_rank=df_rank,
                        technology_destination=best_transition[
                            "technology_destination"
                        ],
                    )

            # CO2 STORAGE
            if "co2_storage_constraint" in constraints_to_apply:
                if not dict_constraints["co2_storage_constraint"]:
                    if CONSTRAINTS_REGIONAL_CHECK:
                        # remove destination technology in exceeding region from ranking
                        logger.debug(
                            f"Handle CO2 storage constraint: removing destination technology "
                            f"in {asset_to_update.region}"
                        )
                        df_rank = remove_all_transitions_with_destination_technology(
                            df_rank=df_rank,
                            technology_destination=best_transition[
                                "technology_destination"
                            ],
                            region=asset_to_update.region,
                        )
                    else:
                        # get regions where CO2 storage constraint is exceeded
                        dict_co2_storage_exceedance = check_co2_storage_constraint(
                            pathway=pathway,
                            product=PRODUCTS[0],
                            stack=tentative_stack,
                            year=year,
                            transition_type="brownfield",
                            return_dict=True,
                        )
                        exceeding_regions = [
                            k
                            for k in dict_co2_storage_exceedance.keys()
                            if not dict_co2_storage_exceedance[k]
                        ]
                        # check if regions other than the tentatively updated asset's region exceed the constraint
                        if exceeding_regions != [asset_to_update.region]:
                            sys.exit(
                                f"{year}: Regions other than the tentatively updated asset's region exceed the CO2 "
                                "storage constraint!"
                            )
                        else:
                            # remove destination technology in exceeding region from ranking
                            logger.debug(
                                f"Handle CO2 storage constraint: removing destination technology "
                                f"in {asset_to_update.region}"
                            )
                            df_rank = (
                                remove_all_transitions_with_destination_technology(
                                    df_rank=df_rank,
                                    technology_destination=best_transition[
                                        "technology_destination"
                                    ],
                                    region=asset_to_update.region,
                                )
                            )

    logger.debug(
        f"{year}: assets transitioned: {n_assets_transitioned}; maximum: {maximum_n_assets_transitioned}; "
        f"assets transitioned incl. switches without tech switch: {n_assets_transitioned_incl_same_tech}"
    )

    return pathway

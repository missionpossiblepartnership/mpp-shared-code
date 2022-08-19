""" Logic for technology transitions of type brownfield rebuild and brownfield renovation."""
import random
from copy import deepcopy

import numpy as np

from cement.config.config_cement import LOG_LEVEL, PRODUCTS
from mppshared.agent_logic.agent_logic_functions import (
    remove_all_transitions_with_destination_technology,
    remove_techs_in_region_by_tech_substr, remove_transition,
    select_best_transition)
from mppshared.models.constraints import (check_alternative_fuel_constraint,
                                          check_constraints,
                                          check_natural_gas_constraint)
from mppshared.models.simulation_pathway import SimulationPathway
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

    # asset stack is changed by the brownfield transitions
    stack = pathway.get_stack(year=year)
    # Get the emissions, used for the LC scenario
    emissions_limit = pathway.carbon_budget.get_annual_emissions_limit(year)
    # unit emissions_limit: [Gt CO2]

    # Get ranking table for brownfield transitions
    df_rank = pathway.get_ranking(year=year, rank_type="brownfield")

    # Get assets eligible for brownfield transitions
    candidates = stack.get_assets_eligible_for_brownfield_cement()

    # Track number of assets that undergo transition
    n_assets_transitioned = 0
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
                        f"Emissions lower than budget: {np.round(co2_scope1_2,2)} <= {np.round(emissions_limit,2)}"
                    )
                    return pathway

            # Find the best transition (i.e., highest brownfield rank)
            best_transition = select_best_transition(df_rank)
            candidates_best_transition = list(
                filter(
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
            best_transition_region = best_transition["region"]
            origin_technology = best_transition["technology_origin"]
            # Remove best transition from ranking table if there are no candidates left for it
            if len(candidates_best_transition) == 0:
                logger.debug(
                    f"No assets available for best transition ({best_transition_region}; {switch_type}; "
                    f"{origin_technology} -> {new_technology})"
                )
                df_rank = remove_transition(df_rank, best_transition)

        # If several candidates for best transition, choose asset for transition randomly
        asset_to_update = random.choice(candidates_best_transition)

        # Update asset tentatively (needs deepcopy to provide changes to original stack)
        tentative_stack = deepcopy(stack)
        assert origin_technology == asset_to_update.technology
        logger.debug(
            f"{year}: Tentatively transitioning asset in {asset_to_update.region} "
            f"from {origin_technology} to {new_technology}."
        )
        tentative_stack.update_asset(
            asset_to_update=asset_to_update,
            new_technology=new_technology,
            new_classification=best_transition["technology_classification"],
            switch_type=switch_type,
            origin_technology=origin_technology,
        )

        # Check constraints with tentative new stack
        dict_constraints = check_constraints(
            pathway=pathway,
            stack=tentative_stack,
            year=year,
            transition_type="brownfield",
            product=PRODUCTS[0],
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
                f"Updating asset in {asset_to_update.region} from {origin_technology} to {new_technology}. "
                f"(annual production: {asset_to_update.get_annual_production_volume()}, UUID: {asset_to_update.uuid}"
            )
            # Update asset stack
            stack.update_asset(
                asset_to_update=asset_to_update,
                new_technology=new_technology,
                new_classification=best_transition["technology_classification"],
                switch_type=switch_type,
                origin_technology=origin_technology,
            )
            # Remove asset from candidates
            candidates.remove(asset_to_update)
            # Only count the transition if the technology is not the same
            if origin_technology != new_technology:
                n_assets_transitioned += 1

        # if not all constraints are fulfilled
        else:
            # todo: make sure that all constraints are being handled here!
            # EMISSIONS
            if "emissions_constraint" in pathway.constraints_to_apply:
                if not dict_constraints["emissions_constraint"]:
                    # remove transition from ranking
                    logger.debug(f"Handle emissions constraint: removing transition")
                    if origin_technology != new_technology:
                        df_rank = remove_transition(
                            df_rank=df_rank, transition=best_transition
                        )
            # RAMPUP
            if "rampup_constraint" in pathway.constraints_to_apply:
                if not dict_constraints["rampup_constraint"]:
                    # remove destination technology from ranking
                    logger.debug(f"Handle ramp up constraint: removing destination technology")
                    df_rank = remove_all_transitions_with_destination_technology(
                        df_rank=df_rank,
                        technology_destination=best_transition[
                            "technology_destination"
                        ],
                    )
            # NATURAL GAS
            if "natural_gas_constraint" in pathway.constraints_to_apply:
                if not dict_constraints["natural_gas_constraint"]:
                    # get regions where natural gas is exceeded
                    dict_natural_gas_exceedance = check_natural_gas_constraint(
                        pathway=pathway,
                        product=PRODUCTS[0],
                        stack=tentative_stack,
                        year=year,
                        transition_type="brownfield",
                        return_dict=True,
                    )
                    exceeding_regions = [
                        k
                        for k in dict_natural_gas_exceedance.keys()
                        if not dict_natural_gas_exceedance[k]
                    ]
                    # check if regions other than the tentatively updated asset's region exceed the constraint
                    if exceeding_regions != [asset_to_update.region]:
                        logger.critical(
                            f"{year}: Regions other than the tentatively updated asset's region exceed the natural gas "
                            f"constraint!"
                        )
                    else:
                        # remove exceeding region from ranking
                        logger.debug(
                            f"Handle natural gas constraint: removing all natural gas technologies "
                            f"in {asset_to_update.region}"
                        )
                        df_rank = remove_techs_in_region_by_tech_substr(
                            df_rank=df_rank,
                            region=asset_to_update.region,
                            tech_substr="natural gas",
                        )
            # ALTERNATIVE FUEL
            if "alternative_fuel_constraint" in pathway.constraints_to_apply:
                if not dict_constraints["alternative_fuel_constraint"]:
                    # get regions where alternative fuel is exceeded
                    dict_alternative_fuel_exceedance = (
                        check_alternative_fuel_constraint(
                            pathway=pathway,
                            product=PRODUCTS[0],
                            stack=tentative_stack,
                            year=year,
                            transition_type="brownfield",
                            return_dict=True,
                        )
                    )
                    exceeding_regions = [
                        k
                        for k in dict_alternative_fuel_exceedance.keys()
                        if not dict_alternative_fuel_exceedance[k]
                    ]
                    # check if regions other than the tentatively updated asset's region exceed the constraint
                    if exceeding_regions != [asset_to_update.region]:
                        logger.critical(
                            f"{year}: Regions other than the tentatively updated asset's region exceed the alternative "
                            "fuel constraint!"
                        )
                    else:
                        # remove exceeding region from ranking
                        logger.debug(
                            f"Handle alternative fuels constraint: removing all alternative fuels technologies "
                            f"in {asset_to_update.region}"
                        )
                        df_rank = remove_techs_in_region_by_tech_substr(
                            df_rank=df_rank,
                            region=asset_to_update.region,
                            tech_substr="alternative fuels",
                        )

    logger.debug(
        f"{year}: {n_assets_transitioned} assets transitioned of maximum {maximum_n_assets_transitioned}."
    )

    return pathway

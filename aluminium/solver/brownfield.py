""" Logic for technology transitions of type brownfield rebuild and brownfield renovation."""
import random
from copy import deepcopy
from operator import methodcaller

import numpy as np

from aluminium.config_aluminium import LOG_LEVEL, SWITCH_TYPES_UPDATE_YEAR_COMMISSIONED
from mppshared.agent_logic.agent_logic_functions import (
    remove_all_transitions_with_destination_technology,
    remove_transition,
    select_best_transition,
)
from mppshared.models.constraints import check_constraints
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def brownfield(pathway: SimulationPathway, year: int) -> SimulationPathway:
    """Apply brownfield rebuild or brownfield renovation transition to eligible Assets in the AssetStack.

    Args:
        pathway: decarbonization pathway that describes the composition of the AssetStack in every year of the model horizon
        year: current year in which technology transitions are enacted

    Returns:
        Updated decarbonization pathway with the updated AssetStack in the subsequent year according to the brownfield transitions enacted
    """
    logger.debug(f"Starting brownfield transition logic for year {year}")

    # Next year's asset stack is changed by the brownfield transitions
    new_stack = pathway.get_stack(year=year + 1)
    # Get the emissions, used for the LC scenario
    if year == 2050:
        emissions_limit = pathway.carbon_budget.get_annual_emissions_limit(year)  # type: ignore
    else:
        emissions_limit = pathway.carbon_budget.get_annual_emissions_limit(year + 1)  # type: ignore

    # Get ranking table for brownfield transitions
    df_rank = pathway.get_ranking(year=year, rank_type="brownfield")

    # Get assets eligible for brownfield transitions
    candidates = new_stack.get_assets_eligible_for_brownfield(
        year=year, investment_cycle=pathway.investment_cycle
    )

    # Track number of assets that undergo transition
    n_assets_transitioned = 0
    maximum_n_assets_transitioned = np.floor(
        pathway.annual_renovation_share * new_stack.get_number_of_assets()
    )
    logger.debug(
        f"Number of assets eligible for brownfield transition: {len(candidates)} in year {year}, of which maximum {maximum_n_assets_transitioned} can be transitioned."
    )

    # Enact brownfield transitions while there are still candidates
    while (candidates != []) & (n_assets_transitioned <= maximum_n_assets_transitioned):
        # TODO: how do we avoid that all assets are retrofit at once in the beginning?
        # TODO: implement foresight with brownfield rebuild

        # Find assets can undergo the best transition. If there are no assets for the best transition, continue searching with the next-best transition
        best_candidates = []  # type: ignore
        while not best_candidates:
            # If no more transitions available, break and return pathway
            if df_rank.empty:
                return pathway

            # Check if LC pathway and check emissions to exit after being lower than the constraint
            # This check minimizes the investment as it only requieres some switches and not all of them
            if pathway.pathway_name == "lc":
                dict_stack_emissions = new_stack.calculate_emissions_stack(
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

            # Choose the best transition, i.e. highest decommission rank
            best_transition = select_best_transition(df_rank)
            # Check it the transition has PPA on it, if so only get plants that allow transition to ppa
            if "PPA" in best_transition["technology_destination"]:
                best_candidates = list(
                    filter(
                        lambda asset: (
                            asset.technology == best_transition["technology_origin"]
                        )
                        & (asset.region == best_transition["region"])
                        & (asset.product == best_transition["product"])
                        & (asset.ppa_allowed == True),
                        candidates,
                    )
                )
            else:
                best_candidates = list(
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
            # Remove best transition from ranking table
            if len(best_candidates) == 0:
                df_rank = remove_transition(df_rank, best_transition)

        # If several candidates for best transition, choose asset for transition randomly
        asset_to_update = random.choice(best_candidates)

        # Update asset tentatively (needs deepcopy to provide changes to original stack)
        tentative_stack = deepcopy(new_stack)
        origin_technology = asset_to_update.technology
        tentative_stack.update_asset(
            year=year,
            asset_to_update=asset_to_update,
            new_technology=new_technology,
            new_classification=best_transition["technology_classification"],
            asset_lifetime=best_transition["technology_lifetime"],
            switch_type=switch_type,
            origin_technology=origin_technology,
            update_year_commission=False,
        )

        # Check constraints with tentative new stack
        assert (
            len(pathway.products) == 1
        ), "Adjust aluminium brownfield logic if more than one product!"
        dict_constraints = check_constraints(
            pathway=pathway,
            product=pathway.products[0],
            stack=tentative_stack,
            year=year,
            transition_type="brownfield",
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
                f"Year {year} Updating {asset_to_update.product} asset from technology {origin_technology} to technology {new_technology} in region {asset_to_update.region}, annual production {asset_to_update.get_annual_production_volume()} and UUID {asset_to_update.uuid}"
            )
            # Update asset stack
            new_stack.update_asset(
                year=year,
                asset_to_update=asset_to_update,
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
            # Only count the transition if the technology is the same
            if origin_technology != new_technology:
                n_assets_transitioned += 1

        # If the emissions constraint and/or the technology ramp-up constraint is hurt, remove remove that destination technology from the ranking table and try again
        elif dict_constraints["emissions_constraint"] == False:
            logger.info(
                f"Emissions constraint hurt for {origin_technology} -> {new_technology}"
            )
            if origin_technology != new_technology:
                df_rank = remove_transition(df_rank, best_transition)
        elif dict_constraints["rampup_constraint"] == False:
            df_rank = remove_all_transitions_with_destination_technology(
                df_rank, best_transition["technology_destination"]
            )

    logger.debug(
        f"{n_assets_transitioned} assets transitioned of maximum {maximum_n_assets_transitioned} in year {year}."
    )

    return pathway

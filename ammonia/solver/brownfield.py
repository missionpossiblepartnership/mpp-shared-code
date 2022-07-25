""" Logic for technology transitions of type brownfield rebuild and brownfield renovation."""
import random
import sys
from copy import deepcopy
from operator import methodcaller

import numpy as np
import pandas as pd
from pandera import Bool

from ammonia.config_ammonia import (ANNUAL_RENOVATION_SHARE,
                                    BROWNFIELD_REBUILD_START_YEAR,
                                    BROWNFIELD_RENOVATION_START_YEAR,
                                    COST_METRIC_DECREASE_BROWNFIELD, LOG_LEVEL,
                                    RANKING_COST_METRIC,
                                    REGIONAL_TECHNOLOGY_BAN)
from mppshared.agent_logic.agent_logic_functions import (
    apply_regional_technology_ban,
    remove_all_transitions_with_destination_technology, remove_transition,
    select_best_transition)
from mppshared.agent_logic.brownfield import (
    apply_brownfield_filters_chemicals,
    apply_start_years_brownfield_transitions)
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
        product: product for which technology transitions are enacted

    Returns:
        Updated decarbonization pathway with the updated AssetStack in the subsequent year according to the brownfield transitions enacted
    """
    logger.debug(f"Starting brownfield transition logic for year {year}")

    # Next year's asset stack is changed by the brownfield transitions
    new_stack = pathway.get_stack(year=year + 1)

    # Get ranking table for brownfield transitions
    df_rank = pathway.get_ranking(year=year, rank_type="brownfield")

    # Apply filters for the chemical sector
    if pathway.sector == "chemicals":
        df_rank = apply_brownfield_filters_chemicals(
            df_rank,
            pathway,
            year,
            ranking_cost_metric=RANKING_COST_METRIC,
            cost_metric_decrease_brownfield=COST_METRIC_DECREASE_BROWNFIELD,
        )

    # Apply regional technology ban
    df_rank = apply_regional_technology_ban(
        df_rank, sector_bans=REGIONAL_TECHNOLOGY_BAN
    )

    # If pathway is BAU, take out brownfield renovation to avoid retrofits to end-state technologies
    if pathway.pathway_name == "BAU":
        df_rank = df_rank.loc[~(df_rank["switch_type"] == "brownfield_renovation")]

    # Apply start years of brownfield transitions
    df_rank = apply_start_years_brownfield_transitions(
        df_rank=df_rank,
        pathway=pathway,
        year=year,
        brownfield_renovation_start_year=BROWNFIELD_RENOVATION_START_YEAR,
        brownfield_rebuild_start_year=BROWNFIELD_REBUILD_START_YEAR,
    )

    # Get assets eligible for brownfield transitions
    candidates = new_stack.get_assets_eligible_for_brownfield(
        year=year,
        investment_cycle=pathway.investment_cycle,
    )

    # Track number of assets that undergo transition
    # TODO: renovation share applied to assets with initial technology?
    n_assets_transitioned = 0
    maximum_n_assets_transitioned = np.ceil(
        ANNUAL_RENOVATION_SHARE * new_stack.get_number_of_assets()
    )

    # From 2045 onwards, all transition techs need to be retrofit to end-state, so apply cap based on remaining number of assets
    # TODO: improve this quick fix

    # Avoid long exponential decline
    # if maximum_n_assets_transitioned < 30:
    #     maximum_n_assets_transitioned = 30
    logger.debug(
        f"Number of assets eligible for brownfield transition: {len(candidates)} in year {year}, of which maximum {maximum_n_assets_transitioned} can be transitioned."
    )

    # Enact brownfield transitions while there are still candidates
    while (candidates != []) & (n_assets_transitioned <= maximum_n_assets_transitioned):
        # TODO: how do we avoid that all assets are retrofit at once in the beginning?
        # TODO: implement foresight with brownfield rebuild

        # Find assets can undergo the best transition. If there are no assets for the best transition, continue searching with the next-best transition
        best_candidates = []
        while not best_candidates:

            # If no more transitions available, break and return pathway
            if df_rank.empty:
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

            # emove best transition from ranking table (other assets could undergo the same transition)
            df_rank = remove_transition(df_rank, best_transition)

        # If several candidates for best transition, choose asset for transition randomly
        asset_to_update = random.choice(best_candidates)

        # Update asset tentatively (needs deepcopy to provide changes to original stack)
        tentative_stack = deepcopy(new_stack)
        origin_technology = asset_to_update.technology
        tentative_stack.update_asset(
            deepcopy(asset_to_update),
            new_technology=new_technology,
            new_classification=best_transition["technology_classification"],
            switch_type=switch_type,
            origin_technology=origin_technology,
        )

        # Check constraints with tentative new stack
        # TODO: Uncoment when constraints are implemented
        # dict_constraints = check_constraints(
        #     pathway=pathway,
        #     stack=tentative_stack,
        #     year=year,
        #     transition_type="brownfield",
        # )
        # TODO: Remove hardcoded dictionary that meets all constraints

        dict_constraints = {
            "emissions_constraint": True,
            "rampup_constrraint": True,
            "co2_storage_constraint": True,
            "electrolysis_capacity_addition_constraint": True,
            "demand_share_constraint": True,
        }

        # If no constraint is hurt, execute the brownfield transition
        if all(constraint == True for constraint in dict_constraints.values()):
            logger.debug(
                f"Updating {asset_to_update.product} asset from technology {origin_technology} to technology {new_technology} in region {asset_to_update.region}, annual production {asset_to_update.get_annual_production_volume()} and UUID {asset_to_update.uuid}"
            )
            # Set retrofit or rebuild attribute to True according to type of brownfield transition
            if best_transition["switch_type"] == "brownfield_renovation":
                asset_to_update.retrofit = True
            if best_transition["switch_type"] == "brownfield_newbuild":
                asset_to_update.rebuild = True

            # Update asset stack
            new_stack.update_asset(
                asset_to_update,
                new_technology=new_technology,
                new_classification=best_transition["technology_classification"],
                switch_type=switch_type,
                origin_technology=origin_technology,
            )

            # Remove asset from candidates
            candidates.remove(asset_to_update)
            n_assets_transitioned += 1

        # If the emissions constraint, the technology ramp-up constraint or the CO2 storage constraint is hurt, remove that destination technology from the ranking table and try again
        elif (
            (dict_constraints["emissions_constraint"] == False)
            | (dict_constraints["rampup_constraint"] == False)
            | (dict_constraints["co2_storage_constraint"] == False)
            | (dict_constraints["electrolysis_capacity_addition_constraint"] == False)
            | (dict_constraints["demand_share_constraint"] == False)
        ):
            df_rank = remove_all_transitions_with_destination_technology(
                df_rank, best_transition["technology_destination"]
            )

    logger.debug(f"{n_assets_transitioned} assets transitioned in year {year}.")

    return pathway

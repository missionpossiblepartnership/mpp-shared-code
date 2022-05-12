""" Logic for technology transitions of type brownfield rebuild and brownfield renovation."""

from copy import deepcopy
from operator import methodcaller
import numpy as np
import random

from mppshared.agent_logic.agent_logic_functions import (
    remove_transition,
    select_best_transition,
    remove_all_transitions_with_destination_technology,
)
from mppshared.config import ANNUAL_RENOVATION_SHARE, LOG_LEVEL
from mppshared.models.constraints import check_constraints
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def brownfield(
    pathway: SimulationPathway, product: str, year: int
) -> SimulationPathway:
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
    df_rank = pathway.get_ranking(year=year, product=product, rank_type="brownfield")

    # Get assets eligible for brownfield transitions
    candidates = new_stack.get_assets_eligible_for_brownfield(
        year=year, sector=pathway.sector
    )

    # Track number of assets that undergo transition
    n_assets_transitioned = 0
    maximum_n_assets_transitioned = np.floor(
        ANNUAL_RENOVATION_SHARE[pathway.sector] * new_stack.get_number_of_assets()
    )
    logger.debug(
        f"Number of assets eligible for brownfield transition: {len(candidates)} in year {year}, of which maximum {maximum_n_assets_transitioned} can be transitioned."
    )

    # Enact brownfield transitions while there are still candidates
    while (candidates != []) & (n_assets_transitioned <= maximum_n_assets_transitioned):

        # Find assets can undergo the best transition. If there are no assets for the best transition, continue searching with the next-best transition
        best_candidates = []
        while not best_candidates:

            # If no more transitions available, break and return pathway
            if df_rank.empty:
                return pathway

            # Choose the best transition, i.e. highest decommission rank
            best_transition = select_best_transition(df_rank)

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
            # Remove best transition from ranking table
            df_rank = remove_transition(df_rank, best_transition)

        # If several candidates for best transition, choose asset for transition randomly
        asset_to_update = random.choice(best_candidates)

        # Update asset tentatively (needs deepcopy to provide changes to original stack)
        tentative_stack = deepcopy(new_stack)
        origin_technology = asset_to_update.technology
        tentative_stack.update_asset(
            asset_to_update,
            new_technology=new_technology,
            new_classification=best_transition["technology_classification"],
        )

        # Check constraints with tentative new stack
        dict_constraints = check_constraints(
            pathway=pathway,
            stack=tentative_stack,
            product=product,
            year=year,
            transition_type="brownfield",
        )

        # If no constraint is hurt, execute the brownfield transition
        if all(value == True for value in dict_constraints.values()):
            logger.debug(
                f"Updating asset from technology {origin_technology} to technology {new_technology} in region {asset_to_update.region}, annual production {asset_to_update.get_annual_production_volume()} and UUID {asset_to_update.uuid}"
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
            )

            # Remove asset from candidates
            candidates.remove(asset_to_update)
            n_assets_transitioned += 1

        # If the emissions constraint and/or the technology ramp-up constraint is hurt, remove remove that destination technology from the ranking table and try again
        elif (dict_constraints["emissions_constraint"] == False) | dict_constraints[
            "rampup_constraint"
        ] == False:
            df_rank = remove_all_transitions_with_destination_technology(
                df_rank, best_transition["technology_destination"]
            )

    logger.debug(
        f"{n_assets_transitioned} assets transitioned in year {year} for product {product} in sector {pathway.sector}"
    )

    return pathway

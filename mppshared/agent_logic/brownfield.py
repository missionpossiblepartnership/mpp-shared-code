""" Logic for technology transitions of type brownfield rebuild and brownfield renovation."""

from operator import methodcaller
from copy import deepcopy

from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.agent_logic.agent_logic_functions import (
    select_best_transition,
    remove_transition,
)
from mppshared.models.constraints import check_constraints
from mppshared.config import LOG_LEVEL
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

    # Next year's asset stack is changed by the brownfield transitions
    new_stack = pathway.get_stack(year=year + 1)

    # Get ranking table for brownfield transitions
    df_rank = pathway.get_ranking(year=year, product=product, rank_type="brownfield")

    # Get assets eligible for brownfield transitions
    candidates = new_stack.get_assets_eligible_for_brownfield(year)

    # Track number of assets that undergo transition
    # TODO: implement constraints for number of brownfield transitions per year
    n_assets_transitioned = 0

    # Enact brownfield transitions while there are still candidates
    while (candidates != []) & (n_assets_transitioned < 10):
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

        # If several candidates for best transition, choose asset with lowest annual production
        # TODO: What happens if several assets have same annual production?
        asset_to_update = min(
            best_candidates, key=methodcaller("get_annual_production_volume")
        )

        # Update asset tentatively (needs deepcopy to provide changes to original stack)
        tentative_stack = deepcopy(new_stack)
        origin_technology = asset_to_update.technology
        tentative_stack.update_asset(asset_to_update, new_technology=new_technology)

        # Check constraints with tentative new stack
        no_constraint_hurt = check_constraints(pathway, tentative_stack, product, year)

        if no_constraint_hurt:
            logger.debug(
                f"Updating asset from technology {origin_technology} to technology {new_technology} in region {asset_to_update.region}, annual production {asset_to_update.get_annual_production_volume()} and UUID {asset_to_update.uuid}"
            )
            new_stack.update_asset(
                asset_to_update,
                new_technology=new_technology,
            )
            n_assets_transitioned += 1

        # If constraint is hurt, remove asset from list of candidates and try again
        candidates.remove(asset_to_update)

    return pathway

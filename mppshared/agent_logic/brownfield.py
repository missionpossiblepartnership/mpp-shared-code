""" Logic for technology transitions of type brownfield rebuild and brownfield renovation."""
import random
from copy import deepcopy
from operator import methodcaller

import numpy as np
import pandas as pd

from mppshared.agent_logic.agent_logic_functions import (
    remove_all_transitions_with_destination_technology,
    remove_transition,
    select_best_transition,
)
from mppshared.config import ANNUAL_RENOVATION_SHARE, LOG_LEVEL
from mppshared.models.constraints import check_constraints
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def brownfield_def(pathway: SimulationPathway, year: int) -> SimulationPathway:
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
    # Get the emissions, used for the LC scenario
    if year == 2050:
        emissions_limit = pathway.carbon_budget.get_annual_emissions_limit(
            year, pathway.sector
        )
    else:
        emissions_limit = pathway.carbon_budget.get_annual_emissions_limit(
            year + 1, pathway.sector
        )

    # Get ranking table for brownfield transitions
    df_rank = pathway.get_ranking(year=year, rank_type="brownfield")

    # Get assets eligible for brownfield transitions
    candidates = new_stack.get_assets_eligible_for_brownfield(
        year=year, investment_cycle=pathway.investment_cycle
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
        # TODO: how do we avoid that all assets are retrofit at once in the beginning?
        # TODO: implement foresight with brownfield rebuild

        # Find assets can undergo the best transition. If there are no assets for the best transition, continue searching with the next-best transition
        best_candidates = []
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
            asset_to_update,
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
        )
        # If no constraint is hurt, execute the brownfield transition
        if (
            (dict_constraints["emissions_constraint"] == True)
            & (dict_constraints["rampup_constraint"] == True)
        ) | (origin_technology == new_technology):
            logger.debug(
                f"Year {year} Updating {asset_to_update.product} asset from technology {origin_technology} to technology {new_technology} in region {asset_to_update.region}, annual production {asset_to_update.get_annual_production_volume()} and UUID {asset_to_update.uuid}"
            )
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
            # Only count the transition if the technology is the same
            if origin_technology != new_technology:
                n_assets_transitioned += 1

        # If the emissions constraint and/or the technology ramp-up constraint is hurt, remove remove that destination technology from the ranking table and try again
        elif dict_constraints["emissions_constraint"] == False:
            logger.debug(
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


def apply_start_years_brownfield_transitions(
    df_rank: pd.DataFrame,
    pathway: SimulationPathway,
    year: int,
    brownfield_renovation_start_year: int,
    brownfield_rebuild_start_year: int,
):
    if pathway.pathway_name in ["fa", "lc"]:

        if year < brownfield_renovation_start_year:
            df_rank = df_rank.loc[df_rank["switch_type"] != "brownfield_renovation"]

        if year < brownfield_rebuild_start_year:
            df_rank = df_rank.loc[df_rank["switch_type"] != "brownfield_newbuild"]

    return df_rank


def apply_brownfield_filters_ammonia(
    df_rank: pd.DataFrame,
    pathway: SimulationPathway,
    year: int,
    ranking_cost_metric: str,
    cost_metric_decrease_brownfield: float,
) -> pd.DataFrame:
    """For ammonia, the BAU and LC pathways are driven by minimum cost. Hence, brownfield transitions only happen
    when they decrease LCOX. For the FA pathway, this is not the case."""

    if pathway.pathway_name == "fa":
        return df_rank

    cost_metric = ranking_cost_metric

    # Get LCOX of origin technologies for retrofit
    df_greenfield = pathway.get_ranking(year=year, rank_type="greenfield")
    df_lcox = df_greenfield.loc[df_greenfield["technology_origin"] == "New-build"]
    df_lcox = df_lcox[
        [
            "product",
            "region",
            "technology_destination",
            "year",
            cost_metric,
        ]
    ]

    df_destination_techs = df_lcox.rename(
        {cost_metric: f"{cost_metric}_destination"}, axis=1
    )

    df_origin_techs = df_lcox.rename(
        {
            "technology_destination": "technology_origin",
            cost_metric: f"{cost_metric}_origin",
        },
        axis=1,
    )

    # Add to ranking table and filter out brownfield transitions which would not decrease LCOX "substantially"
    df_rank = df_rank.merge(
        df_origin_techs,
        on=["product", "region", "technology_origin", "year"],
        how="left",
    ).fillna(0)

    df_rank = df_rank.merge(
        df_destination_techs,
        on=["product", "region", "technology_destination", "year"],
        how="left",
    ).fillna(0)

    filter = df_rank[f"{cost_metric}_destination"] < df_rank[
        f"{cost_metric}_origin"
    ].apply(lambda x: x * (1 - cost_metric_decrease_brownfield))
    df_rank = df_rank.loc[filter]

    return df_rank

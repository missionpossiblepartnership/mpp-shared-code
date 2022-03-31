""" Logic for technology transitions of type greenfield (add new Asset to AssetStack."""

from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.models.asset import AssetStack, Asset, make_new_asset
from mppshared.agent_logic.agent_logic_functions import (
    select_best_transition,
    optimize_cuf,
)
from mppshared.models.constraints import check_constraints
from mppshared.utility.utils import get_logger
from mppshared.config import LOG_LEVEL, MODEL_SCOPE, ASSUMED_ANNUAL_PRODUCTION_CAPACITY


import pandas as pd
import numpy as np
from operator import methodcaller
from copy import deepcopy
import logging

logger = logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def greenfield(
    pathway: SimulationPathway, product: str, year: int
) -> SimulationPathway:
    """Apply greenfield transition and add new Assets to the AssetStack.

    Args:
        pathway: decarbonization pathway that describes the composition of the AssetStack in every year of the model horizon
        year: current year in which technology transitions are enacted
        product: product for which technology transitions are enacted

    Returns:
        Updated decarbonization pathway with the updated AssetStack in the subsequent year according to the decommission transitions enacted
    """
    # Current stack is for calculating production, next year's stack is updated with each decommissioning
    old_stack = pathway.get_stack(year=year)
    new_stack = pathway.get_stack(year=year + 1)

    # Get process data
    df_process_data = pathway.get_all_process_data(product=product, year=year)

    demand = pathway.get_demand(product=product, year=year, region=MODEL_SCOPE)
    production = old_stack.get_annual_production(product)

    # Get ranking table for greenfield transitions
    df_rank = pathway.get_ranking(product=product, year=year, rank_type="greenfield")

    # TODO: Decommission until one asset short of balance between demand and production
    surplus = demand - production
    while surplus > 0:
        # Check whether it is even possible to increase CUF
        cuf_assets = list(
            filter(lambda asset: asset.capacity_factor < 0.95, new_stack.assets)
        )
        if not cuf_assets:
            break

        # Optimize capacity factor and check whether surplus is covered
        if (surplus / ASSUMED_ANNUAL_PRODUCTION_CAPACITY) / len(cuf_assets) > 0.95:
            cuf_array = [0.95] * len(cuf_assets)
        else:
            cuf_array = optimize_cuf(cuf_assets, surplus)

        for i, cuf in enumerate(cuf_array):
            cuf_assets[i].capacity_factor = cuf

    # Get demand balance (demand - production)
    demand = pathway.get_demand(product=product, year=year, region=MODEL_SCOPE)
    production = new_stack.get_annual_production(product)

    # TODO: Decommission until one asset short of balance between demand and production
    surplus = demand - production
    while surplus > 0:

        # Identify asset to be decommissioned
        asset_transition = select_best_transition(
            df_rank=df_rank,
        )

        new_asset = make_new_asset(
            asset_transition=asset_transition,
            df_process_data=df_process_data,
            year=year,
            retrofit=False,
            product=product,
            df_asset_capacities=pathway.df_asset_capacities,
        )

        logger.info(
            f"Building new asset with technology {new_asset.technology} in region {new_asset.region}, annual production {new_asset.get_annual_production(product)} and UUID {new_asset.uuid}"
        )

        new_stack.append(new_asset)
        surplus -= new_asset.get_annual_production(product)

    return pathway

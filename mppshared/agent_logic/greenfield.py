""" Logic for technology transitions of type greenfield (add new Asset to AssetStack."""

from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.models.plant import PlantStack, Plant, make_new_plant
from mppshared.agent_logic.agent_logic_functions import (
    select_best_transition,
    optimize_cuf,
)
from mppshared.models.constraints import check_constraints
from mppshared.utility.utils import get_logger
from mppshared.config import LOG_LEVEL, MODEL_SCOPE, ASSUMED_PLANT_CAPACITY


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
    """Apply newbuild transition to eligible Assets in the AssetStack.

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

    # TODO: Change rank_type to new_build
    # Get ranking table for decommissioning
    df_rank = pathway.get_ranking(product=product, year=year, rank_type="greenfield")

    # TODO: Decommission until one plant short of balance between demand and production
    surplus = demand - production
    while surplus > 0:
        # Check whether it is even possible to increase CUF
        cuf_plants = list(
            filter(lambda plant: plant.capacity_factor < 0.95, new_stack.plants)
        )
        if not cuf_plants:
            break

        # Optimize capacity factor and check whether surplus is covered
        if (surplus / ASSUMED_PLANT_CAPACITY) / len(cuf_plants) > 0.95:
            cuf_array = [0.95] * len(cuf_plants)
        else:
            cuf_array = optimize_cuf(cuf_plants, surplus)

        for i, cuf in enumerate(cuf_array):
            cuf_plants[i].capacity_factor = cuf

    # Get demand balance (demand - production)
    demand = pathway.get_demand(product=product, year=year, region=MODEL_SCOPE)
    production = new_stack.get_annual_production(product)

    # TODO: Decommission until one plant short of balance between demand and production
    surplus = demand - production
    while surplus > 0:

        # Identify asset to be decommissioned
        asset_transition = select_best_transition(
            df_rank=df_rank,
        )

        new_plant = make_new_plant(
            asset_transition=asset_transition,
            df_process_data=df_process_data,
            year=year,
            retrofit=False,
            product=product,
            df_plant_capacities=pathway.df_plant_capacities,
        )

        logger.info(
            f"Building new plant with technology {new_plant.technology} in region {new_plant.region}, annual production {new_plant.get_annual_production(product)} and UUID {new_plant.uuid}"
        )

        new_stack.append(new_plant)
        surplus -= new_plant.get_annual_production(product)

    return pathway

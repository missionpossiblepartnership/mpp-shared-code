import logging

import pandas as pd

from config import AGE_DEPENDENCY, DECOMMISSION_RATES, \
    FORCE_DECOMMISSION_EARLIEST_YEAR, MODEL_SCOPE
from mppshared.pathway.simpathway import SimulationPathway
from mppshared.plant.plant import PlantStack
from util.util import get_plant_capacity_mt

logger = logging.getLogger(__name__)
logger.setLevel("INFO")


def select_plant_to_decommission(
    stack: PlantStack, df_rank: pd.DataFrame, df_tech: pd.DataFrame, chemical: str
):
    """
    Select plant to decommission, based on cost or emissions

    Args:
        stack:
        df_rank:
        df_tech:

    Returns:

    """

    # Keep only plants that exist
    df_old_tech = stack.get_unique_tech(chemical=chemical)
    df_rank = df_rank.merge(
        df_old_tech, left_on=["destination", "region"], right_on=["technology", "region"]
    )

    if df_rank.empty:
        raise ValueError("No more plants to decommission!")

    plant = (
        df_rank[
            df_rank["rank"]
            == df_rank["rank"].min()
        ]
        .sample(n=1)
        .to_dict(orient="records")
    )[0]

    return {
        "technology": plant["destination"],
        "region": plant["region"],
        "chemical": plant["chemical"],
    }


def decommission(pathway: SimulationPathway, year: int, chemical: str):
    """
    Decommission plants: close old tech down

    Args:
        chemical: Run for this chemical
        pathway: The decarbonization pathway
        year: Run for this year

    Returns:
        Updated pathway
    """

    df_rank = pathway.get_ranking(
        year=year, chemical=chemical, rank_type="decommission"
    )

    # Get next year's stack
    stack = pathway.get_stack(year=year + 1)

    # Determine how many plants to decommission
    yearly_volume = stack.get_yearly_volume(chemical=chemical)
    demand = pathway.get_demand(year=year, chemical=chemical)
    surplus = yearly_volume - demand

    # Get the tech available now
    df_tech = pathway.tech

    # Only keep tech that this chemical is the primary chemical of
    df_rank = pathway.filter_tech_primary_chemical(df_tech=df_rank, chemical=chemical, col="destination")

    # Decommission to follow demand decrease; only decommission if we have > 1 plant capacity surplus
    while surplus > get_plant_capacity_mt():
        try:
            decommission_spec = select_plant_to_decommission(
                stack=stack.get_old_plant_stack() if (chemical in AGE_DEPENDENCY and MODEL_SCOPE == "World") else stack,
                df_rank=df_rank,
                df_tech=df_tech,
                chemical=chemical,
            )

        except ValueError:
            logger.info("No more plants to decommission")
            break

        remove_plants = stack.filter_plants(**decommission_spec)
        remove_plants.sort(key=lambda plant: plant.start_year, reverse=False)
        remove_plant = remove_plants[0]
        logger.info("Removing plant with spec %s", decommission_spec)

        # Remove the old
        stack.remove(remove_plant)

        surplus -= remove_plant.get_yearly_volume(chemical=chemical)

    if year >= FORCE_DECOMMISSION_EARLIEST_YEAR and pathway.pathway_name != "bau":
        stack = decommission_old_tech(chemical, df_rank, df_tech, stack)

    return pathway.update_stack(year=year + 1, stack=stack)


def decommission_old_tech(chemical, df_rank, df_tech, stack):
    """ Additionally, decommission to get rid of old tech"""
    for technology in DECOMMISSION_RATES.keys():
        if technology in df_rank.destination.values:
            decommission_rate = DECOMMISSION_RATES[technology]
            total_volume = sum(
                plant.get_yearly_volume(chemical=chemical)
                for plant in stack.filter_plants(technology=technology)
            )

            decommission_volume = total_volume * decommission_rate

            while decommission_volume > 0 or total_volume <= get_plant_capacity_mt():
                try:
                    decommission_spec = select_plant_to_decommission(
                        stack=stack.get_tech_plant_stack(technology=technology),
                        df_rank=df_rank,
                        df_tech=df_tech,
                        chemical=chemical,
                    )
                except ValueError:
                    logger.info("No more plants to decommission")
                    break

                remove_plants = stack.filter_plants(**decommission_spec)
                remove_plants.sort(key=lambda plant: plant.start_year, reverse=False)
                remove_plant = remove_plants[0]
                logger.info("Removing plant with spec %s", decommission_spec)

                # Remove the old
                stack.remove(remove_plant)

                decommission_volume -= remove_plant.get_yearly_volume(chemical=chemical)

    return stack

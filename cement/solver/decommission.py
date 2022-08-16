"""Decommission plants."""

from cement.config.config_cement import LOG_LEVEL, MODEL_SCOPE
from mppshared.agent_logic.decommission import get_best_asset_to_decommission_cement
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def decommission(pathway: SimulationPathway, year: int) -> SimulationPathway:
    """Apply decommission transition to eligible Assets in the AssetStack.

    Args:
        pathway: decarbonization pathway that describes the composition of the AssetStack in every year of the model
            horizon
        year: current year in which technology transitions are enacted

    Returns:
        Updated decarbonization pathway with the updated AssetStack in the subsequent year according to the decommission
            transitions enacted
    """

    # todo: decommission per region!

    for product in pathway.products:

        logger.info(f"Running decommission logic for {product}")

        # Current stack is for calculating production, next year's stack is updated with each decommissioning
        old_stack = pathway.get_stack(year=year - 1)
        new_stack = pathway.get_stack(year=year)

        # Get demand balance (demand - production)
        demand = pathway.get_demand(product=product, year=year, region=MODEL_SCOPE)
        production = old_stack.get_annual_production_volume(product)

        # Get ranking table for decommissioning
        df_rank = pathway.get_ranking(year=year, rank_type="decommission")
        df_rank = df_rank.loc[df_rank["product"] == product]

        # Decommission while production exceeds demand
        surplus = production - demand
        logger.debug(
            f"Year: {year} Production: {production}, Demand: {demand}, Surplus: {surplus}"
        )
        while surplus > 0:

            # Identify asset to be decommissioned
            try:
                asset_to_remove = get_best_asset_to_decommission_cement(
                    stack=new_stack,
                    df_rank=df_rank,
                    product=product,
                )

                # TODO: check if removing this asset violates any constraints

            except ValueError:
                logger.info("--No more assets to decommission")
                break

            logger.debug(
                f"--Removing asset with technology {asset_to_remove.technology} in region {asset_to_remove.region}, "
                f"annual production {asset_to_remove.get_annual_production_volume()} and UUID {asset_to_remove.uuid}"
            )

            new_stack.remove(asset_to_remove)

            surplus -= asset_to_remove.get_annual_production_volume()

            pathway.transitions.add(
                transition_type="decommission", year=year, origin=asset_to_remove
            )

    return pathway

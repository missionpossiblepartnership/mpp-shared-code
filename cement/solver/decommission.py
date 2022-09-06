"""Decommission plants."""

from cement.config.config_cement import (
    LOG_LEVEL,
    REGIONS,
    CAPACITY_UTILISATION_FACTOR,
    ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
)
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

    logger.debug(f"{year}: Starting decommission logic")

    product = pathway.products[0]
    old_stack = pathway.get_stack(year=year - 1)
    new_stack = pathway.get_stack(year=year)

    for region in REGIONS:

        logger.info(f"Running decommission logic in {region}")

        # Get demand balance (demand - production)
        demand = pathway.get_demand(product=product, year=year, region=region)
        production = old_stack.get_annual_production_volume(
            product=product, region=region
        )

        # Get ranking table for decommissioning
        df_rank_region = pathway.get_ranking(year=year, rank_type="decommission")
        df_rank_region = df_rank_region.loc[df_rank_region["region"] == region]

        # Decommission while production exceeds demand
        surplus = production - demand
        logger.debug(
            f"{year}, {region}: Production: {production} Mt {product}, Demand: {demand} Mt {product}, "
            f"Surplus: {surplus} Mt {product}"
        )

        # decommission plants while the surplus is higher than one plant's production volume
        while (
            surplus >= ASSUMED_ANNUAL_PRODUCTION_CAPACITY * CAPACITY_UTILISATION_FACTOR
        ):

            # Identify asset to be decommissioned
            try:
                asset_to_remove = get_best_asset_to_decommission_cement(
                    stack=new_stack,
                    df_rank_region=df_rank_region,
                    product=product,
                    region=region,
                )
                # TODO: check if removing this asset violates any constraints
            except ValueError:
                logger.info("No more assets to decommission")
                break

            logger.debug(
                f"Removing asset in {asset_to_remove.region} with technology {asset_to_remove.technology}, "
                f"annual production {asset_to_remove.get_annual_production_volume()} and UUID {asset_to_remove.uuid}"
            )

            new_stack.remove(asset_to_remove)

            surplus -= asset_to_remove.get_annual_production_volume()

            pathway.transitions.add(
                transition_type="decommission", year=year, origin=asset_to_remove
            )

    return pathway

""" Logic for technology transitions of type greenfield (add new Asset to AssetStack."""

import numpy as np

from cement.config.config_cement import (
    ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
    CAPACITY_UTILISATION_FACTOR,
    LOG_LEVEL,
    CONSTRAINTS_REGIONAL_CHECK,
)
from mppshared.agent_logic.greenfield import (
    enact_greenfield_transition,
    get_region_rank_filter,
    select_asset_for_greenfield,
)
from mppshared.models.constraints import get_regional_production_constraint_table
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def greenfield(pathway: SimulationPathway, year: int) -> SimulationPathway:
    """Apply greenfield transition and add new Assets to the AssetStack.

    Args:
        pathway: decarbonization pathway that describes the composition of the AssetStack in every year of the model
            horizon
        year: current year in which technology transitions are enacted

    Returns:
        Updated decarbonization pathway with the updated AssetStack in the subsequent year according to the greenfield
            transitions enacted
    """
    logger.info(f"{year}: Starting greenfield transition logic")
    stack = pathway.get_stack(year=year)

    # Get ranking table for greenfield transitions
    df_rank = pathway.get_ranking(year=year, rank_type="greenfield")

    product = pathway.products[0]

    # Build new capacity in each region to make sure that the regional production fulfills the regional demand
    df_regional_production = get_regional_production_constraint_table(
        pathway=pathway, stack=stack, product=product, year=year
    )

    # For each region with a production deficit, build new capacity until production meets required minimum
    for (index, row) in df_regional_production.loc[
        ~df_regional_production["check"]
    ].iterrows():
        deficit = (
            row["annual_production_volume_minimum"] - row["annual_production_volume"]
        )
        region = row["region"]
        number_new_assets = np.ceil(
            deficit / (ASSUMED_ANNUAL_PRODUCTION_CAPACITY * CAPACITY_UTILISATION_FACTOR)
        )
        logger.info(
            f"{year}: Building {number_new_assets} new assets in {region} to fulfil production deficit "
            f"of {deficit} Mt {product}"
        )
        # todo: update as this is for low cost power regions
        region_rank_filter = get_region_rank_filter(
            region=region, sector=pathway.sector
        )
        df_rank_region = df_rank.loc[df_rank["region"].isin(region_rank_filter)]

        # Build the required number of assets to meet the minimum production volume
        while number_new_assets >= 1:
            try:
                new_asset, df_rank_region = select_asset_for_greenfield(
                    pathway=pathway,
                    stack=stack,
                    product=product,
                    df_rank=df_rank_region,
                    year=year,
                    annual_production_capacity=ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
                    cuf=CAPACITY_UTILISATION_FACTOR,
                    return_df_rank=True,
                    constraints_regional_check=CONSTRAINTS_REGIONAL_CHECK,
                )
                enact_greenfield_transition(
                    pathway=pathway, stack=stack, new_asset=new_asset, year=year
                )
                number_new_assets -= 1
            except ValueError:
                logger.info(
                    "No more assets for greenfield transition within constraints"
                )
                break

    return pathway

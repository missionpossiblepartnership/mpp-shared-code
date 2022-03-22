import logging

from mppshared.config import (
    START_YEAR,
    END_YEAR,
    LOG_LEVEL,
)
from mppshared.import_data.intermediate_data import IntermediateDataImporter

# from mppshared.agent_logic.build_new import build_new
# from mppshared.agent_logic.decommission import decommission
# from mppshared.agent_logic.retrofit import retrofit
from mppshared.pathway.simpathway import SimulationPathway
# from util.util import timing

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)


def simulate(pathway: SimulationPathway):
    """
    Run the pathway simulation over the years:
        - First, decommission a fixed % of plants
        - Then, retrofit a fixed %
        - Then, build new if increasing demand
    Args:
        pathway: The decarb pathway

    Returns:
        The updated pathway
    """

    for year in range(START_YEAR, END_YEAR):
        logger.info("Optimizing for %s", year)
        pathway.update_plant_status(year=year)

        # Copy over last year's stack to this year
        pathway = pathway.copy_stack(year=year)
        # Run model for all chemicals (Methanol last as it needs MTO/A/P demand)
        for product in pathway.products:
            logger.info(product)

            # Decommission assets
            pathway = decommission(pathway=pathway, year=year, product=product)

            # Retrofit assets, except for business as usual scenario
            if pathway.pathway_name != "bau":
                pathway = retrofit(pathway=pathway, year=year, product=product)

            # Build new assers
            pathway = build_new(pathway=pathway, year=year, product=product)

        # Copy availability to next year
        pathway.copy_availability(year=year)

    return pathway


def simulate_pathway(sector, product, pathway, sensitivity):
    """
    Get data per technology, ranking data and then run the pathway simulation
    """
    importer = IntermediateDataImporter(
        pathway=pathway, sensitivity=sensitivity, sector=sector, product=product
    )

    # Make pathway
    pathway = SimulationPathway(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector, 
        product=product,
        start_year=START_YEAR,
        end_year=END_YEAR,
    )

    # Optimize plant stack on a yearly basis
    pathway = simulate(
        pathway=pathway,
    )

    # Save rankings after they have been adjusted due to MTO
    pathway.save_rankings()
    pathway.save_availability()
    pathway.save_demand()

    for product in PRODUCT[SECTOR]:
        df_stack_total = pathway.aggregate_stacks(this_year=False, product=product)
        df_stack_new = pathway.aggregate_stacks(this_year=True, product=product)

        importer.export_data(
            df=df_stack_total,
            filename="technologies_over_time_region.csv",
            export_dir=f"final/{product}",
        )

        importer.export_data(
            df=df_stack_new,
            filename="technologies_over_time_region_new.csv",
            export_dir=f"final/{product}",
        )

        pathway.plot_stacks(df_stack_total, groupby="technology", chemical=chemical)
        pathway.plot_stacks(df_stack_total, groupby="region", chemical=chemical)

    logger.info("Pathway simulation complete")

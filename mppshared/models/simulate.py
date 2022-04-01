import logging

from mppshared.config import END_YEAR, LOG_LEVEL, START_YEAR, PRODUCTS, SECTOR
from mppshared.import_data.intermediate_data import IntermediateDataImporter

# from mppshared.agent_logic.new_build import new_build
from mppshared.agent_logic.decommission import decommission
from mppshared.agent_logic.brownfield import retrofit
from mppshared.agent_logic.greenfield import greenfield

from mppshared.models.asset import AssetStack

# from mppshared.agent_logic.retrofit import retrofit
from mppshared.models.simulation_pathway import SimulationPathway

# from util.util import timing

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)


def simulate(pathway: SimulationPathway) -> SimulationPathway:
    """
    Run the pathway simulation over the years:
        - First, decommission a fixed % of assets
        - Then, retrofit a fixed %
        - Then, build new if increasing demand
    Args:
        pathway: The decarb pathway

    Returns:
        The updated pathway
    """

    for year in range(START_YEAR, END_YEAR + 1):
        logger.info("Optimizing for %s", year)
        pathway.update_asset_status(year=year)

        # Copy over last year's stack to this year
        pathway = pathway.copy_stack(year=year)
        # Run model for all chemicals (Methanol last as it needs MTO/A/P demand)
        for product in pathway.products:
            logger.info(product)

            # Decommission assets
            pathway = decommission(pathway=pathway, year=year, product=product)

            # Retrofit assets, except for business as usual scenario
            # if pathway.pathway_name != "bau":
            #     pathway = retrofit(pathway=pathway, year=year, product=product)

            # Build new assets
            # pathway = greenfield(pathway=pathway, year=year, product=product)

            # Write stack to csv
            pathway.export_stack_to_csv(year)

        # Copy availability to next year
        # pathway.copy_availability(year=year)

    return pathway


def simulate_pathway(sector: str, pathway: str, sensitivity: str):
    """
    Get data per technology, ranking data and then run the pathway simulation
    """
    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS[sector],
    )

    # Make pathway
    pathway = SimulationPathway(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS[sector],
        year_commissioned=START_YEAR,
        end_year=END_YEAR,
    )

    # Optimize asset stack on a yearly basis
    pathway = simulate(
        pathway=pathway,
    )

    # Save rankings after they have been adjusted due to MTO
    pathway.save_rankings()
    pathway.save_availability()
    pathway.save_demand()

    for product in PRODUCTS[SECTOR]:
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

        pathway.plot_stacks(df_stack_total, groupby="technology", product=product)
        pathway.plot_stacks(df_stack_total, groupby="region", product=product)

    logger.info("Pathway simulation complete")

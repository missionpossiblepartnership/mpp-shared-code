import logging

from mppshared.config import (
    END_YEAR,
    LOG_LEVEL,
    SECTORAL_CARBON_BUDGETS,
    START_YEAR,
    PRODUCTS,
    SECTOR,
)
from mppshared.import_data.intermediate_data import IntermediateDataImporter

from mppshared.agent_logic.decommission import decommission
from mppshared.agent_logic.brownfield import brownfield
from mppshared.agent_logic.greenfield import greenfield
from mppshared.agent_logic.agent_logic_functions import adjust_capacity_utilisation
from mppshared.models.carbon_budget import CarbonBudget, carbon_budget_test
from mppshared.utility.log_utility import get_logger

from mppshared.models.asset import AssetStack

# from mppshared.agent_logic.retrofit import retrofit
from mppshared.models.simulation_pathway import SimulationPathway

# from util.util import timing

logger = get_logger(__name__)
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

        # Copy over last year's stack to this year
        pathway = pathway.copy_stack(year=year)

        # Run pathway simulation for each product
        for product in pathway.products:

            logger.info(product)

            # Adjust capacity utilisation of each asset
            pathway = adjust_capacity_utilisation(
                pathway=pathway, year=year, product=product
            )

            #! Debug: set carbon budget start to initial emissions (needs to be implemented)
            if year == START_YEAR:
                emissions = pathway.calculate_emissions_stack(year, product)
                limit = (emissions["co2_scope1"] + emissions["co2_scope2"]) / 1e3
                df = pathway.carbon_budget.pathways[pathway.sector]
                df.loc[START_YEAR, "annual_limit"] = limit

            # Decommission assets
            pathway = decommission(pathway=pathway, year=year, product=product)

            # Renovate and rebuild assets (brownfield transition)
            pathway = brownfield(pathway=pathway, year=year, product=product)

            # Build new assets
            pathway = greenfield(pathway=pathway, year=year, product=product)

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

    # Create carbon budget
    carbon_budget = CarbonBudget(
        sectoral_carbon_budgets=SECTORAL_CARBON_BUDGETS, pathway_shape="linear"
    )

    # Make pathway
    pathway = SimulationPathway(
        start_year=START_YEAR,
        end_year=END_YEAR,
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS[sector],
        carbon_budget=carbon_budget,
    )

    # Optimize asset stack on a yearly basis
    pathway = simulate(
        pathway=pathway,
    )

    #! Development only: plot technology roadmap and emission trajectory
    pathway.create_technology_roadmap()
    pathway.create_emission_trajectory()

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

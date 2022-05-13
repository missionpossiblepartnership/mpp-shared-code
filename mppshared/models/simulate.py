from datetime import timedelta
from timeit import default_timer as timer

from mppshared.agent_logic.agent_logic_functions import adjust_capacity_utilisation
from mppshared.agent_logic.brownfield import brownfield
from mppshared.agent_logic.decommission import decommission
from mppshared.agent_logic.greenfield import greenfield
from mppshared.config import (
    END_YEAR,
    LOG_LEVEL,
    PRODUCTS,
    SECTORAL_CARBON_BUDGETS,
    START_YEAR,
    TECHNOLOGY_RAMP_UP_CONSTRAINTS,
)
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.models.asset import AssetStack
from mppshared.models.carbon_budget import CarbonBudget

# from mppshared.agent_logic.retrofit import retrofit
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.utility.log_utility import get_logger
from mppshared.models.technology_rampup import TechnologyRampup

# from util.util import timing

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def simulate(pathway: SimulationPathway) -> SimulationPathway:
    """
    Run the pathway simulation over the years
    Args:
        pathway: The decarbonization pathway

    Returns:
        The updated pathway with the asset stack in each year of the model horizon
    """

    # Run pathway simulation in each year for all products simultaneously
    for year in range(START_YEAR, END_YEAR + 1):
        logger.info("Optimizing for %s", year)

        # Copy over last year's stack to this year
        pathway = pathway.copy_stack(year=year)

        # Adjust capacity utilisation of each asset
        pathway = adjust_capacity_utilisation(
            pathway=pathway, year=year, product=product
        )

        # Write stack to csv
        pathway.export_stack_to_csv(year)

        # Decommission assets
        start = timer()
        pathway = decommission(pathway=pathway, year=year, product=product)
        end = timer()
        logger.debug(
            f"Time elapsed for decommission in year {year}: {timedelta(seconds=end-start)} seconds"
        )

        # Renovate and rebuild assets (brownfield transition)
        start = timer()
        pathway = brownfield(pathway=pathway, year=year, product=product)
        end = timer()
        logger.debug(
            f"Time elapsed for brownfield in year {year}: {timedelta(seconds=end-start)} seconds"
        )

        # Build new assets
        start = timer()
        pathway = greenfield(pathway=pathway, year=year, product=product)
        end = timer()
        logger.debug(
            f"Time elapsed for greenfield in year {year}: {timedelta(seconds=end-start)} seconds"
        )

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
        sectoral_carbon_budgets=SECTORAL_CARBON_BUDGETS,
        pathway_shape="linear",
        sector=sector,
        importer=importer,
    )
    carbon_budget.output_emissions_pathway(sector=sector, importer=importer)

    # Create technology ramp-up trajectory for each technology in the form of a dictionary
    dict_technology_rampup = create_dict_technology_rampup(
        sector=sector, importer=importer
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
        technology_rampup=dict_technology_rampup,
    )

    #! Development only
    # pathway.stacks[2020].assets = pathway.stacks[2020].assets[0:3]

    # Optimize asset stack on a yearly basis
    pathway = simulate(
        pathway=pathway,
    )

    logger.info("Pathway simulation complete")


def create_dict_technology_rampup(
    sector: str, importer: IntermediateDataImporter
) -> dict:
    """Create dictionary of TechnologyRampup objects with the technologies in that sector as keys. Set None if the technology has no ramp-up trajectory."""

    technology_characteristics = importer.get_technology_characteristics()
    technologies = technology_characteristics["technology"].unique()
    dict_technology_rampup = dict.fromkeys(technologies)

    for technology in technologies:

        # Expected maturity and classification are constant across regions, products and years, hence take the first row for that technology
        df_characteristics = technology_characteristics.loc[
            technology_characteristics["technology"] == technology
        ].iloc[0]
        expected_maturity = df_characteristics["expected_maturity"]
        classification = df_characteristics["technology_classification"]

        # Only define technology ramp-up rates for transition and end-state technologies
        if classification in ["transition", "end-state"]:
            dict_technology_rampup[technology] = TechnologyRampup(
                technology=technology,
                start_year=expected_maturity,
                end_year=expected_maturity
                + TECHNOLOGY_RAMP_UP_CONSTRAINTS[sector]["years_rampup_phase"],
                maximum_asset_additions=TECHNOLOGY_RAMP_UP_CONSTRAINTS[sector][
                    "maximum_asset_additions"
                ],
                maximum_capacity_growth_rate=TECHNOLOGY_RAMP_UP_CONSTRAINTS[sector][
                    "maximum_capacity_growth_rate"
                ],
            )

    return dict_technology_rampup

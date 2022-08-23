"""Year-by-year optimisation logic of plant investment decisions to simulate a pathway for the cement supply technology
    mix.
"""

from datetime import timedelta
from timeit import default_timer as timer

from cement.config.config_cement import (
    MAX_ANNUAL_RENOVATION_SHARE,
    ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
    CAPACITY_UTILISATION_FACTOR,
    CARBON_BUDGET_SECTOR_CSV,
    CARBON_BUDGET_SHAPE,
    CONSTRAINTS_TO_APPLY,
    EMISSION_SCOPES,
    END_YEAR,
    GHGS,
    INITIAL_ASSET_DATA_LEVEL,
    INVESTMENT_CYCLE,
    LOG_LEVEL,
    PRODUCTS,
    RANK_TYPES,
    REGIONAL_PRODUCTION_SHARES,
    SECTORAL_CARBON_BUDGETS,
    SECTORAL_CARBON_PATHWAY,
    START_YEAR,
    TECHNOLOGY_RAMP_UP_CONSTRAINT,
    YEAR_2050_EMISSIONS_CONSTRAINT,
)
from cement.solver.brownfield import brownfield
from cement.solver.decommission import decommission
from cement.solver.greenfield import greenfield
from mppshared.agent_logic.agent_logic_functions import create_dict_technology_rampup
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.models.carbon_budget import CarbonBudget
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def _simulate(pathway: SimulationPathway) -> SimulationPathway:
    """
    Run the pathway simulation over the years
    Args:
        pathway: The decarbonization pathway

    Returns:
        The updated pathway with the asset stack in each year of the model horizon
    """

    assert (
        len(PRODUCTS) == 1
    ), "Adjust cement model logic if more than one product!"
    product = PRODUCTS[0]

    # Write initial stack to csv
    pathway.export_stack_to_csv(year=START_YEAR)

    # Run pathway simulation in each year for all products simultaneously
    for year in range(START_YEAR + 1, END_YEAR + 1):
        logger.info(f"{year}: Start pathway simulation")

        # Copy over last year's stack to this year
        pathway = pathway.copy_stack(year=year - 1)

        # Decommission assets
        logger.info(
            f"{year}: Production volumes pre decommission: {hex(id(pathway.stacks[year]))}"
        )
        pathway.stacks[year].log_annual_production_volume_by_region_and_tech(
            product=product
        )
        start = timer()
        pathway = decommission(pathway=pathway, year=year)
        end = timer()
        logger.debug(
            f"{year}: Time elapsed for decommission: {timedelta(seconds=end-start)} seconds"
        )

        # Renovate and rebuild assets (brownfield transition)
        logger.info(
            f"{year}: Production volumes pre brownfield: {hex(id(pathway.stacks[year]))}"
        )
        pathway.stacks[year].log_annual_production_volume_by_region_and_tech(
            product=product
        )
        start = timer()
        pathway = brownfield(pathway=pathway, year=year)
        end = timer()
        logger.debug(
            f"{year}: Time elapsed for brownfield: {timedelta(seconds=end-start)} seconds"
        )

        # Build new assets
        logger.info(
            f"{year}: Production volumes pre greenfield: {hex(id(pathway.stacks[year]))}"
        )
        pathway.stacks[year].log_annual_production_volume_by_region_and_tech(
            product=product
        )
        start = timer()
        pathway = greenfield(pathway=pathway, year=year)
        end = timer()
        logger.debug(
            f"{year}: Time elapsed for greenfield: {timedelta(seconds=end-start)} seconds"
        )
        logger.info(
            f"{year}: Production volumes post greenfield: {hex(id(pathway.stacks[year]))}"
        )
        pathway.stacks[year].log_annual_production_volume_by_region_and_tech(
            product=product
        )

        # Write stack to csv
        pathway.export_stack_to_csv(year=year)

    return pathway


def simulate_pathway(sector: str, pathway_name: str, sensitivity: str, products: list):
    """
    Get data per technology, ranking data and then run the pathway simulation
    """

    importer = IntermediateDataImporter(
        pathway_name=pathway_name,
        sensitivity=sensitivity,
        sector=sector,
        products=products,
    )

    # copy config file to output folder
    importer.export_sector_config()

    # Create carbon budget
    carbon_budget = CarbonBudget(
        start_year=START_YEAR,
        end_year=END_YEAR,
        sectoral_carbon_budgets=SECTORAL_CARBON_BUDGETS,
        pathway_shape=CARBON_BUDGET_SHAPE,
        sector=sector,
        carbon_budget_sector_csv=CARBON_BUDGET_SECTOR_CSV,
        sectoral_carbon_pathway=SECTORAL_CARBON_PATHWAY,
        importer=importer,
    )

    # Create technology ramp-up trajectory for each technology in the form of a dictionary
    dict_technology_rampup = create_dict_technology_rampup(
        importer=importer,
        model_start_year=START_YEAR,
        model_end_year=END_YEAR,
        maximum_asset_additions=TECHNOLOGY_RAMP_UP_CONSTRAINT[
            "maximum_asset_additions"
        ],
        maximum_capacity_growth_rate=TECHNOLOGY_RAMP_UP_CONSTRAINT[
            "maximum_capacity_growth_rate"
        ],
        years_rampup_phase=TECHNOLOGY_RAMP_UP_CONSTRAINT["years_rampup_phase"],
    )

    # Make pathway
    pathway = SimulationPathway(
        start_year=START_YEAR,
        end_year=END_YEAR,
        pathway_name=pathway_name,
        sensitivity=sensitivity,
        sector=sector,
        products=products,
        rank_types=RANK_TYPES,
        initial_asset_data_level=INITIAL_ASSET_DATA_LEVEL,
        assumed_annual_production_capacity=ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
        technology_rampup=dict_technology_rampup,
        carbon_budget=carbon_budget,
        emission_scopes=EMISSION_SCOPES,
        cuf_lower_threshold=CAPACITY_UTILISATION_FACTOR,
        cuf_upper_threshold=CAPACITY_UTILISATION_FACTOR,
        ghgs=GHGS,
        regional_production_shares=REGIONAL_PRODUCTION_SHARES,
        investment_cycle=INVESTMENT_CYCLE,
        annual_renovation_share=MAX_ANNUAL_RENOVATION_SHARE,
        constraints_to_apply=CONSTRAINTS_TO_APPLY[pathway_name],
        year_2050_emissions_constraint=YEAR_2050_EMISSIONS_CONSTRAINT,
        set_natural_gas_constraint=(
            "natural_gas_constraint" in CONSTRAINTS_TO_APPLY[pathway_name]
        ),
        set_alternative_fuel_constraint=(
            "alternative_fuel_constraint" in CONSTRAINTS_TO_APPLY[pathway_name]
        ),
    )

    # Optimize asset stack on a yearly basis
    _simulate(pathway=pathway)
    
    logger.info("Pathway simulation complete")

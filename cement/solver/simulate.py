"""Year-by-year optimisation logic of plant investment decisions to simulate a pathway for the cement supply technology
    mix.
"""

from datetime import timedelta
from timeit import default_timer as timer

from cement.config.config_cement import (
    ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
    CAPACITY_UTILISATION_FACTOR,
    CARBON_BUDGET_SECTOR_CSV,
    CARBON_BUDGET_SHAPE,
    CO2_STORAGE_CONSTRAINT_TYPE,
    CONSTRAINTS_TO_APPLY,
    EMISSION_SCOPES,
    END_YEAR,
    GHGS,
    INITIAL_ASSET_DATA_LEVEL,
    INVESTMENT_CYCLE,
    LOG_LEVEL,
    MAX_ANNUAL_RENOVATION_SHARE,
    PRODUCTS,
    RAMP_UP_TECH_CLASSIFICATIONS,
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
from mppshared.models.constraints import (
    check_constraint_regional_production,
    check_constraints,
)
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

    assert len(PRODUCTS) == 1, "Adjust cement model logic if more than one product!"
    product = PRODUCTS[0]

    # Write initial stack to csv
    pathway.export_stack_to_csv(year=START_YEAR)

    # Run pathway simulation in each year for all products simultaneously
    for year in range(START_YEAR + 1, END_YEAR + 1):
        logger.info(f"{year}: Start pathway simulation")

        # Copy over last year's stack to this year
        pathway = pathway.copy_stack(year=year - 1)

        """ Decommission assets """
        logger.info(f"{year}: Production volumes pre decommission:")
        pathway.stacks[year].log_annual_production_volume_by_region_and_tech(
            product=product
        )
        start = timer()
        pathway = decommission(pathway=pathway, year=year)
        end = timer()
        logger.debug(
            f"{year}: Time elapsed for decommission: {timedelta(seconds=end-start)} seconds"
        )

        """ Greenfield: Build new assets """
        logger.info(f"{year}: Production volumes pre greenfield:")
        pathway.stacks[year].log_annual_production_volume_by_region_and_tech(
            product=product
        )
        start = timer()
        pathway = greenfield(pathway=pathway, year=year)
        end = timer()
        logger.debug(
            f"{year}: Time elapsed for greenfield: {timedelta(seconds=end - start)} seconds"
        )
        logger.info(f"{year}: Production volumes post greenfield:")
        pathway.stacks[year].log_annual_production_volume_by_region_and_tech(
            product=product
        )
        # check constraints for all regions
        _check_all_constraints(pathway=pathway, year=year, transition_type="greenfield")

        """ Brownfield: Renovate and rebuild assets """
        logger.info(f"{year}: Production volumes pre brownfield:")
        pathway.stacks[year].log_annual_production_volume_by_region_and_tech(
            product=product
        )
        start = timer()
        pathway = brownfield(pathway=pathway, year=year)
        end = timer()
        logger.debug(
            f"{year}: Time elapsed for brownfield: {timedelta(seconds=end-start)} seconds"
        )
        # check constraints for all regions
        _check_all_constraints(pathway=pathway, year=year, transition_type="brownfield")

        # check regional production constraint
        if not check_constraint_regional_production(
            pathway=pathway,
            stack=pathway.stacks[year],
            product=product,
            year=year,
            transition_type="all",
        ):
            logger.critical(f"{year}: Not every region fulfills its demand!")

        # Write stack to csv
        pathway.export_stack_to_csv(year=year)

    return pathway


def _check_all_constraints(pathway: SimulationPathway, year: int, transition_type: str):
    # Check constraints with tentative new stack
    dict_constraints = check_constraints(
        pathway=pathway,
        stack=pathway.stacks[year],
        year=year,
        transition_type=transition_type,
        product=PRODUCTS[0],
        region=None,
    )
    # If no constraint is hurt, execute the brownfield transition
    if all(
        [
            dict_constraints[k]
            for k in dict_constraints.keys()
            if k in pathway.constraints_to_apply and k != "regional_constraint"
        ]
    ):
        logger.info(f"{year}: All constraints fulfilled for {transition_type}")
    else:
        logger.critical(f"{year}: Not all constraints fulfilled for {transition_type}")


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
        maximum_asset_additions=TECHNOLOGY_RAMP_UP_CONSTRAINT[pathway_name][
            "init_maximum_asset_additions"
        ],
        maximum_capacity_growth_rate=TECHNOLOGY_RAMP_UP_CONSTRAINT[pathway_name][
            "maximum_asset_growth_rate"
        ],
        years_rampup_phase=TECHNOLOGY_RAMP_UP_CONSTRAINT[pathway_name][
            "years_rampup_phase"
        ],
        ramp_up_tech_classifications=RAMP_UP_TECH_CLASSIFICATIONS,
    )
    carbon_budget.output_carbon_budget(sector=sector, importer=importer)

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
        annual_renovation_share=MAX_ANNUAL_RENOVATION_SHARE[pathway_name],
        constraints_to_apply=CONSTRAINTS_TO_APPLY[pathway_name],
        year_2050_emissions_constraint=YEAR_2050_EMISSIONS_CONSTRAINT,
        set_biomass_constraint=(
            "biomass_constraint" in CONSTRAINTS_TO_APPLY[pathway_name]
        ),
        set_co2_storage_constraint=(
            "co2_storage_constraint" in CONSTRAINTS_TO_APPLY[pathway_name]
        ),
        co2_storage_constraint_type=CO2_STORAGE_CONSTRAINT_TYPE,
    )

    # Optimize asset stack on a yearly basis
    _simulate(pathway=pathway)

    logger.info("Pathway simulation complete")

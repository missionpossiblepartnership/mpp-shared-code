"""Execute the MPP Cement model."""

# Library imports
import multiprocessing as mp

from cement.config.config_cement import (CARBON_COSTS, MODEL_YEARS, PRODUCTS,
                                         RUN_PARALLEL, SECTOR, SENSITIVITIES,
                                         run_config)
from cement.solver.implicit_forcing import apply_implicit_forcing
from cement.solver.import_data import import_and_preprocess
from cement.solver.output_processing import calculate_outputs
from cement.solver.ranking import make_rankings
from cement.solver.ranking_inputs import get_ranking_inputs
from cement.solver.simulate import simulate_pathway
# Shared imports
from mppshared.config import LOG_LEVEL
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory
# Initialize logger
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)

funcs = {
    "IMPORT_DATA": import_and_preprocess,
    "CALCULATE_VARIABLES": get_ranking_inputs,
    "APPLY_IMPLICIT_FORCING": apply_implicit_forcing,
    "MAKE_RANKINGS": make_rankings,
    "SIMULATE_PATHWAY": simulate_pathway,
    "CALCULATE_OUTPUTS": calculate_outputs,
    # "CREATE_DEBUGGING_OUTPUTS": create_debugging_outputs,
}


def _run_model(pathway_name, sensitivity):
    for name, func in funcs.items():
        if name in run_config:
            logger.info(
                f"Running pathway {pathway_name} sensitivity {sensitivity} section {name}"
            )
            func(
                pathway_name=pathway_name,
                sensitivity=sensitivity,
                sector=SECTOR,
                products=PRODUCTS,
            )


def run_model_sequential(runs):
    """Run model sequentially, slower but better for debugging"""
    # TODO: Pass carbon cost trajectories into the model
    for pathway_name, sensitivity in runs:
        _run_model(pathway_name=pathway_name, sensitivity=sensitivity)


def run_model_parallel(runs):
    """Run model in parallel, faster but harder to debug"""
    n_cores = mp.cpu_count()
    logger.info(f"{n_cores} cores detected")
    pool = mp.Pool(processes=n_cores - 1)
    logger.info(f"Running model for scenario/sensitivity {runs}")
    for pathway, sensitivity in runs:
        pool.apply_async(_run_model, args=(pathway, sensitivity))
    pool.close()
    pool.join()


def main():
    logger.info(f"Running model for {SECTOR}")

    # Create a list of carbon cost trajectories that each start in 2025 and have a constant carbon cost
    carbon_costs = CARBON_COSTS
    # carbon_costs = [1]  # for creating carbon cost addition DataFrame
    carbon_cost_trajectories = []
    end_year_map = {0: 2025, 50: 2030, 100: 2035, 150: 2040, 200: 2045, 250: 2050}
    for cc in carbon_costs:
        carbon_cost_trajectories.append(
            CarbonCostTrajectory(
                trajectory="linear",
                initial_carbon_cost=0,
                final_carbon_cost=cc,
                start_year=2025,
                end_year=end_year_map[cc],
                model_years=MODEL_YEARS,
            )
        )
    runs = []
    # Add the carbon cost into the runs

    for pathway, sensitivities in SENSITIVITIES.items():
        for sensitivity in sensitivities:
            runs.append((pathway, sensitivity))
    if RUN_PARALLEL:
        run_model_parallel(runs)
    else:
        run_model_sequential(runs)
    # save_consolidated_outputs(SECTOR)


if __name__ == "__main__":
    main()

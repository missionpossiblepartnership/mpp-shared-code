"""Execute the MPP Ammonia model."""

import itertools
import multiprocessing as mp
import os

import numpy as np
import distutils

from ammonia.config_ammonia import (
    CARBON_COSTS,
    END_YEAR,
    LOG_LEVEL,
    PATHWAYS,
    RUN_PARALLEL,
    SECTOR,
    SENSITIVITIES,
    run_config,
)
from ammonia.solver.implicit_forcing import apply_implicit_forcing
from mppshared.models.simulate import simulate_pathway
from mppshared.solver.debugging_outputs import create_debugging_outputs
from mppshared.solver.output_processing import calculate_outputs
from mppshared.solver.ranking import make_rankings
from mppshared.utility.utils import get_logger
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory

# from mppshared.solver.sensitivity_outputs import create_sensitivity_outputs

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)

np.random.seed(100)

funcs = {
    "APPLY_IMPLICIT_FORCING": apply_implicit_forcing,
    # "MAKE_RANKINGS": make_rankings,
    # "SIMULATE_PATHWAY": simulate_pathway,
    # "CALCULATE_OUTPUTS": calculate_outputs,
    # "CREATE_DEBUGGING_OUTPUTS": create_debugging_outputs,
    # "SENSITIVITY_ANALYSIS": create_sensitivity_outputs,
}


def _run_model(pathway, sensitivity, carbon_cost):
    for name, func in funcs.items():
        if name in run_config:
            logger.info(
                f"Running pathway {pathway} sensitivity {sensitivity} section {name}"
            )
            func(
                pathway=pathway,
                sensitivity=sensitivity,
                sector=SECTOR,
                carbon_cost_trajectory=carbon_cost,
            )


def run_model_sequential(runs):
    """Run model sequentially, slower but better for debugging"""
    for pathway, sensitivity, carbon_cost in runs:
        if "APPLY_IMPLICIT_FORCING" in funcs:
            # Copy intermediate folder to right carbon cost directory
            cc = carbon_cost.df_carbon_cost.loc[
                carbon_cost.df_carbon_cost["year"] == END_YEAR, "carbon_cost"
            ].item()
            for folder in ["final", "intermediate", "ranking", "stack_tracker"]:
                final_folder = (
                    f"data/{SECTOR}/{pathway}/{sensitivity}/carbon_cost_{cc}/{folder}"
                )
                if not os.path.exists(final_folder):
                    os.makedirs(final_folder)
                if folder == "intermediate":
                    source_dir = f"{SECTOR}/data/{pathway}/{sensitivity}/{folder}"
                    distutils.dir_util.copy_tree(source_dir, final_folder)
        _run_model(pathway=pathway, sensitivity=sensitivity, carbon_cost=carbon_cost)


def run_model_parallel(runs):
    """Run model in parallel, faster but harder to debug"""
    n_cores = mp.cpu_count()
    logger.info(f"{n_cores} cores detected")
    pool = mp.Pool(processes=n_cores)
    logger.info(f"Running model for scenario/sensitivity {runs}")
    for pathway, sensitivity, carbon_cost in runs:
        if "APPLY_IMPLICIT_FORCING" in funcs:
            # Copy intermediate folder to right carbon cost directory
            cc = carbon_cost.df_carbon_cost.loc[
                carbon_cost.df_carbon_cost["year"] == END_YEAR, "carbon_cost"
            ].item()
            for folder in ["final", "intermediate", "ranking", "stack_tracker"]:
                final_folder = (
                    f"{SECTOR}/data/{pathway}/{sensitivity}/carbon_cost_{cc}/{folder}"
                )
                if not os.path.exists(final_folder):
                    os.makedirs(final_folder)
                if folder == "intermediate":
                    source_dir = f"data/{SECTOR}/{pathway}/{sensitivity}/{folder}"
                    distutils.dir_util.copy_tree(source_dir, final_folder)
        pool.apply_async(_run_model, args=(pathway, sensitivity, carbon_cost))
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
            )
        )
    runs = list(itertools.product(PATHWAYS, SENSITIVITIES, carbon_cost_trajectories))
    if RUN_PARALLEL:
        run_model_parallel(runs)
    else:
        run_model_sequential(runs)
    # Create sensitivity outputs
    # if "SENSITIVITY_ANALYSIS" in funcs:
    #     create_sensitivity_outputs()


if __name__ == "__main__":
    main()
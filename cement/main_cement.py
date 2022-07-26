"""Execute the MPP Cement model."""

# Library imports
import multiprocessing as mp

from cement.config.config_cement import (PRODUCTS, RUN_PARALLEL, SECTOR,
                                         SENSITIVITIES, run_config)
from cement.solver.implicit_forcing import apply_implicit_forcing
from cement.solver.import_data import import_and_preprocess
from cement.solver.ranking_inputs import get_ranking_inputs
# Shared imports
from mppshared.config import LOG_LEVEL
# Initialize logger
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)

funcs = {
    "IMPORT_DATA": import_and_preprocess,
    "CALCULATE_VARIABLES": get_ranking_inputs,
    "APPLY_IMPLICIT_FORCING": apply_implicit_forcing,
    # "MAKE_RANKINGS": make_rankings,
    # "SIMULATE_PATHWAY": simulate_pathway,
    # "CALCULATE_OUTPUTS": calculate_outputs,
    # "CREATE_DEBUGGING_OUTPUTS": create_debugging_outputs,
}


def _run_model(pathway, sensitivity):
    for name, func in funcs.items():
        if name in run_config:
            logger.info(
                f"Running pathway {pathway} sensitivity {sensitivity} section {name}"
            )
            func(
                pathway=pathway,
                sensitivity=sensitivity,
                sector=SECTOR,
                products=PRODUCTS,
            )


def run_model_sequential(runs):
    """Run model sequentially, slower but better for debugging"""
    for pathway, sensitivity in runs:
        _run_model(pathway=pathway, sensitivity=sensitivity)


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
    runs = []
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

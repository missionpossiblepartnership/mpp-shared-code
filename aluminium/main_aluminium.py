"""Execute the MPP Aluminium model."""

# Library imports
import multiprocessing as mp

import numpy as np

from aluminium.config_aluminium import RUN_PARALLEL, SECTOR, SENSITIVITIES, run_config
from aluminium.solver.implicit_forcing import apply_implicit_forcing
from aluminium.solver.output_processing import calculate_outputs
from aluminium.solver.ranking import make_rankings
from aluminium.solver.simulate import simulate_pathway

# Shared imports
from mppshared.config import LOG_LEVEL
from mppshared.solver.output_processing import save_consolidated_outputs

# Initialize logger
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)

funcs = {
    "APPLY_IMPLICIT_FORCING": apply_implicit_forcing,
    "MAKE_RANKINGS": make_rankings,
    "SIMULATE_PATHWAY": simulate_pathway,
    "CALCULATE_OUTPUTS": calculate_outputs,
}


def _run_model(pathway, sensitivity):
    for name, func in funcs.items():
        if name in run_config:
            logger.info(
                f"Running pathway {pathway} sensitivity {sensitivity} section {name}"
            )
            func(
                pathway_name=pathway,
                sensitivity=sensitivity,
                sector=SECTOR,
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
    # runs = list(itertools.product(PATHWAYS, SENSITIVITIES))
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

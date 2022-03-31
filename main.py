from mppshared.utility.utils import get_logger
from mppshared.config import LOG_LEVEL, PATHWAYS, SENSITIVITIES, SECTOR, RUN_PARALLEL, run_config
from mppshared.models.simulate import simulate_pathway
from mppshared.solver.ranking import make_rankings

import numpy as np
import itertools
import multiprocessing as mp


logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)

np.random.seed(100)

funcs = {
    # "MAKE_RANKINGS": make_rankings,
    "SIMULATE_PATHWAY": simulate_pathway,
    # "CALCULATE_OUTPUTS": calculate_outputs,
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
            )


def run_model_sequential(runs):
    """Run model sequentially, slower but better for debugging"""
    for pathway, sensitivity in runs:
        _run_model(pathway=pathway, sensitivity=sensitivity)


def run_model_parallel(runs):
    """Run model in parallel, faster but harder to debug"""
    n_cores = mp.cpu_count()
    logger.info(f"{n_cores} cores detected")
    pool = mp.Pool(processes=n_cores)
    logger.info(f"Running model for scenario/sensitivity {runs}")
    for pathway, sensitivity in runs:
        pool.apply_async(_run_model, args=(pathway, sensitivity))
    pool.close()
    pool.join()


def main():
    runs = list(itertools.product(PATHWAYS, SENSITIVITIES))
    if RUN_PARALLEL:
        run_model_parallel(runs)
    else:
        run_model_sequential(runs)


if __name__ == "__main__":
    main()


""" Logic for technology transitions of type greenfield (add new Asset to AssetStack."""

from copy import deepcopy
from importlib.resources import path
from multiprocessing.sharedctypes import Value
from operator import methodcaller

import numpy as np
import pandas as pd

from mppshared.agent_logic.agent_logic_functions import (
    remove_all_transitions_with_destination_technology,
    remove_transition,
    select_best_transition,
    apply_regional_technology_ban,
)
from mppshared.config import (
    ASSUMED_ANNUAL_PRODUCTION_CAPACITY_MT,
    BUILD_CURRENT_PROJECT_PIPELINE,
    LOG_LEVEL,
    MAP_LOW_COST_POWER_REGIONS,
    MAXIMUM_GLOBAL_DEMAND_SHARE_ONE_REGION,
    MODEL_SCOPE,
    REGIONAL_TECHNOLOGY_BAN,
    REGIONS,
)
from mppshared.models.asset import (
    Asset,
    AssetStack,
    make_new_asset,
    make_new_asset_project_pipeline,
)
from mppshared.models.constraints import (
    check_constraints,
    get_regional_production_constraint_table,
)
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.solver.implicit_forcing import apply_regional_technology_ban
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)

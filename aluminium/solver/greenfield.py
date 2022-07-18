""" Logic for technology transitions of type greenfield (add new Asset to AssetStack."""
import sys
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
)
from mppshared.config import (
    ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
    LOG_LEVEL,
    MAP_LOW_COST_POWER_REGIONS,
    MODEL_SCOPE,
)
from mppshared.models.asset import Asset, AssetStack, make_new_asset
from mppshared.models.constraints import (
    check_constraints,
    get_regional_production_constraint_table,
    hydro_constraints,
)
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)

""" Additional functions required for the agent logic, e.g. demand balances. """

import pandas as pd
import numpy as np
from scipy.optimize import linprog

from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.models.asset import AssetStack
from mppshared.config import ASSUMED_ANNUAL_PRODUCTION_CAPACITY


def get_demand_balance(
    pathway: SimulationPathway,
    current_stack: AssetStack,
    product: str,
    year: int,
    region: str,
) -> float:
    """Calculate balance between production of the AssetStack and demand in the given region in a given year

    Args:
        pathway: contains demand data
        current_stack: contains production assets
        product: product for demand balance
        year: year for demand balance
        region: region for demand balance

    Returns:
        float: demand - production
    """
    demand = pathway.get_demand(product, year, region)
    production = current_stack.get_yearly_volume(product)
    balance = demand - production
    return balance


def select_best_transition(df_rank: pd.DataFrame) -> dict:
    """Based on the ranking, select the best transition

    Args:
        df_rank: contains column "rank" with ranking for each technology transition (minimum rank = optimal technology transition)

    Returns:
        The highest ranking technology transition

    """
    # Best transition has minimum rank
    return (
        df_rank[df_rank["rank"] == df_rank["rank"].min()]
        .sample(n=1)
        .to_dict(orient="records")
    )[0]


def optimize_cuf(
    cuf_assets: list, surplus: float, upper_bound=0.95, lower_bound=0.5
) -> list:
    """

    Args:
        cuf_assets:
        surplus:
        upper_bound:
        lower_bound:

    Returns:
        an array with new CUF to cover the demand

    """
    c = [-1] * len(cuf_assets)
    A_ub = [1] * len(cuf_assets)
    b_ub = surplus / ASSUMED_ANNUAL_PRODUCTION_CAPACITY
    bounds = [(lower_bound, upper_bound)] * len(cuf_assets)

    model_linear = linprog(c=c, A_ub=A_ub, b_ub=b_ub, bounds=bounds)

    return [round(cuf, 2) for cuf in model_linear.x.to_list()]

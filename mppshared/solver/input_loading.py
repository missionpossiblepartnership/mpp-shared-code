""" Import and validate the input tables."""

from mppshared.config import SOLVER_INPUT_DATA_PATH, SOLVER_INPUT_TABLES

import pandas as pd


def load_and_validate_inputs(sector: str) -> dict:
    """Load and validate the sector-specific input tables.

    Args:
        sector (str): sector name

    Returns:
        dict: dictionary with the input DataFrames
    """
    input_dfs = dict.fromkeys(SOLVER_INPUT_TABLES)

    for input_table in input_dfs.keys():
        path = f"{SOLVER_INPUT_DATA_PATH}/{sector}/{input_table}.csv"

        # Demand input table has one header row
        if input_table == "demand":
            df = pd.read_csv(path)
        else:
            df = pd.read_csv(path, header=[0, 1])
        input_dfs[input_table] = df

    # TODO: implement input validation

    return input_dfs

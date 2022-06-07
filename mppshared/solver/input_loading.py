""" Import and validate the input tables."""

import pandas as pd

from mppshared.config import SOLVER_INPUT_DATA_PATH, SOLVER_INPUT_TABLES


def load_and_validate_inputs(sector: str) -> dict:
    """Load and validate the sector-specific input tables.

    Args:
        sector (str): sector name

    Returns:
        dict: dictionary with the input DataFrames
    """

    # TODO: use class IntermediateDataImporter for handling data import
    input_dfs = dict.fromkeys(SOLVER_INPUT_TABLES)

    for input_table in input_dfs.keys():
        path = f"{SOLVER_INPUT_DATA_PATH}/{sector}/{input_table}.csv"
        df = pd.read_csv(path)
        #! Remove for production
        df = filter_df_for_development(df)
        input_dfs[input_table] = df

    # TODO: implement input validation

    return input_dfs


#! For development only
def filter_df_for_development(df: pd.DataFrame) -> pd.DataFrame:

    df = df.loc[df["product"] == "Ammonia"]
    if "technology_destination" in df.columns:
        df = df.loc[
            df["technology_destination"].isin(
                [
                    "Natural Gas SMR + ammonia synthesis",  # Initial
                    "Natural Gas SMR + CCS + ammonia synthesis",  # End-state
                    "Electrolyser - grid PPA + ammonia synthesis",  # End-state
                    "Decommissioned",  # For decommission switch
                    "Electrolyser + SMR + ammonia synthesis",  # Transition
                ]
            )
        ]
    if "technology_origin" in df.columns:
        df = df.loc[
            df["technology_origin"].isin(
                [
                    "Natural Gas SMR + ammonia synthesis",  # Initial
                    "Coal Gasification + ammonia synthesis",  # Initial
                    "Electrolyser + SMR + ammonia synthesis",  # Transition
                    "New-build",  # For greenfield switch
                    "Electrolyser - grid PPA + ammonia synthesis",  # "End-state"
                ]
            )
        ]
    return df

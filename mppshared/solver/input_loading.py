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
        df = pd.read_csv(path)
        #! Remove for production
        df = filter_df_for_development(df)
        input_dfs[input_table] = df

    # TODO: implement input validation

    return input_dfs


#! For development only
def filter_df_for_development(df: pd.DataFrame) -> pd.DataFrame:

    df = df.loc[df["product"] == "Ammonia"]
    if "switch_type" in df.columns:
        df = df.loc[df["switch_type"] == "Greenfield"]
    if "technology_destination" in df.columns:
        df = df.loc[
            df["technology_destination"].isin(
                [
                    "Natural Gas SMR + ammonia synthesis",
                    "Natural Gas SMR + CCS + ammonia synthesis",
                    "Electrolyser - grid PPA + ammonia synthesis",
                ]
            )
        ]
    return df

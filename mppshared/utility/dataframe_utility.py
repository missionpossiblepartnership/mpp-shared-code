"""Utility script to manipulate DataFrames"""

from typing import List

import numpy as np
import pandas as pd
from mppshared.config import LOG_LEVEL
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def add_column_header_suffix(df: pd.DataFrame, cols: list, suffix: str) -> pd.DataFrame:
    # sourcery skip: identity-comprehension
    """Add a suffix with an underscore to each column header of the DataFrame that is in the cols list.

    Args:
        df (pd.DataFrame): contains column headers to be changed
        cols (list): list of column headers to be changed
        suffix (str): suffix to be appended to the selected column headers

    Returns:
        pd.DataFrame: selected column headers are appended with _suffix
    """
    suffix_cols = [f"{col_header}_{suffix}" for col_header in cols]
    rename_dict = {k: v for k, v in zip(cols, suffix_cols)}
    df = df.rename(columns=rename_dict)

    return df


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return df with columns flattened from multi-index to normal index for columns
    Args:
        df: input df

    Returns: the df with flattened column index

    """
    df.columns = ["_".join(col).strip() for col in df.columns.values]
    return df


def get_emission_columns(ghgs: list, scopes: list) -> list:
    """Get list of emissions columns for specified GHGs and emission scopes"""
    return [f"{ghg}_{scope}" for scope in scopes for ghg in ghgs]


def explode_rows_for_all_products(df: pd.DataFrame, products: list) -> pd.DataFrame:
    """Explode rows with entry "All products" in column "product" to all products.

    Args:
        df (pd.DataFrame): contains column "product"
        products:

    Returns:
        pd.DataFrame: contains column "product" where entries are only in PRODUCTS
    """

    df["product"] = df["product"].astype(object)
    df = df.reset_index(drop=True)

    for i in df.loc[df["product"] == "All products"].index:
        df.at[i, "product"] = products

    df = df.explode("product")

    return df


def set_datatypes(df: pd.DataFrame, datatypes_per_column: dict) -> pd.DataFrame:
    """

    Args:
        df ():
        datatypes_per_column (): dict with df's column names as keys and their datatypes as values

    Returns:

    """
    # get relevant columns and their types
    datatypes = {k: v for k, v in datatypes_per_column.items() if k in list(df)}
    # set datatypes
    df = df.astype(
        dtype=datatypes,
        errors="ignore",
    )

    return df


def df_dict_to_df(df_dict: dict) -> pd.DataFrame:
    """
    Converts a dict of dataframes with the same index to one dataframe with a distinct value column for all dataframes
        in the dict

    Args:
        df_dict (): dict of dataframes with the same indices and one "value" column

    Returns:
        df (pd.DataFrame): df with all the dfs in df_dict as columns
    """

    df_list = []
    for key in df_dict.keys():
        # make sure that df only includes one value column
        assert (
            df_dict[key].shape[1] == 1
        ), f"df_dict{key} has more than one value column. Cannot convert to dataframe."
        # convert
        df_append = df_dict[key].rename(columns={"value": f"value_{key}"})
        df_list.append(df_append)

    df = pd.concat(objs=df_list, axis=1)

    return df


def round_significant_numbers(x, p: int):
    """
    Rounds ints/floats or arrays to p significant numbers

    Args:
        x ():
        p ():

    Returns:

    """
    x = np.asarray(x)
    x_positive = np.where(np.isfinite(x) & (x != 0), np.abs(x), 10 ** (p - 1))
    mags = 10 ** (p - 1 - np.floor(np.log10(x_positive)))
    x = np.round(x * mags) / mags
    return x

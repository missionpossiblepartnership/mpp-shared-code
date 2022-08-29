"""Utility module for functions used throughout the module"""

import pandas as pd

from config_ammonia import (
    CALCULATE_FOLDER,
    COMMON_INDEX,
    CORE_DATA_PATH,
    MAP_COLUMN_NAMES,
    COST_DF_INDEX,
    PRODUCTS,
)


def write_intermediate_data_to_csv(
    folder: str, filename: str, df: pd.DataFrame, flag_index=False
):
    """Write DataFrame to .csv in INTERMEDIATE_DATA_PATH/folder.

    Args:
        folder (str): name of the folder for saving (either of import, calculate_variables, TBD)
        filename (str): name of the DataFrame for saving
        df (pd.DataFrame): DataFrame to be saved
    """
    full_path = f"{folder}/{filename}.csv"
    df.to_csv(full_path, index=flag_index)


def load_intermediate_data_from_csv(folder: str, filename: str) -> pd.DataFrame:
    """Load preformatted data from .csv file into DataFrame.

    Args:
        filename (str): Name of the .csv file
        folder (str): Name of the folder in mppchemicals > data > intermediate_data
    Returns:
        pd.DataFrame: DataFrame containing the data in the .csv file
    """

    full_path = f"{folder}/{filename}.csv"
    return pd.read_csv(full_path)


def load_cost_data_from_csv(sensitivity: str) -> pd.DataFrame:
    """Load cost DataFrame with special MultiIndex format from .csv into DataFrame."""

    folder = CALCULATE_FOLDER
    filename = "tco"
    full_path = f"{CORE_DATA_PATH}/{sensitivity}/{folder}/{filename}.csv"

    # Read multi-index
    header = [0, 1]
    index_cols = [0, 1, 2, 3, 4, 5]

    df_cost = pd.read_csv(full_path, header=header, index_col=index_cols)
    df_cost.index.set_names(COST_DF_INDEX, inplace=True)
    return df_cost


def unit_column_suffix(df: pd.DataFrame, suffix: str) -> pd.DataFrame:
    """Append suffix to unit column to be conserved upon DataFrame merge"""

    return df.rename(mapper={"unit": f"unit_{suffix}"}, axis=1)


def technology_column_suffix(df: pd.DataFrame, suffix: str) -> pd.DataFrame:
    """Append suffix to technology column for creation of technology switching DataFrame"""

    return df.rename(mapper={"technology": f"technology_{suffix}"}, axis=1)


def rename_columns_to_standard_names(df: pd.DataFrame):
    """Rename columns according to the MAP_COLUMN_NAMES dictionary in config.py"""
    return df.rename(columns=MAP_COLUMN_NAMES)


def set_common_multi_index(df: pd.DataFrame):
    """Set MultiIndex with a columns from COMMON_INDEX that are in the DataFrame."""
    index_cols = [col for col in COMMON_INDEX if col in df.columns]
    return df.set_index(index_cols, drop=True)


def explode_rows_for_all_products(df: pd.DataFrame) -> pd.DataFrame:
    """Explode rows with entry "All products" in column "product" to all products.

    Args:
        df (pd.DataFrame): contains column "product"

    Returns:
        pd.DataFrame: contains column "product" where entries are only in PRODUCTS
    """

    df["product"] = df["product"].astype(object)
    df = df.reset_index(drop=True)

    # TODO: improve with a more elegant solution
    for i in df.loc[df["product"] == "All products"].index:
        df.at[i, "product"] = PRODUCTS

    df = df.explode("product")

    return df

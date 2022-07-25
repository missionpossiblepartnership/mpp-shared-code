"""Utility script to manipulate DataFrames"""

from typing import List

import numpy as np
import pandas as pd

from mppshared.config import PKL_DATA_INTERMEDIATE, PRODUCTS, SECTOR
from mppshared.utility.file_handling_utility import read_pickle_folder
from mppshared.utility.location_utility import get_region_from_country_code
from mppshared.utility.log_utility import get_logger

logger = get_logger("DataFrame Utility")


def create_line_through_points(
    year_value_dict: dict, line_shape: str = "straight"
) -> pd.DataFrame:
    """A function that returns a dataframe based on a few data points.

    Args:
        year_value_dict (dict): A dictionary with year, value pairings, put as many as you want, minimum two.
        line_shape (str, optional): The shape of the fitting betwene points. Defaults to 'straight'.

    Returns:
        pd.DataFrame: A dataframe with an index as year and one value column.
    """
    logger.info(f"Creating line through points {year_value_dict}")
    # Creates a pairing for all elements based on location
    def create_value_pairings(iterable: list) -> list:
        value_pairings = []
        it = iter(iterable)
        for x in it:
            try:
                value_pairings.append((x, next(it)))
            except StopIteration:
                value_pairings.append((iterable[-2], iterable[-1]))
        return value_pairings

    # Create pairings for years and values
    years = [int(year) for year in year_value_dict]
    values = list(year_value_dict.values())
    year_pairs = create_value_pairings(years)
    value_pairs = create_value_pairings(values)

    # Create dataframes for every pairing
    df_list = []
    for year_pair, value_pair in zip(year_pairs, value_pairs):
        year_range = range(year_pair[0], year_pair[1] + 1)
        start_value = value_pair[0]
        end_value = value_pair[1] + 1
        if line_shape == "straight":
            values = np.linspace(start=start_value, stop=end_value, num=len(year_range))
        df = pd.DataFrame(data={"year": year_range, "values": values})
        df_list.append(df)
    # Combine pair DataFrames into one DataFrame
    combined_df = pd.concat(df_list)
    return combined_df.set_index("year")


def move_cols_to_front(df: pd.DataFrame, cols_at_front: List[str]) -> list:
    """Function that changes the order of columns based on a list of columns you
    want at the front of a DataFrame.

    Args:
        df (pd.DataFrame): A DataFrame containing the column names you want to reorder.
        cols_at_front (list): The columns you would like at the front of the DataFrame

    Returns:
        list: A list of reordered column names.
    """
    non_abatement_columns = list(set(df.columns).difference(set(cols_at_front)))
    return cols_at_front + non_abatement_columns


def expand_dataset_years(df: pd.DataFrame, year_pairs: List[tuple]) -> pd.DataFrame:
    """Expands the number of years contained in a DataFrame where the current timeseries is in intervals.

    Args:
        df (pd.DataFrame): The DataFrame timeseries you want to expand.
        year_pairs (list): A list of year pairings tuples that constitutes the lower and upper boundaries of each interval in the original data.

    Returns:
        pd.DataFrame: The expanded DataFrame Timeseries.
    """
    df_c = df.copy()
    for year_pair in year_pairs:
        start_year, end_year = year_pair
        year_range = range(start_year + 1, end_year)
        for ticker, year in enumerate(year_range, start=1):
            df_c[year] = df_c[year - 1] + (
                (df_c[end_year] / len(year_range)) * (ticker / len(year_range))
            )
    return df_c


def column_sorter(
    df: pd.DataFrame, col_to_sort: List[str], col_order: List[str]
) -> pd.DataFrame:
    """Sorts a DataFrames values according to a specified column and the column value order.

    Args:
        df (pd.DataFrame): The DataFrame you would like to sort.
        col_to_sort (str): A string containing the name of the column you would like to sort.
        col_order (list): A list containing the order of values (descending).

    Returns:
        pd.DataFrame: A DataFrame with values sorted according to col_to_sort, ordered by 'col_order'
    """

    def sorter(column):
        correspondence = {val: order for order, val in enumerate(col_order)}
        return column.map(correspondence)

    return df.copy().sort_values(by=col_to_sort, key=sorter)


def add_scenarios(
    df: pd.DataFrame, scenario_dict: dict, single_line: bool = False
) -> pd.DataFrame:
    """Adds scenario metadata column(s) with metadata to each row in a DataFrame.

    Args:
        df (pd.DataFrame): The DataFrame you want to modify.
        scenario_dict (dict): A metadata dictionary with scenario information.
        single_line (bool, optional): A boolean flag to flatten the scenario dictionary into one line or one column for each dictionart item. Defaults to False.

    Returns:
        pd.DataFrame: A DataFrame with additional scenario metadata column(s).
    """
    df_c = df.copy()
    if single_line:
        df_c["scenarios"] = str(scenario_dict)
    else:
        for key in scenario_dict:
            df_c[f"scenario_{key}"] = scenario_dict[key]
    return df_c


def add_regions(
    df: pd.DataFrame, country_ref_dict: dict, country_ref_col: str, region_schema: str
) -> pd.DataFrame:
    """Adds regional metadata column(s) to each row in a DataFrame.

    Args:
        df (pd.DataFrame): The DataFrame you want to modify.
        country_ref_dict (dict): A dictionary containing the mapping of country codes to regions.
        country_ref_col (str): The column containing the country codes you want to map.
        region_schema (str): The name of the schema you want to map.

    Returns:
        pd.DataFrame: A DataFrame with additional regional metadata column(s).
    """
    df_c = df.copy()
    df_c[f"region_{region_schema}"] = df_c[country_ref_col].apply(
        lambda country: get_region_from_country_code(
            country, region_schema, country_ref_dict
        )
    )
    return df_c


def add_results_metadata(
    df: pd.DataFrame,
    scenario_dict: dict,
    include_regions: bool = True,
    regions_to_map: list = None,
    single_line: bool = False,
) -> pd.DataFrame:
    """Adds scenario and (optionally) regional metadata column(s) to each row in a DataFrame.

    Args:
        df (pd.DataFrame): The DataFrame you want to modify.
        scenario_dict (dict): A metadata dictionary with scenario information.
        include_regions (bool, optional): Boolean flag that optionally adds regional metadata information. Defaults to True.
        single_line (bool, optional): A boolean flag to flatten the scenario dictionary into one line or one column for each dictionart item. Defaults to False.

    Returns:
        pd.DataFrame: The name of the schema you want to map.
    """
    country_reference_dict = read_pickle_folder(
        PKL_DATA_INTERMEDIATE, "country_reference_dict", "dict"
    )
    df_c = df.copy()
    df_c = add_scenarios(df_c, scenario_dict, single_line)
    if include_regions:
        for schema in regions_to_map:
            df_c = add_regions(df_c, country_reference_dict, "country_code", schema)
    return df_c


def return_furnace_group(furnace_dict: dict, tech: str) -> str:
    """Returns the Furnace Group of a technology if the technology is in a furnace group list of technologies.

    Args:
        furnace_dict (dict): A mapping of each technology to a furnace group.
        tech (str): The technology you would like to map.

    Returns:
        str: The Furnace Group of the technology
    """
    for key, value in furnace_dict.items():
        if tech in furnace_dict[key]:
            return value


def melt_and_index(
    df: pd.DataFrame, id_vars: List[str], var_name: str, index: List[str]
) -> pd.DataFrame:

    """Transform a DataFrame by making it tabular and creating a multiindex.

    Args:
        df (pd.DataFrame): The Data you would like to Transform.
        id_vars (list): A list of column names you would not like to melt.
        var_name (list): The name of the variable you are melting.
        index (list): The column(s) you would like to use a MultiIndex.

    Returns:
        pd.DataFrame: The melted / tabular Dataframe.
    """
    df_c = df.copy()
    df_c = pd.melt(frame=df_c, id_vars=id_vars, var_name=var_name)
    return df_c.set_index(index)


def expand_melt_and_sort_years(
    df: pd.DataFrame, year_pairs: List[tuple]
) -> pd.DataFrame:
    """Expands a DataFrame's years according to the year pairings passed. Also melts the DataFrame based on all columns that aren't years.
    Finally Sorts the DataFrame in ascending order of the years.

    Args:
        df (pd.DataFrame): The DataFrame you want to modify.
        year_pairs (list): A list of year pairings tuples that constitutes the lower and upper boundaries of each interval in the original data.

    Returns:
        pd.DataFrame: The modified DataFrame.
    """
    df_c = df.copy()
    df_c = expand_dataset_years(df_c, year_pairs)
    years = [year_col for year_col in df_c.columns if isinstance(year_col, int)]
    df_c = df_c.melt(id_vars=set(df_c.columns).difference(set(years)), var_name="year")
    return df_c.sort_values(by=["year"], axis=0)


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


def get_grouping_columns_for_npv_calculation(sector: str) -> list:
    """Return the grouping columns for calculating NPV (sector-specific)

    Args:
        sector (str): currently only "chemicals"

    Returns:
        list: headers of grouping columns
    """
    grouping_cols = {
        "chemicals": [
            "product",
            "technology_origin",
            "region",
            "switch_type",
            "technology_destination",
        ]
    }
    return grouping_cols[sector]


def convert_df_to_regional(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converts a dataframe that has both regional and global values to one that just has regional values.

    Args:
        df: Dataframe with mixed values

    Returns:
        Dataframe with only regional values
    """

    # Separate world and regional df
    world_idx = df.region == "World"
    df_world = df[world_idx].copy()
    df_regional_1 = df[~world_idx]

    # Regionalize the world df
    df_world.drop(columns="region", inplace=True)
    df_regions = pd.DataFrame({"region": list(REGIONS_OTHER)})
    df_regional_2 = df_world.merge(df_regions, how="cross")

    # Return the region df
    return pd.concat([df_regional_1, df_regional_2])


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return df with columns flattened from multi-index to normal index for columns
    Args:
        df: input df

    Returns: the df with flattened column index

    """
    df.columns = ["_".join(col).strip() for col in df.columns.values]
    return df


def make_multi_df(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """
    Make a df multi-column-indexed

    Args:
        df: Input df
        name: Name of the multi-index top level

    Returns:
        multi-indexed df
    """
    return pd.concat({name: df}, axis=1)


def get_emission_columns(ghgs: list, scopes: list) -> list:
    """Get list of emissions columns for specified GHGs and emission scopes"""
    return [f"{ghg}_{scope}" for scope in scopes for ghg in ghgs]


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
        df.at[i, "product"] = PRODUCTS[SECTOR]

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
        df_dict (): dict of dataframes with the same index and one "value" column

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

"""Utility library for functions used throughout the module"""

import pandas as pd

from mppshared.utility.log_utility import get_logger

logger = get_logger("Utils")


def get_region_rank_filter(region: str, map_low_cost_power_regions) -> list:
    """Return list of (sub)regions if the sector has low-cost power regions mapped to the overall regions"""
    if region in map_low_cost_power_regions.keys():
        return [region, map_low_cost_power_regions[region]]
    return [region]


def get_unique_list_values(nonunique_list: list) -> list:
    """function to get unique values from list"""

    # convert to set and back to list (sets only have unique values)
    unique_list = list(set(nonunique_list))
    return unique_list


def extend_to_all_technologies(
    df: pd.DataFrame, list_technologies: list, technology_column_name: str = "technology_destination"
) -> pd.DataFrame:
    """
    Adds all technologies to a dataframe without "technology_destination" column

    Args:
        df (): indexed df without "technology_destination" column
        list_technologies (): list of all technologies
        technology_column_name (): name of the technology column (defaults to "technology_destination")

    Returns:

    """

    idx = list(df.index.names) + [technology_column_name]

    df_list = []
    for tech in list_technologies:
        df_append = df.copy()
        df_append[technology_column_name] = tech
        df_list.append(df_append)

    df = pd.concat(df_list).reset_index().set_index(idx).sort_index()

    return df


def filter_input_metrics(df: pd.DataFrame, list_metrics: list) -> pd.DataFrame:
    """
    Takes a dataframe with a "metric" column as well as a list of strings with the required metrics as inputs and
        outputs a dataframe that only includes the required metrics.

    Args:
        df (): unindexed df with "metric" column
        list_metrics ():

    Returns:
        df (): Filtered with only the those metrics in list_metrics
    """
    df_list = []
    df = df.copy()
    for metric in list_metrics:
        df_append = df.loc[df["metric"] == metric, :]
        df_list.append(df_append)

    df = pd.concat(df_list).reset_index(drop=True)

    return df

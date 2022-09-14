"""Utility library for functions used throughout the module"""
import itertools
import sys
from collections.abc import Iterable
from datetime import datetime
from typing import Iterable as it
from typing import Union

import pandas as pd
from currency_converter import CurrencyConverter

from mppshared.utility.log_utility import get_logger

logger = get_logger("Utils")


def get_today_time(fmt: str = "%y%m%d_%H%M%S") -> str:
    """Returns a formatted string of todays date.

    Args:
        The format you would like the datetime object to take.

    Returns:
        str: A string with today's date.
    """
    return datetime.today().strftime(fmt)


def create_list_permutations(list1: list, list2: list) -> list:
    """Create a combined list of every permutation of objects in two lists.

    Args:
        list1 (list): The first list you want to use in the permuation.
        list2 (list): The second list you want to use in the permutation.

    Returns:
        list: The combined list of permutations between two lists.
    """
    comb = [
        list(zip(each_permutation, list2))
        for each_permutation in itertools.permutations(list1, len(list2))
    ]
    return list(itertools.chain(*comb))


def stdout_query(question: str, default: str, options: str) -> str:
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
            It must be "yes" (the default), "no" or None (meaning
            an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    if default not in options:
        raise ValueError(f"invalid default answer {default}. Not in options: {options}")

    while True:
        sys.stdout.write(f"{question} {default}")
        choice = input().lower()
        if choice == "":
            return default
        elif choice in options:
            return choice
        else:
            sys.stdout.write(f"Please respond with a choice from {options}.\n")


def get_currency_rate(base: str, target: str) -> str:
    """Gets a currency rate exchange between two currencies using the CurrencyConverter library.

    Args:
        base (str): [description]
        target (str): [description]

    Returns:
        str: [description]
    """
    logger.info(f"Getting currency exchange rate for {base}")

    if (len(base) == 3) & (len(target) == 3):
        try:
            curr = CurrencyConverter()
            return curr.convert(1, base.upper(), target.upper())
        except:
            raise ValueError(
                f"You entered an incorrect currency, either {base} or {target}"
            )
    else:
        raise ValueError(
            f"You entered an incorrect currency, either {base} or {target}"
        )


def enumerate_iterable(iterable: it) -> dict:
    """Enumerates an iterable as dictionary with the iterable value as the key and the order number as the value.

    Args:
        iterable (Iterable): The iterable you want to enumerate

    Returns:
        dict: A dictionary with the iterable value as the key and the order number as the value.
    """
    return dict(zip(iterable, range(len([i for i in iterable]))))


def cast_to_float(val: Union[float, int, list[float|int]]) -> float:
    """Casts a numerical object to a float if not a float already.

    Args:
        val Union[float, int, Iterable]): The numerical value you want to be a float. Can be an iterable containing a numberical value(s), that will be summated as a float.

    Returns:
        float: The float value.
    """
    if isinstance(val, float):
        return val
    elif isinstance(val, list):
        return float(sum(val))


def first(series: pd.Series):
    """Return first element in a series"""
    return series.values[0]


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
    df: pd.DataFrame, list_technologies: list
) -> pd.DataFrame:
    """
    Adds all technologies to a dataframe without "technology_destination" column

    Args:
        df (): indexed df without "technology_destination" column
        list_technologies (): list of all technologies

    Returns:

    """

    idx = list(df.index.names) + ["technology_destination"]

    df_list = []
    for tech in list_technologies:
        df_append = df.copy()
        df_append["technology_destination"] = tech
        df_list.append(df_append)

    df = pd.concat(df_list).reset_index().set_index(idx).sort_index()

    return df

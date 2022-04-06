""" Process outputs to standardised output table."""
import pandas as pd

from mppshared.config import (END_YEAR, LOG_LEVEL, PRODUCTS, SECTOR,
                              SECTORAL_CARBON_BUDGETS, START_YEAR)
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def create_table_sequence_technology():
    pass


def create_table_all_data_year(year):

    pass


def create_table_all_data():
    for year in range(START_YEAR, END_YEAR + 1):
        create_table_all_data_year(year)
    # table has to be structured as follows:
    # Columns:
    # - sector
    # - product
    # - technology
    # - parameter
    # - unit
    # - value
    # - 2020
    # - nth year
    #  To fill it can be done with a long table with a year column and then create a pivot table with the years as index
    pass


def create_outputs_dashboard():
    pass

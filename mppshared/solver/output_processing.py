""" Process outputs to standardised output table."""
import pandas as pd

from mppshared.config import (END_YEAR, LOG_LEVEL, PRODUCTS, SECTOR,
                              SECTORAL_CARBON_BUDGETS, START_YEAR)
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def create_table_sequence_technology():
    pass


def create_table_all_data_year(year, importer):
    df_stack = importer.get_asset_stack(year)
    df_stack["asset"] = 1
    # Group by product, region and technology and count the number of assets, get  coulm with the count
    df_stack_plants = (
        df_stack.groupby(["product", "region", "technology"]).count().reset_index()
    )
    # Rename the column to count
    df_stack_plants.rename(columns={"asset": "value"}, inplace=True)
    df_stack_plants["parameter"] = "Number of plants"
    df_stack_plants["unit"] = "plant"
    return df_stack_plants


def calculate_outputs(pathway, sensitivity, sector):
    print("Hello world")
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

    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS[sector],
    )
    data = []
    for year in range(START_YEAR, END_YEAR + 1):
        logger.info(f"Processing year {year}")
        yearly = create_table_all_data_year(year, importer)
        yearly["year"] = year
        data.append(yearly)
    df = pd.concat(data)
    df["sector"] = sector
    # Pivot the dataframe to have the years as columns
    df_pivot = df.pivot_table(
        index=["sector", "product", "region", "technology", "parameter", "unit"],
        columns="year",
        values="value",
    )
    df_pivot.reset_index(inplace=True)
    df_pivot.fillna(0, inplace=True)
    importer.export_data(df_pivot, "export_all_data.csv", "outputs")


def create_outputs_dashboard():
    pass

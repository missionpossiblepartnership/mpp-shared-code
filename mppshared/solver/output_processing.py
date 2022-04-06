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
    # Calculate the number of assets for each region, product and technology
    df_stack["asset"] = 1
    df_stack_total_assets = (
        df_stack.groupby(["product", "region", "technology"]).count().reset_index()
    )
    df_stack_total_assets.rename(columns={"asset": "value"}, inplace=True)
    df_stack_total_assets["parameter"] = "Number of plants"
    df_stack_total_assets["unit"] = "plant"
    df_stack_total_assets["parameter_group"] = "Production"
    # Calculate the production volume per region, product and technology
    df_stack_production_capacity = (
        df_stack.groupby(["product", "region", "technology"]).sum().reset_index()
    )
    df_stack_production_capacity.rename(
        columns={"annual_production_volume": "value"}, inplace=True
    )
    df_stack_production_capacity["parameter"] = "Annual production volume"
    df_stack_production_capacity["unit"] = "Mt"
    df_stack_production_capacity["parameter_group"] = "Production"

    # Calculate the carbon emissions per region, product and technology
    df_emissions = importer.get_emissions()
    df_emissions = df_emissions[df_emissions["year"] == year]
    df_assets_emissions = df_stack.merge(
        df_emissions, on=["product", "region", "technology"]
    )
    df_stack_emissions = (
        df_assets_emissions.groupby(["product", "region", "technology"])
        .sum()
        .reset_index()
    )
    df_stack_emissions_emitted = df_stack_emissions.melt(
        id_vars=["product", "region", "technology"],
        value_vars=[
            "co2_scope1",
            "co2_scope2",
            "co2_scope3_upstream",
            "co2_scope3_downstream",
        ],
        var_name="parameter",
        value_name="value",
    )
    df_stack_emissions_emitted["unit"] = "t"
    df_stack_emissions_emitted["parameter_group"] = "Emissions"
    df_stack_capture_emissions = df_stack_emissions.melt(
        id_vars=["product", "region", "technology"],
        value_vars=[
            "co2_scope1_captured",
        ],
        var_name="parameter",
        value_name="value",
    )
    df_stack_capture_emissions["unit"] = "t"
    df_stack_capture_emissions["parameter_group"] = "Emissions"

    return pd.concat(
        [
            df_stack_total_assets,
            df_stack_production_capacity,
            df_stack_emissions_emitted,
            df_stack_capture_emissions,
        ]
    )


def calculate_outputs(pathway, sensitivity, sector):
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
        index=[
            "sector",
            "product",
            "region",
            "technology",
            "parameter_group",
            "parameter",
            "unit",
        ],
        columns="year",
        values="value",
    )
    df_pivot.reset_index(inplace=True)
    df_pivot.fillna(0, inplace=True)
    importer.export_data(df_pivot, "export_all_data.csv", "outputs")


def create_outputs_dashboard():
    pass

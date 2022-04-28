""" Process outputs to standardised output table."""
import pandas as pd

from mppshared.config import (
    END_YEAR,
    LOG_LEVEL,
    PRODUCTS,
    SECTOR,
    SECTORAL_CARBON_BUDGETS,
    START_YEAR,
)
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def create_table_sequence_technology():
    pass


def _calculate_number_of_assets(df_stack):
    logger.info("-- Calculating number of assets")
    # Calculate the number of assets for each region, product and technology
    df_stack["asset"] = 1
    df_stack_total_assets = (
        df_stack.groupby(["product", "region", "technology"]).count().reset_index()
    )
    df_stack_total_assets.rename(columns={"asset": "value"}, inplace=True)
    df_stack_total_assets["parameter"] = "Number of plants"
    df_stack_total_assets["unit"] = "plant"
    df_stack_total_assets["parameter_group"] = "Production"
    return df_stack_total_assets


def _calculate_production_volume(df_stack):
    logger.info("-- Calculating production volume")
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
    return df_stack_production_capacity


def _calculate_emissions(df_stack, df_emissions):
    logger.info("-- Calculating emissions")
    # Calculate the carbon emissions per region, product and technology
    df_assets_emissions = df_stack.merge(
        df_emissions, on=["product", "region", "technology"]
    )
    df_assets_emissions["co2_scope1"] = (
        df_assets_emissions["co2_scope1"]
        * df_assets_emissions["annual_production_volume"]
    )
    df_assets_emissions["co2_scope2"] = (
        df_assets_emissions["co2_scope2"]
        * df_assets_emissions["annual_production_volume"]
    )
    df_assets_emissions["co2_scope3_upstream"] = (
        df_assets_emissions["co2_scope3_upstream"]
        * df_assets_emissions["annual_production_volume"]
    )
    df_assets_emissions["co2_scope3_downstream"] = (
        df_assets_emissions["co2_scope3_downstream"]
        * df_assets_emissions["annual_production_volume"]
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
    return df_stack_emissions_emitted, df_stack_capture_emissions


def _calculate_lcox(df_stack, df_transitions):
    logger.info("-- Calculating LCOX")
    df_assets_lcox = df_stack.merge(
        df_transitions,
        left_on=["product", "region", "technology"],
        right_on=["product", "region", "technology_destination"],
    )
    df_stack_lcox = (
        df_assets_lcox.groupby(["product", "region", "technology"]).sum().reset_index()
    )
    df_stack_lcox.rename(columns={"lcox": "value"}, inplace=True)
    df_stack_lcox["parameter"] = "lcox"
    df_stack_lcox["unit"] = "USD/t"
    df_stack_lcox["parameter_group"] = "finance"
    return df_stack_lcox


def _calculate_output_from_input(df_stack, df_inputs_outputs, variable, year):
    logger.info(f"-- Calculating {variable}")
    df_variable = df_inputs_outputs.loc[
        (df_inputs_outputs["parameter"] == variable)
        & (df_inputs_outputs["year"] == year)
    ].copy()
    df_stack = df_stack.merge(df_variable, on=["product", "region", "technology"])
    df_stack["value"] = df_stack["value"] * df_stack["annual_production_volume"]
    df_stack_variable = (
        df_stack.groupby(["product", "region", "technology"]).sum().reset_index()
    )
    df_stack_variable["parameter_group"] = "finance"
    df_stack_variable["unit"] = df_variable["unit"].iloc[0]
    return df_stack_variable


def create_table_all_data_year(year, importer):
    df_stack = importer.get_asset_stack(year)
    df_stack_total_assets = _calculate_number_of_assets(df_stack)
    df_stack_production_capacity = _calculate_production_volume(df_stack)
    df_emissions = importer.get_emissions()
    df_emissions = df_emissions[df_emissions["year"] == year]
    df_stack_emissions_emitted, df_stack_capture_emissions = _calculate_emissions(
        df_stack, df_emissions
    )
    df_transitions = importer.get_technology_transitions_and_cost()
    df_transitions = df_transitions[df_transitions["year"] == year]
    df_stack_lcox = _calculate_lcox(df_stack, df_transitions)
    df_inputs_outputs = importer.get_inputs_outputs()
    data_variables = []
    for variable in df_inputs_outputs["parameter"].unique():
        df_stack_variable = _calculate_output_from_input(
            df_stack, df_inputs_outputs, variable, year
        )
        df_stack_variable["parameter"] = variable
        data_variables.append(df_stack_variable)
    df_variables = pd.concat(data_variables)
    df_variables = df_variables[
        [
            "product",
            "region",
            "technology",
            "parameter_group",
            "parameter",
            "unit",
            "value",
        ]
    ]
    df_all_data_year = pd.concat(
        [
            df_stack_total_assets,
            df_stack_production_capacity,
            df_stack_emissions_emitted,
            df_stack_capture_emissions,
            df_stack_lcox,
            df_variables,
        ]
    )
    return df_all_data_year


def calculate_outputs(pathway, sensitivity, sector):
    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS[sector],
    )
    data = []
    data_stacks = []
    for year in range(START_YEAR, END_YEAR + 1):
        logger.info(f"Processing year {year}")
        yearly = create_table_all_data_year(year, importer)
        yearly["year"] = year
        data.append(yearly)
        df_stack = importer.get_asset_stack(year)
        df_stack["year"] = year
        data_stacks.append(df_stack)
    df_stacks = pd.concat(data_stacks)
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
    importer.export_data(
        df_pivot, f"simulation_outputs_sensitivity_{sensitivity}.csv", "final"
    )
    columns = [
        "sector",
        "product",
        "region",
        "technology",
        "year",
        "parameter_group",
        "parameter",
        "unit",
        "value",
    ]
    importer.export_data(
        df[columns], f"interface_outputs_sensitivity_{sensitivity}.csv", "final"
    )
    importer.export_data(
        df_stacks, f"plant_stack_transition_sensitivity_{sensitivity}.csv", "final"
    )
    logger.info("All data for all years processed.")

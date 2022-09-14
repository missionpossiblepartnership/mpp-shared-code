""" Calculate all cost components (CCS cost, material and energy input cost)."""

import numpy as np
import pandas as pd

from ammonia.config_ammonia import CCS_COST_COMPONENTS, INCLUDE_DAC_IN_COST
from ammonia.preprocess.pivot_inputs import pivot_inputs
from ammonia.utility.utils import unit_column_suffix


def calculate_ccs_cost(
    df_prices: pd.DataFrame, df_emissions: pd.DataFrame
) -> pd.DataFrame:
    """Calculate CCS OPEX (capture and transport & storage).

    Args:
        df_prices: contains column "price" and rows with "CCS capture" and "CCS - T&S" in column "name".
        df_emissions: contains column "scope_1_captured": tCO2/t product captured by CCS.

    Returns:
        pd.DataFrame: DataFrame with column "ccs_cost"
    """
    # Only keep CCS prices
    df_prices = df_prices.loc[df_prices["name"].isin(CCS_COST_COMPONENTS)].reset_index(
        drop=True
    )

    # Join CCS prices to emissions
    df_prices = unit_column_suffix(df_prices, "ccs_cost")
    df_cost = df_emissions.merge(
        df_prices, on=["product", "year", "region"], how="left"
    )

    # Calculate the two components of CCS cost and sum
    df_cost["ccs_cost"] = (df_cost["co2_scope1_captured"] * df_cost["price"]).fillna(0)
    df_cost = df_cost.groupby(
        by=["product", "technology_destination", "year", "region"], as_index=False
    ).aggregate({"ccs_cost": "sum"})

    return df_cost


def calculate_input_cost(
    df_prices: pd.DataFrame, df_inputs: pd.DataFrame, df_emissions: pd.DataFrame
) -> pd.DataFrame:
    """Calculate cost of the energy and material inputs for each technology.

    Args:
        df_inputs: contains column "input" and "category"
        df_prices: contains column "price" and "name"
        df_emissions: required to check if additional CO2 input needed for urea

    Returns:
        pd.DataFrame: contains column "input_cost"
    """

    # Add respective suffix to unit columns and merge
    df_inputs = unit_column_suffix(df_inputs, "input")
    df_prices = unit_column_suffix(df_prices, "price")
    df_cost = df_inputs.merge(
        df_prices, on=["product", "year", "region", "name"], how="left"
    )

    # The CO2 input for urea production depends on the scope 1 emissions data for the technology
    df_emissions_merge = df_emissions[
        ["product", "year", "region", "technology_destination", "external_co2_input"]
    ]
    df_emissions_merge["name"] = "CO2"

    df_cost = df_cost.merge(
        df_emissions_merge,
        on=["product", "year", "region", "technology_destination", "name"],
        how="left",
    ).fillna(0)

    df_cost["input"] = np.where(
        df_cost["name"] == "CO2", df_cost["external_co2_input"], df_cost["input"]
    )
    df_cost = df_cost.drop(columns=["external_co2_input"])

    # Set CO2 input cost to zero if DAC is not priced in
    if not INCLUDE_DAC_IN_COST:
        df_cost["price"] = np.where(df_cost["name"] == "CO2", 0, df_cost["price"])

    # Variable OPEX is energy and material inputs multiplied with their prices (including external CO2 input for urea business cases)
    df_cost["input_cost"] = df_cost["input"] * df_cost["price"]

    # Rename categories and create pivot table
    df_cost["category"] = df_cost["category"].replace(
        {
            "Energy": "opex_energy",
            "Raw material": "opex_material",
            "H2 storage": "opex_h2_storage",
        }
    )

    df_cost = pivot_inputs(df=df_cost, values="input_cost")

    return df_cost


def calculate_all_cost_components(
    df_inputs: pd.DataFrame,
    df_prices: pd.DataFrame,
    df_emissions: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate all variable OPEX cost components (apart from carbon cost)

    Args:
        df_inputs: contains material and energy inputs in column "input" (GJ/t produced)
        df_prices: contains prices in column "price" (USD/GJ and USD/tCO2)
        df_emissions: contains scope 1 emissions of each technology (tCO2/t produced)

    Returns:
        pd.DataFrame: contains columns "cost_ccs", "input_cost"
    """

    # Calculate the two cost components of CCS, capture and transport & storage
    df_ccs_cost = calculate_ccs_cost(df_prices=df_prices, df_emissions=df_emissions)

    # Calculate cost of inputs (returned as pivot table)
    df_cost = calculate_input_cost(
        df_prices=df_prices, df_inputs=df_inputs, df_emissions=df_emissions
    )

    # Add CCS cost
    df_ccs_cost = df_ccs_cost.set_index(
        ["product", "technology_destination", "year", "region"]
    )
    df_cost["opex_other", "ccs"] = df_ccs_cost["ccs_cost"]

    return df_cost

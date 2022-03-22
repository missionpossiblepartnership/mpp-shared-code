""" Apply implicit forcing mechanisms to the input tables: carbon cost, green premium and technology moratorium."""

import pandas as pd
import numpy as np

from mppshared.model.carbon_cost_trajectory import CarbonCostTrajectory
from mppshared.calculations.cost_calculations import discount_costs
from mppshared.utility.dataframe_utility import (
    add_column_header_suffix,
    get_grouping_columns_for_npv_calculation,
)
from mppshared.config import GHGS, EMISSION_SCOPES


def apply_implicit_forcing(
    df_technology_switches: pd.DataFrame,
    df_emissions: pd.DataFrame,
    df_technology_characteristics: pd.DataFrame,
) -> pd.DataFrame:
    """Apply the implicit forcing mechanisms to the input tables.

    Args:
        df_technology_switches: cost data for every technology switch (regional)
        df_emissions: emissions data for every technology (regional)
        df_technology_characteristics: characteristics for every technology

    Returns:
        pd.DataFrame: DataFrame ready for ranking the technology switches
    """

    # Add carbon cost to TCO
    df_carbon_cost = apply_carbon_cost_to_tco(
        df_technology_switches, df_emissions, df_technology_characteristics
    )

    # TODO: add carbon cost to LCOX and other cost metrics

    # TODO: Subtract green premium from eligible technologies

    # TODO: Eliminate switches according to technology moratorium

    # Apply technology availability constraint
    # df = apply_technology_availability_constraint(df_technology_switches, df_technology_characteristics)

    # Calculate emission deltas between origin and destination technology
    df_emission_deltas = calculate_emission_reduction(
        df_technology_switches, df_emissions
    )

    # Create DataFrame ready for ranking
    df_ranking = df_carbon_cost.merge(
        df_emission_deltas,
        on=[
            "product",
            "technology_origin",
            "region",
            "year",
            "switch_type",
            "technology_destination",
        ],
        how="left",
    )

    return df_ranking


def apply_carbon_cost_to_tco(
    df_technology_switches: pd.DataFrame,
    df_emissions: pd.DataFrame,
    df_technology_characteristics: pd.DataFrame,
) -> pd.DataFrame:
    """

    Args:
        df_technology_switches: cost data for every technology switch (regional)
        df_emissions: emissions data for every technology (regional)
        df_technology_characteristics: characteristics for every technology

    Returns:
        pd.DataFrame: merge of the input DataFrames with additional column "carbon_cost_addition" added to TCO
    """
    # Drop emission columns with other GHGs
    for ghg in [ghg for ghg in GHGS if ghg != "co2"]:
        df_emissions = df_emissions.drop(df_emissions.filter(regex=ghg).columns)

    # Merge technology switches, emissions and technology characteristics
    df = df_technology_switches.merge(
        df_emissions.rename(columns={"technology": "technology_destination"}),
        on=["product", "region", "year", "technology_destination"],
        how="left",
    )

    df = df.merge(
        df_technology_characteristics.rename(
            columns={"technology": "technology_destination"}
        ),
        on=["product", "region", "technology_destination"],
        how="left",
    )

    # Additional cost from carbon cost is carbon cost multiplied with sum of scope 1 and scope 2 CO2 emissions
    cc = CarbonCostTrajectory(trajectory="constant")
    cc.set_carbon_cost()
    df_cc = df.merge(cc.df_carbon_cost, on=["year"])
    df_cc["carbon_cost_addition"] = (df_cc["co2_scope1"] + df_cc["co2_scope2"]) * df_cc[
        "carbon_cost"
    ]

    # Discount carbon cost addition
    # TODO: make grouping column function sector-specific
    grouping_cols = get_grouping_columns_for_npv_calculation("chemicals")

    df_discounted = discount_costs(
        df_cc[
            grouping_cols
            + ["year", "carbon_cost_addition", "technology_lifetime", "wacc"]
        ],
        grouping_cols,
    )

    # Add total discounted carbon cost to each technology switch
    df = df.set_index(grouping_cols + ["year"])
    df["carbon_cost_addition"] = df_discounted["carbon_cost_addition"]

    # Contribution of a cost to TCO is net present cost divided by (lifetime * capacity utilisation factor)
    # TODO: integrate dynamic capacity utilisation functionality
    capacity_factor_dummy = 0.95
    df["carbon_cost_addition_tco"] = (
        df["carbon_cost_addition"] / (df["technology_lifetime"] * capacity_factor_dummy)
    ).fillna(0)

    # Update TCO in technology switching DataFrame
    df_technology_switches = df_technology_switches.set_index(grouping_cols + ["year"])
    df_technology_switches["tco"] = df["tco"] + df["carbon_cost_addition_tco"]

    # Return technology switch DataFrame with updated TCO and reset index
    return df_technology_switches.reset_index(drop=False)


def apply_technology_availability_constraint(
    df_technology_switches: pd.DataFrame, df_technology_characteristics: pd.DataFrame
) -> pd.DataFrame:
    """_summary_

    Args:
        df_technology_switches (pd.DataFrame): _description_
        df_technology_characteristics (pd.DataFrame): _description_

    Returns:
        pd.DataFrame: _description_
    """
    pass


def calculate_emission_reduction(
    df_technology_switches: pd.DataFrame, df_emissions: pd.DataFrame
) -> pd.DataFrame:
    """Calculate emission reduction when switching from origin to destination technology by scope.

    Args:
        df_technology_switches (pd.DataFrame): cost data for every technology switch (regional)
        df_emissions (pd.DataFrame): emissions data for every technology

    Returns:
        pd.DataFrame: contains "delta_{}" for every scope and GHG considered
    """
    # Get columns containing emissions
    cols = [f"{ghg}_{scope}" for ghg in GHGS for scope in EMISSION_SCOPES]

    # Rename column headers for origin and destination technology emissions and drop captured emissions columns
    df_emissions_origin = add_column_header_suffix(
        df_emissions.drop(df_emissions.filter(regex="captured").columns, axis=1),
        cols,
        "origin",
    )

    df_emissions_destination = add_column_header_suffix(
        df_emissions.drop(df_emissions.filter(regex="captured").columns, axis=1),
        cols,
        "destination",
    )

    # Merge to insert origin and destination technology emissions into technology switching table
    df = df_technology_switches.merge(
        df_emissions_origin.rename(columns={"technology": "technology_origin"}),
        on=["product", "region", "year", "technology_origin"],
        how="left",
    )

    df = df.merge(
        df_emissions_destination.rename(
            columns={"technology": "technology_destination"}
        ),
        on=["product", "technology_destination", "region", "year"],
        how="left",
    )

    # Calculate emissions reduction for each technology switch by GHG and scope
    for ghg in GHGS:
        for scope in EMISSION_SCOPES:
            df[f"delta_{ghg}_{scope}"] = df[f"{ghg}_{scope}_origin"].fillna(0) - df[
                f"{ghg}_{scope}_destination"
            ].fillna(0)

    # Drop emissions of destination and origin technology
    drop_cols = [
        f"{ghg}_{scope}_{switch_locator}"
        for switch_locator in ["origin", "destination"]
        for ghg in GHGS
        for scope in EMISSION_SCOPES
    ]
    df = df.drop(columns=drop_cols)

    return df

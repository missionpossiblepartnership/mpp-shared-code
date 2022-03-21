""" Apply implicit forcing mechanisms to the input tables: carbon cost, green premium and technology moratorium."""

import pandas as pd
import numpy as np

from mppshared.model.carbon_cost_trajectory import CarbonCostTrajectory
from mppshared.calculations.cost_calculations import discount_costs


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
    df_ranking = apply_carbon_cost_to_tco(
        df_technology_switches, df_emissions, df_technology_characteristics
    )

    # TODO: add carbon cost to LCOX and other cost metrics

    # TODO: Subtract green premium from eligible technologies

    # TODO: Eliminate switches according to technology moratorium

    # Apply technology availability constraint
    # df = apply_technology_availability_constraint(df_technology_switches, df_technology_characteristics)

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
    grouping_cols = [
        "product",
        "technology_origin",
        "region",
        "switch_type",
        "technology_destination",
    ]
    df_discounted = discount_costs(
        df_cc[
            grouping_cols
            + ["year", "carbon_cost_addition", "technology_lifetime", "wacc"]
        ],
        grouping_cols,
    )

    df = df.set_index(grouping_cols + ["year"])
    df["carbon_cost_addition"] = df_discounted["carbon_cost_addition"]

    # Contribution of a cost to TCO is net present cost divided by (lifetime * capacity utilisation factor)
    capacity_factor_dummy = 0.95
    df["carbon_cost_addition_tco"] = (
        df["carbon_cost_addition"] / (df["technology_lifetime"] * capacity_factor_dummy)
    ).fillna(0)

    # Add carbon cost to TCO
    df["tco"] = df["tco"] + df["carbon_cost_addition_tco"]

    return df.reset_index(drop=False)


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

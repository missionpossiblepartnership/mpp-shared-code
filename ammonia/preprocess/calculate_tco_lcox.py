"""Calculate TCO and LCOX for every technology switch."""
from typing import Optional

import numpy as np
import pandas as pd
import math
from xmlrpc.client import Boolean

from ammonia.config_ammonia import COMMON_INDEX, COST_COMPONENTS, LOG_LEVEL

from mppshared.config import END_YEAR

from ammonia.utility.utils import load_cost_data_from_csv, set_common_multi_index

from mppshared.utility.utils import get_logger

# Logging functionality
logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def calculate_variable_opex(
    df_cost: pd.DataFrame, df_capacity_factor: pd.DataFrame
) -> pd.DataFrame:
    """Calculate variable OPEX from all cost contributions and multiply with capacity factor.

    Args:
        df_cost: pivot table containing cost contributions
        df_capacity_factor: contains column "capacity_factor"

    Returns:
        pd.DataFrame: pivot table with variable OPEX before and after multiplication with capacity factor.
    """
    # Variable OPEX is sum of all non-fixed OPEX contributions (before capacity factor multiplication)
    df_cost["opex_sum", "variable_opex_before_cf"] = (
        df_cost["opex_other", "ccs"]
        + df_cost["opex_energy", "total"]
        + df_cost["opex_material", "total"]
        + df_cost["opex_h2_storage", "total"]
    )

    # Add capacity factor
    df_cf = df_capacity_factor.drop(["unit"], axis=1).set_index(COMMON_INDEX)
    df_cost = df_cost.join(pd.concat({"other": df_cf}, axis=1))

    # Multiply variable OPEX with capacity factor
    df_cost["opex_sum", "variable_opex_after_cf"] = (
        df_cost["opex_sum", "variable_opex_before_cf"]
        * df_cost["other", "capacity_factor"]
    )

    return df_cost


def calculate_total_opex(
    df_cost: pd.DataFrame, df_opex_fixed: pd.DataFrame
) -> pd.DataFrame:
    """Calculate total OPEX from variable OPEX (after capacity factor multiplication) and fixed OPEX.

    Args:
        df_cost: pivot table with variable OPEX contributions
        df_opex_fixed: contains column "opex_fixed"

    Returns:
        pd.DataFrame: pivot table with total OPEX
    """
    # Add fixed OPEX
    df_opex_fixed = df_opex_fixed.set_index(COMMON_INDEX)
    df_cost = df_cost.join(pd.concat({"opex_sum": df_opex_fixed}, axis=1))

    # Calculate total OPEX
    df_cost["opex_sum", "total_opex"] = (
        df_cost["opex_sum", "variable_opex_after_cf"]
        + df_cost["opex_sum", "opex_fixed"]
    )

    return df_cost


def subset_cost_df(
    df_cost: pd.DataFrame, start_year: int, lifetime: int
) -> pd.DataFrame:
    """Filter DataFrame with cost data for a year range.

    Args:
        df_cost: contains columns with cost data, indexed by year (int)
        start_year: first year of year range filtering
        lifetime: required length of the cost series

    Returns:
        pd.DataFrame: subset DataFrame, expanded if necessary
    """
    # Remove columns that are not to be discounted
    df_cost = df_cost.drop(columns=["wacc", "capacity_factor", "lifetime"])

    # Filter year range
    df_cost = df_cost[
        (df_cost.index >= start_year) & (df_cost.index <= start_year + lifetime)
    ]

    # Expand DataFrame beyond model years if necessary, assuming that cost data stay constant after END_YEAR
    if start_year + lifetime > END_YEAR:
        cost_value = df_cost.loc[df_cost.index == END_YEAR].copy()
        extension_length = int((start_year + lifetime) - END_YEAR)
        cost_constant = pd.concat([cost_value] * extension_length)
        cost_constant["year"] = np.arange(END_YEAR + 1, start_year + lifetime + 1)
        cost_constant = cost_constant.set_index("year", drop=True)
        cost_constant.index = cost_constant.index.astype(int)

        df_cost = pd.concat([df_cost, cost_constant])

    return df_cost


def calculate_npv_costs(df_cost: pd.DataFrame) -> pd.DataFrame:
    """Calculate net present value (NPV) of all cost columns in the DataFrame of costs.

    Args:
        df_cost: DataFrame indexed by product, technology_origin, technology_destination, region, type and year

    Returns:
        pd.DataFrame: NPV of each column in the DataFrame, indexed by year
    """

    logger.debug(f"Calculate NPV for business case: {df_cost.index[0]}")

    df_cost.index = df_cost.index.droplevel(
        [
            "product",
            "technology_origin",
            "technology_destination",
            "region",
            "switch_type",
        ]
    )

    return df_cost.apply(
        lambda row: net_present_value(
            rate=row["wacc"],
            df=subset_cost_df(
                df_cost=df_cost, start_year=row.name, lifetime=row["lifetime"]
            ),
        ),
        axis=1,
    )


def net_present_value(
    df: pd.DataFrame, rate: float, cols: list[str] = None
) -> pd.Series:
    """Calculate net present value (NPV) of multiple dataframe columns at once.

    Args:
        df: DataFrame with columns for NPV calculation
        rate: discount rate
        cols: the columns to calculate NPV of (if None, use all columns)

    Returns:
        pd.Series: NPVs of the cost columns, indexed by column name
    """
    value_share = (1 + rate) ** np.arange(0, len(df))
    if cols is None:
        cols = df.columns
    return df[cols].div(value_share, axis=0).sum()


def discount_costs(df_cost: pd.DataFrame, from_csv: Boolean = False) -> pd.DataFrame:
    """Calculate NPV of selected cost columns in the cost DataFrame and sum to NPV of variable OPEX.

    Args:
        df_cost (pd.DataFrame): contains columns with cost data and "lifetime", "wacc", "capacity_factor"
        from_csv (Boolean, default False): read data from .csv instead of calculating it

    Returns:
        pd.DataFrame: columns with NPV of various cost components, NPV of variable OPEX before and after multiplication with capacity factor
    """
    if from_csv:
        return load_cost_data_from_csv()

    discounting_cols = {
        "energy_electricity": ("opex_energy", "electricity"),
        "energy_non_electricity": ("opex_energy", "non_electricity"),
        "raw_material_total": ("opex_material", "total"),
        "h2_storage_total": ("opex_h2_storage", "total"),
        "opex_fixed": ("opex_sum", "opex_fixed"),
        "ccs": ("opex_other", "ccs"),
        "lifetime": ("investment_parameters", "lifetime"),
        "wacc": ("investment_parameters", "wacc"),
        "capacity_factor": ("other", "capacity_factor"),
    }

    # Keep only discounting columns
    df = df_cost[list(discounting_cols.values())]

    # Flatten column multi-index to speed things up
    df.columns = discounting_cols.keys()

    # Discount all costs over time
    df_discount = df.groupby(
        [
            "product",
            "technology_origin",
            "technology_destination",
            "region",
            "switch_type",
        ]
    ).apply(calculate_npv_costs)

    # Calculate NPV of energy costs
    df_discount["energy_total"] = (
        df_discount["energy_electricity"] + df_discount["energy_non_electricity"]
    )

    # Calculate NPV of variable OPEX before multiplication with capacity factor
    df_discount["variable_opex_before_cf"] = (
        df_discount["raw_material_total"]
        + df_discount["energy_total"]
        + df_discount["h2_storage_total"]
        + df_discount["ccs"]
    )

    # Join capacity factor column and multiply with variable OPEX
    df_discount = df_discount.join(df["capacity_factor"], how="left")
    df_discount["variable_opex_after_cf"] = (
        df_discount["variable_opex_before_cf"] * df_discount["capacity_factor"]
    )

    # Keep NPV columns only
    df_discount = df_discount.drop(columns=["capacity_factor"])

    # Merge to cost DataFrame
    return df_cost.join(pd.concat({"npv_over_lifetime": df_discount}, axis=1))


def calculate_total_discounted_production(rate: float, lifetime: int) -> Optional[float]:
    """Calculate total discounted production assuming an annual production volume of 1 tpa."""
    if (math.isnan(lifetime)) | (math.isnan(rate)):
        return None
    else:
        return sum(1 / ((1 + rate) ** np.arange(0, lifetime + 1)))


def add_total_discounted_production(df_cost: pd.DataFrame) -> pd.DataFrame:
    """Add total discounted production to once DataFrame, performing calculation only if lifetime and WACC identical across technologies."""

    # If WACC and lifetime assumption identical for all technology switches, perform calculation only once to speed up runtime
    wacc_unique = df_cost["investment_parameters", "wacc"].dropna().unique()
    lifetime_unique = df_cost["investment_parameters", "lifetime"].dropna().unique()
    if len(wacc_unique == 1) & len(lifetime_unique == 1):
        df_cost[
            "npv_over_lifetime", "total_discounted_production"
        ] = calculate_total_discounted_production(
            rate=wacc_unique[0], lifetime=lifetime_unique[0]
        )

    # If different WACCs and lifetimes, perform calculation for each row of DataFrame
    else:
        df_cost["npv_over_lifetime", "total_discounted_production"] = df_cost.apply(
            lambda x: calculate_total_discounted_production(
                rate=x.loc[["investment_parameters"], "wacc"].iloc[0],
                lifetime=x.loc[["investment_parameters"], "lifetime"].iloc[0],
            ),
            axis=1,
        )

    return df_cost


def calculate_tco_lcox(
    df_switch_capex: pd.DataFrame,
    df_cost: pd.DataFrame,
    df_wacc: pd.DataFrame,
    df_lifetime: pd.DataFrame,
    from_csv: Boolean = False,
) -> pd.DataFrame:
    """Calculate TCO and LCOX for every possible technology switch from switch CAPEX, total OPEX, WACC and technology lifetime.

    Args:
        df_switch_capex: all possible switches from technology_origin to technology_destination with type description
        df_cost: DataFrame with two-level column index that contains cost components
        df_wacc: contains WACC for every technology_destination
        df_lifetime: contains lifetime for every technology_destination
        from_csv: read cost DataFrame from .csv

    Returns:
        pd.DataFrame: contains NPV of various cost columns, total NPV of all costs and TCO for every technology switch
    """

    # Join cost data with switch CAPEX table
    # For switch type "decommission", there is no cost data because the destination technology is "Decommissioned", so fill with zero
    df_switch_capex = df_switch_capex.set_index(COMMON_INDEX)
    df_cost = df_cost.join(
        pd.concat({"tech_switch": df_switch_capex}, axis=1), how="right"
    )

    # Add WACC
    # For decommission, add placeholder WACC to prevent error in NPV calculation
    df_add = df_wacc.loc[
        df_wacc["technology_destination"] == "Natural Gas SMR + ammonia synthesis"
    ].copy()
    df_add["technology_destination"] = "Decommissioned"
    df_wacc = pd.concat([df_wacc, df_add])

    df_wacc = set_common_multi_index(df_wacc).drop(columns=["unit"])
    df_cost = df_cost.join(
        pd.concat({"investment_parameters": df_wacc}, axis=1), how="left"
    )

    # Add lifetime
    # For decommission, add placeholder lifetime to prevent error in NPV calculation
    df_add = df_lifetime.loc[
        df_lifetime["technology_destination"] == "Natural Gas SMR + ammonia synthesis"
    ].copy()
    df_add["technology_destination"] = "Decommissioned"
    df_lifetime = pd.concat([df_lifetime, df_add])

    df_lifetime = set_common_multi_index(df_lifetime).drop(columns=["unit"])
    df_cost = df_cost.join(
        pd.concat({"investment_parameters": df_lifetime}, axis=1), how="left"
    )

    # Add technology_origin to index
    df_cost = df_cost.set_index(
        [("tech_switch", "technology_origin")], append=True
    ).rename_axis(index={("tech_switch", "technology_origin"): "technology_origin"})

    # Add switch type to index
    df_cost = df_cost.set_index(
        [("tech_switch", "switch_type")], append=True
    ).rename_axis(index={("tech_switch", "switch_type"): "switch_type"})

    # Ensure that there are no duplicate rows
    df_cost = df_cost.reset_index().drop_duplicates()
    df_cost = df_cost.set_index(
        [
            "product",
            "technology_destination",
            "year",
            "region",
            "technology_origin",
            "switch_type",
        ]
    )

    # Calculate NPV of cost columns and add to cost DataFrame
    logger.info("Calculating net present costs for all business cases.")
    df_cost = discount_costs(df_cost, from_csv=from_csv)

    # Switch CAPEX NPV is identical to input value because it is incurred in year 0
    df_cost["npv_over_lifetime", "switch_capex"] = df_cost[
        "tech_switch", "switch_capex"
    ]

    # Total NPV is variable OPEX multiplied with capacity factor plus fixed OPEX plus switch CAPEX
    df_cost["npv_over_lifetime", "total"] = (
        df_cost["npv_over_lifetime", "variable_opex_after_cf"]
        + df_cost["npv_over_lifetime", "opex_fixed"]
        + df_cost["tech_switch", "switch_capex"]
    )

    # TCO is total NPV of all costs divided by (Lifetime * Capacity factor)
    for contribution in COST_COMPONENTS:

        # Multiply variable OPEX with capacity factor (cancels out in with capacity factor in denominator)
        if contribution in ["opex_fixed", "switch_capex", "total"]:
            df_cost["tco", contribution] = df_cost[
                "npv_over_lifetime", contribution
            ] / (
                df_cost["investment_parameters", "lifetime"]
                * df_cost["other", "capacity_factor"]
            )
        else:
            df_cost["tco", contribution] = (
                df_cost["npv_over_lifetime", contribution]
                / df_cost["investment_parameters", "lifetime"]
            )

    # LCOX is total NPV of all costs divided by (capacity factor * total discounted production)
    df_cost = add_total_discounted_production(df_cost)

    for contribution in COST_COMPONENTS:

        # Multiply variable OPEX with capacity factor (cancels out in with capacity factor in denominator)
        if contribution in ["opex_fixed", "switch_capex", "total"]:
            df_cost["lcox", contribution] = df_cost[
                "npv_over_lifetime", contribution
            ] / (
                df_cost["npv_over_lifetime", "total_discounted_production"]
                * df_cost["other", "capacity_factor"]
            )
        else:
            df_cost["lcox", contribution] = (
                df_cost["npv_over_lifetime", contribution]
                / df_cost["npv_over_lifetime", "total_discounted_production"]
            )

    return df_cost

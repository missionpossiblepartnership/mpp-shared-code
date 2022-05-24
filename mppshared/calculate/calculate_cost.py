""" Function for cost calculations. """

import numpy as np
import pandas as pd

from mppshared.config import END_YEAR, START_YEAR
from mppshared.utility.log_utility import get_logger

logger = get_logger("Cost calculations")


def discount_costs(df_cost: pd.DataFrame, grouping_cols: list) -> pd.DataFrame:
    """Calculate NPV of all columns in the cost DataFrame apart from the grouping columns.

    Args:
        df_cost: contains columns with cost data and "lifetime" and "wacc"
        grouping_cols: list of column headers for grouping of the cost data

    Returns:
        pd.DataFrame: columns with NPV of various cost components
    """
    # Calculate NPV over data groups with cost series across model time horizon
    logger.info("Calculate NPV")
    return df_cost.groupby(grouping_cols).apply(calculate_npv_costs)


def calculate_npv_costs(df_cost: pd.DataFrame) -> pd.DataFrame:
    """Calculate net present value (NPV) of all cost columns in the DataFrame of costs.

    Args:
        df_cost: DataFrame indexed by product, technology_origin, technology_destination, region, type and year

    Returns:
        pd.DataFrame: NPV of each column in the DataFrame, indexed by year
    """

    df_cost = df_cost.set_index("year")
    return df_cost.apply(
        lambda row: net_present_value(
            rate=row["wacc"],
            df=subset_cost_df(
                df_cost=df_cost.drop(columns=["wacc", "technology_lifetime"]),
                start_year=row.name,
                lifetime=row["technology_lifetime"],
            ),
            cols=["carbon_cost_addition"],
        ),
        axis=1,
    )


def net_present_value(
    df: pd.DataFrame, rate: float, cols: list[str] = None
) -> pd.Series:
    """Calculate net present value (NPV) of multiple dataframe columns at once.
    Args:
        df (pd.DataFrame): DataFrame with columns for NPV calculation
        rate: discount rate
        cols: the columns to calculate NPV of (if None, use all columns)
    Returns:
        pd.Series: NPVs of the cost columns, indexed by column name
    """

    value_share = (1 + rate) ** np.arange(0, len(df))
    if cols is None:
        cols = df.columns
    return df[cols].div(value_share, axis=0).sum()


def subset_cost_df(
    df_cost: pd.DataFrame, start_year: int, lifetime: int
) -> pd.DataFrame:
    """Filter DataFrame with cost data for a year range and expand with constant value of the last year if necessary.

    Args:
        df_cost (pd.DataFrame): contains columns with cost data, indexed by year (int)
        start_year (int): first year of year range filtering
        lifetime (int): required length of the cost series

    Returns:
        pd.DataFrame: subset DataFrame, expanded if necessary
    """
    # Filter year range
    df_cost = df_cost[
        (df_cost.index >= start_year) & (df_cost.index <= start_year + lifetime)
    ]

    # Expand DataFrame beyond model years if necessary, assuming that cost data stay constant after MODEL_END_YEAR
    if start_year + lifetime > df_cost.index.max():
        # TODO: make this workaround nicer
        cost_value = df_cost.loc[
            df_cost.index == df_cost.index.max(), ["carbon_cost_addition"]
        ]
        extension_length = int((start_year + lifetime) - df_cost.index.max())
        cost_constant = pd.concat([cost_value] * extension_length)
        cost_constant["year"] = np.arange(
            df_cost.index.max() + 1, start_year + lifetime + 1
        )
        cost_constant = cost_constant.set_index("year", drop=True)
        cost_constant.index = cost_constant.index.astype(int)
        df_cost = pd.concat([df_cost, cost_constant])
    return df_cost
    # if start_year + lifetime > END_YEAR:
    #     logger.debug(start_year + lifetime)

    #     # TODO: make this workaround nicer
    #     cost_value = df_cost.loc[df_cost.index == END_YEAR].copy()
    #     extension_length = int((start_year + lifetime) - END_YEAR)
    #     cost_constant = pd.concat([cost_value] * extension_length)
    #     cost_constant["year"] = np.arange(END_YEAR + 1, start_year + lifetime + 1)
    #     cost_constant = cost_constant.set_index("year", drop=True)
    #     cost_constant.index = cost_constant.index.astype(int)

    #     df_cost = pd.concat([df_cost, cost_constant])

    # return df_cost

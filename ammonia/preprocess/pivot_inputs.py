"""Create pivot table from inputs DataFrame."""

import pandas as pd


def sum_energy_columns(df_pivot: pd.DataFrame) -> pd.DataFrame:
    """Calculate total electricity, total non-electricity and total energy cost in the pivot table of input costs.

    Args:
        df_pivot: pivot table with first column level "opex_energy", second column level describes energy carrier

    Returns:
        pd.DataFrame: pivot table with the summed columns as described above.
    """

    # Create column lists for electricity and non-electricity energy carriers
    electricity_cols = [
        col for col in df_pivot["opex_energy"].columns if "Electricity" in col
    ]
    non_electricity_cols = [
        col for col in df_pivot["opex_energy"].columns if "Electricity" not in col
    ]

    # Sum energy carrier costs in categories electricity, non-electricity
    if "opex_energy" not in df_pivot.columns.levels[0]:
        df_pivot["opex_energy", "total"] = 0
    else:
        df_pivot["opex_energy", "electricity"] = df_pivot["opex_energy"][
            electricity_cols
        ].sum(axis="columns")
        df_pivot["opex_energy", "non_electricity"] = df_pivot["opex_energy"][
            non_electricity_cols
        ].sum(axis="columns")

        # Total energy cost is sum of electricity and non-electricity cost
        df_pivot["opex_energy", "total"] = (
            df_pivot["opex_energy", "electricity"]
            + df_pivot["opex_energy", "non_electricity"]
        )

    return df_pivot


def sum_raw_material_columns(df_pivot: pd.DataFrame) -> pd.DataFrame:
    """Sum cost of material inputs in pivot table of input costs.

    Args:
        df_pivot: pivot table with first column level "opex_material", second column level describes type of material input

    Returns:
        pd.DataFrame: pivot table with total cost of material inputs
    """
    if "opex_material" in df_pivot.columns.levels[0]:
        df_pivot["opex_material", "total"] = df_pivot["opex_material"].sum(
            axis="columns"
        )
    else:
        df_pivot["opex_material", "total"] = 0

    return df_pivot


def sum_h2_storage_columns(df_pivot: pd.DataFrame) -> pd.DataFrame:
    """Sum cost of H2 storage in pivot table of input costs.

    Args:
        df_pivot: pivot table with first column level "opex_h2_storage", second column level describes type of H2 storage input

    Returns:
        pd.DataFrame: pivot table with total cost of H2 storage
    """
    if "opex_h2_storage" in df_pivot.columns.levels[0]:
        df_pivot["opex_h2_storage", "total"] = df_pivot["opex_h2_storage"].sum(
            axis="columns"
        )
    else:
        df_pivot["opex_h2_storage", "total"] = 0

    return df_pivot


def pivot_inputs(df: pd.DataFrame, values: str) -> pd.DataFrame:
    """
    Create pivot table with two-level column ("category", "name") from inputs DataFrame in long format.

    Args:
        df: Dataframe with inputs in long format
        values: Name of the column with values

    Returns:
        pd.DataFrame: Dataframe with inputs in pivot table format (wide)
    """
    df_pivot = df.pivot_table(
        index=["product", "technology_destination", "year", "region"],
        values=values,
        columns=["category", "name"],
        aggfunc="sum",
    ).fillna(0)

    # Sum the different input categories
    df_pivot = sum_energy_columns(df_pivot)
    df_pivot = sum_raw_material_columns(df_pivot)
    df_pivot = sum_h2_storage_columns(df_pivot)

    return df_pivot

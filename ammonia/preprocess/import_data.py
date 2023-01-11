"""Import data from Business Cases.xlsx, extract into DataFrames for each metric, reformat to long format and save as .csv files for subsequent use."""

import numpy as np
import pandas as pd
from ammonia.config_ammonia import *
from ammonia.utility.utils import (
    explode_rows_for_all_products,
    rename_columns_to_standard_names,
    write_intermediate_data_to_csv,
)
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory
from mppshared.utility.utils import get_logger

# Create logger
logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def import_all(
    pathway_name: str,
    sensitivity: str,
    sector: str,
    carbon_cost_trajectory: CarbonCostTrajectory,
):
    """Load all input data, reformat to long format and save to .csv files for subsequent use.

    Args:
        pathway_name: for compatibility with other model step functions
        sensitivity: Business Cases.xlsx needs to have a suffix "_{sensivity}"
        sector: for compatibility
        carbon_cost_trajectory: for compatibility
    """

    # Mapping of regions to cost classification
    region_to_cost = map_region_to_cost_category(sensitivity)

    # Load input data from business cases, prices and emissions
    for sheet_name, metric_list in INPUT_METRICS.items():

        for metric in metric_list:

            logger.info(f"Importing metric {metric} from sheet {sheet_name}.")

            # Extract corresponding sheet
            df = extract_business_case_data(
                df=read_business_case_excel(sheet_name, sensitivity), metric=metric
            )

            # Add regions where needed
            df = fill_regions_from_nan(df, region_to_cost)

            # Expand to individual products where data is for all products
            df = explode_rows_for_all_products(df)

            # Expand price and emissions data to low-cost power regions
            if sheet_name == "Shared inputs - emissions":
                df = expand_to_low_cost_power_regions(df)

            # Write raw imports data to .csv
            write_intermediate_data_to_csv(
                f"{PREPROCESS_DATA_PATH}/imports_raw", metric, df
            )

            # Reformat to long
            df = reformat_df_to_long(df, METRIC_NAMES[metric])

            # Ensure years are int
            df["year"] = df["year"].astype(int)

            # Reorder columns for readability
            df = reorder_columns(df)

            # Write to .csv
            write_intermediate_data_to_csv(
                f"{PREPROCESS_DATA_PATH}/{sensitivity}/imports_processed", metric, df
            )


def apply_cost_sensitivity(
    df: pd.DataFrame, cost_metric: str, relative_sensitivity: float
) -> pd.DataFrame:
    """Apply relative sensitivity to all entries of a specific cost metric in the DataFrame"""
    df["price"] = np.where(
        df["name"] == cost_metric,
        df["price"] * relative_sensitivity,
        df["price"],
    )
    return df


def expand_to_low_cost_power_regions(df: pd.DataFrame) -> pd.DataFrame:
    """Expand emissions data to low-cost power regions by mapping them to the overall regions."""
    # Copy each row with the overall region and rename it to the corresponding LCPR
    for region in LCPR_MAP.keys():
        df_add = df.loc[df["region"] == region]
        df_add["region"] = LCPR_MAP[region]
        df = pd.concat([df, df_add])

    # Drop duplicates that might be created if LCPRS were already specified for some rows
    df = df.drop_duplicates()

    return df


def fill_regions_from_nan(df: pd.DataFrame, region_to_cost: dict) -> pd.DataFrame:
    """Where region is NaN in the DataFrame, copy the respective row and fill with each region in REGIONS.

    Args:
        df (pd.DataFrame): contains column "region"
        region_to_cost (dict): nested dictionary that maps regions to cost classification. For every technology (key), there is a dictionary with "Low", "Standard", "High" as keys and a corresponding list of regions in REGIONS as items.

    Returns:
        pd.DataFrame: contains column "region" filled with entries of REGIONS (no NaN values), rows copied where necessary
    """

    # Case 1: standard/high/low differentiation
    if "cost_classification" in df.columns:

        for index, row in df.iterrows():
            # Identify rows where "Region" is NaN
            if pd.isnull(row["region"]):

                # Identify regions to be added
                regions = region_to_cost[row["technology_destination"]][
                    row["cost_classification"]
                ]

                # Copy row as many times as regions exist
                df_add = row.to_frame().transpose()
                df_add = pd.concat([df_add] * len(regions))

                # Assign all regions and transpose to DataFrame
                df_add["region"] = regions

                # Concatenate with original DataFrame
                df = pd.concat([df, df_add])

    # Case 2: no differentiation in standard/high/low
    else:
        for index, row in df.iterrows():
            # Identify rows where "Region" is NaN
            if pd.isnull(row["region"]):

                # Copy row as many times as regions exist
                df_add = row.to_frame().transpose()
                df_add = pd.concat([df_add] * len(REGIONS))

                # Assign all regions and transpose to DataFrame
                df_add["region"] = REGIONS

                # Concatenate with original DataFrame
                df = pd.concat([df, df_add])

    # Drop rows where region is NaN (residual rows after mapping to regions above)
    df = df.loc[df["region"].notna()]

    return df.reset_index(drop=True)


def read_business_case_excel(sheet_name: str, sensitivity: str) -> pd.DataFrame:
    """Return specified sheet of Business Cases.xlsx as DataFrame.

    Args:
        sheet_name (str): Name of the sheet in Business Cases.xlsx

    Returns:
        pd.DataFrame: Full data of sheet with correct header
    """

    filename = f"Business Cases_{sensitivity}.xlsx"
    full_path = f"{PREPROCESS_DATA_PATH}/{filename}"
    df = pd.read_excel(
        full_path,
        sheet_name=sheet_name,
        header=2,
        usecols=EXCEL_COLUMN_RANGES[sheet_name],
    )

    # If single input, copy single value to every year to make subsequent calculations easy
    if "is single input?" in df.columns:
        mask = df["is single input?"] == 1
        if mask.any():
            df.loc[mask, MODEL_YEARS] = df.loc[mask, "Single input"]

    # Remove \u200b space characters
    df = df.replace("\u200b", "", regex=True)
    df = df.replace("\xa0", " ", regex=True)

    # Drop rows with only NaN
    df = df.dropna(how="all", axis=0)

    return df


def extract_business_case_data(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Extract data for the specified metric from the DataFrame passed and rename columns to standard column names.

    Args:
        df: DataFrame containing the business cases data
        metric (str): Name of the dataseries to be loaded.

    Returns:
        pd.DataFrame: Loaded data
    """
    # Create filters for data extraction
    metric_filter = MAP_EXCEL_NAMES[metric]
    usecols = MAP_FIELDS_TO_DF_NAME[metric] + list(MODEL_YEARS)

    # Apply filters
    if metric_filter[1]:  # type: ignore
        df = df[
            (df["Metric type"] == metric_filter[0]) & (df["Metric"] == metric_filter[1])  # type: ignore
        ]
    else:
        df = df[df["Metric type"] == metric_filter[0]]  # type: ignore
    df = df[usecols]

    # Reset index
    df = df.reset_index(drop=True)

    # Rename columns to standard names
    return rename_columns_to_standard_names(df)


def map_region_to_cost_category(
    sensitivity: str,
) -> dict:  # sourcery skip: remove-dict-keys
    """Read mapping of regions to low, standard, high CAPEX in Business Cases.xlsx and return as nested dictionary.

    Returns:
        dict: technology as keys, values are dictionaries with "low", "standard", "high" as keys
    """

    # Extract the mapping from Business Cases.xlsx
    df = read_business_case_excel(INPUT_SHEETS[3], sensitivity)

    # Delete regions not in REGIONS (e.g., "Global")
    df = df.loc[df["Region"].isin(REGIONS)]

    # Initialize dictionary
    keys = set(df.columns) - {"Region", "Sector", "Product", "Shorthand"}
    cost_map = {k: dict.fromkeys(["Low", "Standard", "High"], []) for k in keys}  # type: ignore

    # Fill dictionary
    for technology in cost_map.keys():
        for level in cost_map[technology].keys():
            regions = df.loc[df[technology] == level, "Region"].to_list()
            cost_map[technology][level] = regions

    return cost_map


def reformat_df_to_long(df: pd.DataFrame, value_name: str) -> pd.DataFrame:
    """
    Pivot inputs data to long format, using MODEL_YEARS as value variables.

    Args:
        df (pd.DataFrame): Dataframe with year columns in wide format
        value_name (str): Name of the value column that's unpivoted to long format

    Returns:
        Dataframe in long format with columns "year", "value_name"
    """

    # All columns apart from MODEL_YEARS are id variables
    id_vars = set(df.columns) - {x for x in MODEL_YEARS}
    df_long = pd.melt(df, id_vars=id_vars, var_name="year", value_name=value_name)

    return df_long


def reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Reorder DataFrame columns according to order in config.py for better readability.

    Args:
        df (pd.DataFrame): DataFrame containing some or all columns in COLUMN_ORDER

    Returns:
        pd.DataFrame: DataFrame where the first columns are ordered according to COLUMN_ORDER, if they exist
    """
    # Create ordered list of columns
    columns_ordered = [x for x in COLUMN_ORDER if x in df.columns]
    columns_residual = [x for x in df.columns if x not in columns_ordered]
    column_names = columns_ordered + columns_residual

    return df.reindex(columns=column_names)


def get_tech_switches(sensitivity: str) -> pd.DataFrame:
    """Get the possible technology switches from Business Cases.xlsx.

    Returns:
        pd.DataFrame: origin technologies in column "Technology", destination technologies as column headers, type(s) of switches as list of str in cell entries.
    """
    df = read_business_case_excel("Technology switching table", sensitivity).drop(
        columns=["Sector", "Shorthand", "Type"]
    )

    return rename_columns_to_standard_names(df)

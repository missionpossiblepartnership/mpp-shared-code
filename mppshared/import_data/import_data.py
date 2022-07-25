"""
    Import data from Business Cases.xlsx and shared models, extract into DataFrames for each metric, reformat to long
    format and save as .csv files for subsequent use.
"""

import pandas as pd

from mppshared.config import LOG_LEVEL, MODEL_YEARS, SECTOR
from mppshared.import_config import (COLUMN_SINGLE_INPUT, IDX_PER_INPUT_METRIC,
                                     INPUT_METRICS, INPUT_SHEETS,
                                     MAP_COLUMN_NAMES, MAP_EXCEL_NAMES,
                                     REGIONS)
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.utility.dataframe_utility import (explode_rows_for_all_products,
                                                 set_datatypes)
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def import_all(importer: IntermediateDataImporter):
    """
    Load all input data, reformat to long format and save to .csv files (if debug mode) for subsequent use.

    Args:
        importer ():

    Returns:

    """

    # TODO: integrate folder and imports nicely with the DataImporter class
    # Todo: switch to an approach per tab (too general in the current approach)

    # Mapping of regions to cost classification
    region_to_cost = get_region_to_capex_mapping(importer=importer)

    # Load input data from business cases, prices and emissions
    for sheet_name, metric_list in INPUT_METRICS[SECTOR].items():

        for metric in metric_list:

            logger.info(f"Importing metric {metric} from sheet {sheet_name}.")

            # Import and extract corresponding sheet
            df = importer.get_raw_input_data(sheet_name=sheet_name)
            df = extract_business_case_data(df=df, metric=metric)

            # Add regions where needed
            df = add_regions_and_filter_cost_classification(
                df=df, region_to_cost=region_to_cost, metric=metric
            )

            # Expand to individual products where data is for all products
            df = explode_rows_for_all_products(df)

            # Reformat to long
            df = reformat_df_to_long(df=df, value_name="value")

            # Ensure years are int
            df["year"] = df["year"].astype(int)

            # set datatypes
            df = set_datatypes(df=df)

            # set and sort index
            df = df.set_index(keys=IDX_PER_INPUT_METRIC[SECTOR][metric]).sort_index()

            # export
            importer.export_data(
                df=df,
                filename=f"{metric}.csv",
                export_dir="import",
            )


def extract_business_case_data(
    df: pd.DataFrame, metric: str
) -> pd.DataFrame:
    """Extract data for the specified metric from the DataFrame passed and rename columns to standard column names.

    Args:
        df: DataFrame containing the business cases data
        metric (str): Name of the dataseries to be loaded.

    Returns:
        pd.DataFrame: Loaded data
    """

    # If single input, copy single value to every year to make subsequent calculations easy
    if COLUMN_SINGLE_INPUT[SECTOR] in df.columns:
        mask = df[COLUMN_SINGLE_INPUT[SECTOR]] == 1
        if mask.any():
            df.loc[mask, MODEL_YEARS] = df.loc[mask, "Single input"]

    # Remove \u200b space characters
    df = df.replace("\u200b", "", regex=True)
    df = df.replace("\xa0", " ", regex=True)

    # Drop rows with only NaN
    df = df.dropna(how="all", axis=0)

    # extract metric
    metric_filter = MAP_EXCEL_NAMES[SECTOR][metric]

    # Apply filters and copy single values to all MODEL_YEARS if required
    if metric_filter[1]:
        df = df[
            (df["Metric type"] == metric_filter[0]) & (df["Metric"] == metric_filter[1])
        ]
    else:
        df = df[df["Metric type"] == metric_filter[0]]

    # Reset index
    df = df.reset_index(drop=True)

    # Rename columns to standard names
    df.rename(columns=MAP_COLUMN_NAMES, inplace=True)

    # extract relevant columns
    usecols = [x for x in IDX_PER_INPUT_METRIC[SECTOR][metric] if x != "year"] + MODEL_YEARS
    df = df[usecols]

    return df


def get_region_to_capex_mapping(
    importer: IntermediateDataImporter,
) -> dict:
    """Read mapping of regions to low, standard, high CAPEX in Business Cases.xlsx and return as nested dictionary.

    Returns:
        dict: technology as keys, values are dictionaries with "low", "standard", "high" as keys
    """

    # Extract the mapping from Business Cases.xlsx
    df = importer.get_raw_input_data(sheet_name=INPUT_SHEETS[SECTOR][2])

    # Remove \u200b space characters
    df = df.replace("\u200b", "", regex=True)
    df = df.replace("\xa0", " ", regex=True)

    # Drop rows with only NaN
    df = df.dropna(how="all", axis=0)

    # Delete regions not in REGIONS (e.g., "Global")
    df = df.loc[df["Region"].isin(REGIONS)]

    # Initialize dictionary
    keys = set(df.columns) - {"Region", "Sector", "Product", "Shorthand"}
    cost_map = {k: dict.fromkeys(["Low", "Standard", "High"], []) for k in keys}

    # Fill dictionary
    for technology in cost_map.keys():
        for level in cost_map[technology].keys():
            regions = df.loc[df[technology] == level, "Region"].to_list()
            cost_map[technology][level] = regions

    return cost_map


def add_regions_and_filter_cost_classification(
    df: pd.DataFrame,
    region_to_cost: dict,
    metric: str,
) -> pd.DataFrame:
    """Where region is NaN in the DataFrame, copy the respective row and fill with each region in REGIONS.

    Args:
        df (pd.DataFrame): contains column "region"
        region_to_cost (dict): nested dictionary that maps regions to CAPEX classification. For every technology (key),
            there is a dictionary with "Low", "Standard", "High" as keys and a corresponding list of regions in REGIONS
            as items.
        metric ():

    Returns:
        pd.DataFrame: contains column "region" filled with entries of REGIONS (no NaN values), rows copied where
            necessary
    """

    # Case 1: standard/high/low differentiation
    if "cost_classification" in df.columns:

        for index, row in df.iterrows():
            # Identify rows where "Region" is NaN
            if pd.isnull(row["region"]):

                # Identify regions to be added
                # todo: remove this workaround
                if metric == "opex":
                    # make sure that every region - cost classification is kept for "Variable OPEX CCU/CCS"
                    regions = REGIONS
                elif metric == "commodity_prices":
                    if row["metric"] in [
                        "CCS - Transport",
                        "CCS - Storage",
                        "CO2",
                    ]:
                        # make sure that every region - cost classification is kept
                        regions = REGIONS
                    else:
                        # Identify rows where "Region" is NaN
                        if pd.isnull(row["region"]):
                            regions = REGIONS
                        else:
                            regions = [row["region"]]
                elif metric == "capex":
                    # add regions according to CAPEX region mapping
                    regions = region_to_cost[row["technology_destination"]][
                        row["cost_classification"]
                    ]
                else:
                    regions = []

                # Copy row as many times as regions exist
                if len(regions) == 0:
                    df_add = pd.DataFrame()
                else:
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


def reformat_df_to_long(
    df: pd.DataFrame, value_name: str
) -> pd.DataFrame:
    """
    Pivot inputs data to long format, using MODEL_YEARS as value variables.

    Args:
        df (pd.DataFrame): Dataframe with year columns in wide format
        value_name (str): Name of the value column that's unpivoted to long format

    Returns:
        Dataframe in long format with columns "year", "value_name"
    """

    # All columns except for MODEL_YEARS are id variables
    id_vars = set(df.columns) - {x for x in MODEL_YEARS}
    df_long = pd.melt(df, id_vars=id_vars, var_name="year", value_name=value_name)

    return df_long


def get_tech_switches(
    importer: IntermediateDataImporter, transition_types: dict
) -> pd.DataFrame:
    """Get the possible technology switches from Business Cases.xlsx.

    Args:
        importer ():
        transition_types (): all possible types of transitions (model nomenclature as keys and Excel nomenclature as
            values)

    Returns:
        pd.DataFrame: origin technologies in column "Technology", destination technologies as column headers, type(s) of
            switches as list of str in cell entries.
    """

    df = importer.get_raw_input_data(sheet_name=INPUT_SHEETS[SECTOR][0])
    df.drop(columns=["Product", "Shorthand", "Type"], inplace=True)

    df.rename(columns=MAP_COLUMN_NAMES, inplace=True)

    # wide to long
    df = pd.melt(
        frame=df,
        id_vars="technology_origin",
        value_vars=[x for x in list(df) if x != "technology_origin"],
        var_name="technology_destination",
        value_name="switch_type",
    )

    # split where more than one switch is allowed
    if df["switch_type"].str.contains(", ").any():
        df[["switch_type", "temp_switch_type"]] = df["switch_type"].str.split(
            pat=", ", expand=True
        )
        df = (
            pd.melt(
                frame=df,
                id_vars=["technology_origin", "technology_destination"],
                value_vars=["switch_type", "temp_switch_type"],
            )
            .drop(columns="variable")
            .rename(columns={"value": "switch_type"})
        )

    # set datatypes
    df = set_datatypes(df=df)

    # remove NaNs (i.e., unfeasible switches) and set index
    df = (
        df.set_index(["technology_origin", "technology_destination"])
        .dropna(how="all")
        .sort_index()
    )

    # rename values
    reversed_switch_types_dict = {v: k for k, v in transition_types.items()}
    df.replace(to_replace=reversed_switch_types_dict, inplace=True)

    return df

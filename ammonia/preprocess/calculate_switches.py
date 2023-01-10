""" Calculate the possible switches for each technology. """
from typing import Any, Sequence
from xmlrpc.client import Boolean

import pandas as pd

from ammonia.config_ammonia import (
    CALCULATE_FOLDER,
    LOG_LEVEL,
    MAP_SWITCH_TYPES_TO_CAPEX,
    MODEL_YEARS,
    PRODUCTS,
    REGIONS,
)
from ammonia.utility.utils import (
    explode_rows_for_all_products,
    load_intermediate_data_from_csv,
)
from mppshared.utility.utils import get_logger

# Logging functionality
logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)

# Create logger
logger = get_logger("Calculate switches")


def calculate_switch_capex(
    df_tech_switches: pd.DataFrame, df_capex: pd.DataFrame, from_csv: Boolean = False
) -> pd.DataFrame:
    """Create DataFrame with switch CAPEX for every technically possible technology switch. Technology availability constraint not yet applied.

    Args:
        df_tech_switches: maps origin technologies (column "Technology") to destination technologies (column headers) by type of switch (cell entries)
        df_capex: contains technology_destination, technology_origin ("Standard" ors specific technology for renovation CAPEX), name and switching_capex
        from_csv: read from .csv file instead of calculating

    Returns:
        pd.DataFrame: contains columns technology_origin, technology_destination, capex_switch (USD/t production capacity) for every product, region, year
    """
    if from_csv:
        return load_intermediate_data_from_csv(CALCULATE_FOLDER, "switch_capex")

    logger.info("Matching switch CAPEX to technology switches.")

    # Reformat to long
    id_vars = ["product", "technology_origin"]
    df = pd.melt(
        df_tech_switches,
        id_vars=id_vars,
        var_name="technology_destination",
        value_name="type",
    )
    # Transform comma-separated type entries into a list
    df.loc[df["type"].notna(), "type"] = df.loc[df["type"].notna(), "type"].apply(
        create_list_from_comma_separated_entry
    )

    # Transfer every element of list to row, replicating index
    df = df.explode("type")

    # Drop switches without type (i.e., that are not possible)
    df = df.dropna(how="any", axis=0)

    # Expand rows with all products
    df = explode_rows_for_all_products(df)

    # Ensure aligned nomenclature
    df["type"] = df["type"].replace(
        {
            "Greenfield": "greenfield",
            "Brownfield rebuild": "brownfield_newbuild",
            "Brownfield renovation": "brownfield_renovation",
            "Decommission": "decommission",
        }
    )

    # Add years
    df_products = pd.DataFrame({"product": PRODUCTS})
    df_years = pd.DataFrame({"year": MODEL_YEARS})
    df_products_years = df_products.merge(df_years, how="cross")
    df = df.merge(df_products_years, on="product", how="left")

    # Add regions and CAPEX low/high/standard
    df_regions = pd.DataFrame({"region": REGIONS})
    df_products_regions = df_products.merge(df_regions, how="cross")
    df = df.merge(df_products_regions, on="product", how="left")

    # Add switching CAPEX values
    # Rename CAPEX values identical to switch types
    df_capex["name"] = df_capex["name"].replace(
        {"Greenfield Capex": "greenfield", "Renovation Capex": "brownfield_renovation"}
    )
    df_capex = df_capex.rename(
        {"name": "type", "switching_capex": "switch_capex"}, axis=1
    )

    # Assume that greenfield CAPEX is identical to brownfield rebuild CAPEX
    df_capex["type"] = df_capex["type"].astype(object)

    for i in df_capex.loc[df_capex["type"] == "greenfield"].index:
        df_capex.at[i, "type"] = ["greenfield", "brownfield_newbuild"]

    df_capex = df_capex.explode("type").reset_index(drop=True)

    # Technology origin for greenfield is "New-build"
    df_capex.loc[df_capex["type"] == "greenfield", "technology_origin"] = "New-build"

    # Technology origin for brownfield rebuild can be any technology (before restriction to allowed switches)
    technologies = list(df_capex["technology_destination"].unique())
    df_capex["technology_origin"] = df_capex["technology_origin"].astype(object)

    for i in df_capex.loc[
        (df_capex["technology_origin"].isna())
        & (df_capex["type"] == "brownfield_newbuild")
    ].index:
        df_capex.at[i, "technology_origin"] = technologies

    df_capex = df_capex.explode("technology_origin")

    # Insert switch CAPEX values with left join to preserve only possible switches
    df = df.merge(
        df_capex,
        on=[
            "product",
            "year",
            "region",
            "type",
            "technology_destination",
            "technology_origin",
        ],
        how="left",
    )

    # Assume that decommission CAPEX is zero
    df.loc[df["type"] == "decommission", "switch_capex"] = 0

    # Drop all rows for which no switch CAPEX value exists
    df = df.loc[df["switch_capex"].notna()]

    df = df.rename({"type": "switch_type"}, axis=1)

    return df.reset_index(drop=True)


def create_list_from_comma_separated_entry(entry: str) -> Sequence[Any]:
    """If the Series entry "type" contains more than one entry separated by comma, return entries as list of strings. Else, return entry unmodified."""
    return list(entry.split(",")) if "," in entry else entry


def get_switch_capex(series: pd.Series, df_capex: pd.DataFrame) -> float | None:
    """Get the right switch CAPEX based on product, technology_origin, technology_destination, year, region and type"""

    # Assume that decommission CAPEX is always zero
    if series["type"] == "decommission":
        return 0

    # Filter CAPEX DataFrame based on the technology switch for which the CAPEX data is needed
    filter = (
        (df_capex["product"] == series["product"])
        & (df_capex["name"] == MAP_SWITCH_TYPES_TO_CAPEX[series["type"]])
        & (df_capex["region"] == series["region"])
        & (df_capex["technology_destination"] == series["technology_destination"])
        & (df_capex["year"] == series["year"])
    )
    subset = df_capex[filter]

    # Return None if no CAPEX data for the technology switch
    if subset.empty:
        return None

    # For brownfield renovation, the CAPEX depends on the origin technology. If the origin technology of the technology switch series is not in the CAPEX DataFrame, take the value where technology_origin is "Standard"
    if series["type"] == "brownfield_renovation":

        # Case 1: the technology in the technology switch series is not in the CAPEX DataFrame. Take the CAPEX where technology_origin is "Standard"
        if subset.loc[subset["technology_origin"] == series["technology_origin"]].empty:
            return subset.loc[
                subset["technology_origin"] == "Standard", "switching_capex"
            ].iloc[0]

        # Case 2: there is a specific renovation CAPEX for the technology switch series
        else:
            return subset.loc[
                subset["technology_origin"] == series["technology_origin"],
                "switching_capex",
            ].iloc[0]

    # For all other switching types, there is only one CAPEX number
    else:
        return subset["switching_capex"].iloc[0]

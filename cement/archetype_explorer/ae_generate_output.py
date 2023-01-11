""" cleans and aggregates outputs of multiple archetype explorer runs """

from pathlib import Path

import pandas as pd
from cement.archetype_explorer.ae_config import (
    AE_SENSITIVITY_MAPPING,
    AE_YEARS,
    TECH_DESTINATION_NAME_MAP,
    TECH_ORIGIN_NAME_MAP,
    TECH_SPLIT_MAP,
)
from cement.config.config_cement import ASSUMED_ANNUAL_PRODUCTION_CAPACITY, PRODUCTS
from mppshared.config import LOG_LEVEL
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.utility.dataframe_utility import round_significant_numbers
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def ae_aggregate_outputs(
    runs: list,
    sector: str,
):
    """Aggregates and exports all outputs from all runs"""

    df_list = []

    for pathway_name, sensitivity in runs:

        logger.info(f"Aggregating outputs for {pathway_name}_{sensitivity}")

        sensitivity_params = AE_SENSITIVITY_MAPPING[sensitivity]

        importer = IntermediateDataImporter(
            pathway_name=pathway_name,
            sensitivity=sensitivity,
            sector=sector,
            products=PRODUCTS,
        )

        df = importer.get_technologies_to_rank()

        # filter brownfield and columns
        df = df.loc[
            (
                (df["switch_type"] == "brownfield_renovation")
                & (df["year"].isin(AE_YEARS))
            ),
            [
                x
                for x in df.columns
                if x
                not in [
                    "switch_type",
                    "co2_scope3_upstream_origin",
                    "ch4_scope1_origin",
                    "ch4_scope2_origin",
                    "ch4_scope3_upstream_origin",
                    "co2e_scope1_origin",
                    "co2e_scope2_origin",
                    "co2e_scope3_upstream_origin",
                    "co2_scope3_upstream_destination",
                    "ch4_scope1_destination",
                    "ch4_scope2_destination",
                    "ch4_scope3_upstream_destination",
                    "co2e_scope1_destination",
                    "co2e_scope2_destination",
                    "co2e_scope3_upstream_destination",
                    "delta_co2_scope3_upstream",
                    "delta_ch4_scope1",
                    "delta_ch4_scope2",
                    "delta_ch4_scope3_upstream",
                    "delta_co2e_scope1",
                    "delta_co2e_scope2",
                    "delta_co2e_scope3_upstream",
                ]
            ],
        ]

        # add capture rate to technology
        df = _add_capture_rate_as_str(importer=importer, df=df)

        # add LCOC technology_origin and LCOC delta
        df = _add_lcoc(importer=importer, df=df)

        # add abatement potential
        df["prod_vol"] = ASSUMED_ANNUAL_PRODUCTION_CAPACITY
        df = _add_abatement_potential(df=df)

        # add relative emission change
        df = _add_emission_delta_rel(df=df)

        # add sensitivity columns
        for key in [x for x in sensitivity_params.keys() if x != "capture_rate"]:
            df[key] = sensitivity_params[key]

        # filter and sort columns
        idx = list(sensitivity_params.keys()) + [
            "product",
            "year",
            "region",
            "technology_origin",
            "technology_destination",
        ]
        val_cols = [
            "lcoc_delta_rel",
            "switch_capex",
            "co2_scope1_destination",
            "co2_scope2_destination",
            "delta_co2_scope1",
            "delta_co2_scope2",
            "delta_rel_co2_scopes12",
            "emission_abatement",
            "abatement_cost",
        ]
        df = df[idx + val_cols]
        df = df.set_index(idx).sort_index()

        # add to df_list
        df_list.append(df)

    # aggregate
    df = pd.concat(df_list)

    # round to 3 significant numbers
    for col in df.columns:
        df[col] = round_significant_numbers(x=df[col], p=3)

    # split and rename technologies (also resets index)
    df = split_and_rename_technologies(df)

    # drop duplicate rows
    df = df.loc[~df.duplicated(), :]

    # export
    export_path = f"{Path(__file__).resolve().parents[2]}/{sector}/data/{pathway_name}/ae_aggregated_outputs.csv"
    df.to_csv(export_path, index=False)


def _add_capture_rate_as_str(
    importer: IntermediateDataImporter, df: pd.DataFrame
) -> pd.DataFrame:

    df_capture_rate = importer.get_imported_input_data(
        input_metrics={"Technology cards": ["capture_rate"]}
    )["capture_rate"]
    df_capture_rate = df_capture_rate.drop(columns=["metric", "unit"]).rename(
        columns={"value": "capture_rate"}
    )

    df_capture_rate["no_capture"] = df_capture_rate["capture_rate"] == 0
    df_capture_rate["capture_rate"] = (
        (df_capture_rate["capture_rate"] * 100).round(decimals=1).astype("string")
    )
    df_capture_rate["pre"] = " ("
    df_capture_rate["suf"] = "% capture rate)"
    df_capture_rate["capture_rate"] = df_capture_rate["pre"].str.cat(
        df_capture_rate["capture_rate"]
    )
    df_capture_rate["capture_rate"] = df_capture_rate["capture_rate"].str.cat(
        df_capture_rate["suf"]
    )
    df_capture_rate.loc[df_capture_rate["no_capture"], "capture_rate"] = ""
    df_capture_rate.drop(columns=["pre", "suf", "no_capture"], inplace=True)

    # merge
    df = pd.merge(
        left=df,
        right=df_capture_rate,
        how="left",
        on=["product", "region", "year", "technology_destination"],
    )

    return df


def _add_lcoc(importer: IntermediateDataImporter, df: pd.DataFrame) -> pd.DataFrame:

    df_lcoc = importer.get_lcox()

    # get LCOC of switches without tech change
    df_lcoc.rename(columns={"value_high_low": "lcoc_origin"}, inplace=True)
    df_lcoc = df_lcoc.loc[
        (
            (df_lcoc["technology_origin"] == df_lcoc["technology_destination"])
            & (df_lcoc["switch_type"] == "brownfield_renovation")
        ),
        ["product", "year", "region", "technology_origin", "lcoc_origin"],
    ]

    # merge
    df.rename(columns={"lcox": "lcoc_switch"}, inplace=True)
    df = pd.merge(
        left=df,
        right=df_lcoc,
        how="left",
        on=["product", "year", "region", "technology_origin"],
    )

    # get change in LCOC
    df["lcoc_delta_rel"] = (df["lcoc_switch"] - df["lcoc_origin"]) / df["lcoc_origin"]

    return df


def _add_abatement_potential(
    df: pd.DataFrame, max_potential: bool = False
) -> pd.DataFrame:

    # emission abatement [kt CO2] = emission factor [t CO2 / t clk] * production volume [Mt CO2] * 1e3
    df["emission_abatement"] = (
        df["prod_vol"] * (df["delta_co2_scope1"] + df["delta_co2_scope2"]) * 1e3
    )

    # abatement cost [USD / t CO2] = (LCOC switch - LCOC origin) [USD / t clk] / delta emission factor [t CO2 / t clk]
    df["abatement_cost"] = (df["lcoc_switch"] - df["lcoc_origin"]) / (
        df["delta_co2_scope1"] + df["delta_co2_scope2"]
    )

    return df


def _add_emission_delta_rel(df: pd.DataFrame) -> pd.DataFrame:

    df["delta_co2_scope1"] *= -1
    df["delta_co2_scope2"] *= -1

    df["delta_rel_co2_scopes12"] = (df["delta_co2_scope1"] + df["delta_co2_scope2"]) / (
        df["co2_scope1_origin"] + df["co2_scope2_origin"]
    )

    return df


def split_and_rename_technologies(df: pd.DataFrame) -> pd.DataFrame:

    idx = [x for x in df.index.names if x != "capture_rate"] + [
        "fuel_type",
        "capture_technology",
    ]
    val_cols = list(df.columns)
    df = df.reset_index()

    # split tech destination
    df["fuel_type"] = df["technology_destination"]
    df["fuel_type"].replace(to_replace=TECH_SPLIT_MAP, inplace=True)
    df["capture_technology"] = df["fuel_type"].str.split(", ", n=1, expand=True)[1]
    df["fuel_type"] = df["fuel_type"].str.split(", ", n=1, expand=True)[0]

    # add capture rate
    df["capture_technology"] = df["capture_technology"].str.cat(df["capture_rate"])

    # rename tech origin & destination
    df["technology_origin"].replace(to_replace=TECH_ORIGIN_NAME_MAP, inplace=True)
    df["technology_destination"].replace(
        to_replace=TECH_DESTINATION_NAME_MAP, inplace=True
    )
    df["technology_destination"] = df["technology_destination"].str.cat(
        df["capture_rate"]
    )

    df = df[idx + val_cols]

    return df

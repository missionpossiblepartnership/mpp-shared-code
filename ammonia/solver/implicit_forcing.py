""" Apply implicit forcing mechanisms to the input tables: technology moratorium, carbon cost, and other filters."""

# Libary imports
from datetime import timedelta
from pathlib import Path
from timeit import default_timer as timer

import numpy as np
import pandas as pd
from ammonia.config_ammonia import (
    EMISSION_SCOPES,
    GHGS,
    GROUPING_COLS_FOR_NPV,
    LOG_LEVEL,
    PRODUCTS,
    RANKING_COST_METRIC,
    REGIONS_SALT_CAVERN_AVAILABILITY,
    SCOPES_CO2_COST,
    STANDARD_CUF,
    STANDARD_LIFETIME,
    STANDARD_WACC,
    START_YEAR,
    TECHNOLOGY_MORATORIUM,
    TRANSITIONAL_PERIOD_YEARS,
)
from mppshared.calculate.calculate_cost import discount_costs
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory
from mppshared.solver.implicit_forcing import (
    add_technology_classification_to_switching_table,
)
from mppshared.utility.dataframe_utility import add_column_header_suffix
from mppshared.utility.function_timer_utility import timer_func
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def apply_implicit_forcing(
    pathway_name: str,
    sensitivity: str,
    sector: str,
    carbon_cost_trajectory: CarbonCostTrajectory,
):
    """Apply the implicit forcing mechanisms to the input tables.

    Args:
        pathway_name: in PATHWAYS
        sensitivity: in SENSITIVITES
        sector: corresponds to SECTOR in config
        carbon_cost_trajectory: describes the evolution of carbon cost
    """
    logger.info(f"Applying implicit forcing for {pathway_name}")

    # Import input tables
    importer = IntermediateDataImporter(
        pathway_name=pathway_name,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS,
        carbon_cost_trajectory=carbon_cost_trajectory,
    )

    df_technology_switches = importer.get_technology_transitions_and_cost()
    df_emissions = importer.get_emissions()
    df_technology_characteristics = importer.get_technology_characteristics()

    # Apply technology availability constraint
    df_technology_switches = apply_technology_availability_constraint(
        df_technology_switches, df_technology_characteristics
    )

    # Eliminate technologies with geological H2 storage in regions without salt caverns
    df_technology_switches = apply_salt_cavern_availability_constraint(
        df_technology_switches, sector
    )

    # Ensure that disallowed technology switches are removed
    switches_drop = (
        df_technology_switches["technology_destination"]
        == "GHR + CCS + ammonia synthesis"
    ) & (df_technology_switches["switch_type"] == "brownfield_renovation")
    df_technology_switches = df_technology_switches.loc[~switches_drop]

    # Waste to ammonia and waste water to ammonium nitrate taken out
    techs_to_drop = [
        "Waste to ammonia",
        "Waste Water to ammonium nitrate",
    ]
    switches_drop = (
        df_technology_switches["technology_destination"].isin(techs_to_drop)
    ) | (df_technology_switches["technology_origin"].isin(techs_to_drop))
    df_technology_switches = df_technology_switches.loc[~switches_drop]

    # Apply technology moratorium (year after which newbuild capacity must be transition or
    # end-state technologies)
    if pathway_name != "bau":
        df_technology_switches = apply_technology_moratorium(
            df_technology_switches=df_technology_switches,
            df_technology_characteristics=df_technology_characteristics,
            moratorium_year=TECHNOLOGY_MORATORIUM,
            transitional_period_years=TRANSITIONAL_PERIOD_YEARS,
        )
    # Add technology classification
    if "technology_classification" not in df_technology_switches.columns:
        # Add the technology classification to the ranking table
        df_technology_switches = add_technology_classification_to_switching_table(
            df_technology_switches, df_technology_characteristics
        )

    # Apply carbon cost
    df_cc = carbon_cost_trajectory.df_carbon_cost
    if df_cc["carbon_cost"].sum() == 0:
        df_carbon_cost = df_technology_switches.copy()
    else:
        start = timer()
        df_carbon_cost_addition = calculate_carbon_cost_addition_to_cost_metric(
            df_technology_switches=df_technology_switches,
            df_emissions=df_emissions,
            df_technology_characteristics=df_technology_characteristics,
            cost_metric=RANKING_COST_METRIC,
            df_carbon_cost=df_cc,
        )
        end = timer()
        logger.info(
            f"Time elapsed to apply carbon cost to {len(df_carbon_cost_addition)} rows: {timedelta(seconds=end-start)}"
        )

        # Write carbon cost to intermediate folder
        importer.export_data(
            df=df_carbon_cost_addition,
            filename="carbon_cost_addition.csv",
            export_dir="intermediate",
            index=False,
        )

        # Update cost metric in technology switching DataFrame with carbon cost
        cost_metric = RANKING_COST_METRIC
        merge_cols = [
            "product",
            "technology_origin",
            "technology_destination",
            "region",
            "switch_type",
            "year",
        ]
        df_carbon_cost = df_technology_switches.merge(
            df_carbon_cost_addition[
                merge_cols + [f"carbon_cost_addition_{cost_metric}"]
            ],
            on=merge_cols,
            how="left",
        )

        df_carbon_cost[cost_metric] = (
            df_carbon_cost[cost_metric]
            + df_carbon_cost[f"carbon_cost_addition_{cost_metric}"]
        )

    # Calculate emission deltas between origin and destination technology
    df_ranking = calculate_emission_reduction(df_carbon_cost, df_emissions)
    importer.export_data(
        df=df_ranking,
        filename="technologies_to_rank.csv",
        export_dir="intermediate",
        index=False,
    )


def apply_salt_cavern_availability_constraint(
    df_technology_transitions: pd.DataFrame, sector: str
) -> pd.DataFrame:
    """Take out technologies with geological H2 storage in regions that do not have salt cavern availability"""
    if sector not in REGIONS_SALT_CAVERN_AVAILABILITY.keys():
        return df_technology_transitions

    salt_cavern_availability = REGIONS_SALT_CAVERN_AVAILABILITY[sector]
    for region in [
        reg for reg in salt_cavern_availability if salt_cavern_availability[reg] == "no"  # type: ignore
    ]:
        filter = (df_technology_transitions["region"] == region) & (
            (
                df_technology_transitions["technology_destination"].str.contains(
                    "H2 storage - geological"
                )
                | (
                    df_technology_transitions["technology_origin"].str.contains(
                        "H2 storage - geological"
                    )
                )
            )
        )

        df_technology_transitions = df_technology_transitions.loc[~filter]

    return df_technology_transitions


def calculate_carbon_cost_addition_to_cost_metric(
    df_technology_switches: pd.DataFrame,
    df_emissions: pd.DataFrame,
    df_technology_characteristics: pd.DataFrame,
    cost_metric: str,
    df_carbon_cost: pd.DataFrame,
) -> pd.DataFrame:
    """Apply constant carbon cost to a cost metric.

    Args:
        df_technology_switches: cost data for every technology switch (regional)
        df_emissions: emissions data for every technology (regional)
        df_technology_characteristics: characteristics for every technology

    Returns:
        pd.DataFrame: merge of the input DataFrames with additional column "carbon_cost_addition" added to TCO
    """
    # Drop emission columns with other GHGs
    for ghg in [ghg for ghg in GHGS if ghg != "co2"]:
        df_emissions = df_emissions.drop(columns=df_emissions.filter(regex=ghg).columns)

    # Merge technology switches, emissions and technology characteristics
    df = df_technology_switches.merge(
        df_emissions.rename(columns={"technology": "technology_destination"}),
        on=["product", "region", "year", "technology_destination"],
        how="left",
    ).fillna(0)

    df = df.merge(
        df_technology_characteristics.rename(
            columns={"technology": "technology_destination"}
        ),
        on=["product", "region", "year", "technology_destination"],
        how="left",
    ).fillna(0)

    # Additional cost from carbon cost is carbon cost multiplied with sum of the co2 emission scopes included in the optimization
    df = df.merge(df_carbon_cost, on=["year"], how="left")
    df["sum_co2_emissions"] = 0
    for scope in SCOPES_CO2_COST:
        df["sum_co2_emissions"] += df[f"co2_{scope}"]
    df["carbon_cost_addition"] = df["sum_co2_emissions"] * df["carbon_cost"]
    df["carbon_cost_addition_marginal_cost"] = df["carbon_cost_addition"]
    df["carbon_cost_addition_annualized_cost"] = df["carbon_cost_addition"]

    # Discount carbon cost addition
    df_discounted = discount_costs(
        df[
            GROUPING_COLS_FOR_NPV
            + ["year", "carbon_cost_addition", "technology_lifetime", "wacc"]
        ],
        GROUPING_COLS_FOR_NPV,
    )

    # Add total discounted carbon cost to each technology switch
    df = df.set_index(GROUPING_COLS_FOR_NPV + ["year"])
    df["carbon_cost_addition"] = df_discounted["carbon_cost_addition"]

    if cost_metric == "tco":
        # Contribution of a cost to TCO is net present cost divided by (lifetime * capacity utilisation factor)
        df["carbon_cost_addition_tco"] = (
            df["carbon_cost_addition"] / (df["technology_lifetime"] * STANDARD_CUF)
        ).fillna(0)

        # Update TCO in technology switching DataFrame
        df_technology_switches = df_technology_switches.set_index(
            GROUPING_COLS_FOR_NPV + ["year"]
        )
        df_technology_switches["tco"] = df["tco"] + df["carbon_cost_addition_tco"]

    elif cost_metric == "lcox":
        # Contribution of a cost to LCOX is net present cost divided by (CUF * total discounted production)
        value_shares = (1 + STANDARD_WACC) ** np.arange(0, STANDARD_LIFETIME + 1)
        total_discounted_production = np.sum(1 / value_shares)

        df["carbon_cost_addition_lcox"] = (
            df["carbon_cost_addition"] / (STANDARD_CUF * total_discounted_production)
        ).fillna(0)

    # Return technology switch DataFrame with carbon cost addition
    return df.reset_index(drop=False).drop(
        columns=[
            "technology_classification_x",
            "technology_classification_y",
            "wacc",
            "trl_current",
            "technology_lifetime",
        ]
    )


def apply_technology_availability_constraint(
    df_technology_switches: pd.DataFrame, df_technology_characteristics: pd.DataFrame
) -> pd.DataFrame:
    """Remove technology switches where the destination technology has not yet reached maturity."""

    # Add classification of origin and destination technologies to technology transitions table
    df_tech_char_destination = df_technology_characteristics[
        ["product", "year", "region", "technology", "technology_classification"]
    ].rename(
        {
            "technology": "technology_destination",
            "technology_classification": "classification_destination",
        },
        axis=1,
    )

    df_tech_char_origin = df_technology_characteristics[
        ["product", "year", "region", "technology", "technology_classification"]
    ].rename(
        {
            "technology": "technology_origin",
            "technology_classification": "classification_origin",
        },
        axis=1,
    )
    df = df_technology_switches.merge(
        df_tech_char_destination,
        on=["product", "year", "region", "technology_destination"],
        how="left",
    ).fillna(0)
    df = df.merge(
        df_tech_char_origin,
        on=["product", "year", "region", "technology_origin"],
        how="left",
    ).fillna(0)

    # Constraint 1: no switches from transition or end-state to initial technologies
    df = df.loc[
        ~(
            (
                (df["classification_origin"] == "transition")
                & (df["classification_destination"] == "initial")
            )
            | (
                (df["classification_origin"] == "end-state")
                & (df["classification_destination"] == "initial")
            )
            | (
                (df["classification_origin"] == "end-state")
                & (df["classification_destination"] == "transition")
            )
        )
    ]

    # Constraint 2: transitions to a technology are only possible when it has reached maturity
    df = df.merge(
        df_technology_characteristics[
            ["product", "year", "region", "technology", "expected_maturity"]
        ].rename({"technology": "technology_destination"}, axis=1),
        on=["product", "year", "region", "technology_destination"],
        how="left",
    ).fillna(START_YEAR)
    df = df.loc[df["year"] >= df["expected_maturity"]]

    # Constraint 3: no transitions between end-state technologies
    df = df.loc[
        ~(
            (df["classification_destination"] == "end-state")
            & (df["classification_origin"] == "end-state")
        )
    ]

    return df.drop(
        columns=[
            "classification_origin",
            "classification_destination",
            "expected_maturity",
        ]
    )


def apply_regional_technology_ban(
    df_technology_switches: pd.DataFrame, sector_bans: dict
) -> pd.DataFrame:
    """Remove certain technologies from the technology switching table that are banned in certain regions (defined in config.py)"""
    if not sector_bans:
        return df_technology_switches
    for region in sector_bans.keys():
        banned_transitions = (df_technology_switches["region"] == region) & (
            df_technology_switches["technology_destination"].isin(sector_bans[region])
        )
        df_technology_switches = df_technology_switches.loc[~banned_transitions]
    return df_technology_switches


def apply_technology_moratorium(
    df_technology_switches: pd.DataFrame,
    df_technology_characteristics: pd.DataFrame,
    moratorium_year: int,
    transitional_period_years: int,
) -> pd.DataFrame:
    """Eliminate all newbuild transitions to a conventional technology after a specific year"""

    # Add technology classification to each destination technology
    df_tech_char_destination = df_technology_characteristics[
        [
            "product",
            "year",
            "region",
            "technology",
            "technology_classification",
            "technology_lifetime",
            "wacc",
        ]
    ].rename(
        {"technology": "technology_destination"},
        axis=1,
    )
    df_technology_switches = df_technology_switches.merge(
        df_tech_char_destination,
        on=["product", "year", "region", "technology_destination"],
        how="left",
    ).fillna(0)

    # Drop technology transitions of type new-build where the technology_destination is classified as initial
    banned_transitions = (
        (df_technology_switches["year"] >= moratorium_year)
        & (df_technology_switches["technology_classification"] == "initial")
        & (df_technology_switches["switch_type"] != "decommission")
    )
    df_technology_switches = df_technology_switches.loc[~banned_transitions]

    # Drop technology transitions for 'transition' technologies after moratorium year + x years
    banned_transitions = (
        (df_technology_switches["year"] >= moratorium_year + transitional_period_years)
        & (df_technology_switches["technology_classification"] == "transition")
        & (df_technology_switches["switch_type"] != "decommission")
    )
    df_technology_switches = df_technology_switches.loc[~banned_transitions]

    return df_technology_switches


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
    # Get columns containing emissions and filter emissions table accordingly
    cols = [f"{ghg}_{scope}" for ghg in GHGS for scope in EMISSION_SCOPES]
    df_emissions = df_emissions[["product", "technology", "year", "region"] + cols]

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

    # Merge to insert origin and destination technology emissions into technology switching table (fill with zero to account for new-build and decommission)
    df = df_technology_switches.merge(
        df_emissions_origin.rename(columns={"technology": "technology_origin"}),
        on=["product", "region", "year", "technology_origin"],
        how="left",
    ).fillna(0)

    df = df.merge(
        df_emissions_destination.rename(
            columns={"technology": "technology_destination"}
        ),
        on=["product", "technology_destination", "region", "year"],
        how="left",
    ).fillna(0)

    # Calculate emissions reduction for each technology switch by GHG and scope
    for ghg in GHGS:
        for scope in EMISSION_SCOPES:
            df[f"delta_{ghg}_{scope}"] = df[f"{ghg}_{scope}_origin"].fillna(0) - df[
                f"{ghg}_{scope}_destination"
            ].fillna(0)

    return df

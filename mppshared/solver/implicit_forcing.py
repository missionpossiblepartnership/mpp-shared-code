""" Functions to apply implicit forcing mechanisms to the solver input tables."""

# Library imports
from datetime import timedelta
from timeit import default_timer as timer
import numpy as np
import pandas as pd

# Shared code imports
from mppshared.calculate.calculate_cost import discount_costs
from mppshared.config import (
    HYDRO_TECHNOLOGY_BAN,
    SCOPES_CO2_COST,
    START_YEAR,
)
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory
from mppshared.utility.dataframe_utility import (
    add_column_header_suffix,
    get_grouping_columns_for_npv_calculation,
)

# Initialize logger
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)


def apply_salt_cavern_availability_constraint(
    df_technology_switches: pd.DataFrame, regions_salt_cavern_availability: dict
) -> pd.DataFrame:
    """Filter out technologies with geological H2 storage in regions that do not have salt cavern availability

    Args:
        df_technology_switches (pd.DataFrame): Needs to contain columns "technology_destination" and "technology_origin"
        regions_salt_cavern_availability (dict): Contains salt cavern availability ("yes"/"no") for each region as in the column "region" of df_technology_switches

    Returns:
        pd.DataFrame: technology switching table with the disallowed switches removed
    """

    # Take out technologies with geological H2 storage for each region without salt cavern availability
    logger.info("Applying salt cavern availability constraint")
    for region in [
        reg
        for reg in regions_salt_cavern_availability
        if regions_salt_cavern_availability[reg] == "no"
    ]:
        filter = (df_technology_switches["region"] == region) & (
            (
                df_technology_switches["technology_destination"].str.contains(
                    "H2 storage - geological"
                )
                | (
                    df_technology_switches["technology_origin"].str.contains(
                        "H2 storage - geological"
                    )
                )
            )
        )

        df_technology_switches = df_technology_switches.loc[~filter]
    logger.info("Applied salt cavern availability constraint")

    return df_technology_switches


def apply_hydro_constraint(
    df_technology_transitions: pd.DataFrame, sector: str, products: list
) -> pd.DataFrame:
    logger.info("Applying hydro constraint")
    if HYDRO_TECHNOLOGY_BAN[sector]:
        # if sector == "aluminium" and "Aluminium" in products:
        logger.debug(f"{sector}: Filtering Hydro banned transitions")
        return df_technology_transitions[
            (
                (
                    df_technology_transitions["technology_destination"].str.contains(
                        "Hydro"
                    )
                )
                & (df_technology_transitions["technology_origin"].str.contains("Hydro"))
            )
            | (
                (
                    df_technology_transitions["technology_destination"].str.contains(
                        "decommission"
                    )
                )
                & (df_technology_transitions["technology_origin"].str.contains("Hydro"))
            )
            | (
                (
                    df_technology_transitions["technology_origin"].str.contains(
                        "New-build"
                    )
                )
                & (
                    df_technology_transitions["technology_destination"].str.contains(
                        "Hydro"
                    )
                )
            )
            | (
                ~(df_technology_transitions["technology_origin"].str.contains("Hydro"))
                & ~(
                    df_technology_transitions["technology_destination"].str.contains(
                        "Hydro"
                    )
                )
            )
        ]
    else:
        logger.debug(f"{sector}: No hydro band transitions")
        return df_technology_transitions


def calculate_carbon_cost_addition_to_cost_metric(
    df_technology_switches: pd.DataFrame,
    df_emissions: pd.DataFrame,
    df_technology_characteristics: pd.DataFrame,
    df_carbon_cost: pd.DataFrame,
    scopes_co2_cost: list,
    cost_metrics: list,
    standard_cuf: float,
    standard_lifetime: float,
    standard_wacc: float,
    grouping_cols_for_npv: list,
    ghgs: list,
) -> pd.DataFrame:
    """Apply the carbon cost to the cost metric for each technology switch across the entire model time horizon.

    Args:
        df_technology_switches: all technology switches along with a value for the cost metric
        df_emissions: emissions data for every technology
        df_technology_characteristics: characteristics for every technology
    Returns:
        pd.DataFrame: all technology switches with the cost metric including the carbon cost component
    Args:
        df_technology_switches (pd.DataFrame): all technology switches for which the carbon cost addition is to be calculated
        df_emissions (pd.DataFrame): emissions data for every technology
        df_technology_characteristics (pd.DataFrame): technology characteristics (lifetime, capacity utilisation factor, WACC)
        df_carbon_cost (pd.DataFrame): cost per ton of CO2 in every year of the model horizon
        scopes_co2_cost (list): include these emission scopes in the application of the carbon cost
        cost_metrics (list): calculate carbon cost addition for these cost metrics (can contain "marginal_cost", "annualized_cost", "lcox", "tco")
        standard_cuf (float): use this standard CUF for calculating the carbon cost addition to LCOX
        standard_lifetime (float): use this standard technology lifetime for calculating the carbon cost addition to TCO and LCOX
        standard_wacc (float): use this standard WACC for calculating the carbon cost addition to LCOX
        grouping_cols_for_npv (list): use these columns to group the technology switches for the NPV calculation

    Returns:
        pd.DataFrame: all technology switches in df_technology_switches along with the carbon cost addition to all cost metrics
    """

    logger.info("Calculating carbon cost addition to cost metric")
    # Drop emission columns with other GHGs than CO2
    for ghg in [ghg for ghg in ghgs if ghg != "co2"]:
        df_emissions = df_emissions.drop(columns=df_emissions.filter(regex=ghg).columns)

    # Merge technology switches, emissions and technology characteristics
    if "technology_classification" in df_technology_switches.columns:
        df_technology_switches = df_technology_switches.drop(
            columns=["technology_classification"]
        )
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
    for scope in scopes_co2_cost:
        df["sum_co2_emissions"] += df[f"co2_{scope}"]
    df["carbon_cost_addition"] = df["sum_co2_emissions"] * df["carbon_cost"]

    # For marginal cost and annualized cost, the carbon cost component corresponds to the carbon cost addition in the same year
    if "marginal_cost" in cost_metrics:
        df["carbon_cost_addition_marginal_cost"] = df["carbon_cost_addition"]

    if "annualized_cost" in cost_metrics:
        df["carbon_cost_addition_annualized_cost"] = df["carbon_cost_addition"]

    # Discount carbon cost addition and replace
    df_discounted = discount_costs(
        df[
            grouping_cols_for_npv
            + ["year", "carbon_cost_addition", "technology_lifetime", "wacc"]
        ],
        grouping_cols_for_npv,
    )

    df = df.set_index(grouping_cols_for_npv + ["year"])
    df["carbon_cost_addition"] = df_discounted["carbon_cost_addition"].fillna(0)

    # Carbon cost component of TCO is net present cost from carbon cost divided by (lifetime * capacity utilisation factor)
    if "tco" in cost_metrics:
        df["carbon_cost_addition_tco"] = (
            df["carbon_cost_addition"] / (df["technology_lifetime"] * standard_cuf)
        ).fillna(0)

    # Carbon cost component of LCOX is net present cost from carbon cost divided by (CUF * total discounted production)
    if "lcox" in cost_metrics:
        value_shares = (1 + standard_wacc) ** np.arange(0, standard_lifetime + 1)
        total_discounted_production = np.sum(1 / value_shares)

        df["carbon_cost_addition_lcox"] = (
            df["carbon_cost_addition"] / (standard_cuf * total_discounted_production)
        ).fillna(0)

    # Return technology switches with carbon cost addition to each cost metric
    logger.info("Carbon cost addition to cost metric calculated")
    return df.reset_index(drop=False).drop(
        columns=[
            "wacc",
            "trl_current",
            "technology_lifetime",
        ]
    )


def add_carbon_cost_addition_to_technology_switches(
    df_technology_switches: pd.DataFrame,
    df_carbon_cost_addition: pd.DataFrame,
    cost_metric: str,
) -> pd.DataFrame:
    """Add the cost metric component from the carbon cost to each cost metric in the technology switching table.

    Args:
        df_technology_switches (pd.DataFrame): contains technology switches along with a cost metric
        df_carbon_cost_addition (pd.DataFrame): contains cost metric component from the carbon cost
        cost_metric (str): the cost metric to which the carbon cost should be added (LCOX, TCO or MC)

    Returns:
        pd.DataFrame: contains technology switches with the cost metric including the carbon cost component
    """

    logger.info("Adding carbon cost addition to cost metric")

    merge_cols = [
        "product",
        "technology_origin",
        "technology_destination",
        "region",
        "switch_type",
        "year",
    ]
    df_carbon_cost = df_technology_switches.merge(
        df_carbon_cost_addition[merge_cols + [f"carbon_cost_addition_{cost_metric}"]],
        on=merge_cols,
        how="left",
    )

    df_carbon_cost[cost_metric] = (
        df_carbon_cost[cost_metric]
        + df_carbon_cost[f"carbon_cost_addition_{cost_metric}"]
    )
    logger.info("Carbon cost addition to cost metric added")

    return df_carbon_cost


def apply_technology_availability_constraint(
    df_technology_switches: pd.DataFrame, df_technology_characteristics: pd.DataFrame
) -> pd.DataFrame:
    """Filter out all technology switches that downgrade the technology classification and to destination technologies that have not reached maturity yet.

    Args:
        df_technology_switches (pd.DataFrame): contains technology switches characterized by "product", "year", "region", "technology_origin" and "technology_destination"
        df_technology_characteristics (pd.DataFrame): _description_

    Returns:
        pd.DataFrame: _description_
    """
    logger.info("Applying technology availability constraint")

    # Add classification of origin and destination technologies to each technology switch
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
    logger.info(
        "Applying constraint 1. No switches from transition or end-state to initial technologies"
    )
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
    logger.info(
        "Applying constraint 2. Transitions to a technology are only possible when it has reached maturity"
    )
    df = df.merge(
        df_technology_characteristics[
            ["product", "year", "region", "technology", "expected_maturity"]
        ].rename({"technology": "technology_destination"}, axis=1),
        on=["product", "year", "region", "technology_destination"],
        how="left",
    ).fillna(START_YEAR)
    df = df.loc[df["year"] >= df["expected_maturity"]]

    logger.info("Technology availability constraint applied")

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
    logger.info("Applying regional technology ban")
    if not sector_bans:
        logger.info("No regional technology ban applied")
        return df_technology_switches
    for region in sector_bans.keys():
        banned_transitions = (df_technology_switches["region"] == region) & (
            df_technology_switches["technology_destination"].isin(sector_bans[region])
        )
        df_technology_switches = df_technology_switches.loc[~banned_transitions]
    logger.info("Regional technology ban applied")
    return df_technology_switches


def apply_technology_moratorium(
    df_technology_switches: pd.DataFrame,
    df_technology_characteristics: pd.DataFrame,
    moratorium_year: int,
    transitional_period_years: int,
) -> pd.DataFrame:
    """Eliminate all newbuild technology switches to a technology of classification "initial" after a specific year

    Args:
        df_technology_switches (pd.DataFrame): contains the possible technology switches
        df_technology_characteristics (pd.DataFrame): contains column "technology_classification" for each technology
        moratorium_year (int): year in which the technology moratorium enters into force
        transitional_period_years (int): period starting in moratorium_year during which switches to technologies of classification "transition" are still allowed

    Returns:
        pd.DataFrame: technology switches without those banned by the moratorium
    """

    # Add technology classification to each destination technology
    df_tech_char_destination = df_technology_characteristics[
        ["product", "year", "region", "technology", "technology_classification"]
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
    df_technology_switches: pd.DataFrame,
    df_emissions: pd.DataFrame,
    emission_scopes: list,
    ghgs: list,
) -> pd.DataFrame:
    """Calculate emission reduction when switching from origin to destination technology by scope.

    Args:
        df_technology_switches (pd.DataFrame): cost data for every technology switch (regional)
        df_emissions (pd.DataFrame): emissions data for every technology

    Returns:
        pd.DataFrame: contains "delta_{}" for every scope and GHG considered
    """
    # Get columns containing emissions and filter emissions table accordingly
    cols = [f"{ghg}_{scope}" for ghg in ghgs for scope in emission_scopes]
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
    for ghg in ghgs:
        for scope in emission_scopes:
            df[f"delta_{ghg}_{scope}"] = df[f"{ghg}_{scope}_origin"].fillna(0) - df[
                f"{ghg}_{scope}_destination"
            ].fillna(0)

    # Drop emissions of destination and origin technology
    # drop_cols = [
    #     f"{ghg}_{scope}_{switch_locator}"
    #     for switch_locator in ["origin", "destination"]
    #     for ghg in GHGS
    #     for scope in EMISSION_SCOPES
    # ]
    # df = df.drop(columns=drop_cols)

    return df


def add_technology_classification_to_switching_table(
    df_technology_switches: pd.DataFrame, df_technology_characteristics: pd.DataFrame
) -> pd.DataFrame:
    """Add column "technology_classification" to the technology switching table.

    Args:
        df_technology_switches (pd.DataFrame): technology switching input table to the solver
        df_technology_characteristics (pd.DataFrame): contains column "technology_classification"

    Returns:
        pd.DataFrame: technology switching table with additional column "technology_classification"
    """
    df_technology_switches = df_technology_switches.merge(
        df_technology_characteristics[
            [
                "product",
                "year",
                "region",
                "technology",
                "technology_classification",
                "technology_lifetime",
                "wacc",
            ]
        ].rename({"technology": "technology_destination"}, axis=1),
        on=["product", "year", "region", "technology_destination"],
        how="left",
    )

    return df_technology_switches

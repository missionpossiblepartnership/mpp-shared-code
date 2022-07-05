""" Apply implicit forcing mechanisms to the input tables: carbon cost, green premium and technology moratorium."""
from datetime import timedelta
from timeit import default_timer as timer

import numpy as np
import pandas as pd

from mppshared.calculate.calculate_cost import discount_costs
from mppshared.config import (
    APPLY_CARBON_COST,
    EMISSION_SCOPES,
    FINAL_CARBON_COST,
    GHGS,
    HYDRO_TECHNOLOGY_BAN,
    INITIAL_CARBON_COST,
    PRODUCTS,
    REGIONAL_TECHNOLOGY_BAN,
    REGIONS_SALT_CAVERN_AVAILABILITY,
    SCOPES_CO2_COST,
    START_YEAR,
    TECHNOLOGY_MORATORIUM,
    TRANSITIONAL_PERIOD_YEARS,
)
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory
from mppshared.solver.input_loading import filter_df_for_development
from mppshared.utility.dataframe_utility import (
    add_column_header_suffix,
    get_grouping_columns_for_npv_calculation,
)
from mppshared.utility.function_timer_utility import timer_func
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)


def apply_implicit_forcing(pathway: str, sensitivity: str, sector: str) -> pd.DataFrame:
    """Apply the implicit forcing mechanisms to the input tables.

    Args:
        pathway:
        sensitivity:
        sector:

    Returns:
        pd.DataFrame: DataFrame ready for ranking the technology switches
    """
    logger.info("Applying implicit forcing")

    # Import input tables
    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS[sector],
    )

    df_technology_switches = importer.get_technology_transitions_and_cost()
    df_emissions = importer.get_emissions()
    df_technology_characteristics = importer.get_technology_characteristics()

    # Apply technology availability constraint
    df_technology_switches = apply_technology_availability_constraint(
        df_technology_switches, df_technology_characteristics
    )

    # Apply regional technology bans
    df_technology_switches = apply_regional_technology_ban(
        df_technology_switches, REGIONAL_TECHNOLOGY_BAN[sector]
    )

    # Eliminate technologies with geological H2 storage in regions without salt caverns
    df_technology_switches = apply_salt_cavern_availability_constraint(
        df_technology_switches, sector
    )

    # Eliminate Hydro technologies from switches not allowed
    df_technology_switches = apply_hydro_constraint(
        df_technology_switches, sector, PRODUCTS[sector]
    )
    # Apply technology moratorium (year after which newbuild capacity must be transition or
    # end-state technologies)
    if pathway not in ["bau", "cc"]:
        df_technology_switches = apply_technology_moratorium(
            df_technology_switches=df_technology_switches,
            df_technology_characteristics=df_technology_characteristics,
            moratorium_year=TECHNOLOGY_MORATORIUM[sector],
            transitional_period_years=TRANSITIONAL_PERIOD_YEARS[sector],
        )
    # Add technology classification
    else:
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

    carbon_cost = 0
    if carbon_cost == 0:
        df_carbon_cost = df_technology_switches.copy()
    else:
        # Add carbon cost to TCO based on scope 1 and 2 CO2 emissions
        # TODO: improve runtime
        start = timer()
        logger.debug("Applying carbon cost")
        # df_technology_switches = filter_df_for_development(df_technology_switches)
        df_technology_switches = df_technology_switches.drop_duplicates()

        cc = CarbonCostTrajectory(
            trajectory="linear",
            initial_carbon_cost=INITIAL_CARBON_COST,
            final_carbon_cost=FINAL_CARBON_COST,
        )
        df_cc = cc.df_carbon_cost
        df_carbon_cost = calculate_carbon_cost_addition_to_cost_metric(
            df_technology_switches=df_technology_switches,
            df_emissions=df_emissions,
            df_technology_characteristics=df_technology_characteristics,
            cost_metric="tco",
            df_carbon_cost=df_cc,
        )
        end = timer()
        logger.info(
            f"Time elapsed to apply carbon cost to {len(df_carbon_cost)} rows: {timedelta(seconds=end-start)}"
        )

    # TODO: add carbon cost to LCOX and other cost metrics

    # TODO: Subtract green premium from eligible technologies

    # Calculate emission deltas between origin and destination technology
    df_ranking = calculate_emission_reduction(df_carbon_cost, df_emissions)
    # if pathway == "cc":
    #     df_ranking = df_ranking.merge(
    #         df_technology_characteristics[
    #             [
    #                 "product",
    #                 "year",
    #                 "region",
    #                 "technology",
    #                 "technology_classification",
    #                 "technology_lifetime",
    #                 "wacc",
    #             ]
    #         ].rename({"technology": "technology_destination"}, axis=1),
    #         on=["product", "year", "region", "technology_destination"],
    #         how="left",
    #     )
    importer.export_data(
        df=df_ranking,
        filename="technologies_to_rank.csv",
        export_dir="intermediate",
        index=False,
    )

    return df_ranking


def apply_salt_cavern_availability_constraint(
    df_technology_transitions: pd.DataFrame, sector: str
) -> pd.DataFrame:
    """Take out technologies with geological H2 storage in regions that do not have salt cavern availability"""
    if sector not in REGIONS_SALT_CAVERN_AVAILABILITY.keys():
        return df_technology_transitions

    salt_cavern_availability = REGIONS_SALT_CAVERN_AVAILABILITY[sector]
    for region in [
        reg for reg in salt_cavern_availability if salt_cavern_availability[reg] == "no"
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


def apply_hydro_constraint(
    df_technology_transitions: pd.DataFrame, sector: str, products: list
) -> pd.DataFrame:
    if HYDRO_TECHNOLOGY_BAN[sector]:
        # if sector == "aluminium" and "Aluminium" in products:
        logger.debug("Filtering Hydro banned transitions")
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
    # TODO: make grouping column function sector-specific
    grouping_cols = get_grouping_columns_for_npv_calculation("chemicals")

    df_discounted = discount_costs(
        df[
            grouping_cols
            + ["year", "carbon_cost_addition", "technology_lifetime", "wacc"]
        ],
        grouping_cols,
    )

    # Add total discounted carbon cost to each technology switch
    df = df.set_index(grouping_cols + ["year"])
    df["carbon_cost_addition"] = df_discounted["carbon_cost_addition"]

    if cost_metric == "tco":
        # Contribution of a cost to TCO is net present cost divided by (lifetime * capacity utilisation factor)
        # TODO: integrate dynamic capacity utilisation functionality
        cuf_dummy = 0.95
        df["carbon_cost_addition_tco"] = (
            df["carbon_cost_addition"] / (df["technology_lifetime"] * cuf_dummy)
        ).fillna(0)

        # Update TCO in technology switching DataFrame
        df_technology_switches = df_technology_switches.set_index(
            grouping_cols + ["year"]
        )
        df_technology_switches["tco"] = df["tco"] + df["carbon_cost_addition_tco"]

    elif cost_metric == "lcox":
        # Contribution of a cost to LCOX is net present cost divided by (CUF * total discounted production)
        # TODO: ensure that sector-specific
        cuf = 0.95
        rate = df_technology_characteristics["wacc"].unique()[0]
        lifetime = df_technology_characteristics["technology_lifetime"].unique()[0]
        value_shares = (1 + rate) ** np.arange(0, lifetime + 1)
        total_discounted_production = np.sum(1 / value_shares)

        df["carbon_cost_addition_lcox"] = (
            df["carbon_cost_addition"] / (cuf * total_discounted_production)
        ).fillna(0)

    # Return technology switch DataFrame with carbon cost addition
    # TODO: improve this workaround
    return df.reset_index(drop=False).drop(
        columns=[
            "technology_classification_x",
            "technology_classification_y",
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

    return df_carbon_cost


# def apply_carbon_cost_to_tco(
#     df_technology_switches: pd.DataFrame,
#     df_emissions: pd.DataFrame,
#     df_technology_characteristics: pd.DataFrame,
# ) -> pd.DataFrame:
#     """

#     Args:
#         df_technology_switches: cost data for every technology switch (regional)
#         df_emissions: emissions data for every technology (regional)
#         df_technology_characteristics: characteristics for every technology

#     Returns:
#         pd.DataFrame: merge of the input DataFrames with additional column "carbon_cost_addition" added to TCO
#     """
#     # Drop emission columns with other GHGs
#     for ghg in [ghg for ghg in GHGS if ghg != "co2"]:
#         df_emissions = df_emissions.drop(df_emissions.filter(regex=ghg).columns)

#     # Merge technology switches, emissions and technology characteristics
#     logger.debug("Merging switches with emissions")
#     df = df_technology_switches.merge(
#         df_emissions.rename(columns={"technology": "technology_destination"}),
#         on=["product", "region", "year", "technology_destination"],
#         how="left",
#     ).fillna(0)
#     logger.debug("Merging switches with characteristics")
#     df = df.merge(
#         df_technology_characteristics.rename(
#             columns={"technology": "technology_destination"}
#         ),
#         on=["product", "region", "technology_destination"],
#         how="left",
#     ).fillna(0)

#     # Additional cost from carbon cost is carbon cost multiplied with sum of scope 1 and scope 2 CO2 emissions
#     logger.debug("Creating Carbon Cost trajectory")
#     cc = CarbonCostTrajectory(
#         trajectory="linear",
#         initial_carbon_cost=INITIAL_CARBON_COST,
#         final_carbon_cost=FINAL_CARBON_COST,
#     )
#     cc.df_carbon_cost.to_csv("debug/carbon_cost.csv")
#     # df = df_technology_switches.copy()
#     df_cc = df.rename(columns={"year_x": "year"}).merge(cc.df_carbon_cost, on=["year"])
#     df_cc = df_cc.drop_duplicates()
#     logger.debug("Calculating carbon cost addition")
#     df_cc["carbon_cost_addition"] = (df_cc["co2_scope1"] + df_cc["co2_scope2"]) * df_cc[
#         "carbon_cost"
#     ]

#     # Discount carbon cost addition
#     # TODO: make grouping column function sector-specific
#     logger.debug("Getting grouping columns")
#     grouping_cols = get_grouping_columns_for_npv_calculation("chemicals")
#     logger.debug("Calculating discount costs")
#     df_discounted = discount_costs(
#         df_cc[
#             grouping_cols
#             + ["year", "carbon_cost_addition", "technology_lifetime", "wacc"]
#         ],
#         grouping_cols,
#     )
#     df_discounted = df_discounted.drop_duplicates()
#     df = df_cc.copy()

#     df_discounted.to_csv("debug/df_discounted.csv")
#     # Add total discounted carbon cost to each technology switch
#     logger.debug("Add total discounted carbon cost to technology switches")
#     df = df_cc.set_index(grouping_cols + ["year"])
#     df.to_csv("debug/df_withouth_cost_addition.csv")
#     df["carbon_cost_addition"] = df_discounted["carbon_cost_addition"]
#     # df = df.reset_index(drop=False).merge(
#     #     df_discounted.reset_index(drop=False),
#     #     on=[
#     #         "product",
#     #         "technology_origin",
#     #         "region",
#     #         "switch_type",
#     #         "technology_destination",
#     #         "year",
#     #     ],
#     # )
#     df.to_csv("debug/df_with_cost_addition.csv")

#     # Contribution of a cost to TCO is net present cost divided by (lifetime * capacity utilisation factor)
#     # TODO: integrate dynamic capacity utilisation functionality
#     cuf_dummy = 0.95
#     # df["carbon_cost_addition_tco"] = (
#     #     df["carbon_cost_addition"] / (df["technology_lifetime"] * cuf_dummy)
#     # ).fillna(0)

#     df["original_tco"] = df["tco"]
#     logger.debug("Calculating new TCO")
#     df["tco"] = df["tco"] + df["carbon_cost_addition"]
#     df.to_csv("debug/df_with_cost_addition.csv")
#     # Update TCO in technology switching DataFrame
#     # df_technology_switches = df_technology_switches.set_index(grouping_cols + ["year"])
#     # df_technology_switches["tco"] = df["tco"] + df["carbon_cost_addition_tco"]

#     # Return technology switch DataFrame with updated TCO
#     # return df_technology_switches.reset_index(drop=False)
#     return df


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
    """Eliminate all newbuild transitions to a conventional technology after a specific year

    Args:
        df_technology_switches (pd.DataFrame): df_technology_switches
        df_technology_characteristics (pd.DataFrame): df_technology_characteristics
        moratorium_year (int): Year from which the technology moratorium kicks in
        transitional_period_years (int): Period during transition to transition technologies is allowed

    Returns:
        pd.DataFrame:
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
        pd.DataFrame: _description_
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

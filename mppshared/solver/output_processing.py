""" Process outputs to standardised output table."""
from collections import defaultdict
from lib2to3.pgen2.pgen import DFAState
from re import T
from tkinter import END
import pandas as pd
import numpy as np

from mppshared.config import *
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.solver.debugging_outputs import create_table_asset_transition_sequences
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def _calculate_number_of_assets(df_stack: pd.DataFrame) -> pd.DataFrame:
    """Calculate number of assets by product, region and technology for a given asset stack"""

    logger.info("-- Calculating number of assets")

    # Count number of assets
    df_stack["asset"] = 1
    df_stack = (
        df_stack.groupby(["product", "region", "technology"])
        .count()["asset"]
        .reset_index()
    )

    # Add parameter descriptions
    df_stack.rename(columns={"asset": "value"}, inplace=True)
    df_stack["parameter_group"] = "Production"
    df_stack["parameter"] = "Number of plants"
    df_stack["unit"] = "plant"

    return df_stack


def _calculate_production_volume(df_stack: pd.DataFrame) -> pd.DataFrame:
    """Calculate annual production volume by product, region and technology for a given asset stack"""

    logger.info("-- Calculating production volume")

    # Sum the annual production volume
    df_stack = (
        df_stack.groupby(["product", "region", "technology"])
        .sum()["annual_production_volume"]
        .reset_index()
    )

    # Add parameter descriptions
    df_stack.rename(columns={"annual_production_volume": "value"}, inplace=True)

    df_stack["parameter_group"] = "Production"
    df_stack["parameter"] = "Annual production volume"
    df_stack["unit"] = "Mt"

    return df_stack


def _calculate_emissions(
    df_stack: pd.DataFrame,
    df_emissions: pd.DataFrame,
    agg_vars=["product", "region", "technology"],
) -> pd.DataFrame:
    """Calculate emissions for all GHGs and scopes by production, region and technology"""

    logger.info("-- Calculating emissions")

    # Emissions are the emissions factor multiplied with the annual production volume
    df_stack = df_stack.merge(df_emissions, on=["product", "region", "technology"])
    scopes = [f"{ghg}_{scope}" for scope in EMISSION_SCOPES for ghg in GHGS]

    for scope in scopes:
        df_stack[scope] = df_stack[scope] * df_stack["annual_production_volume"]

    df_stack = (
        df_stack.groupby(agg_vars)[scopes + ["annual_production_volume"]]
        .sum()
        .reset_index()
    )

    df_stack = df_stack.melt(
        id_vars=agg_vars,
        value_vars=scopes,
        var_name="parameter",
        value_name="value",
    )

    # Add unit and parameter group
    map_unit = {
        f"{ghg}_{scope}": f"Mt {str.upper(ghg)}"
        for scope in EMISSION_SCOPES
        for ghg in GHGS
    }
    map_rename = {
        f"{ghg}_{scope}": f"{str.upper(ghg)} {str.capitalize(scope).replace('_', ' ')}"
        for scope in EMISSION_SCOPES
        for ghg in GHGS
    }

    df_stack["parameter_group"] = "Emissions"
    df_stack["unit"] = df_stack["parameter"].apply(lambda x: map_unit[x])
    df_stack["parameter"] = df_stack["parameter"].replace(map_rename)
    if "technology" not in agg_vars:
        df_stack["technology"] = "All"

    return df_stack


def _calculate_co2_captured(
    df_stack: pd.DataFrame,
    df_emissions: pd.DataFrame,
    agg_vars=["product", "region", "technology"],
) -> pd.DataFrame:
    """Calculate captured CO2 by product, region and technology for a given asset stack"""

    logger.info("-- Calculating CO2 captured")

    # Captured CO2 by technology is calculated by multiplying with the annual production volume
    df_stack = df_stack.merge(df_emissions, on=["product", "region", "technology"])
    df_stack["co2_scope1_captured"] = (
        df_stack["co2_scope1_captured"] * df_stack["annual_production_volume"]
    )

    df_stack = df_stack.groupby(agg_vars)["co2_scope1_captured"].sum().reset_index()

    # Melt and add parameter descriptions
    df_stack = df_stack.melt(
        id_vars=agg_vars,
        value_vars="co2_scope1_captured",
        var_name="parameter",
        value_name="value",
    )
    df_stack["parameter_group"] = "Emissions"
    df_stack["parameter"] = "CO2 Scope1 captured"
    df_stack["unit"] = "Mt CO2"

    if "technology" not in agg_vars:
        df_stack["technology"] = "All"

    return df_stack


def _calculate_emissions_intensity(
    df_stack: pd.DataFrame,
    df_emissions: pd.DataFrame,
    agg_vars=["product", "region", "technology"],
) -> pd.DataFrame:
    """Calculate emissions intensity for a given stack (can also be aggregated by technology by omitting this variable in agg_vars)"""

    logger.info("-- Calculating emissions intensity")

    # Emission scopes
    scopes = [f"{ghg}_{scope}" for scope in EMISSION_SCOPES for ghg in GHGS]

    # If differentiated by technology, emissions intensity is identical to the emission factors calculated previously (even if zero production)
    if agg_vars == ["product", "region", "technology"]:
        for scope in scopes:
            df_stack = df_emissions.rename(
                {scope: f"emissions_intensity_{scope}" for scope in scopes}, axis=1
            ).copy()

    # Otherwise, Emissions are the emissions factor multiplied with the annual production volume
    else:
        df_stack = df_stack.merge(df_emissions, on=["product", "region", "technology"])
        for scope in scopes:
            df_stack[scope] = df_stack[scope] * df_stack["annual_production_volume"]

        df_stack = (
            df_stack.groupby(agg_vars)[scopes + ["annual_production_volume"]]
            .sum()
            .reset_index()
        )

        # Emissions intensity is the emissions divided by annual production volume
        for scope in scopes:
            df_stack[f"emissions_intensity_{scope}"] = (
                df_stack[scope] / df_stack["annual_production_volume"]
            )

    df_stack = df_stack.melt(
        id_vars=agg_vars,
        value_vars=[f"emissions_intensity_{scope}" for scope in scopes],
        var_name="parameter",
        value_name="value",
    )

    # Add unit and parameter group
    map_unit = {
        f"emissions_intensity_{ghg}_{scope}": f"t{str.upper(ghg)}/t"
        for scope in EMISSION_SCOPES
        for ghg in GHGS
    }
    map_rename = {
        f"emissions_intensity_{ghg}_{scope}": f"Emissions intensity {str.upper(ghg)} {str.capitalize(scope).replace('_', ' ')}"
        for scope in EMISSION_SCOPES
        for ghg in GHGS
    }

    df_stack["parameter_group"] = "Emissions intensity"
    df_stack["unit"] = df_stack["parameter"].apply(lambda x: map_unit[x])
    df_stack["parameter"] = df_stack["parameter"].replace(map_rename)
    if "technology" not in agg_vars:
        df_stack["technology"] = "All"

    return df_stack


def _calculate_resource_consumption(
    df_stack: pd.DataFrame,
    df_inputs_outputs: pd.DataFrame,
    resource: str,
    year: int,
    agg_vars=["product", "region", "technology"],
) -> pd.DataFrame:
    """Calculate the consumption of a given resource in a given year, optionally grouped by specific variables."""

    logger.info(f"-- Calculating consumption of {resource}")

    # Get inputs of that resource required for each technology in GJ/t
    df_variable = df_inputs_outputs.loc[
        (df_inputs_outputs["parameter"] == resource)
        & (df_inputs_outputs["year"] == year)
    ].copy()

    df_stack = df_stack.merge(df_variable, on=["product", "region", "technology"])

    # Calculate resource consumption in GJ by multiplying the input with the annual production volume of that technology
    df_stack["value"] = df_stack["value"] * df_stack["annual_production_volume"]
    df_stack = (
        df_stack.groupby(agg_vars + ["parameter_group", "parameter"])["value"].sum()
    ).reset_index()

    # Add unit
    unit_map = {"Energy": "GJ", "Raw material": "GJ", "H2 storage": "GJ", "Cost": "USD"}
    df_stack["unit"] = df_stack["parameter_group"].apply(lambda x: unit_map[x])

    if "technology" not in agg_vars:
        df_stack["technology"] = "All"

    return df_stack


def create_table_all_data_year(
    year: int, importer: IntermediateDataImporter
) -> pd.DataFrame:
    """Create DataFrame with all outputs for a given year."""

    # Calculate asset numbers and production volumes for the stack in that year
    df_stack = importer.get_asset_stack(year)
    df_total_assets = _calculate_number_of_assets(df_stack)
    df_production_capacity = _calculate_production_volume(df_stack)

    # Calculate emissions, CO2 captured and emissions intensity
    df_emissions = importer.get_emissions()
    df_emissions = df_emissions[df_emissions["year"] == year]
    df_stack_emissions = _calculate_emissions(df_stack, df_emissions)
    df_emissions_intensity = _calculate_emissions_intensity(df_stack, df_emissions)
    df_emissions_intensity_all_tech = _calculate_emissions_intensity(
        df_stack, df_emissions, agg_vars=["product", "region"]
    )
    df_co2_captured = _calculate_co2_captured(df_stack, df_emissions)

    # Calculate feedstock and energy consumption
    df_inputs_outputs = importer.get_inputs_outputs()
    data_variables = []

    for resource in df_inputs_outputs["parameter"].unique():
        df_stack_variable = _calculate_resource_consumption(
            df_stack,
            df_inputs_outputs,
            resource,
            year,
            agg_vars=["product", "region", "technology"],
        )
        df_stack_variable["parameter"] = resource
        data_variables.append(df_stack_variable)

    df_inputs = pd.concat(data_variables)

    # Concatenate all the output tables
    df_all_data_year = pd.concat(
        [
            df_total_assets,
            df_production_capacity,
            df_stack_emissions,
            df_emissions_intensity,
            df_emissions_intensity_all_tech,
            df_co2_captured,
            df_inputs,
        ]
    )
    return df_all_data_year


def _calculate_annual_investments(
    df_cost: pd.DataFrame,
    importer: IntermediateDataImporter,
    sector: str,
    agg_vars=["product", "region", "switch_type", "technology_destination"],
) -> pd.DataFrame:
    """Calculate annual investments."""

    # Calculate invesment in newbuild, brownfield retrofit and brownfield rebuild technologies in every year
    switch_types = ["greenfield", "rebuild", "retrofit"]
    df_investment = pd.DataFrame()

    for year in np.arange(START_YEAR + 1, END_YEAR + 1):

        # Get current and previous stack
        drop_cols = ["annual_production_volume", "cuf", "asset_lifetime"]
        current_stack = (
            importer.get_asset_stack(year)
            .drop(columns=drop_cols)
            .rename(
                {
                    "technology": "technology_destination",
                    "annual_production_capacity": "annual_production_capacity_destination",
                },
                axis=1,
            )
        )
        previous_stack = (
            importer.get_asset_stack(year - 1)
            .drop(columns=drop_cols)
            .rename(
                {
                    "technology": "technology_origin",
                    "annual_production_capacity": "annual_production_capacity_origin",
                },
                axis=1,
            )
        )

        # Merge to compare retrofit, rebuild and greenfield status
        previous_stack = previous_stack.rename(
            {
                f"{switch_type}_status": f"previous_{switch_type}_status"
                for switch_type in switch_types
            },
            axis=1,
        )
        df = current_stack.merge(
            previous_stack.drop(columns=["product", "region"]), on="uuid", how="left"
        )

        # Identify newly built assets
        df.loc[
            (df["greenfield_status"] == True)
            & (df["previous_greenfield_status"].isna()),
            ["switch_type", "technology_origin"],
        ] = ["greenfield", "New-build"]

        # Identify retrofit assets
        df.loc[
            (df["retrofit_status"] == True) & (df["previous_retrofit_status"] == False),
            "switch_type",
        ] = "brownfield_renovation"

        # Identify rebuild assets
        df.loc[
            (df["rebuild_status"] == True) & (df["previous_rebuild_status"] == False),
            "switch_type",
        ] = "brownfield_newbuild"

        # Drop all assets that haven't undergone a transition
        df = df.loc[df["switch_type"].notna()]
        df["year"] = year

        # Add the corresponding switching CAPEX to every asset that has changed
        df = df.merge(
            df_cost,
            on=[
                "product",
                "region",
                "year",
                "technology_origin",
                "technology_destination",
                "switch_type",
            ],
            how="left",
        )

        # Calculate investment cost per changed asset by multiplying CAPEX (in USD/tpa) with production capacity (in Mtpa) and sum
        df["investment"] = (
            df["switch_capex"] * df["annual_production_capacity_destination"] * 1e6
        )
        df = df.groupby(agg_vars)[["investment"]].sum().reset_index(drop=False)

        df = df.melt(
            id_vars=agg_vars,
            value_vars="investment",
            var_name="parameter",
            value_name="value",
        )

        df["year"] = year

        df_investment = pd.concat([df_investment, df])

    for variable in ["product", "region", "switch_type", "technology_destination"]:
        if variable not in agg_vars:
            df_investment[variable] = "All"

    if "switch_type" in agg_vars:
        map_parameter_group = {
            "brownfield_renovation": "Brownfield renovation investment",
            "brownfield_newbuild": "Brownfield rebuild investment",
            "greenfield": "Greenfield investment",
        }
        df_investment["parameter"] = df_investment["switch_type"].apply(
            lambda x: map_parameter_group[x]
        )
    else:
        df_investment[
            "parameter"
        ] = "Greenfield, brownfield renovation and brownfield rebuild investment"

    df_investment["parameter_group"] = "Investment"
    df_investment["unit"] = "USD"
    df_investment["sector"] = sector

    df_investment = df_investment.rename(
        columns={"technology_destination": "technology"}
    )
    df_pivot = df_investment.pivot_table(
        index=[
            "sector",
            "product",
            "region",
            "technology",
            "parameter_group",
            "parameter",
            "unit",
        ],
        columns="year",
        values="value",
    ).fillna(0)

    return df_pivot


def calculate_weighted_average_lcox(
    df_cost: pd.DataFrame,
    importer: IntermediateDataImporter,
    sector: str,
    agg_vars=["product", "region", "technology"],
) -> pd.DataFrame:
    """Calculate weighted average of LCOX across the supply mix in a given year."""

    # If granularity on technology level, simply take LCOX from cost DataFrame
    if agg_vars == ["product", "region", "technology"]:
        df = df_cost.rename(
            {"lcox": "value", "technology_destination": "technology"}, axis=1
        ).copy()
        df = df.loc[df["technology_origin"] == "New-build"]

    else:
        df = pd.DataFrame()
        # In every year, get LCOX of the asset based on the year it was commissioned and average according to desired aggregation
        for year in np.arange(START_YEAR, END_YEAR + 1):
            df_stack = importer.get_asset_stack(year)
            df_stack = df_stack.rename(columns={"year_commissioned": "year"})

            # Assume that assets built before start of model time horizon have LCOX of start year
            df_stack.loc[df_stack["year"] < START_YEAR, "year"] = START_YEAR

            # Add LCOX to each asset
            df_cost = df_cost.loc[df_cost["technology_origin"] == "New-build"]
            df_cost = df_cost.rename(columns={"technology_destination": "technology"})
            df_stack = df_stack.merge(
                df_cost, on=["product", "region", "technology", "year"], how="left"
            )

            # Calculate weighted average according to desired aggregation
            df_stack = (
                df_stack.groupby(agg_vars).apply(
                    lambda x: np.average(
                        x["lcox"], weights=x["annual_production_volume"]
                    )
                )
            ).reset_index(drop=False)

            df_stack = df_stack.melt(
                id_vars=agg_vars,
                value_vars="lcox",
                var_name="parameter",
                value_name="value",
            )
            df_stack["year"] = year

            df = pd.concat([df, df_stack])

    # Transform to output table format
    df["parameter_group"] = "Cost"
    df["parameter"] = "LCOX"
    df["unit"] = "USD/t"
    df["sector"] = sector

    for variable in [
        agg_var
        for agg_var in ["product", "region", "technology"]
        if agg_var not in agg_vars
    ]:
        df[variable] = "All"

    df = df.pivot_table(
        index=[
            "sector",
            "product",
            "region",
            "technology",
            "parameter_group",
            "parameter",
            "unit",
        ],
        columns="year",
        values="value",
    ).fillna(0)

    return df


def calculate_electrolysis_capacity(
    importer: IntermediateDataImporter,
    sector: str,
    agg_vars=["product", "region", "technology"],
) -> pd.DataFrame:
    """Calculate electrolysis capacity in every year."""

    df_stack = pd.DataFrame()

    # Get annual production volume by technology in every year
    for year in np.arange(START_YEAR, END_YEAR + 1):
        stack = importer.get_asset_stack(year)
        stack["year"] = year
        df_stack = pd.concat([df_stack, stack])

    # Filter for electrolysis technologies and group
    df_stack = df_stack.loc[df_stack["technology"].str.contains("Electrolyser")]
    df_stack = (
        df_stack.groupby(["product", "region", "technology", "year"])[
            "annual_production_volume"
        ]
        .sum()
        .reset_index(drop=False)
    )

    # Add capacity factors, efficiencies and hydrogen proportions
    electrolyser_cfs = importer.get_electrolyser_cfs().rename(
        columns={"technology_destination": "technology"}
    )
    electrolyser_effs = importer.get_electrolyser_efficiencies().rename(
        columns={"technology_destination": "technology"}
    )
    electrolyser_props = importer.get_electrolyser_proportions().rename(
        columns={"technology_destination": "technology"}
    )

    merge_vars1 = ["product", "region", "technology", "year"]
    merge_vars2 = ["product", "region", "year"]
    df_stack = df_stack.merge(
        electrolyser_cfs[merge_vars1 + ["electrolyser_capacity_factor"]],
        on=merge_vars1,
        how="left",
    )
    df_stack = df_stack.merge(
        electrolyser_effs[merge_vars2 + ["electrolyser_efficiency"]],
        on=merge_vars2,
        how="left",
    )
    df_stack = df_stack.merge(
        electrolyser_props[merge_vars2 + ["electrolyser_hydrogen_proportion"]],
        on=merge_vars2,
        how="left",
    )
    # Electrolysis capacity = Ammonia production * Proportion of H2 produced via electrolysis * Ratio of ammonia to H2 * Electrolyser efficiency / (365 * 24 * CUF)
    df_stack["electrolysis_capacity"] = (
        df_stack["annual_production_volume"]
        * df_stack["electrolyser_hydrogen_proportion"]
        * df_stack["electrolyser_efficiency"]
        / (365 * 24 * df_stack["electrolyser_capacity_factor"])
    )

    def choose_ratio(row: pd.Series) -> float:
        if row["product"] == "Ammonia":
            ratio = H2_PER_AMMONIA
        elif row["product"] == "Urea":
            ratio = H2_PER_AMMONIA * AMMONIA_PER_UREA
        elif row["product"] == "Ammonium nitrate":
            ratio = H2_PER_AMMONIA * AMMONIA_PER_AMMONIUM_NITRATE
        return ratio

    df_stack["electrolysis_capacity"] = df_stack.apply(
        lambda row: row["electrolysis_capacity"] * choose_ratio(row), axis=1
    )

    df = (
        df_stack.groupby(agg_vars + ["year"])[["electrolysis_capacity"]]
        .sum()
        .reset_index(drop=False)
    )

    # Transform to output table format
    df["parameter_group"] = "Capacity"
    df["parameter"] = "Electrolysis capacity"
    df["unit"] = "GW"
    df["sector"] = sector
    df = df.rename(columns={"electrolysis_capacity": "value"})
    df["year"] = df["year"].astype(int)

    for variable in [
        agg_var
        for agg_var in ["product", "region", "technology"]
        if agg_var not in agg_vars
    ]:
        df[variable] = "All"

    df = df.pivot_table(
        index=[
            "sector",
            "product",
            "region",
            "technology",
            "parameter_group",
            "parameter",
            "unit",
        ],
        columns="year",
        values="value",
    ).fillna(0)

    return df


def calculate_outputs(pathway: str, sensitivity: str, sector: str):
    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS[sector],
    )

    # Write key assumptions to txt file
    write_key_assumptions_to_txt(pathway=pathway, sector=sector, importer=importer)

    # Create summary table of asset transitions
    logger.info("Creating table with asset transition sequences.")
    df_transitions = create_table_asset_transition_sequences(importer)
    importer.export_data(
        df_transitions,
        f"asset_transition_sequences_sensitivity_{sensitivity}.csv",
        "final",
    )

    # Calculate electrolysis capacity
    df_electrolysis_capacity = calculate_electrolysis_capacity(
        importer=importer, sector=sector, agg_vars=["product", "region", "technology"]
    )

    df_electrolysis_capacity_all_tech = calculate_electrolysis_capacity(
        importer=importer, sector=sector, agg_vars=["product", "region"]
    )

    df_electrolysis_capacity_all_tech_all_regions = calculate_electrolysis_capacity(
        importer=importer, sector=sector, agg_vars=["product"]
    )

    df_electrolysis_capacity_all_regions = calculate_electrolysis_capacity(
        importer=importer, sector=sector, agg_vars=["product", "technology"]
    )

    # Calculate weighted average of LCOX
    df_cost = importer.get_technology_transitions_and_cost()
    df_lcox = calculate_weighted_average_lcox(
        df_cost=df_cost,
        importer=importer,
        sector=sector,
        agg_vars=["product", "region", "technology"],
    )
    df_lcox_all_techs = calculate_weighted_average_lcox(
        df_cost=df_cost,
        importer=importer,
        sector=sector,
        agg_vars=["product", "region"],
    )
    df_lcox_all_regions = calculate_weighted_average_lcox(
        df_cost=df_cost,
        importer=importer,
        sector=sector,
        agg_vars=["product"],
    )

    # Calculate annual investments
    df_annual_investments = _calculate_annual_investments(
        df_cost=df_cost,
        importer=importer,
        sector=sector,
        agg_vars=["product", "region", "switch_type", "technology_destination"],
    )
    df_annual_investments_all_tech = _calculate_annual_investments(
        df_cost=df_cost,
        importer=importer,
        sector=sector,
        agg_vars=["product", "region", "switch_type"],
    )
    df_annual_investments_all_switch_types = _calculate_annual_investments(
        df_cost=df_cost,
        importer=importer,
        sector=sector,
        agg_vars=["product", "region", "technology_destination"],
    )
    df_annual_investments_all_tech_all_switch_types = _calculate_annual_investments(
        df_cost=df_cost,
        importer=importer,
        sector=sector,
        agg_vars=["product", "region"],
    )

    # Create output table for every year and concatenate
    data = []
    data_stacks = []

    for year in range(START_YEAR, END_YEAR + 1):
        logger.info(f"Processing year {year}")
        yearly = create_table_all_data_year(year, importer)
        yearly["year"] = year
        data.append(yearly)
        df_stack = importer.get_asset_stack(year)
        df_stack["year"] = year
        data_stacks.append(df_stack)

    df_stacks = pd.concat(data_stacks)
    df = pd.concat(data)
    df["sector"] = sector

    # Pivot the dataframe to have the years as columns
    df_pivot = df.pivot_table(
        index=[
            "sector",
            "product",
            "region",
            "technology",
            "parameter_group",
            "parameter",
            "unit",
        ],
        columns="year",
        values="value",
    )

    # Export as required
    df_pivot = pd.concat(
        [
            df_pivot,
            df_annual_investments,
            df_annual_investments_all_tech,
            df_annual_investments_all_tech_all_switch_types,
            df_annual_investments_all_switch_types,
            df_lcox,
            df_lcox_all_techs,
            df_lcox_all_regions,
            df_electrolysis_capacity,
        ]
    )
    df_pivot.reset_index(inplace=True)
    df_pivot.fillna(0, inplace=True)

    suffix = f"{sector}_{pathway}_{sensitivity}"

    importer.export_data(
        df_pivot, f"simulation_outputs_{suffix}.csv", "final", index=False
    )
    df_pivot.to_csv(
        f"{OUTPUT_WRITE_PATH[sector]}/simulation_outputs_{suffix}.csv", index=False
    )

    columns = [
        "sector",
        "product",
        "region",
        "technology",
        "year",
        "parameter_group",
        "parameter",
        "unit",
        "value",
    ]
    importer.export_data(
        df[columns], f"interface_outputs_{suffix}.csv", "final", index=False
    )
    importer.export_data(
        df_stacks, f"plant_stack_transition_{suffix}.csv", "final", index=False
    )
    logger.info("All data for all years processed.")


def write_key_assumptions_to_txt(
    pathway: str, sector: str, importer: IntermediateDataImporter
):
    """Write important assumptions in the configuration file to a txt file"""
    type = "greenfield"
    lines = [
        f"Investment cycle: {INVESTMENT_CYCLES[sector]} years",
        f"CUF: maximum={CUF_UPPER_THRESHOLD}, minimum={CUF_LOWER_THRESHOLD}, cost metric={COST_METRIC_CUF_ADJUSTMENT[sector]}",
        f"Weights: {RANKING_CONFIG[type][pathway]}",
        f"Technology ramp-up: {TECHNOLOGY_RAMP_UP_CONSTRAINTS[sector]}",
        f"Year 2050 emissions constraint: {YEAR_2050_EMISSIONS_CONSTRAINT[sector]}",
        f"Annual renovation share: {ANNUAL_RENOVATION_SHARE[sector]}",
        f"Regional production shares: {REGIONAL_PRODUCTION_SHARES[sector]}"
        f"Technology moratorium year: {TECHNOLOGY_MORATORIUM[sector]}",
        f"Transitional period years: {TRANSITIONAL_PERIOD_YEARS[sector]}",
    ]

    path = importer.final_path.joinpath("configuration.txt")
    with open(path, "w") as f:
        for line in lines:
            f.write(line)
            f.write("\n")

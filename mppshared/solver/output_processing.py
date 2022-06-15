""" Process outputs to standardised output table."""
from collections import defaultdict
import pandas as pd
import numpy as np

from mppshared.config import *
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory
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
    emission_scopes = [
        scope for scope in EMISSION_SCOPES if scope is not "scope3_downstream"
    ]
    # Emissions are the emissions factor multiplied with the annual production volume
    df_stack = df_stack.merge(df_emissions, on=["product", "region", "technology"])
    scopes = [f"{ghg}_{scope}" for scope in emission_scopes for ghg in GHGS]

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
        for scope in emission_scopes
        for ghg in GHGS
    }
    map_rename = {
        f"{ghg}_{scope}": f"{str.upper(ghg)} {str.capitalize(scope).replace('_', ' ')}"
        for scope in emission_scopes
        for ghg in GHGS
    }

    df_stack["parameter_group"] = "Emissions"
    df_stack["unit"] = df_stack["parameter"].apply(lambda x: map_unit[x])
    df_stack["parameter"] = df_stack["parameter"].replace(map_rename)
    if "technology" not in agg_vars:
        df_stack["technology"] = "All"

    return df_stack


def _calculate_emissions_co2e(
    df_stack: pd.DataFrame,
    df_emissions: pd.DataFrame,
    gwp="GWP-100",
    agg_vars=["product", "region", "technology"],
):
    """Calculate GHG emissions in CO2e according to specified GWP (GWP-20 or GWP-100)."""

    logger.info("-- Calculating emissions in CO2e")

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

    for scope in EMISSION_SCOPES:
        df_stack[f"CO2e {str.capitalize(scope).replace('_', ' ')}"] = 0
        for ghg in GHGS:
            df_stack[f"CO2e {str.capitalize(scope).replace('_', ' ')}"] += (
                df_stack[f"{ghg}_{scope}"] * GWP[gwp][ghg]
            )

    df_stack = df_stack.melt(
        id_vars=agg_vars,
        value_vars=[
            f"CO2e {str.capitalize(scope).replace('_', ' ')}"
            for scope in EMISSION_SCOPES
        ],
        var_name="parameter",
        value_name="value",
    )

    df_stack["parameter_group"] = "Emissions"
    df_stack["unit"] = "Mt CO2e"
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
    unit_map = {
        "Energy": "PJ",
        "Raw material": "PJ",
        "H2 storage": "PJ",
        "Cost": "USD",
    }  # GJ/t * Mt = 10^9 * 10^6 J = 10^15 J = PJ
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
    df_stack_emissions_co2e = _calculate_emissions_co2e(
        df_stack, df_emissions, gwp="GWP-100"
    )
    df_stack_emissions_co2e_all_tech = _calculate_emissions_co2e(
        df_stack, df_emissions, gwp="GWP-100", agg_vars=["product", "region"]
    )
    df_emissions_intensity = _calculate_emissions_intensity(df_stack, df_emissions)
    df_emissions_intensity_all_tech = _calculate_emissions_intensity(
        df_stack, df_emissions, agg_vars=["product", "region"]
    )
    df_co2_captured = _calculate_co2_captured(df_stack, df_emissions)

    # Calculate feedstock and energy consumption
    df_inputs_outputs = importer.get_inputs_outputs()
    data_variables = []

    resources = [
        resource
        for resource in df_inputs_outputs["parameter"].unique()
        if resource
        not in ["Variable OPEX", "Fixed OPEX", "Total OPEX", "Greenfield CAPEX"]
    ]
    for resource in resources:
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
            df_stack_emissions_co2e,
            df_stack_emissions_co2e_all_tech,
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


def _calculate_plant_numbers_by_type(
    importer: IntermediateDataImporter,
    sector: str,
    agg_vars=["product", "region", "switch_type", "technology_destination"],
) -> pd.DataFrame:
    """Calculate annual investments."""

    # Calculate invesment in newbuild, brownfield retrofit and brownfield rebuild technologies in every year
    switch_types = ["greenfield", "rebuild", "retrofit"]
    df_plants = pd.DataFrame()

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

        # All assets that haven't undergone a transition are "unchanged"
        df.loc[df["switch_type"].isna(), "switch_type"] = "unchanged"
        df["year"] = year

        # Calculate number of plants per switch type for the aggregation variables
        df["plant_number"] = 1
        df = df.groupby(agg_vars)[["plant_number"]].sum().reset_index(drop=False)

        df = df.melt(
            id_vars=agg_vars,
            value_vars="plant_number",
            var_name="parameter",
            value_name="value",
        )

        df["year"] = year

        df_plants = pd.concat([df_plants, df])

    for variable in ["product", "region", "switch_type", "technology_destination"]:
        if variable not in agg_vars:
            df_plants[variable] = "All"

    map_parameter_group = {
        "brownfield_renovation": "Brownfield renovation plants",
        "brownfield_newbuild": "Brownfield rebuild plants",
        "greenfield": "Greenfield plants",
        "unchanged": "Unchanged plants",
    }
    df_plants["parameter"] = df_plants["switch_type"].apply(
        lambda x: map_parameter_group[x]
    )

    df_plants["parameter_group"] = "Production"
    df_plants["unit"] = "Number of plants"
    df_plants["sector"] = sector

    df_plants = df_plants.rename(columns={"technology_destination": "technology"})
    df_pivot = df_plants.pivot_table(
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


def calculate_weighted_average_cost_metric(
    df_cost: pd.DataFrame,
    carbon_cost: CarbonCostTrajectory,
    importer: IntermediateDataImporter,
    sector: str,
    cost_metric="lcox",
    agg_vars=["product", "region", "technology"],
) -> pd.DataFrame:
    """Calculate weighted average of LCOX across the supply mix in a given year."""
    cost_metrics = ["lcox", "annualized_cost", "marginal_cost"]
    if (
        carbon_cost.df_carbon_cost.loc[
            carbon_cost.df_carbon_cost["year"] == 2050, "carbon_cost"
        ].item()
        > 0
    ):
        # Add carbon cost to cost DataFrame
        df_carbon_cost_addition = importer.get_carbon_cost_addition()
        df_cc = carbon_cost.df_carbon_cost
        df_cost = df_cost.loc[df_cost["technology_origin"] == "New-build"]
        merge_cols = [
            "product",
            "technology_destination",
            "region",
            "switch_type",
            "year",
        ]
        df_cost = df_cost.merge(
            df_carbon_cost_addition[
                merge_cols + [f"carbon_cost_addition_{cm}" for cm in cost_metrics]
            ],
            on=merge_cols,
            how="left",
        ).fillna(0)

        # Carbon cost addition is for 1 USD/tCO2, hence multiply with right factor
        # constant_carbon_cost = df_cc.loc[df_cc["year"] == 2050, "carbon_cost"].item()

        # Always do for all three cost metrics to avoid inconsistencies
        for cm in cost_metrics:
            # df_cost[f"carbon_cost_addition_{cm}"] = (
            #     df_cost[f"carbon_cost_addition_{cm}"] * constant_carbon_cost
            # ).fillna(0)

            df_cost[cm] = df_cost[cm] + df_cost[f"carbon_cost_addition_{cm}"]

            df_cost = df_cost.drop(columns=[f"carbon_cost_addition_{cm}"])

    # If granularity on technology level, simply take cost metric from cost DataFrame
    if agg_vars == ["product", "region", "technology"]:
        df = df_cost.rename(
            {cost_metric: "value", "technology_destination": "technology"}, axis=1
        ).copy()
        df = df.loc[df["technology_origin"] == "New-build"]

    else:
        df = pd.DataFrame()
        # In every year, get LCOX of the asset based on the year it was commissioned and average according to desired aggregation
        for year in np.arange(START_YEAR, END_YEAR + 1):
            df_stack = importer.get_asset_stack(year)
            df_stack = df_stack.rename(columns={"year_commissioned": "year"})

            if cost_metric == "lcox":
                # Assume that assets built before start of model time horizon have LCOX of start year
                # df_stack.loc[df_stack["year"] < START_YEAR, "year"] = START_YEAR
                df_stack["year"] = year
            elif cost_metric == "marginal_cost":
                # Marginal cost needs to correspond to current year
                df_stack["year"] = year

            # Plants existing in 2020: CAPEX assumed to be fully depreciated
            elif cost_metric == "annualized_cost":
                df_stack["year_until_annualized_capex"] = (
                    df_stack["year"].astype(int) + df_stack["asset_lifetime"]
                )
                df_stack["year"] = year

            # Add cost metric to each asset
            df_cost = df_cost.rename(columns={"technology_destination": "technology"})
            df_stack = df_stack.merge(
                df_cost, on=["product", "region", "technology", "year"], how="left"
            )

            # Plants existing in 2020: CAPEX assumed to be fully depreciated, so annualized cost is MC
            if cost_metric == "annualized_cost":
                df_stack["annualized_cost"] = np.where(
                    df_stack["year_until_annualized_capex"] < year,
                    df_stack["marginal_cost"],
                    df_stack["annualized_cost"],
                )

            # Calculate weighted average according to desired aggregation
            df_stack = (
                df_stack.groupby(agg_vars).apply(
                    lambda x: np.average(
                        x[cost_metric], weights=x["annual_production_volume"]
                    )
                )
            ).reset_index(drop=False)

            df_stack = df_stack.melt(
                id_vars=agg_vars,
                value_vars=cost_metric,
                var_name="parameter",
                value_name="value",
            )
            df_stack["year"] = year

            df = pd.concat([df, df_stack])

    # Transform to output table format
    df["parameter_group"] = "Cost"
    parameter_map = {
        "lcox": "LCOX",
        "marginal_cost": "Marginal cost",
        "annualized_cost": "Annualized Cost",
    }
    df["parameter"] = parameter_map[cost_metric]
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
        stack = (
            stack.groupby(["product", "region", "technology"])[
                "annual_production_volume"
            ]
            .sum()
            .reset_index(drop=False)
        )
        stack["year"] = year
        df_stack = pd.concat([df_stack, stack])

    # Filter for electrolysis technologies and group
    df_stack = df_stack.loc[df_stack["technology"].str.contains("Electrolyser")]

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
        electrolyser_props[merge_vars1 + ["electrolyser_hydrogen_proportion"]],
        on=merge_vars1,
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


def calculate_scope3_downstream_emissions(
    importer: IntermediateDataImporter,
    sector: str,
    pathway: str,
    gwp="GWP-100",
    agg_vars=["product", "region"],
) -> pd.DataFrame:

    scope = "3_downstream"
    # Calculate scope 3 downstream emissions for fertiliser in every region
    df_drivers = importer.get_demand_drivers()
    df_drivers = df_drivers.loc[df_drivers["region"] != "Global"]
    df_drivers = df_drivers.loc[df_drivers["driver"] == "Fertiliser"]
    df_drivers = df_drivers.drop(columns="unit").dropna(axis=1, how="all")

    # Driver DataFrame to long format
    df_drivers = df_drivers.melt(
        id_vars=["product", "driver", "region"],
        var_name="year",
        value_name="demand",
    )
    df_drivers["year"] = df_drivers["year"].astype(int)

    for ghg in GHGS:
        df_efs = importer.get_emission_factors(ghg=ghg)

        # Drop emission factors that are not right for the pathway
        if not df_efs["scenario"].isna().all():
            df_efs = df_efs.loc[
                (df_efs["scenario"].isna())
                | (df_efs["scenario"].str.contains(str.upper(pathway)))
            ]
        df_efs = df_efs.loc[df_efs["scope"] == scope]
        df_efs = df_efs[["product", "region", "year", f"emission_factor_{ghg}"]]

        # Add to demand drivers table
        df_drivers = df_drivers.merge(
            df_efs, on=["product", "region", "year"], how="left"
        ).fillna(0)

        # Scope 3 downstream emissions in Mt GHG is fertilizer end-use in Mt of product multiplied with emissions factor
        df_drivers[
            f"{str.upper(ghg)} Scope{str.capitalize(scope).replace('_', ' ')}"
        ] = (df_drivers["demand"] * df_drivers[f"emission_factor_{ghg}"])

    # Calculate CO2e
    df_drivers["CO2e Scope3 downstream"] = 0
    for ghg in GHGS:
        df_drivers["CO2e Scope3 downstream"] += (
            df_drivers[f"{str.upper(ghg)} Scope3 downstream"] * GWP[gwp][ghg]
        )

    # Aggregate and melt
    df_drivers = df_drivers.groupby(agg_vars + ["year"], as_index=False).sum()

    df_drivers = df_drivers[
        agg_vars
        + [
            "year",
            "CO2 Scope3 downstream",
            "N2O Scope3 downstream",
            "CH4 Scope3 downstream",
            "CO2e Scope3 downstream",
        ]
    ].melt(id_vars=agg_vars + ["year"], value_name="value", var_name="parameter")

    # Add parameter descriptions
    df_drivers["parameter_group"] = "Emissions"
    df_drivers["sector"] = sector
    unit_map = {
        "CO2 Scope3 downstream": "Mt CO2",
        "N2O Scope3 downstream": "Mt N2O",
        "CH4 Scope3 downstream": "Mt CH4",
        "CO2e Scope3 downstream": "Mt CO2e",
    }
    df_drivers["unit"] = df_drivers["parameter"].apply(lambda x: unit_map[x])
    for variable in ["product", "region", "technology"]:
        if variable not in agg_vars:
            df_drivers[variable] = "All"

    # Pivot table
    df = df_drivers.pivot_table(
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


def calculate_outputs(
    pathway: str, sensitivity: str, sector: str, carbon_cost: CarbonCostTrajectory
):
    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS[sector],
        carbon_cost=carbon_cost,
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

    # Calculate scope 3 downstream emissions for fertilizer end-use
    df_scope3 = pd.DataFrame()
    aggregations = [["product", "region"], ["product"], []]
    for agg_vars in aggregations:
        df = calculate_scope3_downstream_emissions(
            importer=importer,
            sector=sector,
            pathway=pathway,
            agg_vars=agg_vars,
        )
        df_scope3 = pd.concat([df, df_scope3])

    # Calculate plant numbers by retrofit, newbuild, rebuild, unchanged
    df_plants = _calculate_plant_numbers_by_type(
        importer=importer,
        sector=sector,
        agg_vars=["product", "region", "switch_type", "technology_destination"],
    )

    df_plants_tech_only = _calculate_plant_numbers_by_type(
        importer=importer,
        sector=sector,
        agg_vars=["switch_type", "technology_destination"],
    )

    df_plants_all_tech = _calculate_plant_numbers_by_type(
        importer=importer,
        sector=sector,
        agg_vars=["product", "region", "switch_type"],
    )

    df_plants_all_regions = _calculate_plant_numbers_by_type(
        importer=importer,
        sector=sector,
        agg_vars=["product", "switch_type", "technology_destination"],
    )

    df_plants_all_regions_all_tech = _calculate_plant_numbers_by_type(
        importer=importer,
        sector=sector,
        agg_vars=["product", "switch_type"],
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

    # Add annualized cost to cost DataFrame
    df_cost = importer.get_technology_transitions_and_cost()
    df_tech_characteristics = importer.get_technology_characteristics()
    df_cost = calculate_annualized_cost(
        df_cost=df_cost, df_tech_characteristics=df_tech_characteristics
    )

    # Calculate cost metrics with different aggregation variables
    aggregations = [
        ["product", "region", "technology"],
        ["product", "region"],
        ["product", "technology"],
        ["product"],
    ]
    df_cost_metrics = pd.DataFrame()
    for cost_metric in ["annualized_cost", "lcox", "marginal_cost"]:
        for agg_vars in aggregations:
            df = calculate_weighted_average_cost_metric(
                df_cost=df_cost,
                carbon_cost=carbon_cost,
                importer=importer,
                sector=sector,
                cost_metric=cost_metric,
                agg_vars=agg_vars,
            )
            df_cost_metrics = pd.concat([df, df_cost_metrics])

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

    # Express annual production volume in terms of ammonia
    if SECTOR == "chemicals":
        df_ammonia_all = calculate_annual_production_volume_as_ammonia(df=df)
        df = pd.concat([df, df_ammonia_all])

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
            df_scope3,
            df_cost_metrics,
            df_annual_investments,
            df_annual_investments_all_tech,
            df_annual_investments_all_tech_all_switch_types,
            df_annual_investments_all_switch_types,
            df_electrolysis_capacity,
            df_electrolysis_capacity_all_regions,
            df_electrolysis_capacity_all_tech,
            df_electrolysis_capacity_all_tech_all_regions,
            df_plants,
            df_plants_all_regions,
            df_plants_all_tech,
            df_plants_all_regions_all_tech,
            df_plants_tech_only,
        ]
    )
    df_pivot.reset_index(inplace=True)
    df_pivot.fillna(0, inplace=True)

    suffix = f"{sector}_{pathway}_{sensitivity}"

    importer.export_data(
        df_pivot, f"simulation_outputs_{suffix}.csv", "final", index=False
    )
    cc = carbon_cost.df_carbon_cost.loc[
        carbon_cost.df_carbon_cost["year"] == 2050, "carbon_cost"
    ].item()
    df_pivot.to_csv(
        f"{OUTPUT_WRITE_PATH[sector]}/{pathway}/{sensitivity}/carbon_cost_{cc}/simulation_outputs_{suffix}.csv",
        index=False,
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
        f"Weights: {RANKING_CONFIG[sector][type][pathway]}",
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


def calculate_annualized_cost(
    df_cost: pd.DataFrame, df_tech_characteristics: pd.DataFrame
) -> pd.DataFrame:
    """Calculate annualized cost"""

    # Add WACC and technology lifetime to cost DataFrame
    df_cost = df_cost.merge(
        df_tech_characteristics.rename(
            {"technology": "technology_destination"}, axis=1
        ),
        on=["product", "region", "year", "technology_destination"],
        how="left",
    )

    # Calculate capital recovery factor (CRF)
    df_cost["capital_recovery_factor"] = df_cost["wacc"] / (
        1 - np.power(1 + df_cost["wacc"], -df_cost["technology_lifetime"])
    )

    # Calculate annualized CAPEX and cost
    df_cost["annualized_capex"] = (
        df_cost["capital_recovery_factor"] * df_cost["switch_capex"]
    )
    df_cost["annualized_cost"] = df_cost["annualized_capex"] + df_cost["marginal_cost"]

    return df_cost


def calculate_annual_production_volume_as_ammonia(df):
    """Transform ammonium nitrate and urea production to ammonia and add to product "All" """

    df = df.loc[
        (df["parameter_group"] == "Production")
        & (df["parameter"] == "Annual production volume")
    ]

    df = df.set_index(
        [
            "sector",
            "region",
            "technology",
            "parameter_group",
            "parameter",
            "year",
            "unit",
            "product",
        ]
    )
    df = df.unstack(level=-1, fill_value=0).reset_index()

    # TODO: improve this workaround
    columns = [
        "sector",
        "region",
        "technology",
        "parameter_group",
        "parameter",
        "year",
        "unit",
        "ammonia",
        "ammonium nitrate",
        "urea",
    ]
    df.columns = columns

    df["value"] = (
        df["ammonia"]
        + AMMONIA_PER_AMMONIUM_NITRATE * df["ammonium nitrate"]
        + AMMONIA_PER_UREA * df["urea"]
    )
    df = df.drop(columns=["ammonia", "ammonium nitrate", "urea"])
    df["product"] = "Ammonia_all"
    df["unit"] = "MtNH3"

    # df_test = df.groupby("year").sum()

    return df

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


def _calculate_number_of_assets(
    df_stack: pd.DataFrame, use_standard_cuf=False
) -> pd.DataFrame:
    """Calculate number of assets by product, region and technology for a given asset stack"""

    logger.info("-- Calculating number of assets")

    if use_standard_cuf:
        df_stack = (
            df_stack.groupby(["product", "region", "technology"])
            .sum()["annual_production_volume"]
            .reset_index()
        )
        df_stack["asset"] = df_stack[["product", "annual_production_volume"]].apply(
            lambda x: int(
                x[1]
                / (CUF_UPPER_THRESHOLD * ASSUMED_ANNUAL_PRODUCTION_CAPACITY_MT[x[0]])
            ),
            axis=1,
        )
        df_stack["parameter"] = "Number of plants (standard CUF)"
        df_stack = df_stack.drop(columns=["annual_production_volume"])
    else:
        # Count number of assets
        df_stack["asset"] = 1
        df_stack = (
            df_stack.groupby(["product", "region", "technology"])
            .count()["asset"]
            .reset_index()
        )

        df_stack["parameter"] = "Number of plants (from model)"

    # Add parameter descriptions
    df_stack.rename(columns={"asset": "value"}, inplace=True)
    df_stack["parameter_group"] = "Production"

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
        scope for scope in EMISSION_SCOPES if scope != "scope3_downstream"
    ]
    # Emissions are the emissions factor multiplied with the annual production volume
    df_stack = df_stack.merge(df_emissions, on=["product", "region", "technology"])
    scopes = [f"{ghg}_{scope}" for scope in emission_scopes for ghg in GHGS]

    for scope in scopes:
        df_stack[scope] = df_stack[scope] * df_stack["annual_production_volume"]

    if agg_vars:
        df_stack = (
            df_stack.groupby(agg_vars)[scopes + ["annual_production_volume"]]
            .sum()
            .reset_index()
        )
    else:
        df_stack = (
            df_stack[scopes + ["annual_production_volume"]].sum().to_frame().transpose()
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
    for var in [
        agg_var
        for agg_var in ["product", "region", "technology"]
        if agg_var not in agg_vars
    ]:
        df_stack[var] = "All"

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

    emission_scopes = [
        scope for scope in EMISSION_SCOPES if scope != "scope3_downstream"
    ]
    scopes = [f"{ghg}_{scope}" for scope in emission_scopes for ghg in GHGS]

    for scope in scopes:
        df_stack[scope] = df_stack[scope] * df_stack["annual_production_volume"]

    if agg_vars:
        df_stack = (
            df_stack.groupby(agg_vars)[scopes + ["annual_production_volume"]]
            .sum()
            .reset_index()
        )
    else:
        df_stack = (
            df_stack[scopes + ["annual_production_volume"]].sum().to_frame().transpose()
        )

    for scope in emission_scopes:
        df_stack[f"CO2e {str.capitalize(scope).replace('_', ' ')}"] = 0
        for ghg in GHGS:
            df_stack[f"CO2e {str.capitalize(scope).replace('_', ' ')}"] += (
                df_stack[f"{ghg}_{scope}"] * GWP[gwp][ghg]
            )

    df_stack = df_stack.melt(
        id_vars=agg_vars,
        value_vars=[
            f"CO2e {str.capitalize(scope).replace('_', ' ')}"
            for scope in emission_scopes
        ],
        var_name="parameter",
        value_name="value",
    )

    df_stack["parameter_group"] = "Emissions"
    df_stack["unit"] = "Mt CO2e"
    for var in [
        agg_var
        for agg_var in ["product", "region", "technology"]
        if agg_var not in agg_vars
    ]:
        df_stack[var] = "All"

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

        if agg_vars:
            df_stack = (
                df_stack.groupby(agg_vars)[scopes + ["annual_production_volume"]]
                .sum()
                .reset_index()
            )
        else:
            df_stack = (
                df_stack[scopes + ["annual_production_volume"]]
                .sum()
                .to_frame()
                .transpose()
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
    for var in [
        agg_var
        for agg_var in ["product", "region", "technology"]
        if agg_var not in agg_vars
    ]:
        df_stack[var] = "All"

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
    year: int, aggregations: list, importer: IntermediateDataImporter
) -> pd.DataFrame:
    """Create DataFrame with all outputs for a given year."""

    # Calculate asset numbers and production volumes for the stack in that year
    df_stack = importer.get_asset_stack(year)
    df_total_assets = _calculate_number_of_assets(df_stack, use_standard_cuf=False)
    df_total_assets_std_cuf = _calculate_number_of_assets(
        df_stack, use_standard_cuf=True
    )
    df_production_capacity = _calculate_production_volume(df_stack)

    # Calculate emissions, CO2 captured and emissions intensity
    df_emissions = importer.get_emissions()
    df_emissions = df_emissions[df_emissions["year"] == year]
    df_stack_emissions = pd.DataFrame()
    df_stack_emissions_co2e = pd.DataFrame()
    df_emissions_intensity = pd.DataFrame()
    for agg_vars in aggregations:
        df_stack_emissions = pd.concat(
            [
                df_stack_emissions,
                _calculate_emissions(df_stack, df_emissions, agg_vars=agg_vars),
            ]
        )
        df_stack_emissions_co2e = pd.concat(
            [
                df_stack_emissions_co2e,
                _calculate_emissions_co2e(
                    df_stack, df_emissions, gwp="GWP-100", agg_vars=agg_vars
                ),
            ]
        )
        df_emissions_intensity = pd.concat(
            [
                df_emissions_intensity,
                _calculate_emissions_intensity(
                    df_stack, df_emissions, agg_vars=agg_vars
                ),
            ]
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
            df_total_assets_std_cuf,
            df_production_capacity,
            df_stack_emissions,
            df_stack_emissions_co2e,
            df_emissions_intensity,
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

        # Add ammonia type classification
        df = add_ammonia_type_to_df(df)

        df = (
            df.groupby(agg_vars + ["ammonia_type"])["investment"]
            .sum()
            .reset_index(drop=False)
        )

        df = df.melt(
            id_vars=agg_vars + ["ammonia_type"],
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

        def map_parameter_group(row: pd.Series) -> str:
            map = {
                "brownfield_renovation": "Brownfield renovation investment",
                "brownfield_newbuild": "Brownfield rebuild investment",
                "greenfield": "Greenfield investment",
            }
            name = f'{str.capitalize(row.loc["ammonia_type"])}: {map[row.loc["switch_type"]]}'
            return name

        df_investment["parameter"] = df_investment[
            ["ammonia_type", "switch_type"]
        ].apply(lambda row: map_parameter_group(row), axis=1)
    else:
        df_investment["parameter"] = df_investment["ammonia_type"].apply(
            lambda x: f"{str.capitalize(x)}: total investment"
        )

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
    use_standard_CUF=True,
) -> pd.DataFrame:
    """Calculate plant numbers, based on standard CUF (upper threshold)."""

    # Calculate invesment in newbuild, brownfield retrofit and brownfield rebuild technologies in every year
    switch_types = ["greenfield", "rebuild", "retrofit"]
    df_plants = pd.DataFrame()

    for year in np.arange(START_YEAR + 1, END_YEAR + 1):

        # Get current and previous stack
        drop_cols = ["cuf", "asset_lifetime"]
        current_stack = (
            importer.get_asset_stack(year)
            .drop(columns=drop_cols)
            .rename(
                {
                    "technology": "technology_destination",
                    "annual_production_capacity": "annual_production_capacity_destination",
                    "annual_production_volume": "annual_production_volume_destination",
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
                    "annual_production_volume": "annual_production_volume_origin",
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
        if use_standard_CUF:
            if "product" not in agg_vars:
                agg_vars += ["product"]

            df = (
                df.groupby(agg_vars)[["annual_production_volume_destination"]]
                .sum()
                .reset_index(drop=False)
            )

            df["plant_number"] = df[
                ["product", "annual_production_volume_destination"]
            ].apply(
                lambda x: int(
                    x[1]
                    / (
                        ASSUMED_ANNUAL_PRODUCTION_CAPACITY_MT[x[0]]
                        * CUF_UPPER_THRESHOLD
                    )
                ),
                axis=1,
            )

        else:
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

    if use_standard_CUF:
        df_plants["unit"] = "Number of plants from standard CUF"
    else:
        df_plants["unit"] = "Number of plants in model"

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

            # If CAPEX is fully depreciated, annualized cost is equal to marginal cost
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

    calculate_outputs_interface(pathway, sensitivity, sector, carbon_cost, importer)
    # calculate_outputs_report(pathway, sensitivity, sector, carbon_cost, importer)


def _merge_current_and_previous_stack(
    year: int, importer: IntermediateDataImporter
) -> pd.DataFrame:
    """Merge stacks of the current and previous year and return as DataFrame."""
    # Get current and previous stack
    drop_cols = ["cuf", "asset_lifetime"]
    switch_types = ["greenfield", "rebuild", "retrofit"]
    current_stack = (
        importer.get_asset_stack(year)
        .drop(columns=drop_cols)
        .rename(
            {
                "technology": "technology_destination",
                "annual_production_capacity": "annual_production_capacity_destination",
                "annual_production_volume": "annual_production_volume_destination",
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
                "annual_production_volume": "annual_production_volume_origin",
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
    return df


def _calculate_plant_numbers(
    importer: IntermediateDataImporter,
    sector: str,
    agg_vars=["product", "region", "ammonia_type"],
    use_standard_CUF=True,
) -> pd.DataFrame:
    """Calculate plant numbers, based on standard CUF (upper threshold) or model results."""

    df_plants = pd.DataFrame()

    for year in np.arange(START_YEAR + 1, END_YEAR + 1):

        stack = (
            importer.get_asset_stack(year)
            .drop(columns=["cuf", "asset_lifetime"])
            .rename({"technology": "technology_destination"}, axis=1)
        )
        stack = add_ammonia_type_to_df(stack)

        # Calculate number of plants for the aggregation variables
        if use_standard_CUF:
            if "product" not in agg_vars:
                agg_vars_temp = agg_vars + ["product"]
            else:
                agg_vars_temp = agg_vars

            df = (
                stack.groupby(agg_vars_temp)[["annual_production_volume"]]
                .sum()
                .reset_index(drop=False)
            )

            df["plant_number"] = df[["product", "annual_production_volume"]].apply(
                lambda x: int(
                    x[1]
                    / (
                        ASSUMED_ANNUAL_PRODUCTION_CAPACITY_MT[x[0]]
                        * CUF_UPPER_THRESHOLD
                    )
                ),
                axis=1,
            )

            # Sum over all products if requested
            if "product" not in agg_vars:
                df = df.groupby(agg_vars).sum().reset_index(drop=False)

        else:
            stack["plant_number"] = 1
            df = stack.groupby(agg_vars)[["plant_number"]].sum().reset_index(drop=False)

        df = df.melt(
            id_vars=agg_vars,
            value_vars="plant_number",
            var_name="parameter",
            value_name="value",
        )

        df["year"] = year

        df_plants = pd.concat([df_plants, df])

    for variable in ["product", "region", "technology_destination"]:
        if variable not in agg_vars:
            df_plants[variable] = "All"

    df_plants["parameter"] = df_plants["ammonia_type"].apply(
        lambda x: f"{str.capitalize(x)} ammonia plants"
    )

    df_plants["parameter_group"] = "Plant number"

    if use_standard_CUF:
        df_plants["unit"] = "Number of plants (standard CUF)"
    else:
        df_plants["unit"] = "Number of plants (in model)"

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


def calculate_outputs_interface(
    pathway: str,
    sensitivity: str,
    sector: str,
    carbon_cost: CarbonCostTrajectory,
    importer: IntermediateDataImporter,
):
    aggregations = [
        ["product", "region"],
        ["product"],
        [],
    ]
    # Calculate scope 3 downstream emissions for fertilizer end-use
    df_scope3 = pd.DataFrame()

    for agg_vars in aggregations:
        df = calculate_scope3_downstream_emissions(
            importer=importer,
            sector=sector,
            pathway=pathway,
            agg_vars=agg_vars,
        )
        df_scope3 = pd.concat([df, df_scope3])

    # Calculate plant numbers by retrofit, newbuild, rebuild, unchanged
    df_plants = pd.DataFrame()
    for agg_vars in aggregations:
        df = _calculate_plant_numbers(
            importer=importer,
            sector=sector,
            agg_vars=agg_vars + ["ammonia_type"],
            use_standard_CUF=True,
        )
        df_plants = pd.concat([df, df_plants])

    # Calculate electrolysis capacity
    df_electrolysis_capacity = pd.DataFrame()
    for agg_vars in aggregations:
        df = calculate_electrolysis_capacity(
            importer=importer, sector=sector, agg_vars=agg_vars
        )
        df_electrolysis_capacity = pd.concat([df, df_electrolysis_capacity])

    # Calculate annual investments
    df_cost = importer.get_technology_transitions_and_cost()

    df_annual_investments = pd.DataFrame()
    for agg_vars in aggregations:
        df = _calculate_annual_investments(
            df_cost=df_cost, importer=importer, sector=sector, agg_vars=agg_vars
        )
        df_annual_investments = pd.concat([df, df_annual_investments])

    # Calculate GHG emission reduction wedges

    # Create output table for every year and concatenate
    data = []
    data_stacks = []

    for year in range(START_YEAR, END_YEAR + 1):
        logger.info(f"Processing year {year}")
        yearly = create_table_all_data_year(
            aggregations=aggregations, year=year, importer=importer
        )
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
            df_annual_investments,
            df_electrolysis_capacity,
            df_plants,
        ]
    )
    df_pivot.reset_index(inplace=True)
    df_pivot.fillna(0, inplace=True)

    suffix = f"{sector}_{pathway}_{sensitivity}"

    importer.export_data(
        df_pivot, f"interface_outputs_{suffix}.csv", export_dir="final"
    )
    cc = carbon_cost.df_carbon_cost.loc[
        carbon_cost.df_carbon_cost["year"] == 2050, "carbon_cost"
    ].item()
    df_pivot.to_csv(
        f"{OUTPUT_WRITE_PATH[sector]}/{pathway}/{sensitivity}/carbon_cost_{cc}/interface_outputs_{suffix}.csv",
        index=False,
    )

    logger.info("All data for all years processed.")


def calculate_outputs_report(
    pathway: str,
    sensitivity: str,
    sector: str,
    carbon_cost: CarbonCostTrajectory,
    importer: IntermediateDataImporter,
):

    # Calculate scope 3 downstream emissions for fertilizer end-use
    df_scope3 = pd.DataFrame()
    aggregations = [
        ["product", "region"],
        ["product"],
        [],
    ]
    for agg_vars in aggregations:
        df = calculate_scope3_downstream_emissions(
            importer=importer,
            sector=sector,
            pathway=pathway,
            agg_vars=agg_vars,
        )
        df_scope3 = pd.concat([df, df_scope3])

    # Calculate plant numbers by retrofit, newbuild, rebuild, unchanged
    aggregations = [
        ["product", "region", "switch_type", "technology_destination"],
        ["switch_type", "technology_destination"],
        ["product", "region", "switch_type"],
        ["product", "switch_type", "technology_destination"],
        ["product", "switch_type"],
    ]
    df_plants = pd.DataFrame()
    for use_standard_cuf in [True, False]:
        for agg_vars in aggregations:
            df = _calculate_plant_numbers_by_type(
                importer=importer,
                sector=sector,
                agg_vars=agg_vars,
                use_standard_CUF=use_standard_cuf,
            )
            df_plants = pd.concat([df, df_plants])

    # Calculate electrolysis capacity
    aggregations = [
        ["product", "region", "technology"],
        ["product", "region"],
        ["product"],
        ["product", "technology"],
    ]
    df_electrolysis_capacity = pd.DataFrame()
    for agg_vars in aggregations:
        df = calculate_electrolysis_capacity(
            importer=importer, sector=sector, agg_vars=agg_vars
        )
        df_electrolysis_capacity = pd.concat([df, df_electrolysis_capacity])

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
    aggregations = [
        ["product", "region", "switch_type", "technology_destination"],
        ["product", "region", "switch_type"],
        ["product", "region", "technology_destination"],
        ["product", "region"],
        ["product"],
    ]
    df_annual_investments = pd.DataFrame()
    for agg_vars in aggregations:
        df = _calculate_annual_investments(
            df_cost=df_cost,
            importer=importer,
            sector=sector,
            agg_vars=agg_vars,
            ammonia_type=True,
        )
        df_annual_investments = pd.concat([df, df_annual_investments])

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
            df_electrolysis_capacity,
            df_plants,
        ]
    )
    df_pivot.reset_index(inplace=True)
    df_pivot.fillna(0, inplace=True)

    suffix = f"{sector}_{pathway}_{sensitivity}"

    cc = carbon_cost.df_carbon_cost.loc[
        carbon_cost.df_carbon_cost["year"] == 2050, "carbon_cost"
    ].item()
    df_pivot.to_csv(
        f"{OUTPUT_WRITE_PATH[sector]}/{pathway}/{sensitivity}/carbon_cost_{cc}/simulation_outputs_{suffix}.csv",
        index=False,
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


def add_ammonia_type_to_df(df: pd.DataFrame) -> pd.DataFrame:

    # Add ammonia type
    colour_map = {
        "Natural Gas SMR + ammonia synthesis": "grey",
        "Coal Gasification + ammonia synthesis": "grey",
        "Electrolyser + SMR + ammonia synthesis": "transitional",  # "blue_10%",
        "Electrolyser + Coal Gasification + ammonia synthesis": "transitional",  # "blue_10%",
        "Coal Gasification+ CCS + ammonia synthesis": "blue",
        "Natural Gas SMR + CCS (process emissions only) + ammonia synthesis": "transitional",  # "blue",
        "Natural Gas ATR + CCS + ammonia synthesis": "blue",
        "GHR + CCS + ammonia synthesis": "blue",
        "ESMR Gas + CCS + ammonia synthesis": "blue",
        "Natural Gas SMR + CCS + ammonia synthesis": "blue",
        "Electrolyser - grid PPA + ammonia synthesis": "green",
        "Biomass Digestion + ammonia synthesis": "bio-based",
        "Biomass Gasification + ammonia synthesis": "bio-based",
        "Methane Pyrolysis + ammonia synthesis": "methane pyrolysis",
        "Electrolyser - dedicated VRES + grid PPA + ammonia synthesis": "green",
        "Electrolyser - dedicated VRES + H2 storage - geological + ammonia synthesis": "green",
        "Electrolyser - dedicated VRES + H2 storage - pipeline + ammonia synthesis": "green",
        "Waste Water to ammonium nitrate": "other",
        "Waste to ammonia": "other",
        "Oversized ATR + CCS": "blue",
        "All": "no type",
    }
    df["ammonia_type"] = df["technology_destination"].apply(lambda row: colour_map[row])
    return df


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

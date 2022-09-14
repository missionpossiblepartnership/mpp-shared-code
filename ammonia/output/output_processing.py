""" Process outputs to standardised output table."""
import pandas as pd
import numpy as np

from ammonia.config_ammonia import *
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory
from ammonia.output.debugging_outputs import create_table_asset_transition_sequences
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def calculate_outputs(
    pathway_name: str,
    sensitivity: str,
    sector: str,
    carbon_cost_trajectory: CarbonCostTrajectory,
):
    """Calculate all outputs and save in .csv file"""

    importer = IntermediateDataImporter(
        pathway_name=pathway_name,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS,
        carbon_cost_trajectory=carbon_cost_trajectory,
    )

    # Create summary table of asset transitions
    logger.info("Creating table with asset transition sequences.")
    df_transitions = create_table_asset_transition_sequences(importer)
    importer.export_data(
        df_transitions,
        f"asset_transition_sequences_sensitivity_{sensitivity}.csv",
        "final",
    )

    # Standard aggregations of the outputs
    aggregations = [
        ["region"],
        [],
    ]

    # Calculate the emissions intensity abatement by supply technology type - CHECKED
    df_abatement = pd.DataFrame()

    for agg_vars in aggregations.copy():
        df = _calculate_emissions_intensity_abatement(
            importer=importer,
            sector=sector,
            pathway=pathway_name,
            agg_vars=agg_vars,
        )
        df_abatement = pd.concat([df_abatement, df])

    # Calculate scope 3 downstream emissions for fertilizer end-use - CHECKE
    df_scope3 = pd.DataFrame()

    for agg_vars in [["product"]] + aggregations.copy(): # type: ignore
        df = calculate_scope3_downstream_emissions(
            importer=importer,
            sector=sector,
            pathway=pathway_name,
            agg_vars=agg_vars,
        )
        df_scope3 = pd.concat([df, df_scope3])

    # Calculate electrolysis capacity - CHECKED
    df_electrolysis_capacity = pd.DataFrame()
    for agg_vars in aggregations.copy():
        df = calculate_electrolysis_capacity(
            importer=importer, sector=sector, agg_vars=agg_vars
        )
        df_electrolysis_capacity = pd.concat([df, df_electrolysis_capacity])

    # Calculate annual investments - CHECKED
    df_cost = importer.get_technology_transitions_and_cost()

    df_annual_investments = pd.DataFrame()
    for agg_vars in aggregations.copy():
        df = _calculate_annual_investments(
            df_cost=df_cost, importer=importer, sector=sector, agg_vars=agg_vars
        )
        df_annual_investments = pd.concat([df, df_annual_investments])

    # Create output table for every year and concatenate
    data = []

    for year in range(START_YEAR, END_YEAR + 1):
        logger.info(f"Processing year {year}")
        yearly = create_table_all_data_year(
            aggregations=aggregations.copy(),
            year=year,
            importer=importer,
        )
        yearly["year"] = year
        data.append(yearly)

    df = pd.concat(data)
    df["sector"] = sector

    # Calculate investment into dedicated renewables - CHECKED
    df_investment_renewables = pd.DataFrame()
    for agg_vars in aggregations.copy():
        temp = calculate_investment_dedicated_renewables(
            importer, df, agg_vars=agg_vars
        )
        df_investment_renewables = pd.concat([df_investment_renewables, temp])

    # Calculate total annual investments
    df_total_investments = _calculate_total_annual_investments(
        df_annual_investments, df_investment_renewables, aggregations=[["region"], []]
    )

    # Express annual production volume in terms of ammonia - CHECKED
    df_ammonia_all = calculate_annual_production_volume_as_ammonia(df=df)
    df = pd.concat([df, df_ammonia_all])

    for agg_vars in [["region"], []]:
        df_ammonia_type = calculate_annual_production_volume_by_ammonia_type(
            df=df, agg_vars=agg_vars
        )
        df = pd.concat([df, df_ammonia_type])

    # Convert resource consumption to base unit, aggregate low-cost power regions and energy & materials category
    df = convert_and_aggregate_resource_consumption(df)

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
            df_abatement,
            df_scope3,
            df_annual_investments,
            df_total_investments,
            df_electrolysis_capacity,
            df_investment_renewables,
        ]
    )
    df_pivot.reset_index(inplace=True)
    df_pivot.fillna(0, inplace=True)

    suffix = f"{sector}_{pathway_name}_{sensitivity}"

    # For regions, replace All with Global
    df_pivot["region"] = df_pivot["region"].replace({"All": "Global"})

    importer.export_data(
        df_pivot, f"interface_outputs_{suffix}.csv", export_dir="final", index=False
    )

    logger.info("All data for all years processed.")


def _calculate_total_annual_investments(
    df_annual_investments: pd.DataFrame,
    df_investment_renewables: pd.DataFrame,
    aggregations: list,
) -> pd.DataFrame:
    """Sum direct investments into plants and dedicated renewables investment for each year"""
    melt_vars = [
        "sector",
        "product",
        "region",
        "technology",
        "parameter_group",
        "parameter",
        "unit",
    ]

    group_vars = [
        "sector",
        "product",
        "region",
        "technology",
        "parameter_group",
        "unit",
    ]

    df_annual_investments = df_annual_investments.reset_index()
    df_investment_renewables = df_investment_renewables.reset_index()

    # Sum all types of direct investment
    df_annual_investments = (
        df_annual_investments.groupby(by=group_vars).sum().reset_index()
    )

    df_annual_investments["parameter"] = "Plant investment"

    # Melt tables into long format and merge
    df_annual_investments = df_annual_investments.melt(
        id_vars=melt_vars,
        var_name="year",
        value_name="plant_investment",
    ).drop(columns="parameter")

    df_investment_renewables = df_investment_renewables.melt(
        id_vars=melt_vars,
        var_name="year",
        value_name="renewable_investment",
    ).drop(columns="parameter")

    df = df_annual_investments.merge(
        df_investment_renewables,
        on=[
            "sector",
            "product",
            "region",
            "technology",
            "parameter_group",
            "unit",
            "year",
        ],
        how="outer",
    ).fillna(0)

    # Total investment is sum of plant investment and investment into direct renewables
    df["total_investment"] = df["plant_investment"] + df["renewable_investment"]
    df = df.drop(columns=["plant_investment", "renewable_investment"])
    df["parameter"] = "Total direct investment"
    df["parameter_group"] = "Total direct investment"

    # Pivot table back to wide format
    df["year"] = df["year"].astype(int)
    df = df.pivot_table(
        index=melt_vars,
        columns="year",
        values="total_investment",
    ).fillna(0)

    return df


def convert_and_aggregate_resource_consumption(df: pd.DataFrame) -> pd.DataFrame:
    """For each resource, convert to base unit, sum energy & materials category, and aggregate low-cost power regions"""

    resources = df.loc[
        df["parameter_group"] == "Resource consumption", "parameter"
    ].unique()

    map_desired_units = {
        "Coal": "Mt",
        "Natural gas": "bcm",  # "MMBtu",
        "Electricity - grid": "TWh",
        "Electricity - PPA": "TWh",
        "Electricity - on site VREs": "TWh",
        "CO2": "Mt CO2",
        "Steam": "PJ",
        "Biomass": "PJ",
        "H2 storage - geological": "Mt H2",
        "H2 storage - pipeline": "Mt H2",
    }

    map_conversion_factors_from_PJ = {
        "Coal": 34120.842375357 * 1e-6,
        "Natural gas": 1 / 38.2,  # 9.4781712031 * 1e5,
        "Electricity - grid": 1 / 3.6,
        "Electricity - PPA": 1 / 3.6,
        "Electricity - on site VREs": 1 / 3.6,
        "CO2": 1,
        "Steam": 1,
        "Biomass": 1,
        "H2 storage - geological": 1 / 119.988,
        "H2 storage - pipeline": 1 / 119.988,
    }

    # Convert figures to desired units
    for resource in resources:
        df.loc[df["parameter"] == resource, "value"] *= map_conversion_factors_from_PJ[
            resource
        ]
        df.loc[df["parameter"] == resource, "unit"] = map_desired_units[resource]

    # Aggregate electricity consumption and H2 storage
    df.loc[df["parameter"].str.contains("Electricity"), "parameter"] = "Electricity"
    df.loc[df["parameter"].str.contains("H2 storage"), "parameter"] = "H2 storage"

    # Aggregate the low-cost power regions
    df["region"] = df["region"].apply(
        lambda x: map_low_cost_power_regions(x, map_type="to_category")
    )
    group_cols = [col for col in df.columns.to_list() if col != "value"]
    df = df.groupby(by=group_cols, as_index=False).sum()

    return df


def _calculate_number_of_assets(
    df_stack: pd.DataFrame, use_standard_cuf=False
) -> pd.DataFrame:
    """Calculate number of assets by product, region and technology for a given asset stack"""

    logger.info("-- Calculating number of assets")

    # Map low-cost power regions to individual category
    df_stack["region"] = df_stack["region"].apply(
        lambda x: map_low_cost_power_regions(x, "to_category")
    )

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

    # Map low-cost power regions to individual category
    df_stack["region"] = df_stack["region"].apply(
        lambda x: map_low_cost_power_regions(x, "to_category")
    )

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

    # Map low-cost power regions to individual category
    df_stack["region"] = df_stack["region"].apply(
        lambda x: map_low_cost_power_regions(x, "to_category")
    )

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

    # Map low-cost power regions to individual category
    df_stack["region"] = df_stack["region"].apply(
        lambda x: map_low_cost_power_regions(x, "to_category")
    )

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

    # Map low-cost power regions to individual category
    df_stack["region"] = df_stack["region"].apply(
        lambda x: map_low_cost_power_regions(x, "to_category")
    )

    if agg_vars:
        df_stack = df_stack.groupby(agg_vars)["co2_scope1_captured"].sum().reset_index()
    else:
        df_stack = df_stack[["co2_scope1_captured"]].sum().to_frame().transpose()

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

    for var in [
        agg_var
        for agg_var in ["product", "region", "technology"]
        if agg_var not in agg_vars
    ]:
        df_stack[var] = "All"

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
            regions = df_stack["region"].unique()
            df_stack = (
                df_emissions.loc[df_emissions["region"].isin(regions)]
                .rename(
                    {scope: f"emissions_intensity_{scope}" for scope in scopes}, axis=1
                )
                .copy()
            )

    # Otherwise, Emissions are the emissions factor multiplied with the annual production volume
    else:
        df_stack = df_stack.merge(
            df_emissions, on=["product", "region", "technology"], how="left"
        )
        for scope in scopes:
            df_stack[scope] = df_stack[scope] * df_stack["annual_production_volume"]

        # Map low-cost power regions to individual category
        df_stack["region"] = df_stack["region"].apply(
            lambda x: map_low_cost_power_regions(x, "to_category")
        )

        # If product is not in the aggregation variables, convert all annual production volumes to ammonia
        if "product" not in agg_vars:
            df_stack["annual_production_volume"] = df_stack.apply(
                lambda row: conversion_factor_to_ammonia(row)
                * row["annual_production_volume"],
                axis=1,
            )
            df_stack["product"] = "All"

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
    """Calculate the consumption of a given resource in a given year, optionally grouped by specific variables. Leave cost-power regions as they are because granularity
    needed for calculating direct investment into dedicated renewables."""

    logger.info(f"-- Calculating consumption of {resource}")

    # Get inputs of that resource required for each technology in GJ/t (for CO2: tCO2/t)
    df_variable = df_inputs_outputs.loc[
        (df_inputs_outputs["parameter"] == resource)
        & (df_inputs_outputs["year"] == year)
    ].copy()

    df_stack = df_stack.merge(df_variable, on=["product", "region", "technology"])

    # Calculate resource consumption by multiplying the input with the annual production volume of that technology
    df_stack["value"] = df_stack["value"] * df_stack["annual_production_volume"]

    df_stack = (df_stack.groupby(agg_vars + ["parameter"])["value"].sum()).reset_index()

    # Fill with zeros for regions that do not consume this resource
    if agg_vars == ["region"]:
        for region in get_regions_with_lcprs():
            if region not in df_stack["region"].unique():
                df_zero_line = pd.DataFrame(
                    {"region": [region], "parameter": [resource], "value": [0.0]}
                )
                df_stack = pd.concat([df_stack, df_zero_line])

    elif (agg_vars == []) & df_stack.empty:
        df_stack = pd.DataFrame({"parameter": [resource], "value": [0.0]})

    # Unit is Mt for CO2 (Mt NH3 * tCO2/tNH3) and PJ for other resources (Mt NH3 * GJ/tNH3)
    df_stack["unit"] = np.where(df_stack["parameter"] == "CO2", "Mt", "PJ")
    df_stack["parameter_group"] = "Resource consumption"

    for var in [
        agg_var
        for agg_var in ["product", "region", "technology"]
        if agg_var not in agg_vars
    ]:
        df_stack[var] = "All"

    return df_stack


def create_table_all_data_year(
    year: int, aggregations: list, importer: IntermediateDataImporter
) -> pd.DataFrame:
    """Create DataFrame with all outputs for a given year."""

    # Calculate asset numbers and production volumes for the stack in that year
    df_stack = importer.get_asset_stack(year)

    df_total_assets = _calculate_number_of_assets(
        df_stack.copy(deep=True), use_standard_cuf=False
    )
    df_total_assets_std_cuf = _calculate_number_of_assets(
        df_stack.copy(deep=True), use_standard_cuf=True
    )
    df_production_capacity = _calculate_production_volume(df_stack.copy(deep=True))

    # Calculate emissions, CO2 captured and emissions intensity
    df_emissions = importer.get_emissions()
    df_emissions = df_emissions[df_emissions["year"] == year]
    df_stack_emissions = pd.DataFrame()
    df_stack_emissions_co2e = pd.DataFrame()
    df_emissions_intensity = pd.DataFrame()
    df_co2_captured = pd.DataFrame()

    for agg_vars in aggregations:
        df_stack_emissions = pd.concat(
            [
                df_stack_emissions,
                _calculate_emissions(
                    df_stack.copy(deep=True), df_emissions, agg_vars=agg_vars
                ),
            ]
        )
        df_stack_emissions_co2e = pd.concat(
            [
                df_stack_emissions_co2e,
                _calculate_emissions_co2e(
                    df_stack.copy(deep=True),
                    df_emissions,
                    gwp="GWP-100",
                    agg_vars=agg_vars,
                ),
            ]
        )
        df_emissions_intensity = pd.concat(
            [
                df_emissions_intensity,
                _calculate_emissions_intensity(
                    df_stack.copy(deep=True), df_emissions, agg_vars=agg_vars
                ),
            ]
        )

        df_co2_captured = pd.concat(
            [
                df_co2_captured,
                _calculate_co2_captured(
                    df_stack.copy(deep=True), df_emissions, agg_vars=agg_vars
                ),
            ]
        )

    # Calculate feedstock and energy consumption
    df_inputs_outputs = importer.get_inputs_outputs()
    df_inputs_outputs.loc[
        df_inputs_outputs["parameter"].isin(["Wet biomass", "Dry biomass"]), "parameter"
    ] = "Biomass"
    data_variables = []

    resources = [
        "Coal",
        "Natural gas",
        "Electricity - grid",
        "Electricity - PPA",
        "Electricity - on site VREs",
        "H2 storage - geological",
        "H2 storage - pipeline",
        "Biomass",
    ]
    for agg_vars in aggregations:
        for resource in resources:
            df_stack_variable = _calculate_resource_consumption(
                df_stack.copy(deep=True),
                df_inputs_outputs,
                resource,
                year,
                agg_vars=agg_vars,
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

    # Calculate investment in newbuild, brownfield retrofit and brownfield rebuild technologies in every year
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

        # Map low-cost power regions to individual category
        df["region"] = df["region"].apply(
            lambda x: map_low_cost_power_regions(x, "to_category")
        )

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
            lambda x: f"{str.capitalize(x)}: direct investment"
        )

    # Fill non-existent investment types with zeros for suitable aggregation
    if [
        agg_var
        for agg_var in agg_vars
        if agg_var in ["switch_type", "product", "technology_destination"]
    ] == []:

        ammonia_types = [
            "grey",
            "blue",
            "green",
            "bio-based",
            "methane pyrolysis",
            "transitional",
        ]

        for region in df_investment["region"].unique():
            for ammonia_type in ammonia_types:
                types_in_df = df_investment.loc[
                    df_investment["region"] == region, "ammonia_type"
                ].unique()
                if ammonia_type not in types_in_df:
                    df_zero_line = pd.DataFrame(
                        {
                            "region": [region],
                            "ammonia_type": [ammonia_type],
                            "parameter": [
                                f"{str.capitalize(ammonia_type)}: direct investment"
                            ],
                            "value": [0.0],
                            "year": [2050],
                            "product": ["All"],
                            "switch_type": ["All"],
                            "technology_destination": ["All"],
                        }
                    )
                    df_investment = pd.concat([df_investment, df_zero_line])

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
    regions = df_stack["region"].unique()
    df_stack = df_stack.loc[df_stack["technology"].str.contains("Electrolyser")]

    # Ensure that regions without electrolyser technologies are filled with zeros
    regions_not_in_df = [
        region for region in regions if region not in df_stack["region"].unique()
    ]
    for region in regions_not_in_df:
        df_zero_line = pd.DataFrame(
            {
                "product": ["Ammonia"],
                "region": [region],
                "technology": [
                    "Electrolyser - dedicated VRES + H2 storage - geological + ammonia synthesis"
                ],
                "annual_production_volume": [0.0],
                "year": [2050],
            }
        )
        df_stack = pd.concat([df_stack, df_zero_line])

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

    # Group low-cost power regions into one category
    df_stack = replace_lcprs_with_one_category(df_stack)

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


def replace_lcprs_with_one_category(df: pd.DataFrame):

    lcprs = ["Brazil", "Australia", "Namibia", "Saudi Arabia"]
    df.loc[df["region"].isin(lcprs), "region"] = "Low-cost power regions"
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

    for year in np.arange(START_YEAR, END_YEAR + 1):

        stack = (
            importer.get_asset_stack(year)
            .drop(columns=["cuf", "asset_lifetime"])
            .rename({"technology": "technology_destination"}, axis=1)
        )

        # Map low-cost power regions to corresponding regions
        stack["region"] = stack["region"].apply(lambda x: map_low_cost_power_regions(x)) #type: ignore

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


def map_low_cost_power_regions(low_cost_power_region: str, map_type):

    if map_type == "to_region":
        return {
            "Australia": "Oceania",
            "Saudi Arabia": "Middle East",
            "Brazil": "Latin America",
            "Namibia": "Africa",
            "Africa": "Africa",
            "China": "China",
            "Europe": "Europe",
            "India": "India",
            "Latin America": "Latin America",
            "Middle East": "Middle East",
            "North America": "North America",
            "Oceania": "Oceania",
            "Russia": "Russia",
            "Rest of Asia": "Rest of Asia",
        }[low_cost_power_region]

    if map_type == "to_category":
        category = "Low-cost power regions"
        return {
            "Australia": category,
            "Saudi Arabia": category,
            "Brazil": category,
            "Namibia": category,
            "Africa": "Africa",
            "China": "China",
            "Europe": "Europe",
            "India": "India",
            "Latin America": "Latin America",
            "Middle East": "Middle East",
            "North America": "North America",
            "Oceania": "Oceania",
            "Russia": "Russia",
            "Rest of Asia": "Rest of Asia",
            "All": "All",
            "Low-cost power regions": "Low-cost power regions",
        }[low_cost_power_region]

    if map_type == "to_same":
        return {
            "Australia": "Australia",
            "Saudi Arabia": "Saudi Arabia",
            "Brazil": "Brazil",
            "Namibia": "Namibia",
            "Africa": "Africa",
            "China": "China",
            "Europe": "Europe",
            "India": "India",
            "Latin America": "Latin America",
            "Middle East": "Middle East",
            "North America": "North America",
            "Oceania": "Oceania",
            "Russia": "Russia",
            "Rest of Asia": "Rest of Asia",
        }[low_cost_power_region]


def get_regions_with_lcprs():
    return [
        "Africa",
        "China",
        "Europe",
        "India",
        "Latin America",
        "Middle East",
        "North America",
        "Oceania",
        "Russia",
        "Rest of Asia",
        "Australia",
        "Namibia",
        "Brazil",
        "Saudi Arabia",
    ]


def _calculate_emissions_intensity_abatement(
    importer: IntermediateDataImporter, sector: str, pathway, agg_vars=[]
) -> pd.DataFrame:
    """Calculate the abatement of emissions intensity contributed by each type of supply technology, including circularity.
    Expressed in terms of ammonia. Regional breakdown non-sensical because of trade flows."""

    df = pd.DataFrame()

    # Get the stack in every year and sum annual production volume by supply technology
    for year in np.arange(START_YEAR, END_YEAR + 1):

        df_stack = (
            importer.get_asset_stack(year)
            .drop(columns=["cuf", "asset_lifetime"])
            .rename({"technology": "technology_destination"}, axis=1)
        )

        # Map low-cost power regions to their corresponding regions
        df_stack["region"] = df_stack["region"].apply(
            lambda x: map_low_cost_power_regions(x, "to_region")
        )

        df_stack = add_ammonia_type_to_df(df_stack)

        df_stack = (
            df_stack.groupby(["product", "region", "technology_destination"])
            .sum()["annual_production_volume"]
            .reset_index(drop=False)
        )
        df_stack["year"] = year
        df = pd.concat([df_stack, df])

    df_stacks = df.copy()

    # Add baseline technology (always SMR apart from goal gasification with CCS)
    df["technology_baseline"] = np.where(
        df["technology_destination"].str.contains("Coal"),
        "Coal Gasification + ammonia synthesis",
        "Natural Gas SMR + ammonia synthesis",
    )

    # Add emission factor difference between destination and baseline technology
    df_emissions = importer.get_emissions()
    col_names = ["technology", "co2_scope1", "co2_scope2"]
    df_emissions = df_emissions[["product", "region", "year"] + col_names]

    for suffix in ["destination", "baseline"]:
        df = df.merge(
            df_emissions.rename(
                {col_name: f"{col_name}_{suffix}" for col_name in col_names}, axis=1
            ),
            on=["product", "region", "year", f"technology_{suffix}"],
            how="left",
        )

    # Calculate emissions intensity reduced by each supply technology
    df["emission_intensity_reduction"] = (
        df["co2_scope1_baseline"] + df["co2_scope2_baseline"]
    ) - (df["co2_scope1_destination"] + df["co2_scope2_destination"])

    # Aggregate by type of supply technology
    df["emissions_abated"] = (
        df["emission_intensity_reduction"] * df["annual_production_volume"]
    )  # MtCO2
    df_production = df.copy()
    df = add_ammonia_type_to_df(df)
    df = (
        df.groupby(agg_vars + ["year", "ammonia_type"])
        .sum()["emissions_abated"]
        .reset_index(drop=False)
    )

    # Total emissions reduced by circularity lever is demand reduced by circularity multiplied with unabated emissions intensity
    df_unabated = calculate_unabated_emissions_intensity(
        df_stacks, df_emissions, agg_vars
    )

    if CIRCULARITY_IN_DEMAND[pathway]:
        df_circularity = importer.get_circularity_driver()
        if "region" not in agg_vars:
            df_circularity = df_circularity.loc[df_circularity["region"] == "Global"]
        if "region" in agg_vars:
            df_circularity = df_circularity.loc[df_circularity["region"] != "Global"]
        if "product" not in agg_vars:
            df_circularity["circularity_demand"] = df_circularity.apply(
                lambda row: conversion_factor_to_ammonia(row)
                * row["circularity_demand"],
                axis=1,
            )
            df_circularity["product"] = "All"
            df_circularity = (
                df_circularity.groupby(agg_vars + ["product", "year"])
                .sum()["circularity_demand"]
                .reset_index(drop=False)
            )

        df_abated_circularity = df_unabated.merge(
            df_circularity, on=agg_vars + ["year"], how="left"
        )
        df_abated_circularity["emissions_abated"] = (
            -df_abated_circularity["emissions_intensity_abated"]
            * df_abated_circularity["circularity_demand"]
        )
        df_abated_circularity["ammonia_type"] = "circularity"
        df = pd.concat(
            [
                df,
                df_abated_circularity[
                    agg_vars + ["year", "ammonia_type", "emissions_abated"]
                ],
            ]
        )

    # Calculate abated emissions intensity by dividing with total production volume
    df_production["annual_production_volume"] = df_production.apply(
        lambda row: conversion_factor_to_ammonia(row) * row["annual_production_volume"],
        axis=1,
    )

    df_production = (
        df_production.groupby(agg_vars + ["year"])
        .sum()["annual_production_volume"]
        .reset_index(drop=False)
        .rename({"annual_production_volume": "total_annual_production_volume"}, axis=1)
    )
    df = df.merge(df_production, on=agg_vars + ["year"], how="left")
    df["product"] = "All"

    df["emissions_intensity_abated"] = (
        df["emissions_abated"] / df["total_annual_production_volume"]
    )

    # Add unabated emissions intensity
    df = pd.concat(
        [
            df,
            df_unabated[
                agg_vars + ["year", "ammonia_type", "emissions_intensity_abated"]
            ],
        ]
    ).fillna(0)

    # Add a dummy for non-existent ammonia types
    ammonia_types = [
        "transitional",
        "green",
        "blue",
        "bio-based",
        "methane pyrolysis",
    ]
    if "region" not in agg_vars:
        df["region"] = "All"

    for region in df["region"].unique():
        for ammonia_type in ammonia_types:
            if (
                ammonia_type
                not in df.loc[df["region"] == region, "ammonia_type"].unique()
            ):
                df_zero_line = pd.DataFrame(
                    {
                        "region": [region],
                        "year": [2050],
                        "ammonia_type": [ammonia_type],
                        "emissions_abated": [0.0],
                        "total_annual_production_volume": [0.0],
                        "product": ["All"],
                        "emissions_intensity_abated": [0.0],
                    }
                )
                df = pd.concat([df, df_zero_line])

    # Pivot table
    df["sector"] = sector
    df["product"] = "All"
    df["parameter_group"] = "Abated emissions intensity"
    df["parameter"] = df["ammonia_type"].apply(
        lambda x: apply_parameter_map_ammonia_type(x)
    )
    if "region" not in agg_vars:
        df["region"] = "All"
    df["technology"] = "All"
    df["unit"] = "tCO2/tNH3"
    index = [
        "sector",
        "product",
        "region",
        "technology",
        "parameter_group",
        "parameter",
        "unit",
    ]

    df_pivot = (
        df.pivot_table(index=index, columns="year", values="emissions_intensity_abated")
        .fillna(0)
        .reset_index(drop=False)
    )

    # Calculate unabated emissions intensity
    if "region" in agg_vars:
        regions = df_pivot["region"].unique()
    else:
        regions = ["All"]

    df_pivot = df_pivot.set_index(
        [i for i in index if i not in ["region", "parameter"]]
    )

    for region in regions:
        for ammonia_type in [
            item
            for item in df_pivot.loc[df_pivot["region"] == region, "parameter"].unique()
            if item not in ["All ammonia", "Demand side circularity/ efficiency"]
        ]:
            df_pivot.loc[
                (df_pivot["parameter"] == "All ammonia")
                & (df_pivot["region"] == region),
                START_YEAR:END_YEAR,
            ] -= df_pivot.loc[
                (df_pivot["region"] == region)
                & (df_pivot["parameter"] == ammonia_type),
                START_YEAR:END_YEAR,
            ]

    df_pivot["parameter"] = df_pivot["parameter"].replace(
        {"All ammonia": "Unabated emissions intensity"}
    )

    # Drop grey ammonia (zero abated emissions intensity)
    df_pivot = df_pivot.reset_index()
    df_pivot = df_pivot.loc[df_pivot["parameter"] != "Grey ammonia"]
    df_pivot = df_pivot.set_index(index)

    return df_pivot


def calculate_unabated_emissions_intensity(
    df_stacks: pd.DataFrame, df_emissions: pd.DataFrame, agg_vars: list
) -> pd.DataFrame:

    # Calculate unabated emissions intensity as difference between total emissions intensity and intensity abatements
    df_stacks["technology_destination"] = np.where(
        df_stacks["technology_destination"].str.contains("Coal"),
        "Coal Gasification + ammonia synthesis",
        "Natural Gas SMR + ammonia synthesis",
    )
    df_stacks = df_stacks.merge(
        df_emissions.rename({"technology": "technology_destination"}, axis=1),
        on=["product", "region", "year", "technology_destination"],
    )

    df_stacks["total_emissions"] = (
        df_stacks["co2_scope1"] + df_stacks["co2_scope2"]
    ) * df_stacks["annual_production_volume"]
    df_stacks["annual_production_volume"] = df_stacks.apply(
        lambda row: conversion_factor_to_ammonia(row) * row["annual_production_volume"],
        axis=1,
    )
    df_stacks["product"] = "All"
    df_stacks = (
        df_stacks.groupby(agg_vars + ["year"])
        .sum()[["annual_production_volume", "total_emissions"]]
        .reset_index()
    )
    df_stacks["emissions_intensity_abated"] = (
        df_stacks["total_emissions"] / df_stacks["annual_production_volume"]
    )
    df_stacks["ammonia_type"] = "all"

    return df_stacks


def conversion_factor_to_ammonia(row: pd.Series) -> float:
    if row["product"] == "Ammonium nitrate":
        return AMMONIA_PER_AMMONIUM_NITRATE
    if row["product"] == "Urea":
        return AMMONIA_PER_UREA
    return 1


def apply_parameter_map_ammonia_type(ammonia_type):

    parameter_map = {
        "green": "Green ammonia",
        "blue": "Blue ammonia",
        "methane pyrolysis": "Methane pyrolysis",
        "bio-based": "Bio-based production",
        "transitional": "Transitional technologies",
        "grey": "Grey ammonia",
        "all": "All ammonia",
        "circularity": "Demand side circularity/ efficiency",
    }
    return parameter_map[ammonia_type]


def calculate_investment_dedicated_renewables(
    importer: IntermediateDataImporter,
    df_electricity: pd.DataFrame,
    agg_vars=["product", "region", "technology"],
) -> pd.DataFrame:
    """Calculate direct investment into dedicated renewables from electricity consumption from on-site VREs."""

    # Filter outputs table for electricity consumption from on site VREs
    df = df_electricity.loc[
        (df_electricity["parameter_group"] == "Resource consumption")
        & (df_electricity["parameter"] == "Electricity - on site VREs")
    ]

    # Summing by region can only be done at the end because solar and wind shares, CFs and CAPEX are region-specific#
    agg_vars_initial = agg_vars.copy()
    if "region" not in agg_vars:
        agg_vars += ["region"]

    # Filter outputs table for the right aggregation level
    for var in ["product", "region", "technology"]:
        if var not in agg_vars:
            df = df.loc[df[var] == "All"]
        else:
            df = df.loc[df[var] != "All"]

    # Convert PJ into TWh
    df["value"] = df["value"] / 3.6

    # Calculate additional electricity demand in each year
    df = df.pivot_table(
        index=agg_vars + ["parameter_group", "parameter", "unit"],
        columns="year",
        values="value",
    ).fillna(0)

    for year in [y for y in np.arange(START_YEAR, END_YEAR + 1) if y not in df.columns]:
        df[year] = 0
    df = df.reindex(sorted(df.columns), axis=1)

    for year in np.flip(np.arange(START_YEAR + 1, END_YEAR + 1)):
        df[year] = df[year] - df[year - 1]

    df = df.melt(
        value_name="additional_electricity_TWh", var_name="year", ignore_index=False
    ).reset_index(drop=False)

    # Required wind and solar capacity addition is share of wind/solar in electricity consumption divided by capacity factor
    df_solar_wind = importer.get_solar_wind_shares_cfs()
    df = df.merge(df_solar_wind, on=["region"], how="left")
    df["solar_capacity_addition_GW"] = (
        1e3
        * df["additional_electricity_TWh"]
        * df["solar_share"]
        / (365 * 24 * df["solar_cf"])
    )
    df["wind_capacity_addition_GW"] = (
        1e3
        * df["additional_electricity_TWh"]
        * df["wind_share"]
        / (365 * 24 * df["wind_cf"])
    )

    # Calculate investment to install the additional capacity
    df_solar_capex = importer.get_solar_capex()  # in USD/kW
    df_wind_capex = importer.get_wind_capex()  # in USD/kW
    df = df.merge(df_solar_capex, on=["region", "year"], how="left")
    df = df.merge(df_wind_capex, on=["region", "year"], how="left")
    df["solar_investment"] = 1e6 * df["solar_capex"] * df["solar_capacity_addition_GW"]
    df["wind_investment"] = 1e6 * df["wind_capex"] * df["wind_capacity_addition_GW"]

    # If the investment is negative (corresponding to declining electricity demand), set to zero
    df["solar_investment"] = np.where(
        df["solar_investment"] < 0, 0, df["solar_investment"]
    )
    df["wind_investment"] = np.where(
        df["wind_investment"] < 0, 0, df["wind_investment"]
    )

    # Sum solar and wind investment and aggregate as required
    df["value"] = df["solar_investment"] + df["wind_investment"]

    # Map low-cost power regions to individual category
    df["region"] = df["region"].apply(
        lambda x: map_low_cost_power_regions(x, "to_category")
    )

    # Sum to total investment according to aggregation
    df = df.groupby(agg_vars_initial + ["year"]).sum()["value"].reset_index(drop=False)

    # Pivot table
    df["parameter_group"] = "Investment"
    df["parameter"] = "Dedicated renewables investment"
    df["unit"] = "USD"
    for var in ["product", "region", "technology"]:
        if var not in agg_vars_initial:
            df[var] = "All"
    df["sector"] = SECTOR

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
    ).fillna(0)

    return df_pivot


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
    df["product"] = "All"
    df["unit"] = "MtNH3"

    # df_test = df.groupby("year").sum()

    return df


def calculate_annual_production_volume_by_ammonia_type(
    df: pd.DataFrame, agg_vars=["product", "region"]
) -> pd.DataFrame:
    """Aggregate annual production volume by ammonia type, optionally split by product and region"""

    # Filter outputs table for annual production volume
    df = df.loc[
        (df["parameter_group"] == "Production")
        & (df["parameter"] == "Annual production volume")
    ]

    # Filter outputs table for the right products aggregation
    if "product" in agg_vars:
        df = df.loc[df["product"] != "All"]
    else:
        df = df.loc[df["product"] == "All"]

    # agg_vars = [agg_var for agg_var in agg_vars if agg_var != "product"]

    # Sum annual production volume by ammonia type and optionally by region
    df = add_ammonia_type_to_df(
        df.rename({"technology": "technology_destination"}, axis=1)
    )
    df = df.groupby(agg_vars + ["year", "ammonia_type"]).sum().reset_index(drop=False)

    # Fill missing types with zeros for every region
    ammonia_types = [
        "grey",
        "transitional",
        "blue",
        "green",
        "bio-based",
        "methane pyrolysis",
    ]
    if "region" not in agg_vars:
        df["region"] = "All"

    for region in df["region"].unique():
        for ammonia_type in ammonia_types:
            if (
                ammonia_type
                not in df.loc[df["region"] == region, "ammonia_type"].unique()
            ):
                df_zero_line = pd.DataFrame(
                    {
                        "region": [region],
                        "year": [2050],
                        "ammonia_type": [ammonia_type],
                        "value": [0.0],
                    }
                )

                df = pd.concat([df, df_zero_line])

    df["parameter_group"] = "Production volume by ammonia type"
    df["parameter"] = df["ammonia_type"].apply(
        lambda x: apply_parameter_map_ammonia_type(x)
    )
    df["sector"] = SECTOR
    df["technology"] = "All"
    df["unit"] = "Mt"

    if "product" not in agg_vars:
        df["product"] = "All"

    return df.drop(columns=["ammonia_type"])

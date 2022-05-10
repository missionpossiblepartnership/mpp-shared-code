""" Process outputs to standardised output table."""
import pandas as pd

from mppshared.config import (
    ANNUAL_RENOVATION_SHARE,
    COST_METRIC_CUF_ADJUSTMENT,
    CUF_LOWER_THRESHOLD,
    CUF_UPPER_THRESHOLD,
    END_YEAR,
    GHGS,
    INVESTMENT_CYCLES,
    LOG_LEVEL,
    PRODUCTS,
    RANKING_CONFIG,
    REGIONAL_PRODUCTION_SHARES,
    SECTOR,
    SECTORAL_CARBON_BUDGETS,
    EMISSION_SCOPES,
    START_YEAR,
    TECHNOLOGY_MORATORIUM,
    TECHNOLOGY_RAMP_UP_CONSTRAINTS,
    TRANSITIONAL_PERIOD_YEARS,
    YEAR_2050_EMISSIONS_CONSTRAINT,
)
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
        df_stack.groupby(["product", "region", "technology"]).count()["asset"].reset_index()
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
        df_stack.groupby(["product", "region", "technology"]).sum()["annual_production_volume"].reset_index()
    )

    # Add parameter descriptions
    df_stack.rename(
        columns={"annual_production_volume": "value"}, inplace=True
    )

    df_stack["parameter_group"] = "Production"
    df_stack["parameter"] = "Annual production volume"
    df_stack["unit"] = "Mt"
    
    return df_stack


def _calculate_emissions(df_stack: pd.DataFrame, df_emissions: pd.DataFrame, agg_vars=["product", "region", "technology"]) -> pd.DataFrame:
    """Calculate emissions for all GHGs and scopes by production, region and technology"""

    logger.info("-- Calculating emissions")

    # Emissions are the emissions factor multiplied with the annual production volume
    df_stack = df_stack.merge(
        df_emissions, on=["product", "region", "technology"]
    )
    scopes = [f"{ghg}_{scope}" for scope in EMISSION_SCOPES for ghg in GHGS]

    for scope in scopes:
        df_stack[scope] = (
            df_stack[scope] * df_stack["annual_production_volume"]
        )
    
    df_stack = (
        df_stack.groupby(agg_vars)[scopes + ["annual_production_volume"]]
        .sum().reset_index()
    )

    df_stack = df_stack.melt(
        id_vars=agg_vars,
        value_vars=scopes,
        var_name="parameter",
        value_name="value",
    )

    # Add unit and parameter group
    map_unit = {f"{ghg}_{scope}": f"Mt {str.upper(ghg)}" for scope in EMISSION_SCOPES for ghg in GHGS}
    map_rename = {f"{ghg}_{scope}": f"{str.upper(ghg)} {str.capitalize(scope).replace('_', ' ')}" for scope in EMISSION_SCOPES for ghg in GHGS}

    df_stack["parameter_group"] = "Emissions"
    df_stack["unit"] = df_stack["parameter"].apply(lambda x: map_unit[x])
    df_stack["parameter"] = df_stack["parameter"].replace(map_rename)
    if "technology" not in agg_vars:
        df_stack["technology"] = "All"

    return df_stack

def _calculate_co2_captured(df_stack: pd.DataFrame, df_emissions: pd.DataFrame, agg_vars=["product", "region", "technology"]) -> pd.DataFrame:
    """Calculate captured CO2 by product, region and technology for a given asset stack"""

    logger.info("--Calculating CO2 captured")

    # Captured CO2 by technology is calculated by multiplying with the annual production volume
    df_stack = df_stack.merge(
        df_emissions, on=["product", "region", "technology"]
        )    
    df_stack["co2_scope1_captured"] = df_stack["co2_scope1_captured"] * df_stack["annual_production_volume"]

    df_stack = (
        df_stack.groupby(agg_vars)["co2_scope1_captured"].sum().reset_index()
    )

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


def _calculate_emissions_intensity(df_stack: pd.DataFrame, df_emissions: pd.DataFrame, agg_vars=["product", "region", "technology"])->pd.DataFrame:
    """Calculate emissions intensity for a given stack (can also be aggregated by technology by omitting this variable in agg_vars)"""
    
    logger.info("-- Calculating emissions intensity")

    # Emissions are the emissions factor multiplied with the annual production volume
    df_stack = df_stack.merge(
        df_emissions, on=["product", "region", "technology"]
    )
    scopes = [f"{ghg}_{scope}" for scope in EMISSION_SCOPES for ghg in GHGS]

    for scope in scopes:
        df_stack[scope] = (
            df_stack[scope] * df_stack["annual_production_volume"]
        )
    
    df_stack = (
        df_stack.groupby(agg_vars)[scopes + ["annual_production_volume"]]
        .sum().reset_index()
    )

    # Emissions intensity is the emissions divided by annual production volume
    for scope in scopes:
        df_stack[f"emissions_intensity_{scope}"] = df_stack[scope] / df_stack["annual_production_volume"]

    df_stack = df_stack.melt(
        id_vars=agg_vars,
        value_vars=[f"emissions_intensity_{scope}" for scope in scopes],
        var_name="parameter",
        value_name="value",
    )

    # Add unit and parameter group
    map_unit = {f"emissions_intensity_{ghg}_{scope}": f"t{str.upper(ghg)}/t" for scope in EMISSION_SCOPES for ghg in GHGS}
    map_rename = {f"emissions_intensity_{ghg}_{scope}": 
    f"Emissions intensity {str.upper(ghg)} {str.capitalize(scope).replace('_', ' ')}" for scope in EMISSION_SCOPES for ghg in GHGS
    }

    df_stack["parameter_group"] = "Emissions intensity"
    df_stack["unit"] = df_stack["parameter"].apply(lambda x: map_unit[x])
    df_stack["parameter"] = df_stack["parameter"].replace(map_rename)
    if "technology" not in agg_vars:
        df_stack["technology"] = "All"

    return df_stack
    


def _calculate_lcox(df_stack, df_transitions):
    logger.info("-- Calculating LCOX")
    df_assets_lcox = df_stack.merge(
        df_transitions,
        left_on=["product", "region", "technology"],
        right_on=["product", "region", "technology_destination"],
    )
    df_stack_lcox = (
        df_assets_lcox.groupby(["product", "region", "technology"]).sum().reset_index()
    )
    df_stack_lcox.rename(columns={"lcox": "value"}, inplace=True)
    df_stack_lcox["parameter"] = "LCOX"
    df_stack_lcox["unit"] = "USD/t"
    df_stack_lcox["parameter_group"] = "Cost"
    return df_stack_lcox


def _calculate_resource_consumption(
    df_stack: pd.DataFrame, df_inputs_outputs: pd.DataFrame, resource: str, year: int,
agg_vars=["product", "region", "technology"]
) -> pd.DataFrame:
    """ Calculate the consumption of a given resource in a given year, optionally grouped by specific variables."""
    
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
        "Energy": "GJ",
        "Raw material": "GJ",
        "H2 storage": "GJ",
        "Cost": "USD"
    }
    df_stack["unit"] = df_stack["parameter_group"].apply(lambda x: unit_map[x])
    
    if "technology" not in agg_vars:
        df_stack["technology"] = "All"
    
    return df_stack


def create_table_all_data_year(year: int, importer: IntermediateDataImporter) -> pd.DataFrame:
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
    df_emissions_intensity_all_tech = _calculate_emissions_intensity(df_stack, df_emissions, agg_vars=["product", "region"])
    df_co2_captured = _calculate_co2_captured(df_stack, df_emissions)

    
    # Calculate feedstock and energy consumption
    df_inputs_outputs = importer.get_inputs_outputs()
    data_variables = []

    for resource in df_inputs_outputs["parameter"].unique():
        df_stack_variable = _calculate_resource_consumption(
            df_stack, df_inputs_outputs, resource, year, agg_vars=["product", "region", "technology"]
        )
        df_stack_variable["parameter"] = resource
        data_variables.append(df_stack_variable)

    df_inputs = pd.concat(data_variables)
    
    # Calculate LCOX
    df_transitions = importer.get_technology_transitions_and_cost()
    df_transitions = df_transitions[df_transitions["year"] == year]
    df_stack_lcox = _calculate_lcox(df_stack, df_transitions)

    # Concatenate all the output tables
    df_all_data_year = pd.concat(
        [
            df_total_assets,
            df_production_capacity,
            df_stack_emissions,
            df_emissions_intensity,
            df_emissions_intensity_all_tech,
            df_co2_captured,
            df_stack_lcox,
            df_inputs,
        ]
    )
    return df_all_data_year


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
    importer.export_data(df_transitions, f"asset_transition_sequences_sensitivity_{sensitivity}.csv", "final")

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
    df_pivot.reset_index(inplace=True)
    df_pivot.fillna(0, inplace=True)

    suffix = f"{sector}_{pathway}_{sensitivity}"

    importer.export_data(
        df_pivot, f"simulation_outputs_{suffix}.csv", "final", index=False
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

def write_key_assumptions_to_txt(pathway: str, sector: str, importer: IntermediateDataImporter):
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
        f"Transitional period years: {TRANSITIONAL_PERIOD_YEARS[sector]}"
    ]
    
    path = importer.final_path.joinpath("configuration.txt")
    with open(path, "w") as f:
        for line in lines:
            f.write(line)
            f.write('\n')
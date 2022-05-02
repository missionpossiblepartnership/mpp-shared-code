""" Process outputs to standardised output table."""
import pandas as pd
from pandas import CategoricalDtype
import numpy as np
import plotly.express as px
from plotly.offline import plot
from plotly.subplots import make_subplots

from mppshared.config import (
    END_YEAR,
    LOG_LEVEL,
    PRODUCTS,
    SECTOR,
    SECTORAL_CARBON_BUDGETS,
    EMISSION_SCOPES,
    START_YEAR,
)
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def create_table_asset_transition_sequences(importer: IntermediateDataImporter) -> pd.DataFrame:
    
    # Get initial stack and melt to long for that year
    multiindex = ["uuid", "product", "region", "parameter"]
    df = importer.get_asset_stack(START_YEAR) 
    df = df[["uuid", "product", "region", "technology", "annual_production_capacity", "annual_production_volume", "retrofit_status"]]  
    df = df.set_index(["product", "region", "uuid"])
    df = df.melt(var_name="parameter", value_name=START_YEAR, ignore_index=False)
    df = df.sort_index()
    df = df.reset_index(drop=False).set_index(multiindex)
    
    for year in np.arange(START_YEAR+1, END_YEAR + 1):

        # Get asset stack for that year
        df_stack = importer.get_asset_stack(year=year)
        df_stack = df_stack[["uuid", "product", "region", "technology", "annual_production_capacity", "annual_production_volume", "retrofit_status", "rebuild_status"]]  
        
        # Reformat stack DataFrame
        df_stack = df_stack.set_index(["product", "region", "uuid"])
        df_stack = df_stack.melt(var_name="parameter", value_name=year, ignore_index=False)
        df_stack = df_stack.reset_index().set_index("uuid")
        df_stack = df_stack.sort_index()

        # Differentiate between existing and new assets
        previous_uuids = df.index.unique()
        current_uuids = df_stack.index.unique()

        existing_uuids = [uuid for uuid in current_uuids if uuid in previous_uuids]
        new_uuids = [uuid for uuid in current_uuids if uuid not in previous_uuids]
        vanished_uuids = [uuid for uuid in previous_uuids if uuid not in current_uuids] # Decommissioned assets (not relevant)

        newbuild_stack = df_stack[df_stack.index.isin(new_uuids)].reset_index().set_index(multiindex).sort_index()
        existing_stack = df_stack[df_stack.index.isin(existing_uuids)].reset_index().set_index(multiindex).sort_index()

        # Join existing stack and add newbuild stack
        df[year] = existing_stack[year]
        df = pd.concat([df, newbuild_stack])

    return df

def _calculate_number_of_assets(df_stack):
    logger.info("-- Calculating number of assets")
    # Calculate the number of assets for each region, product and technology
    df_stack["asset"] = 1
    df_stack_total_assets = (
        df_stack.groupby(["product", "region", "technology"]).count().reset_index()
    )
    df_stack_total_assets.rename(columns={"asset": "value"}, inplace=True)
    df_stack_total_assets["parameter"] = "Number of plants"
    df_stack_total_assets["unit"] = "plant"
    df_stack_total_assets["parameter_group"] = "Production"
    return df_stack_total_assets


def _calculate_production_volume(df_stack):
    logger.info("-- Calculating production volume")
    # Calculate the production volume per region, product and technology
    df_stack_production_capacity = (
        df_stack.groupby(["product", "region", "technology"]).sum().reset_index()
    )
    df_stack_production_capacity.rename(
        columns={"annual_production_volume": "value"}, inplace=True
    )
    df_stack_production_capacity["parameter"] = "Annual production volume"
    df_stack_production_capacity["unit"] = "Mt"
    df_stack_production_capacity["parameter_group"] = "Production"
    return df_stack_production_capacity


def _calculate_emissions(df_stack, df_emissions):
    logger.info("-- Calculating emissions")
    # Calculate the carbon emissions per region, product and technology
    df_assets_emissions = df_stack.merge(
        df_emissions, on=["product", "region", "technology"]
    )
    df_assets_emissions["co2_scope1"] = (
        df_assets_emissions["co2_scope1"]
        * df_assets_emissions["annual_production_volume"]
    )
    df_assets_emissions["co2_scope2"] = (
        df_assets_emissions["co2_scope2"]
        * df_assets_emissions["annual_production_volume"]
    )
    df_assets_emissions["co2_scope3_upstream"] = (
        df_assets_emissions["co2_scope3_upstream"]
        * df_assets_emissions["annual_production_volume"]
    )
    df_assets_emissions["co2_scope3_downstream"] = (
        df_assets_emissions["co2_scope3_downstream"]
        * df_assets_emissions["annual_production_volume"]
    )
    df_stack_emissions = (
        df_assets_emissions.groupby(["product", "region", "technology"])
        .sum()
        .reset_index()
    )
    df_stack_emissions_emitted = df_stack_emissions.melt(
        id_vars=["product", "region", "technology"],
        value_vars=[
            "co2_scope1",
            "co2_scope2",
            "co2_scope3_upstream",
            "co2_scope3_downstream",
        ],
        var_name="parameter",
        value_name="value",
    )
    df_stack_emissions_emitted["unit"] = "t"
    df_stack_emissions_emitted["parameter_group"] = "Emissions"
    df_stack_capture_emissions = df_stack_emissions.melt(
        id_vars=["product", "region", "technology"],
        value_vars=[
            "co2_scope1_captured",
        ],
        var_name="parameter",
        value_name="value",
    )
    df_stack_capture_emissions["unit"] = "t"
    df_stack_capture_emissions["parameter_group"] = "Emissions"
    return df_stack_emissions_emitted, df_stack_capture_emissions


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
    df_stack_lcox["parameter"] = "lcox"
    df_stack_lcox["unit"] = "USD/t"
    df_stack_lcox["parameter_group"] = "finance"
    return df_stack_lcox


def _calculate_output_from_input(df_stack, df_inputs_outputs, variable, year):
    logger.info(f"-- Calculating {variable}")
    df_variable = df_inputs_outputs.loc[
        (df_inputs_outputs["parameter"] == variable)
        & (df_inputs_outputs["year"] == year)
    ].copy()
    df_stack = df_stack.merge(df_variable, on=["product", "region", "technology"])
    df_stack["value"] = df_stack["value"] * df_stack["annual_production_volume"]
    df_stack_variable = (
        df_stack.groupby(["product", "region", "technology"]).sum().reset_index()
    )
    df_stack_variable["parameter_group"] = "finance"
    df_stack_variable["unit"] = df_variable["unit"].iloc[0]
    return df_stack_variable


def create_table_all_data_year(year, importer):
    df_stack = importer.get_asset_stack(year)
    df_stack_total_assets = _calculate_number_of_assets(df_stack)
    df_stack_production_capacity = _calculate_production_volume(df_stack)
    df_emissions = importer.get_emissions()
    df_emissions = df_emissions[df_emissions["year"] == year]
    df_stack_emissions_emitted, df_stack_capture_emissions = _calculate_emissions(
        df_stack, df_emissions
    )
    df_transitions = importer.get_technology_transitions_and_cost()
    df_transitions = df_transitions[df_transitions["year"] == year]
    df_stack_lcox = _calculate_lcox(df_stack, df_transitions)
    df_inputs_outputs = importer.get_inputs_outputs()
    data_variables = []
    for variable in df_inputs_outputs["parameter"].unique():
        df_stack_variable = _calculate_output_from_input(
            df_stack, df_inputs_outputs, variable, year
        )
        df_stack_variable["parameter"] = variable
        data_variables.append(df_stack_variable)
    df_variables = pd.concat(data_variables)
    df_variables = df_variables[
        [
            "product",
            "region",
            "technology",
            "parameter_group",
            "parameter",
            "unit",
            "value",
        ]
    ]
    df_all_data_year = pd.concat(
        [
            df_stack_total_assets,
            df_stack_production_capacity,
            df_stack_emissions_emitted,
            df_stack_capture_emissions,
            df_stack_lcox,
            df_variables,
        ]
    )
    return df_all_data_year


def calculate_outputs(pathway, sensitivity, sector):
    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS[sector],
    )

    # Create summary table of asset transitions
    logger.info("Creating table with asset transition sequences.")
    df_transitions = create_table_asset_transition_sequences(importer)
    importer.export_data(df_transitions, f"asset_transition_sequences_sensitivity_{sensitivity}.csv", "final")

    # Create output table
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
    df_pivot.reset_index(inplace=True)
    df_pivot.fillna(0, inplace=True)
    importer.export_data(
        df_pivot, f"simulation_outputs_sensitivity_{sensitivity}.csv", "final"
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
        df[columns], f"interface_outputs_sensitivity_{sensitivity}.csv", "final"
    )
    importer.export_data(
        df_stacks, f"plant_stack_transition_sensitivity_{sensitivity}.csv", "final"
    )
    logger.info("All data for all years processed.")

def create_debugging_outputs(pathway: str, sensitivity: str, sector: str):
    """Create technology roadmap and emissions trajectory for quick debugging and refinement."""

    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS[sector],
    )

    output_emissions_trajectory(importer)
    output_technology_roadmap(importer)

def output_technology_roadmap(importer: IntermediateDataImporter):
    df_roadmap = create_technology_roadmap(importer)
    importer.export_data(df_roadmap, "technology_roadmap.csv", "final")
    plot_technology_roadmap(importer=importer, df_roadmap=df_roadmap)

def output_emissions_trajectory(importer: IntermediateDataImporter):
    df_trajectory = create_emissions_trajectory(importer)
    df_wide = pd.pivot_table(df_trajectory, values="value", index="variable", columns="year")
    importer.export_data(df_wide, "emissions_trajectory.csv", "final")
    plot_emissions_trajectory(importer=importer, df_trajectory=df_trajectory)

def create_technology_roadmap(importer: IntermediateDataImporter) -> pd.DataFrame:
    """Create technology roadmap that shows evolution of stack (supply mix) over model horizon."""

    # TODO: filter by product
    # Annual production volume in MtNH3 by technology
    technologies = importer.get_technology_characteristics()[
        "technology"
    ].unique()
    df_roadmap = pd.DataFrame(data={"technology": technologies})

    for year in np.arange(START_YEAR, END_YEAR + 1):

        # Group by technology and sum annual production volume
        df_stack = importer.get_asset_stack(year=year)
        df_sum = df_stack.groupby(["technology"], as_index=False).sum()
        df_sum = df_sum[["technology", "annual_production_volume"]].rename(
            {"annual_production_volume": year}, axis=1
        )

        # Merge with roadmap DataFrame
        df_roadmap = df_roadmap.merge(df_sum, on=["technology"], how="left").fillna(
            0
        )

    # Sort technologies as required
    df_roadmap = df_roadmap.loc[~(df_roadmap["technology"]=="Waste Water to ammonium nitrate")]
    technologies = [
        "Natural Gas SMR + ammonia synthesis",
        "Coal Gasification + ammonia synthesis",
        "Natural Gas SMR + CCS (process emissions only) + ammonia synthesis",
        "Electrolyser + SMR + ammonia synthesis",
        "Electrolyser + Coal Gasification + ammonia synthesis",
        "Electrolyser - grid PPA + ammonia synthesis",
        "Electrolyser - dedicated VRES + grid PPA + ammonia synthesis",
        "Electrolyser - dedicated VRES + H2 storage - geological + ammonia synthesis",
        "Electrolyser - dedicated VRES + H2 storage - pipeline + ammonia synthesis",
        "Coal Gasification+ CCS + ammonia synthesis",
        "Natural Gas ATR + CCS + ammonia synthesis",
        "Oversized ATR + CCS",
        "Natural Gas SMR + CCS + ammonia synthesis",
        "ESMR Gas + CCS + ammonia synthesis",
        "GHR + CCS + ammonia synthesis",
        "Methane Pyrolysis + ammonia synthesis",
        "Biomass Digestion + ammonia synthesis",
        "Biomass Gasification + ammonia synthesis",
        "Waste to ammonia",
    ]
    tech_order = CategoricalDtype(
        technologies, ordered=True
    )
    df_roadmap["technology"] = df_roadmap["technology"].astype(tech_order)

    df_roadmap = df_roadmap.sort_values(["technology"])

    # Take out ammonia synthesis
    shortened_tech_names = {
        tech.replace(" + ammonia synthesis", ""): tech
        for tech in df_roadmap["technology"].unique()
    }
    df_roadmap["technology"] = df_roadmap["technology"].astype(str)
    df_roadmap["technology"] = df_roadmap["technology"].replace(shortened_tech_names)
    
    return df_roadmap

def plot_technology_roadmap(importer: IntermediateDataImporter, df_roadmap: pd.DataFrame):
    """Plot the technology roadmap and save as .html"""

    # Melt roadmap DataFrame for easy plotting
    df_roadmap = df_roadmap.melt(
        id_vars="technology", var_name="year", value_name="annual_volume"
    )

    fig = make_subplots()
    wedge_fig = px.area(df_roadmap, color="technology", x="year", y="annual_volume")

    fig.add_traces(wedge_fig.data)

    fig.layout.xaxis.title = "Year"
    fig.layout.yaxis.title = "Annual production volume (MtNH3/year)"
    fig.layout.title = "Technology roadmap"

    plot(
        fig,
        filename=str(importer.final_path.joinpath("technology_roadmap.html")),
        auto_open=False,
    )

def create_emissions_trajectory(importer: IntermediateDataImporter) -> pd.DataFrame:
    """Create emissions trajectory for scope 1, 2, 3 along with demand."""

    # Get emissions for each technology
    df_emissions = importer.get_emissions()
    df_trajectory = pd.DataFrame()
    
    greenhousegases = ["co2", "ch4", "n2o"]
    emission_cols = [f"{ghg}_{scope}" for ghg in greenhousegases for scope in EMISSION_SCOPES] + ["co2_scope1_captured"]

    for year in np.arange(START_YEAR, END_YEAR + 1):

        # Filter emissions for the year
        df_em = df_emissions.loc[df_emissions["year"]==year]

        # Calculate annual production volume by technology, merge with emissions and sum for each scope
        df_stack = importer.get_asset_stack(year=year)
        df_sum = df_stack.groupby(["product", "region", "technology"], as_index=True).sum()
        df_sum = df_sum[["annual_production_volume"]].reset_index()
        df_stack_emissions = df_sum.merge(df_em, on=["product", "technology", "region"], how="left")

        # Multiply production volume with emission factor for each region and technology
        for col in emission_cols:
            df_stack_emissions[f"emissions_{col}"] = df_stack_emissions["annual_production_volume"] * df_stack_emissions[col]

        # Melt to long format and concatenate
        cols_to_keep = [f"emissions_{col}" for col in emission_cols]
        df_total = df_stack_emissions.groupby("product").sum()[cols_to_keep]
        df_total = df_total.melt()
        df_total["year"] = year
        df_trajectory = pd.concat([df_total, df_trajectory], axis=0)

    return df_trajectory

def plot_emissions_trajectory(importer: IntermediateDataImporter, df_trajectory: pd.DataFrame):
    """Plot emissions trajectory."""

    fig = make_subplots()
    line_fig = px.line(df_trajectory, color="variable", x="year", y="value")

    fig.add_traces(line_fig.data)

    fig.layout.xaxis.title = "Year"
    fig.layout.yaxis.title = "Annual emissions (Mt GHG)"
    fig.layout.title = "Emission trajectory"

    plot(
        fig,
        filename=str(importer.final_path.joinpath("emission_trajectory.html")),
        auto_open=False,
    )

def sort_technologies_by_classification(df: pd.DataFrame) -> pd.DataFrame:
    """Sort technologies by conventional, transition, end-state.

    Args:
        df (pd.DataFrame): _description_

    Returns:
        pd.DataFrame: _description_
    """
    # TODO: read from Business Cases.xlsx
    tech_class = get_tech_classification()

    tech_class_inv = {
        tech: classification
        for (classification, tech_list) in tech_class.items()
        for tech in tech_list
    }

    # Add tech classification column and sort
    class_order = CategoricalDtype(
        ["Initial", "Transitional", "End-state"], ordered=True
    )
    df["tech_class"] = (
        df["technology"].apply(lambda x: tech_class_inv[x]).astype(class_order)
    )
    df = df.sort_values(["tech_class", "technology"])

    return df

def get_tech_classification() -> dict:
    return {
        "Initial": [
            "Natural Gas SMR + ammonia synthesis",
            "Coal Gasification + ammonia synthesis",
        ],
        "Transitional": [
            "Electrolyser + SMR + ammonia synthesis",
            "Electrolyser + Coal Gasification + ammonia synthesis",
            "Coal Gasification+ CCS + ammonia synthesis",
            "Natural Gas SMR + CCS (process emissions only) + ammonia synthesis",
        ],
        "End-state": [
            "Natural Gas ATR + CCS + ammonia synthesis",
            "GHR + CCS + ammonia synthesis",
            "ESMR Gas + CCS + ammonia synthesis",
            "Natural Gas SMR + CCS + ammonia synthesis",
            "Electrolyser - grid PPA + ammonia synthesis",
            "Biomass Digestion + ammonia synthesis",
            "Biomass Gasification + ammonia synthesis",
            "Methane Pyrolysis + ammonia synthesis",
            "Electrolyser - dedicated VRES + grid PPA + ammonia synthesis",
            "Electrolyser - dedicated VRES + H2 storage - geological + ammonia synthesis",
            "Electrolyser - dedicated VRES + H2 storage - pipeline + ammonia synthesis",
            "Waste Water to ammonium nitrate",
            "Waste to ammonia",
            "Oversized ATR + CCS",
        ],
    }

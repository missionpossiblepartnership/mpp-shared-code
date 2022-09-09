""" Process outputs to standardised output table."""

import numpy as np
import pandas as pd
import plotly.express as px
from plotly.offline import plot

from cement.config.config_cement import (
    EMISSION_SCOPES,
    END_YEAR,
    GHGS,
    PRODUCTS,
    START_YEAR,
    MODEL_YEARS,
)
from cement.config.plot_config_cement import TECHNOLOGY_LAYOUT
from mppshared.config import LOG_LEVEL
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.solver.debugging_outputs import create_table_asset_transition_sequences
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def calculate_outputs(pathway_name: str, sensitivity: str, sector: str, products: list):
    importer = IntermediateDataImporter(
        pathway_name=pathway_name,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS,
    )

    """ technology roadmap """
    logger.info("Post-processing technology roadmap")
    df_tech_roadmap = _create_tech_roadmaps_by_region(
        importer=importer, start_year=START_YEAR, end_year=END_YEAR
    )
    _export_and_plot_tech_roadmaps_by_region(
        pathway_name=pathway_name,
        sensitivity=sensitivity,
        importer=importer,
        df_roadmap=df_tech_roadmap,
        unit="Mt Clk",
        technology_layout=TECHNOLOGY_LAYOUT,
    )

    """ Emissions """
    logger.info("Post-processing emissions")
    df_total_emissions = _calculate_emissions_total(
        importer=importer, ghgs=GHGS, emission_scopes=EMISSION_SCOPES, format_data=False
    )
    _export_and_plot_emissions_by_region(
        pathway_name=pathway_name,
        sensitivity=sensitivity,
        importer=importer,
        df_total_emissions=df_total_emissions,
        ghgs=GHGS,
        emission_scopes=EMISSION_SCOPES,
        technology_layout=TECHNOLOGY_LAYOUT,
    )

    """ Cost """
    logger.info("Post-processing cost data")
    df_investments = _calculate_annual_investments(
        df_cost=importer.get_technology_transitions_and_cost(),
        importer=importer,
        sector=sector,
    )
    importer.export_data(
        df=df_investments,
        filename="pathway_investments.csv",
        export_dir="final/cost",
        index=True,
    )
    if pathway_name != "bau":
        df_additional_investments = _calculate_total_additional_investments(
            df_investments=df_investments,
            importer=importer,
            sector=sector,
            pathway_name=pathway_name,
            sensitivity=sensitivity,
        )
        importer.export_data(
            df=df_additional_investments,
            filename="additional_investments.csv",
            export_dir="final/cost",
            index=True,
        )

    """ LCOC """
    df_lcoc = calculate_weighted_average_lcox(
        df_cost=importer.get_technology_transitions_and_cost(),
        importer=importer,
        sector=sector,
    )
    importer.export_data(
        df=df_lcoc,
        filename="lcoc.csv",
        export_dir="final/cost",
        index=True,
    )

    logger.info("Output processing done")


def _create_tech_roadmaps_by_region(
    importer: IntermediateDataImporter, start_year: int, end_year: int
) -> pd.DataFrame:
    # Annual production volume in Mt production_output by technology and region

    # region
    df_list = []
    for year in np.arange(start_year, end_year + 1):
        # Group by technology and sum annual production volume
        df_stack = importer.get_asset_stack(year=year)
        df_stack = df_stack[["region", "technology", "annual_production_volume"]]
        df_stack = df_stack.groupby(["region", "technology"]).sum().reset_index()
        df_stack["year"] = year
        df_stack = df_stack.set_index(["year", "region", "technology"]).sort_index()
        # add to df_list
        df_list.append(df_stack)
    df_stack = pd.concat(df_list)

    # global
    df_stack_global = df_stack.groupby(["year", "technology"]).sum()
    df_stack_global["region"] = "Global"
    df_stack_global = df_stack_global.reset_index().set_index(
        ["year", "region", "technology"]
    )

    df_stack = pd.concat([df_stack, df_stack_global]).sort_index()

    return df_stack


def _export_and_plot_tech_roadmaps_by_region(
    pathway_name: str,
    sensitivity: str,
    importer: IntermediateDataImporter,
    df_roadmap: pd.DataFrame,
    unit: str,
    technology_layout: dict,
):

    regions = df_roadmap.reset_index()["region"].unique()

    for region in regions:
        df_roadmap_region = df_roadmap.xs(key=region, level="region")

        importer.export_data(
            df=df_roadmap_region,
            filename=f"technology_roadmap_{region}.csv",
            export_dir="final/technology_roadmap",
            index=True,
        )

        fig = px.area(
            data_frame=df_roadmap_region.reset_index(),
            x="year",
            y="annual_production_volume",
            color="technology",
            labels={
                "year": "Year",
                "annual_production_volume": f"Annual production volume in {unit}",
            },
            title=f"{region}: Technology roadmap ({pathway_name}_{sensitivity})",
            category_orders={"technology": list(technology_layout)},
            color_discrete_map=technology_layout,
        )

        fig.for_each_trace(lambda trace: trace.update(fillcolor=trace.line.color))

        plot(
            figure_or_data=fig,
            filename=f"{importer.final_path}/technology_roadmap/technology_roadmap_{region}.html",
            auto_open=False,
        )


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


def _calculate_emissions_year(
    importer: IntermediateDataImporter,
    year: int,
    ghgs: list = GHGS,
    emission_scopes: list = EMISSION_SCOPES,
    format_data: bool = True,
) -> pd.DataFrame:
    """Calculate emissions for all GHGs and scopes by production, region and technology"""

    idx = ["product", "region", "technology"]

    df_emissions = importer.get_emissions()
    df_emissions = df_emissions.loc[df_emissions["year"] == year, :].drop(
        columns="year"
    )
    df_stack = importer.get_asset_stack(year=year)

    # Emissions are the emissions factor multiplied with the annual production volume

    df_stack = df_stack.merge(df_emissions, on=idx)
    scopes = [f"{ghg}_{scope}" for scope in emission_scopes for ghg in ghgs]

    for scope in scopes:
        df_stack[scope] = df_stack[scope] * df_stack["annual_production_volume"]

    df_stack = (
        df_stack.groupby(idx)[scopes + ["annual_production_volume"]].sum().reset_index()
    )

    # global
    df_stack_global = (
        df_stack.copy().set_index(idx).groupby(["product", "technology"]).sum()
    )
    df_stack_global["region"] = "Global"
    df_stack_global = df_stack_global.reset_index()
    df_stack = pd.concat(objs=[df_stack, df_stack_global], axis=0)

    df_stack = df_stack.melt(
        id_vars=idx,
        value_vars=scopes,
        var_name="parameter",
        value_name="value",
    )

    if format_data:
        # Add unit and parameter group
        map_unit = {
            f"{ghg}_{scope}": f"Mt {str.upper(ghg)}"
            for scope in emission_scopes
            for ghg in ghgs
        }
        map_rename = {
            f"{ghg}_{scope}": f"{str.upper(ghg)} {str.capitalize(scope).replace('_', ' ')}"
            for scope in emission_scopes
            for ghg in ghgs
        }

        df_stack["parameter_group"] = "Emissions"
        df_stack["unit"] = df_stack["parameter"].apply(lambda x: map_unit[x])
        df_stack["parameter"] = df_stack["parameter"].replace(map_rename)
        if "technology" not in idx:
            df_stack["technology"] = "All"

    return df_stack


def _calculate_co2_captured(
    importer: IntermediateDataImporter,
    year: int,
    format_data: bool = True,
) -> pd.DataFrame:
    """Calculate captured CO2 by product, region and technology for a given asset stack"""

    idx = ["product", "region", "technology"]

    df_emissions = importer.get_emissions()
    df_emissions = df_emissions.loc[df_emissions["year"] == year, :].drop(
        columns="year"
    )
    df_stack = importer.get_asset_stack(year=year)

    # Captured CO2 by technology is calculated by multiplying with the annual production volume
    df_stack = df_stack.merge(df_emissions, on=idx)
    df_stack["co2_scope1_captured"] = (
        -df_stack["co2_scope1_captured"] * df_stack["annual_production_volume"]
    )

    df_stack = df_stack.groupby(idx)["co2_scope1_captured"].sum().reset_index()

    # global
    df_stack_global = (
        df_stack.copy().set_index(idx).groupby(["product", "technology"]).sum()
    )
    df_stack_global["region"] = "Global"
    df_stack_global = df_stack_global.reset_index()
    df_stack = pd.concat(objs=[df_stack, df_stack_global], axis=0)

    # Melt and add parameter descriptions
    df_stack = df_stack.melt(
        id_vars=idx,
        value_vars="co2_scope1_captured",
        var_name="parameter",
        value_name="value",
    )

    if format_data:
        df_stack["parameter_group"] = "Emissions"
        df_stack["parameter"] = "CO2 Scope1 captured"
        df_stack["unit"] = "Mt CO2"

        if "technology" not in idx:
            df_stack["technology"] = "All"

    return df_stack


def _calculate_emissions_total(
    importer: IntermediateDataImporter,
    ghgs: list = GHGS,
    emission_scopes: list = EMISSION_SCOPES,
    format_data: bool = True,
) -> pd.DataFrame:
    """Calculates the emissions of the entire model horizon"""

    df_list = []
    for year in MODEL_YEARS:
        df_emissions = _calculate_emissions_year(
            importer=importer,
            year=year,
            ghgs=ghgs,
            emission_scopes=emission_scopes,
            format_data=format_data,
        )
        df_captured_emissions = _calculate_co2_captured(
            importer=importer,
            year=year,
            format_data=format_data,
        )
        df_emissions["year"] = year
        df_captured_emissions["year"] = year
        df_list.append(df_emissions)
        df_list.append(df_captured_emissions)

    df = pd.concat(objs=df_list, axis=0)

    cols = ["year"] + [x for x in df.columns if x != "year"]
    df = df[cols]

    df = df.sort_values(
        ["year", "product", "region", "technology", "parameter"]
    ).reset_index(drop=True)

    return df


def _export_and_plot_emissions_by_region(
    pathway_name: str,
    sensitivity: str,
    importer: IntermediateDataImporter,
    df_total_emissions: pd.DataFrame,
    ghgs: list = GHGS,
    emission_scopes: list = EMISSION_SCOPES,
    technology_layout: dict = TECHNOLOGY_LAYOUT,
):

    regions = df_total_emissions["region"].unique()

    for region in regions:
        df_region = df_total_emissions.copy().loc[
            df_total_emissions["region"] == region, :
        ]

        importer.export_data(
            df=df_region,
            filename=f"emissions_{region}.csv",
            export_dir="final/emissions",
            index=False,
        )

        # area plots
        for ghg in ghgs:

            df_region_area = df_region.copy().loc[
                df_region["parameter"].isin([f"{ghg}_{x}" for x in emission_scopes]), :
            ]
            df_region_area = (
                df_region_area.set_index(
                    [x for x in df_region_area.columns if x != "value"]
                )
                .groupby(["year", "technology"])
                .sum()
                .reset_index()
            )

            fig_area = px.area(
                data_frame=df_region_area,
                x="year",
                y="value",
                color="technology",
                labels={
                    "year": "Year",
                    "value": f"{ghg} emissions in Mt {ghg}",
                },
                title=f"{region}: {ghg} emissions all scopes ({pathway_name}_{sensitivity})",
                category_orders={"technology": list(technology_layout)},
                color_discrete_map=technology_layout,
            )

            fig_area.for_each_trace(
                lambda trace: trace.update(fillcolor=trace.line.color)
            )

            plot(
                figure_or_data=fig_area,
                filename=f"{importer.final_path}/emissions/emissions_by_tech_{region}_{ghg}.html",
                auto_open=False,
            )

        # line plots
        df_region_line = (
            df_region.copy()
            .set_index([x for x in df_region.columns if x != "value"])
            .groupby(["year", "parameter"])
            .sum()
            .reset_index()
        )
        # add total emissions over all scopes
        df_list = []
        for ghg in ghgs:
            df_region_line_all_scopes = df_region_line.copy().loc[
                df_region_line["parameter"].isin(
                    [f"{ghg}_{x}" for x in emission_scopes]
                ),
                :,
            ]
            df_region_line_all_scopes = (
                df_region_line_all_scopes.set_index(
                    [
                        x
                        for x in df_region_line_all_scopes.columns
                        if x not in ["value", "co2_scope1_captured"]
                    ]
                )
                .groupby(["year"])
                .sum()
                .reset_index()
            )
            df_region_line_all_scopes["parameter"] = f"{ghg}_all-scopes"
            df_list.append(df_region_line_all_scopes)
        df_region_line = pd.concat(objs=[df_region_line] + df_list, axis=0)
        fig_line = px.line(
            data_frame=df_region_line,
            x="year",
            y="value",
            color="parameter",
            labels={
                "year": "Year",
                "value": f"Emissions in Mt GHG",
            },
            title=f"{region}: Emissions by GHG and scope ({pathway_name}_{sensitivity})",
            category_orders={"technology": list(technology_layout)},
            color_discrete_map=technology_layout,
        )

        plot(
            figure_or_data=fig_line,
            filename=f"{importer.final_path}/emissions/emissions_by_ghg_scope_{region}.html",
            auto_open=False,
        )


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
        "Energy": "GJ",
        "Raw material": "GJ",
        "H2 storage": "GJ",
        "Cost": "USD",
        "Capex": "USD",
        "Opex": "USD",
        "Lifetime": "Years",
        "CF": "%",
    }
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
    # df_emissions = importer.get_emissions()
    # df_emissions = df_emissions[df_emissions["year"] == year]
    # df_stack_emissions = _calculate_emissions(df_stack, df_emissions)
    # df_stack_emissions_co2e = _calculate_emissions_co2e(
    #     df_stack, df_emissions, gwp="GWP-20"
    # )
    # df_stack_emissions_co2e_all_tech = _calculate_emissions_co2e(
    #     df_stack, df_emissions, gwp="GWP-20", agg_vars=["product", "region"]
    # )
    # df_emissions_intensity = _calculate_emissions_intensity(df_stack, df_emissions)
    # df_emissions_intensity_all_tech = _calculate_emissions_intensity(
    #     df_stack, df_emissions, agg_vars=["product", "region"]
    # )
    # df_co2_captured = _calculate_co2_captured(df_stack, df_emissions)

    # Calculate feedstock and energy consumption
    # df_inputs_outputs = importer.get_inputs_outputs()
    # data_variables = []

    # for resource in df_inputs_outputs["parameter"].unique():
    #     df_stack_variable = _calculate_resource_consumption(
    #         df_stack,
    #         df_inputs_outputs,
    #         resource,
    #         year,
    #         agg_vars=["product", "region", "technology"],
    #     )
    #     df_stack_variable["parameter"] = resource
    #     data_variables.append(df_stack_variable)

    # df_inputs = pd.concat(data_variables)

    # Concatenate all the output tables
    df_all_data_year = pd.concat(
        [
            df_total_assets,
            df_production_capacity,
            # df_stack_emissions,
            # df_stack_emissions_co2e,
            # df_stack_emissions_co2e_all_tech,
            # df_emissions_intensity,
            # df_emissions_intensity_all_tech,
            # df_co2_captured,
            # df_inputs,
        ]
    )
    return df_all_data_year


def _calculate_annual_investments(
    df_cost: pd.DataFrame,
    importer: IntermediateDataImporter,
    sector: str,
    agg_vars=["product", "region", "switch_type", "technology_destination"],
) -> pd.DataFrame:
    """Calculate annual investments (CAPEX)."""

    # Calculate investment from newbuild, brownfield retrofit and brownfield rebuild technologies in every year
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
        ).fillna(False)

        # Identify newly built assets
        df.loc[
            (df["greenfield_status"] & ~df["previous_greenfield_status"]),
            ["switch_type", "technology_origin"],
        ] = ["greenfield", "New-build"]

        # Identify retrofit assets
        df.loc[
            (df["retrofit_status"] & ~df["previous_retrofit_status"]),
            "switch_type",
        ] = "brownfield_renovation"

        # Identify rebuild assets
        df.loc[
            (df["rebuild_status"] & ~df["previous_rebuild_status"]),
            "switch_type",
        ] = "brownfield_newbuild"

        # Drop all assets that haven't undergone a transition
        df = df.loc[df["switch_type"].notna(), :]
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

        # Calculate investment cost per changed asset by multiplying CAPEX (in USD/tpa) with production capacity
        #   (in Mtpa) and sum
        df["investment"] = (
            df["switch_capex"] * df["annual_production_capacity_destination"] * 1e6
        )
        df = (
            df.groupby(agg_vars + ["year"])[["investment"]]
            .sum()
            .reset_index(drop=False)
        )

        df = df.melt(
            id_vars=agg_vars + ["year"],
            value_vars="investment",
            var_name="parameter",
            value_name="value",
        )

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


def _calculate_total_additional_investments(
    df_investments: pd.DataFrame,
    importer: IntermediateDataImporter,
    sector: str,
    pathway_name: str,
    sensitivity: str,
) -> pd.DataFrame:
    """Calculates the investments in addition to the BAU scenario

    Args:
        df_investments ():
        importer ():
        sector ():

    Returns:

    """

    if pathway_name != "bau":
        # get BAU demand
        df_investments_bau = importer.get_pathway_investments(
            pathway_name="bau", sensitivity=sensitivity
        )
        model_years_str = [str(x) for x in MODEL_YEARS]
        df_investments_bau = pd.melt(
            frame=df_investments_bau,
            id_vars=[x for x in list(df_investments_bau) if x not in model_years_str],
            value_vars=[str(x) for x in MODEL_YEARS if x != MODEL_YEARS[0]],
            var_name="year",
            value_name="value",
        )[["region", "technology", "parameter", "year", "value"]]
        df_investments_bau = df_investments_bau.astype(
            dtype={
                "region": str,
                "technology": str,
                "parameter": str,
                "year": int,
                "value": float,
            }
        )
        # df_investments_bau.set_index(keys=[x for x in list(df_investments_bau) if x != "value"], inplace=True)

        df_investments = pd.melt(
            frame=df_investments.reset_index(),
            id_vars=list(df_investments.index.names),
            value_vars=list(df_investments),
            var_name="year",
            value_name="value",
        )[["region", "technology", "parameter", "year", "value"]]
        df_investments_bau = df_investments_bau.astype(
            dtype={
                "region": str,
                "technology": str,
                "parameter": str,
                "year": int,
                "value": float,
            }
        )
        # df_investments.set_index(keys=[x for x in list(df_investments) if x != "value"], inplace=True)

        # merge and calculate additional investments
        df_investments = pd.merge(
            left=df_investments_bau.reset_index(drop=True),
            right=df_investments.reset_index(drop=True),
            how="outer",
            on=["region", "technology", "parameter", "year"],
            suffixes=("_bau", f"_{pathway_name}"),
        ).fillna(float(0))
        df_investments["value"] = (
            df_investments[f"value_{pathway_name}"] - df_investments["value_bau"]
        )
        df_investments = df_investments.set_index(
            ["region", "technology", "parameter", "year"]
        ).sort_index()[["value"]]

        return df_investments


def _export_and_plot_investments(
    pathway_name: str,
    sensitivity: str,
    df_investments: pd.DataFrame,
    importer: IntermediateDataImporter,
):

    df_investments = pd.melt(
        frame=df_investments.reset_index(),
        id_vars=list(df_investments.index.names),
        value_vars=list(df_investments),
        var_name="year",
        value_name="value",
    )

    # todo: plot


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
        # In every year, get LCOX of the asset based on the year it was commissioned and average according to desired
        #   aggregation
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
                        x["lcox"] + 1, weights=x["annual_production_volume"] + 1
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


def save_consolidated_outputs(sector: str):
    data = []
    runs = []
    for pathway, sensitivities in SENSITIVITIES.items():
        for sensitivity in sensitivities:
            runs.append((pathway, sensitivity))
    # for pathway, sensitivity in itertools.product(PATHWAYS, SENSITIVITIES):
    for pathway, sensitivity in runs:
        df_ = pd.read_csv(
            f"{SECTOR}/data/{pathway}/{sensitivity}/final/simulation_outputs_{SECTOR}_{pathway}_{sensitivity}.csv"
        )
        df_["pathway"] = pathway
        df_["sensitivity"] = sensitivity
        data.append(df_)
    df = pd.concat(data)
    columns = [
        "sector",
        "product",
        "pathway",
        "sensitivity",
        "region",
        "technology",
        "parameter_group",
        "parameter",
        "unit",
    ] + [str(i) for i in range(START_YEAR, END_YEAR + 1)]
    df = df[columns]
    df.to_csv(
        f"{OUTPUT_WRITE_PATH[sector]}/simulation_outputs_{SECTOR}_consolidated.csv",
        index=False,
    )
    df.to_csv(f"data/{sector}/simulation_outputs_{SECTOR}_consolidated.csv")

""" Create outputs for debugging."""
from collections import defaultdict

import numpy as np
import pandas as pd
import plotly.express as px
from mppshared.config import EMISSION_SCOPES_DEFAULT, LOG_LEVEL
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.utility.log_utility import get_logger
from pandas import CategoricalDtype
from plotly.offline import plot
from plotly.subplots import make_subplots

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def create_debugging_outputs(
    pathway_name: str,
    sensitivity: str,
    sector: str,
    start_year: int,
    end_year: int,
    products: list,
):
    """Create technology roadmap and emissions trajectory for quick debugging and refinement."""

    importer = IntermediateDataImporter(
        pathway_name=pathway_name,
        sensitivity=sensitivity,
        sector=sector,
        products=products,
    )

    # Create summary table of asset transitions
    logger.info("Creating table with asset transition sequences.")
    df_transitions = create_table_asset_transition_sequences(
        importer, start_year=start_year, end_year=end_year
    )
    importer.export_data(
        df_transitions,
        f"asset_transition_sequences_sensitivity_{sensitivity}.csv",
        "final",
    )

    # Create outputs on rebuild capacity
    output_renovation_transitions_by_year(
        df_transitions=df_transitions,
        importer=importer,
        renovation_type="rebuild",
        technology_type="origin",
        start_year=start_year,
        end_year=end_year,
    )
    output_renovation_transitions_by_year(
        df_transitions,
        importer,
        renovation_type="rebuild",
        technology_type="destination",
        start_year=start_year,
        end_year=end_year,
    )

    # Create outputs on retrofit capacity
    output_renovation_transitions_by_year(
        df_transitions,
        importer,
        renovation_type="retrofit",
        technology_type="origin",
        start_year=start_year,
        end_year=end_year,
    )
    output_renovation_transitions_by_year(
        df_transitions,
        importer,
        renovation_type="retrofit",
        technology_type="destination",
        start_year=start_year,
        end_year=end_year,
    )

    # Create outputs on newbuild capacity
    create_newbuild_capacity_outputs_by_region(
        df_transitions=df_transitions,
        importer=importer,
        start_year=start_year,
        end_year=end_year,
    )
    create_newbuild_capacity_outputs_by_technology(
        df_transitions=df_transitions,
        importer=importer,
        start_year=start_year,
        end_year=end_year,
    )

    # Create emissions trajectory and technology roadmap
    output_emissions_trajectory(
        importer=importer,
        start_year=start_year,
        end_year=end_year,
    )
    output_technology_roadmap(
        importer=importer,
        start_year=start_year,
        end_year=end_year,
    )


def output_renovation_transitions_by_year(
    df_transitions: pd.DataFrame,
    importer: IntermediateDataImporter,
    start_year: int,
    end_year: int,
    renovation_type: str = "retrofit",
    technology_type: str = "origin",
):
    """Plot origin or destination technologies of renovation transitions by year."""
    df_transitions = df_transitions.reset_index(drop=False).set_index("uuid")
    df_transitions_renovation_status = df_transitions.loc[
        df_transitions["parameter"] == f"{renovation_type}_status"
    ]
    renovation_techs: defaultdict = defaultdict()

    # Iterate over every year and create dictionary of newbuild technologies in that year (no newbuild in 2020)
    for year in np.arange(start_year, end_year):
        renovation_cond1 = (
            df_transitions.loc[
                df_transitions["parameter"] == f"{renovation_type}_status", year
            ]
            == False
        )
        renovation_cond2 = (
            df_transitions.loc[
                df_transitions["parameter"] == f"{renovation_type}_status", year + 1
            ]
            == True
        )
        renovation_uuids = df_transitions_renovation_status.loc[
            renovation_cond1 & renovation_cond2
        ].index.unique()
        renovation_df = df_transitions.loc[
            (df_transitions.index.isin(renovation_uuids))
            & (df_transitions["parameter"] == "technology")
        ]
        if technology_type == "origin":
            renovation_techs[year + 1] = list(renovation_df[year])
        else:
            renovation_techs[year + 1] = list(renovation_df[year + 1])

    # Create DataFrame from dictionary with technologies as index
    df = pd.DataFrame.from_dict(renovation_techs, orient="index")
    df = df.transpose()

    technologies = {
        value for value_list in renovation_techs.values() for value in value_list
    }
    df_agg = pd.DataFrame(index=technologies)
    df_agg.index.rename("technology", inplace=True)
    for year in renovation_techs.keys():
        for technology in df_agg.index:
            df_agg.loc[df_agg.index == technology, year] = renovation_techs[year].count(
                technology
            )

    # Melt to long format and plot barchart
    df_agg = df_agg.reset_index(drop=False).melt(
        id_vars="technology", var_name="year", value_name="number"
    )
    df_agg = df_agg.loc[df_agg["number"] > 0]
    fig = make_subplots()
    bar_fig = px.bar(df_agg, x="year", y="number", color="technology", text_auto=True)

    fig.add_traces(bar_fig.data)
    fig.update_layout(barmode="stack")

    fig.layout.xaxis.title = "Year"
    fig.layout.yaxis.title = f"Number of plants per technology"
    fig.layout.title = (
        f"Brownfield {renovation_type}: {technology_type} technology (# of plants)"
    )

    plot(
        fig,
        filename=str(
            importer.final_path.joinpath(
                f"{renovation_type}_{technology_type}_technologies_by_year.html"
            )
        ),
        auto_open=False,
    )
    pass


def create_newbuild_capacity_outputs_by_region(
    df_transitions: pd.DataFrame,
    importer: IntermediateDataImporter,
    start_year: int,
    end_year: int,
):
    """Show newbuild capacity by region"""

    df_transitions = df_transitions.reset_index(drop=False)
    newbuild_regions: defaultdict = defaultdict()

    # Iterate over every year and create dictionary of newbuild technologies in that year (no newbuild in 2020)
    for year in np.arange(start_year, end_year):
        newbuild_cond1 = df_transitions[year].isna()
        newbuild_cond2 = df_transitions[year + 1].notna()
        newbuild_uuids = df_transitions.loc[
            newbuild_cond1 & newbuild_cond2, "uuid"
        ].unique()
        newbuild_df = df_transitions.loc[
            (df_transitions["uuid"].isin(newbuild_uuids))
            & (df_transitions["parameter"] == "technology")
        ]
        newbuild_regions[year + 1] = list(newbuild_df["region"])

    # Create DataFrame from dictionary with technologies as index
    df = pd.DataFrame.from_dict(newbuild_regions, orient="index")
    df = df.transpose()

    regions = {
        value for value_list in newbuild_regions.values() for value in value_list
    }
    df_agg = pd.DataFrame(index=regions)
    df_agg.index.rename("region", inplace=True)
    for year in newbuild_regions.keys():
        for technology in df_agg.index:
            df_agg.loc[df_agg.index == technology, year] = newbuild_regions[year].count(
                technology
            )

    # Melt to long format and plot barchart
    df_agg = df_agg.reset_index(drop=False).melt(
        id_vars="region", var_name="year", value_name="number"
    )
    df_agg = df_agg.loc[df_agg["number"] > 0]
    fig = make_subplots()
    bar_fig = px.bar(df_agg, x="year", y="number", color="region", text_auto=True)

    fig.add_traces(bar_fig.data)
    fig.update_layout(barmode="stack")

    fig.layout.xaxis.title = "Year"
    fig.layout.yaxis.title = "Newbuild capacity (# of plants)"
    fig.layout.title = "Newbuild capacity by region"

    plot(
        fig,
        filename=str(importer.final_path.joinpath(f"newbuild_capacity_by_region.html")),
        auto_open=False,
    )


def create_newbuild_capacity_outputs_by_technology(
    df_transitions: pd.DataFrame,
    importer: IntermediateDataImporter,
    start_year: int,
    end_year: int,
):
    """Show newbuild capacity by technology for every year, in stacked bar chart."""

    df_transitions = df_transitions.reset_index(drop=False)
    newbuild_techs: defaultdict = defaultdict()

    # Iterate over every year and create dictionary of newbuild technologies in that year (no newbuild in 2020)
    for year in np.arange(start_year, end_year):
        newbuild_cond1 = df_transitions[year].isna()
        newbuild_cond2 = df_transitions[year + 1].notna()
        newbuild_uuids = df_transitions.loc[
            newbuild_cond1 & newbuild_cond2, "uuid"
        ].unique()
        newbuild_df = df_transitions.loc[
            (df_transitions["uuid"].isin(newbuild_uuids))
            & (df_transitions["parameter"] == "technology")
        ]
        newbuild_techs[year + 1] = list(newbuild_df[year + 1])

    # Create DataFrame from dictionary with technologies as index
    df = pd.DataFrame.from_dict(newbuild_techs, orient="index")
    df = df.transpose()

    technologies = {
        value for value_list in newbuild_techs.values() for value in value_list
    }
    df_agg = pd.DataFrame(index=technologies)
    df_agg.index.rename("technology", inplace=True)
    for year in newbuild_techs.keys():
        for technology in df_agg.index:
            df_agg.loc[df_agg.index == technology, year] = newbuild_techs[year].count(
                technology
            )

    # Melt to long format and plot barchart
    df_agg = df_agg.reset_index(drop=False).melt(
        id_vars="technology", var_name="year", value_name="number"
    )
    df_agg = df_agg.loc[df_agg["number"] > 0]
    fig = make_subplots()
    bar_fig = px.bar(df_agg, x="year", y="number", color="technology", text_auto=True)

    fig.add_traces(bar_fig.data)
    fig.update_layout(barmode="stack")

    fig.layout.xaxis.title = "Year"
    fig.layout.yaxis.title = "Newbuild capacity (# of plants)"
    fig.layout.title = f"Newbuild capacity by technology"

    plot(
        fig,
        filename=str(
            importer.final_path.joinpath(f"newbuild_capacity_by_technology.html")
        ),
        auto_open=False,
    )


def create_table_asset_transition_sequences(
    importer: IntermediateDataImporter,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:

    # Get initial stack and melt to long for that year
    multiindex = ["uuid", "product", "region", "parameter"]
    df = importer.get_asset_stack(start_year)
    df = df[
        [
            "uuid",
            "product",
            "region",
            "technology",
            "annual_production_capacity",
            "annual_production_volume",
            "retrofit_status",
            "rebuild_status",
            "greenfield_status",
        ]
    ]
    df = df.set_index(["product", "region", "uuid"])
    df = df.melt(var_name="parameter", value_name=start_year, ignore_index=False)
    df = df.sort_index()
    df = df.reset_index(drop=False).set_index(multiindex)

    for year in np.arange(start_year + 1, end_year + 1):

        # Get asset stack for that year
        df_stack = importer.get_asset_stack(year=year)
        df_stack = df_stack[
            [
                "uuid",
                "product",
                "region",
                "technology",
                "annual_production_capacity",
                "annual_production_volume",
                "retrofit_status",
                "rebuild_status",
            ]
        ]

        # Reformat stack DataFrame
        df_stack = df_stack.set_index(["product", "region", "uuid"])
        df_stack = df_stack.melt(
            var_name="parameter", value_name=year, ignore_index=False
        )
        df_stack = df_stack.reset_index().set_index("uuid")
        df_stack = df_stack.sort_index()

        # Differentiate between existing and new assets
        previous_uuids = df.index.unique()
        current_uuids = df_stack.index.unique()

        existing_uuids = [uuid for uuid in current_uuids if uuid in previous_uuids]
        new_uuids = [uuid for uuid in current_uuids if uuid not in previous_uuids]
        vanished_uuids = [
            uuid for uuid in previous_uuids if uuid not in current_uuids
        ]  # Decommissioned assets (not relevant)

        newbuild_stack = (
            df_stack[df_stack.index.isin(new_uuids)]
            .reset_index()
            .set_index(multiindex)
            .sort_index()
        )
        existing_stack = (
            df_stack[df_stack.index.isin(existing_uuids)]
            .reset_index()
            .set_index(multiindex)
            .sort_index()
        )

        # Join existing stack and add newbuild stack
        df[year] = existing_stack[year]
        df = pd.concat([df, newbuild_stack])

    return df


def output_technology_roadmap(
    importer: IntermediateDataImporter,
    start_year: int,
    end_year: int,
):
    df_roadmap = create_technology_roadmap(
        importer=importer,
        start_year=start_year,
        end_year=end_year,
    )
    importer.export_data(df_roadmap, "technology_roadmap.csv", "final")
    plot_technology_roadmap(importer=importer, df_roadmap=df_roadmap)


def output_emissions_trajectory(
    importer: IntermediateDataImporter,
    start_year: int,
    end_year: int,
):
    df_trajectory = create_emissions_trajectory(
        importer=importer,
        start_year=start_year,
        end_year=end_year,
    )
    df_wide = pd.pivot_table(
        df_trajectory, values="value", index="variable", columns="year"
    )
    importer.export_data(df_wide, "emissions_trajectory.csv", "final")
    plot_emissions_trajectory(importer=importer, df_trajectory=df_trajectory)


def create_technology_roadmap(
    importer: IntermediateDataImporter,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """Create technology roadmap that shows evolution of stack (supply mix) over model horizon."""

    # Annual production volume in MtNH3 by technology
    technologies = importer.get_technology_characteristics()["technology"].unique()
    df_roadmap = pd.DataFrame(data={"technology": technologies})

    for year in np.arange(start_year, end_year + 1):

        # Group by technology and sum annual production volume
        df_stack = importer.get_asset_stack(year=year)
        df_sum = df_stack.groupby(["technology"], as_index=False).sum()
        df_sum = df_sum[["technology", "annual_production_volume"]].rename(
            {"annual_production_volume": year}, axis=1
        )

        # Merge with roadmap DataFrame
        df_roadmap = df_roadmap.merge(df_sum, on=["technology"], how="left").fillna(0)

    # Sort technologies as required
    df_roadmap = df_roadmap.loc[
        ~(df_roadmap["technology"] == "Waste Water to ammonium nitrate")
    ]
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
    tech_order = CategoricalDtype(technologies, ordered=True)
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


def plot_technology_roadmap(
    importer: IntermediateDataImporter, df_roadmap: pd.DataFrame
):
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


def create_emissions_trajectory(
    importer: IntermediateDataImporter,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """Create emissions trajectory for scope 1, 2, 3 along with demand."""

    # Get emissions for each technology
    df_emissions = importer.get_emissions()
    df_trajectory = pd.DataFrame()

    greenhousegases = ["co2", "ch4", "n2o"]
    emission_cols = [
        f"{ghg}_{scope}" for ghg in greenhousegases for scope in EMISSION_SCOPES_DEFAULT
    ] + ["co2_scope1_captured"]

    for year in np.arange(start_year, end_year + 1):

        # Filter emissions for the year
        df_em = df_emissions.loc[df_emissions["year"] == year]

        # Calculate annual production volume by technology, merge with emissions and sum for each scope
        df_stack = importer.get_asset_stack(year=year)
        df_sum = df_stack.groupby(
            ["product", "region", "technology"], as_index=True
        ).sum()
        df_sum = df_sum[["annual_production_volume"]].reset_index()
        df_stack_emissions = df_sum.merge(
            df_em, on=["product", "technology", "region"], how="left"
        )

        # Multiply production volume with emission factor for each region and technology
        for col in emission_cols:
            df_stack_emissions[f"emissions_{col}"] = (
                df_stack_emissions["annual_production_volume"] * df_stack_emissions[col]
            )

        # Melt to long format and concatenate
        cols_to_keep = [f"emissions_{col}" for col in emission_cols]
        df_total = df_stack_emissions.groupby("product").sum()[cols_to_keep]
        df_total = df_total.melt()
        df_total["year"] = year
        df_trajectory = pd.concat([df_total, df_trajectory], axis=0)

    return df_trajectory


def plot_emissions_trajectory(
    importer: IntermediateDataImporter, df_trajectory: pd.DataFrame
):
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

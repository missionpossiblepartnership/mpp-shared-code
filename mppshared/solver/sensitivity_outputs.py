import os
import pandas as pd
import numpy as np
import plotly.express as px
from plotly.offline import plot
from plotly.subplots import make_subplots

from mppshared.config import CARBON_COSTS, GWP

AUTO_OPEN = True


def create_sensitivity_outputs():
    """Create outputs to show impact of natural gas price sensitivities and carbon price."""

    ### PARAMETERS ###
    save_path = "C:/Users/JohannesWuellenweber/SYSTEMIQ Ltd/MPP Materials - 1. Ammonia/01_Work Programme/3_Data/4_Model results/Sensitivity analysis"
    pathways = [
        # "fa",
        "lc"
    ]
    sensitivities = [
        "def",
        # "ng_partial",
        # "ng_high"
    ]

    # For emissions calculations
    years = [2020, 2030, 2040, 2050]
    emissions_list = [
        "CO2 Scope 1&2",
        "CH4 Scope2",
        "N2O Scope2",
        "N2O Scope3 downstream",
        "CO2 Scope3 upstream",
        "CO2 Scope3 downstream",
        "CO2e Scope1",
        "CO2e Scope3 upstream",
        "CO2e Scope3 downstream",
    ]

    # Carbon costs
    anchor_carbon_cost = 75
    carbon_costs = CARBON_COSTS
    # carbon_costs = np.arange(0, 101, step=25)
    # carbon_costs = [anchor_carbon_cost]
    # carbon_costs = [0]

    # Output file dictionary
    dict_sens = get_dict_sens(pathways, sensitivities, carbon_costs)

    for pathway in pathways:
        if pathway == "fa":
            anchor_carbon_cost = 0

        create_sensitivity_table(
            dict_sens, pathway, sensitivities, carbon_costs, save_path
        )
        if len(sensitivities) > 1:
            ### SHARES BY NATURAL GAS PRICE ###
            create_shares_by_sensitivity(
                dict_sens=dict_sens,
                pathway=pathway,
                save_path=save_path,
                carbon_cost=anchor_carbon_cost,
                sensitivities=sensitivities,
                years=years,
            )

            ### CUMULATIVE EMISSIONS BY SENSITIVITY ###
            create_cumulative_emissions_by_sensitivity(
                dict_sens=dict_sens,
                pathway=pathway,
                save_path=save_path,
                carbon_cost=anchor_carbon_cost,
                sensitivities=sensitivities,
                emissions_list=emissions_list,
            )
            ### RESIDUAL EMISSIONS BY SENSITIVITY ###
            create_residual_emissions_by_sensitivity(
                dict_sens=dict_sens,
                pathway=pathway,
                save_path=save_path,
                carbon_cost=anchor_carbon_cost,
                sensitivities=sensitivities,
            )

        if len(carbon_costs) > 1:
            ### SHARES BY CARBON PRICE ###
            create_shares_by_carbon_price(
                dict_sens=dict_sens,
                pathway=pathway,
                save_path=save_path,
                carbon_costs=carbon_costs,
                sensitivity="def",
                years=years,
            )

            ### CUMULATIVE EMISSIONS BY CARBON PRICE ###
            create_cumulative_emissions_by_carbon_price(
                dict_sens=dict_sens,
                pathway=pathway,
                save_path=save_path,
                carbon_costs=carbon_costs,
                sensitivity="def",
                emissions_list=emissions_list,
            )

            ### RESIDUAL EMISSIONS BY CARBON PRICE ###
            create_residual_emissions_by_carbon_price(
                dict_sens=dict_sens,
                pathway=pathway,
                save_path=save_path,
                carbon_costs=carbon_costs,
                sensitivity="def",
            )


def create_sensitivity_table(
    dict_sens: dict,
    pathway: str,
    sensitivities: list,
    carbon_costs: list,
    save_path: str,
):
    """Create 2x2 matrix with carbon cost and sensitivity with entries being share of green/share of blue ammonia"""
    df_sens = pd.DataFrame(
        index=sensitivities,
        columns=pd.MultiIndex.from_product(
            [carbon_costs, ["blue", "green"]], names=["Carbon Cost", "Ammonia Type"]
        ),
    )

    for sensitivity in sensitivities:
        for carbon_cost in carbon_costs:
            df = dict_sens[pathway][sensitivity][carbon_cost]
            df = add_ammonia_type_to_df(df)

            # Sum production volume by ammonia type
            df = df.loc[df["parameter"] == "Annual production volume"]
            df = df.groupby(["ammonia_type"]).sum()

            if "blue_10%" in df.index:
                df.loc["blue"] += df.loc["blue_10%"] * 0.1
                df.loc["grey"] += df.loc["blue_10%"] * 0.9

            # Calculate shares
            df.loc["total"] = df.loc["blue"] + df.loc["green"] + df.loc["grey"]
            for ammonia_type in ["blue", "green", "grey"]:
                df.loc[ammonia_type] = df.loc[ammonia_type] / df.loc["total"]

            # Drop auxiliary rows
            rows_to_drop = [row for row in ["blue_10%", "total"] if row in df.index]
            df = df.drop(index=rows_to_drop)
            df = df["2050"]

            # Add into DataFrame
            df_sens.loc[sensitivity, (carbon_cost, "blue")] = df.loc["blue"]
            df_sens.loc[sensitivity, (carbon_cost, "green")] = df.loc["green"]

    df_sens.to_csv(f"{save_path}/sensitivity_table_pathway={pathway}.csv")


def get_dict_sens(pathways, sensitivities, carbon_costs):
    dict_fa = {
        sens: {carbon_cost: None}
        for carbon_cost in carbon_costs
        for sens in sensitivities
    }

    dict_lc = {
        sens: {carbon_cost: None}
        for carbon_cost in carbon_costs
        for sens in sensitivities
    }
    dict_sens = {"fa": dict_fa, "lc": dict_lc}

    # Get simulation outputs for each combination
    for pathway in pathways:
        for sensitivity in sensitivities:
            for carbon_cost in carbon_costs:
                path = f"data/chemicals/{pathway}/{sensitivity}/carbon_cost_{carbon_cost}/final/simulation_outputs_chemicals_{pathway}_{sensitivity}.csv"
                if os.path.exists(path):
                    dict_sens[pathway][sensitivity][carbon_cost] = pd.read_csv(path)
                else:
                    dict_sens[pathway][sensitivity][carbon_cost] = None
    return dict_sens


def add_titles_and_save_figure_html(
    save_path: str,
    fig,
    title: str,
    xtitle: str,
    ytitle: str,
    filename: str,
    pathway: str,
    df: pd.DataFrame,
):
    fig.layout.xaxis.title = xtitle
    fig.layout.yaxis.title = ytitle
    fig.layout.title = title

    path = f"{save_path}/{filename}_{pathway}"
    plot(fig, filename=f"{path}.html", auto_open=AUTO_OPEN)

    df.to_csv(f"{path}.csv")


def create_outputs_dict(
    pathways: list, sensitivities: list, carbon_costs: list
) -> dict:
    dict_fa = {
        sens: {carbon_cost: None}
        for carbon_cost in carbon_costs
        for sens in sensitivities
    }

    dict_lc = {
        sens: {carbon_cost: None}
        for carbon_cost in carbon_costs
        for sens in sensitivities
    }
    dict_sens = {"fa": dict_fa, "lc": dict_lc}

    # Get simulation outputs for each combination
    for pathway in pathways:
        for sensitivity in sensitivities:
            for carbon_cost in carbon_costs:
                path = f"data/chemicals/{pathway}/{sensitivity}/carbon_cost_{carbon_cost}/final/simulation_outputs_chemicals_{pathway}_{sensitivity}.csv"
                dict_sens[pathway][sensitivity][carbon_cost] = pd.read_csv(path)

    return dict_sens


def create_shares_by_sensitivity(
    dict_sens: dict,
    pathway: str,
    save_path: str,
    carbon_cost: float,
    sensitivities: list,
    years: list,
):
    """Plot shares of grey, blue and green ammonia by natural gas price sensitivity"""

    df_shares_sens = pd.DataFrame()
    for sensitivity in sensitivities:
        df = dict_sens[pathway][sensitivity][carbon_cost]
        df = add_ammonia_type_to_df(df)

        # Sum production volume by ammonia type
        df = df.loc[df["parameter"] == "Annual production volume"]
        df = df.groupby(["ammonia_type"]).sum()

        if "blue_10%" in df.index:
            df.loc["blue"] += df.loc["blue_10%"] * 0.1
            df.loc["grey"] += df.loc["blue_10%"] * 0.9

        # Calculate shares
        df.loc["total"] = df.loc["blue"] + df.loc["green"] + df.loc["grey"]
        for ammonia_type in ["blue", "green", "grey"]:
            df.loc[ammonia_type] = df.loc[ammonia_type] / df.loc["total"]

        # Drop auxiliary rows
        rows_to_drop = [row for row in ["blue_10%", "total"] if row in df.index]
        df = df.drop(index=rows_to_drop)

        # Melt so that years are column
        df = df.melt(var_name="year", value_name=sensitivity, ignore_index=False)
        df = df.reset_index(drop=False).set_index(["ammonia_type", "year"])
        df_shares_sens = pd.concat([df_shares_sens, df], axis=1)

    # Plot
    df_shares_sens = df_shares_sens.melt(
        var_name="sensitivity", value_name="share", ignore_index=False
    )
    df_shares_sens = df_shares_sens.reset_index(drop=False)
    df_shares_sens["year"] = df_shares_sens["year"].astype(int)
    df_shares_sens = df_shares_sens.loc[df_shares_sens["year"].isin(years)]
    df_shares_sens["identifier"] = (
        df_shares_sens["year"].astype(str) + df_shares_sens["sensitivity"]
    )
    fig = make_subplots()
    bar_fig = px.bar(
        df_shares_sens,
        x="identifier",
        y="share",
        color="ammonia_type",
        barmode="stack",
        color_discrete_sequence=["blue", "green", "grey"],
        text=[f"{np.round(share*100)}%" for share in df_shares_sens["share"]],
    )

    fig.add_traces(bar_fig.data)
    add_titles_and_save_figure_html(
        save_path=save_path,
        fig=fig,
        xtitle="Year",
        ytitle="Share in global production volume (%)",
        title=f"Pathway {pathway}: Impact of natural gas price sensitivity on grey, blue, green ammonia shares",
        pathway=pathway,
        filename=f"ng-sens_shares_cc={carbon_cost}",
        df=df_shares_sens,
    )


def add_ammonia_type_to_df(df: pd.DataFrame) -> pd.DataFrame:

    # Add ammonia type
    colour_map = {
        "Natural Gas SMR + ammonia synthesis": "grey",
        "Coal Gasification + ammonia synthesis": "grey",
        "Electrolyser + SMR + ammonia synthesis": "blue_10%",
        "Electrolyser + Coal Gasification + ammonia synthesis": "blue_10%",
        "Coal Gasification+ CCS + ammonia synthesis": "blue",
        "Natural Gas SMR + CCS (process emissions only) + ammonia synthesis": "blue",
        "Natural Gas ATR + CCS + ammonia synthesis": "blue",
        "GHR + CCS + ammonia synthesis": "blue",
        "ESMR Gas + CCS + ammonia synthesis": "blue",
        "Natural Gas SMR + CCS + ammonia synthesis": "blue",
        "Electrolyser - grid PPA + ammonia synthesis": "green",
        "Biomass Digestion + ammonia synthesis": "green",
        "Biomass Gasification + ammonia synthesis": "green",
        "Methane Pyrolysis + ammonia synthesis": "blue",
        "Electrolyser - dedicated VRES + grid PPA + ammonia synthesis": "green",
        "Electrolyser - dedicated VRES + H2 storage - geological + ammonia synthesis": "green",
        "Electrolyser - dedicated VRES + H2 storage - pipeline + ammonia synthesis": "green",
        "Waste Water to ammonium nitrate": "green",
        "Waste to ammonia": "green",
        "Oversized ATR + CCS": "blue",
        "All": "no type",
    }
    df["ammonia_type"] = df["technology"].apply(lambda row: colour_map[row])
    return df


def create_shares_by_carbon_price(
    dict_sens: dict,
    pathway: str,
    save_path: str,
    carbon_costs: float,
    sensitivity: list,
    years: list,
):
    """Plot shares of green, grey, blue ammonia by carbon price for a set sensitivity."""

    df_shares_cc = pd.DataFrame()
    for carbon_cost in carbon_costs:
        df = dict_sens[pathway][sensitivity][carbon_cost]
        df = add_ammonia_type_to_df(df)

        # Sum production volume by ammonia type
        df = df.loc[df["parameter"] == "Annual production volume"]
        df = df.groupby(["ammonia_type"]).sum()

        # Calculate shares
        df.loc["total"] = df.loc["blue"] + df.loc["green"] + df.loc["grey"]
        for ammonia_type in ["blue", "green", "grey"]:
            df.loc[ammonia_type] = df.loc[ammonia_type] / df.loc["total"]

        # Drop auxiliary rows
        rows_to_drop = [row for row in ["blue_10%", "total"] if row in df.index]
        df = df.drop(index=rows_to_drop)

        # Melt so that years are column
        df = df.melt(var_name="year", value_name=carbon_cost, ignore_index=False)
        df = df.reset_index(drop=False).set_index(["ammonia_type", "year"])
        df_shares_cc = pd.concat([df_shares_cc, df], axis=1)

    # Plot
    df_shares_cc = df_shares_cc.melt(
        var_name="carbon_cost", value_name="share", ignore_index=False
    )
    df_shares_cc = df_shares_cc.reset_index(drop=False)
    df_shares_cc["year"] = df_shares_cc["year"].astype(int)
    df_shares_cc = df_shares_cc.loc[df_shares_cc["year"].isin(years)]
    df_shares_cc["identifier"] = df_shares_cc.apply(
        lambda row: f"{row['year']}_{row['carbon_cost']} USD/tCO2", axis=1
    )
    fig = make_subplots()
    bar_fig = px.bar(
        df_shares_cc,
        x="identifier",
        y="share",
        color="ammonia_type",
        barmode="group",
        color_discrete_sequence=["blue", "green", "grey"],
        text=[f"{np.round(share*100)}%" for share in df_shares_cc["share"]],
    )

    fig.add_traces(bar_fig.data)
    add_titles_and_save_figure_html(
        save_path=save_path,
        fig=fig,
        xtitle="Year",
        ytitle="Share in global production volume (%)",
        title=f"Pathway {pathway}: Impact of carbon price on grey, blue, green ammonia shares",
        filename=f"shares_co2_cost_sens={sensitivity}",
        pathway=pathway,
        df=df_shares_cc,
    )


def create_cumulative_emissions_by_carbon_price(
    dict_sens: dict,
    pathway: str,
    save_path: str,
    carbon_costs: float,
    sensitivity: list,
    emissions_list: list,
):
    """Plot cumulative emissions by carbon price for a set sensitivity"""

    df_cumulative = pd.DataFrame()
    for carbon_cost in carbon_costs:

        df = dict_sens[pathway][sensitivity][carbon_cost]
        df = df.loc[df["parameter_group"] == "Emissions"]
        df = df.groupby(["parameter"]).sum()
        df = df.sum(axis=1) / 1e3
        df = df.rename(carbon_cost)
        df_cumulative = pd.concat([df_cumulative, df], axis=1)

    # We want to plot scope 1 + 2 CO2, CO2 scope 3 upstream and downstream, CO2e for all scopes
    gwp = GWP["GWP-100"]
    df_cumulative.loc["CO2 Scope 1&2"] = (
        df_cumulative.loc["CO2 Scope1"] + df_cumulative.loc["CO2 Scope2"]
    )
    for scope in ["Scope1", "Scope2", "Scope3 upstream", "Scope3 downstream"]:
        df_cumulative.loc[f"CO2e {scope}"] = (
            df_cumulative.loc[f"CH4 {scope}"] * gwp["ch4"]
            + df_cumulative.loc[f"N2O {scope}"] * gwp["n2o"]
            + df_cumulative.loc[f"CO2 {scope}"]
        )

    df = df_cumulative.reset_index()
    df = df.loc[df["index"].isin(emissions_list)]

    df = (
        df.set_index("index")
        .melt(ignore_index=False, var_name="carbon_cost", value_name="emissions")
        .reset_index()
    )

    fig = make_subplots()
    bar_fig = px.bar(
        data_frame=df,
        x="carbon_cost",
        y="emissions",
        color="index",
        text=[f"{np.round(emissions)} Gt" for emissions in df["emissions"]],
    )

    fig.add_traces(bar_fig.data)

    add_titles_and_save_figure_html(
        save_path=save_path,
        fig=fig,
        title=f"Pathway {pathway}: Impact of carbon price on cumulative scope 1&2 CO2 emissions",
        xtitle="Carbon cost (USD/tCO2)",
        ytitle="Cumulative scope 1 and 2 CO2 emissions",
        filename=f"cumulative_emissions_co2_cost_sens={sensitivity}",
        pathway=pathway,
        df=df,
    )


def create_cumulative_emissions_by_sensitivity(
    dict_sens: dict,
    pathway: str,
    save_path: str,
    carbon_cost: float,
    sensitivities: list,
    emissions_list: list,  # TODO: implement
):
    """Cumulative emissions for all sensitivities with a set carbon cost"""
    totals = []
    for sensitivity in sensitivities:
        df = dict_sens[pathway][sensitivity][carbon_cost]
        df = df.loc[df["parameter"].isin(["CO2 Scope1", "CO2 Scope2"])]
        df = df.groupby(["parameter"]).sum()
        total_Gt = df.sum().sum() / 1e3
        totals.append(total_Gt)

    fig = make_subplots()
    bar_fig = px.bar(
        x=sensitivities, y=totals, text=[f"{np.round(total, 2)} Gt" for total in totals]
    )

    fig.add_traces(bar_fig.data)

    df = pd.DataFrame(
        index=sensitivities, data={"cumulative_emissions_Gt": total for total in totals}
    )

    add_titles_and_save_figure_html(
        save_path=save_path,
        fig=fig,
        xtitle="Sensitivity",
        ytitle="Cumulative emissions",
        title=f"Pathway {pathway}: Impact of sensitivity on cumulative scope 1&2 CO2 emissions",
        filename=f"cumulative_emissions_sens_cc={carbon_cost}",
        pathway=pathway,
        df=df,
    )


def create_residual_emissions_by_carbon_price(
    dict_sens: dict,
    pathway: str,
    save_path: str,
    carbon_costs: float,
    sensitivity: list,
):
    """Plot Residual emissions by carbon cost for a set sensitivity."""
    totals = []
    shares = []

    for carbon_cost in carbon_costs:
        df = dict_sens[pathway][sensitivity][carbon_cost]
        df = df.loc[df["parameter"].isin(["CO2 Scope1", "CO2 Scope2"])]
        df = df.groupby(["parameter"]).sum()
        initial_Mt = df["2020"].sum()
        residual_Mt = df["2050"].sum()
        totals.append(residual_Mt)
        shares.append(residual_Mt / initial_Mt)

    fig = make_subplots()
    bar_fig = px.bar(
        x=[str(c) for c in carbon_costs],
        y=totals,
        text=[f"{np.round(total, 2)} Mt" for total in totals],
    )

    fig.add_traces(bar_fig.data)
    df = pd.DataFrame(
        index=carbon_costs, data={"residual_emissions_Mt": total for total in totals}
    )

    add_titles_and_save_figure_html(
        save_path=save_path,
        fig=fig,
        xtitle="Carbon cost (USD/tCO2)",
        ytitle="Residual scope 1 and 2 CO2 emissions",
        title=f"Pathway {pathway}: Impact of carbon price on residual scope 1&2 CO2 emissions",
        filename=f"residual_emissions_co2_cost_sens={sensitivity}",
        pathway=pathway,
        df=df,
    )

    fig = make_subplots()
    bar_fig = px.bar(
        x=carbon_costs,
        y=shares,
        text=[f"{np.round(share*100, 1)} %" for share in shares],
    )

    fig.add_traces(bar_fig.data)
    df = pd.DataFrame(
        index=carbon_costs, data={"residual_emissions_share": share for share in shares}
    )

    add_titles_and_save_figure_html(
        save_path=save_path,
        fig=fig,
        xtitle="Carbon cost (USD/tCO2)",
        ytitle="Share of residual scope 1 and 2 CO2 emissions",
        title=f"Pathway {pathway}: Impact of carbon price on share of residual scope 1&2 CO2 emissions",
        filename=f"share_residual_emissions_co2_cost_sens={sensitivity}",
        pathway=pathway,
        df=df,
    )


def create_residual_emissions_by_sensitivity(
    dict_sens: dict,
    pathway: str,
    save_path: str,
    carbon_cost: float,
    sensitivities: list,
):
    """Plot Residual emissions by sensitivity for a set carbon cost."""

    totals = []
    shares = []
    for sensitivity in sensitivities:

        df = dict_sens[pathway][sensitivity][carbon_cost]
        df = df.loc[df["parameter"].isin(["CO2 Scope1", "CO2 Scope2"])]
        df = df.groupby(["parameter"]).sum()
        initial_Mt = df["2020"].sum()
        residual_Mt = df["2050"].sum()
        totals.append(residual_Mt)
        shares.append(residual_Mt / initial_Mt)

    fig = make_subplots()
    bar_fig = px.bar(
        x=sensitivities,
        y=totals,
        text=[f"{np.round(total, 2)} Mt" for total in totals],
    )

    fig.add_traces(bar_fig.data)
    df = pd.DataFrame(
        index=sensitivities, data={"residual_emissions_Mt": total for total in totals}
    )

    add_titles_and_save_figure_html(
        save_path=save_path,
        fig=fig,
        xtitle="Carbon cost (USD/tCO2)",
        ytitle="Residual scope 1 and 2 CO2 emissions",
        title=f"Pathway {pathway}: Impact of sensitivity on residual scope 1&2 CO2 emissions",
        filename=f"residual_emissions_sens_cc={carbon_cost}",
        pathway=pathway,
        df=df,
    )

    fig = make_subplots()
    bar_fig = px.bar(
        x=sensitivities,
        y=shares,
        text=[f"{np.round(share*100, 1)} %" for share in shares],
    )

    fig.add_traces(bar_fig.data)
    df = pd.DataFrame(
        index=sensitivities,
        data={"residual_emissions_share": share for share in shares},
    )

    add_titles_and_save_figure_html(
        save_path=save_path,
        fig=fig,
        xtitle="Carbon cost (USD/tCO2)",
        ytitle="Share of residual scope 1 and 2 CO2 emissions in initial emissions",
        title=f"Pathway {pathway}: Impact of sensitivity on share of residual scope 1&2 CO2 emissions",
        filename=f"share_residual_emissions_sens_cc={carbon_cost}",
        pathway=pathway,
        df=df,
    )

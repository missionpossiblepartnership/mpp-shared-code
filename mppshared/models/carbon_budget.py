from copy import deepcopy

import numpy as np
import pandas as pd

from mppshared.config import (
    SECTORAL_CARBON_BUDGETS,
    SECTORAL_PATHWAYS,
    START_YEAR,
    END_YEAR,
)
from mppshared.import_data.intermediate_data import IntermediateDataImporter

import plotly.express as px
from plotly.offline import plot
from plotly.subplots import make_subplots
import plotly.io as pio
pio.kaleido.scope.mathjax = None


class CarbonBudget:
    def __init__(self, sectoral_carbon_budgets: dict, pathway_shape: str):
        self.budgets = sectoral_carbon_budgets
        self.pathway_shape = pathway_shape
        self.pathways = self.set_emission_pathways()

    def __repr__(self):
        return "Carbon Budget Class"

    def __str__(self):
        return "Instance of Carbon Budget"

    def set_budget_dict(self, budget_dict: dict):
        self.budgets = deepcopy(budget_dict)
        self.pathways = {}

    def list_pathways(self):
        return list(self.pathways.keys())

    def total_budget_all_sectors(self):
        return sum(list(self.budgets.values()))

    def create_emissions_pathway(self, pathway_shape: str, sector: str) -> pd.DataFrame:
        """Create emissions pathway for specified sector according to given shape"""
        index = pd.RangeIndex(START_YEAR, END_YEAR + 1, step=1, name="year")

        # Annual emissions are reduced linearly
        # TODO: implement in a better way
        trajectory = SECTORAL_PATHWAYS[sector]
        if pathway_shape == "linear":
            initial_level = np.full(
                trajectory["action_start"] - START_YEAR,
                trajectory["emissions_start"],
            )
            linear_reduction = np.linspace(
                trajectory["emissions_start"],
                trajectory["emissions_end"],
                num=END_YEAR - trajectory["action_start"] + 1,
            )
            values = np.concatenate((initial_level, linear_reduction))
        # TODO: implement other pathway shapes
        df = pd.DataFrame(data={"year": index, "annual_limit": values}).set_index(
            "year"
        )
        return df

    def set_emission_pathways(self):
        """Set emission pathways for all sectors."""
        return {
            sector: self.create_emissions_pathway(
                pathway_shape=self.pathway_shape, sector=sector
            )
            for sector in self.budgets.keys()
        }

    def get_annual_emissions_limit(self, year: int, sector: str) -> float:
        """Get scope 1 and 2 CO2 emissions limit for a specific year for the given sector"""
        df = self.pathways[sector]
        return df.loc[year, "annual_limit"]

    # TODO: implement
    def output_emissions_pathway(self, sector: str, importer: IntermediateDataImporter):
        df = self.pathways[sector]
        fig = make_subplots()
        line_fig = px.line(df, x=df.index, y="annual_limit")

        fig.add_traces(line_fig.data)

        fig.layout.xaxis.title = "Year"
        fig.layout.yaxis.title = "CO2 emissions (GtCO2/year)"
        cumulative_emissions = np.round(df["annual_limit"].sum(), 1)
        fig.layout.title = f"Emission trajectory aligned with carbon budget (Cumulative emissions: {cumulative_emissions} GtCO2)"

        plot(
            fig,
            filename=str(importer.final_path.joinpath("carbon_budget.html")),
            auto_open=False,
        )

        # TODO: debug why writing image with kaleido enters into seemingly infinite loop
        # fig.write_image(importer.final_path.joinpath("carbon_budget.png"), engine="kaleido")
        importer.export_data(df, "carbon_budget.csv", "final")

    def pathway_getter(self, sector: str, year: int, value_type: str):
        mapper = {"annual": "annual_limit", "cumulative": "cumulative_limit"}
        return self.pathways[sector].loc[year][mapper[value_type]]


def carbon_budget_test():
    CarbonBudget = CarbonBudget()
    CarbonBudget.set_budget_dict(CARBON_BUDGET_REF)
    CarbonBudget.total_budget_all_sectors()
    pathway = CarbonBudget.set_emissions_pathway(2020, 2050, "steel", "straight")
    print(pathway)
    CarbonBudget.plot_emissions_pathway("steel")
    print(CarbonBudget.pathway_getter("steel", 2030, "annual"))

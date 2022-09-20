import sys

import numpy as np
import pandas as pd
import plotly.express as px
from plotly.offline import plot
from plotly.subplots import make_subplots

from mppshared.config import LOG_LEVEL
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


class CarbonBudget:
    def __init__(
        self,
        start_year: int,
        end_year: int,
        sectoral_carbon_budgets: dict,
        pathway_shape: str,
        sector: str,
        carbon_budget_sector_csv: bool,
        sectoral_carbon_pathway: dict,
        importer: IntermediateDataImporter,
    ):
        logger.info("Initializing Carbon Budget")
        self.start_year = start_year
        self.end_year = end_year
        self.sector = sector
        self.budgets = sectoral_carbon_budgets
        self.pathway_shape = pathway_shape
        self.importer = importer
        self.carbon_budget_sector_csv = carbon_budget_sector_csv
        self.sectoral_carbon_pathway = sectoral_carbon_pathway
        self.df_pathway = self.create_emissions_pathway(pathway_shape=pathway_shape)
        logger.info("Carbon Budget initialized")

    def __repr__(self):
        return "Carbon Budget Class"

    def __str__(self):
        return "Instance of Carbon Budget"

    def total_budget_all_sectors(self):
        return sum(list(self.budgets.values()))

    def create_emissions_pathway(self, pathway_shape: str) -> pd.DataFrame:
        """Create emissions pathway for specified sector according to given shape"""
        if self.carbon_budget_sector_csv:
            df = self.importer.get_carbon_budget()
            df.set_index("year", inplace=True)
        else:
            index = pd.RangeIndex(
                self.start_year, self.end_year + 1, step=1, name="year"
            )

            # Annual emissions are reduced linearly
            trajectory = self.sectoral_carbon_pathway
            if pathway_shape == "linear":
                initial_level = np.full(
                    trajectory["action_start"] - self.start_year,
                    trajectory["emissions_start"],
                )
                linear_reduction = np.linspace(
                    trajectory["emissions_start"],
                    trajectory["emissions_end"],
                    num=self.end_year - trajectory["action_start"] + 1,
                )
                values = np.concatenate((initial_level, linear_reduction))

                if values.sum() > self.budgets[self.sector]:
                    sys.exit(
                        "Config parameters for linear shape do not yield carbon budget shape within the sectoral "
                        "budget!"
                    )

            if pathway_shape == "cement":
                # init values with immediate action start
                values1 = np.linspace(
                    start=trajectory["emissions_start"],
                    stop=0.6 * trajectory["emissions_start"],
                    num=2035 - self.start_year,
                )
                values2 = np.linspace(
                    start=0.6 * trajectory["emissions_start"],
                    stop=trajectory["emissions_end"],
                    num=self.end_year - 2035 + 2,
                )[1:]
                values = np.concatenate((values1, values2))

                # check whether the initial values are within the total carbon budget and revert to linear shape if so
                if values.sum() > self.budgets[self.sector]:
                    logger.critical(
                        "Cannot find exponential carbon budget shape within the sectoral budget! "
                        "Revert to linear shape."
                    )
                    self.pathway_shape = "linear"
                    self.create_emissions_pathway(pathway_shape=self.pathway_shape)

            df = pd.DataFrame(data={"year": index, "annual_limit": values}).set_index(
                "year"
            )
        return df

    def get_annual_emissions_limit(self, year: int) -> float:
        """Get scope 1 and 2 CO2 emissions limit for a specific year for the given sector"""
        return self.df_pathway.loc[year, "annual_limit"]

    def output_carbon_budget(self, sector: str, importer: IntermediateDataImporter):
        if self.carbon_budget_sector_csv:
            df = self.importer.get_carbon_budget()
            df.set_index("year", inplace=True)
        else:
            df = self.df_pathway
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

        importer.export_data(df, "carbon_budget.csv", "final")

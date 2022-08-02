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
        self.budgets = sectoral_carbon_budgets
        self.pathway_shape = pathway_shape
        self.importer = importer
        self.carbon_budget_sector_csv = carbon_budget_sector_csv
        self.sectoral_carbon_pathway = sectoral_carbon_pathway
        self.df_pathway = self.create_emissions_pathway(
            pathway_shape=pathway_shape, sector=sector
        )
        logger.info("Carbon Budget initialized")

    def __repr__(self):
        return "Carbon Budget Class"

    def __str__(self):
        return "Instance of Carbon Budget"

    def list_pathways(self):
        return list(self.pathways.keys())

    def total_budget_all_sectors(self):
        return sum(list(self.budgets.values()))

    def create_emissions_pathway(self, pathway_shape: str, sector: str) -> pd.DataFrame:
        """Create emissions pathway for specified sector according to given shape"""
        if self.carbon_budget_sector_csv:
            df = self.importer.get_carbon_budget()
            df.set_index("year", inplace=True)
        else:
            index = pd.RangeIndex(
                self.start_year, self.end_year + 1, step=1, name="year"
            )

            # Annual emissions are reduced linearly
            # TODO: implement in a better way
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
            # TODO: implement other pathway shapes
            df = pd.DataFrame(data={"year": index, "annual_limit": values}).set_index(
                "year"
            )
        return df

    def get_annual_emissions_limit(self, year: int, sector: str) -> float:
        """Get scope 1 and 2 CO2 emissions limit for a specific year for the given sector"""
        return self.df_pathway.loc[year, "annual_limit"]

    # TODO: implement
    def output_emissions_pathway(self, sector: str, importer: IntermediateDataImporter):
        if self.carbon_budget_sector_csv == True:
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

    def pathway_getter(self, sector: str, year: int, value_type: str):
        """pathway_getter.

        Args:
            sector (str): sector
            year (int): year
            value_type (str): value_type
        """
        mapper = {"annual": "annual_limit", "cumulative": "cumulative_limit"}
        return self.pathways[sector].loc[year][mapper[value_type]]

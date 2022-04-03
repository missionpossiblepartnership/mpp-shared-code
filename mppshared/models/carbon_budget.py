from copy import deepcopy

import numpy as np
import pandas as pd

from mppshared.config import SECTORAL_CARBON_BUDGETS, START_YEAR, END_YEAR


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
        cumulative_max = self.budgets[sector]
        if pathway_shape == "linear":
            values = np.linspace(cumulative_max, 0, num=len(index))
        elif pathway_shape == "log":
            values = np.logspace(cumulative_max, 0, num=len(index))

        # TODO: exponential is non-sensical, debug
        elif pathway_shape == "exp":
            values = np.geomspace(cumulative_max, 1e-10, num=len(index))
        df = pd.DataFrame(data={"year": index, "cumulative_limit": values}).set_index(
            "year"
        )
        df_a = df.diff(-1).fillna(0)
        df["annual_limit"] = df_a["cumulative_limit"]
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

    def plot_emissions_pathway(self, sector: str):
        self.pathways[sector].plot()

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

from copy import deepcopy

import numpy as np
import pandas as pd

from mppshared.config import CARBON_BUDGET_REF


class CarbonBudgetClass:
    def __init__(self):
        self.budgets = {}
        self.pathways = {}

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

    def create_emissions_pathway(
        self, year_start: int, year_end: int, end_value: float, line_shape: str
    ):
        index = pd.RangeIndex(year_start, year_end + 1, step=1, name="year")
        if line_shape == "straight":
            values = np.linspace(end_value, 0, num=len(index))
        elif line_shape == "log":
            values = np.logspace(end_value, 0, num=len(index))
        elif line_shape == "exp":
            values = np.geomspace(end_value, 0, num=len(index))
        df = pd.DataFrame(data={"year": index, "cumulative_limit": values}).set_index(
            "year"
        )
        df_a = df.diff(-1).fillna(0)
        df["annual_limit"] = df_a["cumulative_limit"]
        return df

    def set_emissions_pathway(
        self, year_start: int, year_end: int, sector: str, line_shape: str = "straight"
    ):
        budget_value = self.budgets[sector]
        emissions_pathway = self.create_emissions_pathway(
            year_start, year_end, budget_value, line_shape
        )
        self.pathways[sector] = emissions_pathway
        return emissions_pathway

    def plot_emissions_pathway(self, sector: str):
        self.pathways[sector].plot()

    def pathway_getter(self, sector: str, year: int, value_type: str):
        mapper = {"annual": "annual_limit", "cumulative": "cumulative_limit"}
        return self.pathways[sector].loc[year][mapper[value_type]]


def carbon_budget_test():
    CarbonBudget = CarbonBudgetClass()
    CarbonBudget.set_budget_dict(CARBON_BUDGET_REF)
    CarbonBudget.total_budget_all_sectors()
    pathway = CarbonBudget.set_emissions_pathway(2020, 2050, "steel", "straight")
    print(pathway)
    CarbonBudget.plot_emissions_pathway("steel")
    print(CarbonBudget.pathway_getter("steel", 2030, "annual"))

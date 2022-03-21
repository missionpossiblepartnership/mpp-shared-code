import pandas as pd
from mppshared.config import MODEL_YEARS


class CarbonCostTrajectory:
    """Class to define a yearly carbon cost trajectory."""

    def __init__(self, trajectory):
        self.df_carbon_cost = pd.DataFrame(
            data={"year": MODEL_YEARS, "carbon_cost": None}
        )
        self.trajectory = trajectory

    def set_carbon_cost(self):
        if self.trajectory == "constant":
            self.df_carbon_cost["carbon_cost"] = 50

    def get_carbon_cost(self, year: int) -> float:
        return self.df_carbon_cost.set_index("year").loc[year, "carbon_cost"]

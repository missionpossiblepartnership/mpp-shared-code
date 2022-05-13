import pandas as pd
import numpy as np

from mppshared.config import END_YEAR, MODEL_YEARS, START_YEAR


class CarbonCostTrajectory:
    """Class to define a yearly carbon cost trajectory."""

    def __init__(self, trajectory, initial_carbon_cost, final_carbon_cost):

        # Initialize attributes
        self.trajectory = trajectory

        # Initialize DataFrame with carbon cost trajectory
        self.set_carbon_cost(trajectory, initial_carbon_cost, final_carbon_cost)

    def set_carbon_cost(
        self, trajectory: str, initial_carbon_cost: float, final_carbon_cost: float
    ):
        """Set carbon cost trajectory in the form of a DataFrame with columns "year", "carbon_cost"

        Args:
            trajectory: either of "constant", # TODO
            initial_carbon_cost: carbon cost at MODEL_START_YEAR in USD/tCO2
            final_carbon_cost: carbon cost at MODEL_END_YEAR in USD/tCO2
        """
        # Initialize DataFrame
        self.df_carbon_cost = pd.DataFrame(
            data={"year": MODEL_YEARS, "carbon_cost": None}
        )

        # Constant carbon cost
        if trajectory == "constant":
            self.df_carbon_cost["carbon_cost"] = initial_carbon_cost

        elif trajectory == "linear":
            self.df_carbon_cost["carbon_cost"] = np.linspace(
                initial_carbon_cost, final_carbon_cost, num=END_YEAR - START_YEAR
            )

        # TODO: implement logistic carbon cost

        # TODO: implement exponential carbon cost

    def get_carbon_cost(self, year: int) -> float:
        return self.df_carbon_cost.set_index("year").loc[year, "carbon_cost"]

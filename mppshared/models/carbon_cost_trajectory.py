import numpy as np
import pandas as pd


class CarbonCostTrajectory:
    """Class to define a yearly carbon cost trajectory."""

    def __init__(
        self,
        trajectory,
        initial_carbon_cost,
        final_carbon_cost,
        start_year,
        end_year,
        model_years: range,
    ):

        # Initialize attributes
        self.trajectory = trajectory
        self.model_years = model_years

        # Initialize DataFrame with carbon cost trajectory
        self.df_carbon_cost = self.set_carbon_cost(
            trajectory=self.trajectory,
            initial_carbon_cost=initial_carbon_cost,
            final_carbon_cost=final_carbon_cost,
            start_year=start_year,
            end_year=end_year,
        )

    def set_carbon_cost(
        self,
        trajectory: str,
        initial_carbon_cost: float,
        final_carbon_cost: float,
        start_year: int,
        end_year: int,
    ):
        """Set carbon cost trajectory in the form of a DataFrame with columns "year", "carbon_cost"
        Args:
            trajectory: either of "constant", "linear", # TODO
            initial_carbon_cost: carbon cost at MODEL_START_YEAR in USD/tCO2
            final_carbon_cost: carbon cost at MODEL_END_YEAR in USD/tCO2
            start_year:
            end_year:
        """
        # Initialize DataFrame
        df_carbon_cost = pd.DataFrame(
            data={"year": self.model_years, "carbon_cost": None}
        )

        # TODO: make this much nicer
        # Constant carbon cost
        if trajectory == "constant":
            df_carbon_cost.loc[df_carbon_cost["year"] < start_year, "carbon_cost"] = 0
            df_carbon_cost.loc[
                df_carbon_cost["year"] >= start_year, "carbon_cost"
            ] = initial_carbon_cost
        elif trajectory == "linear":
            df_carbon_cost.loc[df_carbon_cost["year"] < start_year, "carbon_cost"] = 0
            df_carbon_cost.loc[
                df_carbon_cost["year"].between(start_year, end_year), "carbon_cost"
            ] = np.linspace(
                initial_carbon_cost, final_carbon_cost, num=end_year - start_year + 1
            )
            df_carbon_cost.loc[
                df_carbon_cost["year"] >= end_year, "carbon_cost"
            ] = final_carbon_cost

        # TODO: implement logistic carbon cost

        # TODO: implement exponential carbon cost

        df_carbon_cost = df_carbon_cost.astype(
            dtype={"year": int, "carbon_cost": float}
        )

        return df_carbon_cost

    def get_carbon_cost(self, year: int) -> float:
        return self.df_carbon_cost.set_index("year").loc[year, "carbon_cost"]

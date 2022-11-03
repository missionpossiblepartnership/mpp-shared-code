""" Class that describes the ramp-up of a technology to be used as a model constraint."""
import sys

import numpy as np
import pandas as pd


class TechnologyRampup:
    """Describes an approximately exponential ramp-up trajectory for a technology with a maximum number of absolute
    asset additions per year.
    """

    def __init__(
        self,
        model_start_year: int,
        model_end_year: int,
        technology: str,
        ramp_up_start_year: int,
        ramp_up_end_year: int,
        init_maximum_asset_additions: int,
        maximum_asset_growth_rate: float,
        curve_type: str,
    ):
        """
        Args:
            model_start_year:
            model_end_year:
            technology: technology to be ramped-up
            ramp_up_start_year: Start year for technology ramp-up (year of technology maturity from technology
                characteristics)
            ramp_up_end_year: End year for technology ramp-up
            init_maximum_asset_additions: Maximum number of assets that can be added in ramp_up_start_year
            maximum_asset_growth_rate: Maximum rate at which number of assets per technology can grow from one
                year to the next
            curve_type: "exponential" or "rayleigh"
        """
        self.model_start_year = model_start_year
        self.model_end_year = model_end_year
        self.technology = technology
        self.ramp_up_start_year = ramp_up_start_year
        self.ramp_up_end_year = (ramp_up_end_year if ramp_up_end_year <= model_end_year else model_end_year)
        self.init_maximum_asset_additions = init_maximum_asset_additions
        self.maximum_asset_growth_rate = maximum_asset_growth_rate
        self.curve_type = curve_type
        self.df_rampup = self.create_rampup_df()

    def create_rampup_df(self):
        """
        Create DataFrame indexed by year with absolute maximum number of asset additions. The shape of the curver is
            either...
            - exponential: init_maximum_asset_additions as baseline value that grows with annual rate
                maximum_asset_growth_rate
            - rayleigh: takes init_maximum_asset_additions as baseline and adds rayleigh-shaped curve to it. It uses
                maximum_asset_growth_rate * init_maximum_asset_additions as the maximum, which will be reached in the
                first years after steep incline. After the maximum, the curve rapidly declines convexly to the baseline.
        """

        df_rampup = pd.DataFrame(
            index=np.arange(self.model_start_year, self.model_end_year + 1),
            columns=["maximum_asset_additions"],
        )
        df_rampup = df_rampup.astype(dtype={"maximum_asset_additions": float})

        # exponential
        if self.curve_type == "exponential":
            for year in np.arange(self.model_start_year, self.model_end_year + 1):
                if year == self.ramp_up_start_year:
                    df_rampup.loc[year, "maximum_asset_additions"] = float(
                        self.init_maximum_asset_additions
                    )
                elif year in np.arange(
                    self.ramp_up_start_year + 1, self.ramp_up_end_year + 1
                ):
                    df_rampup.loc[year, "maximum_asset_additions"] = df_rampup.loc[
                        year - 1, "maximum_asset_additions"
                    ] * (1 + self.maximum_asset_growth_rate)
                else:
                    df_rampup.loc[year, "maximum_asset_additions"] = np.nan

        # rayleigh
        elif self.curve_type == "rayleigh":
            step = (10 / (self.ramp_up_end_year - self.ramp_up_start_year))
            ramp_up = np.arange(0, 10 + step/2, step)
            std = 3
            # get shape
            ramp_up = (ramp_up / std ** 2) * np.exp((-(ramp_up ** 2)) / (2 * (std ** 2)))
            # scale
            ramp_up *= (self.init_maximum_asset_additions * (self.maximum_asset_growth_rate - 1)) / np.amax(ramp_up)
            # add baseline
            ramp_up += self.init_maximum_asset_additions
            # add to df_ramp_up
            df_rampup.loc[self.ramp_up_start_year:(self.ramp_up_end_year + 1), "maximum_asset_additions"] = ramp_up

        else:
            sys.exit(f"Unknown ramp up curve type provided: {self.curve_type}")

        df_rampup = df_rampup.apply(lambda x: np.round(x, decimals=0))

        return df_rampup

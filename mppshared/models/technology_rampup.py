""" Class that describes the ramp-up of a technology to be used as a model constraint."""

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
        """
        self.model_start_year = model_start_year
        self.model_end_year = model_end_year
        self.technology = technology
        self.ramp_up_start_year = ramp_up_start_year
        self.ramp_up_end_year = ramp_up_end_year
        self.init_maximum_asset_additions = init_maximum_asset_additions
        self.maximum_asset_growth_rate = maximum_asset_growth_rate
        self.df_rampup = self.create_rampup_df()

    def create_rampup_df(self):
        """Create DataFrame indexed by year with absolute maximum number of asset additions."""

        df_rampup = pd.DataFrame(
            index=np.arange(self.model_start_year, self.model_end_year + 1),
            columns=["maximum_asset_additions"],
        )
        df_rampup = df_rampup.astype(dtype={"maximum_asset_additions": float})

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

        df_rampup = df_rampup.apply(lambda x: np.round(x, decimals=0))

        return df_rampup

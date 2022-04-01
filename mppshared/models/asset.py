"""Asset and asset stack classes, code adapted from MCC"""
from uuid import uuid4

import pandas as pd

from mppshared.config import (
    DECOMMISSION_RATES,
    CUF_LOWER_THRESHOLD,
)

from mppshared.utility.utils import first


class Asset:
    """Define an asset that produces a specific product with a specific technology."""

    def __init__(
        self,
        product: str,
        technology: str,
        region: str,
        year_commissioned: int,
        annual_production_capacity: float,
        capacity_factor: float,
        asset_lifetime: int,
        df_asset_capacities: pd.DataFrame,
        type_of_tech="Initial",
        retrofit=False,
        asset_status="new",
    ):
        # Unique ID to identify and compare assets
        self.uuid = uuid4().hex

        # Characteristics
        self.product = product
        self.technology = technology
        self.region = region
        self.year_commissioned = year_commissioned

        # Production capacity parameters
        self.annual_production_capacity = annual_production_capacity
        self.capacity_factor = capacity_factor
        self.df_asset_capacities = df_asset_capacities
        self.capacities = self.import_capacities()

        # Asset status parameters
        self.retrofit = retrofit
        self.asset_status = asset_status
        self.asset_lifetime = asset_lifetime
        self.type_of_tech = type_of_tech

    def __eq__(self, other):
        return self.uuid == other.uuid

    def __ne__(self, other):
        return self.uuid != other.uuid

    def get_age(self, year):
        return year - self.year_commissioned

    def import_capacities(self) -> dict:
        """Import asset capacities for the different products that this asset produces"""
        df = self.df_asset_capacities

        # Find the capacities
        df_capacities = df[
            (df.technology == self.technology) & (df.region == self.region)
        ]

        return {
            product: df_capacities.loc[
                df_capacities["product"] == product, "annual_production_capacity"
            ].values[0]
            for product in df_capacities["product"]
        }

    def get_capacity(self, product=None):
        """Get asset capacity"""
        return self.capacities.get(product or self.product, 0)

    def get_annual_production(self, product):
        return self.get_capacity(product) * self.capacity_factor


def create_assets(n_assets: int, df_asset_capacities: pd.DataFrame, **kwargs) -> list:
    """Convenience function to create a list of asset at once"""
    return [
        Asset(df_asset_capacities=df_asset_capacities, **kwargs)
        for _ in range(n_assets)
    ]


class AssetStack:
    def __init__(self, assets: list):
        self.assets = assets
        # Keep track of all assets added this year
        self.new_ids = []

    def remove(self, remove_asset):
        self.assets = [asset for asset in self.assets if asset != remove_asset]

    def append(self, new_asset):
        self.assets.append(new_asset)
        self.new_ids.append(new_asset.uuid)

    def empty(self):
        """Return True if no asset in stack"""
        return not self.assets

    def filter_assets(self, sector=None, region=None, technology=None, product=None):
        """Filter asset based on one or more criteria"""
        assets = self.assets
        if sector is not None:
            assets = filter(lambda asset: asset.sector == sector, assets)
        if region is not None:
            assets = filter(lambda asset: asset.region == region, assets)
        if technology is not None:
            assets = filter(lambda asset: asset.technology == technology, assets)
        if product is not None:
            assets = filter(
                lambda asset: (asset.product == product)
                or (product in asset.byproducts),
                assets,
            )
        # Commenting out the following lines as it is not cleare if we will need
        # something similar for ammonia and aluminium
        # if methanol_type is not None:
        #     asset = filter(
        #         lambda asset: asset.technology in METHANOL_SUPPLY_TECH[methanol_type],
        #         asset,
        #     )

        return list(assets)

    def get_fossil_assets(self, product):
        return [
            asset
            for asset in self.assets
            if (
                (asset.technology in DECOMMISSION_RATES.keys())
                and (asset.product == product)
            )
        ]

    def get_capacity(self, product, methanol_type=None, **kwargs):
        """Get the asset capacity, optionally filtered by region, technology, product"""
        if methanol_type is not None:
            kwargs["methanol_type"] = methanol_type

        assets = self.filter_assets(product=product, **kwargs)
        return sum(asset.get_capacity(product) for asset in assets)

    def get_annual_production(self, product, **kwargs):
        """Get the yearly volume, optionally filtered by region, technology, product"""

        assets = self.filter_assets(product=product, **kwargs)
        return sum(asset.get_annual_production(product=product) for asset in assets)

    def get_tech(self, id_vars, product=None):
        """
        Get technologies of this stack

        Args:
            id_vars: aggregate by these variables

        Returns:
            Dataframe with technologies
        """

        df = pd.DataFrame(
            [
                {
                    "product": asset.product,
                    "technology": asset.technology,
                    "region": asset.region,
                    "retrofit": asset.retrofit,
                    "capacity": asset.get_capacity(product),
                }
                for asset in self.assets
            ]
        )
        try:
            return df.groupby(id_vars).agg(
                capacity=("capacity", "sum"), number_of_assets=("capacity", "count")
            )
        except KeyError:
            # There are no asset
            return pd.DataFrame()

    def get_new_asset_stack(self):
        return AssetStack(
            assets=[asset for asset in self.assets if asset.asset_status == "new"]
        )

    def get_old_asset_stack(self):
        return AssetStack(
            assets=[asset for asset in self.assets if asset.asset_status == "old"]
        )

    def get_unique_tech(self, product=None):
        if product is not None:
            assets = self.filter_assets(product=product)
        else:
            assets = self.assets

        valid_combos = {(asset.technology, asset.region) for asset in assets}
        return pd.DataFrame(valid_combos, columns=["technology", "region"])

    def get_regional_contribution(self):
        df_agg = (
            pd.DataFrame(
                [
                    {
                        "region": asset.region,
                        "capacity": asset.get_capacity(),
                    }
                    for asset in self.assets
                ]
            )
            .groupby("region", as_index=False)
            .sum()
        )
        df_agg["proportion"] = df_agg["capacity"] / df_agg["capacity"].sum()
        return df_agg

    def get_regional_production(self, product):
        return (
            pd.DataFrame(
                {
                    "region": asset.region,
                    "annual_production": asset.get_annual_production(product),
                }
                for asset in self.assets
            )
            .groupby("region", as_index=False)
            .sum()
        )

    def aggregate_stack(self, product=None, year=None, this_year=False):

        # Filter for product
        if product is not None:
            assets = self.filter_assets(product=product)
        else:
            assets = self.assets

        # Keep only asset that were built in a year
        if this_year:
            assets = [asset for asset in assets if asset.uuid in self.new_ids]

        # Calculate capacity and number of asset for new and retrofit
        try:
            df_agg = (
                pd.DataFrame(
                    [
                        {
                            "capacity": asset.get_capacity(product),
                            "yearly_volume": asset.get_annual_production(
                                product=product
                            ),
                            "technology": asset.technology,
                            "region": asset.region,
                            "retrofit": asset.retrofit,
                        }
                        for asset in assets
                    ]
                )
                .groupby(["technology", "region", "retrofit"], as_index=False)
                .agg(
                    capacity=("capacity", "sum"),
                    number_of_assets=("capacity", "count"),
                    yearly_volume=("yearly_volume", "sum"),
                )
            ).fillna(0)

            # Helper column to avoid having True and False as column names
            df_agg["build_type"] = "new_build"
            df_agg.loc[df_agg.retrofit, "build_type"] = "retrofit"

            df = df_agg.pivot_table(
                values=["capacity", "number_of_assets", "yearly_volume"],
                index=["region", "technology"],
                columns="build_type",
                dropna=False,
                fill_value=0,
            )

            # Make sure all columns are present
            for col in [
                ("capacity", "retrofit"),
                ("capacity", "new_build"),
                ("number_of_assets", "retrofit"),
                ("number_of_assets", "new_build"),
                ("yearly_volume", "retrofit"),
                ("yearly_volume", "new_build"),
            ]:
                if col not in df.columns:
                    df[col] = 0

            # Add totals
            df[("capacity", "total")] = (
                df[("capacity", "new_build")] + df[("capacity", "retrofit")]
            )
            df[("number_of_assets", "total")] = (
                df[("number_of_assets", "new_build")]
                + df[("number_of_assets", "retrofit")]
            )
            df[("yearly_volume", "total")] = (
                df[("yearly_volume", "new_build")] + df[("yearly_volume", "retrofit")]
            )

        # No asset exist
        except KeyError:
            return pd.DataFrame()

        df.columns.names = ["quantity", "build_type"]

        # Add year to index if passed (to help identify chunks)
        if year is not None:
            df["year"] = year
            df = df.set_index("year", append=True)

        return df

    def get_tech_asset_stack(self, technology: str):
        return AssetStack(
            assets=[asset for asset in self.assets if asset.technology == technology]
        )

    def get_assets_eligible_for_decommission(self) -> list():
        """Return a list of Assets from the AssetStack that are eligible for decommissioning

        Returns:
            list of Assets
        """
        # Filter for CUF < threshold
        candidates = filter(
            lambda asset: asset.capacity_factor < CUF_LOWER_THRESHOLD, self.assets
        )

        # TODO: filter based on asset age

        return list(candidates)

    def export_stack_to_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "product": asset.product,
                "region": asset.region,
                "technology": asset.technology,
                "daily_production_capacity": asset.get_capacity(),
                "capacity_factor": asset.capacity_factor,
                "asset_lifetime": asset.asset_lifetime,
                "retrofit_status": asset.retrofit,
                "uuid": asset.uuid,
            }
            for asset in self.assets
        )


def make_new_asset(
    asset_transition, df_process_data, year, retrofit, product, df_asset_capacities
):
    """
    Make a new asset, based on a transition entry from the ranking dataframe

    Args:
        asset_transition: The best transition (destination is the asset to build)
        df_process_data: The inputs dataframe (needed for asset specs)
        year: Build the asset in this year
        retrofit: Asset is retrofitted from an old asset

    Returns:
        The new asset
    """
    df_process_data = df_process_data.reset_index()
    spec = df_process_data[
        (df_process_data.technology == asset_transition["technology_destination"])
        & (df_process_data.year == asset_transition["year"])
        & (df_process_data.region == asset_transition["region"])
    ]

    # Map tech type back from ints
    # TODO: Integrate type of tech destination into the asset transition (this throws a bag)
    types_of_tech = {1: "Initial", 2: "Transition", 3: "End-state"}
    type_of_tech = types_of_tech[asset_transition["type_of_tech_destination"]]

    return Asset(
        sector=first(spec["sector"]),  # TODO: this also throws a bug
        product=product,
        technology=first(spec["technology"]),
        region=first(spec["region"]),
        year_commissioned=year,
        retrofit=retrofit,
        asset_lifetime=first(spec["spec", "", "asset_lifetime"]),
        capacity_factor=first(spec["spec", "", "capacity_factor"]),
        type_of_tech=type_of_tech,
        df_asset_capacities=df_asset_capacities,
    )

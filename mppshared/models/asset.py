"""Asset and asset stack classes, code adapted from MCC"""
from uuid import uuid4
from xmlrpc.client import Boolean

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
        cuf: float,
        asset_lifetime: int,
        technology_classification="Initial",
        retrofit=False,
    ):
        # Unique ID to identify and compare assets
        self.uuid = uuid4().hex

        # Characteristics
        self.product = product
        self.technology = technology
        self.region = region
        self.year_commissioned = year_commissioned

        # Production capacity parameters
        self.annual_production_capacity = annual_production_capacity  # unit: Mt/year
        self.cuf = cuf  # capacity utilisation factor (decimal)

        # Asset status parameters
        self.retrofit = retrofit
        self.asset_lifetime = asset_lifetime  # unit: years
        self.type_of_tech = technology_classification

    def __str__(self):
        return f"<Asset with UUID {self.uuid}, technology {self.technology} in region {self.region}>"

    def __eq__(self, other):
        return self.uuid == other.uuid

    def __ne__(self, other):
        return self.uuid != other.uuid

    def get_age(self, year):
        return year - self.year_commissioned

    def get_annual_production_capacity(self):
        return self.annual_production_capacity

    def get_annual_production_volume(self):
        return self.get_annual_production_capacity() * self.cuf

    def get_lcox(self, df_cost: pd.DataFrame, year: int) -> float:
        """Get LCOX based on table with cost data for technology transitions and specified year

        Args:
            df_cost: contains columns "product", "technology_origin", "region", "year", "technology_destination", "lcox"
            year: year for which to get the asset lcox

        Returns:
            LCOX for the asset in the given year
        """
        return df_cost.query(
            f"product=='{self.product}' & technology_origin=='New-build' & year=={year} & region=='{self.region}' & technology_destination=='{self.technology}'"
        )["lcox"].iloc[0]


def create_assets(n_assets: int, **kwargs) -> list:
    """Convenience function to create a list of asset at once"""
    return [Asset(**kwargs) for _ in range(n_assets)]


class AssetStack:
    """Define an AssetStack composed of several Assets"""

    def __init__(self, assets: list):
        self.assets = assets
        # Keep track of all assets added this year
        self.new_ids = []

    def remove(self, remove_asset: Asset):
        """Remove asset from stack"""
        self.assets = [asset for asset in self.assets if asset != remove_asset]

    def append(self, new_asset: Asset):
        "Add new asset to stack"
        self.assets.append(new_asset)
        self.new_ids.append(new_asset.uuid)

    def empty(self) -> Boolean:
        """Return True if no asset in stack"""
        return not self.assets

    def filter_assets(self, product=None, region=None, technology=None) -> list:
        """Filter assets based on one or more criteria"""
        assets = self.assets
        if region is not None:
            assets = filter(lambda asset: asset.region == region, assets)
        if technology is not None:
            assets = filter(lambda asset: asset.technology == technology, assets)
        if product is not None:
            assets = filter(lambda asset: (asset.product == product), assets)

        return list(assets)

    def get_annual_production_capacity(
        self, product, region=None, technology=None
    ) -> float:
        """Get annual production capacity of the AssetStack for a specific product, optionally filtered by region and technology"""
        assets = self.filter_assets(
            product=product, region=region, technology=technology
        )
        return sum(asset.get_annual_production_capacity() for asset in assets)

    def get_annual_production_volume(
        self, product, region=None, technology=None
    ) -> float:
        """Get the yearly production volume of the AssetStack for a specific product, optionally filtered by region and technology"""

        assets = self.filter_assets(
            product=product, region=region, technology=technology
        )
        return sum(asset.get_annual_production_volume() for asset in assets)

    def get_products(self) -> list:
        """Get list of unique products produced by the AssetStack"""
        return list({asset.product for asset in self.assets})

    def aggregate_stack(self, aggregation_vars, product=None) -> pd.DataFrame:
        """
        Aggregate AssetStack according to product, technology or region, and show annual production capacity, annual production volume and number of assets. Optionally filtered by product

        Args:
            aggregation_vars: aggregate by these variables

        Returns:
            Dataframe with technologies
        """

        # Optional filter by product
        assets = self.filter_assets(product) if product else self.assets

        # Aggregate stack to DataFrame
        df = pd.DataFrame(
            [
                {
                    "product": asset.product,
                    "technology": asset.technology,
                    "region": asset.region,
                    "annual_production_capacity": asset.get_annual_production_capacity(),
                    "annual_production_volume": asset.get_annual_production_volume(),
                }
                for asset in assets
            ]
        )
        try:
            return df.groupby(aggregation_vars).agg(
                annual_production_capacity=("annual_production_capacity", "sum"),
                annual_production_volume=("annual_production_volume", "sum"),
                number_of_assets=("annual_production_capacity", "count"),
            )
        except KeyError:
            # There are no assets
            return pd.DataFrame()

    def export_stack_to_df(self) -> pd.DataFrame:
        """Format the entire AssetStack as a DataFrame (no aggregation)."""
        return pd.DataFrame(
            {
                "uuid": asset.uuid,
                "product": asset.product,
                "region": asset.region,
                "technology": asset.technology,
                "annual_production_capacity": asset.get_annual_production_capacity(),
                "annual_production_volume": asset.get_annual_production_volume(),
                "cuf": asset.cuf,
                "asset_lifetime": asset.asset_lifetime,
                "retrofit_status": asset.retrofit,
            }
            for asset in self.assets
        )

    def get_unique_tech_by_region(self, product=None) -> pd.DataFrame:
        """Get the unique technologies in the AssetStack for each region, optionally filtered by product"""
        if product is not None:
            assets = self.filter_assets(product=product)
        else:
            assets = self.assets

        valid_combos = {(asset.technology, asset.region) for asset in assets}
        return pd.DataFrame(valid_combos, columns=["technology", "region"])

    def get_regional_contribution_annual_production_volume(
        self, product
    ) -> pd.DataFrame:
        """Get the share of each region in the annual production volume for a specific product."""
        assets = self.filter_assets(product)
        df_agg = (
            pd.DataFrame(
                [
                    {
                        "region": asset.region,
                        "volume": asset.get_annual_production_volume(),
                    }
                    for asset in assets
                ]
            )
            .groupby("region", as_index=False)
            .sum()
        )
        df_agg["proportion"] = df_agg["volume"] / df_agg["volume"].sum()
        return df_agg

    def get_regional_production_volume(self, product):
        """Get annual production volume in each region for a specific product."""
        assets = self.filter_assets(product)
        return (
            pd.DataFrame(
                {
                    "region": asset.region,
                    "annual_production_volume": asset.get_annual_production_volume(),
                }
                for asset in assets
            )
            .groupby("region", as_index=False)
            .sum()
        )

    def get_tech_asset_stack(self, technology: str):
        """Get AssetStack with a specific technology."""
        return AssetStack(
            assets=[asset for asset in self.assets if asset.technology == technology]
        )

    def get_assets_eligible_for_decommission(self) -> list():
        """Return a list of Assets from the AssetStack that are eligible for decommissioning

        Returns:
            list of Assets
        """
        # Filter for CUF < threshold
        candidates = filter(lambda asset: asset.cuf < CUF_LOWER_THRESHOLD, self.assets)

        # TODO: filter based on asset age

        return list(candidates)


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
        cuf=first(spec["spec", "", "cuf"]),
        technology_classification=type_of_tech,
        df_asset_capacities=df_asset_capacities,
    )

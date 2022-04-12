"""Asset and asset stack classes, code adapted from MCC"""
from uuid import uuid4
from xmlrpc.client import Boolean

import pandas as pd

from mppshared.config import (ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
                              CUF_LOWER_THRESHOLD, CUF_UPPER_THRESHOLD,
                              DECOMMISSION_RATES, INVESTMENT_CYCLE, LOG_LEVEL)
from mppshared.utility.utils import first, get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


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
        technology_classification: str,
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
        self.technology_classification = technology_classification

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
        logger.debug(
            f"product=='{self.product}' & technology_origin=='New-build' & year=={year} & region=='{self.region}' & technology_destination=='{self.technology}'"
        )
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

    def update_asset(self, asset_to_update: Asset, new_technology: str):
        """Update an asset in AssetStack, unique ID remains the same"""
        asset_to_update.technology = new_technology

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

    def get_assets_eligible_for_decommission(self) -> list:
        """Return a list of Assets from the AssetStack that are eligible for decommissioning"""
        # Assets can be decommissioned if their CUF is lower than the threshold
        candidates = filter(lambda asset: asset.cuf < CUF_LOWER_THRESHOLD, self.assets)

        # TODO: filter based on asset age

        return list(candidates)

    def get_assets_eligible_for_brownfield(self, year) -> list:
        """Return a list of Assets from the AssetStack that are eligible for a brownfield technology transition"""

        # Assets can be renovated or rebuild if their CUF exceeds the threshold and they are older than the investment cycle
        # TODO: is there a distinction between brownfield renovation and brownfield rebuild?
        candidates = filter(
            lambda asset: (asset.cuf > CUF_LOWER_THRESHOLD)
            & (asset.get_age(year) >= INVESTMENT_CYCLE),
            self.assets,
        )

        return list(candidates)


def make_new_asset(
    asset_transition: dict, df_technology_characteristics: pd.DataFrame, year: int
):
    """Make a new asset, based on asset transition from the ranking DataFrame. The asset is assumed to start operating at the highest possible capacity utilisation

    Args:
        asset_transition: The best transition (destination is the asset to build)
        df_technology_characteristics: needed for asset lifetime and technology classification
        year: Build the asset in this year
        retrofit: Asset is retrofitted from an old asset

    Returns:
        The new asset
    """
    technology_characteristics = df_technology_characteristics.loc[
        (df_technology_characteristics["product"] == asset_transition["product"])
        & (df_technology_characteristics["region"] == asset_transition["region"])
        & (
            df_technology_characteristics["technology"]
            == asset_transition["technology_destination"]
        )
    ]

    return Asset(
        product=asset_transition["product"],
        technology=asset_transition["technology_destination"],
        region=asset_transition["region"],
        year_commissioned=year,
        annual_production_capacity=ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
        cuf=CUF_UPPER_THRESHOLD,
        asset_lifetime=technology_characteristics["technology_lifetime"],
        technology_classification=technology_characteristics[
            "technology_classification"
        ],
        retrofit=False,
    )

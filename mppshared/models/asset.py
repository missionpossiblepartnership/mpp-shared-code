"""Asset and asset stack classes, code adapted from MCC"""
import sys
from copy import deepcopy
from uuid import uuid4
from xmlrpc.client import Boolean

import pandas as pd

from mppshared.config import LOG_LEVEL
from mppshared.utility.dataframe_utility import get_emission_columns
from mppshared.utility.utils import get_logger, get_unique_list_values

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
        emission_scopes: list,
        cuf_lower_threshold: float,
        ghgs: list,
        retrofit=False,
        rebuild=False,
        greenfield=False,
        stay_same=False,
        ppa_allowed=True,
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
        self.cuf_lower_threshold = cuf_lower_threshold  # lower threshold for cuf

        # Emissions parameters
        self.emission_scopes = emission_scopes
        self.ghgs = ghgs

        # Asset status parameters
        self.retrofit = retrofit
        self.rebuild = rebuild
        self.greenfield = greenfield
        self.asset_lifetime = asset_lifetime  # unit: years
        self.technology_classification = technology_classification
        self.ppa_allowed = ppa_allowed
        self.stay_same = stay_same

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
        # logger.debug(
        #     f"product=='{self.product}' & technology_origin=='New-build' & year=={year} & region=='{self.region}' & technology_destination=='{self.technology}'"
        # )
        result = df_cost.query(
            f"product=='{self.product}' & technology_origin=='New-build' & year=={year} & region=='{self.region}' & technology_destination=='{self.technology}'"
        )["lcox"]
        return result.iloc[0]

    def get_mc(self, df_cost: pd.DataFrame, year: int) -> float:
        """Get MC (marginal cost of production for an asset in a specific year"""
        result = df_cost.query(
            f"product=='{self.product}' & technology_origin=='New-build' & year=={year} & region=='{self.region}' & technology_destination=='{self.technology}'"
        )["marginal_cost"]
        return result.iloc[0]


def create_assets(n_assets: int, **kwargs) -> list:
    """Convenience function to create a list of asset at once"""
    return [Asset(**kwargs) for _ in range(n_assets)]


class AssetStack:
    """Define an AssetStack composed of several Assets"""

    def __init__(
        self,
        assets: list,
        emission_scopes: list,
        ghgs: list,
        cuf_lower_threshold: float,
    ):
        self.assets = assets
        self.emission_scopes = emission_scopes
        self.ghgs = ghgs
        self.cuf_lower_threshold = cuf_lower_threshold
        # Keep track of all assets added this year
        self.new_ids: list[str] = []

    def __eq__(self, other):
        self_uuids = {asset.uuid for asset in self.assets}
        other_uuids = {asset.uuid for asset in other.assets}
        return self_uuids == other_uuids

    def remove(self, remove_asset: Asset):
        """Remove asset from stack"""
        self.assets = [asset for asset in self.assets if asset != remove_asset]

    def append(self, new_asset: Asset):
        "Add new asset to stack"
        self.assets.append(new_asset)
        self.new_ids.append(new_asset.uuid)

    def update_asset(
        self,
        year: int,
        asset_to_update: Asset,
        new_technology: str,
        new_classification: str,
        asset_lifetime: int,
        switch_type: str,
        origin_technology: str,
        update_year_commission: bool,
    ):
        """Update an asset's technology and technology classification in AssetStack (while retaining the same UUID).

        Args:
            asset_to_update ():
            year ():
            new_technology ():
            new_classification ():
            asset_lifetime ():
            switch_type ():
            origin_technology ():
            update_year_commission (): if True, the asset's year_commissioned will be updated to the current year
                (except for those cases where
                (new_technology == origin_technology) & (switch_type == brownfield_renovation))

        Returns:

        """

        # check to make sure that number of assets does not change
        len_pre = len(self.assets)

        uuid_update = asset_to_update.uuid
        asset_to_update.technology = new_technology
        asset_to_update.technology_classification = new_classification
        asset_to_update.asset_lifetime = asset_lifetime
        if origin_technology != new_technology:
            if switch_type == "brownfield_renovation":
                asset_to_update.retrofit = True
                asset_to_update.stay_same = False
            if (switch_type == "brownfield_rebuild") or (
                switch_type == "brownfield_newbuild"
            ):
                # todo: make it count in cement if it's the same tech!
                asset_to_update.rebuild = True
                asset_to_update.stay_same = False
        if origin_technology == new_technology:
            asset_to_update.stay_same = True
        if update_year_commission:
            if not (new_technology == origin_technology) & (
                switch_type == "brownfield_renovation"
            ):
                asset_to_update.year_commissioned = year

        self.assets = [asset for asset in self.assets if asset.uuid != uuid_update]
        self.assets.append(asset_to_update)

        # check to make sure that number of assets does not change
        assert len_pre == len(
            self.assets
        ), "Function update_asset has changed the number of assets in the stack!"

    def empty(self) -> Boolean:
        """Return True if no asset in stack"""
        return not self.assets

    def filter_assets(
        self,
        product=None,
        region=None,
        technology=None,
        technology_classification=None,
        status=None,
    ) -> list:
        """Filter assets based on one or more criteria"""
        assets = self.assets
        if region is not None:
            assets = list(filter(lambda asset: asset.region == region, assets))
        if technology is not None:
            assets = list(filter(lambda asset: asset.technology == technology, assets))
        if product is not None:
            assets = list(filter(lambda asset: (asset.product == product), assets))
        if technology_classification is not None:
            assets = list(
                filter(
                    lambda asset: (
                        asset.technology_classification == technology_classification
                    ),
                    assets,
                )
            )
        if status == "greenfield_status":
            assets = list(filter(lambda asset: asset.greenfield == True, assets))
        if status == "retrofit_status":
            assets = list(filter(lambda asset: asset.retrofit == True, assets))
        if status == "rebuild_status":
            assets = list(filter(lambda asset: asset.rebuild == True, assets))

        return assets

    def get_annual_production_capacity(
        self, product, region=None, technology=None
    ) -> float:
        """Get annual production capacity of the AssetStack for a specific product,
        optionally filtered by region and technology"""
        assets = self.filter_assets(
            product=product, region=region, technology=technology
        )
        return sum(asset.get_annual_production_capacity() for asset in assets)

    def get_annual_production_volume(
        self, product, region=None, technology=None
    ) -> float:
        """Get the yearly production volume of the AssetStack for a specific product,
        optionally filtered by region and technology"""

        assets = self.filter_assets(
            product=product, region=region, technology=technology
        )
        return sum(asset.get_annual_production_volume() for asset in assets)

    def log_annual_production_volume_by_region_and_tech(self, product: str):
        """Only in debug logger mode: logs production volumes per region and technology"""
        regions = get_unique_list_values(
            [x for x in [asset.region for asset in self.filter_assets(product=product)]]
        )

        for region in regions:
            technologies = get_unique_list_values(
                [
                    x
                    for x in [
                        asset.technology
                        for asset in self.filter_assets(product=product, region=region)
                    ]
                ]
            )
            for technology in technologies:
                prod_vol = self.get_annual_production_volume(
                    product=product, region=region, technology=technology
                )
                logger.debug(f"{region} | {technology}: {prod_vol} Mt {product}")

    def get_products(self) -> list:
        """Get list of unique products produced by the AssetStack"""
        return list({asset.product for asset in self.assets})

    def aggregate_stack(
        self,
        aggregation_vars: list,
        technology_classification: str = None,
        product: str = None,
    ) -> pd.DataFrame:
        """
        Aggregate AssetStack according to product, technology or region, and show annual production capacity, annual
            production volume and number of assets. Optionally filtered by technology classification and/or product

        Args:
            aggregation_vars: aggregate by these variables
            technology_classification:
            product:

        Returns:
            Dataframe with technologies
        """

        # Optional filter by technology classification and product
        assets = self.filter_assets(
            technology_classification=technology_classification, product=product
        )

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

    def calculate_emissions_stack(
        self,
        year: int,
        df_emissions: pd.DataFrame,
        technology_classification=None,
        product=None,
    ) -> dict:
        """Calculate emissions of the current stack in MtGHG by GHG and scope, optionally filtered for technology
        classification and/or a specific product"""

        # Sum emissions by GHG and scope
        emission_columns = get_emission_columns(
            ghgs=self.ghgs, scopes=self.emission_scopes
        )
        dict_emissions = dict.fromkeys(emission_columns)

        # Get DataFrame with annual production volume by product, region and technology (optionally filtered for
        #   technology classification and specific product)
        df_stack = self.aggregate_stack(
            aggregation_vars=["technology", "product", "region"],
            technology_classification=technology_classification,
            product=product,
        )

        # If the stack DataFrame is empty, return 0 for all emissions
        if df_stack.empty:
            for scope in dict_emissions.keys():
                dict_emissions[scope] = 0
            return dict_emissions

        df_stack = df_stack.reset_index()

        # Filter emissions DataFrame for the given year
        df_emissions = df_emissions.reset_index()
        df_emissions = df_emissions[(df_emissions.year == year)]

        # Add emissions by GHG and scope to each technologyy
        df_emissions_stack = df_stack.merge(
            df_emissions, how="left", on=["technology", "product", "region"]
        )

        for emission_item in emission_columns:
            dict_emissions[emission_item] = (
                df_emissions_stack[emission_item]
                * df_emissions_stack["annual_production_volume"]
            ).sum()

        return dict_emissions

    def calculate_co2_captured_stack(
        self,
        year: int,
        df_emissions: pd.DataFrame,
        technology_classification: str = None,
        product: str = None,
        region: str = None,
        usage_storage: str = None,
    ) -> float:
        """Calculate the CO2 captured by the stack in a given year.

        Args:
            year ():
            df_emissions ():
            technology_classification ():
            product ():
            region ():
            usage_storage (): if "usage" or "storage" provided, return only the captured sum of emissions from
                technologies with "usage" / "storage" in their name

        Returns:

        """

        # Get DataFrame with annual production volume by product, region and technology (optionally filtered for
        #   technology classification and specific product)
        df_stack = self.aggregate_stack(
            aggregation_vars=["technology", "product", "region"],
            technology_classification=technology_classification,
            product=product,
        )

        # If the stack DataFrame is empty, return 0 for all emissions
        if df_stack.empty:
            return float(0)

        df_stack = df_stack.reset_index()

        # Filter emissions DataFrame for the given year
        df_emissions = df_emissions.reset_index()
        df_emissions = df_emissions.loc[(df_emissions.year == year), :]

        # Add emissions by GHG and scope to each technology
        df_stack = df_stack.merge(
            df_emissions, how="left", on=["technology", "product", "region"]
        )

        # apply filters
        if region:
            df_stack = df_stack.loc[(df_stack.region == region), :]

        if usage_storage:
            df_stack = df_stack.loc[
                (df_stack["technology"].str.contains(usage_storage)), :
            ]

        co2_captured = (
            df_stack["co2_scope1_captured"] * df_stack["annual_production_volume"]
        ).sum()

        return co2_captured

    def export_stack_to_df(self) -> pd.DataFrame:
        """Format the entire AssetStack as a DataFrame (no aggregation)."""
        return pd.DataFrame(
            {
                "uuid": asset.uuid,
                "product": asset.product,
                "region": asset.region,
                "technology": asset.technology,
                "technology_classification": asset.technology_classification,
                "annual_production_capacity": asset.get_annual_production_capacity(),
                "annual_production_volume": asset.get_annual_production_volume(),
                "cuf": asset.cuf,
                "year_commissioned": asset.year_commissioned,
                "asset_lifetime": asset.asset_lifetime,
                "retrofit_status": asset.retrofit,
                "rebuild_status": asset.rebuild,
                "greenfield_status": asset.greenfield,
                "stay_same_status": asset.stay_same,
            }
            for asset in self.assets
        )

    def get_unique_tech_by_region(self, product=None) -> pd.DataFrame:
        """Get the unique technologies in the AssetStack for each region, optionally filtered by
        product"""
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
        df = pd.DataFrame(
            {
                "region": asset.region,
                "annual_production_volume": asset.get_annual_production_volume(),
            }
            for asset in assets
        )
        df["region"] = df["region"].replace(
            {
                "Brazil": "Latin America",
                "Namibia": "Africa",
                "Saudi Arabia": "Middle East",
                "Australia": "Oceania",
            }
        )
        df = df.groupby("region", as_index=False).sum()
        return df

    def get_number_of_assets(
        self, product=None, technology=None, region=None, status=None
    ):
        "Get number of assets in the asset stack"
        assets = self.filter_assets(
            product=product, technology=technology, region=region, status=status
        )
        return len(assets)

    def get_tech_asset_stack(self, technology: str):
        """Get AssetStack with a specific technology."""
        return AssetStack(
            assets=[asset for asset in self.assets if asset.technology == technology],
            emission_scopes=self.emission_scopes,
            ghgs=self.ghgs,
            cuf_lower_threshold=self.cuf_lower_threshold,
        )

    def get_assets_eligible_for_decommission(
        self,
        year: int,
        product: str,
        cuf_lower_threshold: float,
        minimum_decommission_age: float,
    ) -> list:
        """Return a list of Assets from the AssetStack that are eligible for decommissioning"""

        # Filter for assets with the specified product
        assets = self.filter_assets(product=product)

        # Assets can be decommissioned if their CUF is lower than or equal to the lower threshold
        candidates = filter(lambda asset: asset.cuf <= cuf_lower_threshold, assets)

        # Assets can be decommissioned if their age is at least as high as the minimum decommission age
        candidates = filter(
            lambda asset: asset.get_age(year) >= minimum_decommission_age, candidates
        )

        return list(candidates)

    def get_assets_eligible_for_decommission_cement(
        self,
        product: str,
        region: str,
        year: int,
    ) -> list:
        """Return a list of Assets from the AssetStack that are eligible for decommissioning in a region"""

        # Filter for assets with the specified product
        assets = deepcopy(self.filter_assets(product=product, region=region))

        # assets can be decommissioned if they have not undergone a renovation or rebuild
        candidates = list(filter(lambda asset: not asset.retrofit, assets))

        # if there are no assets left, those that are at the end of their lifetime can be decommissioned
        if len(candidates) == 0:
            candidates = list(
                filter(
                    lambda asset: (asset.get_age(year) >= asset.asset_lifetime), assets
                )
            )

            # if there are still no assets left, every asset in the region can be decommissioned
            if len(candidates) == 0:
                candidates = assets

        if len(candidates) == 0:
            logger.critical(f"{year}: No assets can be found in {region}")
        else:
            return candidates

    def get_assets_eligible_for_brownfield(
        self, year: int, investment_cycle: int
    ) -> list:
        """Return a list of Assets from the AssetStack that are eligible for a brownfield technology transition"""

        # Assets can be renovated at any time unless they've been renovated already
        candidates_renovation = filter(
            lambda asset: (not asset.retrofit),
            self.assets,
        )

        # Assets can be rebuild if their CUF exceeds the threshold and if they are older than the investment cycle
        candidates_rebuild = filter(
            lambda asset: (asset.cuf > self.cuf_lower_threshold)
            & (asset.get_age(year) >= investment_cycle),
            self.assets,
        )

        return list(candidates_renovation) + list(candidates_rebuild)

    def get_assets_eligible_for_brownfield_cement_renovation(self, year: int) -> list:
        """Return a list of Assets from the AssetStack that are eligible for a brownfield renovation transition in
        cement"""

        # all initial assets can switch
        candidates_renovation = filter(
            lambda asset: (asset.technology_classification == "initial"),
            self.assets,
        )

        # do not allow assets that have been newly built in the current year to undergo a brownfield transition
        candidates_renovation = filter(
            lambda asset: (asset.year_commissioned != year),
            candidates_renovation,
        )

        return deepcopy(list(candidates_renovation))

    def get_assets_eligible_for_brownfield_cement_rebuild(self, year: int) -> list:
        """Return a list of Assets from the AssetStack that are eligible for a brownfield rebuild transition in
        cement"""

        # all assets that reached the end of their lifetime can switch
        candidates_rebuild = filter(
            lambda asset: asset.get_age(year) >= asset.asset_lifetime,
            self.assets,
        )

        # do not allow assets that have been newly built in the current year to undergo a brownfield transition
        candidates_rebuild = filter(
            lambda asset: (asset.year_commissioned != year),
            candidates_rebuild,
        )

        return deepcopy(list(candidates_rebuild))


def make_new_asset(
    asset_transition: dict,
    df_technology_characteristics: pd.DataFrame,
    year: int,
    annual_production_capacity: float,
    cuf: float,
    emission_scopes: list,
    cuf_lower_threshold: float,
    ghgs: list,
):
    """Make a new asset, based on asset transition from the ranking DataFrame.

    Args:
        asset_transition: The best transition (destination is the asset to build)
        df_technology_characteristics: needed for asset lifetime and technology classification
        year: Build the asset in this year
        annual_production_capacity: The annual production capacity of the asset
        cuf: The capacity utilization factor of the asset
        emission_scopes:
        cuf_lower_threshold:
        ghgs:

    Returns:
        The new asset
    """
    # Filter row of technology characteristics DataFrame that corresponds to the asset transition
    technology_characteristics = df_technology_characteristics.loc[
        (df_technology_characteristics["product"] == asset_transition["product"])
        & (df_technology_characteristics["region"] == asset_transition["region"])
        & (
            df_technology_characteristics["technology"]
            == asset_transition["technology_destination"]
        )
        & (df_technology_characteristics["year"] == year)
    ]

    # Create the new asset with the corresponding technology characteristics and assumptions
    return Asset(
        product=asset_transition["product"],
        technology=asset_transition["technology_destination"],
        region=asset_transition["region"],
        year_commissioned=year,
        annual_production_capacity=annual_production_capacity,
        cuf=cuf,
        emission_scopes=emission_scopes,
        cuf_lower_threshold=cuf_lower_threshold,
        ghgs=ghgs,
        asset_lifetime=technology_characteristics["technology_lifetime"].values[0],
        technology_classification=technology_characteristics[
            "technology_classification"
        ].values[0],
        retrofit=False,
        rebuild=False,
    )


def make_new_asset_project_pipeline(
    region: str,
    product: str,
    annual_production_capacity_mt: float,
    technology: str,
    df_technology_characteristics: pd.DataFrame,
    year: int,
    cuf: float,
    emission_scopes: list,
    cuf_lower_threshold: float,
    ghgs: list,
) -> Asset:
    """Make new asset based on the current project pipeline.
    Args:
        region (str): _description_
        product (str): _description_
        annual_production_capacity_mt (float): _description_
        technology (str): _description_
        df_technology_characteristics (pd.DataFrame): _description_
        year (int): _description_
    Returns:
        The new Asset
    """
    # Filter row of technology characteristics DataFrame that corresponds to the asset transition
    technology_characteristics = df_technology_characteristics.loc[
        (df_technology_characteristics["product"] == product)
        & (df_technology_characteristics["region"] == region)
        & (df_technology_characteristics["technology"] == technology)
        & (df_technology_characteristics["year"] == year)
    ]

    return Asset(
        product=product,
        technology=technology,
        region=region,
        year_commissioned=year,
        annual_production_capacity=annual_production_capacity_mt,
        cuf=cuf,
        emission_scopes=emission_scopes,
        cuf_lower_threshold=cuf_lower_threshold,
        ghgs=ghgs,
        asset_lifetime=technology_characteristics["technology_lifetime"].values[0],
        technology_classification=technology_characteristics[
            "technology_classification"
        ].values[0],
        retrofit=False,
        rebuild=False,
        greenfield=True,
    )

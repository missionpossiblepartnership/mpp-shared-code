import logging
import math
import sys
from collections import defaultdict
from copy import deepcopy
from multiprocessing.sharedctypes import Value

import numpy as np
import pandas as pd
import plotly.express as px
from plotly.offline import plot
from plotly.subplots import make_subplots

from mppshared.config import LOG_LEVEL
from mppshared.import_data.intermediate_data import IntermediateDataImporter
# from mppshared.rank.rank_technologies import import_tech_data, rank_tech
from mppshared.models.asset import Asset, AssetStack, create_assets
from mppshared.models.carbon_budget import CarbonBudget
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory
from mppshared.models.technology_rampup import TechnologyRampup
from mppshared.models.transition import TransitionRegistry
from mppshared.utility.dataframe_utility import (flatten_columns,
                                                 get_emission_columns)
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


class SimulationPathway:
    """Define a pathway that simulates the evolution of the AssetStack in each year of the model time horizon"""

    def __init__(
        self,
        start_year: int,
        end_year: int,
        pathway: str,
        sensitivity: str,
        sector: str,
        products: list,
        rank_types: list,
        initial_asset_data_level: str,
        assumed_annual_production_capacity: float,
        technology_rampup: dict,
        carbon_budget: CarbonBudget,
        emission_scopes: list,
        cuf_lower_threshold: float,
        cuf_upper_threshold: float,
        ghgs: list,
        investment_cycle: int,
        annual_renovation_share: float,
        carbon_cost_trajectory: CarbonCostTrajectory = None,
    ):
        # Attributes describing the pathway
        self.start_year = start_year
        self.end_year = end_year
        self.pathway = pathway
        self.sensitivity = sensitivity
        self.sector = sector
        self.investment_cycle = investment_cycle
        self.products = products
        self.rank_types = rank_types
        self.initial_asset_data_level = initial_asset_data_level
        self.emission_scopes = emission_scopes
        self.cuf_lower_threshold = cuf_lower_threshold
        self.cuf_upper_threshold = cuf_upper_threshold
        self.annual_renovation_share = annual_renovation_share
        self.ghgs = ghgs

        # Carbon Budget (already initialized with emissions pathway)
        self.carbon_budget = carbon_budget

        # Technology ramp-up is a dictionary with the technologies as keys
        self.technology_rampup = technology_rampup

        # Use importer to get all data required for simulating the pathway
        self.importer = IntermediateDataImporter(
            pathway=pathway,
            sensitivity=sensitivity,
            sector=sector,
            products=products,
            carbon_cost_trajectory=carbon_cost_trajectory,
        )
        self.carbon_cost_trajectory = carbon_cost_trajectory

        self.assumed_annual_production_capacity = assumed_annual_production_capacity

        # Make initial asset stack from input data
        logger.debug("Making asset stack")
        if self.initial_asset_data_level == "regional":
            self.stacks = self.make_initial_asset_stack_from_regional_data()
        elif self.initial_asset_data_level == "individual_assets":
            self.stacks = self.make_initial_asset_stack_from_asset_data()

        # Import demand for all regions
        logger.debug("Getting demand")
        self.demand = self.importer.get_demand(region=None)

        # Import ranking of technology transitions for all transition types
        logger.debug("Getting rankings")
        self.rankings = self._import_rankings()

        # Import emissions data
        logger.debug("Getting emissions")
        self.emissions = self.importer.get_process_data(data_type="emissions")

        # Import technology characteristics
        logger.debug("Getting technology characteristics")
        self.df_technology_characteristics = (
            self.importer.get_technology_characteristics()
        )

        self.df_cost = self.importer.get_technology_transitions_and_cost()

        # TODO: Availability missing, if it is available we should import
        # logger.debug("Getting availability")
        # self.availability = self._import_availability()

        logger.debug("Getting process data")
        # self.process_data = self.importer.get_all_process_data()
        logger.debug("Getting all transitions and cost")
        self.df_cost = self.importer.get_technology_transitions_and_cost()
        # TODO: Raw material data is missing and should be called inputs to import it
        # self.inputs_pivot = self.importer.get_process_data(data_type="inputs")
        logger.debug("Getting the asset specs")
        # self.asset_specs = self.importer.get_asset_specs()

        # Initialize TransitionRegistry to track technology transitions
        logger.debug("Getting the transition registry to track technology transitions")
        self.transitions = TransitionRegistry()

    def _import_rankings(self):
        """Import ranking for all products and rank types from the CSVs"""
        rankings = defaultdict(dict)
        for rank_type in self.rank_types:
            df_rank = self.importer.get_ranking(rank_type=rank_type)

            rankings[rank_type] = {}
            for year in range(self.start_year, self.end_year + 1):
                rankings[rank_type][year] = df_rank.query(f"year == {year}")
        return rankings

    def save_rankings(self):
        for product in self.products:
            for rank_type in self.rank_types:
                df = pd.concat(
                    [
                        pd.concat([df_ranking])
                        for year, df_ranking in self.rankings[product][
                            rank_type
                        ].items()
                    ]
                )
                self.importer.export_data(
                    df=df,
                    filename=f"{product}_post_rank.csv",
                    export_dir=f"ranking/{product}",
                )

    def save_demand(self):
        df = self.demand
        df = df[df.year <= self.end_year]
        df = df.pivot(index="product", columns="year", values="demand")
        self.importer.export_data(
            df=df,
            filename="demand_output.csv",
            export_dir="final/All",
        )

    def save_availability(self):
        df = self.availability
        self.importer.export_data(
            df=df,
            filename="availability_output.csv",
            export_dir="final/All",
        )

    def export_stack_to_csv(self, year):
        df = self.get_stack(year).export_stack_to_df()
        self.importer.export_data(df, f"stack_{year}.csv", "stack_tracker", index=False)

    def output_technology_roadmap(self):
        logger.debug("Creatting technology roadmap")
        df_roadmap = self.create_technology_roadmap()
        logger.debug("Exporting technology roadmap")
        self.importer.export_data(df_roadmap, "technology_roadmap.csv", "final")
        self.plot_technology_roadmap(df_roadmap=df_roadmap)

    def create_technology_roadmap(self) -> pd.DataFrame:
        """Create technology roadmap that shows evolution of stack (supply mix) over model horizon."""

        # TODO: filter by product
        # Annual production volume in MtNH3 by technology
        technologies = self.importer.get_technology_characteristics()[
            "technology"
        ].unique()
        df_roadmap = pd.DataFrame(data={"technology": technologies})
        logger.debug("Calculating annual production volume")

        for year in np.arange(self.start_year, self.end_year + 1):

            # Group by technology and sum annual production volume
            df_stack = self.importer.get_asset_stack(year=year)
            df_sum = df_stack.groupby(["technology"], as_index=False).sum()
            df_sum = df_sum[["technology", "annual_production_volume"]].rename(
                {"annual_production_volume": year}, axis=1
            )

            # Merge with roadmap DataFrame
            df_roadmap = df_roadmap.merge(df_sum, on=["technology"], how="left").fillna(
                0
            )

        return df_roadmap

    def plot_technology_roadmap(self, df_roadmap: pd.DataFrame):
        """Plot the technology roadmap and save as .html"""

        # Melt roadmap DataFrame for easy plotting
        logger.debug("Melting roadmap DataFrame")
        df_roadmap = df_roadmap.melt(
            id_vars="technology", var_name="year", value_name="annual_volume"
        )
        logger.debug("Plotting technology roadmap")
        fig = make_subplots()
        wedge_fig = px.area(df_roadmap, color="technology", x="year", y="annual_volume")

        fig.add_traces(wedge_fig.data)

        fig.layout.xaxis.title = "Year"
        fig.layout.yaxis.title = "Annual production volume (MtNH3/year)"
        fig.layout.title = "Technology roadmap"
        logger.debug("Exporting technology roadmap HTML")

        plot(
            fig,
            filename=str(self.importer.final_path.joinpath("technology_roadmap.html")),
            auto_open=False,
        )
        logger.debug("Exporting technology roadmap PNG")
        fig.write_image(self.importer.final_path.joinpath("technology_roadmap.png"))

    def output_emission_trajectory(self):
        """Output emission trajectory as csv and figure"""
        pass

    def create_emission_trajectory(self) -> pd.DataFrame:
        pass

    def plot_emission_trajectory(self, df_emissions: pd.DataFrame) -> pd.DataFrame:
        pass

    def get_emissions(self, year, product=None):
        """Get  the emissions for a product in a year"""
        df = self.emissions.copy()

        return df.query(f"product == '{product}' & year == {year}").droplevel(
            ["product", "year"]
        )

    def get_asset_lcox(self, asset: Asset, year: int) -> float:
        """Get LCOX for a specific Asset if the Asset is in the AssetStack of the given year."""
        if asset not in self.get_stack(year).assets:
            raise ValueError(
                f"Asset with UUID {asset.uuid} is not in this year's AssetStack."
            )
        return self.df_cost.query(
            f"product=='{asset.product}' & technology_origin=='New-build' & year=={year} & region=='{asset.region}' & technology_destination=='{asset.technology}'"
        )["lcox"].iloc[0]

    def get_cost(self, product, year):
        """Get  the cost for a product in a year"""
        df = self.df_cost
        return df.query(f"product == '{product}' & year == {year}").droplevel(
            ["product", "year"]
        )

    def get_inputs_pivot(self, product, year):
        """Get  the cost for a product in a year"""
        df = self.inputs_pivot
        return df.query(f"product == '{product}' & year == {year}").droplevel(
            ["product", "year"]
        )

    def get_specs(self, product, year):
        df = self.asset_specs
        return df.query(f"product == '{product}' & year == {year}").droplevel(
            ["product", "year"]
        )

    def get_demand(
        self,
        product: str,
        year: int,
        region: str,
    ):
        """
        Get the demand for a product in a given year and region

        Args:
            product: get for this product
            region: get for this region
            year: and this year
        Returns:

        """
        df = self.demand
        return df.loc[
            (df["product"] == product)
            & (df["year"] == year)
            & (df["region"] == region),
            "value",
        ].item()

    def get_regional_demand(self, product: str, year: int):
        df = self.demand
        return pd.DataFrame(
            {"region": region, "demand": self.get_demand(product, year, region)}
            for region in df["region"].unique()
        )

    def get_inputs(self, year, product=None):
        """Get the inputs for a product in a year"""
        df = self.inputs

        if product is not None:
            df = df[df.product == product]
        return df[df.year == year]

    def get_all_process_data(self, product, year):
        """Get all process data for a product in a year"""
        df = self.process_data
        df = df.reset_index(level=["product", "year"])
        return df[(df[("product", "")] == product) & (df[("year", "")] == year)]

    def get_ranking(self, year, rank_type):
        """Get ranking df for a specific year/product"""
        if rank_type not in self.rank_types:
            raise ValueError(
                "Rank type %s not recognized, choose one of %s",
                rank_type,
                self.rank_types,
            )

        return self.rankings[rank_type][year]

    def update_ranking(self, df_rank, product, year, rank_type):
        """Update ranking for a product, year, type"""
        self.rankings[product][rank_type][year] = df_rank

    def copy_availability(self, year):
        df = self.availability

        for product in self.products:
            df.loc[df.year == year + 1, f"{product}_used"] = list(
                df.loc[df.year == year, f"{product}_used"]
            )

        df.loc[df.year == year + 1, "used"] = list(df.loc[df.year == year, "used"])
        df.loc[
            (df.year == year + 1) & (df.name.str.contains("Methanol")), "cap"
        ] = list(
            df.loc[(df.year == year + 1) & (df.name.str.contains("Methanol")), "cap"]
        )

    def update_availability(self, asset, year, remove=False):
        """
        Update the amount used of resources

        Args:
            year: current year
            remove:
            asset: update based on this asset
        """
        df = self.availability
        df = None
        self.availability = df.round(1)
        return self

    def get_availability(self, year=None, name=None):
        df = self.availability.drop(columns=["unit"])

        if year is not None:
            df = df[df.year == year]

        if name is not None:
            df = df[df.name == name]

        return df

    def get_stack(self, year: int) -> AssetStack:
        return self.stacks[year]

    def update_stack(self, year, stack):
        self.stacks[year] = stack
        return self

    def copy_stack(self, year):
        """Copy this year's stack to next year"""
        old_stack = self.get_stack(year=year)
        new_stack = AssetStack(
            assets=deepcopy(old_stack.assets),
            emission_scopes=deepcopy(old_stack.emission_scopes),
            ghgs=deepcopy(old_stack.ghgs),
            cuf_lower_threshold=deepcopy(old_stack.cuf_lower_threshold),
        )
        return self.add_stack(year=year + 1, stack=new_stack)

    def add_stack(self, year, stack):
        if year in self.stacks.keys():
            raise ValueError(
                "Cannot add stack, already present. Please use the update method"
            )

        self.stacks[year] = stack
        return self

    def get_capacity(self, year):
        """Get the capacity for a year"""
        stack = self.get_stack(year=year)
        return stack.get_annual_production_capacity()

    def aggregate_stacks(self, product, this_year=False):
        return pd.concat(
            [
                stack.aggregate_stack(year=year, this_year=this_year, product=product)
                for year, stack in self.stacks.items()
            ]
        )

    def make_initial_asset_stack_from_regional_data(self):
        """Make AssetStack from input data organised by region on total production volume and capacity, average capacity utilisation factor and average age in the initial year."""
        df_stack = self.importer.get_initial_asset_stack()

        # Get the number assets required
        # TODO: based on distribution of typical production capacities
        # TODO: create smaller asset to meet production capacity precisely
        df_stack["number_assets"] = (
            df_stack["annual_production_capacity"]
            / self.assumed_annual_production_capacity
        ).apply(lambda x: int(x))

        # Merge with technology specifications to get technology lifetime
        df_tech_characteristics = self.importer.get_technology_characteristics()
        df_stack = df_stack.merge(
            df_tech_characteristics[
                [
                    "product",
                    "region",
                    "technology",
                    "year",
                    "technology_classification",
                    "technology_lifetime",
                ]
            ],
            on=["product", "region", "year", "technology"],
            how="left",
        )

        # Create list of assets for every product, region and technology (corresponds to one row in the DataFrame)
        # TODO: based on distribution of CUF and commissioning year
        assets = df_stack.apply(
            lambda row: create_assets(
                n_assets=row["number_assets"],
                product=row["product"],
                technology=row["technology"],
                region=row["region"],
                year_commissioned=row["year"] - row["average_age"],
                annual_production_capacity=self.assumed_annual_production_capacity,
                cuf=row["average_cuf"],
                asset_lifetime=row["technology_lifetime"],
                technology_classification=row["technology_classification"],
                emission_scopes=self.emission_scopes,
                cuf_lower_threshold=self.cuf_lower_threshold,
                ghgs=self.ghgs,
            ),
            axis=1,
        ).tolist()
        assets = [item for sublist in assets for item in sublist]

        # Create AssetStack for model start year
        return {
            self.start_year: AssetStack(
                assets=assets,
                emission_scopes=self.emission_scopes,
                ghgs=self.ghgs,
                cuf_lower_threshold=self.cuf_lower_threshold,
            )
        }

    def make_initial_asset_stack_from_asset_data(self):
        """Make AssetStack from asset-specific data (as opposed to average regional data)."""
        logger.info("Creating initial asset stack from asset data")
        df_stack = self.importer.get_initial_asset_stack()
        df_stack["number_assets"] = 1
        df_tech_characteristics = self.importer.get_technology_characteristics()
        df_tech_characteristics.rename(
            columns={"technology_destination": "technology"}, inplace=True
        )
        df_stack.rename(columns={"year": "year_commissioned"}, inplace=True)
        df_stack["year"] = self.start_year
        df_stack = df_stack.merge(
            df_tech_characteristics[
                [
                    "year",
                    "product",
                    "region",
                    "technology",
                    "technology_classification",
                    "technology_lifetime",
                ]
            ],
            on=["product", "year", "region", "technology"],
            how="left",
        )
        assets = df_stack.apply(
            lambda row: create_assets(
                n_assets=row["number_assets"],
                product=row["product"],
                technology=row["technology"],
                region=row["region"],
                year_commissioned=row["year_commissioned"],
                annual_production_capacity=row["annual_production_capacity"],
                cuf=row["capacity_factor"],
                asset_lifetime=row["technology_lifetime"],
                technology_classification=row["technology_classification"],
                ppa_allowed=row["ppa_allowed"],
                emission_scopes=self.emission_scopes,
                cuf_lower_threshold=self.cuf_lower_threshold,
                ghgs=self.ghgs,
            ),
            axis=1,
        ).tolist()
        assets = [item for sublist in assets for item in sublist]
        logger.info(f"Created {len(assets)} initial assets")

        # Create AssetStack for model start year
        return {
            self.start_year: AssetStack(
                assets=assets,
                emission_scopes=self.emission_scopes,
                ghgs=self.ghgs,
                cuf_lower_threshold=self.cuf_lower_threshold,
            )
        }

    def _get_weighted_average(
        self, df, vars, product, year, methanol_type: str = None, emissions=True
    ):
        """Calculate the weighted average of variables over regions/technologies"""
        df_assets = flatten_columns(self.stacks[year].aggregate_stack(product=product))

        df = pd.merge(
            df_assets.reset_index(),
            df.reset_index(),
            on=["technology", "region"],
        )

        return (
            (
                df[vars].multiply(df["capacity_total"], axis="index").sum()
                / df["capacity_total"].sum()
            ).to_dict()
            if emissions
            else (
                df[vars].multiply(df["capacity_total"], axis="index").sum()
                / df["capacity_total"].sum()
            ).mean()
        )

    def get_average_emissions(
        self, product: str, year: int, methanol_type: str = None
    ) -> int:
        """
        Calculate emissions of a product, based on the assets that produce it in a year

        Returns:
            Emissions of producing the product in this year (averaged over technologies and locations)
        """
        df_emissions = self.get_emissions(product=product, year=year)

        return self._get_weighted_average(
            df=df_emissions,
            vars=["scope_1", "scope_2", "scope_3_upstream", "scope_3_downstream"],
            year=year,
            product=product,
            methanol_type=methanol_type,
            emissions=True,
        )

    def get_average_levelized_cost(
        self, product: str, year: int, methanol_type: str = None
    ) -> int:
        """
        Calculate levelized cost of a product, based on the assets that produce it in a year

        Returns:
            Levelized cost of producing the product in this year (averaged over technologies and locations)
        """

        df_lcox = self.get_cost(product=product, year=year)["lcox"]
        return self._get_weighted_average(
            df_lcox,
            vars=["new_build_brownfield"],
            year=year,
            product=product,
            methanol_type=methanol_type,
            emissions=False,
        )

    def get_total_volume(self, product: str, year: int, methanol_type=None):
        """Get total volume produced of a product in a year"""
        df_assets = flatten_columns(self.stacks[year].aggregate_stack(product=product))

        # Return total capacity in Mton/annum
        return df_assets["capacity_total"].sum()

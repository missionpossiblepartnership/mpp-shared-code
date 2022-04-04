from pathlib import Path

import pandas as pd
from pandas.errors import ParserError

# from util.util import make_multi_df
from mppshared.config import ASSUMED_ANNUAL_PRODUCTION_CAPACITY, MODEL_SCOPE, PRODUCTS
from mppshared.utility.dataframe_utility import make_multi_df


class IntermediateDataImporter:
    """Imports data that is output by the model at some point in time"""

    def __init__(
        self,
        pathway: str,
        sensitivity: str,
        sector: str,
        products: list,
    ):
        parent_path = Path(__file__).resolve().parents[2]
        self.input_path = parent_path.joinpath(
            "data/Master template - python copy.xlsx"
        )
        self.sector = sector
        self.products = products
        self.pathway = pathway
        self.sensitivity = sensitivity
        self.export_dir = parent_path.joinpath(f"data/{sector}/{pathway}/{sensitivity}")
        self.intermediate_path = self.export_dir.joinpath("intermediate")
        self.final_path = self.export_dir.joinpath("final")
        self.aggregate_export_dir = parent_path.joinpath("output/")

    def export_data(
        self,
        df: pd.DataFrame,
        filename: str,
        export_dir: str,
        index=True,
        aggregate=False,
    ):
        """
        Export output data into the output directory

        Args:
            aggregate:
            df: Data to export
            filename: Filename to export to
            export_dir: Additional directory to create
            index: index is exported if True (default)
        """
        output_dir = self.aggregate_export_dir if aggregate else self.export_dir
        if export_dir is not None:
            output_dir = output_dir.joinpath(export_dir)
        else:
            output_dir = output_dir

        # Make export directory if it doesn't exist yet
        output_dir.mkdir(exist_ok=True, parents=True)

        export_path = output_dir.joinpath(filename)

        df.to_csv(export_path, index=index)

    def get_availabilities(self):
        return pd.read_csv(self.intermediate_path.joinpath("availabilities.csv"))

    def get_emissions(self):
        return pd.read_csv(self.intermediate_path.joinpath("emissions.csv"))

    def get_current_production(self):
        return pd.read_csv(self.intermediate_path.joinpath("initial_state.csv"))

    def get_initial_asset_stack(self):
        return pd.read_csv(self.intermediate_path.joinpath("initial_asset_stack.csv"))

    def get_technology_characteristics(self):
        return pd.read_csv(
            self.intermediate_path.joinpath("technology_characteristics.csv")
        )

    def get_asset_specs(self):
        df_spec = pd.read_csv(
            self.intermediate_path.joinpath("technology_characteristics.csv"),
            index_col=["product", "technology", "region"],
        )
        df_spec.annual_production_capacity = (
            ASSUMED_ANNUAL_PRODUCTION_CAPACITY * 365 / 1e6
        )
        df_spec["yearly_volume"] = (
            df_spec.annual_production_capacity * df_spec.capacity_factor
        )
        df_spec["total_volume"] = df_spec.technology_lifetime * df_spec.yearly_volume
        return df_spec

    def get_asset_sizes(self):
        """Get asset sizes for each different product/process"""
        df_spec = self.get_asset_specs()
        return df_spec.reset_index()[
            [
                "product",
                "technology",
                "annual_production_capacity",
                "cuf",
                "yearly_volume",
                "total_volume",
            ]
        ].drop_duplicates(["product", "technology"])

    def get_asset_capacities(self):
        df_spec = self.get_asset_specs().reset_index()
        df_spec.annual_production_capacity = ASSUMED_ANNUAL_PRODUCTION_CAPACITY
        df_spec["yearly_volume"] = df_spec.annual_production_capacity * df_spec.cuf
        df_spec["total_volume"] = df_spec.technology_lifetime * df_spec.yearly_volume
        return df_spec.drop_duplicates(["product", "region", "technology"])[
            [
                "product",
                "technology",
                "region",
                "annual_production_capacity",
                "yearly_volume",
                "total_volume",
            ]
        ]

    def get_demand(self, region=None):
        df = pd.read_csv(self.intermediate_path.joinpath("demand.csv"))

        if not region:
            return df
        return df.loc[df["region"] == region]

    def get_technology_transitions_and_cost(self):
        return pd.read_csv(
            self.intermediate_path.joinpath("technology_transitions.csv")
        )

    def get_process_data(self, data_type):
        """Get data outputted by the model on process level: cost/inputs/emissions"""
        file_path = self.intermediate_path.joinpath(f"{data_type}.csv")

        # Read multi-index
        header = [0, 1] if data_type in ["cost", "inputs_pivot"] else 0

        # Costs
        index_cols = (
            ["product", "technology_destination", "year", "region"]
            if data_type == "technology_transitions"
            else ["product", "technology", "year", "region"]
        )

        return pd.read_csv(file_path, header=header, index_col=index_cols)

    def get_all_process_data(self, product=None):
        """Get combined data outputted by the model on process level"""
        # df_inputs_pivot = self.get_process_data("inputs_pivot")
        df_emissions = self.get_process_data("emissions")
        df_cost = self.get_process_data("technology_transitions")
        df_spec = self.get_asset_specs()

        # Add multi index layers to join
        # 2 levels for emissions/spec to get it on the right level
        df_emissions = make_multi_df(df=df_emissions, name="emissions")
        df_spec = make_multi_df(df=df_spec, name="spec")
        df_cost = make_multi_df(df=df_cost, name="cost")
        df_cost.index.names = ["product", "technology", "year", "region"]
        # df_inputs_pivot = make_multi_df(df=df_inputs_pivot, name="inputs")

        df_all = df_spec.join(df_emissions).join(df_cost)
        # df_all.columns.names = ["group", "category", "name"]

        if product is not None:
            df_all = df_all.query(f"product == '{product}'").droplevel("product")
        return df_all.query("year <= 2050")

    def get_technologies_to_rank(self):
        """Return the list of technologies to rank with the TCO and emission deltas."""
        file_path = self.intermediate_path.joinpath("technologies_to_rank.csv")
        return pd.read_csv(file_path)

    def get_variable_per_year(self, product, variable):
        file_path = self.export_dir.joinpath(
            "final", product, f"{variable}_per_year.csv"
        )
        index_col = 0 if variable == "outputs" else [0, 1]
        return pd.read_csv(file_path, header=[0, 1], index_col=index_col)

    def get_ranking(self, rank_type, product):
        file_path = self.export_dir.joinpath(
            "ranking", product, f"{rank_type}_rank.csv"
        )
        return pd.read_csv(file_path)

    # def get_technology_distribution(self, product, new=False):
    #     suffix = "_new" if new else ""
    #     file_path = self.export_dir.joinpath(
    #         "final", product, f"technologies_over_time_region{suffix}.csv"
    #     )
    #     try:
    #         df = pd.read_csv(file_path, index_col=[0, 1, 2], header=[0, 1]).fillna(0)
    #     except ParserError:
    #         # No assets, return empty df with right columns and index
    #         parameters = ["capacity", "number_of_assets", "yearly_volume"]
    #         build_types = ["new_build", "retrofit", "total"]
    #         columns = pd.MultiIndex.from_product([parameters, build_types])
    #         index = pd.MultiIndex.from_arrays(
    #             [[], [], []], names=("region", "technology", "year")
    #         )
    #         return pd.DataFrame(columns=columns, index=index)
    #
    #     # Only keep rows which have assets
    #     return df[df[("number_of_assets", "total")] != 0]

    # def get_availability_used(self):
    #     path = self.final_path.joinpath("All", "availability_output.csv")
    #     return pd.read_csv(path)

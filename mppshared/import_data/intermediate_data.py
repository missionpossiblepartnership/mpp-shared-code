import sys
from pathlib import Path

import pandas as pd

from mppshared.config import ASSUMED_ANNUAL_PRODUCTION_CAPACITY, LOG_LEVEL
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


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
        self.export_dir = parent_path.joinpath(f"{sector}/data/{pathway}/{sensitivity}")
        self.intermediate_path = self.export_dir.joinpath("intermediate")
        self.stack_tracker_path = self.export_dir.joinpath("stack_tracker")
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

    def get_emissions(self):
        return pd.read_csv(self.intermediate_path.joinpath("emissions.csv"))

    def get_current_production(self):
        return pd.read_csv(self.intermediate_path.joinpath("initial_state.csv"))

    def get_initial_asset_stack(self):
        return pd.read_csv(self.intermediate_path.joinpath("initial_asset_stack.csv"))

    def get_carbon_budget(self):
        return pd.read_csv(self.intermediate_path.joinpath("carbon_budget.csv"))

    def get_technology_characteristics(self):
        return pd.read_csv(
            self.intermediate_path.joinpath("technology_characteristics.csv")
        )

    def get_electrolyser_cfs(self):
        return pd.read_csv(self.intermediate_path.joinpath("electrolyser_cfs.csv"))

    def get_electrolyser_efficiencies(self):
        return pd.read_csv(
            self.intermediate_path.joinpath("electrolyser_efficiencies.csv")
        )

    def get_electrolyser_proportions(self):
        return pd.read_csv(
            self.intermediate_path.joinpath("electrolyser_proportions.csv")
        )

    # TODO: remove this legacy function
    def get_asset_specs(self):
        df_spec = pd.read_csv(
            self.intermediate_path.joinpath("technology_characteristics.csv"),
            index_col=["product", "technology_destination", "region"],
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

    def get_asset_stack(self, year):
        return pd.read_csv(self.stack_tracker_path.joinpath(f"stack_{year}.csv"))

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

    def get_technologies_to_rank(self):
        """Return the list of technologies to rank with the TCO and emission deltas."""
        file_path = self.intermediate_path.joinpath("technologies_to_rank.csv")
        return pd.read_csv(file_path)

    def get_ranking(self, rank_type):
        file_path = self.export_dir.joinpath("ranking", f"{rank_type}_rank.csv")
        return pd.read_csv(file_path)

    def get_inputs_outputs(self):
        return pd.read_csv(
            self.intermediate_path.joinpath("inputs_outputs.csv"),
        )

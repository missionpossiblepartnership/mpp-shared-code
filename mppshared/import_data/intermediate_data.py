import shutil
from pathlib import Path

import pandas as pd

from mppshared.config import END_YEAR, LOG_LEVEL
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


class IntermediateDataImporter:
    """Imports data that is output by the model at some point in time"""

    def __init__(
        self,
        pathway_name: str,
        sensitivity: str,
        sector: str,
        products: list,
        carbon_cost_trajectory=None,
    ):
        parent_path = Path(__file__).resolve().parents[2]
        self.sector = sector
        self.products = products
        self.pathway_name = pathway_name
        self.sensitivity = sensitivity

        # Export directory depends on whether a CarbonCostTrajectory is passed or not
        if carbon_cost_trajectory:
            final_carbon_cost = carbon_cost_trajectory.df_carbon_cost.loc[
                carbon_cost_trajectory.df_carbon_cost["year"] == END_YEAR, "carbon_cost"
            ].item()
            self.export_dir = parent_path.joinpath(
                f"{sector}/data/{pathway_name}/{sensitivity}/carbon_cost_{final_carbon_cost}"
            )
        else:
            self.export_dir = parent_path.joinpath(
                f"{sector}/data/{pathway_name}/{sensitivity}"
            )
        self.raw_path = parent_path.joinpath(f"{sector}/data/01_business_case_raw")
        self.import_path = self.export_dir.joinpath("import")
        self.intermediate_path = self.export_dir.joinpath("intermediate")
        self.stack_tracker_path = self.export_dir.joinpath("stack_tracker")
        self.final_path = self.export_dir.joinpath("final")
        self.aggregate_export_dir = parent_path.joinpath("output/")

    def export_data(
        self,
        df: pd.DataFrame,
        filename: str,
        export_dir: str,
        index: bool = True,
        aggregate: bool = False,
    ):
        """
        Export output data into the output directory

        Args:
            df: Data to export
            filename: Filename to export to
            export_dir: Additional directory to create
            index: index is exported if True (default)
            aggregate:
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

    def export_sector_config(self):
        # Make export directory if it doesn't exist yet
        self.final_path.mkdir(exist_ok=True, parents=True)

        # export config script
        shutil.copyfile(
            src=f"{Path(__file__).resolve().parents[2]}/{self.sector}/config/config_{self.sector}.py",
            dst=f"{self.final_path}/run_config.py",
        )

    # imports & preprocessing
    def get_raw_input_data(
        self,
        sheet_name: str,
        header_business_case_excel: int,
        excel_column_ranges: dict,
    ):
        """Return specified sheet of Business Cases_{sensitivity}.xlsx as DataFrame.

        Args:
            sheet_name (str): Name of the sheet in Business Cases.xlsx
            header_business_case_excel ():
            excel_column_ranges ():

        Returns:
            pd.DataFrame: Full data of sheet with correct header
        """

        filename = f"Business Cases_{self.sensitivity}.xlsx"
        full_path = self.raw_path.joinpath(filename)
        df = pd.read_excel(
            full_path,
            sheet_name=sheet_name,
            header=header_business_case_excel,
            usecols=excel_column_ranges[sheet_name],
        )

        return df

    def get_imported_input_data(
        self,
        input_metrics: dict,
        index: bool = False,
        idx_per_input_metric: dict = None,
    ):
        """imports all files that are declared as metrics in INPUT_METRICS"""
        imported_input_data = {}
        for input_sheet in input_metrics.keys():
            for metric in input_metrics[input_sheet]:
                imported_input_data[metric] = pd.read_csv(
                    self.import_path.joinpath(f"{metric}.csv")
                )
                if index:
                    assert idx_per_input_metric is not None, "No index passed"
                    imported_input_data[metric].set_index(
                        keys=idx_per_input_metric[metric], inplace=True
                    )
        return imported_input_data

    # intermediate
    def get_lcox(self):
        return pd.read_csv(self.intermediate_path.joinpath("lcox.csv"))

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

    def get_carbon_cost_addition(self):
        return pd.read_csv(self.intermediate_path.joinpath("carbon_cost_addition.csv"))

    def get_co2_storage_constraint(self):
        return pd.read_csv(
            self.intermediate_path.joinpath("co2_storage_constraint.csv")
        )

    def get_natural_gas_constraint(self):
        """
        Returns: natural_gas_constraint (Unit: Mt production_output)
        """

        return pd.read_csv(
            self.intermediate_path.joinpath("natural_gas_constraint.csv")
        )

    def get_alternative_fuel_constraint(self):
        """
        Returns: alternative_fuel_constraint (Unit: Mt production_output)
        """

        return pd.read_csv(
            self.intermediate_path.joinpath("alternative_fuel_constraint.csv")
        )

    def get_electrolysis_capacity_addition_constraint(self):
        return pd.read_csv(
            self.intermediate_path.joinpath(
                "electrolysis_capacity_addition_constraint.csv"
            )
        )

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

    def get_demand_drivers(self):
        file_path = self.intermediate_path.joinpath("demand_by_driver.csv")
        return pd.read_csv(file_path).dropna(axis=0, how="all")

    def get_emission_factors(self, ghg: str):
        file_path = self.intermediate_path.joinpath(f"emission_factors_{ghg}.csv")
        return pd.read_csv(file_path)

    def get_project_pipeline(self):
        file_path = self.intermediate_path.joinpath("project_pipeline.csv")
        return pd.read_csv(file_path)

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

    def get_start_technologies(self):
        return pd.read_csv(
            self.intermediate_path.joinpath("start_technologies.csv"),
        )

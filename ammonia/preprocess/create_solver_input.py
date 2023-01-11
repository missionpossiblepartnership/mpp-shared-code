"""Create and copy over the input files for the solver."""
import os
from functools import reduce

import pandas as pd
from ammonia.config_ammonia import (
    CORE_DATA_PATH,
    GHGS,
    PREPROCESS_DATA_PATH,
    TECHNOLOGIES_NOT_FOR_SOLVER,
)
from ammonia.utility.utils import (
    load_cost_data_from_csv,
    load_intermediate_data_from_csv,
)
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory


def create_solver_input_tables(
    pathway_name: str,
    sensitivity: str,
    sector: str,
    carbon_cost_trajectory: CarbonCostTrajectory,
):
    """Create the input tables required to run the solver in the mpp-shared codebase.

    Args:
        pathway_name: for compatibility with other model step functions
        sensitivity: the desired sensitivity (usually "def")"
        sector: for compatibility
        carbon_cost_trajectory: for compatibility
    """
    calculate_folder = f"{PREPROCESS_DATA_PATH}/{sensitivity}/calculate_variables"
    imports_folder = f"{PREPROCESS_DATA_PATH}/{sensitivity}/imports_processed"
    write_path = f"{PREPROCESS_DATA_PATH}/{sensitivity}/solver_input_tables"

    if not os.path.exists(write_path):
        os.makedirs(write_path)

    solver_input_paths = [
        f"{CORE_DATA_PATH}/{pathway}/{sensitivity}/intermediate"
        for pathway in ["lc", "fa", "bau"]
    ]

    for path in solver_input_paths:
        if not os.path.exists(path):
            os.makedirs(path)

    # Emissions table is only copy and paste
    df_emissions = load_intermediate_data_from_csv(calculate_folder, "emissions")
    df_emissions = df_emissions.rename({"technology_destination": "technology"}, axis=1)
    df_emissions.to_csv(f"{write_path}/emissions.csv", index=False)
    for path in solver_input_paths:
        df_emissions.to_csv(f"{path}/emissions.csv", index=False)

    # Also copy over emission factors
    for ghg in GHGS:
        df_efs = load_intermediate_data_from_csv(
            imports_folder, f"emission_factors_{ghg}"
        )
        for path in solver_input_paths:
            df_efs.to_csv(f"{path}/emission_factors_{ghg}.csv", index=False)

    # Create technology transitions
    df_tech_transitions = load_cost_data_from_csv(sensitivity)

    flat_cols = {
        "tco": ("tco", "total"),
        "lcox": ("lcox", "total"),
        "switch_capex": ("tech_switch", "switch_capex"),
        "marginal_cost": ("opex_sum", "total_opex"),
    }
    df_tech_transitions = df_tech_transitions[list(flat_cols.values())]
    df_tech_transitions.columns = flat_cols.keys()
    df_tech_transitions = df_tech_transitions.fillna(0)
    df_tech_transitions = df_tech_transitions.reset_index(drop=False)
    df_tech_transitions = df_tech_transitions.rename({"type": "switch_type"}, axis=1)

    # Filter out undesired technologies
    df_tech_transitions = df_tech_transitions.loc[
        ~df_tech_transitions["technology_destination"].isin(TECHNOLOGIES_NOT_FOR_SOLVER)
    ]
    df_tech_transitions = df_tech_transitions.loc[
        ~df_tech_transitions["technology_origin"].isin(TECHNOLOGIES_NOT_FOR_SOLVER)
    ]

    df_tech_transitions.to_csv(f"{write_path}/technology_transitions.csv", index=True)

    for path in solver_input_paths:
        df_tech_transitions.to_csv(f"{path}/technology_transitions.csv", index=False)

    # Create technology characteristics
    df_maturity = load_intermediate_data_from_csv(
        imports_folder, "expected_maturity"
    ).drop(columns="unit")
    df_wacc = load_intermediate_data_from_csv(imports_folder, "wacc").drop(
        columns="unit"
    )
    df_lifetime = load_intermediate_data_from_csv(imports_folder, "lifetime").drop(
        columns="unit"
    )
    df_trl = load_intermediate_data_from_csv(imports_folder, "trl_current").drop(
        columns="unit"
    )
    df_classification = load_intermediate_data_from_csv(
        imports_folder, "classification"
    ).drop(columns="unit")

    # Rename classification to follow convention
    df_classification = df_classification.replace(
        {
            "Conventional": "initial",
            "Transition": "transition",
            "End-state": "end-state",
        }
    )

    dfs = [df_maturity, df_wacc, df_lifetime, df_trl, df_classification]
    df_tech_characteristics = reduce(
        lambda left, right: pd.merge(
            left,
            right,
            on=["product", "year", "region", "technology_destination"],
            how="left",
        ),
        dfs,
    )

    df_tech_characteristics = df_tech_characteristics.rename(
        {
            "technology_destination": "technology",
            "classification": "technology_classification",
            "type": "switch_type",
            "lifetime": "technology_lifetime",
        },
        axis=1,
    )

    df_tech_characteristics.to_csv(
        f"{write_path}/technology_characteristics.csv", index=False
    )

    for path in solver_input_paths:
        df_tech_characteristics.to_csv(
            f"{path}/technology_characteristics.csv", index=False
        )

    # Create table with OPEX, CAPEX and material and energy inputs
    df_cost = load_cost_data_from_csv(sensitivity)

    # Keep variable OPEX, fixed OPEX and total OPEX from cost table
    col_mapper = {
        "Variable OPEX": ("opex_sum", "variable_opex_after_cf"),
        "Fixed OPEX": ("opex_sum", "opex_fixed"),
        "Total OPEX": ("opex_sum", "total_opex"),
        "Greenfield CAPEX": ("tech_switch", "switch_capex"),
    }
    df_cost = df_cost[list(col_mapper.values())]
    df_cost.columns = col_mapper.keys()
    df_cost = df_cost.reset_index(drop=False)

    # Keep only New-build and destination technology
    df_cost = df_cost.loc[df_cost["type"] == "greenfield"]
    df_cost = df_cost.drop(columns=["technology_origin", "type"])
    df_cost = df_cost.rename({"technology_destination": "technology"}, axis=1)

    # Unstack to long
    df_cost = df_cost.melt(
        id_vars=["product", "technology", "year", "region"],
        var_name="parameter",
        value_name="value",
    )
    df_cost["parameter_group"] = "Cost"
    df_cost.loc[df_cost["parameter_group"] == "Cost", "unit"] = "USD/tpa"

    # Add material and energy inputs
    df_inputs = load_intermediate_data_from_csv(imports_folder, "inputs_all")
    df_inputs = df_inputs.rename(
        {
            "name": "parameter",
            "category": "parameter_group",
            "input": "value",
            "technology_destination": "technology",
        },
        axis=1,
    )

    # Concatenate
    df_inputs = df_inputs.set_index(["product", "technology", "region", "year"])
    df_cost = df_cost.set_index(["product", "technology", "region", "year"])
    df_inputs = pd.concat([df_inputs, df_cost]).reset_index(drop=False)

    # Add sector and export
    df_inputs["sector"] = "chemicals"
    df_inputs.to_csv(f"{write_path}/inputs_outputs.csv", index=False)

    for path in solver_input_paths:
        df_inputs.to_csv(f"{path}/inputs_outputs.csv", index=False)

    # To wide format
    df_inputs = df_inputs.set_index(
        [
            "sector",
            "product",
            "region",
            "technology",
            "parameter_group",
            "parameter",
            "unit",
        ]
    )
    df_inputs = df_inputs.pivot(columns="year", values="value")
    df_inputs = df_inputs.reset_index(drop=False)
    df_inputs.to_csv(f"{write_path}/inputs_outputs_wide.csv", index=False)

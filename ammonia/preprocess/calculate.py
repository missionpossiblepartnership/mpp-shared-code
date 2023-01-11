"""Calculate cost and emission metrics for every technology switch"""

import pandas as pd
from ammonia.config_ammonia import INPUT_METRICS, LOG_LEVEL, PREPROCESS_DATA_PATH
from ammonia.preprocess.calculate_cost import calculate_all_cost_components
from ammonia.preprocess.calculate_emissions import calculate_emissions_aggregate
from ammonia.preprocess.calculate_switches import calculate_switch_capex
from ammonia.preprocess.calculate_tco_lcox import (
    calculate_tco_lcox,
    calculate_total_opex,
    calculate_variable_opex,
)
from ammonia.preprocess.import_data import get_tech_switches
from ammonia.utility.utils import (
    load_intermediate_data_from_csv,
    write_intermediate_data_to_csv,
)
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory
from mppshared.utility.utils import get_logger

# Logging functionality
logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def calculate_variables(
    pathway_name: str,
    sensitivity: str,
    sector: str,
    carbon_cost_trajectory: CarbonCostTrajectory,
):
    """Calculate all variables for each technology switch and save in .csv file for subsequent use in technology ranking.

    Args:
        pathway_name: for compatibility with other model step functions
        sensitivity: the desired sensitivity (usually "def")"
        sector: for compatibility
        carbon_cost_trajectory: for compatibility
    """

    # PREPARE INPUT DATA
    # Load input data as dictionary
    keys_list = [entry for sublist in list(INPUT_METRICS.values()) for entry in sublist]
    input_data = dict.fromkeys(keys_list)
    for key in input_data.keys():
        input_data[key] = load_intermediate_data_from_csv(
            f"{PREPROCESS_DATA_PATH}/{sensitivity}/imports_processed", key
        )

    # Concatenate material and energy inputs
    df_inputs = concatenate_input_dfs(
        input_data["inputs_material"],
        input_data["inputs_energy"],
        input_data["h2_storage"],
    )
    write_intermediate_data_to_csv(
        f"{PREPROCESS_DATA_PATH}/{sensitivity}/imports_processed",
        "inputs_all",
        df_inputs,
    )

    # Concatenate all emission factors
    df_emission_factors = concatenate_emission_factor_dfs(
        input_data["emission_factors_co2"],
        input_data["emission_factors_n2o"],
        input_data["emission_factors_ch4"],
    )

    # CALCULATE EMISSIONS
    df_emissions = calculate_emissions_aggregate(
        df_inputs=df_inputs,
        df_emission_factors=df_emission_factors,
        df_capture_rates=input_data["capture_rates"],
        df_technology_classification=input_data["classification"],
    )

    # Save as .csv
    calculate_folder = f"{PREPROCESS_DATA_PATH}/{sensitivity}/calculate_variables"
    write_intermediate_data_to_csv(calculate_folder, "emissions", df_emissions)

    # CALCULATE TCO
    # Get possible technology switches
    df_tech_switches = get_tech_switches(sensitivity)

    # Calculate switching CAPEX for each technology switch, region and year
    df_switch_capex = calculate_switch_capex(
        df_tech_switches=df_tech_switches, df_capex=input_data["capex"], from_csv=False
    )

    write_intermediate_data_to_csv(calculate_folder, "switch_capex", df_switch_capex)

    # Calculate all cost components (apart from carbon cost)
    df_cost = calculate_all_cost_components(
        df_inputs=df_inputs,
        df_prices=input_data["prices"],
        df_emissions=df_emissions,
    )

    # Calculate variable OPEX before and after capacity factor
    df_cost = calculate_variable_opex(df_cost, input_data["capacity_factor"])

    # Calculate total OPEX from variable and fixed OPEX
    df_cost = calculate_total_opex(df_cost, input_data["opex_fixed"])

    # Drop business cases where low-cost power regions do not apply
    lcpr_techs = [
        "Electrolyser - grid PPA + ammonia synthesis",
        "Electrolyser - dedicated VRES + grid PPA + ammonia synthesis",
        "Electrolyser - dedicated VRES + H2 storage - pipeline + ammonia synthesis",
        "Electrolyser - dedicated VRES + H2 storage - geological + ammonia synthesis",
    ]
    lcprs = ["Brazil", "Saudi Arabia", "Australia", "Namibia"]
    df_cost = df_cost.reset_index()
    df_cost = df_cost.drop(
        df_cost[
            (~df_cost["technology_destination"].isin(lcpr_techs))
            & (df_cost["region"].isin(lcprs))
        ].index
    )
    df_cost = df_cost.set_index(["product", "technology_destination", "year", "region"])

    write_intermediate_data_to_csv(calculate_folder, "cost", df_cost, flag_index=True)

    # Calculate TCO
    df_tco = calculate_tco_lcox(
        sensitivity=sensitivity,
        df_switch_capex=df_switch_capex,
        df_cost=df_cost,
        df_wacc=input_data["wacc"],
        df_lifetime=input_data["lifetime"],
        from_csv=False,
    )

    write_intermediate_data_to_csv(calculate_folder, "tco", df_tco.reset_index())


def concatenate_input_dfs(
    df_inputs_material: pd.DataFrame,
    df_inputs_energy: pd.DataFrame,
    df_h2_storage: pd.DataFrame,
) -> pd.DataFrame:
    """Concatenate the material, energy and h2 storage inputs into a DataFrame with a column category that is either "Energy" or "Raw material"

    Args:
        df_inputs_material (pd.DataFrame): contains column "input_material"
        df_inputs_energy (pd.DataFrame): contains column "input_energy"
        df_h2_storage (pd.DataFrame): contains column "h2_storage"

    Returns:
        pd.DataFrame: contains columns "input", "category"
    """
    # Add category
    df_inputs_material["category"] = "Raw material"
    df_inputs_energy["category"] = "Energy"
    df_h2_storage["category"] = "H2 storage"

    # Rename input columns
    df_inputs_material = df_inputs_material.rename(
        mapper={"input_material": "input"}, axis=1
    )
    df_inputs_energy = df_inputs_energy.rename(mapper={"input_energy": "input"}, axis=1)
    df_h2_storage = df_h2_storage.rename(mapper={"h2_storage": "input"}, axis=1)

    # Concatenate DataFrames
    df_inputs = pd.concat([df_inputs_material, df_inputs_energy, df_h2_storage])

    # Sort for better viewing
    df_inputs = df_inputs.sort_values(
        by=["technology_destination", "year", "region", "category", "name"],
        ignore_index=True,
    )

    return df_inputs


def concatenate_emission_factor_dfs(
    df_emission_factors_co2: pd.DataFrame,
    df_emission_factors_n2o: pd.DataFrame,
    df_emission_factors_ch4: pd.DataFrame,
) -> pd.DataFrame:
    """Concenate list of DataFrames with emission factors for different GHGs"""

    dfs = [df_emission_factors_co2, df_emission_factors_n2o, df_emission_factors_ch4]
    ghgs = ["co2", "n2o", "ch4"]

    # Add GHG column and rename emission factor column
    for (i, df) in enumerate(dfs):
        df["ghg"] = ghgs[i]
        df.rename(
            mapper={f"emission_factor_{ghgs[i]}": "emission_factor"},
            axis=1,
            inplace=True,
        )

    # Concatenate
    df_emission_factors = pd.concat(dfs)

    return df_emission_factors

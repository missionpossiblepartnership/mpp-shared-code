"""Calculate emissions for each technology, region and year by scope."""

from functools import reduce

import numpy as np
import pandas as pd

from ammonia.config_ammonia import (
    GHGS,
    LOG_LEVEL,
    UREA_CO2_EMISSIONS_TO_SCOPE1,
    UREA_YEAR_MANDATORY_DAC,
)
from ammonia.utility.utils import unit_column_suffix
from mppshared.utility.utils import get_logger

# Logging functionality
logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def calculate_emissions_scope1_co2(
    df_inputs: pd.DataFrame,
    df_emission_factors: pd.DataFrame,
    df_capture_rates: pd.DataFrame,
    df_technology_classification: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate scope 1 emissions for CO2: emissions from the inputs used such as gas and coal

    Args:
        df_inputs: contains Energy and Raw material inputs for each product, technology, year and region. No difference between energy and process emissivities assumed.
        df_emission_factors: emission factors
        df_capture_rates: share of emissions captured by CCS (for technologies with CCS)

    Returns:
        Dataframe with columns "scope1_pre_process_input_pre_ccs", "scope1_captured_pre_process_input", "scope1_captured", "scope1" and "additional_co2_input" for each product, technology, year and region
    """

    # Keep scope 1 only and filter out CO2 input
    df_emission_factors = df_emission_factors.loc[df_emission_factors["scope"] == "1"]
    df_inputs_no_co2 = df_inputs.loc[df_inputs["name"] != "CO2"]

    # Merge with emission factors
    df_inputs_no_co2 = unit_column_suffix(df_inputs_no_co2, "input")
    df_emission_factors = unit_column_suffix(df_emission_factors, "emission_factor")

    df_emissions = df_inputs_no_co2.merge(
        df_emission_factors, on=["product", "name", "year", "region"], how="left"
    )

    # Calculate emissions in tCO2/t of product (before CCS) for emissions from fossil and bio inputs
    df_emissions["scope1_pre_process_input_pre_ccs"] = (
        df_emissions["input"] * df_emissions["emission_factor"]
    ).fillna(0)

    # Sum emissions for each technology (for a specific product, year and region)
    df_emissions = (
        df_emissions.groupby(
            ["product", "technology_destination", "year", "region"],
            as_index=False,
        )
        .agg({"scope1_pre_process_input_pre_ccs": "sum"})
        .fillna(0)
    )

    # Calculate scope 1 emissions after process input, before CCS
    # For urea production with fossil-based and bio-based technologies, the CO2 from the process stream of ammonia synthesis is used as an input for urea synthesis
    df_inputs_co2 = df_inputs.loc[df_inputs["name"] == "CO2"]
    df_emissions = df_emissions.merge(
        df_inputs_co2[["product", "year", "region", "technology_destination", "input"]],
        on=["product", "year", "region", "technology_destination"],
        how="left",
    )

    df_emissions["scope1_pre_ccs"] = (
        df_emissions["scope1_pre_process_input_pre_ccs"] - df_emissions["input"]
    )

    # For urea production, the CO2 input is taken directly from the process stream; if the resulting scope 1 emissions would be negative, set them to zero and adjust the additional CO2 input required accordingly
    df_emissions["scope1_pre_ccs"] = (
        df_emissions["scope1_pre_process_input_pre_ccs"] - df_emissions["input"]
    )

    df_emissions["external_co2_input"] = np.where(
        df_emissions["scope1_pre_ccs"] < 0, -df_emissions["scope1_pre_ccs"], 0
    )

    df_emissions.loc[df_emissions["scope1_pre_ccs"] < 0, "scope1_pre_ccs"] = 0
    df_emissions.loc[
        df_emissions["scope1_pre_ccs"].isna(), "scope1_pre_ccs"
    ] = df_emissions["scope1_pre_process_input_pre_ccs"]

    # Special case: for waste to ammonia, there's no process integration
    df_emissions.loc[
        df_emissions["technology_destination"] == "Waste to ammonia",
        "external_co2_input",
    ] = df_emissions["input"]

    # From the year in which DAC is mandated for urea production, also fossil-based end-state technologies need external CO2 input
    if UREA_YEAR_MANDATORY_DAC < 2050:
        df_emissions = df_emissions.merge(
            df_technology_classification.drop(columns=["unit"]),
            on=["product", "year", "region", "technology_destination"],
            how="left",
        )

        df_emissions.loc[
            (df_emissions["year"] >= UREA_YEAR_MANDATORY_DAC)
            & (df_emissions["classification"] == "End-state"),
            "external_co2_input",
        ] = df_emissions["input"]

        df_emissions = df_emissions.drop(columns=["classification"])

    # If urea CO2 emissions are allocated to scope 1, pre CCS emissions are the same as pre CCS and pre process emissions
    if UREA_CO2_EMISSIONS_TO_SCOPE1 == True:
        df_emissions["scope1_pre_ccs"] = df_emissions[
            "scope1_pre_process_input_pre_ccs"
        ]

    # Add CCS capture rate for each technology
    df_emissions = df_emissions.merge(
        df_capture_rates,
        on=["product", "technology_destination", "year", "region"],
        how="left",
    )

    # Calculate captured CCS emissions before input to subsequent production process of urea
    df_emissions["scope1_captured"] = (
        df_emissions["scope1_pre_ccs"] * df_emissions["capture_rate"]
    ).fillna(0)

    # Final scope 1 emissions are scope 1 emissions before CCS minus captured emissions
    df_emissions["scope1"] = (
        df_emissions["scope1_pre_ccs"] - df_emissions["scope1_captured"]
    )

    # Special case 1: for bio-based technologies, scope 1 emissions are set to zero because they are assumed carbon-neutral
    df_emissions.loc[
        df_emissions["technology_destination"].str.contains("Biomass|Waste"), "scope1"
    ] = 0

    # Special case 2: scope 1 emissions from methane pyrolysis are zero because it produces black carbon
    df_emissions.loc[
        df_emissions["technology_destination"]
        == "Methane Pyrolysis + ammonia synthesis",
        "scope1",
    ] = 0

    # Add CO2 prefix to each output column
    output_cols = [
        "scope1_pre_process_input_pre_ccs",
        "scope1_captured_pre_process_input",
        "scope1_captured",
        "scope1",
    ]
    df_emissions = df_emissions.rename(
        {output_col: f"co2_{output_col}" for output_col in output_cols}, axis=1
    )

    return df_emissions.drop(["name", "unit", "input", "capture_rate"], axis=1)


def calculate_emissions_scope1_n2o(
    df_inputs: pd.DataFrame,
    df_emission_factors: pd.DataFrame,
    df_capture_rates: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate scope 1 emissions for N2O

    Args:
        df_inputs: contains Energy and Raw material inputs for each product, technology, year and region. No difference between energy and process emissivities assumed.
        df_emission_factors: emission factors for a specific GHG
        df_capture_rates: capture rates for N2O

    Returns:
        Dataframe with column "scope1" for each product, technology, year and region
    """
    # Keep scope 1 only
    df_emission_factors = df_emission_factors.loc[df_emission_factors["scope"] == "1"]

    # For N2O, the emissions per ton of product are equal to the emission factors
    df_emissions = (
        df_inputs[["product", "year", "region", "technology_destination"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    df_emissions = df_emissions.merge(
        df_emission_factors, on=["product", "year", "region"], how="left"
    )

    # Calculate emissions after capture
    df_emissions = df_emissions.merge(
        df_capture_rates,
        on=["product", "technology_destination", "year", "region"],
        how="left",
    )
    df_emissions["n2o_scope1"] = (
        df_emissions["emission_factor"] * (1 - df_emissions["capture_rate"])
    ).fillna(0)

    return df_emissions[
        ["product", "year", "region", "technology_destination", "n2o_scope1"]
    ]


def calculate_emissions_scope2_co2(
    df_inputs: pd.DataFrame, df_emission_factors: pd.DataFrame
) -> pd.DataFrame:
    """
    Calculate scope 2 emissions: indirect emissions of purchased electricity (CO2 emissions only)

    Args:
        df_inputs: Inputs per process
        df_emission_factors: Emission factors

    Returns:
        Dataframe with scope 2 emissions by GHG
    """

    # Keep scope 2 only
    df_emission_factors = df_emission_factors.loc[(df_emission_factors["scope"] == "2")]

    # Merge inputs with emission factors
    df_inputs = unit_column_suffix(df_inputs, "input")
    df_emission_factors = unit_column_suffix(df_emission_factors, "emission_factor")

    df_emissions = df_inputs.merge(
        df_emission_factors, on=["product", "name", "year", "region"], how="left"
    )

    # Calculate emissions in tCO2/t of product, filling with 0 if no scope 2 emissions of input
    df_emissions["co2_scope2"] = df_emissions["input"] * df_emissions["emission_factor"]

    # Sum emissions from process (material input) and energy (energy input) and all energy carriers ("name")
    df_emissions = (
        df_emissions.groupby(
            ["product", "technology_destination", "year", "region"], as_index=False
        )
        .agg({"co2_scope2": "sum"})
        .fillna(0)
    )

    return df_emissions


def calculate_emissions_scope3_upstream(
    df_inputs: pd.DataFrame, df_emission_factors: pd.DataFrame
) -> pd.DataFrame:
    """Calculate scope 3 emissions upstream

    Args:
        df_inputs: Inputs per process
        df_emission_factors: Emission factors

    Returns:
        Dataframe with upstream scope 3 emissions by GHG
    """

    # Keep scope 3 upstream emission factors only
    df_emission_factors = df_emission_factors.loc[
        df_emission_factors["scope"] == "3_upstream"
    ]

    # Merge inputs with emission factors
    df_inputs = unit_column_suffix(df_inputs, "input")
    df_emission_factors = unit_column_suffix(df_emission_factors, "emission_factor")

    df_emissions = df_inputs.merge(
        df_emission_factors, on=["product", "name", "year", "region"], how="left"
    )

    # Calculate emissions for each GHG, filling with 0 if no scope 3 emissions of input
    for ghg in GHGS:
        df_emissions.loc[df_emissions["ghg"] == ghg, f"{ghg}_scope3_upstream"] = (
            df_emissions["input"] * df_emissions["emission_factor"]
        )

        df_emissions[f"{ghg}_scope3_upstream"] = df_emissions[
            f"{ghg}_scope3_upstream"
        ].fillna(0)

    # Sum all emission contributions
    df_emissions = df_emissions.groupby(
        ["product", "technology_destination", "year", "region"],
        as_index=False,
    ).agg({f"{ghg}_scope3_upstream": "sum" for ghg in GHGS})

    return df_emissions


def calculate_emissions_scope3_downstream(
    df_inputs: pd.DataFrame, df_emission_factors: pd.DataFrame
) -> pd.DataFrame:
    """Calculate scope 3 emissions downstream

    Args:
        df_inputs: Inputs per process
        df_emission_factors: Emission factors

    Returns:
        Dataframe with downstream scope 3 emissions by GHG
    """

    # Keep scope 3 downstream emission factors only
    df_emission_factors = df_emission_factors.loc[
        df_emission_factors["scope"] == "3_downstream"
    ]

    # For scope 3 downstream emissions, the emissions per ton of product are equal to the emission factors
    df_emissions = (
        df_inputs[["product", "year", "region", "technology_destination"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    df_emissions = df_emissions.merge(
        df_emission_factors, on=["product", "year", "region"], how="left"
    )

    # Calculate scope 3 downstream emissions for each GHG, filling 0 if no scope 3 emissions for that GHG
    for ghg in GHGS:
        df_emissions.loc[df_emissions["ghg"] == ghg, f"{ghg}_scope3_downstream"] = (
            df_emissions["emission_factor"]
        ).fillna(0)

        df_emissions[f"{ghg}_scope3_downstream"] = df_emissions[
            f"{ghg}_scope3_downstream"
        ].fillna(0)

    # Sum all emission contributions
    df_emissions = df_emissions.groupby(
        ["product", "technology_destination", "year", "region"],
        as_index=False,
    ).agg({f"{ghg}_scope3_downstream": "sum" for ghg in GHGS})

    return df_emissions


def combine_emissions_data(dfs) -> pd.DataFrame:
    """
    Combine emissions data into one dataframe

    Args:
        dfs: List of dataframes with emissions data

    Returns:
        Dataframe with scope 1,2,3 upstream/downstream emissions by GHG
    """

    # Outer join to keep all processes and years
    df_emissions = reduce(
        lambda left, right: pd.merge(
            left,
            right,
            on=["product", "technology_destination", "year", "region"],
            how="outer",
        ),
        dfs,
    ).fillna(0)

    # Add missing column for scope 1 CH4 emissions and scope 2 CH4 and N2O emissions
    df_emissions["ch4_scope1"] = 0
    df_emissions["ch4_scope2"] = 0
    df_emissions["n2o_scope2"] = 0

    return df_emissions


def calculate_emissions_aggregate(
    df_inputs: pd.DataFrame,
    df_emission_factors: pd.DataFrame,
    df_capture_rates: pd.DataFrame,
    df_technology_classification: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate the scope 1,2,3 emissions for all GHGs per process/year/region
    Args:
        df_inputs: Inputs per process
        df_emission_factors: Emissions factors per input for all GHGs
        df_ccs_rate: CCS rate per process and year

    Returns:
        Dataframe with emissions
    """

    # CO2 scope 1 emissions (including carbon capture)
    df_scope1_co2 = calculate_emissions_scope1_co2(
        df_inputs=df_inputs,
        df_emission_factors=df_emission_factors.loc[
            df_emission_factors["ghg"] == "co2"
        ],
        df_capture_rates=df_capture_rates.loc[
            df_capture_rates["name"] == "CCS Capture rate"
        ],
        df_technology_classification=df_technology_classification,
    )

    # N2O scope 1 emissions (including capture of N2O emissions)
    df_scope1_n2o = calculate_emissions_scope1_n2o(
        df_inputs=df_inputs,
        df_emission_factors=df_emission_factors.loc[
            df_emission_factors["ghg"] == "n2o"
        ],
        df_capture_rates=df_capture_rates.loc[
            df_capture_rates["name"] == "N2O Capture rate"
        ],
    )

    # Scope 2 emissions for all GHG
    df_scope2 = calculate_emissions_scope2_co2(
        df_inputs=df_inputs, df_emission_factors=df_emission_factors
    )

    # Scope 3 upstream and downstream emissions for all GHG
    df_scope3_upstream = calculate_emissions_scope3_upstream(
        df_inputs=df_inputs, df_emission_factors=df_emission_factors
    )

    df_scope3_downstream = calculate_emissions_scope3_downstream(
        df_inputs=df_inputs, df_emission_factors=df_emission_factors
    )

    return combine_emissions_data(
        [
            df_scope1_co2,
            df_scope1_n2o,
            df_scope2,
            df_scope3_upstream,
            df_scope3_downstream,
        ]
    )

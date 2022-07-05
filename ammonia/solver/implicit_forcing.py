"""Apply implicit forcing (carbon cost, technology moratorium and other filters for technology switches)."""

# Library imports
from datetime import timedelta
from pathlib import Path
from re import M
from timeit import default_timer as timer
import numpy as np
import pandas as pd

# Shared imports
from ammonia.config_ammonia import (
    GROUPING_COLS_FOR_NPV,
    REGIONS_SALT_CAVERN_AVAILABILITY,
    TECHNOLOGY_MORATORIUM,
    TRANSITIONAL_PERIOD_YEARS,
    PRODUCTS,
    RANKING_COST_METRIC,
    SCOPES_CO2_COST,
    STANDARD_LIFETIME,
    STANDARD_CUF,
    STANDARD_WACC,
)
from mppshared.solver.implicit_forcing import (
    add_carbon_cost_addition_to_technology_switches,
    add_technology_classification_to_switching_table,
    apply_technology_availability_constraint,
    apply_salt_cavern_availability_constraint,
    apply_technology_moratorium,
    calculate_carbon_cost_addition_to_cost_metric,
    calculate_emission_reduction,
)
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory

# Initialize logger
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)


def apply_implicit_forcing(
    pathway: str,
    sensitivity: str,
    sector: str,
    carbon_cost_trajectory: CarbonCostTrajectory,
):
    """Apply the implicit forcing mechanisms to the input tables.
    Args:
        pathway:
        sensitivity:
        sector:
    Returns:
        pd.DataFrame: DataFrame ready for ranking the technology switches
    """
    logger.info("Applying implicit forcing")

    # Import input tables (folder paths include the carbon cost)
    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS,
        carbon_cost_trajectory=carbon_cost_trajectory,
    )

    df_technology_switches = importer.get_technology_transitions_and_cost()
    df_emissions = importer.get_emissions()
    df_technology_characteristics = importer.get_technology_characteristics()

    # Eliminate technology switches that downgrade technology classification and to an immature technology
    df_technology_switches = apply_technology_availability_constraint(
        df_technology_switches, df_technology_characteristics
    )

    # Eliminate technologies with geological H2 storage in regions without salt caverns
    df_technology_switches = apply_salt_cavern_availability_constraint(
        df_technology_switches, REGIONS_SALT_CAVERN_AVAILABILITY
    )

    # Apply technology moratorium (year after which newbuild capacity must be transition or end-state technologies)
    if pathway != "bau":
        df_technology_switches = apply_technology_moratorium(
            df_technology_switches=df_technology_switches,
            df_technology_characteristics=df_technology_characteristics,
            moratorium_year=TECHNOLOGY_MORATORIUM,
            transitional_period_years=TRANSITIONAL_PERIOD_YEARS,
        )
    # Add technology classification
    else:
        df_technology_switches = add_technology_classification_to_switching_table(
            df_technology_switches, df_technology_characteristics
        )

    # Apply carbon cost
    start = timer()
    df_carbon_cost_addition = calculate_carbon_cost_addition_to_cost_metric(
        df_technology_switches=df_technology_switches,
        df_emissions=df_emissions,
        df_technology_characteristics=df_technology_characteristics,
        df_carbon_cost=carbon_cost_trajectory.df_carbon_cost,
        scopes_co2_cost=SCOPES_CO2_COST,
        cost_metrics=["annualized_cost", "marginal_cost", "lcox"],
        standard_cuf=STANDARD_CUF,
        standard_lifetime=STANDARD_LIFETIME,
        standard_wacc=STANDARD_WACC,
        grouping_cols_for_npv=GROUPING_COLS_FOR_NPV,
    )
    end = timer()
    logger.info(
        f"Time elapsed to apply carbon cost to {len(df_carbon_cost_addition)} rows: {timedelta(seconds=end-start)}"
    )

    # Output carbon cost addition to intermediate folder
    importer.export_data(
        df=df_carbon_cost_addition,
        filename="carbon_cost_addition.csv",
        export_dir="intermediate",
        index=False,
    )

    # Update LCOX in technology switching DataFrame with carbon cost
    df_technology_switches = add_carbon_cost_addition_to_technology_switches(
        df_technology_switches, df_carbon_cost_addition, "lcox"
    )

    # Calculate emission deltas between origin and destination technology
    df_ranking = calculate_emission_reduction(df_technology_switches, df_emissions)

    importer.export_data(
        df=df_ranking,
        filename="technologies_to_rank.csv",
        export_dir="intermediate",
        index=False,
    )

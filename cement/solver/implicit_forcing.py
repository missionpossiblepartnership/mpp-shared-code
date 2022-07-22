"""Apply implicit forcing (carbon cost, technology moratorium and other filters for technology switches)."""

# Library imports
import numpy as np
import pandas as pd

# Shared code imports
from aluminium.config_aluminium import (EMISSION_SCOPES, GHGS,
                                        PATHWAYS_WITH_TECHNOLOGY_MORATORIUM,
                                        PRODUCTS, TECHNOLOGY_MORATORIUM,
                                        TRANSITIONAL_PERIOD_YEARS)
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.solver.implicit_forcing import (
    add_technology_classification_to_switching_table, apply_hydro_constraint,
    apply_technology_availability_constraint, apply_technology_moratorium,
    calculate_emission_reduction)
# Initialize logger
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)


def apply_implicit_forcing(pathway: str, sensitivity: str, sector: str) -> pd.DataFrame:
    """Apply the implicit forcing mechanisms to the input tables.

    Args:
        pathway: either of "bau", "fa", "lc", "cc"
        sensitivity: in ALL_SENSITIVITIES
        sector: "aluminium"

    Returns:
        pd.DataFrame: DataFrame ready for ranking the technology switches
    """
    logger.info("Applying implicit forcing")

    # Import input tables
    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS,
    )

    df_technology_switches = importer.get_technology_transitions_and_cost()
    df_emissions = importer.get_emissions()
    df_technology_characteristics = importer.get_technology_characteristics()

    # Take out technology switches that downgrade technology classification and to immature technologeies
    df_technology_switches = apply_technology_availability_constraint(
        df_technology_switches, df_technology_characteristics
    )

    # Eliminate disallowed technology switches with hydro technologies
    df_technology_switches = apply_hydro_constraint(
        df_technology_switches, sector, PRODUCTS
    )

    # Apply technology moratorium (year after which newbuild capacity must be transition or end-state technologies)
    if pathway in PATHWAYS_WITH_TECHNOLOGY_MORATORIUM:
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

    # Calculate emission deltas between origin and destination technology
    df_ranking = calculate_emission_reduction(
        df_technology_switches, df_emissions, EMISSION_SCOPES, GHGS
    )

    # Export technology switching table to be used for ranking
    importer.export_data(
        df=df_ranking,
        filename="technologies_to_rank.csv",
        export_dir="intermediate",
        index=False,
    )

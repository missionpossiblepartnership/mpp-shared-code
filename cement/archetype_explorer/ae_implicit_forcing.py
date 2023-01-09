"""Applies implicit forcing for archetype explorer"""

# Library imports
import pandas as pd

# Shared code imports
from cement.config.config_cement import (
    EMISSION_SCOPES,
    GHGS,
    START_YEAR,
    CCUS_CONTEXT,
)
from mppshared.config import LOG_LEVEL
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.solver.implicit_forcing import (
    apply_technology_availability_constraint,
    calculate_emission_reduction,
)

from cement.archetype_explorer.ae_config import AE_LIST_TECHNOLOGIES

# Initialize logger
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def ae_apply_implicit_forcing(
    pathway_name: str, sensitivity: str, sector: str, products: list
):
    """Apply the implicit forcing mechanisms to the input tables.

    Args:
        pathway_name:
        sensitivity:
        sector:
        products:

    Returns:
        pd.DataFrame: DataFrame ready for ranking the technology switches
    """
    logger.info("Applying implicit forcing")

    # Import input tables
    importer = IntermediateDataImporter(
        pathway_name=pathway_name,
        sensitivity=sensitivity,
        sector=sector,
        products=products,
    )

    df_technology_switches = importer.get_technology_transitions_and_cost()
    df_emissions = importer.get_emissions()
    df_technology_characteristics = importer.get_technology_characteristics()

    # Take out technology switches that downgrade the technology classification and to destination technologies
    #   that have not reached maturity yet
    df_technology_switches = apply_technology_availability_constraint(
        df_technology_switches, df_technology_characteristics, start_year=START_YEAR
    )

    # Remove all switches from / to Dry kiln reference plant
    df_technology_switches = df_technology_switches.loc[
        df_technology_switches["technology_origin"] != "Dry kiln reference plant",
        :,
    ]
    df_technology_switches = df_technology_switches.loc[
        df_technology_switches["technology_destination"] != "Dry kiln reference plant",
        :,
    ]

    # Remove switches where technology_origin == technology_destination
    df_technology_switches = df_technology_switches.loc[
        df_technology_switches["technology_destination"] != df_technology_switches["technology_origin"],
        :,
    ]

    # filter technologies
    df_technology_switches = df_technology_switches.loc[
        (
            (
                (df_technology_switches["technology_destination"].isin(AE_LIST_TECHNOLOGIES))
                & (df_technology_switches["technology_origin"].isin(AE_LIST_TECHNOLOGIES))
            ) ^ (
                (df_technology_switches["switch_type"] == "decommission")
                & (df_technology_switches["technology_origin"].isin(AE_LIST_TECHNOLOGIES))
            ) ^ (
                (df_technology_switches["technology_destination"].isin(AE_LIST_TECHNOLOGIES))
                & (df_technology_switches["switch_type"] == "greenfield")
            )
        ), :
    ]

    # Calculate emission deltas between origin and destination technology
    df_tech_to_rank = calculate_emission_reduction(
        df_technology_switches=df_technology_switches,
        df_emissions=df_emissions,
        emission_scopes=EMISSION_SCOPES,
        ghgs=GHGS,
    )

    # filter CCU/S OPEX context
    if "opex_context" in df_tech_to_rank.columns:
        df_tech_to_rank = df_tech_to_rank.loc[
            (df_tech_to_rank["opex_context"] == f"value_{CCUS_CONTEXT[0]}"), :
        ]

    # Export technology switching table to be used for ranking
    importer.export_data(
        df=df_tech_to_rank,
        filename="technologies_to_rank.csv",
        export_dir="intermediate",
        index=False,
    )

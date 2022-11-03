"""Apply implicit forcing (carbon cost, technology moratorium and other filters for technology switches)."""

# Library imports
import pandas as pd

# Shared code imports
from cement.config.config_cement import (
    EMISSION_SCOPES,
    GHGS,
    PATHWAYS_WITH_TECHNOLOGY_MORATORIUM,
    REGIONS_NATURAL_GAS,
    START_YEAR,
    TECHNOLOGY_MORATORIUM,
    TRANSITIONAL_PERIOD_YEARS,
    MARKET_ENTRY_AF_90,
    MARKET_ENTRY_CCUS,
    LIST_TECHNOLOGIES,
    CCUS_CONTEXT,
)
from mppshared.config import LOG_LEVEL
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.solver.implicit_forcing import (
    add_technology_classification_to_switching_table,
    apply_technology_availability_constraint,
    apply_technology_moratorium,
    calculate_emission_reduction,
)

# Initialize logger
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def apply_implicit_forcing(
    pathway_name: str, sensitivity: str, sector: str, products: list
):
    """Apply the implicit forcing mechanisms to the input tables.

    Args:
        pathway_name: either of "bau", "fa", "lc", "cc"
        sensitivity: in ALL_SENSITIVITIES
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

    # filter technologies
    df_technology_switches = df_technology_switches.loc[
        (
            (
                (df_technology_switches["technology_destination"].isin(LIST_TECHNOLOGIES[sensitivity]))
                & (df_technology_switches["technology_origin"].isin(LIST_TECHNOLOGIES[sensitivity]))
            ) ^ (
                (df_technology_switches["switch_type"] == "decommission")
                & (df_technology_switches["technology_origin"].isin(LIST_TECHNOLOGIES[sensitivity]))
            ) ^ (
                (df_technology_switches["technology_destination"].isin(LIST_TECHNOLOGIES[sensitivity]))
                & (df_technology_switches["switch_type"] == "greenfield")
            )
        ), :
    ]

    # Apply technology moratorium
    if pathway_name in PATHWAYS_WITH_TECHNOLOGY_MORATORIUM:
        df_technology_switches = apply_technology_moratorium(
            df_technology_switches=df_technology_switches,
            df_technology_characteristics=df_technology_characteristics,
            moratorium_year=TECHNOLOGY_MORATORIUM,
            transitional_period_years=TRANSITIONAL_PERIOD_YEARS,
        )

    # allow switches to all CCS setups after a certain market entry year
    df_technology_switches = df_technology_switches.loc[
        ~(
             df_technology_switches["technology_destination"].str.contains("storage")
             & (df_technology_switches["year"] < MARKET_ENTRY_CCUS)
        ), :
    ]
    # allow switches to all CCU setups after a certain market entry year
    df_technology_switches = df_technology_switches.loc[
        ~(
             df_technology_switches["technology_destination"].str.contains("usage")
             & (df_technology_switches["year"] < MARKET_ENTRY_CCUS)
        ), :
    ]
    # allow switches to all alternative fuels 90% setups after a certain market entry year
    df_technology_switches = df_technology_switches.loc[
        ~(
            df_technology_switches["technology_destination"].str.contains("90%")
            & (df_technology_switches["year"] < MARKET_ENTRY_AF_90)
        ), :
    ]

    # Add technology classification
    df_technology_switches = add_technology_classification_to_switching_table(
        df_technology_switches, df_technology_characteristics
    )

    # Calculate emission deltas between origin and destination technology
    df_tech_to_rank = calculate_emission_reduction(
        df_technology_switches=df_technology_switches,
        df_emissions=df_emissions,
        emission_scopes=EMISSION_SCOPES,
        ghgs=GHGS,
    )

    # only allow switches to natural gas in regions in REGIONS_NATURAL_GAS
    df_tech_to_rank = df_tech_to_rank.loc[
        ~(
            ~df_tech_to_rank["region"].isin(REGIONS_NATURAL_GAS)
            & df_tech_to_rank["technology_destination"].str.contains("natural gas")
        ),
        :,
    ]

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

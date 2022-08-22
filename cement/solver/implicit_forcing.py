"""Apply implicit forcing (carbon cost, technology moratorium and other filters for technology switches)."""

# Library imports
import pandas as pd

# Shared code imports
from cement.config.config_cement import (
    EMISSION_SCOPES,
    GHGS,
    PATHWAYS_WITH_TECHNOLOGY_MORATORIUM,
    START_YEAR,
    TECHNOLOGY_MORATORIUM,
    TRANSITIONAL_PERIOD_YEARS,
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

    # Take out technology switches that downgrade technology classification and to immature technologies
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

    # Apply technology moratorium (year after which newbuild capacity must be transition or end-state technologies)
    if pathway_name in PATHWAYS_WITH_TECHNOLOGY_MORATORIUM:
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
    df_tech_to_rank = calculate_emission_reduction(
        df_technology_switches=df_technology_switches,
        df_emissions=df_emissions,
        emission_scopes=EMISSION_SCOPES,
        ghgs=GHGS,
    )

    # todo: For future Luis, Timon or any other developer, this line was added to filter the technologies and only
    # keep the ones with the right context for the first run of the code
    # Only get the rows with value value_high_low in column opex_context
    df_tech_to_rank = df_tech_to_rank[
        df_tech_to_rank["opex_context"] == "value_high_low"
    ]

    # todo dev: remove this workaround of excluding all usage techs
    df_tech_to_rank = df_tech_to_rank.loc[
        ~(
            df_tech_to_rank["technology_origin"].str.contains("usage")
            | df_tech_to_rank["technology_destination"].str.contains("usage")
        ),
        :,
    ]
    # todo dev

    # todo dev: discuss whether or not and if so, how to include renovations from and to same tech / rebuilds.
    df_tech_to_rank = df_tech_to_rank.loc[
        ~(
            (df_tech_to_rank["technology_origin"] == df_tech_to_rank["technology_destination"])
            & (df_tech_to_rank["switch_type"] == "brownfield_renovation")
        )
    ]
    # todo dev

    # Export technology switching table to be used for ranking
    importer.export_data(
        df=df_tech_to_rank,
        filename="technologies_to_rank.csv",
        export_dir="intermediate",
        index=False,
    )

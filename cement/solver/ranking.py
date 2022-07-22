"""Create ranking of technology switches (decommission, brownfield, greenfield)."""

from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.solver.ranking import rank_technology_histogram
from aluminium.config_aluminium import (
    PRODUCTS,
    RANK_TYPES,
    RANKING_COST_METRIC,
    NUMBER_OF_BINS_RANKING,
    EMISSION_SCOPES_RANKING,
    GHGS_RANKING,
    RANKING_CONFIG,
)


def make_rankings(pathway: str, sensitivity: str, sector: str):
    """Create the ranking for the three types of technology switches"""

    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS,
    )

    # Create ranking using the histogram methodology for every rank type
    df_ranking = importer.get_technologies_to_rank()
    for rank_type in RANK_TYPES:
        df_rank = rank_technology_histogram(
            df_ranking=df_ranking,
            rank_type=rank_type,
            pathway=pathway,
            cost_metric=RANKING_COST_METRIC,
            n_bins=NUMBER_OF_BINS_RANKING,
            ranking_config=RANKING_CONFIG[rank_type][pathway],
            emission_scopes_ranking=EMISSION_SCOPES_RANKING,
            ghgs_ranking=GHGS_RANKING,
        )

        # Save ranking table as csv
        importer.export_data(
            df=df_rank,
            filename=f"{rank_type}_rank.csv",
            export_dir=f"ranking",
            index=False,
        )

"""Create ranking of technology switches (decommission, brownfield, greenfield)."""

from cement.config.config_cement import (BIN_METHODOLOGY,
                                         COST_METRIC_RELATIVE_UNCERTAINTY,
                                         EMISSION_SCOPES_RANKING, GHGS_RANKING,
                                         NUMBER_OF_BINS_RANKING, RANK_TYPES,
                                         RANKING_CONFIG, RANKING_COST_METRIC,
                                         UNCERTAINTY_RANKING_GROUPS)
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.solver.ranking import (rank_technology_histogram,
                                      rank_technology_uncertainty_bins)


def make_rankings(pathway_name: str, sensitivity: str, sector: str, products: list):
    """Create the ranking for the three types of technology switches"""

    importer = IntermediateDataImporter(
        pathway_name=pathway_name,
        sensitivity=sensitivity,
        sector=sector,
        products=products,
    )

    # Create ranking using the histogram methodology for every rank type
    df_ranking = importer.get_technologies_to_rank()
    for rank_type in RANK_TYPES:
        if BIN_METHODOLOGY == "histogram":
            df_rank = rank_technology_histogram(
                df_ranking=df_ranking,
                rank_type=rank_type,
                pathway_name=pathway_name,
                cost_metric=RANKING_COST_METRIC,
                n_bins=NUMBER_OF_BINS_RANKING,
                ranking_config=RANKING_CONFIG[rank_type][pathway_name],
                emission_scopes_ranking=EMISSION_SCOPES_RANKING,
                ghgs_ranking=GHGS_RANKING,
            )
        if BIN_METHODOLOGY == "uncertainty":
            df_rank = rank_technology_uncertainty_bins(
                df_ranking=df_ranking,
                rank_type=rank_type,
                pathway_name=pathway_name,
                cost_metric=RANKING_COST_METRIC,
                cost_metric_relative_uncertainty=COST_METRIC_RELATIVE_UNCERTAINTY,
                ranking_config=RANKING_CONFIG[rank_type][pathway_name],
                emission_scopes_ranking=EMISSION_SCOPES_RANKING,
                ghgs_ranking=GHGS_RANKING,
                ranking_groups=UNCERTAINTY_RANKING_GROUPS,
            )

        # Save ranking table as csv
        importer.export_data(
            df=df_rank,
            filename=f"{rank_type}_rank.csv",
            export_dir=f"ranking",
            index=False,
        )

"""Create ranking of technology switches (decommission, brownfield, greenfield)."""

from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory
from mppshared.solver.ranking import rank_technology_uncertainty_bins
from aluminium.config_aluminium import (
    PRODUCTS,
    RANK_TYPES,
    RANKING_COST_METRIC,
)


def make_rankings(
    pathway: str,
    sensitivity: str,
    sector: str,
    carbon_cost_trajectory: CarbonCostTrajectory,
):
    """Create the ranking for the three types of technology switches"""

    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=PRODUCTS,
        carbon_cost_trajectory=carbon_cost_trajectory,
    )

    # Create ranking using the histogram methodology for every rank type
    df_ranking = importer.get_technologies_to_rank()
    for rank_type in RANK_TYPES:
        df_rank = rank_technology_uncertainty_bins(
            df_ranking=df_ranking,
            rank_type=rank_type,
            pathway=pathway,
            sector=sector,
            cost_metric=RANKING_COST_METRIC,
        )

        # Save ranking table as csv
        importer.export_data(
            df=df_rank,
            filename=f"{rank_type}_rank.csv",
            export_dir=f"ranking",
            index=False,
        )

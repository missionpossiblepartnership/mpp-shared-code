""" Logic for technology transitions of type brownfield rebuild and brownfield renovation."""

import pandas as pd
from mppshared.config import LOG_LEVEL
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def apply_start_years_brownfield_transitions(
    df_rank: pd.DataFrame,
    pathway: SimulationPathway,
    year: int,
    brownfield_renovation_start_year: int,
    brownfield_rebuild_start_year: int,
):
    if pathway.pathway_name in ["fa", "lc"]:

        if year < brownfield_renovation_start_year:
            df_rank = df_rank.loc[df_rank["switch_type"] != "brownfield_renovation"]

        if year < brownfield_rebuild_start_year:
            df_rank = df_rank.loc[df_rank["switch_type"] != "brownfield_newbuild"]

    return df_rank


def apply_brownfield_filters_ammonia(
    df_rank: pd.DataFrame,
    pathway: SimulationPathway,
    year: int,
    ranking_cost_metric: str,
    cost_metric_decrease_brownfield: float,
) -> pd.DataFrame:
    """For ammonia, the BAU and LC pathways are driven by minimum cost. Hence, brownfield transitions only happen
    when they decrease LCOX. For the FA pathway, this is not the case."""

    if pathway.pathway_name == "fa":
        return df_rank

    cost_metric = ranking_cost_metric

    # Get LCOX of origin technologies for retrofit
    df_greenfield = pathway.get_ranking(year=year, rank_type="greenfield")
    df_lcox = df_greenfield.loc[df_greenfield["technology_origin"] == "New-build"]
    df_lcox = df_lcox[
        [
            "product",
            "region",
            "technology_destination",
            "year",
            cost_metric,
        ]
    ]

    df_destination_techs = df_lcox.rename(
        {cost_metric: f"{cost_metric}_destination"}, axis=1
    )

    df_origin_techs = df_lcox.rename(
        {
            "technology_destination": "technology_origin",
            cost_metric: f"{cost_metric}_origin",
        },
        axis=1,
    )

    # Add to ranking table and filter out brownfield transitions which would not decrease LCOX "substantially"
    df_rank = df_rank.merge(
        df_origin_techs,
        on=["product", "region", "technology_origin", "year"],
        how="left",
    ).fillna(0)

    df_rank = df_rank.merge(
        df_destination_techs,
        on=["product", "region", "technology_destination", "year"],
        how="left",
    ).fillna(0)

    _filter = df_rank[f"{cost_metric}_destination"] < df_rank[
        f"{cost_metric}_origin"
    ].apply(lambda x: x * (1 - cost_metric_decrease_brownfield))
    df_rank = df_rank.loc[_filter]

    return df_rank

import pandas as pd
import numpy as np
from pathlib import Path

from mppshared.solver.ranking import rank_technology_histogram, rank_technology_uncertainty_bins


def test_rank_technology_histogram_greenfield():
    df_ranking = pd.read_csv("tests/test_data/technologies_to_rank.csv")
    df_rank = rank_technology_histogram(
        df_ranking=df_ranking,
        rank_type="greenfield",
        pathway_name="bau",
        cost_metric="tco",
        n_bins=50,
        ranking_config={"cost": 1.0, "emissions": 0.0},
        emission_scopes_ranking=["scope1", "scope2"],
        ghgs_ranking=["co2"],
    )
    assert df_rank["rank"].min() == 1.0

    # assert technology_origin and technology_destination for the minimum rank is the same as the one with the lowest
    #   value in the tco column
    assert (
        df_rank[df_rank["rank"] == df_rank["rank"].min()][
            "technology_destination"
        ].values[0]
        == df_rank[df_rank["tco"] == df_rank["tco"].min()][
            "technology_destination"
        ].values[0]
    )


def test_rank_technology_histogram_brownfield():
    df_ranking = pd.read_csv("tests/test_data/technologies_to_rank.csv")
    df_rank = rank_technology_histogram(
        df_ranking=df_ranking,
        rank_type="brownfield",
        pathway_name="bau",
        cost_metric="tco",
        n_bins=50,
        ranking_config={"cost": 1.0, "emissions": 0.0},
        emission_scopes_ranking=["scope1", "scope2"],
        ghgs_ranking=["co2"],
    )
    assert df_rank["rank"].min() == 1.0

    assert (
        df_rank[df_rank["rank"] == df_rank["rank"].min()][
            "technology_destination"
        ].values[0]
        == df_rank[df_rank["tco"] == df_rank["tco"].min()][
            "technology_destination"
        ].values[0]
    )


def test_rank_technology_histogram_decommission():
    df_ranking = pd.read_csv("tests/test_data/technologies_to_rank.csv")
    df_rank = rank_technology_histogram(
        df_ranking=df_ranking,
        rank_type="decommission",
        pathway_name="bau",
        cost_metric="tco",
        n_bins=50,
        ranking_config={"cost": 1.0, "emissions": 0.0},
        emission_scopes_ranking=["scope1", "scope2"],
        ghgs_ranking=["co2"],
    )

    assert (
        df_rank[df_rank["rank"] == df_rank["rank"].min()]["technology_origin"].values[0]
        == df_rank[df_rank["tco"] == df_rank["tco"].min()]["technology_origin"].values[
            0
        ]
    )


def test_rank_technology_uncertainty():
    df_ranking = pd.read_csv("tests/test_data/technologies_to_rank.csv")

    rank_types = ["greenfield", "decommission", "brownfield"]
    ranking_groups = ["year"]
    cost_metric = "tco"

    for rank_type in rank_types:
        df_rank = rank_technology_uncertainty_bins(
            df_ranking=df_ranking,
            rank_type=rank_type,
            pathway_name="bau",
            cost_metric=cost_metric,
            cost_metric_relative_uncertainty=0.1,
            ranking_config={"cost": 1.0, "emissions": 0.0},
            emission_scopes_ranking=["scope1", "scope2"],
            ghgs_ranking=["co2"],
            ranking_groups=ranking_groups,
        )

        # test whether the max TCO value of rank i is smaller than the min TCO value of rank i+1
        df_rank.groupby(ranking_groups).apply(
            lambda x: _uncertainty_group_test(df_group=x, cost_metric=cost_metric)
        )


def _uncertainty_group_test(df_group: pd.DataFrame, cost_metric: str):
    # test whether the max TCO value of rank i is smaller than the min TCO value of rank i+1
    df_group_min = df_group.groupby(by=["rank"], sort=True).min()
    df_group_max = df_group.groupby(by=["rank"], sort=True).max()
    check = np.where(
        df_group_max[cost_metric].shift() <= df_group_min[cost_metric],
        True,
        False
    )
    check = np.delete(check, 0)
    assert np.all(check)

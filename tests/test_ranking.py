import pandas as pd

from mppshared.solver.ranking import rank_technology_histogram


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

    # assert technology_origin and technology_destination for the minimum rank is the same as the one with the lowest value in the tco column
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

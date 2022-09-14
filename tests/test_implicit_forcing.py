import pandas as pd

from mppshared.solver.implicit_forcing import (
    add_technology_classification_to_switching_table,
    apply_technology_availability_constraint,
    apply_technology_moratorium,
)


def test_add_technology_classification_to_switching_table():
    df_switching_table = pd.read_csv("tests/test_data/technology_transitions.csv")
    df_technology_characteristics = pd.read_csv(
        "tests/test_data/technology_characteristics.csv"
    )
    df_technologies = add_technology_classification_to_switching_table(
        df_switching_table, df_technology_characteristics
    )
    assert "technology_classification" in df_technologies.columns


def test_apply_technology_availability_constraint():
    df_switching_table = pd.read_csv("tests/test_data/technology_transitions.csv")
    df_technology_characteristics = pd.read_csv(
        "tests/test_data/technology_characteristics.csv"
    )
    df_technologies = apply_technology_availability_constraint(
        df_switching_table, df_technology_characteristics, start_year=2020
    )
    assert (
        df_technologies[
            df_technologies["technology_destination"] == "Inert Anode + Grid"
        ]["year"].min()
        == 2030
    )
    assert (
        len(
            df_technologies[
                df_technologies["technology_origin"] == "Inert Anode + Grid"
            ]
        )
        == 0
    )


def test_apply_technology_moratorium():
    df_switching_table = pd.read_csv("tests/test_data/technology_transitions.csv")
    df_technology_characteristics = pd.read_csv(
        "tests/test_data/technology_characteristics.csv"
    )
    df_technologies = apply_technology_moratorium(
        df_switching_table,
        df_technology_characteristics,
        moratorium_year=2030,
        transitional_period_years=10,
    )
    df_technologies = add_technology_classification_to_switching_table(
        df_technologies, df_technology_characteristics)

    assert (
        df_technologies[df_technologies["technology_classification"] == "initial"][
            "year"
        ].max()
        <= 2030
    )
    assert (
        df_technologies[df_technologies["technology_classification"] == "transition"][
            "year"
        ].min()
        == 2020
    )
    assert (
        df_technologies[df_technologies["technology_classification"] == "transition"][
            "year"
        ].max()
        <= 2040
    )

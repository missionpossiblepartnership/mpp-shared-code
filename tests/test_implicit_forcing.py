import pandas as pd

from mppshared.solver.implicit_forcing import \
    add_technology_classification_to_switching_table


def test_add_technology_classification_to_switching_table():
    df_switching_table = pd.read_csv("tests/test_data/technology_transitions.csv")
    df_technology_characteristics = pd.read_csv(
        "tests/test_data/technology_characteristics.csv"
    )
    df_technologies = add_technology_classification_to_switching_table(
        df_switching_table, df_technology_characteristics
    )
    assert "technology_classification" in df_technologies.columns

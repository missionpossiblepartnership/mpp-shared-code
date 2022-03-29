import pandas as pd

from mppshared.models.plant import Plant


def update_availability_from_plant(
    df_availability: pd.DataFrame, plant: Plant, year: int
):
    """
    Update availabilities based on a plant that is added or removed

    Args:
        df_availability: Availabilities data
        plant: The plant in consideration
        year: Year the plant is added or removed

    Returns:
        The updated availability data
    """

    return None


def test_func():
    pass

import pandas as pd

from mppshared.models.asset import Asset


def update_availability_from_asset(
    df_availability: pd.DataFrame, asset: Asset, year: int
):
    """
    Update availabilities based on a asset that is added or removed

    Args:
        df_availability: Availabilities data
        asset: The asset in consideration
        year: Year the asset is added or removed

    Returns:
        The updated availability data
    """

    return None


def test_func():
    pass

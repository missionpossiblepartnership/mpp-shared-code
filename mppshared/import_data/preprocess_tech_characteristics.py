"""Compiles the technology characteristics required for technology ranking"""

import pandas as pd

from mppshared.config import (IDX_TECH_CHARACTERISTICS, LOG_LEVEL,
                              TECH_CLASSIFICATIONS)
from mppshared.utility.log_utility import get_logger

# Create logger
logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def get_tech_characteristics(
    df_tech_classification: pd.DataFrame,
    df_trl_current: pd.DataFrame,
    df_expected_maturity: pd.DataFrame,
    df_lifetime: pd.DataFrame,
    df_wacc: pd.DataFrame,
) -> pd.DataFrame:
    """

    Args:
        df_tech_classification ():
        df_trl_current ():
        df_expected_maturity ():
        df_lifetime ():
        df_wacc ():

    Returns:

    """

    # prepare data
    df_tech_classification = _prepare_tech_classification_data(
        df=df_tech_classification, column_name="technology_classification"
    )
    df_trl_current = _prepare_tech_classification_data(
        df=df_trl_current, column_name="trl_current"
    )
    df_expected_maturity = _prepare_tech_classification_data(
        df=df_expected_maturity, column_name="expected_maturity"
    )
    df_lifetime = _prepare_tech_classification_data(
        df=df_lifetime, column_name="technology_lifetime"
    )
    df_wacc = _prepare_tech_classification_data(df=df_wacc, column_name="wacc")

    # concat
    df_tech_characteristics = pd.concat(
        [
            df_tech_classification,
            df_trl_current,
            df_expected_maturity,
            df_lifetime,
            df_wacc,
        ],
        axis=1,
    )

    return df_tech_characteristics


"""private functions"""


def _prepare_tech_classification_data(
    df: pd.DataFrame, column_name: str
) -> pd.DataFrame:
    df = (
        df.reset_index()[IDX_TECH_CHARACTERISTICS + ["value"]]
        .set_index(IDX_TECH_CHARACTERISTICS)
        .sort_index()
    )
    if column_name == "technology_classification":
        df.replace(
            to_replace={v: k for k, v in TECH_CLASSIFICATIONS.items()}, inplace=True
        )
    df.rename(columns={"value": column_name}, inplace=True)

    return df

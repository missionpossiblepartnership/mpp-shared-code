"""Tests for Utility folder"""

from mppshared.utils.dataframe_utility import move_cols_to_front

import pandas as pd

def test_move_cols_to_front():
    test_df = pd.DataFrame([(1, 2, 3), (4, 5, 6)], columns=["A", "B", "C"])
    test_df_mod = move_cols_to_front(test_df, ['C'])
    assert test_df_mod == ['C', 'A', 'B']
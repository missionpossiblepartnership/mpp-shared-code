""" Class to track technology transitions of assets."""

from typing import Literal, Optional

import pandas as pd

from mppshared.models.plant import Asset


class TransitionRegistry:
    def __init__(self):
        self.transitions = []

    def add(
        self,
        year: int,
        transition_type: Literal[
            "decommission", "brownfield_renovation", "brownfield_newbuild", "newbuild"
        ],
        origin: Optional[Asset] = None,
        destination: Optional[Asset] = None,
    ):
        transition = {
            "year": year,
            "transition_type": transition_type,
            "region": getattr(origin, "region", None) or destination.region,
            "product": getattr(origin, "product", None) or destination.product,
            "technology_origin": getattr(origin, "technology", None),
            "type_of_tech_origin": getattr(origin, "type_of_tech", None),
            "technology_destination": getattr(destination, "technology", None),
            "type_of_tech_destination": getattr(destination, "type_of_tech", None),
        }

        self.transitions.append(transition)

    def to_dataframe(self):
        return pd.DataFrame(self.transitions)

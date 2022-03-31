""" Enforce constraints in the yearly optimization of technology switches."""

from pandera import Bool
import numpy as np

from mppshared.models.plant import Asset, AssetStack
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.config import REGIONAL_PRODUCTION_SHARE


def check_constraints(
    pathway: SimulationPathway, stack: AssetStack, product: str, year: int
) -> Bool:
    """Check all constraints for a given asset stack.

    Args:
        pathway: contains data on demand and resource availability
        stack: stack of assets for which constraints are to be checked
        product
        year: required for resource availabilities

    Returns:
        Returns True if no constraint hurt
    """
    # TODO: improve runtime by not applying all constraints to every agent logic

    # TODO: Check regional production constraint
    constraints_not_hurt = check_constraint_regional_production(
        pathway=pathway, stack=stack, product=product, year=year
    )

    # TODO: Check technology ramp-up constraint

    # TODO: Check resource availability constraint

    #! Placeholder
    return constraints_not_hurt


def check_constraint_regional_production(
    pathway: SimulationPathway, stack: AssetStack, product: str, year: int
) -> Bool:
    """Check constraints that regional production is at least a specified share of regional demand

    Args:
        stack (_type_): _description_
        product (_type_): _description_
    """
    # Get regional production and demand
    df_regional_production = stack.get_regional_production(product)
    df_demand = pathway.get_regional_demand(product, year)

    # Check for every region in DataFrame
    df = df_regional_production.merge(df_demand, on=["region"], how="left")
    df["share_regional_production"] = df["region"].map(REGIONAL_PRODUCTION_SHARE)

    # Compare regional production with required demand share up to specified number of significant figures
    sf = 2
    df["check"] = np.round(df["annual_production"], sf) >= np.round(
        df["demand"] * df["share_regional_production"], sf
    )

    # The constraint is hurt if any region does not meet its required regional production share
    if False in df["check"]:
        return False

    return True

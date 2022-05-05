""" Enforce constraints in the yearly optimization of technology switches."""
from copy import deepcopy

import numpy as np
import pandas as pd
from pandera import Bool
from pyparsing import col

from mppshared.config import LOG_LEVEL, REGIONAL_PRODUCTION_SHARES
from mppshared.models.asset import Asset, AssetStack
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def check_constraints(
    pathway: SimulationPathway,
    stack: AssetStack,
    product: str,
    year: int,
    transition_type: str,
) -> dict:
    """Check all constraints for a given asset stack and return dictionary of Booleans with constraint types as keys.

    Args:
        pathway: contains data on demand and resource availability
        stack: stack of assets for which constraints are to be checked
        product
        year: required for resource availabilities
        transition_type: either of "decommission", "brownfield", "greenfield"

    Returns:
        Returns True if no constraint hurt
    """
    # TODO: Map constraint application to the three transition types

    # Check regional production constraint
    # TODO: is this still needed for any of the transition types?
    # regional_constraint = check_constraint_regional_production(
    #     pathway=pathway, stack=stack, product=product, year=year
    # )

    # If pathway not bau, then check for constraints, else return true
    if pathway.pathway != "bau":
        # Check constraint for annual emissions limit from carbon budget
        emissions_constraint = check_annual_carbon_budget_constraint(
            pathway=pathway, stack=stack, product=product, year=year
        )
        # Check technology ramp-up constraint
        rampup_constraint = check_technology_rampup_constraint(
            pathway=pathway, stack=stack, year=year
        )

        # TODO: Check resource availability constraint
        return {
            "emissions_constraint": emissions_constraint,
            "rampup_constraint": rampup_constraint
        }
    else:
        return {
            "emissions_constraint": True,
            "rampup_constraint": True
        }

def check_technology_rampup_constraint(
    pathway: SimulationPathway, stack: AssetStack, year: int
) -> Bool:
    """Check if the technology rampup between the stacked passed and the previous year's stack complies with the technology ramp-up trajectory

    Args:
        pathway: contains the stack of the previous year
        stack: new stack for which the ramp-up constraint is to be checked
        year: year corresponding to the stack passed
    """
    # Get asset numbers of new and old stack for each technology
    df_old_stack = pathway.stacks[year].aggregate_stack(aggregation_vars=["technology"])[["number_of_assets"]].rename({"number_of_assets": "number_old"}, axis=1)
    df_new_stack = stack.aggregate_stack(aggregation_vars=["technology"])[["number_of_assets"]].rename({"number_of_assets": "number_new"}, axis=1)

    # Create DataFrame for rampup comparison
    df_rampup = df_old_stack.join(df_new_stack, how="outer").fillna(0)
    df_rampup["proposed_asset_additions"] = df_rampup["number_new"] - df_rampup["number_old"]
    for technology in df_rampup.index:
        rampup_constraint = pathway.technology_rampup[technology]
        if rampup_constraint:
            df_rampup.loc[technology, "maximum_asset_additions"] = rampup_constraint.df_rampup.loc[year, "maximum_asset_additions"]
        else:
            df_rampup.loc[technology, "maximum_asset_additions"] = None

    df_rampup["check"] = (df_rampup["proposed_asset_additions"] <= df_rampup["maximum_asset_additions"]) | (df_rampup["maximum_asset_additions"].isna())
    
    if df_rampup["check"].all():
        return True
    
    technology_affected = list(df_rampup[df_rampup["check"]==False].index)
    logger.debug(f"Technology ramp-up constraint hurt for {technology_affected}.")
    return False

def check_constraint_regional_production(
    pathway: SimulationPathway, stack: AssetStack, product: str, year: int
) -> Bool:
    """Check constraints that regional production is at least a specified share of regional demand

    Args:
        stack (_type_): _description_
        product (_type_): _description_
    """
    df = get_regional_production_constraint_table(pathway, stack, product, year)
    # The constraint is hurt if any region does not meet its required regional production share
    if df["check"].all():
        return True

    return False


def get_regional_production_constraint_table(
    pathway: SimulationPathway, stack: AssetStack, product: str, year: int
) -> pd.DataFrame:
    """Get table that compares regional production with regional demand for a given year"""
    # Get regional production and demand
    df_regional_production = stack.get_regional_production_volume(product)
    df_demand = pathway.get_regional_demand(product, year)

    # Check for every region in DataFrame
    df = df_regional_production.merge(df_demand, on=["region"], how="left")
    df["share_regional_production"] = df["region"].map(
        REGIONAL_PRODUCTION_SHARES[pathway.sector]
    )

    # Add required regional production column
    df["annual_production_volume_minimum"] = (
        df["demand"] * df["share_regional_production"]
    )

    # Compare regional production with required demand share up to specified number of significant figures
    sf = 2
    df["check"] = np.round(df["annual_production_volume"], sf) >= np.round(
        df["annual_production_volume_minimum"], sf
    )
    return df


def check_annual_carbon_budget_constraint(
    pathway: SimulationPathway, stack: AssetStack, product: str, year: int
) -> Bool:
    """Check if the stack exceeds the Carbon Budget defined in the pathway for the given product and year"""
    # Create deep copy of pathway with updated tentative stack
    temp_pathway = deepcopy(pathway)
    temp_pathway.update_stack(year=year, stack=stack)

    # TODO: improve hacky workaround
    dict_stack_emissions = temp_pathway.calculate_emissions_stack(
        year=year, product=product
    )
    co2_scope1_2 = (
        dict_stack_emissions["co2_scope1"] + dict_stack_emissions["co2_scope2"]
    ) / 1e3  # Gt CO2

    # TODO: integrate sector
    limit = temp_pathway.carbon_budget.get_annual_emissions_limit(
        year, temp_pathway.sector
    )
    if np.round(co2_scope1_2, 2) <= np.round(limit, 2):
        return True

    return False

""" Enforce constraints in the yearly optimization of technology switches."""

import sys
from typing import Union

import numpy as np
import pandas as pd
from ammonia.config_ammonia import END_YEAR

from mppshared.config import (
    AMMONIA_PER_AMMONIUM_NITRATE,
    AMMONIA_PER_UREA,
    H2_PER_AMMONIA,
    HYDRO_TECHNOLOGY_BAN,
    LOG_LEVEL,
)
from mppshared.models.asset import AssetStack
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.utility.utils import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def check_constraints(
    pathway: SimulationPathway,
    stack: AssetStack,
    year: int,
    transition_type: str,
    product: str,
    constraints_to_apply: list = None,
    region: str = None,
) -> dict:
    """Check all constraints for a given asset stack and return dictionary of Booleans with constraint types as keys.

    Args:
        pathway:
        stack: stack of assets for which constraints are to be checked
        product:
        year: required for resource availabilities
        transition_type: either of "decommission", "brownfield", "greenfield"
        constraints_to_apply: a list of constraints to apply can be passed. If it is None, it will be set to
            pathway.constraints_to_apply
        region: some constraints allow a regional and global checks to improve runtime. If a region is provided, these
            constraints will only check the constraint fulfilment in that region

    Returns:
        Returns a dictionary with all constraints that have been checked and respective values (True if constraint
            satisfied, False if constraint hurt)
    """

    funcs_constraints = {
        "emissions_constraint": check_annual_carbon_budget_constraint,
        "rampup_constraint": check_technology_rampup_constraint,
        "regional_constraint": check_constraint_regional_production,
        "demand_share_constraint": check_global_demand_share_constraint,
        "electrolysis_capacity_addition_constraint": check_electrolysis_capacity_addition_constraint,
        "co2_storage_constraint": check_co2_storage_constraint,
        "alternative_fuel_constraint": check_alternative_fuel_constraint,
    }

    if constraints_to_apply is None:
        constraints_to_apply = pathway.constraints_to_apply

    constraints_checked = {}
    if constraints_to_apply:
        # if the list is not empty
        for constraint in constraints_to_apply:
            if constraint == "emissions_constraint":
                emissions_constraint, flag_residual = funcs_constraints[constraint]( # type: ignore
                    pathway=pathway,
                    stack=stack,
                    year=year,
                    transition_type=transition_type,
                )
                constraints_checked[constraint] = emissions_constraint
                constraints_checked["flag_residual"] = flag_residual
            elif region is not None and constraint in ["co2_storage_constraint", "alternative_fuel_constraint"]:
                constraints_checked[constraint] = funcs_constraints[constraint]( # type: ignore
                    pathway=pathway,
                    stack=stack,
                    product=product,
                    year=year,
                    transition_type=transition_type,
                    region=region,
                )
            else:
                constraints_checked[constraint] = funcs_constraints[constraint]( # type: ignore
                    pathway=pathway,
                    stack=stack,
                    product=product,
                    year=year,
                    transition_type=transition_type,
                )
    else:
        logger.info(f"Pathway {pathway.pathway_name} has no constraints to apply")

    return constraints_checked


def check_technology_rampup_constraint(
    pathway: SimulationPathway,
    stack: AssetStack,
    product: str,
    year: int,
    transition_type: str,
) -> bool:
    """Check if the technology rampup between the stack passed and the previous year's stack complies with the
        technology ramp-up trajectory

    Args:
        pathway: contains the stack of the previous year
        stack: new stack for which the ramp-up constraint is to be checked
        product: dummy for this function; standardisation required as constraint functions are called from dictionary
        year: year corresponding to the stack passed
        transition_type:
    """
    logger.info(
        f"{year}: Checking ramp-up constraint (transition type: {transition_type})"
    )
    # Get asset numbers of new and old stack for each technology
    if product == "Clinker":
        year_old_stack = year - 1
    else:
        year_old_stack = year
    df_old_stack = (
        pathway.stacks[year_old_stack]
        .aggregate_stack(aggregation_vars=["technology"])[["number_of_assets"]]
        .rename({"number_of_assets": "number_old"}, axis=1)
    )
    df_new_stack = stack.aggregate_stack(aggregation_vars=["technology"])[
        ["number_of_assets"]
    ].rename({"number_of_assets": "number_new"}, axis=1)

    # Create DataFrame for rampup comparison
    df_rampup = (
        df_old_stack.join(df_new_stack, how="outer")
        .fillna(0)
        .astype(dtype={"number_old": int, "number_new": int})
    )
    df_rampup["proposed_asset_additions"] = (
        df_rampup["number_new"] - df_rampup["number_old"]
    )
    for technology in df_rampup.index:
        rampup_constraint = pathway.technology_rampup[technology] # type: ignore
        if rampup_constraint:
            df_rampup.loc[
                technology, "maximum_asset_additions"
            ] = rampup_constraint.df_rampup.loc[year, "maximum_asset_additions"]
        else:
            df_rampup.loc[technology, "maximum_asset_additions"] = np.nan

    df_rampup["check"] = (
        df_rampup["proposed_asset_additions"] <= df_rampup["maximum_asset_additions"]
    ) | (df_rampup["maximum_asset_additions"].isna())

    if df_rampup["check"].all():
        logger.info("Technology ramp-up constraint satisfied")
        return True
    else:
        technology_affected = list(df_rampup[~df_rampup["check"]].index)
        logger.info(f"Technology ramp-up constraint hurt for {technology_affected}.")
        return False


def check_constraint_regional_production(
    pathway: SimulationPathway,
    stack: AssetStack,
    product: str,
    year: int,
    transition_type: str,
) -> bool:
    """Check constraints that regional production is at least a specified share of regional demand

    Args:
        pathway
        stack (_type_): _description_
        product (_type_): _description_
        year
        transition_type: dummy for this function; standardisation required as constraint functions are called from
            dictionary
    """
    logger.info(
        f"{year}: Checking regional production constraint (transition type: {transition_type})"
    )
    df = get_regional_production_constraint_table(pathway, stack, product, year)
    # The constraint is hurt if any region does not meet its required regional production share
    if df["check"].all():
        logger.info("Regional production constraint satisfied")
        return True
    else:
        logger.info("Regional production constraint hurt")
        return False


def get_regional_production_constraint_table(
    pathway: SimulationPathway,
    stack: AssetStack,
    product: str,
    year: int,
) -> pd.DataFrame:
    """Get table that compares regional production with regional demand for a given year"""
    # Get regional production and demand
    df_regional_production = stack.get_regional_production_volume(product)
    df_demand = pathway.get_regional_demand(product=product, year=year)

    # Check for every region in DataFrame
    df = df_regional_production.merge(df_demand, on=["region"], how="left")
    df["share_regional_production"] = df["region"].map(
        pathway.regional_production_shares
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
    pathway: SimulationPathway,
    stack: AssetStack,
    year: int,
    transition_type: str,
) -> tuple[bool, bool]:
    """Check if the stack exceeds the Carbon Budget defined in the pathway for the given product and year

    Args:
        pathway ():
        stack ():
        year ():
        transition_type ():

    Returns:

    """

    logger.info(
        f"{year}: Checking annual carbon budget constraint (transition type: {transition_type})"
    )

    # After a sector-specific year, all end-state newbuild capacity has to fulfill the 2050 emissions limit with a stack
    #   composed of only end-state technologies
    # todo: change this such that YEAR_2050_EMISSIONS_CONSTRAINT can be set to None
    if (transition_type == "greenfield") & (
        year >= pathway.year_2050_emissions_constraint # type: ignore
    ):
        limit = pathway.carbon_budget.get_annual_emissions_limit(pathway.end_year) # type: ignore

        dict_stack_emissions = stack.calculate_emissions_stack(
            year=year,
            df_emissions=pathway.emissions,
            technology_classification="end-state",
        )
        flag_residual = True

    # In other cases, the limit is equivalent to that year's emission limit
    else:
        limit = pathway.carbon_budget.get_annual_emissions_limit(year=year) # type: ignore

        dict_stack_emissions = stack.calculate_emissions_stack(
            year=year, df_emissions=pathway.emissions, technology_classification=None
        )
        flag_residual = False

    # Compare scope 1 and 2 CO2 emissions to the allowed limit in that year
    co2_scope1_2 = (
        dict_stack_emissions["co2_scope1"] + dict_stack_emissions["co2_scope2"]
    ) / 1e3
    # Unit co2_scope1_2: [Gt CO2]

    if np.round(co2_scope1_2, 2) <= np.round(limit, 2):
        logger.info(f"Annual carbon budget constraint is satisfied")
        return True, flag_residual
    logger.info(f"Annual carbon budget constraint is hurt")
    return False, flag_residual


def hydro_constraints(df_ranking: pd.DataFrame, sector: str) -> pd.DataFrame:
    # TODO: refactor to not check for sector
    # check if the product is aluminium:
    if HYDRO_TECHNOLOGY_BAN[sector]:
        logger.debug("Removing new builds Hydro")
        return df_ranking[
            ~(
                df_ranking["technology_origin"].str.contains("New-build")
                & df_ranking["technology_destination"].str.contains("Hydro")
            )
        ]
    else:
        return df_ranking


def apply_greenfield_filters_chemicals(
    df_rank: pd.DataFrame, pathway: SimulationPathway, year: int, product: str
) -> pd.DataFrame:
    """For chemicals, new ammonia demand can only be supplied by transition and end-state technologies,
    while new urea and ammonium nitrate demand can also be supplied by initial technologies"""
    if product == "Ammonia":
        filter = df_rank["technology_classification"] == "initial"
        df_rank = df_rank.loc[~filter]
        return df_rank
    return df_rank


def check_global_demand_share_constraint(
    pathway: SimulationPathway,
    stack: AssetStack,
    year: int,
    transition_type: str,
    product: str,
) -> bool:
    """
    Check for specified technologies whether they fulfill the constraint of supplying a maximum share of global demand

    Args:
        pathway ():
        stack ():
        year ():
        transition_type ():

    Returns:

    """

    df_stack = stack.aggregate_stack(
        aggregation_vars=["product", "technology"]
    ).reset_index()
    constraint = True

    for technology in pathway.technologies_maximum_global_demand_share:  # type: ignore

        # Calculate annual production volume based on CUF upper threshold
        df = (
            df_stack.loc[df_stack["technology"] == technology]
            .groupby("product", as_index=False)
            .sum()
        )
        df["annual_production_volume"] = (
            df["annual_production_capacity"] * pathway.cuf_upper_threshold
        )

        # Add global demand and corresponding constraint
        df["demand"] = df["product"].apply(
            lambda x: pathway.get_demand(product=x, year=year, region="Global")
        )
        df["demand_maximum"] = pathway.maximum_global_demand_share[year] * df["demand"]  # type: ignore

        # Compare
        df["check"] = np.where(
            df["annual_production_volume"] <= df["demand_maximum"], True, False
        )

        if df["check"].all():
            constraint = constraint & True

        else:
            logger.debug(f"Maximum demand share hurt for technology {technology}.")
            return False

    return constraint


def check_electrolysis_capacity_addition_constraint(
    pathway: SimulationPathway,
    stack: AssetStack,
    year: int,
    transition_type: str,
    product: str,
) -> bool:
    """Check if the annual addition of electrolysis capacity fulfills the constraint

    Args:
        pathway ():
        stack ():
        year ():
        transition_type ():

    Returns:

    """

    # Get annual production capacities per technology of current and tentative new stack
    df_old_stack = (
        pathway.stacks[year]
        .aggregate_stack(
            aggregation_vars=["product", "region", "technology"],
        )
        .reset_index()
    )
    df_new_stack = stack.aggregate_stack(
        aggregation_vars=["product", "region", "technology"]
    ).reset_index()

    # Calculate required electrolysis capacity
    df_old_stack = convert_production_volume_to_electrolysis_capacity(
        df_old_stack.loc[df_old_stack["technology"].str.contains("Electrolyser")],
        year,
        pathway,
    )
    df_new_stack = convert_production_volume_to_electrolysis_capacity(
        df_new_stack.loc[df_new_stack["technology"].str.contains("Electrolyser")],
        year,
        pathway,
    )

    # Sum to total required electrolysis capacity
    capacity_old_stack = df_old_stack.sum()["electrolysis_capacity"]
    capacity_new_stack = df_new_stack.sum()["electrolysis_capacity"]

    # Compare to electrolysis capacity addition constraint in that year
    capacity_addition = capacity_new_stack - capacity_old_stack
    df_constr = (
        pathway.importer.get_electrolysis_capacity_addition_constraint().set_index(
            "year"
        )
    )
    capacity_addition_constraint = df_constr.loc[year, "value"]

    if capacity_addition <= capacity_addition_constraint:
        return True

    logger.debug("Annual electrolysis capacity addition constraint hurt.")
    return False


def convert_production_volume_to_electrolysis_capacity(
    df_stack: pd.DataFrame, year: int, pathway: SimulationPathway
) -> float:
    """Convert a production volume in Mt into required electrolysis capacity in MW."""

    # Get capacity factors, efficiencies and hydrogen proportions
    electrolyser_cfs = pathway.importer.get_electrolyser_cfs().rename(
        columns={"technology_destination": "technology"}
    )
    electrolyser_effs = pathway.importer.get_electrolyser_efficiencies().rename(
        columns={"technology_destination": "technology"}
    )
    electrolyser_props = pathway.importer.get_electrolyser_proportions().rename(
        columns={"technology_destination": "technology"}
    )

    # Add year to stack DataFrame
    df_stack = df_stack.copy()
    df_stack.loc[:, "year"] = year

    # Merge with stack DataFrame
    merge_vars1 = ["product", "region", "technology", "year"]
    merge_vars2 = ["product", "region", "year"]

    df_stack = df_stack.merge(
        electrolyser_cfs[merge_vars1 + ["electrolyser_capacity_factor"]],
        on=merge_vars1,
        how="left",
    )
    df_stack = df_stack.merge(
        electrolyser_effs[merge_vars2 + ["electrolyser_efficiency"]],
        on=merge_vars2,
        how="left",
    )
    df_stack = df_stack.merge(
        electrolyser_props[merge_vars1 + ["electrolyser_hydrogen_proportion"]],
        on=merge_vars1,
        how="left",
    )
    # Production volume needs to be based on standard CUF (user upper threshold)
    df_stack["annual_production_volume"] = (
        df_stack["annual_production_capacity"] * pathway.cuf_upper_threshold
    )

    # Electrolysis capacity  = Ammonia production * Proportion of H2 produced via electrolysis * Ratio of ammonia to H2 * Electrolyser efficiency / (365 * 24 * CUF)
    df_stack["electrolysis_capacity"] = (
        df_stack["annual_production_volume"]  # MtNH3
        * df_stack["electrolyser_hydrogen_proportion"]
        * df_stack["electrolyser_efficiency"]  # kWh/tH2
        / (365 * 24 * df_stack["electrolyser_capacity_factor"])
    )

    def choose_ratio(row: pd.Series) -> float:
        if row["product"] == "Ammonia":
            ratio = H2_PER_AMMONIA  # tH2/tNH3
        elif row["product"] == "Urea":
            ratio = H2_PER_AMMONIA * AMMONIA_PER_UREA
        elif row["product"] == "Ammonium nitrate":
            ratio = H2_PER_AMMONIA * AMMONIA_PER_AMMONIUM_NITRATE
        return ratio

    # Electrolysis capacity in GW
    df_stack["electrolysis_capacity"] = df_stack.apply(
        lambda row: row["electrolysis_capacity"] * choose_ratio(row), axis=1
    )

    return df_stack


def check_co2_storage_constraint(
    pathway: SimulationPathway,
    stack: AssetStack,
    product: str,
    year: int,
    transition_type: str,
    region: str = None,
    return_dict: bool = False,
):
    """Check if the constraint on CO2 storage (globally or regionally) is met

    Args:
        pathway ():
        stack ():
        product ():
        year ():
        transition_type ():
        region (): If a region is provided, only checks constraint fulfilment in this region. Only valid for
            pathway.co2_storage_constraint_type == "total_cumulative" (will not have an impact for other types)
        return_dict (): Returns dict with constraint fulfilment for every region if True. Else returns only True or
            False, depending on overall constraint fulfilment

    Returns:

    """

    if not return_dict:
        logger.info(
            f"{year}: Checking CO2 storage constraint  (transition type: {transition_type})"
        )

    # Get constraint value
    if product == "Clinker":
        df_co2_storage = pathway.co2_storage_constraint
        limit = df_co2_storage.loc[df_co2_storage["year"] == year, :]
    else:
        df_co2_storage = pathway.co2_storage_constraint
        if year < END_YEAR:
            limit_year = year
        else:
            limit_year = END_YEAR

        limit = df_co2_storage.loc[df_co2_storage["year"] == limit_year, "value"].item()

    # Global constraint based on total CO2 storage available in that year
    if pathway.co2_storage_constraint_type == "annual_cumulative":

        # Calculate CO2 captured annually by the stack (Mt CO2)
        co2_captured = stack.calculate_co2_captured_stack(
            year=year, df_emissions=pathway.emissions
        )

        # Compare with the limit on annual CO2 storage addition (MtCO2)
        if limit >= co2_captured:
            return True
        else:
            logger.debug("CO2 storage constraint hurt.")
            return False

    # Constraint based on addition of storage capacity for additional captured CO2 in that year
    elif pathway.co2_storage_constraint_type == "annual_addition":
        # Calculate new CO2 captured
        co2_captured_old_stack = pathway.stacks[year].calculate_co2_captured_stack(
            year=year, df_emissions=pathway.emissions
        )

        co2_captured_new_stack = stack.calculate_co2_captured_stack(
            year=year + 1, df_emissions=pathway.emissions
        )

        additional_co2_captured = co2_captured_new_stack - co2_captured_old_stack

        # Compare with the limit on additional storage capacity
        if limit >= additional_co2_captured:
            return True
        else:
            logger.debug("CO2 storage constraint hurt.")
            return False

    # Regional or global constraint based on cumulative volume of CO2 stored over all model years (until current year)
    elif pathway.co2_storage_constraint_type == "total_cumulative":
        # get all years that have already been modelled
        modelled_years = pathway.stacks.keys()

        if region is None:
            # check constraint fulfilment for all regions that have a CO2 storage constraint
            dict_regional_fulfilment = {}
            for region_to_check in limit.region.unique():
                # get the cumulative sum of annually stored CO2 over all modelled years [Mt CO2]
                co2_captured_storage = float(0)
                for year in modelled_years:
                    co2_captured_storage += stack.calculate_co2_captured_stack(
                        year=year,
                        df_emissions=pathway.emissions,
                        region=region_to_check,
                        usage_storage="storage",
                        product=product,
                    )

                limit_region = limit.loc[limit["region"] == region_to_check, "value"].squeeze()

                # add to dict (change sign of co2_captured_storage since captured emissions are provided as negative
                #   values)
                dict_regional_fulfilment[region_to_check] = limit_region >= -co2_captured_storage

                if not return_dict:
                    logger.debug(
                        f"{region_to_check}: {dict_regional_fulfilment[region_to_check]} (limit: {limit_region} Mt CO2, "
                        f"CCS volume: {-co2_captured_storage} Mt CO2)"
                    )

            if return_dict:
                return dict_regional_fulfilment
            else:
                if all(dict_regional_fulfilment.values()):
                    logger.info("CO2 storage constraint satisfied")
                else:
                    logger.info("CO2 storage constraint hurt")
                return all(dict_regional_fulfilment.values())

        else:
            # check constraint fulfilment for one region only
            # get the cumulative sum of annually stored CO2 over all modelled years [Mt CO2]
            co2_captured_storage = float(0)
            for year in modelled_years:
                co2_captured_storage += stack.calculate_co2_captured_stack(
                    year=year,
                    df_emissions=pathway.emissions,
                    region=region,
                    usage_storage="storage",
                    product=product,
                )
            limit_region = limit.loc[limit["region"] == region, "value"].squeeze()

            # check fulfilment (change sign of co2_captured_storage since captured emissions are provided as negative
            #   values)
            regional_fulfilment = limit_region >= -co2_captured_storage
            logger.debug(
                f"{region}: {regional_fulfilment} (limit: {limit_region} Mt CO2, "
                f"CCS volume: {-co2_captured_storage} Mt CO2)"
            )

            if regional_fulfilment:
                logger.info("CO2 storage constraint satisfied")
            else:
                logger.info("CO2 storage constraint hurt")
            return regional_fulfilment

    else:
        sys.exit(
            "Invalid string for config parameter CO2_STORAGE_CONSTRAINT_TYPE provided"
        )


def check_alternative_fuel_constraint(
    pathway: SimulationPathway,
    product: str,
    stack: AssetStack,
    year: int,
    transition_type: str,
    region: str = None,
    return_dict: bool = False,
) -> Union[dict, bool]:
    """

    Args:
        pathway ():
        product ():
        stack ():
        year ():
        transition_type ():
        region (): If a region is provided, only checks constraint fulfilment in this region. Only valid for
            pathway.co2_storage_constraint_type == "total_cumulative" (will not have an impact for other types)
        return_dict ():

    Returns:

    """
    """Check if the constraint on annual alternative fuel capacity (regionally) is fulfilled"""

    if not return_dict:
        logger.info(
            f"{year}: Checking alternative fuel constraint  (transition type: {transition_type})"
        )

    # Get constraint value
    df_af_limit = pathway.alternative_fuel_constraint

    if region is None:
        # check constraint fulfilment for all regions that have a CO2 storage constraint
        dict_regional_fulfilment = {}
        regions = list(df_af_limit["region"].unique())
        for region_to_check in regions:
            limit_region = df_af_limit.loc[
                ((df_af_limit["year"] == year) & (df_af_limit["region"] == region_to_check)),
                "value",
            ].squeeze()

            # calculate natural gas-based production capacity
            af_prod_volume = stack.get_annual_ng_af_production_volume(
                product=product, region=region_to_check, tech_substr="alternative fuels"
            )

            # add to dict
            dict_regional_fulfilment[region_to_check] = limit_region >= af_prod_volume

            if not return_dict:
                logger.debug(
                    f"{region_to_check}: {dict_regional_fulfilment[region_to_check]} (limit: {limit_region}, prod. vol.: {af_prod_volume})"
                )

        if return_dict:
            return dict_regional_fulfilment
        else:
            if all(dict_regional_fulfilment.values()):
                logger.info("Alternative fuel constraint satisfied")
            else:
                logger.info("Alternative fuel constraint hurt")
            return all(dict_regional_fulfilment.values())

    else:
        # check constraint fulfilment for one region only
        limit_region = df_af_limit.loc[
            ((df_af_limit["year"] == year) & (df_af_limit["region"] == region)),
            "value",
        ].squeeze()

        # calculate natural gas-based production capacity
        af_prod_volume = stack.get_annual_ng_af_production_volume(
            product=product, region=region, tech_substr="alternative fuels"     # , aggregate_techs=False
        )

        # add to dict
        regional_fulfilment = limit_region >= af_prod_volume

        if not return_dict:
            logger.debug(
                f"{region}: {regional_fulfilment} (limit: {limit_region}, prod. vol.: {af_prod_volume})"
            )

    if return_dict:
        return regional_fulfilment
    else:
        if regional_fulfilment:
            logger.info("Alternative fuel constraint satisfied")
        else:
            logger.info("Alternative fuel constraint hurt")
        return regional_fulfilment

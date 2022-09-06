"""Calculates all cost metrics required for technology ranking"""

import sys
from itertools import chain
from copy import deepcopy

import numpy as np
import pandas as pd

from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory
from mppshared.config import IDX_TECH_RANKING_COLUMNS, LOG_LEVEL
from mppshared.utility.dataframe_utility import df_dict_to_df
from mppshared.utility.log_utility import get_logger
from mppshared.utility.utils import get_unique_list_values

# Create logger
logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def calculate_tech_transitions(
    importer: IntermediateDataImporter,
    # parameters
    sector: str,
    model_years: np.ndarray,
    products: list,
    model_regions: list,
    compute_lcox: bool,
    cost_classifications: dict,
    map_switch_types_to_capex_type: dict,
    idx_per_input_metric: dict,
    opex_energy_metrics: list,
    opex_materials_metrics: list,
    opex_ccus_emissivity_metrics: list,
    opex_ccus_emissivity_metric_types: list,
    opex_ccus_process_metrics_energy: list,
    opex_ccus_process_metrics_material: list,
    opex_ccus_context_metrics: dict,
    list_technologies: list,
    carbon_cost_scopes: list,
    # data
    df_tech_switches: pd.DataFrame,
    dict_emissivity: dict,
    df_emissions: pd.DataFrame,
    df_capex: pd.DataFrame,
    df_opex: pd.DataFrame,
    df_inputs_material: pd.DataFrame,
    df_inputs_energy: pd.DataFrame,
    df_commodity_prices: pd.DataFrame,
    df_wacc: pd.DataFrame,
    df_capacity_factor: pd.DataFrame,
    df_lifetime: pd.DataFrame,
    df_capture_rate: pd.DataFrame,
    carbon_cost_trajectory: CarbonCostTrajectory,
) -> pd.DataFrame:
    """
    Calculate all cost metrics for each technology switch for use in the technology ranking.
    Calculated variables:
        1) Switch CAPEX
        2) Fixed OPEX
        3) Variable OPEX
        4) LCOX
        5) TCO (not yet implemented)
        6) Marginal cost (not yet implemented)

    Args:
        importer ():
        sector ():
        model_years ():
        products ():
        model_regions ():
        compute_lcox (): function will compute LCOX data if True
        cost_classifications ():
        map_switch_types_to_capex_type
        idx_per_input_metric ():
        opex_energy_metrics ():
        opex_materials_metrics ():
        opex_ccus_emissivity_metrics ():
        opex_ccus_emissivity_metric_types ():
        opex_ccus_process_metrics_energy ():
        opex_ccus_process_metrics_material ():
        opex_ccus_context_metrics ():
        list_technologies (): list of all technologies in the model
        carbon_cost_scopes ():
        df_tech_switches (): df with all feasible tech switches and their switch type
        dict_emissivity (): dict of all emissivity metric types
        df_emissions ():
        df_capex ():
        df_opex ():
        df_inputs_material ():
        df_inputs_energy ():
        df_commodity_prices ():
        df_wacc ():
        df_capacity_factor ():
        df_lifetime ():
        df_capture_rate ():
        carbon_cost_trajectory ():

    Returns:

    """

    logger.info("Calculate CAPEX AND OPEX")

    # CAPEX
    df_switch_capex = _get_switch_capex(
        df_tech_switches=df_tech_switches,
        df_capex=df_capex,
        products=products,
        model_years=model_years,
        model_regions=model_regions,
        map_switch_types_to_capex_type=map_switch_types_to_capex_type,
    )
    # check for negative values
    if any(df_switch_capex["value"] < 0):
        logger.critical("Warning: Negative switch CAPEX values exist!")

    # OPEX fixed
    df_opex_fixed = _get_opex_fixed(df_opex=df_opex)
    # check for negative values
    if any(df_opex_fixed["value"] < 0):
        logger.critical("Warning: Negative OPEX_fixed values exist!")

    # OPEX variable
    if sector == "cement":
        dict_opex_variable = _get_opex_variable(
            dict_emissivity=dict_emissivity,
            df_emissions=df_emissions,
            df_inputs_material=df_inputs_material,
            df_inputs_energy=df_inputs_energy,
            df_commodity_prices=df_commodity_prices,
            df_capture_rate=df_capture_rate,
            carbon_cost_trajectory=carbon_cost_trajectory,
            sector=sector,
            list_technologies=list_technologies,
            cost_classifications=cost_classifications,
            idx_per_input_metric=idx_per_input_metric,
            opex_energy_metrics=opex_energy_metrics,
            opex_materials_metrics=opex_materials_metrics,
            opex_ccus_emissivity_metrics=opex_ccus_emissivity_metrics,
            opex_ccus_emissivity_metric_types=opex_ccus_emissivity_metric_types,
            opex_ccus_process_metrics_energy=opex_ccus_process_metrics_energy,
            opex_ccus_process_metrics_material=opex_ccus_process_metrics_material,
            opex_ccus_context_metrics=opex_ccus_context_metrics,
            carbon_cost_scopes=carbon_cost_scopes,
        )
        # convert dict to df
        df_opex_variable = df_dict_to_df(df_dict=dict_opex_variable)
    else:
        # placeholder
        df_opex_variable = pd.DataFrame()
    # check for negative values
    if (
        (df_opex_variable[[x for x in df_opex_variable.columns if "value" in x]] < 0)
        .any()
        .any()
    ):
        logger.critical("Warning: Negative OPEX_variable values exist!")

    # LCOX
    if compute_lcox:
        logger.info("Calculate LCOX")
        if sector == "cement":
            dict_lcox = _get_lcox(
                df_switch_capex=df_switch_capex,
                df_opex_fixed=df_opex_fixed,
                dict_opex_variable=dict_opex_variable,
                df_wacc=df_wacc,
                df_capacity_factor=df_capacity_factor,
                df_lifetime=df_lifetime,
            )
            for key in dict_lcox.keys():
                dict_lcox[key] = dict_lcox[key][["lcox"]]
                dict_lcox[key].rename(columns={"lcox": "value"}, inplace=True)
            # convert dict to df
            df_lcox = df_dict_to_df(df_dict=dict_lcox)
            # export lcox
            importer.export_data(
                df=df_lcox,
                filename="lcox.csv",
                export_dir="intermediate",
            )
    else:
        try:
            logger.info("Import LCOX")
            df_lcox = importer.get_lcox().set_index(IDX_TECH_RANKING_COLUMNS)
        except FileNotFoundError:
            sys.exit(
                "No LCOX data found. Set config parameter COMPUTE_LCOX to True to generate LCOX data."
            )
    # check for negative values
    if (df_lcox[[x for x in df_lcox.columns if "value" in x]] < 0).any().any():
        logger.critical("Warning: Negative LCOX values exist!")

    # add all outputs to dict
    # todo: add missing dataframes
    dict_cost_metrics = {
        "switch_capex": df_switch_capex,
        "opex_fixed": df_opex_fixed,
        "opex_variable": df_opex_variable,
        "lcox": df_lcox,
        "tco": None,
        "marginal_cost": None,
    }

    # compose technology_transitions dataframe
    df_list = []
    column_name_opex_context = "opex_context"
    for cost_metric in [
        x for x in dict_cost_metrics.keys() if x not in ["opex_fixed", "opex_variable"]
    ]:
        if dict_cost_metrics[cost_metric] is not None:
            if len(list(dict_cost_metrics[cost_metric])) > 1:
                # wide to long by adding opex_context column if there are different, opex_context-dependent cost values
                df_temp = pd.melt(
                    frame=dict_cost_metrics[cost_metric].reset_index(),
                    id_vars=IDX_TECH_RANKING_COLUMNS,
                    value_vars=list(dict_cost_metrics[cost_metric]),
                    var_name=column_name_opex_context,
                    value_name=cost_metric,
                )
                df_temp = df_temp.set_index(keys=IDX_TECH_RANKING_COLUMNS).sort_index()
                df_list.append(df_temp)
            else:
                df_temp = dict_cost_metrics[cost_metric].copy()
                df_temp.rename(columns={list(df_temp)[0]: cost_metric}, inplace=True)
                df_list.append(df_temp)
    df_tech_transitions = pd.concat(df_list, axis=1)
    if column_name_opex_context in list(df_tech_transitions):
        df_tech_transitions = (
            df_tech_transitions.reset_index()
            .set_index(keys=IDX_TECH_RANKING_COLUMNS + [column_name_opex_context])
            .sort_index()
        )

    return df_tech_transitions


# private functions (main)
def _get_switch_capex(
    df_tech_switches: pd.DataFrame,
    df_capex: pd.DataFrame,
    products: list,
    model_years: np.ndarray,
    model_regions: list,
    map_switch_types_to_capex_type: dict,
) -> pd.DataFrame:
    """
    Computes the switch CAPEX for all technology switches, products, years, and regions.

    Args:
        df_tech_switches ():
        df_capex (): Indexed CAPEX dataframe. Unit: [total USD/t production_output]
        products ():
        model_years ():
        map_switch_types_to_capex_type ():

    Returns:
        df_switch_capex (): Unindexed dataframe with switch_capex. Unit: [total USD/t production_output]
    """

    # remove cost_classification
    df_capex = df_capex.reset_index().drop(columns="cost_classification")

    # rename column "metric" to "switch_type" and adjust values
    df_capex.rename(columns={"metric": "switch_type"}, inplace=True)
    df_capex.replace(to_replace=map_switch_types_to_capex_type, inplace=True)

    """decommission"""

    # get slice
    df_decommission = (
        df_capex.copy()
        .loc[df_capex["switch_type"] == "decommission"]
        .reset_index(drop=True)
    )

    # adjust tech origin and destination
    df_decommission.loc[:, "technology_origin"] = df_decommission.loc[
        :, "technology_destination"
    ]
    df_decommission.loc[:, "technology_destination"] = "Decommissioned"

    # filter columns
    df_decommission = df_decommission[IDX_TECH_RANKING_COLUMNS + ["value"]]

    # todo-dev: delete
    df_decommission["value"] = float(0)
    # todo

    """greenfield"""

    # get slice
    df_greenfield = (
        df_capex.copy()
        .loc[df_capex["switch_type"] == "greenfield"]
        .reset_index(drop=True)
    )

    # adjust tech origin and destination
    df_greenfield.loc[:, "technology_origin"] = "New-build"

    # filter columns
    df_greenfield = df_greenfield[IDX_TECH_RANKING_COLUMNS + ["value"]]

    """brownfield"""

    # get slice
    df_brownfield = (
        df_capex.copy()
        .loc[
            df_capex["switch_type"].isin(
                ["brownfield_renovation", "brownfield_rebuild"]
            )
        ]
        .reset_index(drop=True)
    )

    # adjust tech origin and destination
    df_brownfield.loc[:, "technology_origin"] = "Dry kiln reference plant"

    # extend df_tech_switches to all products, model years, and regions
    df_list = []
    for product in products:
        for year in model_years:
            for region in model_regions:
                df_append = df_tech_switches.copy()
                df_append["product"] = product
                df_append["year"] = year
                df_append["region"] = region
                df_list.append(df_append)
    df_tech_switches = pd.concat(df_list)

    # reset index and order columns
    df_tech_switches = df_tech_switches.reset_index()[IDX_TECH_RANKING_COLUMNS]

    # get switch CAPEX values: rebuild (assumption: rebuild CAPEX equals greenfield CAPEX)
    df_brownfield_rebuild = (
        df_tech_switches.copy()
        .loc[df_tech_switches["switch_type"] == "brownfield_rebuild", :]
        .reset_index(drop=True)
    )
    df_brownfield_rebuild = df_brownfield_rebuild.merge(
        right=df_greenfield,
        how="left",
        on=["product", "year", "region", "technology_destination"],
        suffixes=("", "_right"),
    )
    df_brownfield_rebuild = df_brownfield_rebuild[IDX_TECH_RANKING_COLUMNS + ["value"]]

    # get switch CAPEX values: renovation
    df_brownfield_renovation = (
        df_tech_switches.copy()
        .loc[df_tech_switches["switch_type"] == "brownfield_renovation", :]
        .reset_index(drop=True)
    )
    # get origin CAPEX value
    df_brownfield_renovation = df_brownfield_renovation.merge(
        right=df_brownfield,
        how="left",
        left_on=["product", "year", "region", "technology_origin", "switch_type"],
        right_on=["product", "year", "region", "technology_destination", "switch_type"],
        suffixes=("", "_right"),
    )
    df_brownfield_renovation = df_brownfield_renovation[
        IDX_TECH_RANKING_COLUMNS + ["value"]
    ]
    df_brownfield_renovation.rename(columns={"value": "value_origin"}, inplace=True)
    # get destination CAPEX value
    df_brownfield_renovation = df_brownfield_renovation.merge(
        right=df_brownfield,
        how="left",
        left_on=["product", "year", "region", "technology_destination", "switch_type"],
        right_on=["product", "year", "region", "technology_destination", "switch_type"],
        suffixes=("", "_right"),
    )
    df_brownfield_renovation = df_brownfield_renovation[
        IDX_TECH_RANKING_COLUMNS + ["value_origin", "value"]
    ]
    df_brownfield_renovation.rename(
        columns={"value": "value_destination"}, inplace=True
    )
    # compute switch CAPEX value
    df_brownfield_renovation["value"] = (
        df_brownfield_renovation["value_destination"]
        - df_brownfield_renovation["value_origin"]
    )
    # brownfield switch CAPEX for switches from one CCU/S tech to another CCU/S tech are set to the renovation CAPEX of
    #   the destination tech
    df_brownfield_renovation.loc[
        (
            df_brownfield_renovation["technology_origin"].str.contains(
                "post combustion"
            )
            & (
                df_brownfield_renovation["technology_destination"].str.contains(
                    "oxyfuel"
                )
                ^ df_brownfield_renovation["technology_destination"].str.contains(
                    "direct separation"
                )
            )
        ),
        "value",
    ] = df_brownfield_renovation["value_destination"]
    df_brownfield_renovation.loc[
        (
            df_brownfield_renovation["technology_origin"].str.contains("oxyfuel")
            & (
                df_brownfield_renovation["technology_destination"].str.contains(
                    "post combustion"
                )
                ^ df_brownfield_renovation["technology_destination"].str.contains(
                    "direct separation"
                )
            )
        ),
        "value",
    ] = df_brownfield_renovation["value_destination"]
    df_brownfield_renovation.loc[
        (
            df_brownfield_renovation["technology_origin"].str.contains(
                "direct separation"
            )
            & (
                df_brownfield_renovation["technology_destination"].str.contains(
                    "post combustion"
                )
                ^ df_brownfield_renovation["technology_destination"].str.contains(
                    "oxyfuel"
                )
            )
        ),
        "value",
    ] = df_brownfield_renovation["value_destination"]

    # filter relevent columns
    df_brownfield_renovation = df_brownfield_renovation[
        IDX_TECH_RANKING_COLUMNS + ["value"]
    ]

    """concatenate"""

    df_switch_capex = pd.concat(
        [
            df_greenfield,
            df_brownfield_rebuild,
            df_brownfield_renovation,
            df_decommission,
        ]
    ).reset_index(drop=True)
    df_switch_capex = df_switch_capex.set_index(IDX_TECH_RANKING_COLUMNS).sort_index()

    return df_switch_capex


def _get_opex_fixed(
    df_opex: pd.DataFrame,
) -> pd.DataFrame:
    """
    Computes the fixed OPEX data per product, year, region, and technology_destination.

    Args:
        df_opex ():

    Returns:
        df_opex_fixed (): Unit: [USD / t product_output]
    """

    idx_opex = [
        x
        for x in IDX_TECH_RANKING_COLUMNS
        if x not in ["technology_origin", "switch_type"]
    ]

    # sum different fixed OPEX components
    df_opex_fixed = df_opex.copy().groupby(idx_opex).sum().sort_index()

    return df_opex_fixed


def _get_opex_variable(
    # data
    dict_emissivity: dict,
    df_emissions: pd.DataFrame,
    df_inputs_material: pd.DataFrame,
    df_inputs_energy: pd.DataFrame,
    df_commodity_prices: pd.DataFrame,
    df_capture_rate: pd.DataFrame,
    carbon_cost_trajectory: CarbonCostTrajectory,
    # parameters
    sector: str,
    list_technologies: list,
    cost_classifications: dict,
    idx_per_input_metric: dict,
    opex_energy_metrics: list,
    opex_materials_metrics: list,
    opex_ccus_process_metrics_energy: list,
    opex_ccus_process_metrics_material: list,
    opex_ccus_emissivity_metric_types: list,
    opex_ccus_emissivity_metrics: list,
    opex_ccus_context_metrics: dict,
    carbon_cost_scopes: list,
) -> dict:
    """
    Computes the variable OPEX data per product, year, region, and technology_destination, considering the different
        CCU/CCS contexts.

    Args:
        dict_emissivity (): Unit: [t GHG / GJ]
        df_emissions (): Unit: [t GHG / t production_output]
        df_inputs_material (): Unit: [t input_material / t product_output]
        df_inputs_energy (): Unit: [GJ / t product_output]
        df_commodity_prices (): Units: [USD / resource_consumption]
        df_capture_rate (): Unit: [$]
        carbon_cost_trajectory ():
        sector ():
        list_technologies ():
        idx_per_input_metric ():
        opex_energy_metrics ():
        opex_materials_metrics ():
        opex_ccus_process_metrics_energy ():
        opex_ccus_process_metrics_material ():
        opex_ccus_emissivity_metric_types ():
        opex_ccus_emissivity_metrics ():
        carbon_cost_scopes ():

    Returns:
        dict_opex_variable (dict): Dictionary with cost_classifications as keys and respective variable OPEX dataframes
            as values. Unit: [USD / t product_output]
    """

    """index lists"""

    idx_opex = [
        x
        for x in IDX_TECH_RANKING_COLUMNS
        if x not in ["technology_origin", "switch_type"]
    ]
    # ov: short for opex_variable
    idx_ov_commodity_prices = [
        x for x in idx_per_input_metric["commodity_prices"] if x != "unit"
    ]

    """materials OPEX"""

    # filter all relevant input materials
    idx_ov_inputs_material = [
        x for x in idx_per_input_metric["inputs_material"] if x != "unit"
    ]
    df_ov_inputs_material = _filter_input_metrics(
        df=df_inputs_material.reset_index(), list_metrics=opex_materials_metrics
    )
    df_ov_inputs_material = (
        df_ov_inputs_material[idx_ov_inputs_material + ["value"]]
        .set_index(idx_ov_inputs_material)
        .sort_index()
    )
    # unit df_ov_inputs_material: [GJ / t product_output]

    # filter all relevant commodity material prices
    df_ov_commodity_prices_material = _filter_input_metrics(
        df=df_commodity_prices.reset_index(), list_metrics=opex_materials_metrics
    )
    df_ov_commodity_prices_material = (
        df_ov_commodity_prices_material[idx_ov_commodity_prices + ["value"]]
        .set_index(idx_ov_commodity_prices)
        .sort_index()
    )
    # unit df_ov_commodity_prices_material: [USD / GJ]

    # compute materials OPEX
    df_ov_materials = df_ov_inputs_material.mul(df_ov_commodity_prices_material)
    df_ov_materials = df_ov_materials.groupby(idx_opex).sum()
    df_ov_materials = df_ov_materials.reorder_levels(idx_opex)
    # unit df_ov_materials: [USD / t product_output]

    """energy OPEX"""

    # filter all relevant energy inputs
    idx_ov_inputs_energy = [
        x for x in idx_per_input_metric["inputs_energy"] if x != "unit"
    ]
    df_ov_inputs_energy = _filter_input_metrics(
        df=df_inputs_energy.reset_index(), list_metrics=opex_energy_metrics
    )
    df_ov_inputs_energy = (
        df_ov_inputs_energy[idx_ov_inputs_energy + ["value"]]
        .set_index(idx_ov_inputs_energy)
        .sort_index()
    )
    # unit df_ov_inputs_energy: [GJ / t product_output]

    # filter all relevant commodity energy prices
    df_ov_commodity_prices_energy = _filter_input_metrics(
        df=df_commodity_prices.reset_index(), list_metrics=opex_energy_metrics
    )
    df_ov_commodity_prices_energy = (
        df_ov_commodity_prices_energy[idx_ov_commodity_prices + ["value"]]
        .set_index(idx_ov_commodity_prices)
        .sort_index()
    )
    # unit df_ov_commodity_prices_energy: [USD / GJ]

    # compute energy OPEX
    df_ov_energy = df_ov_inputs_energy.mul(df_ov_commodity_prices_energy)
    df_ov_energy = df_ov_energy.groupby(idx_opex).sum()
    df_ov_energy = df_ov_energy.reorder_levels(idx_opex)
    # unit df_ov_energy: [USD / t product_output]

    """CCU/S OPEX (considering the different contexts)"""

    # CCU/S: CC process cost (energy)
    # get unique keys as list from opex_ccus_process_metrics
    dict_ccus_process_cost = get_unique_list_values(
        list(chain(*[list(x.keys()) for x in opex_ccus_process_metrics_energy]))
    )
    # generate dict from the unique list
    dict_ccus_process_cost = dict.fromkeys(dict_ccus_process_cost)
    # fill dict with respective dataframes
    dict_ccus_process_cost["inputs_energy"] = df_inputs_energy
    dict_ccus_process_cost["commodity_prices"] = df_commodity_prices
    # compute all cost components of CC process cost
    df_ov_ccus_process_energy = _opex_get_ccus_process_cost(
        input_data=dict_ccus_process_cost,
        idx_opex=idx_opex,
        idx_per_input_metric=idx_per_input_metric,
        opex_ccus_process_metrics=opex_ccus_process_metrics_energy,
    )
    # df_ov_ccus_process unit: [USD / t Clk]

    # CCU/S: CC process cost (material)
    # get unique keys as list from opex_ccus_process_metrics
    dict_ccus_process_cost = get_unique_list_values(
        list(chain(*[list(x.keys()) for x in opex_ccus_process_metrics_material]))
    )
    # generate dict from the unique list
    dict_ccus_process_cost = dict.fromkeys(dict_ccus_process_cost)
    # fill dict with respective dataframes
    dict_ccus_process_cost["inputs_material"] = df_inputs_material
    dict_ccus_process_cost["commodity_prices"] = df_commodity_prices
    # compute all cost components of CC process cost
    df_ov_ccus_process_material = _opex_get_ccus_process_cost(
        input_data=dict_ccus_process_cost,
        idx_opex=idx_opex,
        idx_per_input_metric=idx_per_input_metric,
        opex_ccus_process_metrics=opex_ccus_process_metrics_material,
    )
    # df_ov_ccus_process unit: [USD / t CO2]

    # CCU/S: get context-dependent cost components as dict
    dict_ov_ccus_context = _opex_get_ccus_context_cost_components(
        df_commodity_prices=df_commodity_prices,
        list_technologies=list_technologies,
        idx_opex=idx_opex,
        cost_classifications=cost_classifications,
        opex_ccus_context_metrics=opex_ccus_context_metrics,
    )
    # unit dict_ov_ccus_context: [USD / t CO2]

    # CCU/S: captured emissivity
    # concatenate all emissivity metric types in one df
    df_list_ov_ccus_emissivity = []
    for emissivity_metric_type in opex_ccus_emissivity_metric_types:
        df_temp = _filter_input_metrics(
            df=dict_emissivity[emissivity_metric_type].reset_index(),
            list_metrics=opex_ccus_emissivity_metrics,
        )
        # filter by scope and drop scope column
        df_temp = df_temp.loc[df_temp["scope"] == "1", :]
        df_temp.drop(columns="scope", inplace=True)
        # concat
        df_list_ov_ccus_emissivity.append(df_temp)
    df_ov_ccus_emissivity = pd.concat(df_list_ov_ccus_emissivity).reset_index(drop=True)
    # get captured emissivity (i.e., capture rate x emissivity)
    if sector == "cement":
        df_ov_ccus_captured_emissivity = _get_ccus_captured_emissivity_cement(
            df_ov_ccus_emissivity=df_ov_ccus_emissivity,
            df_inputs_energy=df_inputs_energy,
            df_capture_rate=df_capture_rate,
            idx_opex=idx_opex,
        )
        # unit df_ov_ccus_captured_emissivity: [t CO2 / t Clk]
    else:
        # avoid reference before assignment warning
        df_ov_ccus_captured_emissivity = pd.DataFrame()

    # compute CCU/S OPEX in [USD / t product_output]
    dict_ov_ccus = dict.fromkeys(dict_ov_ccus_context)
    for cost_classification in dict_ov_ccus.keys():
        # CCU/S OPEX process (material) + CCU/S OPEX non-process
        dict_ov_ccus[cost_classification] = dict_ov_ccus_context[
            cost_classification
        ].add(df_ov_ccus_process_material)
        # unit dict_ov_ccus: [USD / t CO2]
        # * captured emissivity
        dict_ov_ccus[cost_classification] = dict_ov_ccus[cost_classification].mul(
            df_ov_ccus_captured_emissivity
        )
        # unit dict_ov_ccus: [USD / t production_output]
        # + CCU/S OPEX process (energy)
        dict_ov_ccus[cost_classification] = dict_ov_ccus[cost_classification].add(
            df_ov_ccus_process_energy
        )
        # unit dict_ov_ccus: [USD / t production_output]

    """carbon cost"""

    if carbon_cost_trajectory is not None:
        df_ov_carbon_cost = (
            deepcopy(carbon_cost_trajectory.df_carbon_cost)
            .set_index("year")
            .sort_index()
        )
        df_ov_carbon_cost.rename(
            columns={list(df_ov_carbon_cost)[0]: "value"}, inplace=True
        )
        df_emissions = (
            df_emissions[[f"co2_{x}" for x in carbon_cost_scopes]]
            .sum(axis=1)
            .to_frame()
        )
        df_emissions.rename(columns={list(df_emissions)[0]: "value"}, inplace=True)
        df_ov_carbon_cost = df_ov_carbon_cost.mul(df_emissions).sort_index()
        # unit df_ov_carbon_cost: [USD / t product_output]

    """aggregate"""

    dict_opex_variable = dict.fromkeys(dict_ov_ccus)
    for cost_classification in dict_opex_variable.keys():
        # CCU/S OPEX + materials OPEX
        dict_opex_variable[cost_classification] = dict_ov_ccus[cost_classification].add(
            df_ov_materials
        )
        # + energy OPEX
        dict_opex_variable[cost_classification] = dict_opex_variable[
            cost_classification
        ].add(df_ov_energy)
        if carbon_cost_trajectory is not None:
            # + carbon cost
            dict_opex_variable[cost_classification] = dict_opex_variable[
                cost_classification
            ].add(df_ov_carbon_cost)
        # unit dict_opex_variable: [USD / t product_output]
        dict_opex_variable[cost_classification].sort_index(inplace=True)

    return dict_opex_variable


def _get_lcox(
    df_switch_capex: pd.DataFrame,
    df_opex_fixed: pd.DataFrame,
    dict_opex_variable: dict,
    df_wacc: pd.DataFrame,
    df_capacity_factor: pd.DataFrame,
    df_lifetime: pd.DataFrame,
) -> dict:

    # get WACC
    df_wacc = _filter_input_metrics(
        df=df_wacc.reset_index(), list_metrics=["Real WACC"]
    )
    idx_wacc = [
        x
        for x in IDX_TECH_RANKING_COLUMNS
        if x not in ["technology_origin", "switch_type"]
    ]
    df_wacc = df_wacc[idx_wacc + ["value"]].set_index(idx_wacc).sort_index()
    # unit df_wacc: [%]

    # get capacity factor
    df_capacity_factor = _filter_input_metrics(
        df=df_capacity_factor.reset_index(), list_metrics=["Capacity factor"]
    )
    idx_capacity_factor = [
        x
        for x in IDX_TECH_RANKING_COLUMNS
        if x not in ["technology_origin", "switch_type"]
    ]
    df_capacity_factor = (
        df_capacity_factor[idx_capacity_factor + ["value"]]
        .set_index(idx_capacity_factor)
        .sort_index()
    )
    # unit df_capacity_factor: [%]

    # get lifetimes
    df_lifetime = _filter_input_metrics(
        df=df_lifetime.reset_index(), list_metrics=["Lifetime"]
    )
    idx_lifetime = [
        x
        for x in IDX_TECH_RANKING_COLUMNS
        if x not in ["technology_origin", "switch_type"]
    ]
    df_lifetime = (
        df_lifetime[idx_lifetime + ["value"]].set_index(idx_lifetime).sort_index()
    )
    # unit df_lifetime: [years]

    """LCOX"""

    # merge CAPEX and OPEX
    dict_capex_opex = dict.fromkeys(dict_opex_variable)
    for key in dict_capex_opex.keys():
        # merge fixed and variable OPEX
        dict_capex_opex[key] = pd.merge(
            left=df_opex_fixed,
            right=dict_opex_variable[key],
            how="left",
            left_index=True,
            right_index=True,
            suffixes=("_opex_fixed", "_opex_variable"),
        )
        dict_capex_opex[key].rename(
            columns={
                "value_opex_fixed": "opex_fixed",
                "value_opex_variable": "opex_variable",
            },
            inplace=True,
        )
        # merge OPEX and CAPEX
        dict_capex_opex[key] = pd.merge(
            left=df_switch_capex,
            right=dict_capex_opex[key],
            how="left",
            left_index=True,
            right_index=True,
        )
        dict_capex_opex[key].rename(columns={"value": "switch_capex"}, inplace=True)
        # merge with WACC, capacity factors, and lifetime
        dict_capex_opex[key] = pd.merge(
            left=dict_capex_opex[key],
            right=df_wacc,
            how="left",
            left_index=True,
            right_index=True,
        )
        dict_capex_opex[key].rename(columns={"value": "wacc"}, inplace=True)
        dict_capex_opex[key] = pd.merge(
            left=dict_capex_opex[key],
            right=df_capacity_factor,
            how="left",
            left_index=True,
            right_index=True,
        )
        dict_capex_opex[key].rename(columns={"value": "capacity_factor"}, inplace=True)
        dict_capex_opex[key] = pd.merge(
            left=dict_capex_opex[key],
            right=df_lifetime,
            how="left",
            left_index=True,
            right_index=True,
        )
        dict_capex_opex[key].rename(columns={"value": "lifetime"}, inplace=True)
        # reorder levels and sort
        dict_capex_opex[key] = (
            dict_capex_opex[key].reorder_levels(IDX_TECH_RANKING_COLUMNS).sort_index()
        )

        # create copy of dict_capex_opex[key] that copies the values of the last model year into the future to make sure
        #   that all present values for all lifetimes can be computed
        df_capex_opex_extended = _get_extended_df_capex_opex(
            df_capex_opex=dict_capex_opex[key]
        )

        # compute LCOX
        logger.info(f'Calculate LCOX for context "{key}"')
        dict_capex_opex[key]["lcox"] = np.nan
        dict_capex_opex[key].apply(
            func=(lambda x: _compute_lcox(row=x, df=df_capex_opex_extended)),
            axis=1,
        )

    return dict_capex_opex


# private functions (helper)
def _filter_input_metrics(df: pd.DataFrame, list_metrics: list) -> pd.DataFrame:
    """
    Takes a dataframe with a "metric" column as well as a list of strings with the required metrics as inputs and
        outputs a dataframe that only includes the required metrics.

    Args:
        df (): unindexed df with "metric" column
        list_metrics ():

    Returns:
        df (): Filtered with only the those metrics in list_metrics
    """
    df_list = []
    df = df.copy()
    for metric in list_metrics:
        df_append = df.loc[df["metric"] == metric, :]
        df_list.append(df_append)

    df = pd.concat(df_list).reset_index(drop=True)

    return df


def _opex_get_ccus_context_cost_components(
    # data
    df_commodity_prices: pd.DataFrame,
    # parameters
    cost_classifications: dict,
    list_technologies: list,
    idx_opex: list,
    opex_ccus_context_metrics: dict,
) -> dict:
    """
    Composes and calculates CCU/S OPEX for all combinations of context-dependent cost_classifications

    Args:
        df_commodity_prices ():
        cost_classifications ():
        list_technologies ():
        idx_opex ():
        opex_ccus_context_metrics ():

    Returns:
        dict_ccus_context_cost (): dict with all combinations of cost_classifications as keys and the respective
            dataframes as values. Unit: [USD / t CO2]
    """

    df_ccus_context_cost = df_commodity_prices.copy().reset_index()
    # rename cost_classification and metric values
    df_ccus_context_cost.replace(
        to_replace={v: k for k, v in cost_classifications.items()}, inplace=True
    )
    df_ccus_context_cost.replace(
        to_replace={v: k for k, v in opex_ccus_context_metrics.items()}, inplace=True
    )
    # filter relevant input metrics
    df_ccus_context_cost = _filter_input_metrics(
        df=df_ccus_context_cost, list_metrics=list(opex_ccus_context_metrics.keys())
    )
    df_ccus_context_cost.drop(columns="unit", inplace=True)
    # unit df_ccus_context_cost: [USD / t CO2]

    # split into all different cost classifications
    dict_ccus_context_cost = dict.fromkeys(opex_ccus_context_metrics)
    for key in dict_ccus_context_cost:
        # split into different context dimensions
        dict_ccus_context_cost[key] = _filter_input_metrics(
            df=df_ccus_context_cost,
            list_metrics=[key],
        )
        # rename cost_classification and value columns
        dict_ccus_context_cost[key].rename(
            columns={"cost_classification": f"{key}_cost_classification"}, inplace=True
        )
        dict_ccus_context_cost[key].rename(
            columns={"value": f"{key}_value"}, inplace=True
        )
        # drop metric column
        dict_ccus_context_cost[key].drop(columns="metric", inplace=True)

    # merge all dataframes in dict_ccus_context_cost
    # first merge transport and storage (they have the same context, i.e., always the same cost_classification)
    df_ccus_context_cost = pd.merge(
        left=dict_ccus_context_cost["transport"],
        right=dict_ccus_context_cost["storage"],
        how="left",
        left_on=["product", "region", "year", "transport_cost_classification"],
        right_on=["product", "region", "year", "storage_cost_classification"],
    ).drop(columns="storage_cost_classification")
    df_ccus_context_cost.rename(
        columns={"transport_cost_classification": "ts_cost_classification"},
        inplace=True,
    )
    df_ccus_context_cost = pd.merge(
        left=df_ccus_context_cost,
        right=dict_ccus_context_cost["carbon_price"],
        how="left",
        on=["product", "region", "year"],
    )
    df_ccus_context_cost.rename(
        columns={"carbon_price_cost_classification": "cp_cost_classification"},
        inplace=True,
    )

    # extend to all technologies (by adding technology_destination column)
    df_list = []
    for tech in list_technologies:
        df_temp = df_ccus_context_cost.copy()
        if "storage" in tech:
            # CCS OPEX includes transport and storage
            df_temp["value"] = df_temp["transport_value"] + df_temp["storage_value"]
        elif "usage" in tech:
            # CCU OPEX includes transport and the negative carbon price
            df_temp["value"] = (
                df_temp["transport_value"] - df_temp["carbon_price_value"]
            )
        else:
            # CCU/S OPEX is 0 if no storage nor usage in tech
            df_temp["value"] = float(0)
        df_temp.drop(
            columns=[f"{x}_value" for x in opex_ccus_context_metrics.keys()],
            inplace=True,
        )
        # set tech
        df_temp["technology_destination"] = tech
        # append
        df_list.append(df_temp)
    # concat
    df_ccus_context_cost = pd.concat(df_list)

    # generate dataframes for all cost classifications
    # merge both cost classification columns to one
    df_ccus_context_cost["cost_classification"] = df_ccus_context_cost[
        "ts_cost_classification"
    ].str.cat(others=df_ccus_context_cost["cp_cost_classification"], sep="_")
    df_ccus_context_cost.drop(
        columns=["ts_cost_classification", "cp_cost_classification"], inplace=True
    )
    # get unique values in cost_classification column
    cost_classifications = list(np.unique(df_ccus_context_cost["cost_classification"]))

    dict_ccus_context_cost = {k: None for k in cost_classifications}
    for cost_classification in cost_classifications:
        df_temp = df_ccus_context_cost.copy().loc[
            df_ccus_context_cost["cost_classification"] == cost_classification
        ]
        # filter relevant columns
        df_temp = df_temp[idx_opex + ["value"]]
        # set index
        df_temp = df_temp.reset_index(drop=True).set_index(idx_opex)
        # attach to dict
        dict_ccus_context_cost[cost_classification] = df_temp

    # unit dict_ccus_context_cost: [USD / t CO2]
    return dict_ccus_context_cost


def _opex_get_ccus_process_cost(
    input_data: dict,
    idx_opex: list,
    idx_per_input_metric: dict,
    opex_ccus_process_metrics: list,
) -> pd.DataFrame:
    """
    Takes as input a dictionary that includes all the dataframes that are required for computing the CCU/S process cost.
        The function then calculates all cost components, by multiplying two dataframes with each other based on the
        OPEX_CCUS_PROCESS_METRICS dictionary in config.py.

    Args:
        input_data (dict): dictionary that includes all the dataframes that are required for computing the CCU/S process
            capture cost
        idx_opex ():
        idx_per_input_metric ():
        opex_ccus_process_metrics (list): List of all CCU/S process cost components. Every item in the list is a dict
            with two keys: the name of the dataframe with prices (must be part of input_data) and a price metric as
            value as well as the corresponding name of the energy or material intensity dataframe (must be part of
            input_data) and an energy/material intensity metric as value.

    Returns:
        df_ov_ccus_process (): Unit: [USD / t production_output] or [USD / t CO2]
    """

    df_list = []
    for ccus_process_cost_component in opex_ccus_process_metrics:

        df_subcomponent_list = []
        for subcomponent in ccus_process_cost_component.keys():
            # filter all relevant energy inputs
            idx_subcomponent = [
                x
                for x in idx_per_input_metric[subcomponent]
                if x not in ["cost_classification", "metric", "unit"]
            ]
            df_subcomponent = _filter_input_metrics(
                df=input_data[subcomponent].reset_index(),
                list_metrics=ccus_process_cost_component[subcomponent],
            )
            df_subcomponent = (
                df_subcomponent[idx_subcomponent + ["value"]]
                .set_index(idx_subcomponent)
                .sort_index()
            )
            # append to df_subcomponent_list
            df_subcomponent_list.append(df_subcomponent)
        # multiply
        df_capture_cost_component = df_subcomponent_list[0].mul(df_subcomponent_list[1])
        # append to df_list
        df_list.append(df_capture_cost_component)

    # concat and groupby
    df_ov_ccus_process = pd.concat(df_list).reorder_levels(idx_opex)
    df_ov_ccus_process = df_ov_ccus_process.groupby(
        list(df_ov_ccus_process.index.names)
    ).sum()
    df_ov_ccus_process = df_ov_ccus_process.sort_index()

    return df_ov_ccus_process


def _get_ccus_captured_emissivity_cement(
    df_ov_ccus_emissivity: pd.DataFrame,
    df_inputs_energy: pd.DataFrame,
    df_capture_rate: pd.DataFrame,
    idx_opex: list,
) -> pd.DataFrame:
    """

    Args:
        df_ov_ccus_emissivity (): Emissivity of metric types in opex_ccus_emissivity_metric_types and corresponding
            metrics in opex_ccus_emissivity_metrics. Unit: mixed ([t CO2 / t Clk] & [t CO2 / t GJ])
        df_inputs_energy (): Unit: [GJ / t Clk]
        df_capture_rate (): Unit: [%]
        idx_opex ():

    Returns:
        df_ov_ccus_captured_emissivity: Unit: [t CO2 / t product_output]
    """

    """emissions with unit [t CO2 / GJ]"""

    # split into emissions of unit [t CO2 / GJ] and other emissions
    df_ov_ccus_emissivity_gj = (
        df_ov_ccus_emissivity.copy()
        .loc[df_ov_ccus_emissivity["emissivity_type"] != "Process", :]
        .reset_index(drop=True)
    )

    # filter relevant columns and set index
    idx_ov_ccus_emissivity = ["product", "region", "year", "metric"]
    df_ov_ccus_emissivity_gj = df_ov_ccus_emissivity_gj[
        idx_ov_ccus_emissivity + ["value"]
    ]
    df_ov_ccus_emissivity_gj = df_ov_ccus_emissivity_gj.set_index(
        idx_ov_ccus_emissivity
    ).sort_index()
    # unit df_ov_ccus_emissivity_gj: [t CO2 / GJ]

    # get required energy inputs
    idx_inputs_energy = [
        "product",
        "region",
        "year",
        "technology_destination",
        "metric",
    ]
    df_inputs_energy = df_inputs_energy.reset_index()[idx_inputs_energy + ["value"]]
    df_inputs_energy = df_inputs_energy.set_index(idx_inputs_energy).sort_index()
    # unit df_inputs_energy: [GJ / t Clk]

    # get capture rate
    idx_capture_rate = [
        "product",
        "region",
        "year",
        "technology_destination",
    ]
    df_capture_rate = df_capture_rate.reset_index()[idx_capture_rate + ["value"]]
    df_capture_rate = df_capture_rate.set_index(idx_capture_rate).sort_index()

    # multiply to get [t CO2 / t Clk]
    df_ov_ccus_captured_emissivity_gj = df_ov_ccus_emissivity_gj.mul(df_inputs_energy)
    # unit df_ov_ccus_captured_emissivity_gj: [t CO2 / t Clk]

    # multiply with capture rate
    df_ov_ccus_captured_emissivity_gj = df_ov_ccus_captured_emissivity_gj.mul(
        df_capture_rate
    )
    # unit df_ov_ccus_captured_emissivity_gj: [t CO2 / t Clk]

    df_ov_ccus_captured_emissivity_gj = (
        df_ov_ccus_captured_emissivity_gj.reorder_levels(idx_inputs_energy).dropna(
            how="all"
        )
    )

    """emissions with unit [t CO2 / t Clk]"""

    df_ov_ccus_emissivity_tclk = (
        df_ov_ccus_emissivity.copy()
        .loc[df_ov_ccus_emissivity["emissivity_type"] == "Process", :]
        .reset_index(drop=True)
    )

    # filter relevant columns and set index
    df_ov_ccus_emissivity_tclk = df_ov_ccus_emissivity_tclk[
        idx_ov_ccus_emissivity + ["value"]
    ]
    df_ov_ccus_emissivity_tclk = df_ov_ccus_emissivity_tclk.set_index(
        idx_ov_ccus_emissivity
    ).sort_index()
    # unit df_ov_ccus_emissivity_tclk: [t CO2 / t Clk]

    # multiply with capture rate
    df_ov_ccus_captured_emissivity_tclk = df_ov_ccus_emissivity_tclk.mul(
        df_capture_rate
    )
    # unit df_ov_ccus_captured_emissivity_tclk: [t CO2 / t Clk]

    df_ov_ccus_captured_emissivity_tclk = (
        df_ov_ccus_captured_emissivity_tclk.reorder_levels(idx_inputs_energy).dropna(
            how="all"
        )
    )

    """concat and aggregate"""

    df_ov_ccus_captured_emissivity = pd.concat(
        [df_ov_ccus_captured_emissivity_gj, df_ov_ccus_captured_emissivity_tclk]
    )
    df_ov_ccus_captured_emissivity = df_ov_ccus_captured_emissivity.groupby(
        idx_opex
    ).sum()
    # unit df_ov_ccus_captured_emissivity: [t CO2 / t Clk]

    return df_ov_ccus_captured_emissivity


def _get_extended_df_capex_opex(df_capex_opex: pd.DataFrame) -> pd.DataFrame:
    df_capex_opex_extended = df_capex_opex.copy()
    t_max = df_capex_opex.index.get_level_values("year").max()
    max_lifetime = df_capex_opex_extended["lifetime"].max().astype(int)
    t_extended_max = t_max + max_lifetime
    t = t_max + 1

    df_list = [df_capex_opex_extended]
    while t < t_extended_max:
        df_append = df_capex_opex_extended.copy().xs(key=t_max, level="year")
        df_append["year"] = t
        df_append = df_append.reset_index().set_index(IDX_TECH_RANKING_COLUMNS)
        df_list.append(df_append)
        t = t + 1

    df_capex_opex_extended = pd.concat(df_list).sort_index()

    return df_capex_opex_extended


def _compute_lcox(row: pd.Series, df: pd.DataFrame) -> pd.Series:
    """
    The df's index must be ordered according to IDX_TECH_RANKING_COLUMNS and sorted!

    Args:
        row ():
        df ():

    Returns:

    """

    idx_switch = row.name
    df = df.copy()

    # check if row's switch_type == "decommission" and set LCOX to switch_capex if so
    if idx_switch[IDX_TECH_RANKING_COLUMNS.index("switch_type")] == "decommission":
        row.loc["lcox"] = row.loc["switch_capex"]
        return row

    # get first and last year (based on lifetime)
    first_year = idx_switch[IDX_TECH_RANKING_COLUMNS.index("year")]
    lifetime = row.loc["lifetime"]
    last_year = first_year + lifetime - 1

    # get sub-dataframe with all values required for computing the present value
    df_pv = df.xs(
        key=tuple([x for x in idx_switch if x != first_year]),
        level=tuple([x for x in IDX_TECH_RANKING_COLUMNS if x != "year"]),
    )
    df_pv = df_pv.loc[first_year:last_year, :]

    # set all switch_capex values except for first one to 0
    df_pv.rename(columns={"switch_capex": "capex"}, inplace=True)
    df_pv.loc[(first_year + 1) :, "capex"] = float(0)

    # compute OPEX
    cuf = df_pv.loc[first_year, "capacity_factor"]
    df_pv["opex"] = df_pv["opex_fixed"] + df_pv["opex_variable"] * cuf

    # insert exponent column
    df_pv["exp"] = range(0, df_pv.shape[0])

    # compute (1 / (1 + WACC)^t)
    df_pv["pv_norm"] = 1 / ((1 + df_pv["wacc"]) ** df_pv["exp"])

    # compute present value
    df_pv["pv"] = df_pv["capex"] + df_pv["opex"] * df_pv["pv_norm"]

    # compute and set LCOX
    row.loc["lcox"] = df_pv["pv"].sum() / (cuf * df_pv["pv_norm"].sum())

    return row

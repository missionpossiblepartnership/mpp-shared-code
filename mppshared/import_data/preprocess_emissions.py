"""Calculates all emissions required for technology ranking"""

import pandas as pd

from mppshared.config import GHG_CONVERSION, IDX_EMISSIVITY, LOG_LEVEL
from mppshared.utility.log_utility import get_logger
from mppshared.utility.utils import extend_to_all_technologies

# Create logger
logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def calculate_emissions(
    sector: str,
    dict_emissivity: dict,
    df_inputs_energy: pd.DataFrame,
    df_capture_rate: pd.DataFrame,
    list_technologies: list,
) -> pd.DataFrame:
    """
    Calculates the emissivities per technology for all scopes.
        WARNING: cement has only CO2 emissions in scopes 1 and 2 (otherwise the units would have to be considered here)

    Args:
        sector ():
        dict_emissivity (): Unit: [t GHG / t production_output] or [t GHG / GJ]
        df_inputs_energy (): Unit: [GJ / t Clk]
        df_capture_rate (): Unit: [%]
        list_technologies ():

    Returns:

    """

    dict_emissivity = dict_emissivity.copy()
    idx_emissivity_precursor = [
        x for x in IDX_EMISSIVITY if x != "technology_destination"
    ] + ["metric", "ghg"]

    df_inputs_energy = df_inputs_energy.copy().droplevel("unit")
    df_capture_rate = df_capture_rate.copy().droplevel(["metric", "unit"])

    """scope 1"""

    df_scope_1 = _filter_emissivity_data_by_scope(
        dict_emissivity=dict_emissivity,
        scope="1",
        idx_emissivity=idx_emissivity_precursor,
    )

    if sector == "cement":

        # split into energy and process emissions
        df_scope_1.reset_index(inplace=True)
        df_scope_1_process = df_scope_1.loc[
            df_scope_1["metric"] == "Calcination process emissions", :
        ].set_index(idx_emissivity_precursor)
        # unit df_scope_1_process: [t CO2 / t Clk]
        df_scope_1_energy = df_scope_1.loc[
            df_scope_1["metric"] != "Calcination process emissions", :
        ].set_index(idx_emissivity_precursor)
        # unit df_scope_1_energy: [t CO2 / GJ]

        # extend df_scope_1_process to all regions
        df_scope_1_process = extend_to_all_technologies(
            df=df_scope_1_process, list_technologies=list_technologies
        )

        # multiply energy emissivity with energy intensity
        df_scope_1_energy = df_scope_1_energy.mul(df_inputs_energy).dropna(how="all")
        # unit df_scope_1_process: [t CO2 / t Clk]

        df_scope_1 = pd.concat([df_scope_1_energy, df_scope_1_process]).sort_index()
        df_scope_1 = df_scope_1.groupby(IDX_EMISSIVITY + ["ghg"]).sum()

        # get captured emissions (WARNING: only for CO2!)
        df_scope_1_captured = df_scope_1.copy().mul(df_capture_rate)
        df_scope_1_captured = df_scope_1_captured.xs(
            key="emissivity_co2", level="ghg", drop_level=False
        )

    # rename and concat
    df_scope_1.rename(columns={"value": "scope_1"}, inplace=True)
    df_scope_1_captured.rename(columns={"value": "scope_1_captured"}, inplace=True)
    # unit df_scope_1: [t GHG / t production_output]

    """scope 2"""

    df_scope_2 = _filter_emissivity_data_by_scope(
        dict_emissivity=dict_emissivity,
        scope="2",
        idx_emissivity=idx_emissivity_precursor,
    )

    # multiply energy emissivity with energy intensity
    df_scope_2 = df_scope_2.mul(df_inputs_energy).dropna(how="all").droplevel("metric")
    df_scope_2 = df_scope_2.reorder_levels(IDX_EMISSIVITY + ["ghg"]).sort_index()
    df_scope_2.rename(columns={"value": "scope_2"}, inplace=True)
    # unit df_scope_2: [t GHG / t production_output]

    """scope 3 upstream"""

    df_scope_3_upstream = _filter_emissivity_data_by_scope(
        dict_emissivity=dict_emissivity,
        scope="3_upstream",
        idx_emissivity=idx_emissivity_precursor,
    )

    # multiply energy emissivity with energy intensity
    df_scope_3_upstream = (
        df_scope_3_upstream.mul(df_inputs_energy).dropna(how="all").droplevel("metric")
    )
    df_scope_3_upstream = df_scope_3_upstream.reorder_levels(
        IDX_EMISSIVITY + ["ghg"]
    ).sort_index()
    df_scope_3_upstream.rename(columns={"value": "scope_3_upstream"}, inplace=True)
    # unit df_scope_3_upstream: [t GHG / t production_output]

    """scope 3 downstream"""

    df_scope_3_downstream = pd.DataFrame()
    # unit df_scope_3_downstream: [t GHG / t production_output]

    """merge and convert to CO2e"""

    # concat
    df_emissivity = pd.concat(
        [
            df_scope_1,
            df_scope_1_captured,
            df_scope_2,
            df_scope_3_upstream,
            df_scope_3_downstream,
        ],
        axis=1,
    )

    # convert to CO2e
    df_conversion = pd.DataFrame.from_dict(
        data=GHG_CONVERSION, orient="index", columns=["value"]
    )
    df_conversion.index.name = "ghg"
    # wide to long
    id_vars = list(df_emissivity.index.names)
    df_emissivity_cols = list(df_emissivity)
    df_emissivity = pd.melt(
        frame=df_emissivity.reset_index(),
        id_vars=id_vars,
        value_vars=df_emissivity_cols,
        var_name="scope",
        value_name="value",
    )
    idx_emissivity_long = [x for x in list(df_emissivity) if x != "value"]
    df_emissivity.set_index(keys=idx_emissivity_long, inplace=True)
    # convert and sum
    df_emissivity = df_emissivity.mul(df_conversion)
    df_emissivity = df_emissivity.groupby(
        [x for x in idx_emissivity_long if x != "ghg"]
    ).sum()
    # long to wide
    df_emissivity = df_emissivity.reset_index().pivot(
        index=IDX_EMISSIVITY, columns="scope", values="value"
    )

    return df_emissivity


"""private helper functions"""


def _filter_emissivity_data_by_scope(
    dict_emissivity: dict,
    scope: str,
    idx_emissivity,
) -> pd.DataFrame():
    """

    Args:
        dict_emissivity (): dict with emissivities of all GHGs
        scope (): Scope number as string

    Returns:

    """

    df_list = []
    for key in dict_emissivity.keys():
        df_append = dict_emissivity[key].reset_index()
        df_append = df_append.loc[df_append["scope"] == scope, :].reset_index(drop=True)
        df_append["ghg"] = key
        df_list.append(df_append)
    df_scope = pd.concat(df_list)

    df_scope = df_scope[idx_emissivity + ["value"]]
    df_scope = df_scope.set_index(idx_emissivity).sort_index()

    return df_scope

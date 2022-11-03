"""Calculates all emissions required for technology ranking"""

import pandas as pd
from itertools import chain

from mppshared.config import GHG_CONVERSION, IDX_EMISSIVITY, LOG_LEVEL
from mppshared.utility.log_utility import get_logger
from mppshared.utility.utils import (
    extend_to_all_technologies,
    filter_input_metrics,
    get_unique_list_values,
)

# Create logger
logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def calculate_emissions(
    dict_emissivity: dict,
    df_inputs_energy: pd.DataFrame,
    df_capture_rate: pd.DataFrame,
    list_technologies: list,
    emissivity_ccus_process_metrics_energy: list,
    idx_per_input_metric: dict,
) -> pd.DataFrame:
    """
    Calculates the emissivities per technology for all scopes.
        WARNING: cement has only CO2 emissions in scopes 1 and 2 (otherwise the units would have to be considered here)

    Args:
        dict_emissivity (): Unit: [t GHG / t production_output] or [t GHG / GJ]
        df_inputs_energy (): Unit: [GJ / t Clk]
        df_capture_rate (): Unit: [%]
        list_technologies ():
        emissivity_ccus_process_metrics_energy ():
        idx_per_input_metric ():

    Returns:
        Unit: [t GHG / t production_output]
    """

    dict_emissivity = dict_emissivity.copy()
    idx_emissivity_precursor_raw = [x for x in IDX_EMISSIVITY if x != "technology"] + [
        "metric",
        "ghg",
    ]
    idx_emissivity_precursor = IDX_EMISSIVITY.copy()

    df_inputs_energy = df_inputs_energy.copy().droplevel("unit")
    df_capture_rate = df_capture_rate.copy().droplevel(["metric", "unit"])

    # rename column "technology_destination" to "technology"
    idx_input_energy = [x for x in idx_per_input_metric["inputs_energy"] if x != "unit"]
    idx_input_energy[idx_input_energy.index("technology_destination")] = "technology"
    df_inputs_energy = (
        df_inputs_energy.reset_index()
        .rename(columns={"technology_destination": "technology"})
        .set_index(idx_input_energy)
    )

    """scope 1"""

    df_scope_1 = _filter_emissivity_data_by_scope(
        dict_emissivity=dict_emissivity,
        scope="1",
        idx_emissivity=idx_emissivity_precursor_raw,
    )

    # split into energy and process emissions
    df_scope_1.reset_index(inplace=True)
    df_scope_1_process = df_scope_1.loc[
        df_scope_1["metric"] == "Calcination process emissions", :
    ].set_index(idx_emissivity_precursor_raw)
    # unit df_scope_1_process: [t CO2 / t Clk]
    df_scope_1_energy = df_scope_1.loc[
        df_scope_1["metric"] != "Calcination process emissions", :
    ].set_index(idx_emissivity_precursor_raw)
    # unit df_scope_1_energy: [t CO2 / GJ]

    # extend df_scope_1_process to all regions
    df_scope_1_process = extend_to_all_technologies(
        df=df_scope_1_process,
        list_technologies=list_technologies,
        technology_column_name="technology",
    )

    # energy emissions (non-CCU/S process): multiply energy emissivity with energy intensity
    df_scope_1_energy_nonccus = (
        df_scope_1_energy.copy().mul(df_inputs_energy).dropna(how="all")
    )
    # unit df_scope_1_energy_nonccus: [t CO2 / t Clk]

    # energy emissions (CCU/S process)
    # get unique keys as list from emissivity_ccus_process_metrics_energy
    dict_ccus_process_emissions = get_unique_list_values(
        list(chain(*[list(x.keys()) for x in emissivity_ccus_process_metrics_energy]))
    )
    # generate dict from the unique list
    dict_ccus_process_emissions = dict.fromkeys(dict_ccus_process_emissions)
    # fill dict with respective dataframes
    dict_ccus_process_emissions["inputs_energy"] = df_inputs_energy
    dict_ccus_process_emissions["emissivity"] = df_scope_1_energy
    # compute all emissivity components of CC process
    df_scope_1_energy_ccus = _get_ccus_process_emissivity(
        input_data=dict_ccus_process_emissions,
        emissivity_ccus_process_metrics=emissivity_ccus_process_metrics_energy,
    )
    # df_scope_1_energy_ccus unit: [t CO2 / t Clk]

    df_scope_1 = pd.concat(
        [
            df_scope_1_process,
            df_scope_1_energy_nonccus.reorder_levels(
                list(df_scope_1_process.index.names)
            ),
            df_scope_1_energy_ccus.reorder_levels(list(df_scope_1_process.index.names)),
        ]
    ).sort_index()
    df_scope_1 = df_scope_1.groupby(idx_emissivity_precursor + ["ghg"]).sum()

    # get captured emissions (only for CO2!)
    df_capture_rate = (
        df_capture_rate.reset_index()
        .rename(columns={"technology_destination": "technology"})
        .set_index(idx_emissivity_precursor)
    )
    df_scope_1_captured = df_scope_1.copy().mul(df_capture_rate)
    df_scope_1_captured = df_scope_1_captured.xs(
        key="emissivity_co2", level="ghg", drop_level=False
    )

    # rename and concat
    df_scope_1.rename(columns={"value": "scope1"}, inplace=True)
    df_scope_1_captured.rename(columns={"value": "scope1_captured"}, inplace=True)
    # unit df_scope_1: [t GHG / t production_output]

    """scope 2"""

    df_scope_2 = _filter_emissivity_data_by_scope(
        dict_emissivity=dict_emissivity,
        scope="2",
        idx_emissivity=idx_emissivity_precursor_raw,
    )

    # non-CCU/S process
    df_scope_2_nonccus = (
        df_scope_2.copy().mul(df_inputs_energy).dropna(how="all").droplevel("metric")
    )
    # df_scope_2_nonccus unit: [t CO2 / t Clk]

    # CCU/S process
    # update emissivity dataframe dataframes
    dict_ccus_process_emissions["emissivity"] = df_scope_2.copy()
    # compute all emissivity components of CC process
    df_scope_2_ccus = _get_ccus_process_emissivity(
        input_data=dict_ccus_process_emissions,
        emissivity_ccus_process_metrics=emissivity_ccus_process_metrics_energy,
    ).droplevel("metric")
    # df_scope_2_ccus unit: [t CO2 / t Clk]

    df_scope_2 = pd.concat(
        [
            df_scope_2_nonccus,
            df_scope_2_ccus.reorder_levels(list(df_scope_2_nonccus.index.names)),
        ]
    ).sort_index()
    df_scope_2 = df_scope_2.groupby(idx_emissivity_precursor + ["ghg"]).sum()

    df_scope_2 = df_scope_2.reorder_levels(
        idx_emissivity_precursor + ["ghg"]
    ).sort_index()
    df_scope_2.rename(columns={"value": "scope2"}, inplace=True)
    # unit df_scope_2: [t GHG / t production_output]

    """scope 3 upstream"""

    df_scope_3_upstream = _filter_emissivity_data_by_scope(
        dict_emissivity=dict_emissivity,
        scope="3_upstream",
        idx_emissivity=idx_emissivity_precursor_raw,
    )

    # multiply energy emissivity with energy intensity
    df_scope_3_upstream_nonccus = (
        df_scope_3_upstream.copy().mul(df_inputs_energy).dropna(how="all")
    )
    # df_scope_3_upstream_nonccus unit: [t CO2 / t Clk]

    # CCU/S process
    # update emissivity dataframe dataframes
    dict_ccus_process_emissions["emissivity"] = df_scope_3_upstream.copy()
    # compute all emissivity components of CC process
    df_scope_3_upstream_ccus = _get_ccus_process_emissivity(
        input_data=dict_ccus_process_emissions,
        emissivity_ccus_process_metrics=emissivity_ccus_process_metrics_energy,
    )
    # df_scope_3_upstream_ccus unit: [t CO2 / t Clk]

    # aggregate
    df_scope_3_upstream = pd.concat(
        [
            df_scope_3_upstream_nonccus,
            df_scope_3_upstream_ccus.reorder_levels(
                list(df_scope_3_upstream_nonccus.index.names)
            ),
        ]
    ).sort_index()
    df_scope_3_upstream = df_scope_3_upstream.groupby(
        [x for x in df_scope_3_upstream.index.names if x != "metric"]
    ).sum()
    df_scope_3_upstream = df_scope_3_upstream.reorder_levels(
        idx_emissivity_precursor + ["ghg"]
    ).sort_index()
    df_scope_3_upstream.rename(columns={"value": "scope3_upstream"}, inplace=True)
    # unit df_scope_3_upstream: [t GHG / t production_output]

    """merge and convert to CO2e"""

    # concat
    df_emissivity = pd.concat(
        [
            df_scope_1,
            df_scope_1_captured,
            df_scope_2,
            df_scope_3_upstream,
        ],
        axis=1,
    ).fillna(value=float(0))

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
    df_emissivity_co2e = df_emissivity.copy().mul(df_conversion)
    df_emissivity_co2e = df_emissivity_co2e.groupby(
        [x for x in idx_emissivity_long if x != "ghg"]
    ).sum()
    # long to wide
    df_emissivity_co2e = df_emissivity_co2e.reset_index().pivot(
        index=idx_emissivity_precursor, columns="scope", values="value"
    )
    # rename columns
    # add "co2e" to all scopes
    dict_rename = {k: f"co2e_{k}" for k in list(df_emissivity_co2e)}
    df_emissivity_co2e.rename(columns=dict_rename, inplace=True)
    # pivot and rename columns in df_emissivity
    df_emissivity = df_emissivity.reset_index().pivot(
        index=idx_emissivity_precursor, columns=["ghg", "scope"], values="value"
    )
    # reduce multiindex columns
    df_emissivity.columns = ["_".join(col) for col in df_emissivity.columns.values]
    df_emissivity.rename(
        columns={
            # CO2
            "emissivity_co2_scope1": "co2_scope1",
            "emissivity_co2_scope1_captured": "co2_scope1_captured",
            "emissivity_co2_scope2": "co2_scope2",
            "emissivity_co2_scope3_upstream": "co2_scope3_upstream",
            # CH4
            "emissivity_ch4_scope1": "ch4_scope1",
            "emissivity_ch4_scope1_captured": "ch4_scope1_captured",
            "emissivity_ch4_scope2": "ch4_scope2",
            "emissivity_ch4_scope3_upstream": "ch4_scope3_upstream",
        },
        inplace=True,
    )
    # concat
    df_emissivity = pd.concat(objs=[df_emissivity, df_emissivity_co2e], axis=1)

    # make captured emissions negative
    capture_cols = [x for x in df_emissivity.columns if "captured" in x]
    df_emissivity.loc[:, capture_cols] *= -1
    df_emissivity.fillna(value=float(0), inplace=True)
    # compute scope 1 emissions after capturing
    df_emissivity["co2_scope1"] += df_emissivity["co2_scope1_captured"]
    df_emissivity["ch4_scope1"] += df_emissivity["ch4_scope1_captured"]
    df_emissivity["co2e_scope1"] += df_emissivity["co2e_scope1_captured"]

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


def _get_ccus_process_emissivity(
    input_data: dict,
    emissivity_ccus_process_metrics: list,
) -> pd.DataFrame:
    """
    Takes as input a dictionary that includes all the dataframes that are required for computing the CCU/S emissivity.
        The function then calculates all emissivity components by multiplying two dataframes with each other based on
        ccus_emissivity_metrics.

    Args:
        input_data (dict): dictionary that includes all the dataframes that are required for computing the CCU/S
            emissivity
        emissivity_ccus_process_metrics (list): List of all CCU/S emissivity components. Every item in the list is a
            dict with two keys: the name of the dataframe with emissivities (must be part of input_data) and an
            emissivity metric as value as well as the corresponding name of the energy intensity dataframe (must also be
            part of input_data) and an energy intensity metric as value.

    Returns:
        df_cc_emissivity (): Unit: [t CO2 / t production_output]
    """

    df_list = []
    for ccus_process_cost_component in emissivity_ccus_process_metrics:

        df_subcomponent_list = []
        for subcomponent in ccus_process_cost_component.keys():
            # filter all relevant energy inputs
            idx_subcomponent = [
                x
                for x in input_data[subcomponent].index.names
                if x not in ["metric", "unit"]
            ]
            df_subcomponent = filter_input_metrics(
                df=input_data[subcomponent].copy().reset_index(),
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
        df_cc_emissivity_component = df_subcomponent_list[0].mul(
            df_subcomponent_list[1]
        )
        # append to df_list
        df_list.append(df_cc_emissivity_component)

    # concat and groupby
    df_cc_emissivity = pd.concat(df_list)
    df_cc_emissivity = df_cc_emissivity.groupby(
        list(df_cc_emissivity.index.names)
    ).sum()
    df_cc_emissivity["metric"] = "CC capture process emissions"
    df_cc_emissivity = (
        df_cc_emissivity.reset_index()
        .set_index(IDX_EMISSIVITY + ["ghg", "metric"])
        .sort_index()
    )

    return df_cc_emissivity

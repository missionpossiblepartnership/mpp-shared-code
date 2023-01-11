"""Calculate technology switch-specific data for archetype explorer"""

from cement.archetype_explorer.ae_config import (
    AE_CARBON_COST,
    AE_COMPUTE_LCOX,
    AE_SENSITIVITY_MAPPING,
    AE_YEARS,
    AF_PRICE,
    CAPEX,
    CAPTURE_RATE,
    ELEC_PRICE,
    FOSSIL_PRICE,
)
from cement.config.config_cement import (
    ALL_TECHNOLOGIES,
    CARBON_COST_SCOPES,
    CCUS_CONTEXT,
    COST_CLASSIFICATIONS,
    INVESTMENT_CYCLE,
    MODEL_YEARS,
    REGIONS,
    TRANSITION_TYPES,
)
from cement.config.dataframe_config_cement import (
    DF_DATATYPES_PER_COLUMN,
    IDX_PER_INPUT_METRIC,
)
from cement.config.import_config_cement import (
    EMISSIVITY_CCUS_PROCESS_METRICS_ENERGY,
    EXCEL_COLUMN_RANGES,
    HEADER_BUSINESS_CASE_EXCEL,
    INPUT_METRICS,
    INPUT_SHEETS,
    MAP_SWITCH_TYPES_TO_CAPEX_TYPE,
    OPEX_CCUS_CONTEXT_METRICS,
    OPEX_CCUS_EMISSIVITY_METRIC_TYPES,
    OPEX_CCUS_EMISSIVITY_METRICS,
    OPEX_CCUS_PROCESS_METRICS_ENERGY,
    OPEX_ENERGY_METRICS,
)
from cement.preprocess.import_data import get_tech_switches
from cement.preprocess.preprocess_emissions import calculate_emissions
from cement.preprocess.preprocess_tech_characteristics import get_tech_characteristics
from cement.preprocess.preprocess_tech_transitions import calculate_tech_transitions
from mppshared.config import LOG_LEVEL
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def ae_get_ranking_inputs(
    pathway_name: str, sensitivity: str, sector: str, products: list
):
    """
    Calculates all inputs for the archetype explorer

    Args:
        pathway_name ():
        sensitivity ():
        sector ():
        products ():

    Returns:

    """

    sensitivity_params = AE_SENSITIVITY_MAPPING[sensitivity]

    importer = IntermediateDataImporter(
        pathway_name=pathway_name,
        sensitivity=sensitivity,
        sector=sector,
        products=products,
        carbon_cost_trajectory=None,
        business_case_excel_filename="business_cases.xlsx",
    )

    # get imported inputs
    imported_input_data = importer.get_imported_input_data(
        input_metrics=INPUT_METRICS,
        index=True,
        idx_per_input_metric=IDX_PER_INPUT_METRIC,
    )

    """ apply parameter adjustments """
    imported_input_data = _apply_parameter_adjustments(
        sensitivity_params=sensitivity_params,
        imported_input_data=imported_input_data,
    )
    # export
    for metric in imported_input_data.keys():
        importer.export_data(
            df=imported_input_data[metric],
            filename=f"{metric}.csv",
            export_dir="import",
        )

    """ emissions """
    df_emissions = calculate_emissions(
        dict_emissivity={
            x: imported_input_data[x]
            for x in INPUT_METRICS["Shared inputs - Emissivity"]
        },
        df_inputs_energy=imported_input_data["inputs_energy"],
        df_capture_rate=imported_input_data["capture_rate"],
        list_technologies=ALL_TECHNOLOGIES,
        emissivity_ccus_process_metrics_energy=EMISSIVITY_CCUS_PROCESS_METRICS_ENERGY,
        idx_per_input_metric=IDX_PER_INPUT_METRIC,
    )
    # export
    importer.export_data(
        df=df_emissions,
        filename="emissions.csv",
        export_dir="intermediate",
        index=True,
    )

    """ cost metrics """

    # calculate carbon cost
    if AE_CARBON_COST[sensitivity_params["carbon_cost"]] is not None:
        carbon_cost_trajectory = CarbonCostTrajectory(
            trajectory=AE_CARBON_COST[sensitivity_params["carbon_cost"]]["trajectory"],  # type: ignore
            initial_carbon_cost=AE_CARBON_COST[sensitivity_params["carbon_cost"]][
                "initial_carbon_cost"
            ],  # type: ignore
            final_carbon_cost=AE_CARBON_COST[sensitivity_params["carbon_cost"]][
                "final_carbon_cost"
            ],  # type: ignore
            start_year=AE_CARBON_COST[sensitivity_params["carbon_cost"]]["start_year"],  # type: ignore
            end_year=AE_CARBON_COST[sensitivity_params["carbon_cost"]]["end_year"],  # type: ignore
            model_years=MODEL_YEARS,
        )
    else:
        carbon_cost_trajectory = None
    df_tech_transitions = calculate_tech_transitions(
        importer=importer,
        # parameters
        sector=sector,
        model_years=MODEL_YEARS,
        products=products,
        model_regions=REGIONS,
        compute_lcox=AE_COMPUTE_LCOX,
        ccus_context=CCUS_CONTEXT,
        list_technologies=ALL_TECHNOLOGIES,
        cost_classifications=COST_CLASSIFICATIONS,
        idx_per_input_metric=IDX_PER_INPUT_METRIC,
        map_switch_types_to_capex_type=MAP_SWITCH_TYPES_TO_CAPEX_TYPE,
        opex_ccus_context_metrics=OPEX_CCUS_CONTEXT_METRICS,
        opex_energy_metrics=OPEX_ENERGY_METRICS,
        opex_ccus_process_metrics_energy=OPEX_CCUS_PROCESS_METRICS_ENERGY,
        opex_ccus_emissivity_metrics=OPEX_CCUS_EMISSIVITY_METRICS,
        opex_ccus_emissivity_metric_types=OPEX_CCUS_EMISSIVITY_METRIC_TYPES,
        carbon_cost_scopes=CARBON_COST_SCOPES,
        investment_cycle=INVESTMENT_CYCLE,
        # data
        df_tech_switches=get_tech_switches(
            importer=importer,
            transition_types=TRANSITION_TYPES,
            input_sheets=INPUT_SHEETS,
            datatypes_per_column=DF_DATATYPES_PER_COLUMN,
            excel_column_ranges=EXCEL_COLUMN_RANGES,
            header_business_case_excel=HEADER_BUSINESS_CASE_EXCEL,
        ),
        dict_emissivity={
            x: imported_input_data[x]
            for x in INPUT_METRICS["Shared inputs - Emissivity"]
        },
        df_emissions=df_emissions,
        df_capex=imported_input_data["capex"],
        df_opex=imported_input_data["opex"],
        df_inputs_energy=imported_input_data["inputs_energy"],
        df_commodity_prices=imported_input_data["commodity_prices"],
        df_wacc=imported_input_data["wacc"],
        df_capacity_factor=imported_input_data["capacity_factor"],
        df_lifetime=imported_input_data["lifetime"],
        df_capture_rate=imported_input_data["capture_rate"],
        carbon_cost_trajectory=carbon_cost_trajectory,
        # archetype explorer
        archetype_explorer=True,
        ae_years=AE_YEARS,
        ae_switch_type="brownfield_renovation",
    )
    # export
    importer.export_data(
        df=df_tech_transitions,
        filename="technology_transitions.csv",
        export_dir="intermediate",
    )

    """ technology characteristics """
    df_tech_characteristics = get_tech_characteristics(
        df_tech_classification=imported_input_data["tech_classification"],
        df_trl_current=imported_input_data["trl_current"],
        df_expected_maturity=imported_input_data["expected_maturity"],
        df_lifetime=imported_input_data["lifetime"],
        df_wacc=imported_input_data["wacc"],
    )
    # export
    importer.export_data(
        df=df_tech_characteristics,
        filename="technology_characteristics.csv",
        export_dir="intermediate",
    )


def _apply_parameter_adjustments(
    sensitivity_params: dict, imported_input_data: dict
) -> dict:
    """
    Adjusts the imported input data according to the following contextual parameters in ae_config.py:
        - electricity price
        - fossil price (coal & natural gas)
        - alternative fuels price (biomass, waste, & hydrogen)
        - CAPEX
        - Capture rate

    Args:
        imported_input_data ():

    Returns:

    """

    # electricity price #

    df = imported_input_data["commodity_prices"].copy()

    idx_elec = df.index.get_level_values("metric").str.contains("Electricity")
    df.loc[idx_elec, :] *= 1 + ELEC_PRICE[sensitivity_params["elec_price"]]

    imported_input_data["commodity_prices"] = df.copy()

    # fossil price #

    df = imported_input_data["commodity_prices"].copy()

    idx_fossil = df.index.get_level_values("metric").str.contains(
        "Coal|Natural gas", regex=True
    )
    df.loc[idx_fossil, :] *= 1 + FOSSIL_PRICE[sensitivity_params["fossil_price"]]

    imported_input_data["commodity_prices"] = df.copy()

    # alternative fuels price #

    df = imported_input_data["commodity_prices"].copy()

    idx_af = df.index.get_level_values("metric").str.contains(
        "Biomass|Hydrogen|Waste", regex=True
    )
    df.loc[idx_af, :] *= 1 + AF_PRICE[sensitivity_params["af_price"]]

    imported_input_data["commodity_prices"] = df.copy()

    # CAPEX #

    imported_input_data["capex"] *= 1 + CAPEX[sensitivity_params["capex"]]

    # Capture rate #

    imported_input_data["capture_rate"].loc[
        (imported_input_data["capture_rate"]["value"] > 0), :
    ] = CAPTURE_RATE[sensitivity_params["capture_rate"]]

    return imported_input_data

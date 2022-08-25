"""Create inputs for ranking of technology switches (cost metrics, emissions, and technology characteristics)."""

from cement.config.config_cement import (
    COST_CLASSIFICATIONS,
    LIST_TECHNOLOGIES,
    MODEL_YEARS,
    REGIONS,
    TRANSITION_TYPES,
    COMPUTE_LCOX,
    PATHWAYS_WITH_CARBON_COST,
    CARBON_COST_SENSITIVITIES,
    CARBON_COST_SCOPES,
)
from cement.config.dataframe_config_cement import (
    DF_DATATYPES_PER_COLUMN,
    IDX_PER_INPUT_METRIC,
)
from cement.config.import_config_cement import (
    EXCEL_COLUMN_RANGES,
    HEADER_BUSINESS_CASE_EXCEL,
    INPUT_METRICS,
    INPUT_SHEETS,
    MAP_SWITCH_TYPES_TO_CAPEX_TYPE,
    OPEX_CCUS_CONTEXT_METRICS,
    OPEX_CCUS_EMISSIVITY_METRIC_TYPES,
    OPEX_CCUS_EMISSIVITY_METRICS,
    OPEX_CCUS_PROCESS_METRICS,
    OPEX_ENERGY_METRICS,
    OPEX_MATERIALS_METRICS,
)
from mppshared.config import LOG_LEVEL
from cement.preprocess.import_data import get_tech_switches
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from cement.preprocess.preprocess_emissions import calculate_emissions
from cement.preprocess.preprocess_tech_characteristics import (
    get_tech_characteristics,
)
from cement.preprocess.preprocess_tech_transitions import calculate_tech_transitions
from mppshared.models.carbon_cost_trajectory import CarbonCostTrajectory
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def get_ranking_inputs(
    pathway_name: str, sensitivity: str, sector: str, products: list
):
    """Create the input files for the ranking for the three types of technology switches"""

    importer = IntermediateDataImporter(
        pathway_name=pathway_name,
        sensitivity=sensitivity,
        sector=sector,
        products=products,
    )

    # get imported inputs
    imported_input_data = importer.get_imported_input_data(
        input_metrics=INPUT_METRICS,
        index=True,
        idx_per_input_metric=IDX_PER_INPUT_METRIC,
    )

    # get emissions
    df_emissions = calculate_emissions(
        sector=sector,
        dict_emissivity={
            x: imported_input_data[x]
            for x in INPUT_METRICS["Shared inputs - Emissivity"]
        },
        df_inputs_energy=imported_input_data["inputs_energy"],
        df_capture_rate=imported_input_data["capture_rate"],
        list_technologies=LIST_TECHNOLOGIES,
    )
    # export
    importer.export_data(
        df=df_emissions,
        filename="emissions.csv",
        export_dir="intermediate",
    )

    # get cost metrics
    # calculate carbon cost
    if pathway_name in PATHWAYS_WITH_CARBON_COST:
        carbon_cost_trajectory = CarbonCostTrajectory(
            trajectory=CARBON_COST_SENSITIVITIES[sensitivity]["trajectory"],
            initial_carbon_cost=CARBON_COST_SENSITIVITIES[sensitivity]["initial_carbon_cost"],
            final_carbon_cost=CARBON_COST_SENSITIVITIES[sensitivity]["final_carbon_cost"],
            start_year=CARBON_COST_SENSITIVITIES[sensitivity]["start_year"],
            end_year=CARBON_COST_SENSITIVITIES[sensitivity]["end_year"],
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
        compute_lcox=COMPUTE_LCOX,
        list_technologies=LIST_TECHNOLOGIES,
        cost_classifications=COST_CLASSIFICATIONS,
        idx_per_input_metric=IDX_PER_INPUT_METRIC,
        map_switch_types_to_capex_type=MAP_SWITCH_TYPES_TO_CAPEX_TYPE,
        opex_ccus_context_metrics=OPEX_CCUS_CONTEXT_METRICS,
        opex_energy_metrics=OPEX_ENERGY_METRICS,
        opex_ccus_process_metrics=OPEX_CCUS_PROCESS_METRICS,
        opex_materials_metrics=OPEX_MATERIALS_METRICS,
        opex_ccus_emissivity_metrics=OPEX_CCUS_EMISSIVITY_METRICS,
        opex_ccus_emissivity_metric_types=OPEX_CCUS_EMISSIVITY_METRIC_TYPES,
        carbon_cost_scopes=CARBON_COST_SCOPES,
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
        df_inputs_material=imported_input_data["inputs_material"],
        df_inputs_energy=imported_input_data["inputs_energy"],
        df_commodity_prices=imported_input_data["commodity_prices"],
        df_wacc=imported_input_data["wacc"],
        df_capacity_factor=imported_input_data["capacity_factor"],
        df_lifetime=imported_input_data["lifetime"],
        df_capture_rate=imported_input_data["capture_rate"],
        carbon_cost_trajectory=carbon_cost_trajectory,
    )
    # export
    importer.export_data(
        df=df_tech_transitions,
        filename="technology_transitions.csv",
        export_dir="intermediate",
    )

    # get technology characteristics
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

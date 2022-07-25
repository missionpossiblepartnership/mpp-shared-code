"""Create ranking of technology switches (decommission, brownfield, greenfield)."""

from cement.config.config_cement import (BIN_METHODOLOGY, COST_CLASSIFICATIONS,
                                         COST_METRIC_RELATIVE_UNCERTAINTY,
                                         EMISSION_SCOPES_RANKING, GHGS_RANKING,
                                         LIST_TECHNOLOGIES, MODEL_YEARS,
                                         NUMBER_OF_BINS_RANKING, PRODUCTS,
                                         RANK_TYPES, RANKING_CONFIG,
                                         RANKING_COST_METRIC, REGIONS, SECTOR,
                                         TRANSITION_TYPES)
from cement.config.dataframe_config_cement import (DF_DATATYPES_PER_COLUMN,
                                                   IDX_PER_INPUT_METRIC)
from cement.config.import_config_cement import (
    INPUT_METRICS, INPUT_SHEETS, MAP_SWITCH_TYPES_TO_CAPEX_TYPE,
    OPEX_CCUS_CONTEXT_METRICS, OPEX_CCUS_EMISSIVITY_METRIC_TYPES,
    OPEX_CCUS_EMISSIVITY_METRICS, OPEX_CCUS_PROCESS_METRICS,
    OPEX_ENERGY_METRICS, OPEX_MATERIALS_METRICS)
from mppshared.import_data.import_data import get_tech_switches
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.import_data.preprocess_cost_metrics import \
    calculate_cost_metrics
from mppshared.import_data.preprocess_emissions import calculate_emissions
from mppshared.import_data.preprocess_tech_characteristics import \
    get_tech_characteristics
from mppshared.solver.ranking import (rank_technology_histogram,
                                      rank_technology_uncertainty_bins)


def get_ranking_inputs(
    pathway: str,
    sensitivity: str,
):
    """Create the input files for the ranking for the three types of technology switches"""

    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=SECTOR,
        products=PRODUCTS,
    )

    # get imported inputs
    imported_input_data = importer.get_imported_input_data(
        input_metrics=INPUT_METRICS,
        index=True,
        idx_per_input_metric=IDX_PER_INPUT_METRIC,
    )

    # get cost metrics
    """dict_cost_metrics = calculate_cost_metrics(
        # parameters
        sector=SECTOR,
        model_years=MODEL_YEARS,
        products=PRODUCTS,
        model_regions=REGIONS,
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
        # data
        df_tech_switches=get_tech_switches(
            importer=importer,
            transition_types=TRANSITION_TYPES,
            input_sheets=INPUT_SHEETS,
            datatypes_per_column=DF_DATATYPES_PER_COLUMN,
        ),
        dict_emissivity={
            x: imported_input_data[x]
            for x in INPUT_METRICS["Shared inputs - Emissivity"]
        },
        df_capex=imported_input_data["capex"],
        df_opex=imported_input_data["opex"],
        df_inputs_material=imported_input_data["inputs_material"],
        df_inputs_energy=imported_input_data["inputs_energy"],
        df_commodity_prices=imported_input_data["commodity_prices"],
        df_wacc=imported_input_data["wacc"],
        df_capacity_factor=imported_input_data["capacity_factor"],
        df_lifetime=imported_input_data["lifetime"],
        df_capture_rate=imported_input_data["capture_rate"],
    )
    # export
    for cost_metric in dict_cost_metrics.keys():
        if dict_cost_metrics[cost_metric] is not None:
            importer.export_data(
                df=dict_cost_metrics[cost_metric],
                filename=f"{cost_metric}.csv",
                export_dir="intermediate",
            )"""

    # get emissions
    df_emissions = calculate_emissions(
        sector=SECTOR,
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


def make_rankings(pathway: str, sensitivity: str, sector: str, products: list):
    """Create the ranking for the three types of technology switches"""

    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=sector,
        products=products,
    )

    # Create ranking using the histogram methodology for every rank type
    df_ranking = importer.get_technologies_to_rank()
    for rank_type in RANK_TYPES:
        if BIN_METHODOLOGY == "histogram":
            df_rank = rank_technology_histogram(
                df_ranking=df_ranking,
                rank_type=rank_type,
                pathway=pathway,
                cost_metric=RANKING_COST_METRIC,
                n_bins=NUMBER_OF_BINS_RANKING,
                ranking_config=RANKING_CONFIG[rank_type][pathway],
                emission_scopes_ranking=EMISSION_SCOPES_RANKING,
                ghgs_ranking=GHGS_RANKING,
            )
        if BIN_METHODOLOGY == "uncertainty":
            df_rank = rank_technology_uncertainty_bins(
                df_ranking=df_ranking,
                rank_type=rank_type,
                pathway=pathway,
                cost_metric=RANKING_COST_METRIC,
                cost_metric_relative_uncertainty=COST_METRIC_RELATIVE_UNCERTAINTY,
                ranking_config=RANKING_CONFIG[rank_type][pathway],
                emission_scopes_ranking=EMISSION_SCOPES_RANKING,
                ghgs_ranking=GHGS_RANKING,
            )

        # Save ranking table as csv
        importer.export_data(
            df=df_rank,
            filename=f"{rank_type}_rank.csv",
            export_dir=f"ranking",
            index=False,
        )

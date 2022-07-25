"""import and pre-process all input files"""

from cement.config.config_cement import MODEL_YEARS, PRODUCTS, REGIONS, SECTOR
from cement.config.dataframe_config_cement import (DF_DATATYPES_PER_COLUMN,
                                                   IDX_PER_INPUT_METRIC)
from cement.config.import_config_cement import (COLUMN_SINGLE_INPUT,
                                                EXCEL_COLUMN_RANGES,
                                                HEADER_BUSINESS_CASE_EXCEL,
                                                INPUT_METRICS, INPUT_SHEETS,
                                                MAP_EXCEL_NAMES)
from mppshared.import_data.import_data import import_all
from mppshared.import_data.intermediate_data import IntermediateDataImporter


def import_and_preprocess(
    pathway: str,
    sensitivity: str,
):

    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=SECTOR,
        products=PRODUCTS,
    )

    import_all(
        importer=importer,
        model_years=MODEL_YEARS,
        model_regions=REGIONS,
        input_sheets=INPUT_SHEETS,
        input_metrics=INPUT_METRICS,
        map_excel_names=MAP_EXCEL_NAMES,
        idx_per_input_metric=IDX_PER_INPUT_METRIC,
        column_single_input=COLUMN_SINGLE_INPUT,
        datatypes_per_column=DF_DATATYPES_PER_COLUMN,
        header_business_case_excel=HEADER_BUSINESS_CASE_EXCEL,
        excel_column_ranges=EXCEL_COLUMN_RANGES
    )

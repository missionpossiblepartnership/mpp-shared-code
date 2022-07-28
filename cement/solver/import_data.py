"""import and pre-process all input files"""

import pandas as pd

from cement.config.config_cement import MODEL_YEARS, REGIONS
from cement.config.dataframe_config_cement import (DF_DATATYPES_PER_COLUMN,
                                                   IDX_PER_INPUT_METRIC)
from cement.config.import_config_cement import (COLUMN_SINGLE_INPUT,
                                                EXCEL_COLUMN_RANGES,
                                                HEADER_BUSINESS_CASE_EXCEL,
                                                INPUT_METRICS, INPUT_SHEETS,
                                                MAP_EXCEL_NAMES)
from mppshared.config import LOG_LEVEL
from mppshared.import_data.import_data import import_all
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.utility.dataframe_utility import set_datatypes
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def import_and_preprocess(pathway_name: str, sensitivity: str, sector: str, products: list):

    importer = IntermediateDataImporter(
        pathway_name=pathway_name,
        sensitivity=sensitivity,
        sector=sector,
        products=products,
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
        excel_column_ranges=EXCEL_COLUMN_RANGES,
    )

    # import and preprocess average start technologies
    df_start_technologies = importer.get_raw_input_data(
        sheet_name="Start technologies",
        header_business_case_excel=HEADER_BUSINESS_CASE_EXCEL,
        excel_column_ranges=EXCEL_COLUMN_RANGES,
    ).rename(columns={"Region": "region"})
    # set datatypes
    datatypes = {
        "region": str,
        "Dry kiln coal": float,
        "Dry kiln natural gas": float,
        "Dry kiln alternative fuels": float,
    }
    df_start_technologies = set_datatypes(df=df_start_technologies, datatypes_per_column=datatypes)
    # export
    importer.export_data(
        df=df_start_technologies,
        filename="start_technologies",
        export_dir="intermediate"
    )

    # import and preprocess OPEX context mapping
    df_opex_context_mapping = importer.get_raw_input_data(
        sheet_name="Region OPEX mapping",
        header_business_case_excel=HEADER_BUSINESS_CASE_EXCEL,
        excel_column_ranges=EXCEL_COLUMN_RANGES,
    )
    # export
    importer.export_data(
        df=df_opex_context_mapping,
        filename="opex_context_mapping",
        export_dir="intermediate"
    )

    # import and preprocess demand
    df_demand = importer.get_raw_input_data(
        sheet_name="demand",
        header_business_case_excel=HEADER_BUSINESS_CASE_EXCEL,
        excel_column_ranges=EXCEL_COLUMN_RANGES,
    )
    df_demand = pd.melt(
        frame=df_demand,
        id_vars="region",
        value_vars=MODEL_YEARS,
        var_name="year",
        value_name="value",
    )
    # export
    importer.export_data(
        df=df_demand,
        filename="demand",
        export_dir="intermediate"
    )

    stop = 1

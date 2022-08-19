"""import and pre-process all input files"""

import numpy as np
import pandas as pd

from cement.config.config_cement import (ASSUMED_ANNUAL_PRODUCTION_CAPACITY,
                                         LIST_TECHNOLOGIES, MODEL_YEARS,
                                         REGIONS, START_YEAR)
from cement.config.dataframe_config_cement import (DF_DATATYPES_PER_COLUMN,
                                                   IDX_PER_INPUT_METRIC)
from cement.config.import_config_cement import (AVERAGE_PLANT_COMMISSION_YEAR,
                                                COLUMN_SINGLE_INPUT,
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


def import_and_preprocess(
    pathway_name: str, sensitivity: str, sector: str, products: list
):

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

    # START TECHNOLOGIES
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
        "Dry kiln alternative fuels 43%": float,
        "Dry kiln alternative fuels 90%": float,
    }
    df_start_technologies = set_datatypes(df=df_start_technologies, datatypes_per_column=datatypes)
    # export
    importer.export_data(
        df=df_start_technologies,
        filename="start_technologies.csv",
        export_dir="intermediate",
        index=False,
    )

    # OPEX CONTEXT MAPPING
    df_opex_context_mapping = importer.get_raw_input_data(
        sheet_name="Region OPEX mapping",
        header_business_case_excel=HEADER_BUSINESS_CASE_EXCEL,
        excel_column_ranges=EXCEL_COLUMN_RANGES,
    )
    # export
    importer.export_data(
        df=df_opex_context_mapping,
        filename="opex_context_mapping.csv",
        export_dir="intermediate",
        index=False,
    )

    # DEMAND
    df_demand = importer.get_raw_input_data(
        sheet_name="demand",
        header_business_case_excel=HEADER_BUSINESS_CASE_EXCEL,
        excel_column_ranges=EXCEL_COLUMN_RANGES,
    )
    df_demand.rename(columns={"Product": "product"}, inplace=True)
    df_demand = pd.melt(
        frame=df_demand,
        id_vars=["product", "region"],
        value_vars=MODEL_YEARS,
        var_name="year",
        value_name="value",
    )
    # convert from [t Clk / year] to [Mt Clk / year]
    df_demand["value"] *= 1e-6
    # export
    importer.export_data(
        df=df_demand,
        filename="demand.csv",
        export_dir="intermediate",
        index=False,
    )

    # INITIAL ASSET STACK
    df_initial_asset_stack = _get_initial_asset_stack(importer=importer, product=products)
    # export
    importer.export_data(
        df=df_initial_asset_stack,
        filename="initial_asset_stack.csv",
        export_dir="intermediate",
        index=False,
    )

    # NATURAL GAS AND ALTERNATIVE FUEL CONSTRAINTS
    df_ng_af_constraint = importer.get_raw_input_data(
        sheet_name="Alternative fuels and NG",
        header_business_case_excel=HEADER_BUSINESS_CASE_EXCEL,
        excel_column_ranges=EXCEL_COLUMN_RANGES,
    ).rename(columns={"Region": "region"})

    # natural gas
    df_ng_constraint = df_ng_af_constraint.copy().loc[
        df_ng_af_constraint["Metric"] == "Maximum demand from natural gas", :
    ]
    df_ng_constraint = pd.melt(
        frame=df_ng_constraint,
        id_vars="region",
        value_vars=MODEL_YEARS,
        var_name="year",
        value_name="value",
    )
    df_ng_constraint = set_datatypes(
        df=df_ng_constraint, datatypes_per_column=DF_DATATYPES_PER_COLUMN
    )
    # convert from [t Clk / year] to [Mt Clk / year]
    df_ng_constraint["value"] *= 1e-6
    importer.export_data(
        df=df_ng_constraint,
        filename="natural_gas_constraint.csv",
        export_dir="intermediate",
        index=False,
    )
    # Unit df_ng_constraint: [Mt Clk / year]

    # alternative fuel
    df_af_constraint = df_ng_af_constraint.copy().loc[
        df_ng_af_constraint["Metric"] == "Maximum demand from alternative fuels", :
    ]
    df_af_constraint = pd.melt(
        frame=df_af_constraint,
        id_vars="region",
        value_vars=MODEL_YEARS,
        var_name="year",
        value_name="value",
    )
    df_af_constraint = set_datatypes(
        df=df_af_constraint, datatypes_per_column=DF_DATATYPES_PER_COLUMN
    )
    # convert from [t Clk / year] to [Mt Clk / year]
    df_af_constraint["value"] *= 1e-6
    importer.export_data(
        df=df_af_constraint,
        filename="alternative_fuel_constraint.csv",
        export_dir="intermediate",
        index=False,
    )
    # Unit df_af_constraint: [Mt Clk / year]


def _get_initial_asset_stack(
    importer: IntermediateDataImporter, product: list
) -> pd.DataFrame():
    """
    Creates the initial_asset_stack dataframe
    Args:
        importer (): Unit per relevant dataframe:
            plant_capacity: [t Clk / day]

    Returns:
        df_initial_asset_stack (): Unit per column:
            annual_production_capacity: [t Clk / year]
            capacity_utilisation_factor: [%]
    """

    imported_input_data = importer.get_imported_input_data(
        input_metrics=INPUT_METRICS,
        index=True,
        idx_per_input_metric=IDX_PER_INPUT_METRIC,
    )

    assert len(product) == 1, "More than one product for Clinker!"
    product = product[0]

    # import required data
    df_plant_capacity = imported_input_data["plant_capacity"]
    df_capacity_factor = imported_input_data["capacity_factor"]
    df_start_technologies = importer.get_start_technologies()
    df_demand = importer.get_demand()

    # filter for model start year
    df_plant_capacity = df_plant_capacity.xs(key=START_YEAR, level="year")
    df_capacity_factor = df_capacity_factor.xs(key=START_YEAR, level="year")
    df_demand = df_demand.loc[df_demand["year"] == START_YEAR, :]

    # transform df_plant_capacity's unit from [t Clk / day] to [t Clk / year]
    df_plant_capacity *= 365

    df_initial_asset_stack = pd.DataFrame(
        columns=[
            "region",
            "country",
            "coordinates",
            "product",
            "technology",
            "annual_production_capacity",
            "year_commissioned",
            "capacity_factor",
        ]
    )
    df_initial_asset_stack = df_initial_asset_stack.astype(
        dtype={
            "region": str,
            "country": str,
            "coordinates": str,
            "product": str,
            "technology": str,
            "annual_production_capacity": float,
            "year_commissioned": int,
            "capacity_factor": float,
        }
    )

    df_list = []
    for region in REGIONS:
        for technology in [
            x for x in list(df_start_technologies) if x in LIST_TECHNOLOGIES
        ]:
            init_tech_share = df_start_technologies.loc[
                df_start_technologies["region"] == region, technology
            ].squeeze()
            demand = df_demand.loc[df_demand["region"] == region, "value"].squeeze() * (
                init_tech_share / 100
            )
            """plant_capacity = df_plant_capacity.xs(
                key=(region, technology), level=("region", "technology_destination")
            ).squeeze()"""
            capacity_factor = df_capacity_factor.xs(
                key=(region, technology), level=("region", "technology_destination")
            ).squeeze()
            plant_capacity = ASSUMED_ANNUAL_PRODUCTION_CAPACITY
            # round up to have a small overshoot in production volume rather than not fulfilling demand
            n_plants = int(np.ceil((demand / (plant_capacity * capacity_factor))))
            # create plants
            df_append = df_initial_asset_stack.copy()
            df_append["annual_production_capacity"] = n_plants * [plant_capacity]
            df_append["technology"] = technology
            df_append["capacity_factor"] = capacity_factor
            df_append["region"] = region
            df_list.append(df_append)

    df_initial_asset_stack = pd.concat(df_list)
    df_initial_asset_stack["product"] = product
    df_initial_asset_stack["year_commissioned"] = AVERAGE_PLANT_COMMISSION_YEAR

    return df_initial_asset_stack

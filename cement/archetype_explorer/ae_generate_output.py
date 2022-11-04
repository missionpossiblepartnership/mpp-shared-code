"""
1 remove reference plant
2 add columns for all contextual parameters
3 add abatement potential
4 merge all sensitivities
"""

import pandas as pd
from pathlib import Path

from cement.config.config_cement import PRODUCTS

from cement.archetype_explorer.ae_config import AE_SENSITIVITY_MAPPING

from mppshared.config import LOG_LEVEL
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def ae_aggregate_outputs(
    runs: list,
    sector: str,
):
    """Aggregates and exports all outputs from all runs"""

    df_list = []

    for pathway_name, sensitivity in runs:

        logger.info(f"Aggregating outputs for {pathway_name}_{sensitivity}")

        sensitivity_params = AE_SENSITIVITY_MAPPING[sensitivity]

        importer = IntermediateDataImporter(
            pathway_name=pathway_name,
            sensitivity=sensitivity,
            sector=sector,
            products=PRODUCTS,
        )

        df = importer.get_technologies_to_rank()

        # filter brownfield
        df = df.loc[
            (df["switch_type"] == "brownfield_renovation"),
            [x for x in df.columns if x != "switch_type"]
        ]

        # add LCOC for technology_origin and LCOC delta
        df_lcoc = importer.get_lcox()
        # todo

        # add sensitivity columns
        cols = list(sensitivity_params.keys()) + list(df.columns)
        for key in sensitivity_params.keys():
            df[key] = sensitivity_params[key]
        df = df[cols]

        # add to df_list
        df_list.append(df.reset_index(drop=True))

    # aggregate
    df = pd.concat(df_list).reset_index(drop=True)

    # export
    export_path = (
        f"{Path(__file__).resolve().parents[2]}/{sector}/data/{pathway_name}/ae_aggregated_outputs.csv"
    )
    df.to_csv(export_path, index=False)

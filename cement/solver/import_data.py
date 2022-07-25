"""import and pre-process all input files"""

from cement.config.config_cement import MODEL_YEARS, PRODUCTS
from mppshared.config import SECTOR
from mppshared.import_data.import_data import import_all
from mppshared.import_data.intermediate_data import IntermediateDataImporter


def import_and_preprocess(pathway: str, sensitivity: str):

    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=SECTOR,
        products=PRODUCTS,
    )

    import_all(
        importer=importer,
        model_years=MODEL_YEARS
    )

"""import and pre-process all input files"""

from mppshared.config import PRODUCTS, SECTOR
from mppshared.import_data.import_data import import_all
from mppshared.import_data.intermediate_data import IntermediateDataImporter


def import_and_preprocess(pathway: str, sensitivity: str):

    importer = IntermediateDataImporter(
        pathway=pathway,
        sensitivity=sensitivity,
        sector=SECTOR,
        products=PRODUCTS[SECTOR],
    )

    import_all(
        importer=importer,
    )

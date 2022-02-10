"""Configuration file for the library."""
import logging

# Define Data Path
CORE_DATA_PATH = "mppshared/data"
LOG_PATH = "logs/"
IMPORT_DATA_PATH = f"{CORE_DATA_PATH}/import_data"
OUTPUT_FOLDER = f"{CORE_DATA_PATH}/output_data"
PKL_FOLDER = f"{CORE_DATA_PATH}/pkl_data"
PKL_DATA_IMPORTS = f"{PKL_FOLDER}/imported_data"
PKL_DATA_INTERMEDIATE = f"{PKL_FOLDER}/intermediate_data"
PKL_DATA_FINAL = f"{PKL_FOLDER}/final_data"

# Log formatter
LOG_FORMATTER = logging.Formatter(
    "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)

FOLDERS_TO_CHECK_IN_ORDER = [
    # Top level folders
    CORE_DATA_PATH,
    LOG_PATH,
    # Second level folders
    IMPORT_DATA_PATH,
    PKL_FOLDER,
    OUTPUT_FOLDER,
    # Third level folders
    PKL_DATA_IMPORTS,
    PKL_DATA_INTERMEDIATE,
    PKL_DATA_FINAL,
]

PE_MODEL_FILENAME_DICT = {
    "power": "Power Model.xlsx",
    "ccus": "CCUS Model.xlsx",
    "hydrogen": "H2 Model.xlsx",
}

PE_MODEL_SHEETNAME_DICT = {
    "power": ["GridPrice", "GridEmissions", "RESPrice"],
    "ccus": ["Transport", "Storage"],
    "hydrogen": ["Prices", "Emissions"],
}

MPP_COLOR_LIST = [
    "#A0522D",
    "#7F6000",
    "#1E3B63",
    "#9DB1CF",
    "#FFC000",
    "#59A270",
    "#BCDAC6",
    "#E76B67",
    "#A5A5A5",
    "#F2F2F2",
]

NEW_COUNTRY_COL_LIST = [
    "country_code",
    "country",
    "official_name",
    "m49_code",
    "region",
    "continent",
    "wsa_region",
    "rmi_region",
]

NEW_COUNTRY_COL_LIST = [
    "country_code",
    "country",
    "official_name",
    "m49_code",
    "region",
    "continent",
    "wsa_region",
    "rmi_region",
]

FILES_TO_REFRESH = []

EU_COUNTRIES = [
    "AUT",
    "BEL",
    "BGR",
    "CYP",
    "CZE",
    "DEU",
    "DNK",
    "ESP",
    "EST",
    "FIN",
    "FRA",
    "GRC",
    "HRV",
    "HUN",
    "IRL",
    "ITA",
    "LTU",
    "LUX",
    "LVA",
    "MLT",
    "NLD",
    "POL",
    "PRT",
    "ROU",
    "SVK",
    "SVN",
    "SWE",
]

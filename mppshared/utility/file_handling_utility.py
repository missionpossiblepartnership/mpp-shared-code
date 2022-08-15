"""Script for handling files and folder"""

import os
import pickle
from pathlib import Path
from typing import Union

import pandas as pd

from mppshared.config import LOG_LEVEL
from mppshared.utility.log_utility import get_logger

logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def read_pickle_folder(
    data_path: str, pkl_file: str = "", mode: str = "dict", log: bool = False
) -> Union[pd.DataFrame, dict]:
    """Reads a path where pickle files are stores and saves them to a dictionary
    Args:
        data_path (str): A path in the repository where pickle files are stored
        pkl_file (str, optional): The file you want to unpickle. Defaults to "".
        mode (str, optional): Describes the unpickled format: A dictionary (dict) or a DataFrame (df). Defaults to "dict".
        log (bool, optional): Optional flag to log file read. Defaults to False.
    Returns:
        Union[pd.DataFrame, dict]: A DataFrame or a Dictionary object depending on `mode`.
    """

    if pkl_file:
        mode = "df"

    if mode == "df":
        if log:
            logger.info(f"||| Loading pickle file {pkl_file} from path {data_path}")
        with open(rf"{data_path}/{pkl_file}.pickle", "rb") as f:
            return pickle.load(f)

    elif mode == "dict":
        if log:
            logger.info(f"||| Loading pickle files from path {data_path}")
        new_data_dict = {}
        for pkl_file in os.listdir(data_path):
            if log:
                logger.info(f"|||| Loading {pkl_file}")
            with open(rf"{data_path}/{pkl_file}", "rb") as f:
                new_data_dict[pkl_file.split(".")[0]] = pickle.load(f)
        return new_data_dict


def extract_data(
    data_path: str,
    filename: str,
    ext: str,
    sheet: Union[int, str] = None,
    dtype: Union[str, dict] = None,
    first_row: int = 0,
) -> pd.DataFrame:
    """Extracts data from excel or csv files based on input parameters
    Args:
        data_path (str): path where data files are stored
        filename (str): name of file to extract (without extension)
        ext (str): extension of the file to extract
        sheet (int or str): Number (int; starting with 0) or name (str) of the sheet to extract. For xlsx (workbook)
            files only.
        dtype (defaults to None): Defines the data type of the imported dataframe. Must be a type name or dict of type
            names per column.
        first_row (int, defaults to None): First row (0-indexed) in csv / xlsx file that contains data
    Returns:
        DataFrame: A dataframe of the data file
    """
    # Full path of the file
    full_filename = rf"{data_path}/{filename}.{ext}"
    # If else logic that determines which pandas function to call based on the extension
    logger.info(f"|| Extracting file {filename}.{ext}")
    if ext == "xlsx":
        return pd.read_excel(
            io=full_filename, sheet_name=sheet, dtype=dtype, header=first_row
        )
    elif ext == "csv":
        return pd.read_csv(
            filepath_or_buffer=full_filename, dtype=dtype, header=first_row
        )


def serialize_file(obj, pkl_folder: str, filename: str) -> None:
    """Serializes a file using the pickle protocol.
    Args:
        obj: The object that you want to serialize.
        pkl_folder (str): The folder where you want to store the pickle file.
        filename (str): The name of the file you want to use (do not include a file extension in the string)
    """
    with open(f"{pkl_folder}/{filename}.pickle", "wb") as f:
        # Pickle the 'data' using the highest protocol available.
        logger.info(f"* Saving Pickle file {filename} to path")
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)


def serialize_df_dict(data_path: str, data_dict: dict) -> None:
    """Iterate through each df and store the file as pickle or feather. Does not return any object.
    Args:
        data_dict (dict): A data dictionary where the DataFrames are stored
        data_path (str): The path where the pickle files will be stored
    """
    logger.info(f"||| Serializing each df to a pickle file {data_path}")
    for df_name in data_dict:
        serialize_file(data_dict[df_name], data_path, df_name)


def create_folders_if_nonexistent(folder_list: list) -> None:
    """For each path in the `folder_list`, check if the folder already exists and create it if it doesn't exist.
    Args:
        folder_list (list): A list of folder paths to check.
    """
    for folder_path in folder_list:
        if os.path.isdir(folder_path):
            logger.info(f"{folder_path} already exists")
        else:
            logger.info(f"{folder_path} does not exist yet. Creating folder.")
            Path(folder_path).mkdir(parents=True, exist_ok=True)


def pickle_to_csv(
    csv_folder: str, pkl_folder: str, pkl_filename: str, csv_filename: str = ""
) -> None:
    """Checks a folder path where a pickled DataFrame is stored. Loads the DataFrame and converts it to a .csv file.
    Args:
        csv_folder (str): The path where you want to save the .csv file.
        pkl_folder (str): The path where the pickled DataFrame is stored.
        pkl_filename (str): The name of the pickle file you want to load. (No .pkl/.pickle extension necessary).
        csv_filename (str, optional): The name of the newly created csv file. (No .csv extension necessary). If none, defaults to pickle_filename. Defaults to "".
    """
    df = read_pickle_folder(pkl_folder, pkl_filename)
    logger.info(
        f"||| Saving {pkl_filename} pickle file as {csv_filename or pkl_filename}.csv"
    )
    if csv_filename:
        df.to_csv(f"{csv_folder}/{csv_filename}.csv", index=False)
    else:
        df.to_csv(f"{csv_folder}/{pkl_filename}.csv", index=False)

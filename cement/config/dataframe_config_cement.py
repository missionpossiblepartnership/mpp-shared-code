"""dataframe config"""


# dict to define datatypes of columns
DF_DATATYPES_PER_COLUMN = {
    "product": str,
    "year": int,
    "region": str,
    "technology_origin": str,
    "technology_destination": str,
    "switch_type": str,
    "cost_classification": str,
    "emissivity_type": str,
    "scope": str,
    "metric": str,
    "unit": str,
    "value": float,
}


"""define indices"""


# raw data
# Set index per metric (and columns to import from Business Cases.xlsx for each metric in addition to MODEL_YEARS)
standard_idx_prefix = ["product", "region", "year"]
standard_idx_suffix = ["metric", "unit"]
IDX_PER_INPUT_METRIC = {
    # technology cards
    "capex": standard_idx_prefix
    + [
        "technology_destination",
        "cost_classification",
    ]
    + standard_idx_suffix,
    "opex": standard_idx_prefix
    + ["technology_destination", "cost_classification"]
    + standard_idx_suffix,
    "wacc": standard_idx_prefix + ["technology_destination"] + standard_idx_suffix,
    "capacity_factor": standard_idx_prefix
    + ["technology_destination"]
    + standard_idx_suffix,
    "lifetime": standard_idx_prefix + ["technology_destination"] + standard_idx_suffix,
    "trl_current": standard_idx_prefix
    + ["technology_destination"]
    + standard_idx_suffix,
    "expected_maturity": standard_idx_prefix
    + ["technology_destination"]
    + standard_idx_suffix,
    "tech_classification": standard_idx_prefix
    + ["technology_destination"]
    + standard_idx_suffix,
    "inputs_material": standard_idx_prefix
    + ["technology_destination"]
    + standard_idx_suffix,
    "inputs_energy": standard_idx_prefix
    + ["technology_destination"]
    + standard_idx_suffix,
    "capture_rate": standard_idx_prefix
    + ["technology_destination"]
    + standard_idx_suffix,
    "plant_capacity": standard_idx_prefix
    + ["technology_destination"]
    + standard_idx_suffix,
    # emissivity
    "emissivity_co2": standard_idx_prefix
    + ["emissivity_type", "scope"]
    + standard_idx_suffix,
    "emissivity_ch4": standard_idx_prefix
    + ["emissivity_type", "scope"]
    + standard_idx_suffix,
    # commodity prices
    "commodity_prices": standard_idx_prefix
    + ["cost_classification"]
    + standard_idx_suffix,
}

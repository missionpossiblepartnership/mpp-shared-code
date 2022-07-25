"""Import config"""


### generic ###

# regions
REGIONS = {
    "cement": [
        "China",
        "Rest of Asia",
        "North America",
        "Russia",
        "Europe",
        "India",
        "Middle East",
        "Africa",
        "Latin America",
        "Oceania",
    ]
}


### Business case excel ###

# header line
HEADER_BUSINESS_CASE_EXCEL = {
    "cement": 5,
}

# List of input sheets in Business Cases.xlsx (do not change order)
INPUT_SHEETS = {
    "cement": [
        "Technology switching table",
        "Technology cards",
        "Region CAPEX mapping",
        "Shared inputs - Prices",
        "Shared inputs - Emissivity",
    ]
}

# Column ranges
EXCEL_COLUMN_RANGES = {
    "cement": {
        # todo: check again when structure of Business case excel is final
        "Technology switching table": "C:AA",
        "Technology cards": "B:AT",
        "Region CAPEX mapping": "B:W",
        "Shared inputs - Prices": "B:AS",
        "Shared inputs - Emissivity": "B:AS",
    }
}

# name of column that determines whether metric has single value (rather than annual values)
COLUMN_SINGLE_INPUT = {"cement": "Single input (yes/no)"}

# Names of DataFrames created from imported data, indexed by sheet name in Business Cases.xlsx
INPUT_METRICS = {
    "cement": {
        "Technology cards": [
            "capex",
            "opex",
            "wacc",
            "capacity_factor",
            "lifetime",
            "trl_current",
            "expected_maturity",
            "tech_classification",
            "inputs_material",
            "inputs_energy",
            "plant_capacity",
            "capture_rate",
        ],
        "Shared inputs - Emissivity": [
            "emissivity_co2",
            "emissivity_ch4",
        ],
        "Shared inputs - Prices": ["commodity_prices"],
    }
}

# DataFrames are extracted based on columns ["Metric type", "Metric"] in Business Cases.xlsx
MAP_EXCEL_NAMES = {
    "cement": {
        # technology cards
        "capex": ["Capex", None],
        "opex": ["Opex", None],
        "wacc": ["WACC", "Real WACC"],
        "capacity_factor": ["CF", "Capacity factor"],
        "lifetime": ["Lifetime", "Lifetime"],
        "trl_current": ["TRL", "Current TRL"],
        "expected_maturity": ["TRL", "Expected maturity (TRL>=8)"],
        "tech_classification": ["Classification", "Technology classification"],
        "inputs_material": ["Raw material", None],
        "inputs_energy": ["Energy", None],
        "capture_rate": ["Capture rate", "CO2 capture rate"],
        "plant_capacity": ["Plant capacity", "Average plant capacity"],
        # emissivity
        "emissivity_co2": ["CO2 Emissivity", None],
        "emissivity_ch4": ["CH4 Emissivity", None],
        # commodity prices
        "commodity_prices": ["Commodity prices", None],
    }
}

# Renaming of columns to follow naming convention
MAP_COLUMN_NAMES = {
    "Unit": "unit",
    "Product": "product",
    "Technology": "technology_destination",
    "Technology origin": "technology_origin",
    "Renovation from": "technology_origin",
    "Region": "region",
    "Metric": "metric",
    "Scope": "scope",
    "Cost classification": "cost_classification",
    "Emissivity type": "emissivity_type",
}

# Set index per metric (and columns to import from Business Cases.xlsx for each metric in addition to MODEL_YEARS)
standard_idx_prefix = ["product", "region", "year"]
standard_idx_suffix = ["metric", "unit"]
IDX_PER_INPUT_METRIC = {
    "cement": {
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
        "lifetime": standard_idx_prefix
        + ["technology_destination"]
        + standard_idx_suffix,
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
}

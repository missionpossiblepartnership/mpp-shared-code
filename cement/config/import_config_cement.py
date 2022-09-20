"""Import config"""


### Business case excel ###

# header line
HEADER_BUSINESS_CASE_EXCEL = 5

# List of input sheets in Business Cases.xlsx (do not change order)
INPUT_SHEETS = [
    "Technology switching table",
    "Technology cards",
    "Region CAPEX mapping",
    "Shared inputs - Prices",
    "Shared inputs - Emissivity",
]

# Column ranges
EXCEL_COLUMN_RANGES = {
    # todo: check again when structure of Business case excel is final
    "Technology switching table": "C:AI",
    "Technology cards": "B:AT",
    "Region CAPEX mapping": "B:AE",
    "Shared inputs - Prices": "B:AS",
    "Shared inputs - Emissivity": "B:AS",
    "Start technologies": "B:F",
    "Region OPEX mapping": "B:F",
    "demand": "B:AS",
    "Biomass": "B:AK",
    "CO2 storage capacity": "B:AK",
}

# name of column that determines whether metric has single value (rather than annual values)
COLUMN_SINGLE_INPUT = "Single input (yes/no)"

# Names of DataFrames created from imported data, indexed by sheet name in Business Cases.xlsx
INPUT_METRICS = {
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

# DataFrames are extracted based on columns ["Metric type", "Metric"] in Business Cases.xlsx
MAP_EXCEL_NAMES = {
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

MAP_SWITCH_TYPES_TO_CAPEX_TYPE = {
    "Greenfield Capex": "greenfield",
    "Rebuild Capex": "brownfield_rebuild",
    "Renovation Capex": "brownfield_renovation",
    "Decommission Capex": "decommission",
}


### variable OPEX ###

# set of input energy metrics that are included in variable OPEX
OPEX_ENERGY_METRICS = [
    "Coal",
    "Natural gas",
    "Alternative fuels (H2)",
    "Alternative fuels (excl. H2)",
    "Electricity - grid",
    "Waste of fossil origin (including fossil fuel from mixed fuels)",
    "Biomass (including biomass from mixed fuels)",
    "Hydrogen",
]

# set of input materials that are included in variable OPEX
OPEX_MATERIALS_METRICS = ["Raw meal"]

OPEX_CCUS_CONTEXT_METRICS = {
    "transport": "CCS - Transport",
    "storage": "CCS - Storage",
    "carbon_price": "CO2",
}

# emissivity metric types that are relevant for computing the CCU/S OPEX
OPEX_CCUS_EMISSIVITY_METRIC_TYPES = ["emissivity_co2"]

# emissivity metrics that are relevant for computing the CCU/S emissivity
OPEX_CCUS_EMISSIVITY_METRICS = [
    "Calcination process emissions",
    "Coal",
    "Natural gas",
    "Waste of fossil origin (including fossil fuel from mixed fuels)",
    "Biomass (including biomass from mixed fuels)",
]

# energy metrics that are included in the CCU/S process OPEX.
OPEX_CCUS_PROCESS_METRICS_ENERGY = [
    # values of this dict must always be dicts with 2 keys!
    {
        "commodity_prices": ("Electricity - grid",),
        "inputs_energy": ("CC Electricity - grid",),
    },
    {
        "commodity_prices": ("Coal",),
        "inputs_energy": ("CC Coal",),
    },
    {
        "commodity_prices": ("Natural gas",),
        "inputs_energy": ("CC Natural gas",),
    },
    {
        "commodity_prices": (
            "Waste of fossil origin (including fossil fuel from mixed fuels)",
        ),
        "inputs_energy": (
            "CC Waste of fossil origin (including fossil fuel from mixed fuels)",
        ),
    },
    {
        "commodity_prices": ("Biomass (including biomass from mixed fuels)",),
        "inputs_energy": ("CC Biomass (including biomass from mixed fuels)",),
    },
    {
        "commodity_prices": ("Hydrogen",),
        "inputs_energy": ("CC Hydrogen",),
    },
]

# material metrics that are included in the CCU/S process OPEX.
OPEX_CCUS_PROCESS_METRICS_MATERIAL = [
    # values of this dict must always be dicts with 2 keys!
    {
        "commodity_prices": ("CC - MEA make up stream",),
        "inputs_material": ("CC - MEA make up stream",),
    },
    {
        "commodity_prices": ("CC - Process water",),
        "inputs_material": ("CC - Process water",),
    },
    {
        "commodity_prices": ("CC - Cooling water",),
        "inputs_material": ("CC - Cooling water",),
    },
]

### initial asset stack ###
AVERAGE_PLANT_COMMISSION_YEAR = 2005

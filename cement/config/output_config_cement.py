# define colours for different technologies
TECHNOLOGY_LAYOUT = {
    # ref
    "Dry kiln reference plant": None,
    # coal
    "Dry kiln coal": "#4d2000",
    "Dry kiln coal + post combustion + storage": "#662b00",
    "Dry kiln coal + post combustion + usage": "#803500",
    "Dry kiln coal + oxyfuel + storage": "#994000",
    "Dry kiln coal + oxyfuel + usage": "#9e4200",
    "Dry kiln coal + direct separation + storage": "#b34a00",
    "Dry kiln coal + direct separation + usage": "#cc5500",
    # natural gas
    "Dry kiln natural gas": "#800000",
    "Dry kiln natural gas + post combustion + storage": "#990000",
    "Dry kiln natural gas + post combustion + usage": "#b30000",
    "Dry kiln natural gas + oxyfuel + storage": "#bb0000",
    "Dry kiln natural gas + oxyfuel + usage": "#cc0000",
    "Dry kiln natural gas + direct separation + storage": "#e60000",
    "Dry kiln natural gas + direct separation + usage": "#ff0000",
    # alternative fuels 43%
    "Dry kiln alternative fuels 43%": "#000080",
    "Dry kiln alternative fuels (43%) + post combustion + storage": "#0000b3",
    "Dry kiln alternative fuels (43%) + post combustion + usage": "#0000ff",
    "Dry kiln alternative fuels (43%) + oxyfuel + storage": "#1a1aff",
    "Dry kiln alternative fuels (43%) + oxyfuel + usage": "#4d4dff",
    "Dry kiln alternative fuels (43%) + direct separation + storage": "#6666ff",
    "Dry kiln alternative fuels (43%) + direct separation + usage": "#9999ff",
    # alternative fuels 90%
    "Dry kiln alternative fuels 90%": "#008080",
    "Dry kiln alternative fuels (90%) + post combustion + storage": "#009999",
    "Dry kiln alternative fuels (90%) + post combustion + usage": "#00b3b3",
    "Dry kiln alternative fuels (90%) + oxyfuel + storage": "#00cccc",
    "Dry kiln alternative fuels (90%) + oxyfuel + usage": "#00e6e6",
    "Dry kiln alternative fuels (90%) + direct separation + storage": "#00ffff",
    "Dry kiln alternative fuels (90%) + direct separation + usage": "#b3ffff",
    # electric & H2
    "Electric kiln + direct separation": "#33cc33",
    "Dry kiln + Hydrogen + direct separation": "#336600",
}

# define and map resource consumption metrics
RESOURCE_CONSUMPTION_METRICS = {
    "Biomass (including biomass from mixed fuels)": [
        "Biomass (including biomass from mixed fuels)",
        "CC Biomass (including biomass from mixed fuels)",
    ],
    "Coal": ["Coal", "CC Coal"],
    "Electricity": [
        "Electricity - grid",
        "CC Electricity - grid",
        "Electricity - on site VREs",
        "CC Electricity - on site VREs",
    ],
    "Hydrogen": ["Hydrogen", "CC Hydrogen"],
    "Natural gas": ["Natural gas", "CC Natural gas"],
    "Waste of fossil origin (including fossil fuel from mixed fuels)": [
        "Waste of fossil origin (including fossil fuel from mixed fuels)",
        "CC Waste of fossil origin (including fossil fuel from mixed fuels)",
    ],
    "Alternative fuels": [
        "Biomass (including biomass from mixed fuels)",
        "CC Biomass (including biomass from mixed fuels)",
        "Waste of fossil origin (including fossil fuel from mixed fuels)",
        "CC Waste of fossil origin (including fossil fuel from mixed fuels)",
        "Hydrogen",
        "CC Hydrogen",
    ],
}

# define mapping from technology with carbon capture to its corresponding initial technology
MAP_EMISSION_FACTOR_PRE_CAPTURE = {
    "Dry kiln reference plant": None,
    "Dry kiln coal": None,
    "Dry kiln natural gas": None,
    "Dry kiln alternative fuels 43%": None,
    "Dry kiln alternative fuels 90%": None,
    "Dry kiln coal + post combustion + storage": "Dry kiln coal",
    "Dry kiln natural gas + post combustion + storage": "Dry kiln natural gas",
    "Dry kiln alternative fuels (43%) + post combustion + storage": "Dry kiln alternative fuels 43%",
    "Dry kiln alternative fuels (90%) + post combustion + storage": "Dry kiln alternative fuels 90%",
    "Dry kiln coal + oxyfuel + storage": "Dry kiln coal",
    "Dry kiln natural gas + oxyfuel + storage": "Dry kiln natural gas",
    "Dry kiln alternative fuels (43%) + oxyfuel + storage": "Dry kiln alternative fuels 43%",
    "Dry kiln alternative fuels (90%) + oxyfuel + storage": "Dry kiln alternative fuels 90%",
    "Dry kiln coal + direct separation + storage": "Dry kiln coal",
    "Dry kiln natural gas + direct separation + storage": "Dry kiln natural gas",
    "Dry kiln alternative fuels (43%) + direct separation + storage": "Dry kiln alternative fuels 43%",
    "Dry kiln alternative fuels (90%) + direct separation + storage": "Dry kiln alternative fuels 90%",
    "Dry kiln coal + post combustion + usage": "Dry kiln coal",
    "Dry kiln natural gas + post combustion + usage": "Dry kiln natural gas",
    "Dry kiln alternative fuels (43%) + post combustion + usage": "Dry kiln alternative fuels 43%",
    "Dry kiln alternative fuels (90%) + post combustion + usage": "Dry kiln alternative fuels 90%",
    "Dry kiln coal + oxyfuel + usage": "Dry kiln coal",
    "Dry kiln natural gas + oxyfuel + usage": "Dry kiln natural gas",
    "Dry kiln alternative fuels (43%) + oxyfuel + usage": "Dry kiln alternative fuels 43%",
    "Dry kiln alternative fuels (90%) + oxyfuel + usage": "Dry kiln alternative fuels 90%",
    "Dry kiln coal + direct separation + usage": "Dry kiln coal",
    "Dry kiln natural gas + direct separation + usage": "Dry kiln natural gas",
    "Dry kiln alternative fuels (43%) + direct separation + usage": "Dry kiln alternative fuels 43%",
    "Dry kiln alternative fuels (90%) + direct separation + usage": "Dry kiln alternative fuels 90%",
    "Electric kiln + direct separation": "process_only",
    "Dry kiln + Hydrogen + direct separation": "process_only",
}

ASSUMED_CARBON_CAPTURE_RATE = 0.95

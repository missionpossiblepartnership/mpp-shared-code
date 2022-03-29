""" Functions for demand balances. """

from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.models.plant import PlantStack


def get_demand_balance(
    pathway: SimulationPathway,
    current_stack: PlantStack,
    product: str,
    year: int,
    region: str,
) -> float:
    """Calculate balance between production of the AssetStack and demand in the given region in a given year

    Args:
        pathway: contains demand data
        current_stack: contains production assets
        product: product for demand balance
        year: year for demand balance
        region: region for demand balance

    Returns:
        float: demand - production
    """
    demand = pathway.get_demand(product, year, region)
    production = current_stack.get_yearly_volume(product)
    balance = demand - production
    return balance

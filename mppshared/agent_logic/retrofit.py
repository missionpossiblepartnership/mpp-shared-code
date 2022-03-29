""" Logic for technology transitions of type brownfield rebuild and brownfield renovation."""

from mppshared.models.simulation_pathway import SimulationPathway


def retrofit(pathway: SimulationPathway, year: int, product: str) -> SimulationPathway:
    """Apply brownfield rebuild or brownfield renovation transition to eligible Assets in the AssetStack.

    Args:
        pathway: decarbonization pathway that describes the composition of the AssetStack in every year of the model horizon
        year: current year in which technology transitions are enacted
        product: product for which technology transitions are enacted

    Returns:
        Updated decarbonization pathway with the updated AssetStack in the subsequent year according to the retrofits enacted
    """

    # Get AssetStack in current and next year
    old_stack = pathway.get_stack(year=year)
    new_stack = pathway.get_stack(year=year + 1)

    # Get ranking table and filter for all assets that are eligible for retrofit
    df_rank = pathway.get_ranking(year=year, product=product, rank_type="retrofit")

    # Selected assets eligible for retrofit

    return pathway

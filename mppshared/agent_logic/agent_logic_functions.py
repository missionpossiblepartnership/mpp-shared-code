""" Additional functions required for the agent logic, e.g. demand balances. """

from operator import methodcaller

import pandas as pd

from mppshared.config import (
    COST_METRIC_CUF_ADJUSTMENT,
    CUF_LOWER_THRESHOLD,
    CUF_UPPER_THRESHOLD,
    LOG_LEVEL,
    MODEL_SCOPE,
)
from mppshared.import_data.intermediate_data import IntermediateDataImporter
from mppshared.models.simulation_pathway import SimulationPathway
from mppshared.models.technology_rampup import TechnologyRampup
from mppshared.utility.utils import get_logger

logger = logger = get_logger(__name__)
logger.setLevel(LOG_LEVEL)


def select_best_transition(df_rank: pd.DataFrame) -> dict:
    """Based on the ranking, select the best transition

    Args:
        df_rank: contains column "rank" with ranking for each technology transition
        (minimum rank = optimal technology transition)

    Returns:
        The highest ranking technology transition

    """
    # Best transition has minimum rank (if same rank, chosen randomly with sample)
    return (
        df_rank[df_rank["rank"] == df_rank["rank"].min()]
        .sample(n=1)
        .to_dict(orient="records")
    )[0]


def remove_transition(df_rank: pd.DataFrame, transition: dict) -> pd.DataFrame:
    """Filter transition from ranking table.

    Args:
        df_rank: table with ranking of technology switches
        transition: row from the ranking table

    Returns:
        ranking table with the row corresponding to the transition removed
    """
    return df_rank.loc[
        ~(df_rank[list(transition)] == pd.Series(transition)).all(axis=1)
    ]


def remove_all_transitions_with_destination_technology(
    df_rank: pd.DataFrame, technology_destination: str
) -> pd.DataFrame:
    """Remove all transitions with a specific destination technology from the ranking table. This is done when the transition for this technology hits the technology ramp-up constraint."""
    df_rank = df_rank.loc[
        ~(df_rank["technology_destination"] == technology_destination)
    ]
    return df_rank


def remove_transition_in_region_by_tech_substr(
    df_rank: pd.DataFrame, transition: dict, tech_substr: str
) -> pd.DataFrame:

    df_rank = df_rank.loc[
        ~(
            df_rank["region"]
            == transition["region"]
            & df_rank["technology_destination"].str.contains(tech_substr)
        ),
        :,
    ]

    return df_rank


def adjust_capacity_utilisation(
    pathway: SimulationPathway, year: int
) -> SimulationPathway:
    """Adjust capacity utilisation of each asset based on a predefined cost metric (LCOX or marginal cost of production) within predefined thresholds to balance demand
    and production as much as possible in the given year.

    Args:
        pathway: pathway with AssetStack and demand data for the specified year
        product:
        year:

    Returns:
        pathway with updated capacity factor for each Asset in the AssetStack of the given year
    """

    # Adjust capacity utilisation for each product
    for product in pathway.products:

        # Get demand and production in that year
        demand = pathway.get_demand(product=product, year=year, region=MODEL_SCOPE)
        stack = pathway.get_stack(year=year)
        production = stack.get_annual_production_volume(product)

        # TODO: make sure that CUF adjustment does not overshoot demand and production balance
        # If demand exceeds production, increase capacity utilisation of each asset to make production
        # deficit as small as possible, starting at the asset with the lowest cost metric
        if demand > production:
            logger.info(
                f"Increasing capacity utilisation of {product} assets to minimise production deficit"
            )
            pathway = increase_cuf_of_assets(
                pathway=pathway,
                demand=demand,
                product=product,
                year=year,
                cost_metric=COST_METRIC_CUF_ADJUSTMENT[pathway.sector],
            )

        # If production exceeds demand, decrease capacity utilisation of each asset to make production
        # surplus as small as possible, starting at asset with highest cost metric
        elif production > demand:
            logger.info(
                f"Decreasing capacity utilisation of {product} assets to minimise production surplus"
            )
            pathway = decrease_cuf_of_assets(
                pathway=pathway,
                demand=demand,
                product=product,
                year=year,
                cost_metric=COST_METRIC_CUF_ADJUSTMENT[pathway.sector],
            )

        production = stack.get_annual_production_volume(product)

    return pathway


def increase_cuf_of_assets(
    pathway: SimulationPathway, demand: float, product: str, year: int, cost_metric: str
) -> SimulationPathway:
    """Increase CUF of assets to minimise the production deficit."""

    # Get AssetStack for the given year
    stack = pathway.get_stack(year)

    # Identify all assets that produce below CUF threshold and sort list so asset with lowest LCOX
    # is first
    assets_below_cuf_threshold = list(
        filter(lambda asset: asset.cuf < CUF_UPPER_THRESHOLD, stack.assets)
    )
    assets_below_cuf_threshold = sort_assets_cost_metric(
        assets_below_cuf_threshold, pathway, year, cost_metric
    )

    # Increase CUF of assets to upper threshold in order of ascending LCOX until production meets
    # demand or no assets left for CUF increase
    while demand > stack.get_annual_production_volume(product):

        if not assets_below_cuf_threshold:
            break

        # Increase CUF of asset with lowest LCOX to upper threshold and remove from list
        asset = assets_below_cuf_threshold[0]
        # logger.debug(f"Increase CUF of {str(asset)}")
        asset.cuf = CUF_UPPER_THRESHOLD
        assets_below_cuf_threshold.pop(0)

    return pathway


def decrease_cuf_of_assets(
    pathway: SimulationPathway, demand: float, product: str, year: int, cost_metric: str
) -> SimulationPathway:
    """Decrease CUF of assets to minimise the production surplus."""

    # Get AssetStack for the given year
    stack = pathway.get_stack(year)

    # Identify all assets that produce above CUF threshold and sort list so asset with highest
    assets_above_cuf_threshold = list(
        filter(lambda asset: asset.cuf > CUF_LOWER_THRESHOLD, stack.assets)
    )
    assets_above_cuf_threshold = sort_assets_cost_metric(
        assets_above_cuf_threshold, pathway, year, cost_metric, descending=True
    )

    # Decrease CUF of assets to lower threshold in order of descending LCOX until production meets
    # demand or no assets left for CUF decrease
    while stack.get_annual_production_volume(product) > demand:

        if not assets_above_cuf_threshold:
            break

        # Increase CUF of asset with lowest LCOX to upper threshold and remove from list
        asset = assets_above_cuf_threshold[0]
        # logger.debug(f"Decrease CUF of {str(asset)}")
        asset.cuf = CUF_LOWER_THRESHOLD
        assets_above_cuf_threshold.pop(0)

    return pathway


def sort_assets_cost_metric(
    assets: list,
    pathway: SimulationPathway,
    year: int,
    cost_metric: str,
    descending=False,
):
    """Sort list of assets according to a cost metric (LCOX or MC) in the specified year in ascending order"""
    return sorted(
        assets,
        key=methodcaller(f"get_{cost_metric}", df_cost=pathway.df_cost, year=year),
        reverse=descending,
    )


def create_dict_technology_rampup(
    importer: IntermediateDataImporter,
    model_start_year: int,
    model_end_year: int,
    maximum_asset_additions: int,
    maximum_capacity_growth_rate: float,
    years_rampup_phase: int,
) -> dict:
    """Create dictionary of TechnologyRampup objects with the technologies in that sector as keys. Set None if the technology has no ramp-up trajectory."""
    logger.info("Creating ramp-up trajectories for technologies")

    technology_characteristics = importer.get_technology_characteristics()
    technologies = technology_characteristics["technology"].unique()
    dict_technology_rampup = dict.fromkeys(technologies)

    for technology in technologies:

        # Expected maturity and classification are constant across regions, products and years, hence take the first row for that technology
        df_characteristics = technology_characteristics.loc[
            technology_characteristics["technology"] == technology
        ].iloc[0]
        expected_maturity = df_characteristics["expected_maturity"]
        classification = df_characteristics["technology_classification"]

        # Only define technology ramp-up rates for transition and end-state technologies
        if classification in ["transition", "end-state"]:
            dict_technology_rampup[technology] = TechnologyRampup(
                model_start_year=model_start_year,
                model_end_year=model_end_year,
                technology=technology,
                start_year=expected_maturity,
                end_year=expected_maturity + years_rampup_phase,
                maximum_asset_additions=maximum_asset_additions,
                maximum_capacity_growth_rate=maximum_capacity_growth_rate,
            )

    return dict_technology_rampup


def apply_regional_technology_ban(
    df_technology_switches: pd.DataFrame, sector_bans: dict
) -> pd.DataFrame:
    """Remove certain technologies from the technology switching table that are banned in certain regions (defined in config.py)"""
    if not sector_bans:
        return df_technology_switches
    for region in sector_bans.keys():
        banned_transitions = (df_technology_switches["region"] == region) & (
            df_technology_switches["technology_destination"].isin(sector_bans[region])
        )
        df_technology_switches = df_technology_switches.loc[~banned_transitions]
    return df_technology_switches

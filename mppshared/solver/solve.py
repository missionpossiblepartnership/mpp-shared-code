""" Execute the solver."""

from mppshared.config import SOLVER_INPUT_DATA_PATH
from mppshared.solver.implicit_forcing import apply_implicit_forcing
from mppshared.solver.input_loading import load_and_validate_inputs
from mppshared.solver.ranking import create_ranking


# TODO: which arguments are needed?
def solve(sector: str):

    # TODO: write a class for data handling
    # Load and validate input tables
    input_dfs = load_and_validate_inputs(sector)

    # Apply implicit forcing
    # TODO: implement caching or optional load from .csv
    df_ranking = apply_implicit_forcing(
        df_technology_switches=input_dfs["technology_switches"],
        df_emissions=input_dfs["emissions"],
        df_technology_characteristics=input_dfs["technology_characteristics"],
    )

    df_ranking.to_csv(SOLVER_INPUT_DATA_PATH + f"{sector}_ranking.csv")
    pass
    # Output of this should be a technology switching table with cost, emissions and characteristics

    # Create ranking
    # placeholder for the pathway
    # pathway = "bau"
    # sensitivity = 0
    # ranking = create_ranking(df_ranking, sensitivity, pathway)
    # # Find optimum technology switches year-by-year
    # Process outputs

    # Import carbon budget
    # Grid search

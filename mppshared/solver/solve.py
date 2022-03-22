""" Execute the solver."""

from mppshared.solver.implicit_forcing import apply_implicit_forcing, 
from mppshared.solver.input_loading import load_and_validate_inputs
from mppshared.config import SOLVER_INPUT_DATA_PATH


# TODO: which arguments are needed?
def solve(sector: str):

    # TODO: write a class for data handling
    # Load and validate input tables
    input_dfs = load_and_validate_inputs(sector)

    # Apply implicit forcing
    # TODO: implement caching or optional load from .csv
    # TODO: implement calculation of emission deltas
    df_ranking = apply_implicit_forcing(
        df_technology_switches=input_dfs["technology_switches"],
        df_emissions=input_dfs["emissions"],
        df_technology_characteristics=input_dfs["technology_characteristics"],
    )


    pass
    # Output of this should be a technology switching table with cost, emissions and characteristics

    # Create ranking
    # Find optimum technology switches year-by-year
    # Process outputs

    # Import carbon budget
    # Grid search

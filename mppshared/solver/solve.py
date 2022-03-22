""" Execute the solver."""

from mppshared.solver.implicit_forcing import apply_implicit_forcing
from mppshared.solver.input_loading import load_and_validate_inputs


# TODO: which arguments are needed?
def solve(sector: str):

    # Load and validate input tables
    input_dfs = load_and_validate_inputs(sector)

    # Apply implicit forcing
    input_dfs = apply_implicit_forcing(input_dfs)

    # Create ranking
    # Find optimum technology switches year-by-year
    # Process outputs

    # Import carbon budget
    # Grid search

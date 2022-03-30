""" Enforce constraints in the yearly optimization of technology switches."""

from pandera import Bool
from mppshared.models.plant import Plant, PlantStack


def check_constraints(stack: PlantStack) -> Bool:
    """Check all constraints for a given asset stack.

    Args:
        stack: stack of assets for which constraints are to be checked

    Returns:
        Returns True if no constraint hurt
    """
    # TODO: improve runtime by not applying all constraints to every agent logic

    # TODO: Check regional production constraint

    # TODO: Check technology ramp-up constraint

    # TODO: Check resource availability constraint

    #! Placeholder
    return True

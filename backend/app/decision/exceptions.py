"""Explicit failures for mixed or invalid decision inputs."""

class DecisionInputError(ValueError):
    """Confidence and clusters do not describe the same evaluation snapshot."""

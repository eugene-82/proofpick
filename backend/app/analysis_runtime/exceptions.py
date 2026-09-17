"""Controlled errors exposed by the demo runtime boundary."""


class AnalysisRuntimeError(RuntimeError):
    """Base runtime orchestration error."""


class AnalysisInputError(AnalysisRuntimeError):
    """The request cannot be resolved to one stable product."""


class AnalysisProviderUnavailableError(AnalysisRuntimeError):
    """A required external provider is missing or unavailable."""


class AnalysisIntegrityError(AnalysisRuntimeError):
    """Decision artifacts failed a downstream integrity boundary."""

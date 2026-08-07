class DailyVideoError(RuntimeError):
    """Base error for a failed pipeline operation."""


class ConfigurationError(DailyVideoError):
    """Configuration is missing or invalid."""


class ProviderUnavailable(DailyVideoError):
    """A provider cannot run in the current environment."""


class ProviderFailed(DailyVideoError):
    """A provider was available but failed its operation."""


class QualityGateFailed(DailyVideoError):
    """Generated content did not meet a mandatory quality or policy gate."""


class AlreadyPublished(DailyVideoError):
    """The requested publication date already has a completed upload."""


class SembleGrammarsError(Exception):
    """Base class for all semble-grammars errors."""


class UnsupportedPlatformError(SembleGrammarsError):
    """No compiled grammar bundle is available for the current platform."""


class LanguageNotFoundError(SembleGrammarsError):
    """The requested language is not present in the bundled manifest."""

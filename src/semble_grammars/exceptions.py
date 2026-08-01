class UnsupportedPlatformError(Exception):
    """No compiled grammar bundle is available for the current platform."""


class LanguageNotFoundError(Exception):
    """The requested language is not present in the bundled manifest."""


class GrammarLoadError(Exception):
    """A bundled native grammar library failed to load or returned an invalid language."""

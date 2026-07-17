import platform

from semble_grammars.exceptions import UnsupportedPlatformError

_OS_NAMES = {"darwin": "macos", "linux": "linux", "windows": "windows"}
_ARCH_NAMES = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x86_64", "amd64": "x86_64"}


def current_platform_tag() -> str:
    """Return the archive platform tag (e.g. ``macos-arm64``) for the running machine.

    :raises UnsupportedPlatformError: if the OS or architecture is not recognized.
    :returns: the platform tag used to select the bundled grammar archive.
    """
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system not in _OS_NAMES or machine not in _ARCH_NAMES:
        raise UnsupportedPlatformError(f"Unsupported platform: system={system!r}, machine={machine!r}")
    return f"{_OS_NAMES[system]}-{_ARCH_NAMES[machine]}"

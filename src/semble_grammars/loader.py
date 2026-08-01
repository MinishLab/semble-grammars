import ctypes
import json
import platform
import tarfile
from functools import lru_cache
from importlib import resources
from pathlib import Path

from tree_sitter import Language, Parser

from semble_grammars.cache import cache_dir, extract_atomic
from semble_grammars.exceptions import GrammarLoadError, LanguageNotFoundError, UnsupportedPlatformError

# Keep native libraries resident while their Language objects are in use.
_loaded_libraries: dict[Path, ctypes.CDLL] = {}

_ALIASES = {
    "py": "python",
    # Terraform files are valid HCL; there is no separate compiled grammar.
    "terraform": "hcl",
    "embeddedtemplate": "embedded_template",
    # Zsh is largely a superset of POSIX shell; there is no separate compiled grammar.
    "zsh": "bash",
}

_OS_NAMES = {"darwin": "macos", "linux": "linux", "windows": "windows"}
_ARCH_NAMES = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x86_64", "amd64": "x86_64"}


def _platform_tag() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system not in _OS_NAMES or machine not in _ARCH_NAMES:
        raise UnsupportedPlatformError(f"Unsupported platform: system={system!r}, machine={machine!r}")
    return f"{_OS_NAMES[system]}-{_ARCH_NAMES[machine]}"


@lru_cache(maxsize=1)
def _platform_manifest() -> dict:
    plat = _platform_tag()
    grammars_dir = resources.files("semble_grammars") / "grammars" / plat
    manifest_path = grammars_dir / "manifest.json"
    if not manifest_path.is_file():
        raise UnsupportedPlatformError(f"No bundled grammar archive for platform {plat!r}")
    return json.loads(manifest_path.read_text())


def available_languages() -> list[str]:
    """Return the canonical names of all languages bundled for this platform."""
    return sorted(_platform_manifest()["languages"])


def _extracted_library_path(manifest: dict, entry: dict) -> Path:
    plat = manifest["platform"]
    grammars_dir = resources.files("semble_grammars") / "grammars" / plat
    archive_path = Path(str(grammars_dir / manifest["archive"]))
    dest_path = cache_dir() / plat / entry["file"]

    try:
        extract_atomic(archive_path, entry["file"], dest_path, entry["sha256"])
    except (KeyError, OSError, tarfile.TarError, ValueError) as exc:
        raise GrammarLoadError(f"Failed to extract {entry['file']!r} from the bundled archive") from exc
    return dest_path


def _load_capsule(lib_path: Path, symbol: str) -> object:
    try:
        lib = ctypes.CDLL(str(lib_path))
    except OSError as exc:
        raise GrammarLoadError(f"Failed to load {lib_path.name}") from exc
    _loaded_libraries[lib_path] = lib

    try:
        entry_point = getattr(lib, symbol)
    except AttributeError as exc:
        raise GrammarLoadError(f"{lib_path.name}: missing expected symbol {symbol!r}") from exc

    entry_point.restype = ctypes.c_void_p
    language_ptr = entry_point()
    if not language_ptr:
        raise GrammarLoadError(f"{lib_path.name}: {symbol}() returned a null language pointer")

    py_capsule_new = ctypes.pythonapi.PyCapsule_New
    py_capsule_new.restype = ctypes.py_object
    py_capsule_new.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p)
    return py_capsule_new(language_ptr, b"tree_sitter.Language", None)


@lru_cache(maxsize=None)
def get_language(name: str) -> Language:
    """Return the compiled :class:`tree_sitter.Language` for ``name``.

    :param name: canonical language name or known alias, e.g. ``"python"``.
    :raises LanguageNotFoundError: if ``name`` is not in the bundled manifest.
    :returns: the loaded tree-sitter language.
    """
    language = _ALIASES.get(name, name)
    manifest = _platform_manifest()
    entry = manifest["languages"].get(language)
    if entry is None:
        raise LanguageNotFoundError(f"Unknown language {language!r}. Available: {', '.join(available_languages())}")

    lib_path = _extracted_library_path(manifest, entry)
    capsule = _load_capsule(lib_path, entry["symbol"])
    return Language(capsule)


def get_parser(name: str) -> Parser:
    """Return a ready-to-use :class:`tree_sitter.Parser` for ``name``.

    :param name: canonical language name or known alias, e.g. ``"python"``. See :func:`get_language`
        for the errors this can raise.
    :returns: a parser configured for the requested language.
    """
    return Parser(get_language(name))

import ctypes
import json
from functools import lru_cache
from importlib import resources
from pathlib import Path

from tree_sitter import Language, Parser

from semble_grammars.cache import cache_dir, extract_atomic
from semble_grammars.exceptions import LanguageNotFoundError, UnsupportedPlatformError
from semble_grammars.platform import current_platform_tag

_ALIASES = {
    "py": "python",
}


def canonical_name(name: str) -> str:
    """Resolve a language name or alias to its canonical manifest name."""
    return _ALIASES.get(name, name)


@lru_cache(maxsize=1)
def _platform_manifest() -> dict:
    plat = current_platform_tag()
    grammars_dir = resources.files("semble_grammars") / "_grammars" / plat
    manifest_path = grammars_dir / "manifest.json"
    if not manifest_path.is_file():
        raise UnsupportedPlatformError(f"No bundled grammar archive for platform {plat!r}")
    return json.loads(manifest_path.read_text())


def available_languages() -> list[str]:
    """Return the canonical names of all languages bundled for this platform."""
    return sorted(_platform_manifest()["languages"])


def _extracted_library_path(manifest: dict, entry: dict) -> Path:
    plat = manifest["platform"]
    grammars_dir = resources.files("semble_grammars") / "_grammars" / plat
    archive_path = Path(str(grammars_dir / manifest["archive"]))
    dest_path = cache_dir() / plat / entry["file"]

    extract_atomic(archive_path, entry["file"], dest_path)
    return dest_path


def _load_capsule(lib_path: Path, symbol: str) -> object:
    lib = ctypes.CDLL(str(lib_path))
    entry_point = getattr(lib, symbol)
    entry_point.restype = ctypes.c_void_p
    language_ptr = entry_point()

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
    language = canonical_name(name)
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

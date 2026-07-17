import os
import tarfile
import tempfile
from pathlib import Path

from semble_grammars.version import __version__

_CACHE_DIR_ENV_VAR = "SEMBLE_GRAMMARS_CACHE_DIR"


def cache_dir() -> Path:
    """Return the versioned cache directory grammars are extracted into.

    Honors ``SEMBLE_GRAMMARS_CACHE_DIR`` as an override; otherwise defaults to
    ``$XDG_CACHE_HOME/semble/grammars/<version>`` (or ``~/.cache/...`` if unset).
    """
    override = os.environ.get(_CACHE_DIR_ENV_VAR)
    if override:
        return Path(override)
    base = Path(os.environ.get("XDG_CACHE_HOME", "~/.cache")).expanduser()
    return base / "semble" / "grammars" / __version__


def extract_atomic(archive_path: Path, member_name: str, dest_path: Path) -> None:
    """Extract a single member from a tar archive into ``dest_path`` atomically.

    If ``dest_path`` already exists, extraction is skipped. Concurrent callers
    each extract to a unique temporary file in the same directory and rename
    it into place with :func:`os.replace`, which is atomic, so interrupted or
    racing extractions cannot leave a corrupt or partially written file at
    ``dest_path``.
    """
    if dest_path.exists():
        return
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=dest_path.parent, prefix=f".{dest_path.name}.")
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            source = tar.extractfile(member_name)
            if source is None:
                raise KeyError(f"{member_name!r} not found in archive {archive_path}")
            with os.fdopen(fd, "wb") as dest:
                dest.write(source.read())
        os.chmod(tmp_name, 0o755)
        try:
            os.replace(tmp_name, dest_path)
        except OSError:
            # Unlike POSIX, Windows can transiently deny a rename onto a path
            # another thread is simultaneously replacing (mandatory file
            # locking, not just advisory). If dest_path exists by now, some
            # other racing caller's replace already won and produced an
            # equally valid file, so this isn't a real failure.
            if not dest_path.exists():
                raise
    finally:
        Path(tmp_name).unlink(missing_ok=True)

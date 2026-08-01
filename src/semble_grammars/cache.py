import hashlib
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_atomic(archive_path: Path, member_name: str, dest_path: Path, expected_sha256: str) -> None:
    """Extract and verify one archive member atomically."""
    if dest_path.exists():
        return
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=dest_path.parent, prefix=f".{dest_path.name}.")
    try:
        with os.fdopen(fd, "wb") as dest, tarfile.open(archive_path, "r:gz") as tar:
            source = tar.extractfile(member_name)
            if source is None:
                raise KeyError(f"{member_name!r} not found in archive {archive_path}")
            while chunk := source.read(1024 * 1024):
                dest.write(chunk)
        if _sha256(Path(tmp_name)) != expected_sha256:
            raise ValueError(f"Checksum mismatch for {member_name!r} in {archive_path}")
        os.chmod(tmp_name, 0o755)
        try:
            os.replace(tmp_name, dest_path)
        except OSError:
            if not dest_path.exists():
                raise
    finally:
        Path(tmp_name).unlink(missing_ok=True)

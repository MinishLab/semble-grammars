"""Build one platform-specific wheel per grammar archive already present under `_grammars/`.

For each platform directory found in ``semble_grammars/_grammars/`` (produced by
``build_grammars.py``), this copies the repo into an isolated temp directory with
every *other* platform's archive pruned out, then builds a wheel tagged for just
that platform via ``setup.py``'s custom ``bdist_wheel`` command. This keeps a
Linux install from downloading the macOS archive (and vice versa).

Usage: uv run python tools/build_wheels.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GRAMMARS_DIR = REPO_ROOT / "semble_grammars" / "_grammars"
DIST_DIR = REPO_ROOT / "dist"

EXCLUDE_DIRS = {".git", ".venv", "dist", "build", "assets", "__pycache__", "tools"}
SHARED_GRAMMAR_ENTRIES = {"licenses", "provenance.json", "THIRD_PARTY_NOTICES.md"}


def discover_platforms() -> list[str]:
    """Return the platform tags that have a built manifest under `_grammars/`."""
    return sorted(p.name for p in GRAMMARS_DIR.iterdir() if p.is_dir() and p.name not in SHARED_GRAMMAR_ENTRIES)


def copy_pruned_repo(target_platform: str, dest: Path) -> None:
    """Copy the repo into `dest`, keeping only `target_platform`'s grammar archive."""

    def ignore(dir_path: str, names: list[str]) -> set[str]:
        skipped = {n for n in names if n in EXCLUDE_DIRS or n.endswith(".egg-info")}
        if Path(dir_path) == GRAMMARS_DIR:
            other_platforms = set(discover_platforms()) - {target_platform}
            skipped |= other_platforms
        return skipped

    shutil.copytree(REPO_ROOT, dest, ignore=ignore, dirs_exist_ok=True)


def build_wheel_for_platform(target_platform: str) -> None:
    """Build a single wheel tagged for `target_platform` into `DIST_DIR`."""
    with tempfile.TemporaryDirectory(prefix=f"semble-grammars-{target_platform}-") as tmp:
        build_root = Path(tmp) / "repo"
        copy_pruned_repo(target_platform, build_root)

        env = dict(os.environ, SEMBLE_GRAMMARS_WHEEL_PLATFORM=target_platform)
        subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(DIST_DIR)],
            cwd=build_root,
            check=True,
            env=env,
        )


if __name__ == "__main__":
    DIST_DIR.mkdir(exist_ok=True)
    platforms = discover_platforms()
    if not platforms:
        print("no platform grammar archives found under semble_grammars/_grammars/", file=sys.stderr)
        sys.exit(1)

    for target in platforms:
        print(f"building wheel for {target}", file=sys.stderr)
        build_wheel_for_platform(target)

    print("built wheels:", file=sys.stderr)
    for whl in sorted(DIST_DIR.glob("*.whl")):
        print(f"  {whl.name} ({whl.stat().st_size} bytes)", file=sys.stderr)

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tarfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = REPO_ROOT / "assets" / "_build"
GRAMMARS_DIR = REPO_ROOT / "src" / "semble_grammars" / "grammars"

# tree-sitter-cli requires the glibc version provided by Debian trixie.
DOCKER_TARGETS = [
    ("linux-x86_64", "linux/amd64", "debian:trixie-slim"),
    ("linux-arm64", "linux/arm64", "debian:trixie-slim"),
]


@dataclass
class GrammarSpec:
    """Pinned upstream source for a single tree-sitter grammar."""

    language: str
    repository: str
    commit: str
    ref: str
    spdx_license: str
    sources: list[str] = field(default_factory=lambda: ["src/parser.c"])
    generate: bool = False
    symbol_override: str | None = None

    @property
    def symbol(self) -> str:
        """Native entry point exported by the compiled grammar.

        Usually ``tree_sitter_<language>``, but some grammars export a symbol
        that doesn't match Semble's canonical language name (e.g. the
        ``csharp`` grammar exports ``tree_sitter_c_sharp``); ``symbol_override``
        covers those.
        """
        return self.symbol_override or f"tree_sitter_{self.language}"


GRAMMARS = [
    GrammarSpec(language=language, **spec)
    for language, spec in json.loads((GRAMMARS_DIR / "sources.json").read_text()).items()
]


def sha256(path: Path) -> str:
    """Return the hex sha256 digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


CLONE_TIMEOUT_SECONDS = 60
GENERATE_TIMEOUT_SECONDS = 180


def clone_source(spec: GrammarSpec) -> Path:
    """Shallow-fetch a grammar repository at its pinned tag, returning the checkout path.

    Fetches only the pinned ref at depth 1 (instead of a full clone) so this stays fast
    and cannot hang on a repo's full history. The checked-out commit is verified against
    ``spec.commit`` so a moved/mutated tag is caught rather than silently trusted.
    """
    checkout = BUILD_DIR / f"{spec.language}-src"
    if checkout.exists():
        shutil.rmtree(checkout)
    checkout.mkdir(parents=True)

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=checkout, check=True, timeout=CLONE_TIMEOUT_SECONDS, capture_output=True, text=True
        )

    git("init", "--quiet")
    fetch_target = f"refs/tags/{spec.ref}" if spec.ref else spec.commit
    git("fetch", "--quiet", "--depth", "1", spec.repository, fetch_target)
    git("checkout", "--quiet", "FETCH_HEAD")

    actual_commit = git("rev-parse", "HEAD").stdout.strip()
    if actual_commit != spec.commit:
        raise RuntimeError(
            f"{spec.language}: tag {spec.ref!r} now points at {actual_commit}, expected pinned {spec.commit}"
        )

    if spec.generate:
        tree_sitter_cli = shutil.which("tree-sitter")
        if not tree_sitter_cli:
            raise RuntimeError(
                f"{spec.language}: needs `tree-sitter generate` but the tree-sitter CLI isn't installed "
                "(npm install -g tree-sitter-cli)"
            )
        subprocess.run([tree_sitter_cli, "generate"], cwd=checkout, check=True, timeout=GENERATE_TIMEOUT_SECONDS)

    return checkout


def compile_grammar(spec: GrammarSpec, checkout: Path, ext: str, compiler: list[str]) -> Path:
    """Compile a grammar's sources into a shared library and return its path."""
    output = BUILD_DIR / f"libtree_sitter_{spec.language}{ext}"
    include_dir = (checkout / spec.sources[0]).parent
    sources = [str(checkout / src) for src in spec.sources]
    subprocess.run(
        [*compiler, "-fPIC", "-shared", "-O2", "-I", str(include_dir), *sources, "-o", str(output)],
        check=True,
    )
    return output


LICENSE_FILENAMES = ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING.txt"]


def write_license(spec: GrammarSpec, checkout: Path) -> None:
    """Copy a grammar's license text into the shared licenses directory."""
    licenses_dir = GRAMMARS_DIR / "licenses"
    licenses_dir.mkdir(parents=True, exist_ok=True)
    dest_name = f"{spec.language}-LICENSE.txt"

    source = next((checkout / name for name in LICENSE_FILENAMES if (checkout / name).is_file()), None)
    if source is None:
        raise FileNotFoundError(f"{spec.language}: no license file found in {checkout} (tried {LICENSE_FILENAMES})")

    text = source.read_text()
    (licenses_dir / dest_name).write_text(text.rstrip("\n") + "\n")


def build_bundle(plat: str, ext: str, compiler: list[str]) -> None:
    """Build the grammar bundle for `plat` with `compiler`."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    plat_dir = GRAMMARS_DIR / plat
    plat_dir.mkdir(parents=True, exist_ok=True)

    manifest_languages: dict[str, dict] = {}
    lib_paths: list[Path] = []

    for spec in GRAMMARS:
        print(f"building {spec.language} from {spec.repository}@{spec.commit}", file=sys.stderr)
        checkout = clone_source(spec)
        lib_path = compile_grammar(spec, checkout, ext, compiler)
        write_license(spec, checkout)
        lib_paths.append(lib_path)

        manifest_languages[spec.language] = {
            "file": lib_path.name,
            "symbol": spec.symbol,
            "sha256": sha256(lib_path),
        }

    archive_path = plat_dir / "bundle.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        for lib_path in lib_paths:
            tar.add(lib_path, arcname=lib_path.name)

    manifest = {
        "platform": plat,
        "archive": archive_path.name,
        "languages": manifest_languages,
    }
    (plat_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_third_party_notices()
    print(f"wrote {archive_path} ({archive_path.stat().st_size} bytes)", file=sys.stderr)


WINDOWS_CROSS_COMPILER = "x86_64-w64-mingw32-gcc"


def _native_compiler() -> list[str]:
    """Return a suitable compiler for the host platform."""
    if platform.system() != "Windows":
        return ["clang"]
    for candidate in ("gcc", WINDOWS_CROSS_COMPILER):
        if shutil.which(candidate):
            return [candidate]
    raise RuntimeError("no MinGW-w64 gcc found on PATH for a native Windows build (choco install mingw)")


def build_native() -> None:
    """Build the grammar bundle for the current (host) platform."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    os_name = {"darwin": "macos", "linux": "linux", "windows": "windows"}[system]
    arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x86_64", "amd64": "x86_64"}[machine]
    extension = {"darwin": ".dylib", "linux": ".so", "windows": ".dll"}[system]
    build_bundle(f"{os_name}-{arch}", extension, _native_compiler())


def write_third_party_notices() -> None:
    """Regenerate THIRD_PARTY_NOTICES.md from the grammar sources."""
    lines = [
        "# Third-party notices",
        "",
        "This package bundles compiled tree-sitter grammars built from the following",
        "upstream sources. Each grammar is a separate upstream work with its own",
        "license; see `sources.json` for exact commits and `licenses/` for the",
        "full license text of each.",
        "",
        "| Language | Repository | Commit | License |",
        "|---|---|---|---|",
    ]
    for spec in sorted(GRAMMARS, key=lambda item: item.language):
        revision = f"`{spec.commit}`"
        if spec.ref:
            revision += f" ({spec.ref})"
        lines.append(f"| {spec.language} | {spec.repository} | {revision} | {spec.spdx_license} |")
    lines.append("")
    lines.append("Grammars are compiled from these pinned commits with no source modifications.")
    (GRAMMARS_DIR / "THIRD_PARTY_NOTICES.md").write_text("\n".join(lines) + "\n")


def build_via_docker(expected_platform: str, docker_platform: str, image: str) -> None:
    """Cross-build a Linux grammar bundle inside a Docker container."""
    print(f"building {expected_platform} via docker ({docker_platform}, {image})", file=sys.stderr)
    container_cmd = (
        "apt-get update -qq && "
        "apt-get install -y -qq clang git ca-certificates python3 nodejs npm > /dev/null && "
        "npm install -g --silent tree-sitter-cli > /dev/null && "
        "python3 scripts/build_grammars.py --native"
    )
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--platform",
            docker_platform,
            "-v",
            f"{REPO_ROOT}:/repo",
            "-w",
            "/repo",
            image,
            "bash",
            "-c",
            container_cmd,
        ],
        check=True,
    )
    built_manifest = GRAMMARS_DIR / expected_platform / "manifest.json"
    if not built_manifest.is_file():
        raise RuntimeError(f"docker build did not produce {built_manifest}")


if __name__ == "__main__":
    if "--all" in sys.argv[1:]:
        build_native()
        for expected_platform, docker_platform, image in DOCKER_TARGETS:
            build_via_docker(expected_platform, docker_platform, image)
        if shutil.which(WINDOWS_CROSS_COMPILER):
            build_bundle("windows-x86_64", ".dll", [WINDOWS_CROSS_COMPILER])
        else:
            print(
                f"skipping windows-x86_64: {WINDOWS_CROSS_COMPILER} not found "
                "(install mingw-w64, e.g. `brew install mingw-w64`)",
                file=sys.stderr,
            )
    elif "--windows" in sys.argv[1:]:
        build_bundle("windows-x86_64", ".dll", [WINDOWS_CROSS_COMPILER])
    else:
        build_native()

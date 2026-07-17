"""Build the compiled grammar bundle for one or more platforms from pinned upstream commits.

Clones each grammar repository at a pinned commit, compiles its parser (and
external scanner, if any) into a shared library, and packages the result
into ``semble_grammars/_grammars/<platform>/`` together with a manifest and
provenance/license metadata.

Usage:
    uv run python tools/build_grammars.py            # build for the host platform only
    uv run python tools/build_grammars.py --windows   # cross-build windows-x86_64 via mingw-w64
    uv run python tools/build_grammars.py --all       # host + Linux (Docker) + Windows (mingw-w64)
    uv run python tools/build_grammars.py --native    # internal: used inside the build container
"""

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
GRAMMARS_DIR = REPO_ROOT / "semble_grammars" / "_grammars"

# (host platform tag, docker --platform value, apt-based build image)
DOCKER_TARGETS = [
    ("linux-x86_64", "linux/amd64", "debian:bookworm-slim"),
    ("linux-arm64", "linux/arm64", "debian:bookworm-slim"),
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

    @property
    def symbol(self) -> str:
        """Native entry point exported by the compiled grammar."""
        return f"tree_sitter_{self.language}"


GRAMMARS = [
    GrammarSpec(
        language="python",
        repository="https://github.com/tree-sitter/tree-sitter-python",
        commit="293fdc02038ee2bf0e2e206711b69c90ac0d413f",
        ref="v0.25.0",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="json",
        repository="https://github.com/tree-sitter/tree-sitter-json",
        commit="ee35a6ebefcef0c5c416c0d1ccec7370cfca5a24",
        ref="v0.24.8",
        spdx_license="MIT",
    ),
    GrammarSpec(
        language="javascript",
        repository="https://github.com/tree-sitter/tree-sitter-javascript",
        commit="44c892e0be055ac465d5eeddae6d3e194424e7de",
        ref="v0.25.0",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="go",
        repository="https://github.com/tree-sitter/tree-sitter-go",
        commit="1547678a9da59885853f5f5cc8a99cc203fa2e2c",
        ref="v0.25.0",
        spdx_license="MIT",
    ),
    GrammarSpec(
        language="rust",
        repository="https://github.com/tree-sitter/tree-sitter-rust",
        commit="77a3747266f4d621d0757825e6b11edcbf991ca5",
        ref="v0.24.2",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="c",
        repository="https://github.com/tree-sitter/tree-sitter-c",
        commit="b780e47fc780ddc8da13afa35a3f4ed5c157823d",
        ref="v0.24.2",
        spdx_license="MIT",
    ),
    GrammarSpec(
        language="cpp",
        repository="https://github.com/tree-sitter/tree-sitter-cpp",
        commit="f41e1a044c8a84ea9fa8577fdd2eab92ec96de02",
        ref="v0.23.4",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="java",
        repository="https://github.com/tree-sitter/tree-sitter-java",
        commit="94703d5a6bed02b98e438d7cad1136c01a60ba2c",
        ref="v0.23.5",
        spdx_license="MIT",
    ),
    GrammarSpec(
        language="ruby",
        repository="https://github.com/tree-sitter/tree-sitter-ruby",
        commit="71bd32fb7607035768799732addba884a37a6210",
        ref="v0.23.1",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="html",
        repository="https://github.com/tree-sitter/tree-sitter-html",
        commit="5a5ca8551a179998360b4a4ca2c0f366a35acc03",
        ref="v0.23.2",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="css",
        repository="https://github.com/tree-sitter/tree-sitter-css",
        commit="dda5cfc5722c429eaba1c910ca32c2c0c5bb1a3f",
        ref="v0.25.0",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="bash",
        repository="https://github.com/tree-sitter/tree-sitter-bash",
        commit="a06c2e4415e9bc0346c6b86d401879ffb44058f7",
        ref="v0.25.1",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="yaml",
        repository="https://github.com/tree-sitter-grammars/tree-sitter-yaml",
        commit="7708026449bed86239b1cd5bce6e3c34dbca6415",
        ref="v0.7.2",
        spdx_license="MIT",
        sources=[
            "src/parser.c",
            "src/scanner.c",
            "src/schema.core.c",
            "src/schema.json.c",
            "src/schema.legacy.c",
        ],
    ),
    GrammarSpec(
        language="toml",
        repository="https://github.com/tree-sitter-grammars/tree-sitter-toml",
        commit="64b56832c2cffe41758f28e05c756a3a98d16f41",
        ref="v0.7.0",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    # --- batch 2: config/build formats ---
    GrammarSpec(
        language="dockerfile",
        repository="https://github.com/camdencheek/tree-sitter-dockerfile",
        commit="868e44ce378deb68aac902a9db68ff82d2299dd0",
        ref="v0.2.0",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="hcl",
        repository="https://github.com/tree-sitter-grammars/tree-sitter-hcl",
        commit="fad991865fee927dd1de5e172fb3f08ac674d914",
        ref="v1.2.0",
        spdx_license="Apache-2.0",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="ini",
        repository="https://github.com/justinmk/tree-sitter-ini",
        commit="f0285fe577ad298ad79f8633e643ad60646e3027",
        ref="v1.4.0",
        spdx_license="Apache-2.0",
    ),
    GrammarSpec(
        language="properties",
        repository="https://github.com/tree-sitter-grammars/tree-sitter-properties",
        commit="579b62f5ad8d96c2bb331f07d1408c92767531d9",
        ref="v0.3.0",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="gitignore",
        repository="https://github.com/shunsambongi/tree-sitter-gitignore",
        commit="f4685bf11ac466dd278449bcfe5fd014e94aa504",
        ref="",
        spdx_license="MIT",
    ),
    GrammarSpec(
        language="make",
        repository="https://github.com/tree-sitter-grammars/tree-sitter-make",
        commit="5e9e8f8ff3387b0edcaa90f46ddf3629f4cfeb1d",
        ref="v1.1.1",
        spdx_license="MIT",
    ),
    GrammarSpec(
        language="cmake",
        repository="https://github.com/uyha/tree-sitter-cmake",
        commit="ca627bb5828616b6246aafdc3c3222789e728e37",
        ref="v0.7.4",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="nix",
        repository="https://github.com/nix-community/tree-sitter-nix",
        commit="ea1d87f7996be1329ef6555dcacfa63a69bd55c6",
        ref="v0.3.0",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="xml",
        repository="https://github.com/tree-sitter-grammars/tree-sitter-xml",
        commit="4b64dd3a03ec002258d6268d712fd93716d6ab57",
        ref="v0.7.0",
        spdx_license="MIT",
        sources=["xml/src/parser.c", "xml/src/scanner.c"],
    ),
    GrammarSpec(
        language="dtd",
        repository="https://github.com/tree-sitter-grammars/tree-sitter-xml",
        commit="4b64dd3a03ec002258d6268d712fd93716d6ab57",
        ref="v0.7.0",
        spdx_license="MIT",
        sources=["dtd/src/parser.c", "dtd/src/scanner.c"],
    ),
    GrammarSpec(
        language="markdown",
        repository="https://github.com/tree-sitter-grammars/tree-sitter-markdown",
        commit="f969cd3ae3f9fbd4e43205431d0ae286014c05b5",
        ref="v0.5.3",
        spdx_license="MIT",
        sources=["tree-sitter-markdown/src/parser.c", "tree-sitter-markdown/src/scanner.c"],
    ),
    GrammarSpec(
        language="markdown_inline",
        repository="https://github.com/tree-sitter-grammars/tree-sitter-markdown",
        commit="f969cd3ae3f9fbd4e43205431d0ae286014c05b5",
        ref="v0.5.3",
        spdx_license="MIT",
        sources=["tree-sitter-markdown-inline/src/parser.c", "tree-sitter-markdown-inline/src/scanner.c"],
    ),
    # --- batch 3: major languages not yet covered ---
    GrammarSpec(
        language="typescript",
        repository="https://github.com/tree-sitter/tree-sitter-typescript",
        commit="f975a621f4e7f532fe322e13c4f79495e0a7b2e7",
        ref="v0.23.2",
        spdx_license="MIT",
        sources=["typescript/src/parser.c", "typescript/src/scanner.c"],
    ),
    GrammarSpec(
        language="tsx",
        repository="https://github.com/tree-sitter/tree-sitter-typescript",
        commit="f975a621f4e7f532fe322e13c4f79495e0a7b2e7",
        ref="v0.23.2",
        spdx_license="MIT",
        sources=["tsx/src/parser.c", "tsx/src/scanner.c"],
    ),
    GrammarSpec(
        language="swift",
        repository="https://github.com/alex-pinkus/tree-sitter-swift",
        commit="31d17fe7e818a2048c808b5c6fdc2dc792f4f5b5",
        ref="0.7.3-with-generated-files",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="kotlin",
        repository="https://github.com/tree-sitter-grammars/tree-sitter-kotlin",
        commit="77dd60ea0a9003ce062c9728a513ffe1aaff8c82",
        ref="v1.1.0",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="scala",
        repository="https://github.com/tree-sitter/tree-sitter-scala",
        commit="38950b525c9dfc44c8b60d44bdd6e54217286ca8",
        ref="v0.26.0",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="dart",
        repository="https://github.com/UserNobody14/tree-sitter-dart",
        commit="be07cf7118d3dba06236a3f19541685a68209934",
        ref="",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="lua",
        repository="https://github.com/tree-sitter-grammars/tree-sitter-lua",
        commit="10fe0054734eec83049514ea2e718b2a56acd0c9",
        ref="v0.5.0",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="php",
        repository="https://github.com/tree-sitter/tree-sitter-php",
        commit="5b5627faaa290d89eb3d01b9bf47c3bb9e797dea",
        ref="v0.24.2",
        spdx_license="MIT",
        sources=["php/src/parser.c", "php/src/scanner.c"],
    ),
    GrammarSpec(
        language="php_only",
        repository="https://github.com/tree-sitter/tree-sitter-php",
        commit="5b5627faaa290d89eb3d01b9bf47c3bb9e797dea",
        ref="v0.24.2",
        spdx_license="MIT",
        sources=["php_only/src/parser.c", "php_only/src/scanner.c"],
    ),
    GrammarSpec(
        language="elixir",
        repository="https://github.com/elixir-lang/tree-sitter-elixir",
        commit="e2d9e6e0e76b0c436fa48a0b8c32a031d0cbdf49",
        ref="v0.3.5",
        spdx_license="Apache-2.0",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    # sql (DerekStride/tree-sitter-sql) skipped: its tagged releases don't commit a
    # generated src/parser.c, only grammar.js + scanner.c. Adding it needs a
    # `tree-sitter generate` codegen step this build script doesn't have yet.
    # --- batch 4: web/template ---
    GrammarSpec(
        language="vue",
        repository="https://github.com/tree-sitter-grammars/tree-sitter-vue",
        commit="ce8011a414fdf8091f4e4071752efc376f4afb08",
        ref="",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="svelte",
        repository="https://github.com/tree-sitter-grammars/tree-sitter-svelte",
        commit="774a65aea563accc35f5d45fafa4d96ec5761f57",
        ref="v1.0.2",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="graphql",
        repository="https://github.com/bkegley/tree-sitter-graphql",
        commit="5e66e961eee421786bdda8495ed1db045e06b5fe",
        ref="",
        spdx_license="MIT",
    ),
    GrammarSpec(
        language="proto",
        repository="https://github.com/mitchellh/tree-sitter-proto",
        commit="42d82fa18f8afe59b5fc0b16c207ee4f84cb185f",
        ref="",
        spdx_license="MIT",
    ),
    # --- batch 5: specialist, repo-frequency-filtered ---
    GrammarSpec(
        language="zig",
        repository="https://github.com/tree-sitter-grammars/tree-sitter-zig",
        commit="b670c8df85a1568f498aa5c8cae42f51a90473c0",
        ref="v1.1.2",
        spdx_license="MIT",
    ),
    GrammarSpec(
        language="solidity",
        repository="https://github.com/JoranHonig/tree-sitter-solidity",
        commit="4e938a46c7030dd001bc99e1ac0f0c750ac98254",
        ref="v1.2.13",
        spdx_license="MIT",
    ),
    GrammarSpec(
        language="julia",
        repository="https://github.com/tree-sitter/tree-sitter-julia",
        commit="e0f9dcd180fdcfcfa8d79a3531e11d99e79321d3",
        ref="v0.25.0",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
    GrammarSpec(
        language="clojure",
        repository="https://github.com/sogaiu/tree-sitter-clojure",
        commit="3a1ace906c151dd631cf6f149b5083f2b60e6a9e",
        ref="v0.0.13",
        spdx_license="CC0-1.0",
    ),
    GrammarSpec(
        language="jsonnet",
        repository="https://github.com/sourcegraph/tree-sitter-jsonnet",
        commit="ddd075f1939aed8147b7aa67f042eda3fce22790",
        ref="",
        spdx_license="MIT",
        sources=["src/parser.c", "src/scanner.c"],
    ),
]


def detect_platform() -> str:
    """Return the archive platform tag for the current machine."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    os_name = {"darwin": "macos", "linux": "linux", "windows": "windows"}[system]
    arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x86_64", "amd64": "x86_64"}[machine]
    return f"{os_name}-{arch}"


def dylib_extension() -> str:
    """Return the native shared-library extension for the current platform."""
    return {"darwin": ".dylib", "linux": ".so", "windows": ".dll"}[platform.system().lower()]


def sha256(path: Path) -> str:
    """Return the hex sha256 digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


CLONE_TIMEOUT_SECONDS = 60


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


def write_license(spec: GrammarSpec, checkout: Path) -> str:
    """Copy a grammar's license text into the shared licenses directory."""
    licenses_dir = GRAMMARS_DIR / "licenses"
    licenses_dir.mkdir(parents=True, exist_ok=True)
    dest_name = f"{spec.language}-LICENSE.txt"

    source = next((checkout / name for name in LICENSE_FILENAMES if (checkout / name).is_file()), None)
    if source is None:
        raise FileNotFoundError(f"{spec.language}: no license file found in {checkout} (tried {LICENSE_FILENAMES})")

    text = source.read_text()
    (licenses_dir / dest_name).write_text(text.rstrip("\n") + "\n")
    return dest_name


def build_bundle(plat: str, ext: str, compiler: list[str]) -> None:
    """Build the grammar bundle for `plat`, compiling with `compiler`, and write manifest/provenance."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    plat_dir = GRAMMARS_DIR / plat
    plat_dir.mkdir(parents=True, exist_ok=True)

    provenance: dict[str, dict] = {}
    manifest_languages: dict[str, dict] = {}
    lib_paths: list[Path] = []

    for spec in GRAMMARS:
        print(f"building {spec.language} from {spec.repository}@{spec.commit}", file=sys.stderr)
        checkout = clone_source(spec)
        lib_path = compile_grammar(spec, checkout, ext, compiler)
        license_file = write_license(spec, checkout)
        lib_paths.append(lib_path)

        provenance[spec.language] = {
            "repository": spec.repository,
            "commit": spec.commit,
            "ref": spec.ref,
            "spdx_license": spec.spdx_license,
            "license_file": license_file,
        }
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
        "archive_sha256": sha256(archive_path),
        "languages": manifest_languages,
    }
    (plat_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (GRAMMARS_DIR / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    write_third_party_notices(provenance)
    print(f"wrote {archive_path} ({archive_path.stat().st_size} bytes)", file=sys.stderr)


def build_native() -> None:
    """Build the grammar bundle for the current (host) platform."""
    build_bundle(detect_platform(), dylib_extension(), ["clang"])


WINDOWS_CROSS_COMPILER = "x86_64-w64-mingw32-gcc"


def build_windows_cross() -> None:
    """Cross-compile the grammar bundle for windows-x86_64 using mingw-w64.

    Runs directly on the host (no container) since mingw-w64 is itself a
    cross-compiler; ``brew install mingw-w64`` on macOS or the
    ``mingw-w64`` apt package on Linux provides it.
    """
    build_bundle("windows-x86_64", ".dll", [WINDOWS_CROSS_COMPILER])


def write_third_party_notices(provenance: dict[str, dict]) -> None:
    """Regenerate THIRD_PARTY_NOTICES.md from the provenance table."""
    lines = [
        "# Third-party notices",
        "",
        "This package bundles compiled tree-sitter grammars built from the following",
        "upstream sources. Each grammar is a separate upstream work with its own",
        "license; see `provenance.json` for exact commits and `licenses/` for the",
        "full license text of each.",
        "",
        "| Language | Repository | Commit | License |",
        "|---|---|---|---|",
    ]
    for language in sorted(provenance):
        entry = provenance[language]
        lines.append(
            f"| {language} | {entry['repository']} | `{entry['commit']}` ({entry['ref']}) | {entry['spdx_license']} |"
        )
    lines.append("")
    lines.append("Grammars are compiled from these pinned commits with no source modifications.")
    (GRAMMARS_DIR / "THIRD_PARTY_NOTICES.md").write_text("\n".join(lines) + "\n")


def build_via_docker(expected_platform: str, docker_platform: str, image: str) -> None:
    """Cross-build a Linux grammar bundle inside a Docker container."""
    print(f"building {expected_platform} via docker ({docker_platform}, {image})", file=sys.stderr)
    container_cmd = (
        "apt-get update -qq && apt-get install -y -qq clang git ca-certificates python3 > /dev/null && "
        "python3 tools/build_grammars.py --native"
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
            build_windows_cross()
        else:
            print(
                f"skipping windows-x86_64: {WINDOWS_CROSS_COMPILER} not found "
                "(install mingw-w64, e.g. `brew install mingw-w64`)",
                file=sys.stderr,
            )
    elif "--windows" in sys.argv[1:]:
        build_windows_cross()
    else:
        build_native()

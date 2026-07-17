# semble-grammars

Locally-cached tree-sitter grammar bundle for [Semble](https://github.com/MinishLab/semble).

`semble-grammars` ships compiled tree-sitter grammars as package data. There
is no runtime network access: the grammar archive for your platform is
installed by `pip` as part of the wheel, and individual native libraries are
extracted from it lazily, on first use, into a local cache.

```python
from semble_grammars import get_parser

parser = get_parser("python")
tree = parser.parse(b"def hello():\n    print('hi')\n")
```

## Status

Working proof of concept, not yet released. It currently bundles 45
grammars for four platforms (`macos-arm64`, `linux-x86_64`, `linux-arm64`,
`windows-x86_64`), each built into its own platform-tagged wheel. The three
non-Windows wheels are verified end to end: installed from the built
`.whl` (not `-e .`) into clean `python:3.12-slim` containers, with network
access blocked at parse time. The Windows build is cross-compiled with
mingw-w64 and statically verified (valid PE32+ DLL, correct exported
symbol, no non-standard runtime DLL dependencies) but has not been
dynamically loaded on real Windows — no Windows machine or working Wine
install was available in this environment; `release.yaml`'s
`build-windows` job builds it natively on a `windows-latest` GitHub runner
instead, which is untested until that workflow actually runs.

Bundled languages: `python`, `json`, `javascript`, `typescript`, `tsx`,
`go`, `rust`, `c`, `cpp`, `java`, `ruby`, `swift`, `kotlin`, `scala`,
`dart`, `lua`, `php`, `php_only`, `elixir`, `html`, `css`, `vue`, `svelte`,
`graphql`, `proto`, `bash`, `yaml`, `toml`, `dockerfile`, `hcl`, `ini`,
`properties`, `gitignore`, `make`, `cmake`, `nix`, `xml`, `dtd`,
`markdown`, `markdown_inline`, `zig`, `solidity`, `julia`, `clojure`,
`jsonnet` (41 MIT, 3 Apache-2.0, 1 CC0-1.0 — see
`semble_grammars/_grammars/provenance.json` and `THIRD_PARTY_NOTICES.md`).
Selection heuristic: repo-frequency value (config/build formats and major
languages first) weighed against build cost (single grammar repo, plain C
sources, no codegen step needed); niche/narrow-audience grammars (verilog,
cuda, fish/zsh, perl) were deliberately left out for now, matching the
distribution plan's own "defer" list.
`sql` (DerekStride/tree-sitter-sql) was evaluated and skipped: its tagged
releases don't commit a generated `parser.c`, only `grammar.js` — adding it
needs a `tree-sitter generate` codegen step the build script doesn't have
yet.

Done:

- package scaffolding (`semble_grammars`, pinned `tree-sitter` dependency);
- manifest-driven loader: `get_language(name)` / `get_parser(name)` /
  `available_languages()`;
- lazy, atomic, concurrency-safe extraction into
  `$XDG_CACHE_HOME/semble/grammars/<version>/<platform>/` (override with
  `SEMBLE_GRAMMARS_CACHE_DIR`);
- no network access at import or parse time;
- grammars built from pinned upstream commits with license/provenance
  metadata (`semble_grammars/_grammars/provenance.json`,
  `THIRD_PARTY_NOTICES.md`), reproducible via `tools/build_grammars.py`,
  including cross-compiled Linux builds via Docker;
- one platform-tagged wheel per architecture (`tools/build_wheels.py`), so a
  Linux install never downloads the macOS archive or vice versa;
- verified against real installs (`pip install dist/*.whl`) in clean
  containers, not just `pytest` against an editable install.

Not yet done (open items from the distribution plan):

- final language selection is still open — 45 are bundled; `sql` and other
  languages that need `tree-sitter generate` codegen aren't yet;
- the Windows build has only been statically verified (see above), not
  dynamically loaded — needs a real `windows-latest` CI run or a Windows
  machine to close that gap;
- CI now builds grammars before testing (`ci.yaml`) and `release.yaml`
  builds real platform wheels (including Windows), but neither has been run
  on actual GitHub Actions yet — only validated locally and via Docker;
- license audit is per-grammar and automated from `provenance.json`, but
  each entry has only been checked against the GitHub-reported SPDX
  license (or the raw LICENSE file text when the API didn't detect one),
  not a full manual audit;
- fallback/unsupported-language behavior for Semble's own integration;
- cache versioning/eviction policy beyond the current version-scoped path;
- reproducible (bit-identical) builds — compiling the same commit twice
  currently produces different checksums.

## Development

```bash
make install   # uv sync + pre-commit install
make test       # pytest with coverage
make fix        # run pre-commit (ruff, mypy, pydoclint, ...)
```

To rebuild the grammar bundle for the current platform from pinned upstream
sources:

```bash
uv run python tools/build_grammars.py          # host platform only
uv run python tools/build_grammars.py --windows # cross-build windows-x86_64 via mingw-w64
uv run python tools/build_grammars.py --all    # host + Linux (Docker) + Windows (mingw-w64)
```

This shallow-fetches each grammar repository at a pinned tag, compiles it
with `clang`, and writes the compiled archive, manifest, and license files
under `semble_grammars/_grammars/`. `--all` additionally cross-builds the
Linux archives inside `debian:bookworm-slim` containers (requires a running
Docker daemon) and, if `x86_64-w64-mingw32-gcc` is on `PATH`, the Windows
archive (`brew install mingw-w64` on macOS).

To build one platform-tagged wheel per already-built grammar archive:

```bash
uv run python tools/build_wheels.py
```

This produces `dist/semble_grammars-<version>-py3-none-<platform tag>.whl`
for each platform found under `semble_grammars/_grammars/`, each containing
only that platform's archive.

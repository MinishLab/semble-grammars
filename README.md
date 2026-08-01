<h1 align="center">
  semble-grammars<br/>
  <sub>Prebuilt tree-sitter grammars for Semble</sub>
</h1>

<div align="center">
  <h2>
    <a href="https://pypi.org/project/semble-grammars/"><img src="https://img.shields.io/pypi/v/semble-grammars?color=%23007ec6&label=pypi%20package" alt="Package version"></a>
    <a href="https://github.com/MinishLab/semble-grammars/blob/main/LICENSE">
      <img src="https://img.shields.io/badge/license-MIT-green" alt="License - MIT">
    </a>
  </h2>
</div>

Compiled [tree-sitter](https://tree-sitter.github.io/tree-sitter/) grammars for
[Semble](https://github.com/MinishLab/semble).

The package installs a platform-specific grammar archive and extracts individual
libraries to a local cache on first use. It does not access the network at
runtime.

## Installation

```bash
pip install semble-grammars
```

## Usage

```python
from semble_grammars import get_parser

parser = get_parser("python")
tree = parser.parse(b"def hello(): pass")
```

`available_languages()` lists the bundled languages. The package supports
macOS arm64 and x86-64, Linux arm64 and x86-64, and Windows arm64 and x86-64.

<details>
<summary>Included grammars (77)</summary>

The canonical names accepted by `get_parser()` are:

`asciidoc`, `astro`, `bash`, `batch`, `c`, `clojure`, `cmake`, `cpp`,
`csharp`, `css`, `dart`, `dockerfile`, `dtd`, `elixir`, `embedded_template`,
`erlang`, `fortran`, `gitignore`, `go`, `gotmpl`, `graphql`, `groovy`,
`haskell`, `hcl`, `heex`, `html`, `ini`, `java`, `javascript`, `jinja2`,
`json`, `json5`, `jsonc`, `jsonnet`, `julia`, `just`, `kdl`, `kotlin`,
`latex`, `lua`, `make`, `markdown`, `markdown_inline`, `nix`, `objc`,
`ocaml`, `org`, `perl`, `php`, `php_only`, `powershell`, `properties`,
`proto`, `python`, `r`, `racket`, `rst`, `ruby`, `rust`, `scala`, `scheme`,
`scss`, `solidity`, `sql`, `starlark`, `svelte`, `swift`, `toml`, `tsx`,
`typescript`, `typst`, `vim`, `vue`, `wat`, `xml`, `yaml`, `zig`.

`py` is an alias for `python`, `terraform` is an alias for `hcl`,
`embeddedtemplate` is an alias for `embedded_template`, and `zsh` is an alias
for `bash`.
</details>

The MIT license above covers `semble-grammars`' own code. Each bundled grammar is a
separate upstream work with its own license; see
[`THIRD_PARTY_NOTICES.md`](src/semble_grammars/grammars/THIRD_PARTY_NOTICES.md) for the
full list.

## Building from source

Build grammars from the pinned sources in
[`sources.json`](src/semble_grammars/grammars/sources.json):

```bash
uv run python scripts/build_grammars.py           # current platform
uv run python scripts/build_grammars.py --windows # Windows via mingw-w64
uv run python scripts/build_grammars.py --all     # current, Linux, and Windows
```

This requires a C compiler, Git, and the tree-sitter CLI (`npm install -g
tree-sitter-cli@0.26.11`). Linux cross-builds also require Docker. Build the available
platform archives into wheels with:

```bash
uv run python scripts/build_wheels.py
```

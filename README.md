# semble-grammars

Compiled [tree-sitter](https://tree-sitter.github.io/tree-sitter/) grammars for
[Semble](https://github.com/MinishLab/semble).

The package installs a platform-specific grammar archive and extracts individual
libraries to a local cache on first use. It does not access the network at
runtime.

```python
from semble_grammars import get_parser

parser = get_parser("python")
tree = parser.parse(b"def hello(): pass")
```

`available_languages()` lists the bundled languages. The package supports
macOS arm64 and x86-64, Linux x86-64 and arm64, and Windows arm64 and x86-64.

<details>
<summary>Included grammars (75)</summary>

The canonical names accepted by `get_parser()` are:

`asciidoc`, `astro`, `bash`, `c`, `clojure`, `cmake`, `cpp`, `csharp`, `css`,
`dart`, `dockerfile`, `dtd`, `elixir`, `embedded_template`, `erlang`, `fortran`,
`gitignore`, `go`, `gotmpl`, `graphql`, `groovy`, `haskell`, `hcl`, `html`,
`ini`, `java`, `javascript`, `jinja2`, `json`, `json5`, `jsonc`, `jsonnet`,
`julia`, `just`, `kdl`, `kotlin`, `latex`, `lua`, `make`, `markdown`,
`markdown_inline`, `nix`, `objc`, `ocaml`, `org`, `perl`, `php`, `php_only`,
`powershell`, `properties`, `proto`, `python`, `r`, `racket`, `rst`, `ruby`,
`rust`, `scala`, `scheme`, `scss`, `solidity`, `sql`, `starlark`, `svelte`,
`swift`, `toml`, `tsx`, `typescript`, `typst`, `vim`, `vue`, `wat`, `xml`,
`yaml`, `zig`.

`py` is an alias for `python`, and `terraform` is an alias for `hcl`.
</details>

## Development

```bash
make install
make test
make lint
make typecheck
```

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

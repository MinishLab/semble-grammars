import socket

import pytest

from semble_grammars import LanguageNotFoundError, available_languages, get_parser


@pytest.mark.parametrize(
    ("name", "source", "expect_error"),
    [
        ("python", b"def foo(x):\n    return x + 1\n", False),
        ("py", b"x = 1\n", False),
        ("python", b"def foo(:\n", True),
        ("json", b'{"a": [1, 2, 3]}', False),
        ("javascript", b"function f(x) { return x + 1; }", False),
        ("go", b"package main\nfunc main() {}\n", False),
        ("rust", b'fn main() { println!("hi"); }', False),
        ("c", b"int main() { return 0; }", False),
        ("cpp", b"int main() { return 0; }", False),
        ("java", b"class A { void f() {} }", False),
        ("ruby", b"def f(x)\n  x + 1\nend\n", False),
        ("html", b"<html><body>hi</body></html>", False),
        ("css", b".a { color: red; }", False),
        ("bash", b"echo hello\n", False),
        ("yaml", b"a: 1\nb:\n  - 2\n", False),
        ("toml", b"a = 1\n[b]\nc = 2\n", False),
    ],
)
def test_get_parser_parses_bundled_languages(name, source, expect_error):
    parser = get_parser(name)
    tree = parser.parse(source)
    assert tree.root_node.has_error is expect_error


def test_unknown_language_raises_with_available_languages_listed():
    with pytest.raises(LanguageNotFoundError, match="nonexistent"):
        get_parser("nonexistent")


def test_available_languages_has_no_duplicates_and_covers_core_set():
    languages = available_languages()
    assert len(languages) == len(set(languages))
    assert {"python", "json", "typescript", "markdown", "dockerfile"} <= set(languages)


@pytest.mark.parametrize("name", available_languages())
def test_every_bundled_language_loads_and_parses(name):
    parser = get_parser(name)
    tree = parser.parse(b"")
    assert tree is not None


def test_extraction_reuses_cache_on_second_call():
    from semble_grammars import _cache, _loader
    from semble_grammars._platform import current_platform_tag

    get_parser("python")
    dest = _cache.cache_dir() / current_platform_tag() / "libtree_sitter_python.dylib"
    first_mtime = dest.stat().st_mtime_ns

    _loader.get_language.cache_clear()
    get_parser("python")
    assert dest.stat().st_mtime_ns == first_mtime


def test_no_network_access_during_load(monkeypatch):
    def blocked_connect(self, *args, **kwargs):
        raise AssertionError("semble_grammars must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
    parser = get_parser("json")
    assert not parser.parse(b"{}").root_node.has_error

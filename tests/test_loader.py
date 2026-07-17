import socket

import pytest

from semble_grammars import (
    GrammarLoadError,
    LanguageNotFoundError,
    available_languages,
    cache,
    get_language,
    get_parser,
    loader,
)


@pytest.mark.parametrize(
    ("name", "source", "expect_error"),
    [
        ("python", b"def foo(x):\n    return x + 1\n", False),
        ("python", b"def foo(:\n", True),
        ("json", b'{"a": [1, 2, 3]}', False),
        ("sql", b"SELECT * FROM foo WHERE x = 1;", False),
    ],
)
def test_get_parser_parses_bundled_languages(name, source, expect_error):
    parser = get_parser(name)
    tree = parser.parse(source)
    assert tree.root_node.has_error is expect_error


def test_terraform_is_an_alias_for_hcl():
    assert get_language("terraform") == get_language("hcl")


def test_unknown_language_raises_with_available_languages_listed():
    with pytest.raises(LanguageNotFoundError, match="nonexistent"):
        get_parser("nonexistent")


def test_available_languages_covers_core_set():
    languages = available_languages()
    assert {"python", "json", "typescript", "markdown", "dockerfile"} <= set(languages)


@pytest.mark.parametrize("name", available_languages())
def test_every_bundled_language_loads(name):
    assert get_language(name)


def test_load_capsule_raises_on_missing_symbol():
    get_parser("python")
    manifest = loader._platform_manifest()
    filename = manifest["languages"]["python"]["file"]
    lib_path = cache.cache_dir() / manifest["platform"] / filename

    with pytest.raises(GrammarLoadError, match="missing expected symbol"):
        loader._load_capsule(lib_path, "not_a_real_symbol")


def test_no_network_access_during_load(monkeypatch):
    def blocked_connect(self, *args, **kwargs):
        raise AssertionError("semble_grammars must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
    parser = get_parser("json")
    assert not parser.parse(b"{}").root_node.has_error

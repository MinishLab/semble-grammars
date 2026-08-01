import pytest

from semble_grammars import loader


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Give every test a fresh on-disk cache and clear in-process memoization."""
    monkeypatch.setenv("SEMBLE_GRAMMARS_CACHE_DIR", str(tmp_path / "cache"))
    loader.get_language.cache_clear()
    loader._platform_manifest.cache_clear()
    yield
    loader.get_language.cache_clear()
    loader._platform_manifest.cache_clear()

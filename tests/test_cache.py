import tarfile
import threading

from semble_grammars.cache import extract_atomic


def _make_archive(path, member_name, content):
    with tarfile.open(path, "w:gz") as tar:
        data_path = path.parent / member_name
        data_path.write_bytes(content)
        tar.add(data_path, arcname=member_name)


def test_extract_atomic_is_idempotent(tmp_path):
    archive = tmp_path / "bundle.tar.gz"
    _make_archive(archive, "grammar.bin", b"grammar-bytes")
    dest = tmp_path / "cache" / "grammar.bin"

    extract_atomic(archive, "grammar.bin", dest)
    assert dest.read_bytes() == b"grammar-bytes"

    dest.write_bytes(b"corrupted")
    extract_atomic(archive, "grammar.bin", dest)
    assert dest.read_bytes() == b"corrupted"  # existing file is left untouched


def test_extract_atomic_survives_concurrent_first_use(tmp_path):
    archive = tmp_path / "bundle.tar.gz"
    _make_archive(archive, "grammar.bin", b"grammar-bytes" * 1000)
    dest = tmp_path / "cache" / "grammar.bin"

    errors = []

    def worker():
        try:
            extract_atomic(archive, "grammar.bin", dest)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert dest.read_bytes() == b"grammar-bytes" * 1000

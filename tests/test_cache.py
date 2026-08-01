import hashlib
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
    content = b"grammar-bytes"
    checksum = hashlib.sha256(content).hexdigest()
    _make_archive(archive, "grammar.bin", content)
    dest = tmp_path / "cache" / "grammar.bin"

    extract_atomic(archive, "grammar.bin", dest, checksum)
    first_mtime = dest.stat().st_mtime_ns
    extract_atomic(archive, "grammar.bin", dest, checksum)

    assert dest.read_bytes() == content
    assert dest.stat().st_mtime_ns == first_mtime


def test_extract_atomic_survives_concurrent_first_use(tmp_path):
    archive = tmp_path / "bundle.tar.gz"
    content = b"grammar-bytes" * 1000
    checksum = hashlib.sha256(content).hexdigest()
    _make_archive(archive, "grammar.bin", content)
    dest = tmp_path / "cache" / "grammar.bin"

    errors = []

    def worker():
        try:
            extract_atomic(archive, "grammar.bin", dest, checksum)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert dest.read_bytes() == content

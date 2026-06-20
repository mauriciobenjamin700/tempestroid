"""Tests for the G4 on-device model store (``native/model_store.py``).

Uses ``file://`` URLs (no network/server) to exercise download → cache → verify.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from tempestroid.native.model_store import ModelStoreError, ensure_model


def _serve(tmp_path: Path, name: str, data: bytes) -> tuple[str, str]:
    """Write ``data`` to a source file and return its ``file://`` URL + sha256.

    Args:
        tmp_path: The pytest temp dir.
        name: The source file name.
        data: The bytes to write.

    Returns:
        A ``(file_url, sha256_hex)`` pair.
    """
    src = tmp_path / "src" / name
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(data)
    return src.as_uri(), hashlib.sha256(data).hexdigest()


async def test_download_and_cache(tmp_path: Any) -> None:
    """A model is fetched into the cache dir and returned."""
    url, digest = _serve(tmp_path, "model.onnx", b"ONNX-BYTES" * 100)
    cache = tmp_path / "cache"

    path = await ensure_model(url, cache, sha256=digest)
    assert path == cache / "model.onnx"
    assert path.read_bytes() == b"ONNX-BYTES" * 100


async def test_cache_hit_skips_download(tmp_path: Any) -> None:
    """An existing cached file is returned without re-fetching (cache-first)."""
    cache = tmp_path / "cache"
    cache.mkdir()
    cached = cache / "model.onnx"
    cached.write_bytes(b"ALREADY-CACHED")
    # URL points at *different* content; with the file present + no hash, the
    # cached copy must win (no download).
    url, _ = _serve(tmp_path, "model.onnx", b"FRESH-FROM-SERVER")

    path = await ensure_model(url, cache)
    assert path.read_bytes() == b"ALREADY-CACHED"


async def test_sha256_verifies_download(tmp_path: Any) -> None:
    """A download whose hash matches is accepted."""
    url, digest = _serve(tmp_path, "m.ort", b"weights")
    path = await ensure_model(url, tmp_path / "c", sha256=digest, filename="m.ort")
    assert path.is_file()


async def test_sha256_mismatch_rejects_and_cleans_up(tmp_path: Any) -> None:
    """A download whose hash mismatches raises and leaves no partial file."""
    url, _ = _serve(tmp_path, "m.onnx", b"weights")
    cache = tmp_path / "c"
    with pytest.raises(ModelStoreError, match="hash_mismatch"):
        await ensure_model(url, cache, sha256="00" * 32)
    assert not (cache / "m.onnx").exists()
    assert not (cache / "m.onnx.part").exists()


async def test_download_failure_raises(tmp_path: Any) -> None:
    """A missing source raises download_failed (no partial file left)."""
    missing = (tmp_path / "nope.onnx").as_uri()
    cache = tmp_path / "c"
    with pytest.raises(ModelStoreError, match="download_failed"):
        await ensure_model(missing, cache)
    assert not (cache / "nope.onnx").exists()


async def test_stale_cache_redownloads_on_hash_mismatch(tmp_path: Any) -> None:
    """A cached file that fails the expected hash is replaced by a fresh download."""
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "model.onnx").write_bytes(b"STALE")
    url, digest = _serve(tmp_path, "model.onnx", b"CORRECT-WEIGHTS")

    path = await ensure_model(url, cache, sha256=digest)
    assert path.read_bytes() == b"CORRECT-WEIGHTS"

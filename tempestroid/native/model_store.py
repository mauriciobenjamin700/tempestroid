"""On-device model delivery: cache + download + verify (Trilho G4).

A vision app ships its ``.onnx``/``.ort`` model one of two ways:

* **Embedded** — bundled as a project asset and extracted with the app bundle
  (what ``examples/visionspike`` does; already proven on device). The model path
  resolves inside the extracted bundle; nothing here is needed.
* **Downloaded** — fetched at runtime into a cache so the APK stays lean (large
  models, or models updated independently of releases). :func:`ensure_model`
  implements this: it returns a cached path if present (and hash-verified), else
  downloads once, verifies, and caches it.

Either way the model ends up as a **file path** handed to
:meth:`~tempestroid.native.inference.AarBackend.create`; ONNX Runtime mmaps the
file on load, so a large model does not have to be read fully into RAM.

The download is pure Python stdlib (``urllib`` + ``hashlib``) so it runs on the
embedded interpreter with no extra native module, and it is run **off the event
loop** (``asyncio.to_thread``) so a multi-megabyte fetch never blocks the UI.
``file://`` URLs are supported (tests, or a model pushed to the device).
"""

from __future__ import annotations

import asyncio
import hashlib
import urllib.request
from pathlib import Path

__all__ = ["ensure_model", "ModelStoreError"]

#: Bytes read per chunk when hashing/streaming (keeps memory flat on big models).
_CHUNK = 1 << 20  # 1 MiB


class ModelStoreError(RuntimeError):
    """A model could not be fetched or failed verification.

    Attributes:
        code: A short machine-readable code (``"download_failed"`` or
            ``"hash_mismatch"``).
    """

    def __init__(self, code: str, message: str = "") -> None:
        """Initialize the error.

        Args:
            code: The machine-readable code.
            message: A human-readable detail.
        """
        self.code: str = code
        super().__init__(f"{code}: {message}" if message else code)


def _sha256(path: Path) -> str:
    """Compute the SHA-256 of a file, streaming in chunks.

    Args:
        path: The file to hash.

    Returns:
        The lowercase hex digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, dest: Path, timeout: float) -> None:
    """Download ``url`` to ``dest`` (streamed), raising on failure.

    Args:
        url: The source URL (``http(s)://`` or ``file://``).
        dest: The destination file path.
        timeout: Socket timeout in seconds.

    Raises:
        ModelStoreError: If the fetch fails for any reason.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            with dest.open("wb") as handle:
                while True:
                    chunk = response.read(_CHUNK)
                    if not chunk:
                        break
                    handle.write(chunk)
    except (OSError, ValueError) as exc:
        dest.unlink(missing_ok=True)
        raise ModelStoreError("download_failed", f"{url}: {exc}") from exc


async def ensure_model(
    url: str,
    dest_dir: str | Path,
    *,
    sha256: str | None = None,
    filename: str | None = None,
    timeout: float = 60.0,
) -> Path:
    """Return a local path to the model, downloading + caching it if needed.

    Cache-first: if the target already exists (and matches ``sha256`` when
    given), it is returned without a network call. Otherwise the model is
    downloaded — off the event loop — to a temporary file, verified, and
    atomically renamed into place.

    Args:
        url: The model URL (``http(s)://``; ``file://`` is also accepted).
        dest_dir: Directory to cache the model in (created if absent). On device
            pass a writable app dir; the returned path lives here.
        sha256: Optional expected SHA-256 hex digest; when given, a cached or
            freshly downloaded file that does not match is rejected.
        filename: Cache filename; defaults to the URL's basename.
        timeout: Per-connection socket timeout in seconds.

    Returns:
        The path to the cached, verified model file.

    Raises:
        ModelStoreError: If the download fails, or the hash does not match.
        ValueError: If no filename can be derived from ``url``.
    """
    cache_dir = Path(dest_dir)
    name = filename or url.rsplit("/", 1)[-1].split("?", 1)[0]
    if not name:
        raise ValueError(f"cannot derive a filename from url: {url!r}")
    target = cache_dir / name

    def _resolve() -> Path:
        cache_dir.mkdir(parents=True, exist_ok=True)
        if target.is_file() and (sha256 is None or _sha256(target) == sha256.lower()):
            return target
        tmp = target.with_suffix(target.suffix + ".part")
        _download(url, tmp, timeout)
        if sha256 is not None:
            actual = _sha256(tmp)
            if actual != sha256.lower():
                tmp.unlink(missing_ok=True)
                raise ModelStoreError(
                    "hash_mismatch", f"expected {sha256.lower()}, got {actual}"
                )
        tmp.replace(target)
        return target

    # Hashing + the network fetch are blocking; keep the UI loop responsive.
    return await asyncio.to_thread(_resolve)

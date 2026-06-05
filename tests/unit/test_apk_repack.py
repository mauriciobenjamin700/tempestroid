"""Tests for the APK repackaging that powers `tempest build` (no Gradle).

Covers the pure-Python bundle-injection step (drop old signature, add the
bundle, preserve other entries' compression). The `zipalign` + `apksigner` steps
need the Android SDK build-tools and are exercised on the maintainer's host, not
in CI.
"""

import io
import zipfile
from pathlib import Path

from tempestroid.cli.apk_repack import inject_bundle


def _fake_host_apk(path: Path) -> None:
    """Write a minimal fake host APK: a STORED .so, a signature, an asset."""
    with zipfile.ZipFile(path, "w") as apk:
        so = zipfile.ZipInfo("lib/arm64-v8a/libpython.so")
        so.compress_type = zipfile.ZIP_STORED
        apk.writestr(so, b"\x7fELF native bytes")
        apk.writestr("classes.dex", b"dex" * 100)  # deflated by default
        apk.writestr("META-INF/CERT.RSA", b"old signature")
        apk.writestr("META-INF/MANIFEST.MF", b"old manifest")
        apk.writestr("assets/tempest_app_bundle.zip", b"OLD BUNDLE")


def test_inject_drops_signature_adds_bundle(tmp_path: Path) -> None:
    host = tmp_path / "host.apk"
    _fake_host_apk(host)
    out = tmp_path / "out.apk"

    inject_bundle(host, b"NEW BUNDLE BYTES", out)

    with zipfile.ZipFile(out) as result:
        names = set(result.namelist())
        # Old signature dropped.
        assert "META-INF/CERT.RSA" not in names
        assert "META-INF/MANIFEST.MF" not in names
        # Other entries survive.
        assert "lib/arm64-v8a/libpython.so" in names
        assert "classes.dex" in names
        # The bundle is replaced with the new bytes.
        assert result.read("assets/tempest_app_bundle.zip") == b"NEW BUNDLE BYTES"
        # The native lib keeps its STORED compression (so it stays mmap-able).
        so_info = result.getinfo("lib/arm64-v8a/libpython.so")
        assert so_info.compress_type == zipfile.ZIP_STORED


def test_inject_output_is_valid_zip(tmp_path: Path) -> None:
    host = tmp_path / "host.apk"
    _fake_host_apk(host)
    out = tmp_path / "out.apk"
    inject_bundle(host, b"x", out)
    # The result opens cleanly and the .so bytes round-trip.
    with zipfile.ZipFile(io.BytesIO(out.read_bytes())) as result:
        assert result.read("lib/arm64-v8a/libpython.so") == b"\x7fELF native bytes"

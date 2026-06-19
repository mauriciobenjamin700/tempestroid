"""Unit tests for the on-device image decode bridge (Trilho G2).

A fake ``send_native_request`` stands in for the Kotlin ``image`` host module
(BitmapFactory), so the decode path — path/bytes args → host reply → HWC uint8
RGB ndarray — is exercised in-process with no device.
"""

from __future__ import annotations

import base64
from typing import Any

import numpy as np
import pytest

from tempestroid.native import image as image_mod
from tempestroid.native.dispatch import NativeError
from tempestroid.native.image import decode_image


def _fake_decoder(array: np.ndarray) -> Any:
    """Build a fake ``send_native_request`` returning ``array`` as RGB pixels.

    Args:
        array: The HWC uint8 RGB array the fake host "decodes".

    Returns:
        An async callable with the ``send_native_request`` signature; it records
        the args it received on ``.last_args``.
    """

    async def fake_send(
        module: str, action: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        assert module == "image"
        assert action == "decode"
        fake_send.last_args = args  # type: ignore[attr-defined]
        height, width = array.shape[0], array.shape[1]
        return {
            "width": width,
            "height": height,
            "data": base64.b64encode(array.tobytes()).decode("ascii"),
        }

    return fake_send


async def test_decode_image_by_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """A path is sent under ``path`` and the RGB pixels round-trip to an ndarray."""
    expected = np.arange(4 * 5 * 3, dtype=np.uint8).reshape(4, 5, 3)
    fake = _fake_decoder(expected)
    monkeypatch.setattr(image_mod, "send_native_request", fake)

    out = await decode_image("photo.jpg", max_size=640)
    assert out.shape == (4, 5, 3)
    assert out.dtype == np.uint8
    assert np.array_equal(out, expected)
    assert fake.last_args["path"] == "photo.jpg"  # type: ignore[attr-defined]
    assert fake.last_args["max_size"] == 640  # type: ignore[attr-defined]


async def test_decode_image_by_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raw bytes are base64-sent under ``bytes`` (decoded from memory)."""
    expected = np.zeros((2, 2, 3), dtype=np.uint8)
    fake = _fake_decoder(expected)
    monkeypatch.setattr(image_mod, "send_native_request", fake)

    out = await decode_image(b"\xff\xd8\xff\xe0jpegbytes")
    assert out.shape == (2, 2, 3)
    sent = fake.last_args["bytes"]  # type: ignore[attr-defined]
    assert base64.b64decode(sent) == b"\xff\xd8\xff\xe0jpegbytes"
    assert "path" not in fake.last_args  # type: ignore[attr-defined]


async def test_decode_image_byte_count_mismatch_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reply whose pixel count disagrees with width*height*3 raises NativeError."""

    async def bad_send(
        module: str, action: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        # Claims 4x4 but returns only 3 bytes.
        return {"width": 4, "height": 4, "data": base64.b64encode(b"abc").decode()}

    monkeypatch.setattr(image_mod, "send_native_request", bad_send)
    with pytest.raises(NativeError, match="decode_failed"):
        await decode_image("photo.jpg")


async def test_decode_image_malformed_reply_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reply missing width/height/data raises ValueError."""

    async def empty_send(
        module: str, action: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(image_mod, "send_native_request", empty_send)
    with pytest.raises(ValueError, match="malformed"):
        await decode_image("photo.jpg")

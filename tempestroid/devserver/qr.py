"""Render a QR code for the dev server URL (phase B5).

Lets the device pair by scanning instead of typing an IP. ``qrcode`` is an
optional convenience: if it is not installed, the URL is printed plainly so the
loop still works (e.g. with ``adb reverse``, where the device uses localhost).
"""

from __future__ import annotations

import io

__all__ = ["render_qr"]


def render_qr(data: str) -> str:
    """Render ``data`` as a terminal-friendly QR code (or a plain fallback).

    Args:
        data: The text to encode (typically the dev server URL).

    Returns:
        An ASCII QR code if ``qrcode`` is installed, else a labelled plain string.
    """
    try:
        import qrcode  # type: ignore[import-untyped]
    except ImportError:
        return f"(install the qrcode package for a scannable code)\n  {data}"

    qr = qrcode.QRCode(border=1)
    qr.add_data(data)
    qr.make(fit=True)
    buffer = io.StringIO()
    qr.print_ascii(out=buffer)
    return f"{buffer.getvalue()}\n  {data}"

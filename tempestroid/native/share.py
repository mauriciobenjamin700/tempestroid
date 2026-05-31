"""Native sharing capability.

Fire-and-forget intents over the device's share sheet. :func:`share` opens the
system chooser (Android ``ACTION_SEND``); :func:`share_to_whatsapp` targets the
WhatsApp package directly; :func:`open_url` hands a URL to the default handler.
None return a value — the user interacts with another app — so they are one-way
``native`` commands.
"""

from __future__ import annotations

from tempestroid.native.dispatch import send_native

__all__ = ["share", "share_to_whatsapp", "open_url"]


def share(text: str = "", url: str = "", title: str = "") -> None:
    """Open the system share sheet with text and/or a URL.

    Args:
        text: The body text to share.
        url: A URL to append/share (combined with ``text`` by the host).
        title: The chooser dialog title.
    """
    send_native("share", "share", {"text": text, "url": url, "title": title})


def share_to_whatsapp(text: str = "", phone: str = "") -> None:
    """Share text directly to WhatsApp, optionally pre-targeting a number.

    Args:
        text: The message text.
        phone: An optional E.164 phone number (digits, no ``+``) to open a chat
            with via ``wa.me``; empty opens the WhatsApp chooser.
    """
    send_native("share", "whatsapp", {"text": text, "phone": phone})


def open_url(url: str) -> None:
    """Open a URL with the device's default handler (browser, app link, …).

    Args:
        url: The URL to open.
    """
    send_native("share", "open_url", {"url": url})

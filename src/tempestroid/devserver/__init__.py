"""LAN code-push dev server (phase B5).

The Expo-style on-device inner loop: a :class:`DevServer` on the dev machine
serves the app source and relays device logs; :func:`run_dev_client` /
:func:`serve_device` run on the device, polling for changes and hot-restarting
the app over the bridge. :func:`render_qr` shows the URL to pair by scanning.
"""

from tempestroid.devserver.client import run_dev_client, serve_device
from tempestroid.devserver.qr import render_qr
from tempestroid.devserver.server import DevServer, source_hash

__all__ = [
    "DevServer",
    "source_hash",
    "run_dev_client",
    "serve_device",
    "render_qr",
]

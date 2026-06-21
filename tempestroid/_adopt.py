"""Adopt the extracted ``tempest-core`` engine as tempestroid's shared modules.

The renderer-agnostic engine — style, widgets, components, the core
IR/reconciler/state, animation, navigation, theme, i18n, icons, devices and
validators — used to be vendored under ``tempestroid/`` but now lives in the
standalone ``tempest-core`` package, with tempestroid consuming it as the single
source of truth.

Importing this module (which :mod:`tempestroid` does first) aliases every shared
``tempest_core`` submodule under its historical ``tempestroid.<name>`` path in
``sys.modules``, so every existing import — ``from tempestroid.core import App``,
``from tempestroid.style import Color`` — keeps resolving unchanged even though no
such files exist under ``tempestroid`` anymore. The renderer / native / bridge /
cli layers stay tempestroid's own and are untouched.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys

import tempest_core


def adopt_tempest_core() -> None:
    """Alias every ``tempest_core`` submodule under ``tempestroid.<name>``.

    Pre-seeding ``sys.modules`` (and the parent package attribute) makes
    ``import tempestroid.<shared>`` resolve to the extracted ``tempest_core``
    package. Walking the package yields parents before children, so each parent
    alias is registered before its submodules reference it.
    """
    package_root = "tempestroid"
    prefix = f"{tempest_core.__name__}."
    for info in pkgutil.walk_packages(tempest_core.__path__, prefix=prefix):
        module = importlib.import_module(info.name)
        alias = info.name.replace(tempest_core.__name__, package_root, 1)
        sys.modules[alias] = module
        parent_name, _, leaf = alias.rpartition(".")
        parent = sys.modules.get(parent_name)
        if parent is not None:
            setattr(parent, leaf, module)


adopt_tempest_core()

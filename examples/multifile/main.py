"""Multi-file example entry: imports a sibling package, then renders it.

Run on a connected device with:

    tempest deploy examples/multifile/main.py   # offline push (no SDK/NDK)
    tempest build  examples/multifile/main.py   # standalone shippable APK

The ``from widgets import counter_card`` import only resolves because the whole
project tree is bundled and placed on ``sys.path`` on the device.
"""

from __future__ import annotations

from dataclasses import dataclass

from widgets import counter_card

from tempestroid import App, Widget


@dataclass
class State:
    """The app state: a single counter."""

    count: int = 0


def make_state() -> State:
    """Build the initial state.

    Returns:
        A fresh :class:`State`.
    """
    return State()


def view(app: App[State]) -> Widget:
    """Render the counter card from the imported sibling module.

    Args:
        app: The running app (state + ``set_state``).

    Returns:
        The widget tree.
    """

    def increment() -> None:
        # `set_state` mutates the state in place (it does not replace it with a
        # return value), so bump the field directly.
        def bump(state: State) -> None:
            state.count += 1

        app.set_state(bump)

    return counter_card(app.state.count, increment)

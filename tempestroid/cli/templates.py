"""Project templates for ``tempest new --template`` (beyond the default).

The ``default`` template (a single ``app.py``) lives in
:mod:`tempestroid.cli.scaffold`. This module holds the **multi-file** templates a
team reaches for on a real project:

* ``multi`` — a pythonic multi-file layout: a typed ``state.py``, one ``view``
  function per screen under ``screens/``, a reusable ``Card`` ``Component`` under
  ``components/``, and an ``app.py`` that routes between screens with the
  framework's ``Navigator`` / ``Route`` stack.
* ``native`` — the ``multi`` layout plus a screen that calls native capabilities:
  ``notify`` (fire-and-forget) and ``get_position`` (``await`` a typed result,
  guarded by ``on_device`` and ``try/except NativeError``).

Every generated module stays **renderer-agnostic** — only ``tempestroid`` is
imported at module top; ``run_qt`` is imported lazily inside ``__main__`` — so
the same project runs in the Qt simulator and on the Android device unchanged.

Each file's content carries the ``%APP_NAME%`` sentinel, replaced with the
project's display name by :func:`render_files`.
"""

from __future__ import annotations

__all__ = ["TEMPLATES", "Template", "render_files", "py_safe"]

#: The placeholder replaced with the project's display name in template files.
_APP_NAME = "%APP_NAME%"


class Template:
    """A named project template: a set of files to write under the project root.

    Attributes:
        name: The template key (e.g. ``"multi"``).
        description: A one-line summary shown in CLI help / errors.
        files: A mapping of POSIX-style relative path → file content (carrying the
            ``%APP_NAME%`` sentinel).
    """

    def __init__(self, name: str, description: str, files: dict[str, str]) -> None:
        """Initialize a template.

        Args:
            name: The template key.
            description: A one-line summary.
            files: Relative path → content mapping.
        """
        self.name: str = name
        self.description: str = description
        self.files: dict[str, str] = files


def py_safe(display_name: str) -> str:
    r"""Escape a display name for safe interpolation into a Python string literal.

    The sentinel is substituted into generated ``.py`` files (docstrings, a title
    ``Text`` and an ``f``-string), so a project/directory name containing a
    backslash or double-quote would otherwise produce invalid Python (an
    unterminated or mis-escaped literal). This happens only on an in-place
    scaffold (``tempest new .``), where the name is the raw directory name and is
    not constrained by the named-project validator.

    Args:
        display_name: The raw project display name.

    Returns:
        The name with ``\\`` and ``"`` backslash-escaped — valid inside both
        double-quoted and triple-quoted string literals.
    """
    # Use chr() for the backslash (92) and double-quote (34) so this source holds
    # no escaped-quote literal (which ruff Q003 would rewrite to single quotes,
    # against the project's double-quote convention).
    backslash = chr(92)
    quote = chr(34)
    return display_name.replace(backslash, backslash * 2).replace(
        quote, backslash + quote
    )


def render_files(template: Template, display_name: str) -> dict[str, str]:
    """Render a template's files for a concrete project name.

    Every template file is Python, so the substituted name is escaped via
    :func:`py_safe` to stay valid inside the generated string literals.

    Args:
        template: The template to render.
        display_name: The project's human display name.

    Returns:
        A mapping of relative path → rendered content (sentinel substituted).
    """
    safe = py_safe(display_name)
    return {
        path: content.replace(_APP_NAME, safe)
        for path, content in template.files.items()
    }


# --- shared file bodies ------------------------------------------------------

_STATE_PY = """\
\"\"\"Typed application state for %APP_NAME%.\"\"\"

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppState:
    \"\"\"The app's mutable state.

    Attributes:
        taps: How many times the primary action was tapped.
    \"\"\"

    taps: int = 0
"""

_COMPONENTS_INIT = """\
\"\"\"Reusable composite components for %APP_NAME%.\"\"\"

from components.card import Card

__all__ = [\"Card\"]
"""

_CARD_PY = """\
\"\"\"A reusable card component for %APP_NAME%.\"\"\"

from __future__ import annotations

from tempestroid import (
    Color,
    Column,
    Component,
    Edge,
    FontWeight,
    Style,
    Text,
    Widget,
)


class Card(Component):
    \"\"\"A titled surface card that lowers to a primitive ``Column``.

    A ``Component`` is expanded by the reconciler into primitive widgets before
    diffing, so it renders identically in the Qt simulator and on the device.

    Attributes:
        title: The card's heading.
        body: The card's body text.
    \"\"\"

    title: str = \"\"
    body: str = \"\"

    def render(self) -> Widget:
        \"\"\"Lower the card into a styled column.

        Returns:
            A ``Column`` with the title and body text.
        \"\"\"
        return Column(
            style=Style(
                gap=6.0,
                padding=Edge.all(16.0),
                radius=12.0,
                background=Color.from_hex(\"#1f2937\"),
            ),
            children=[
                Text(
                    content=self.title,
                    style=Style(
                        color=Color.from_hex(\"#f9fafb\"),
                        font_size=18.0,
                        font_weight=FontWeight.BOLD,
                    ),
                ),
                Text(
                    content=self.body,
                    style=Style(
                        color=Color.from_hex(\"#9ca3af\"),
                        font_size=14.0,
                    ),
                ),
            ],
        )
"""

_HOME_PY = """\
\"\"\"Home screen for %APP_NAME%.\"\"\"

from __future__ import annotations

from tempestroid import (
    App,
    Button,
    Color,
    Column,
    Edge,
    Route,
    Style,
    Widget,
)

from components import Card
from state import AppState


def home_screen(app: App[AppState]) -> Widget:
    \"\"\"Build the home screen.

    Args:
        app: The running app (read ``app.state``, wire handlers, navigate).

    Returns:
        The home screen widget.
    \"\"\"
    return Column(
        style=Style(
            gap=16.0,
            padding=Edge.all(24.0),
            background=Color.from_hex(\"#0b0f14\"),
        ),
        children=[
            Card(
                title=\"%APP_NAME%\",
                body=f\"Taps: {app.state.taps}\",
                key=\"card\",
            ),
            Button(
                label=\"Tap me\",
                on_click=lambda: app.set_state(
                    lambda s: setattr(s, \"taps\", s.taps + 1)
                ),
                key=\"tap\",
            ),
            Button(
                label=\"Open detail\",
                on_click=lambda: app.push(Route(name=\"/detail\")),
                key=\"go-detail\",
            ),
        ],
    )
"""

_DETAIL_PY = """\
\"\"\"Detail screen for %APP_NAME%.\"\"\"

from __future__ import annotations

from tempestroid import (
    App,
    Button,
    Color,
    Column,
    Edge,
    Style,
    Text,
    Widget,
)

from state import AppState


def detail_screen(app: App[AppState]) -> Widget:
    \"\"\"Build the detail screen (pushed onto the navigation stack).

    Args:
        app: The running app. ``app.pop`` returns to the previous screen — the
            Android system back button and the simulator's Esc do the same.

    Returns:
        The detail screen widget.
    \"\"\"
    return Column(
        style=Style(
            gap=16.0,
            padding=Edge.all(24.0),
            background=Color.from_hex(\"#0b0f14\"),
        ),
        children=[
            Text(
                content=\"Detail screen\",
                style=Style(color=Color.from_hex(\"#f9fafb\"), font_size=22.0),
                key=\"detail-title\",
            ),
            Text(
                content=f\"You tapped {app.state.taps} time(s) on home.\",
                style=Style(color=Color.from_hex(\"#9ca3af\"), font_size=14.0),
                key=\"detail-body\",
            ),
            Button(label=\"Back\", on_click=app.pop, key=\"back\"),
        ],
    )
"""


def _app_py(routes: str, imports: str) -> str:
    """Build the ``app.py`` entry for a multi-screen project.

    Args:
        routes: The body of the route → screen dispatch (inside ``view``).
        imports: The ``from screens import ...`` line.

    Returns:
        The rendered ``app.py`` source.
    """
    return f"""\
\"\"\"%APP_NAME% — a multi-file tempestroid app.

Run it in the Qt simulator with hot reload::

    uv run tempest dev

Push it to a device over LAN (no APK rebuild)::

    uv run tempest serve

The contract every tempestroid app honors: a ``make_state()`` factory and a
``view(app)`` builder. This module stays free of Qt imports so it runs on both
the desktop simulator and the Android device; ``run_qt`` is imported lazily in
``__main__`` only. Screens live in ``screens/`` (one ``view`` function each)
and reusable widgets in ``components/``.
\"\"\"

from __future__ import annotations

from tempestroid import App, Navigator, Widget

{imports}
from state import AppState


def make_state() -> AppState:
    \"\"\"Build a fresh initial state (used on every hot restart).

    Returns:
        A new application state.
    \"\"\"
    return AppState()


def view(app: App[AppState]) -> Widget:
    \"\"\"Route to the current screen and wrap it for animated transitions.

    The active route is ``app.nav.top.name`` (the framework's navigation
    stack); ``app.push(Route(...))`` and ``app.pop`` move between screens.

    Args:
        app: The running app.

    Returns:
        The current screen, wrapped in a ``Navigator`` so push/pop animate.
    \"\"\"
    name = app.nav.top.name
{routes}
    screen = screen.model_copy(update={{\"key\": name}})
    return Navigator(
        child=screen,
        transition=\"slide\",
        depth=len(app.nav.stack),
    )


if __name__ == \"__main__\":
    # Lazy Qt import — keep this module renderer-agnostic
    # (see the module docstring).
    from tempestroid.renderers.qt import run_qt

    raise SystemExit(run_qt(make_state(), view, title=\"%APP_NAME%\"))
"""


# --- multi template ----------------------------------------------------------

_MULTI_SCREENS_INIT = """\
\"\"\"Screens for %APP_NAME% — one ``view`` function per screen.\"\"\"

from screens.detail import detail_screen
from screens.home import home_screen

__all__ = [\"home_screen\", \"detail_screen\"]
"""

_MULTI_ROUTES = """\
    if name == "/detail":
        screen = detail_screen(app)
    else:
        screen = home_screen(app)"""

_MULTI = Template(
    name="multi",
    description="Multi-file project: state + screens/ + components/ + Navigator.",
    files={
        "app.py": _app_py(
            routes=_MULTI_ROUTES,
            imports="from screens import detail_screen, home_screen",
        ),
        "state.py": _STATE_PY,
        "components/__init__.py": _COMPONENTS_INIT,
        "components/card.py": _CARD_PY,
        "screens/__init__.py": _MULTI_SCREENS_INIT,
        "screens/home.py": _HOME_PY,
        "screens/detail.py": _DETAIL_PY,
    },
)


# --- native template ---------------------------------------------------------

_NATIVE_STATE_PY = """\
\"\"\"Typed application state for %APP_NAME%.\"\"\"

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppState:
    \"\"\"The app's mutable state.

    Attributes:
        taps: How many times the primary action was tapped.
        location: The last fetched location (or a status string).
    \"\"\"

    taps: int = 0
    location: str = \"(not fetched)\"
"""

_NATIVE_HOME_PY = """\
\"\"\"Home screen for %APP_NAME%.\"\"\"

from __future__ import annotations

from tempestroid import (
    App,
    Button,
    Color,
    Column,
    Edge,
    Route,
    Style,
    Widget,
)

from components import Card
from state import AppState


def home_screen(app: App[AppState]) -> Widget:
    \"\"\"Build the home screen.

    Args:
        app: The running app (read ``app.state``, wire handlers, navigate).

    Returns:
        The home screen widget.
    \"\"\"
    return Column(
        style=Style(
            gap=16.0,
            padding=Edge.all(24.0),
            background=Color.from_hex(\"#0b0f14\"),
        ),
        children=[
            Card(
                title=\"%APP_NAME%\",
                body=f\"Taps: {app.state.taps}\",
                key=\"card\",
            ),
            Button(
                label=\"Tap me\",
                on_click=lambda: app.set_state(
                    lambda s: setattr(s, \"taps\", s.taps + 1)
                ),
                key=\"tap\",
            ),
            Button(
                label=\"Native capabilities\",
                on_click=lambda: app.push(Route(name=\"/native\")),
                key=\"go-native\",
            ),
        ],
    )
"""

_NATIVE_SCREEN_PY = """\
\"\"\"Native capabilities screen for %APP_NAME%.

Shows the two shapes of native calls:

* **fire-and-forget** — ``notify(...)`` returns immediately.
* **request/response** — ``await get_position()`` resolves a typed
  ``Position``; guard with ``on_device()`` (the Qt simulator has no GPS) and
  catch ``NativeError`` for a denied permission or a missing sensor.
\"\"\"

from __future__ import annotations

from tempestroid import (
    App,
    Button,
    Color,
    Column,
    Edge,
    Style,
    Text,
    Widget,
)
from tempestroid.native import NativeError, get_position, notify, on_device

from state import AppState


def native_screen(app: App[AppState]) -> Widget:
    \"\"\"Build the native-capabilities screen.

    Args:
        app: The running app.

    Returns:
        The native screen widget.
    \"\"\"

    def send_notification() -> None:
        \"\"\"Post a system notification (fire-and-forget).\"\"\"
        notify(\"%APP_NAME%\", \"Hello from a native notification!\")

    async def fetch_location() -> None:
        \"\"\"Fetch the device location (request/response) and store it.\"\"\"
        if not on_device():
            app.set_state(lambda s: setattr(s, \"location\", \"(device only)\"))
            return
        try:
            pos = await get_position()
            app.set_state(
                lambda s: setattr(
                    s, \"location\", f\"{pos.latitude:.4f}, {pos.longitude:.4f}\"
                )
            )
        except NativeError as exc:
            message = f\"error: {exc}\"
            app.set_state(lambda s: setattr(s, \"location\", message))

    return Column(
        style=Style(
            gap=16.0,
            padding=Edge.all(24.0),
            background=Color.from_hex(\"#0b0f14\"),
        ),
        children=[
            Text(
                content=\"Native capabilities\",
                style=Style(color=Color.from_hex(\"#f9fafb\"), font_size=22.0),
                key=\"native-title\",
            ),
            Button(
                label=\"Send notification\",
                on_click=send_notification,
                key=\"notify\",
            ),
            Button(
                label=\"Fetch location\",
                on_click=fetch_location,
                key=\"locate\",
            ),
            Text(
                content=f\"Location: {app.state.location}\",
                style=Style(color=Color.from_hex(\"#9ca3af\"), font_size=14.0),
                key=\"location\",
            ),
            Button(label=\"Back\", on_click=app.pop, key=\"back\"),
        ],
    )
"""

_NATIVE_SCREENS_INIT = """\
\"\"\"Screens for %APP_NAME% — one ``view`` function per screen.\"\"\"

from screens.detail import detail_screen
from screens.home import home_screen
from screens.native import native_screen

__all__ = [\"home_screen\", \"detail_screen\", \"native_screen\"]
"""

_NATIVE_ROUTES = """\
    if name == "/native":
        screen = native_screen(app)
    elif name == "/detail":
        screen = detail_screen(app)
    else:
        screen = home_screen(app)"""

_NATIVE = Template(
    name="native",
    description="The multi layout plus a screen calling native capabilities.",
    files={
        "app.py": _app_py(
            routes=_NATIVE_ROUTES,
            imports=(
                "from screens import detail_screen, home_screen, native_screen"
            ),
        ),
        "state.py": _NATIVE_STATE_PY,
        "components/__init__.py": _COMPONENTS_INIT,
        "components/card.py": _CARD_PY,
        "screens/__init__.py": _NATIVE_SCREENS_INIT,
        "screens/home.py": _NATIVE_HOME_PY,
        "screens/detail.py": _DETAIL_PY,
        "screens/native.py": _NATIVE_SCREEN_PY,
    },
)


#: The non-default templates, keyed by name.
TEMPLATES: dict[str, Template] = {_MULTI.name: _MULTI, _NATIVE.name: _NATIVE}

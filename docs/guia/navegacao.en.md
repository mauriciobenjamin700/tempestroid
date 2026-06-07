# Navigation between screens

A real app has more than one screen: product list, detail, cart, profile.
In tempestroid navigation is modelled as a **route stack** of plain, serializable
data — no magic dedicated widget is needed. The `view(app)` function reads
`app.nav.top` to decide which widget tree to build; switching routes is simply
`view` producing a different tree, and the existing reconciler diffs it normally
with no new patch kind. The Android back button (and `Esc` in the Qt simulator)
calls `app.pop` automatically — you don't need to wire anything.

---

## The model: route stack

Every route stack is built from two types in `tempestroid.navigation`:

```python
from tempestroid import Route
from tempestroid.navigation import NavStack
```

### `Route`

An immutable destination with a **name** (a URL-path-style identifier) and an
optional **params** dictionary:

```python
from tempestroid import Route

home = Route(name="/")
details = Route(name="/details", params={"id": 42})
```

`Route` is a frozen Pydantic model — it is compared by value, just like `Style`.
This lets the reconciler detect route changes as any other prop change.

### `NavStack`

The app's route stack. The bottom is the root; the top is the visible screen.

```python
from tempestroid.navigation import NavStack, Route

stack = NavStack()
print(stack.top.name)   # "/"
print(stack.can_pop)    # False — we're at the root
```

| Property | Type | Description |
|---|---|---|
| `top` | `Route` | The route on top of the stack (the visible screen). |
| `can_pop` | `bool` | `True` when there is more than one route on the stack. |

`App` already creates a stack with the root route `"/"` by default — you never
construct a `NavStack` manually unless you want a custom initial state (e.g. for
deep links).

---

## Push and pop: `push` / `pop`

The most common way to navigate is to push a new route with `app.push` and go
back with `app.pop`. The `view` reads `app.nav.top.name` to pick which screen to
render:

```python
from dataclasses import dataclass

from tempestroid import App, Button, Column, Route, Text, Widget


@dataclass
class State:
    """Sample app state."""


def make_state() -> State:
    """Return the initial state."""
    return State()


def home_screen(app: App[State]) -> Widget:
    """Home screen."""
    return Column(
        children=[
            Text(content="Home", key="title"),
            Button(
                label="View product 42 details",
                on_click=lambda: app.push(Route(name="/details", params={"id": 42})),
                key="btn",
            ),
        ],
    )


def details_screen(app: App[State]) -> Widget:
    """Details screen."""
    item_id = app.nav.top.params.get("id")
    return Column(
        children=[
            Text(content=f"Product {item_id}", key="title"),
            Button(label="Back", on_click=app.pop, key="back"),
        ],
    )


def view(app: App[State]) -> Widget:
    """Pick the screen based on the route at the top of the stack."""
    if app.nav.top.name == "/details":
        return details_screen(app)
    return home_screen(app)
```

!!! tip "Route params"
    Pass any serializable data in `params`. On the destination screen read it with
    `app.nav.top.params.get("key")`. The params are part of the immutable `Route`
    object — the same model that travels over the bridge to the device.

!!! note "Exact signatures"
    ```text
    app.push(route: Route) -> None
    app.pop() -> bool          # True if a route was popped, False if already at root
    ```
    `pop` returns `False` at the root instead of raising — the stack is never
    empty.

### Three chained screens

The same pattern scales to as many screens as you like. Each `push` adds a route
to the stack; each `pop` removes the last one:

```python
from dataclasses import dataclass

from tempestroid import App, Button, Column, Route, Text, Widget


@dataclass
class State:
    """Three-screen app state."""


def make_state() -> State:
    """Return the initial state."""
    return State()


def screen_a(app: App[State]) -> Widget:
    """Screen A."""
    return Column(
        children=[
            Text(content="Screen A", key="t"),
            Button(
                label="Go to B",
                on_click=lambda: app.push(Route(name="/b")),
                key="btn",
            ),
        ],
    )


def screen_b(app: App[State]) -> Widget:
    """Screen B."""
    return Column(
        children=[
            Text(content="Screen B", key="t"),
            Button(
                label="Go to C",
                on_click=lambda: app.push(Route(name="/c")),
                key="next",
            ),
            Button(label="Back to A", on_click=app.pop, key="back"),
        ],
    )


def screen_c(app: App[State]) -> Widget:
    """Screen C."""
    return Column(
        children=[
            Text(content="Screen C (end of stack)", key="t"),
            Button(label="Back to B", on_click=app.pop, key="back"),
        ],
    )


_SCREENS = {"/": screen_a, "/b": screen_b, "/c": screen_c}


def view(app: App[State]) -> Widget:
    """Route by the name at the top of the stack."""
    screen_fn = _SCREENS.get(app.nav.top.name, screen_a)
    return screen_fn(app)
```

---

## Replace and reset: `replace` / `reset`

Beyond pushing and popping, there are two methods for specific scenarios.

### `replace` — swap without changing depth

Use when you want to replace the current screen with another without adding an
entry to the stack (the user cannot go "back" to the previous screen):

```python
from tempestroid import Route

# Replace the current screen with "/login" without pushing:
app.replace(Route(name="/login"))
```

Typical scenarios: step-by-step onboarding (each step replaces the previous one),
redirect after logout, a confirmation that replaces a form.

```text
# Signature:
app.replace(route: Route) -> None
```

### `reset` — redefine the entire stack

Use when you need to discard all navigation history and set a brand-new stack —
for example, after a successful login:

```python
from tempestroid import Route

# After login: clean stack with home on top
app.reset([Route(name="/")])
```

`reset` requires a non-empty list — an app must always have a screen to render.

```text
# Signature:
app.reset(stack: list[Route]) -> None  # raises ValueError if stack is empty
```

!!! warning "Stack can never be empty"
    Passing an empty list to `reset` raises `ValueError`. The app must always
    have at least one route.

---

## Visual hosts

Changing routes already swaps the widget tree — the reconciler diffs and applies
patches. **Navigation hosts** are optional widgets that add transition animations,
tabs, or a drawer to the same mechanism.

For full prop details and more examples, see the
[Navigation Widgets](widgets/navigation.md) page.

### `Navigator` — animated stack

Wrap the current screen in a `Navigator` to get slide/fade animations when
navigating. Pass `depth=len(app.nav.stack)` so the renderers know the direction
(forward vs. back):

```python
from dataclasses import dataclass

from tempestroid import App, Button, Column, Navigator, Route, Text, Widget


@dataclass
class State:
    """Navigator example state."""


def make_state() -> State:
    """Return the initial state."""
    return State()


def view(app: App[State]) -> Widget:
    """Screen with navigation animation."""
    depth = len(app.nav.stack)

    if app.nav.top.name == "/details":
        content = Column(
            children=[
                Text(content="Details", key="title"),
                Button(label="Back", on_click=app.pop, key="back"),
            ],
            key=f"screen-{depth}",
        )
    else:
        content = Column(
            children=[
                Text(content="Home", key="title"),
                Button(
                    label="Details",
                    on_click=lambda: app.push(Route(name="/details")),
                    key="fwd",
                ),
            ],
            key=f"screen-{depth}",
        )

    return Navigator(child=content, transition="slide", depth=depth)
```

!!! tip "The animated key"
    Give each screen tree a different `key` per depth (`key=f"screen-{depth}"`).
    The reconciler treats a key change as a replacement, signalling to the renderer
    that it should animate the transition.

### `TabView` / `TabBar` — tabs as routes

Use `TabView` for integrated tabs (bar + content) or `TabBar` for a standalone bar
you position freely. Both emit `RouteChangeEvent` with `params["index"]`:

```python
from dataclasses import dataclass

from tempestroid import App, Column, RouteChangeEvent, TabView, Text, Widget


@dataclass
class State:
    """Tabbed app state."""

    tab: int = 0


def make_state() -> State:
    """Return the initial state."""
    return State()


def view(app: App[State]) -> Widget:
    """Three-tab app."""

    def on_tab(event: RouteChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "tab", event.params["index"]))

    bodies = [
        Column(children=[Text(content="Home", key="h")], key="home"),
        Column(children=[Text(content="Search", key="s")], key="search"),
        Column(children=[Text(content="Profile", key="p")], key="profile"),
    ]

    return TabView(
        tabs=["Home", "Search", "Profile"],
        active=app.state.tab,
        child=bodies[app.state.tab],
        on_change=on_tab,
    )
```

### `RouteDrawer` — side drawer

For a sliding side menu, use `RouteDrawer`. The `open` state controls visibility;
`on_change` is emitted when the user closes the drawer by gesture or tapping
outside:

```python
from dataclasses import dataclass

from tempestroid import (
    App,
    Button,
    Column,
    RouteChangeEvent,
    RouteDrawer,
    Text,
    Widget,
)


@dataclass
class State:
    """Drawer app state."""

    drawer_open: bool = False


def make_state() -> State:
    """Return the initial state."""
    return State()


def view(app: App[State]) -> Widget:
    """Main screen with a side drawer."""

    def on_drawer_change(event: RouteChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "drawer_open", False))

    return RouteDrawer(
        child=Column(
            children=[
                Text(content="Content", key="main"),
                Button(
                    label="Open menu",
                    on_click=lambda: app.set_state(
                        lambda s: setattr(s, "drawer_open", True)
                    ),
                    key="open",
                ),
            ],
        ),
        drawer=Column(
            children=[Text(content="Side menu", key="menu")],
        ),
        open=app.state.drawer_open,
        on_change=on_drawer_change,
    )
```

---

## Android back button

The Android back button (and the `Esc` key in the Qt simulator) is captured
automatically by the runtime and calls `app.pop()`.

- **At the root** (`app.nav.can_pop == False`): `pop` is a no-op — the Android
  system assumes its default back action (typically closes the app).
- **On any other screen**: the top route is removed and the coalesced rebuild runs
  normally.

You **do not** need to wire the back button manually. An explicit "Back" button in
your widgets (`on_click=app.pop`) is only for the user's convenience — the system
button is already handled.

!!! info "In the Qt simulator"
    The `Esc` key triggers the same `app.pop`. Useful for testing navigation
    behaviour without a physical device.

---

## Deep links

A deep link arrives as an Android intent (or a launch argument in the simulator)
and must open the app directly on a specific screen, with the back stack already
built. `routes_from_path` converts a path into an initial stack:

```python
from tempestroid.navigation import routes_from_path

# "/shop/item" → [Route("/"), Route("/shop"), Route("/shop/item")]
stack = routes_from_path("/shop/item")
```

Pass that stack to `app.reset(...)` at app startup and the user can navigate back
through the intermediate screens normally:

```python
from dataclasses import dataclass

from tempestroid import App, Button, Column, Text, Widget
from tempestroid.navigation import routes_from_path


@dataclass
class State:
    """App state with deep-link support."""

    deep_link: str = ""


def make_state() -> State:
    """Return the initial state."""
    return State()


def view(app: App[State]) -> Widget:
    """Screen that responds to deep links."""
    route_name = app.nav.top.name

    def open_deep() -> None:
        stack = routes_from_path(app.state.deep_link or "/shop/item")
        app.reset(stack)

    return Column(
        children=[
            Text(content=f"Current route: {route_name}", key="route"),
            Button(label="Simulate deep link /shop/item", on_click=open_deep, key="dl"),
            Button(label="Back", on_click=app.pop, key="back"),
        ],
    )
```

!!! note "Root path"
    `routes_from_path("/")` and `routes_from_path("")` both return
    `[Route(name="/")]` — the same as the default `NavStack`, with no extra
    entries.

---

## Transitions

`Navigator` accepts a `transition` prop that is a **hint** to the renderers about
how to animate the screen swap:

| Value | Behaviour |
|---|---|
| `"slide"` | Slides the new screen in (Qt: `QPropertyAnimation`; Compose: `AnimatedContent`). |
| `"fade"` | Cross-fades between screens. |
| `"none"` | Instant swap, no animation. |

```python
from tempestroid import Navigator, Route

# In the view:
navigator = Navigator(child=current_screen, transition="slide", depth=depth)
```

!!! tip "Transition is a hint, not a contract"
    The renderers may interpret `transition` slightly differently (Qt uses
    `QPropertyAnimation`; Compose uses `AnimatedContent`). To disable animations
    entirely, use `"none"`.

---

## Recap

- `App` maintains a `NavStack` at `app.nav`. The `view` reads `app.nav.top` to
  decide which screen to render — navigation is just the `view` producing a
  different tree.
- `app.push(Route(name="..."))` pushes a new route; `app.pop()` goes back to the
  previous one (no-op at the root).
- `app.replace(Route(...))` replaces the current screen without changing the stack
  depth.
- `app.reset([...])` resets the entire stack — useful after login or on a deep
  link.
- `routes_from_path("/a/b")` converts a path into an initial stack for deep links.
- `Navigator`, `TabView`/`TabBar`, and `RouteDrawer` are optional visual hosts
  that add animation, tabs, and a side drawer to the same mechanism.
- The Android back button and `Esc` in the simulator call `app.pop`
  automatically.

## Next steps

- [Navigation Widgets](widgets/navigation.md) — full props for `Navigator`,
  `TabView`, `TabBar`, and `RouteDrawer`.
- Full navigation example:
  [`examples/navigation/app.py`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/navigation/app.py)
- Tabs example:
  [`examples/tabs/app.py`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/tabs/app.py)

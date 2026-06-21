# Media and graphics widgets

The media and graphics widgets cover image display, named vector icons, scalable
vector graphics (`Svg`), a programmatic drawing surface (`Canvas`), embedded
video and web pages (`VideoPlayer` / `WebView`), and visual effects applied on
top of other widgets (`Blur` / `BackdropFilter` / `ClipPath`). Most of them run
on **both renderers** — the Qt simulator and Compose on device; widgets that rely
on camera or GPS hardware (`CameraPreview`, `QrScanner`, `MapView`) are
device-only.

!!! warning "Device-only widgets"
    `CameraPreview`, `QrScanner`, and `MapView` render **only on the Android
    device (Compose)**.  In the Qt simulator they appear as a **signalled
    placeholder** (a grey box with the widget name) so the surrounding UI can
    still be developed on the desktop — but the real widget only works on
    hardware. The opposite is not true: every other widget on this page works
    on both renderers.

---

## Image

Displays a bitmap image loaded from a URL or asset path.

```python
from tempestroid import Column, Image, Style, Text

Column(
    style=Style(gap=12.0, padding=16.0),
    children=[
        Image(
            src="https://example.com/photo.jpg",
            fit="cover",
            alt="Profile picture",
            key="avatar",
        ),
        Text(content="Maurício", key="name"),
    ],
)
```

![Image](../../assets/components/image.png)

| Prop | Type | Default | Description |
|---|---|---|---|
| `src` | `str` | *(required)* | URL or asset path of the image. |
| `fit` | `ImageFit` | `ImageFit.CONTAIN` | Fit mode: `CONTAIN`, `COVER`, `FILL`, `NONE`. |
| `alt` | `str` | `""` | Alternative text for accessibility. |

---

## Icon

Displays a named vector icon from the platform's icon set.

```python
from tempestroid import Icon, Row, Text

Row(
    children=[
        Icon(name="star", size=24.0, key="ico"),
        Text(content="Favourite", key="lbl"),
    ],
)
```

![Icon](../../assets/components/icon.png)

| Prop | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | *(required)* | Icon name on the platform (e.g. `"star"`, `"home"`, `"close"`). |
| `size` | `float \| None` | `None` | Size in logical pixels. `None` inherits from the theme. |

---

## Svg

Displays a scalable vector graphic (SVG) loaded from a URL or asset path.

```python
from tempestroid import Container, Svg, Style

Container(
    style=Style(width=120.0, height=120.0),
    child=Svg(
        src="assets/logo.svg",
        fit="contain",
        key="logo",
    ),
)
```

![Svg](../../assets/components/svg.png)

| Prop | Type | Default | Description |
|---|---|---|---|
| `src` | `str` | *(required)* | URL or path of the SVG file. |
| `fit` | `ImageFit` | `ImageFit.CONTAIN` | Fit mode: `CONTAIN`, `COVER`, `FILL`, `NONE`. |

---

## Canvas

A retained-mode drawing surface that interprets a list of draw commands. Useful
for custom charts, graphs, and vector animations.

```python
from tempestroid import Canvas
from tempestroid.widgets.media import (
    MoveTo, LineTo, StrokeCmd,
)

Canvas(
    width=200.0,
    height=100.0,
    commands=[
        MoveTo(x=0.0, y=50.0),
        LineTo(x=200.0, y=50.0),
        StrokeCmd(color="#FF0000", width=2.0),
    ],
    key="chart",
)
```

![Canvas](../../assets/components/canvas.png)

| Prop | Type | Default | Description |
|---|---|---|---|
| `commands` | `list[DrawCommand]` | `[]` | Sequence of draw commands: `MoveTo`, `LineTo`, `ArcTo`, `Close`, `FillCmd`, `StrokeCmd`, `DrawText`, `DrawRect`, `DrawOval`. |
| `width` | `float \| None` | `None` | Surface width in logical pixels. |
| `height` | `float \| None` | `None` | Surface height in logical pixels. |

!!! tip "Commands are cumulative"
    `Canvas` commands build a retained path. `MoveTo` / `LineTo` / `ArcTo`
    construct the outline; `FillCmd` / `StrokeCmd` paint the current path;
    `Close` closes the current segment. `DrawText` / `DrawRect` / `DrawOval`
    are standalone shapes that do not affect the path being built.

---

## VideoPlayer

An embedded video player that plays a local or remote file.

```python
from tempestroid import VideoPlayer

VideoPlayer(
    src="https://example.com/video.mp4",
    autoplay=False,
    loop=True,
    controls=True,
    muted=False,
    key="player",
)
```

![VideoPlayer](../../assets/components/video_player.png)

| Prop | Type | Default | Description |
|---|---|---|---|
| `src` | `str` | *(required)* | URL or file path of the video. |
| `autoplay` | `bool` | `False` | Start playback automatically on mount. |
| `loop` | `bool` | `False` | Repeat the video when it ends. |
| `controls` | `bool` | `True` | Show native play/pause/seek controls. |
| `muted` | `bool` | `False` | Mute audio (required for autoplay on some platforms). |

---

## WebView

An embedded browser window that loads a remote web page by URL.

```python
from tempestroid import WebView

WebView(
    url="https://docs.tempestroid.dev",
    javascript_enabled=True,
    key="docs",
)
```

![WebView](../../assets/components/web_view.png)

| Prop | Type | Default | Description |
|---|---|---|---|
| `url` | `str` | *(required)* | URL of the page to load. |
| `javascript_enabled` | `bool` | `True` | Enable JavaScript execution in the page. |

---

## Blur

Wraps a child and applies a Gaussian blur to it.

```python
from tempestroid import Blur, Image

Blur(
    radius=12.0,
    child=Image(src="https://example.com/bg.jpg", key="bg"),
    key="blurred",
)
```

![Blur](../../assets/components/blur.png)

| Prop | Type | Default | Description |
|---|---|---|---|
| `radius` | `float` | `8.0` | Blur radius in logical pixels. Larger values = more blur. |
| `child` | `Widget \| None` | `None` | The child to blur. |

---

## BackdropFilter

Wraps a child and applies a Gaussian blur **to the layers behind it** (semantic
alias of `Blur`). Ideal for frosted glass effects.

```python
from tempestroid import BackdropFilter, Container, Stack, Style, Text

Stack(
    children=[
        Container(
            style=Style(background="https://example.com/bg.jpg"),
            key="bg",
        ),
        BackdropFilter(
            radius=16.0,
            child=Container(
                style=Style(
                    background="rgba(255,255,255,0.2)",
                    padding=24.0,
                    border_radius=12.0,
                ),
                child=Text(content="Frosted glass", key="label"),
                key="glass",
            ),
            key="backdrop",
        ),
    ],
)
```

![BackdropFilter](../../assets/components/backdrop_filter.png)

| Prop | Type | Default | Description |
|---|---|---|---|
| `radius` | `float` | `8.0` | Blur radius applied to the layers behind the child. |
| `child` | `Widget \| None` | `None` | The child displayed on top of the blur. |

!!! note "BackdropFilter vs Blur"
    `Blur` blurs the **child itself**; `BackdropFilter` blurs **what is behind**
    the child (lower layers). The operation is the same Gaussian blur by radius
    — the difference is which target is blurred.

---

## ClipPath

Clips its child to a predefined shape.

```python
from tempestroid import ClipPath, Image
from tempestroid.widgets.media import ClipShape

ClipPath(
    shape=ClipShape.CIRCLE,
    radius=0.0,
    child=Image(src="https://example.com/avatar.jpg", key="img"),
    key="clip",
)
```

![ClipPath](../../assets/components/clip_path.png)

| Prop | Type | Default | Description |
|---|---|---|---|
| `shape` | `ClipShape` | `ClipShape.ROUNDED_RECT` | Clip shape: `ROUNDED_RECT`, `CIRCLE`, `OVAL`. |
| `radius` | `float` | `8.0` | Corner radius for `ROUNDED_RECT`. Ignored for `CIRCLE` / `OVAL`. |
| `child` | `Widget \| None` | `None` | The child to clip. |

---

## CameraPreview

**(Device-only)** — Live camera preview surface, rendered by the device hardware.
Shows a signalled placeholder in the Qt simulator.

```python
from tempestroid import CameraPreview

CameraPreview(
    facing="back",
    key="cam",
)
```

![CameraPreview](../../assets/components/camera_preview.png)

| Prop | Type | Default | Description |
|---|---|---|---|
| `facing` | `str` | `"back"` | Camera to use: `"back"` (rear) or `"front"` (selfie). |

!!! warning "Device-only"
    `CameraPreview` requires access to Android camera hardware. In the Qt
    simulator it appears as a **signalled placeholder** — no real camera is
    accessed on the desktop.

---

## QrScanner

**(Device-only)** — Live camera surface that reads QR codes and barcodes in
real time, reporting each result via `on_scan`. Shows a signalled placeholder in
the Qt simulator.

```python
from tempestroid import QrScanner, QrScanEvent, Text

async def on_code(e: QrScanEvent) -> None:
    app.set_state(lambda s: setattr(s, "last_code", e.value))

QrScanner(
    on_scan=on_code,
    key="scanner",
)
```

![QrScanner](../../assets/components/qr_scanner.png)

| Prop | Type | Default | Description |
|---|---|---|---|
| `on_scan` | `handler → QrScanEvent` | `None` | Called for each detected code. The handler receives a `QrScanEvent` with the `value` field (the decoded string). |

!!! warning "Device-only"
    `QrScanner` requires Android camera hardware. In the Qt simulator it
    appears as a **signalled placeholder** — no code is scanned on the desktop.

---

## MapView

**(Device-only)** — Interactive map centred on a coordinate, with optional
markers. Shows a signalled placeholder in the Qt simulator.

```python
from tempestroid import MapView

MapView(
    latitude=-15.7801,
    longitude=-47.9292,
    zoom=14.0,
    markers=[
        {"lat": -15.7801, "lon": -47.9292, "title": "Brasília"},
    ],
    key="map",
)
```

![MapView](../../assets/components/map_view.png)

| Prop | Type | Default | Description |
|---|---|---|---|
| `latitude` | `float` | `0.0` | Centre latitude in decimal degrees. |
| `longitude` | `float` | `0.0` | Centre longitude in decimal degrees. |
| `zoom` | `float` | `12.0` | Zoom level (typical range: 1–20). |
| `markers` | `list[dict[str, Any]]` | `[]` | List of markers; each dict must have `"lat"`, `"lon"` and optionally `"title"`. |

!!! warning "Device-only"
    `MapView` depends on Android map APIs (Google Maps or equivalent). In the
    Qt simulator it appears as a **signalled placeholder** — no real map is
    loaded on the desktop.

---

## Recap

- **`Image` / `Icon`** — raster and named-vector primitives; both work on both
  renderers.
- **`Svg`** — scalable vector graphic from a URL or asset.
- **`Canvas`** — programmatic drawing surface via a command list; great for
  custom charts and graphics.
- **`VideoPlayer` / `WebView`** — embedded content (video and web page); work on
  both renderers.
- **`Blur` / `BackdropFilter`** — Gaussian blur effects over the child itself or
  the layers behind it; `radius` controls intensity.
- **`ClipPath`** — clips the child to `ROUNDED_RECT`, `CIRCLE`, or `OVAL`.
- **`CameraPreview` / `QrScanner` / `MapView`** — Android device only (Compose);
  appear as a placeholder in Qt.

Next steps: style the widgets with **[Styles](../estilos.en.md)**, explore
animation effects in **[Animation](animation.en.md)**, or see full apps in the
**[Example gallery](../exemplos.en.md)**.

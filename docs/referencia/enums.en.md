# Enums

tempestroid's enums are typed constants that express intent — values like
`AlignItems.CENTER`, `FontWeight.BOLD`, or `Curve.EASE_IN_OUT` travel as strings
to the renderer (Qt or Compose) and across the native bridge. All are importable
from the top-level package:

```python
from tempestroid import AlignItems, FontWeight, JustifyContent, Style
```

!!! tip "Design-system enums"
    The variant-API enums — `Variant` (solid/outline/ghost/link), `Size`
    (xs/sm/md/lg), `FieldVariant` (outline/filled/flushed) and `ComponentState` —
    come from the `tempest_core` package and are described in the
    [design-system guide](../guia/design-system/variantes.md).

Each member exposes a `.value` attribute holding the string (or integer) that
crosses the boundary; always use the member name (`AlignItems.CENTER`), not the
raw `.value`.

**Quick example:**

```python
from tempestroid import AlignItems, FlexDirection, FontWeight, JustifyContent, Style

layout = Style(
    direction=FlexDirection.COLUMN,
    justify=JustifyContent.SPACE_BETWEEN,
    align=AlignItems.CENTER,
)

text = Style(
    font_weight=FontWeight.SEMIBOLD,
    font_size=18.0,
)
```

---

## Layout and flexbox

### AlignItems

Controls child alignment on the **cross-axis**, equivalent to the CSS
`align-items` property.

| Member | Value | Meaning |
|---|---|---|
| `START` | `"start"` | Children aligned to the start of the cross-axis. |
| `END` | `"end"` | Children aligned to the end of the cross-axis. |
| `CENTER` | `"center"` | Children centered on the cross-axis. |
| `STRETCH` | `"stretch"` | Children stretched to fill the cross-axis. |

### JustifyContent

Distributes space between children along the **main axis**, equivalent to CSS
`justify-content`.

| Member | Value | Meaning |
|---|---|---|
| `START` | `"start"` | Children packed at the start of the main axis. |
| `END` | `"end"` | Children packed at the end of the main axis. |
| `CENTER` | `"center"` | Children centered on the main axis. |
| `SPACE_BETWEEN` | `"space-between"` | Equal space between children; no margin at the edges. |
| `SPACE_AROUND` | `"space-around"` | Equal space around each child. |
| `SPACE_EVENLY` | `"space-evenly"` | Identical space at every gap (including edges). |

### FlexDirection

Sets the main-axis direction of a flex container.

| Member | Value | Meaning |
|---|---|---|
| `ROW` | `"row"` | Children laid out in a row (horizontal). |
| `COLUMN` | `"column"` | Children laid out in a column (vertical). |

### FlexWrap

Controls whether children can wrap to the next line when space runs out,
equivalent to CSS `flex-wrap`. Used by the `Wrap` widget and `Style.flex_wrap`.

| Member | Value | Meaning |
|---|---|---|
| `NOWRAP` | `"nowrap"` | All children on one line; overflows if needed. |
| `WRAP` | `"wrap"` | Children wrap to the next line when there is no room. |
| `WRAP_REVERSE` | `"wrap-reverse"` | Like `WRAP`, but wrapping goes in the opposite direction. |

### Position

Controls the positioning mode of a child inside a `Stack`. The `top`/`right`/
`bottom`/`left` fields only take effect when `position=Position.ABSOLUTE`.

| Member | Value | Meaning |
|---|---|---|
| `STATIC` | `"static"` | Normal flow positioning. |
| `ABSOLUTE` | `"absolute"` | Positioned with explicit coordinates relative to the parent. |

### StackAlign

Aligns **non-positioned** children on both axes inside a `Stack`.

| Member | Value | Meaning |
|---|---|---|
| `TOP_START` | `"top_start"` | Top-left corner. |
| `TOP_CENTER` | `"top_center"` | Top edge, centered horizontally. |
| `TOP_END` | `"top_end"` | Top-right corner. |
| `CENTER_START` | `"center_start"` | Vertically centered, left-aligned. |
| `CENTER` | `"center"` | Centered on both axes. |
| `CENTER_END` | `"center_end"` | Vertically centered, right-aligned. |
| `BOTTOM_START` | `"bottom_start"` | Bottom-left corner. |
| `BOTTOM_CENTER` | `"bottom_center"` | Bottom edge, centered horizontally. |
| `BOTTOM_END` | `"bottom_end"` | Bottom-right corner. |

---

## Text and typography

### FontWeight

Font weight on the numeric CSS scale. Use `Style.font_weight`.

| Member | Value | Meaning |
|---|---|---|
| `THIN` | `100` | Lightest available weight. |
| `LIGHT` | `300` | Slightly thinner than normal. |
| `NORMAL` | `400` | Default weight. |
| `MEDIUM` | `500` | Slightly heavier than normal. |
| `SEMIBOLD` | `600` | Soft bold, good for secondary headings. |
| `BOLD` | `700` | Standard bold. |
| `BLACK` | `900` | Maximum weight. |

### FontStyle

Font style. Use `Style.font_style`.

| Member | Value | Meaning |
|---|---|---|
| `NORMAL` | `"normal"` | Roman (upright) font style (default). |
| `ITALIC` | `"italic"` | Italic font style. |

### TextAlign

Horizontal text alignment. Use `Style.text_align`.

| Member | Value | Meaning |
|---|---|---|
| `LEFT` | `"left"` | Text aligned to the left. |
| `CENTER` | `"center"` | Text centered. |
| `RIGHT` | `"right"` | Text aligned to the right. |
| `JUSTIFY` | `"justify"` | Justified text (both edges aligned). |

### TextDecoration

Text decoration. Use `Style.text_decoration`.

| Member | Value | Meaning |
|---|---|---|
| `NONE` | `"none"` | No decoration. |
| `UNDERLINE` | `"underline"` | Underlined text. |
| `LINE_THROUGH` | `"line-through"` | Struck-through text. |

### TextOverflow

Behavior when text overflows its container. Use `Style.text_overflow`.

| Member | Value | Meaning |
|---|---|---|
| `CLIP` | `"clip"` | Text clipped abruptly at the container boundary. |
| `ELLIPSIS` | `"ellipsis"` | Text clipped with a trailing ellipsis (`…`). |

### KeyboardType

Soft keyboard type shown when editing an `Input`. Use `Input.keyboard_type`.

| Member | Value | Meaning |
|---|---|---|
| `TEXT` | `"text"` | Standard alphanumeric keyboard (default). |
| `NUMBER` | `"number"` | Numeric keypad. |
| `EMAIL` | `"email"` | Keyboard optimized for e-mail addresses (suggests `@`). |
| `PHONE` | `"phone"` | Telephone dial-pad. |
| `URL` | `"url"` | Keyboard optimized for URLs (suggests `.`/`/`). |
| `PASSWORD` | `"password"` | Characters are masked as typed. |

---

## Color, gradient, and image

### GradientDirection

Direction of a linear gradient. Passed as `Gradient.direction`.

| Member | Value | Meaning |
|---|---|---|
| `TOP_BOTTOM` | `"top-bottom"` | From top to bottom. |
| `BOTTOM_TOP` | `"bottom-top"` | From bottom to top. |
| `LEFT_RIGHT` | `"left-right"` | From left to right. |
| `RIGHT_LEFT` | `"right-left"` | From right to left. |

### ImageFit

How the image fills its container, equivalent to CSS `object-fit`. Passed as
`Image.fit`.

| Member | Value | Meaning |
|---|---|---|
| `CONTAIN` | `"contain"` | Image scaled to fit without cropping (preserves aspect ratio). |
| `COVER` | `"cover"` | Image scaled to cover the whole container (may crop). |
| `FILL` | `"fill"` | Image stretched to fill the container (ignores aspect ratio). |
| `NONE` | `"none"` | No scaling; displayed at its original size. |

### ClipShape

Shape of the clip applied by `ClipPath`.

| Member | Value | Meaning |
|---|---|---|
| `CIRCLE` | `"circle"` | Circular clip (avatars, round icons). |
| `ROUNDED_RECT` | `"rounded_rect"` | Rectangle with rounded corners. |
| `OVAL` | `"oval"` | Ellipse — wider or taller than a circle. |

---

## Animation

### Curve

Easing curve for `Transition` and for the Track E animation controllers.

| Member | Value | Meaning |
|---|---|---|
| `LINEAR` | `"linear"` | Constant speed throughout the animation. |
| `EASE_IN` | `"ease-in"` | Starts slow, accelerates toward the end. |
| `EASE_OUT` | `"ease-out"` | Starts fast, decelerates toward the end. |
| `EASE_IN_OUT` | `"ease-in-out"` | Slow at both ends, fast in the middle. |
| `EASE` | `"ease"` | Smooth easing similar to the CSS default. |
| `BOUNCE` | `"bounce"` | Bouncing effect when reaching the final value. |
| `ELASTIC` | `"elastic"` | Overshoots slightly then springs back. |

```python
from tempestroid import Color, Curve, Style, Transition

Style(
    background=Color.from_hex("#3b82f6"),
    transition=Transition(duration_ms=250, curve=Curve.EASE_IN_OUT),
)
```

---

## Theme and screen

### ThemeMode

Application theme mode. Set via `App.set_theme`.

| Member | Value | Meaning |
|---|---|---|
| `LIGHT` | `"light"` | Light theme forced. |
| `DARK` | `"dark"` | Dark theme forced. |
| `SYSTEM` | `"system"` | Follows the operating system preference. |

### Orientation

Requested screen orientation. Passed in platform calls.

| Member | Value | Meaning |
|---|---|---|
| `PORTRAIT` | `"portrait"` | Vertical orientation. |
| `LANDSCAPE` | `"landscape"` | Horizontal orientation. |
| `AUTO` | `"auto"` | System decides based on the device's physical position. |

### StatusBarStyle

Style of the status-bar icons. Passed in platform calls.

| Member | Value | Meaning |
|---|---|---|
| `LIGHT` | `"light"` | Light icons (use on dark status bars). |
| `DARK` | `"dark"` | Dark icons (use on light status bars). |

### SafeAreaEdge

Edges to be respected by the `SafeArea` widget. Pass multiple values as a list to
`SafeArea.edges`.

| Member | Value | Meaning |
|---|---|---|
| `TOP` | `"top"` | Top inset (status bar / notch). |
| `RIGHT` | `"right"` | Right inset (landscape mode / side camera). |
| `BOTTOM` | `"bottom"` | Bottom inset (navigation bar / home indicator). |
| `LEFT` | `"left"` | Left inset (landscape mode). |

### Device

Qt simulator screen preset. Passed to `run_qt(size=Device.PIXEL_8)`. Each
member's value is the **device's display name**; the simulator uses the
corresponding dp dimensions to size the window.

**Available families:**

| Family | Members |
|---|---|
| Google Pixel | `PIXEL_4`, `PIXEL_4A`, `PIXEL_5`, `PIXEL_6`, `PIXEL_6A`, `PIXEL_7`, `PIXEL_7A`, `PIXEL_8`, `PIXEL_8_PRO` |
| Samsung Galaxy S | `GALAXY_S8`, `GALAXY_S21`, `GALAXY_S22`, `GALAXY_S23`, `GALAXY_S23_ULTRA`, `GALAXY_S24`, `GALAXY_S24_ULTRA` |
| Samsung Galaxy A | `GALAXY_A51`, `GALAXY_A52`, `GALAXY_A54` |
| Redmi / Poco / Xiaomi | `REDMI_NOTE_10`, `REDMI_NOTE_11`, `REDMI_NOTE_12`, `REDMI_NOTE_13`, `REDMI_11`, `REDMI_12`, `POCO_X5`, `XIAOMI_13`, `XIAOMI_14` |
| Motorola | `MOTO_G_POWER`, `MOTO_G52` |
| OnePlus | `ONEPLUS_9`, `ONEPLUS_11` |

**Example:**

```python
from tempestroid import Device
from tempestroid.renderers.qt import run_qt

# Simulate a Pixel 8 (1080 × 2400 dp)
run_qt(state, view, title="My App", size=Device.PIXEL_8)
```

!!! tip "33 presets in total"
    Use `Device.<TAB>` in the REPL to browse all available options.

---

## Platform and system

### AppState

Application lifecycle state, received in `LifecycleEvent.state`.

| Member | Value | Meaning |
|---|---|---|
| `FOREGROUND` | `"foreground"` | App visible and focused. |
| `BACKGROUND` | `"background"` | App in the background (not visible). |
| `INACTIVE` | `"inactive"` | App visible but without focus (e.g., a system overlay). |

### ConnectivityState

Network connectivity state, received in `ConnectivityEvent.state`.

| Member | Value | Meaning |
|---|---|---|
| `CONNECTED` | `"connected"` | Connected to some network. |
| `DISCONNECTED` | `"disconnected"` | No connectivity. |
| `WIFI` | `"wifi"` | Connected via Wi-Fi. |
| `MOBILE` | `"mobile"` | Connected via mobile network (cellular data). |

### PermissionStatus

Result of a platform permission request.

| Member | Value | Meaning |
|---|---|---|
| `GRANTED` | `"granted"` | Permission granted by the user. |
| `DENIED` | `"denied"` | Permission denied (can be requested again). |
| `PERMANENTLY_DENIED` | `"permanently_denied"` | Permanently denied; direct the user to Settings. |

### SensorType

Physical sensor type to subscribe to via `native`. Passed when registering a
sensor callback.

| Member | Value | Meaning |
|---|---|---|
| `ACCELEROMETER` | `"accelerometer"` | Linear acceleration on three axes (m/s²). |
| `GYROSCOPE` | `"gyroscope"` | Rotation rate on three axes (rad/s). |
| `MAGNETOMETER` | `"magnetometer"` | Magnetic field on three axes (μT). |
| `PRESSURE` | `"pressure"` | Barometric pressure (hPa). |
| `LIGHT` | `"light"` | Ambient illuminance level (lux). |
| `PROXIMITY` | `"proximity"` | Distance to a nearby object (cm or binary). |
| `STEP_COUNTER` | `"step_counter"` | Cumulative step count since last boot. |

### ImpactStyle

Haptic feedback intensity generated by `native.haptics`. Passed in vibration
calls.

| Member | Value | Meaning |
|---|---|---|
| `LIGHT` | `"light"` | Soft tap (subtle confirmations). |
| `MEDIUM` | `"medium"` | Medium tap (standard interactions). |
| `HEAVY` | `"heavy"` | Strong tap (alerts or destructive actions). |

---

## Gestures

### SwipeDirection

Direction of a swipe gesture, received in `SwipeEvent.direction`.

| Member | Value | Meaning |
|---|---|---|
| `LEFT` | `"left"` | Swiped to the left. |
| `RIGHT` | `"right"` | Swiped to the right. |
| `UP` | `"up"` | Swiped upward. |
| `DOWN` | `"down"` | Swiped downward. |

---

## Recap

- Always import from the package level: `from tempestroid import AlignItems, Curve`.
- Use the **member name** (`FontWeight.BOLD`), not the raw string value.
- The `.value` of each member is the string (or integer) sent to the renderer and
  the native bridge — you will rarely need to access it directly.
- Layout enums (`AlignItems`, `JustifyContent`, `FlexDirection`, `FlexWrap`,
  `Position`, `StackAlign`) are `Style` fields; platform enums (`AppState`,
  `ConnectivityState`, `SensorType`) arrive inside events; `Device` sizes the
  simulator window.
- The full reference of `Style` fields is in the [styles guide](../guia/estilos.md);
  the events that carry these enums are in the [events guide](../guia/eventos.md).

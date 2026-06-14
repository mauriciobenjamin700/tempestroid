# Qt renderer fidelity roadmap

Box-model fidelity gaps in the Qt desktop simulator (`tempestroid/renderers/qt/`)
and the imperative fixes that close them. Each fix lives in the renderer (not the
`Style` translator), so the phase-D conformance `_COVERAGE` table is unchanged —
the translator stays inert and Compose keeps owning the device-side realization.

The items are implemented in order: P0 → P1 (radius) → P1 (sizing) → P2.

## P0 — Unscoped QSS cascades box decoration onto children

**Symptom.** Every text/icon inside a bordered card gets a stray 1px box; a
container background tints descendants.

**Root cause.** The renderer applied a *bare* QSS body
(`node.widget.setStyleSheet(qss)`, where `qss = "border: …; border-radius: …; …"`).
Qt treats bare declarations as an implicit universal selector, so the box
decoration applies to the widget **and all its descendants**; a child's own
`setStyleSheet` (color/font) does not reset the inherited border.

**Fix.** Scope every node's QSS to itself via an `#objectName` selector
(`_scoped_stylesheet`):

```python
name = node.widget.objectName() or f"tw_{id(node.widget):x}"
node.widget.setObjectName(name)
node.widget.setStyleSheet(f"#{name} {{ {qss} }}")
```

The same scoping is applied to the other `setStyleSheet` sites carrying box
decoration (the `FormField` error label and the `Toast`/`Tooltip` floating
pills). `_TextLabel.paintEvent` still draws its own background/border because the
scoped QSS still targets the label itself.

## P1 — border-radius does not clip the background reliably

**Symptom.** A box with a background plus a large radius (pill sentinel `999`)
renders square; circles/pills are squared off.

**Root cause.** (1) Qt only clips a QSS `background-color` to `border-radius` when
the widget has `WA_StyledBackground` set *or* a border is also present —
background-only rounded boxes paint square. (2) `style_translator._qss_radius_rules`
emits the raw value, so `999px` passes through and Qt's handling of a radius far
larger than the box is inconsistent.

**Fix.** In `_apply_visual`, when `style.background is not None or style.radius is
not None`, set `WA_StyledBackground`. After sizing, clamp a uniform radius to
`min(w, h) / 2` (the pill sentinel becomes fully rounded); per-corner `Corners`
clamps component-wise (`_clamp_radius`). The clamp re-renders the scoped QSS with
a size-adjusted copy of the style (`_clamp_node_radius`), so the translator stays
inert. Custom-painted widgets honor the clamp too: `_ClipWidget._apply_mask`
clamps its rounded-rect radius; `_TextLabel` paints its box from the (now clamped)
scoped QSS; `_CanvasWidget` draws explicit command geometry with no border-radius,
so it is unaffected.

## P1 — Fixed size not honored for flex containers

**Symptom.** A `Container` with `width == height` (icon disc, avatar) renders
oval/stretched, not square.

**Root cause.** `_apply_sizing` did `setFixedWidth`/`setFixedHeight`, but for a
container that is also a flex child the parent `QBoxLayout` stretch wins on the
cross axis (the size policy was not pinned).

**Fix.** When **both** dimensions are fixed, also
`setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)`; otherwise the
policy is reset to `Preferred`/`Preferred` (idempotent). `_apply_sizing` targets
the styled widget (the one carrying the background) for container nodes.

## P2 — Arbitrary icon names fall back to raw text

**Symptom.** `Icon(name="photo_camera")` (a non-curated Material name) shows the
literal string. The curated set is ~28 line icons.

**Root cause.** `_icon_pixmap` returned `None` for unknown names, so the caller
rendered the name as text.

**Fix.** A built-in Material-name → curated alias map (`_ICON_ALIASES`,
`_resolve_icon_name`) maps common names (`photo_camera`, `image`, `history`,
`person`, `science`, `close`, `add`, `delete`, …) to the nearest curated glyph,
consulted by `_icon_pixmap` before it gives up. `register_icon` remains the escape
hatch for project-specific glyphs.

## Validation

Headless tests under `QT_QPA_PLATFORM=offscreen` (`tests/unit/test_qt_boxmodel.py`):

- **P0** — a bordered `Container` with a `Text` child: the child's stylesheet
  carries no `border`; the container's box QSS is `#objectName`-scoped.
- **P1 (radius)** — a 96×96 styled `Container` with a `999` pill radius emits
  `border-radius: 48.0px` (clamped to `min(w, h) / 2`); `_clamp_radius` /
  `_clamp_radius_value` unit-checked for uniform and per-corner radii.
- **P1 (sizing)** — a both-dimensions-fixed `Container` pins a `Fixed`/`Fixed`
  size policy (square); a single fixed dimension stays flexible.
- **P2** — `Icon(name="photo_camera")` resolves to a curated glyph pixmap instead
  of the literal-text fallback (`_resolve_icon_name` / `_icon_pixmap`).

The `Style` translators (`to_qss` / `to_compose`) are **unchanged**, so the
phase-D conformance goldens and the `_COVERAGE` parity table are untouched — all
fixes are imperative in the renderer (the A3 pattern).

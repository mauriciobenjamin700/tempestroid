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

## Parity — `margin` now reacts in the `Style → Qt` translator

**Symptom.** `Style.margin` rendered nothing in the Qt simulator: the
`Style → Qt` translator never emitted it and the renderer never applied it, so a
margined box sat flush against its siblings. Compose, by contrast, lowers
`margin` into its spec (mirrored under RTL), making the two renderers diverge —
the only box-model field where Qt was silently inert.

**Root cause.** `to_qss` emitted `padding`/`border`/`radius`/`min`/`max` but had
no `margin` branch; no renderer code read `style.margin`.

**Fix (translator, not imperative).** Unlike the four box-model items above —
which stay imperative so `_COVERAGE` is untouched — `margin` is realized in the
**translator** to keep parity with Compose (the Compose side consumes `margin`
in its translator too). `to_qss` now emits a QSS `margin: T R B L` rule for both
leaves and containers (always, unlike `padding`, which a container routes to its
layout's `contentsMargins`), with `left`/`right` mirrored under `rtl`. Qt honours
a QSS `margin` on a styled widget as true *outer* space: the background/border
paints inside the margin, leaving the margin zone transparent — matching
Compose's `Modifier` padding outside the background. `_apply_visual` sets
`WA_StyledBackground` when a margin is present so the outer space renders even on
a border/background-only box.

**Conformance touched (deliberately).** `_COVERAGE["margin"]` flips
`(True, False) → (True, True)`; the `grow_margin` and `rtl_layout` goldens were
regenerated (`UPDATE_GOLDEN=1`) to include the new `margin` QSS; the resolved
`margin` row was removed from the E9 `_E9_RTL_DIVERGENCES` tripwire table and
`test_e9_rtl_margin_divergence_is_real` was rewritten as
`test_e9_rtl_margin_parity` (both translators mirror margin under RTL). Gradient
backgrounds, `Border`/`SideBorder`, and `min/max` sizing were audited and were
already faithful (golden `gradient`/`corners_sides`/`sizing`, all `(True, True)`)
— no change needed.

## Validation

Headless tests under `QT_QPA_PLATFORM=offscreen` (`tests/unit/test_qt_boxmodel.py`):

- **margin** — a margined `Container` carries a `margin: T R B L` QSS rule with
  `WA_StyledBackground` set (`test_margin_emitted_into_node_qss`); a rendered
  margined box leaves the margin zone clear and paints the background inside it
  (`test_margin_renders_as_true_outer_space`).
- **P0** — a bordered `Container` with a `Text` child: the child's stylesheet
  carries no `border`; the container's box QSS is `#objectName`-scoped.
- **P1 (radius)** — a 96×96 styled `Container` with a `999` pill radius emits
  `border-radius: 48.0px` (clamped to `min(w, h) / 2`); `_clamp_radius` /
  `_clamp_radius_value` unit-checked for uniform and per-corner radii.
- **P1 (sizing)** — a both-dimensions-fixed `Container` pins a `Fixed`/`Fixed`
  size policy (square); a single fixed dimension stays flexible.
- **P2** — `Icon(name="photo_camera")` resolves to a curated glyph pixmap instead
  of the literal-text fallback (`_resolve_icon_name` / `_icon_pixmap`).

The four box-model fixes above (P0–P2) are imperative in the renderer (the A3
pattern), so the `Style → Qt` translator stays inert for them and the phase-D
conformance goldens / `_COVERAGE` parity table are untouched. The **margin**
parity fix is the one deliberate exception: it lives in the `to_qss` translator
(to match Compose), so its `_COVERAGE` row, two goldens, and the E9 RTL tripwire
were updated alongside it.

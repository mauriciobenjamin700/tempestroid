"""Unit tests for the E7 media and graphics widgets.

Covers the ``Canvas`` draw-command IR (every command instantiates, serializes to
JSON-safe dicts with no tuples, and discriminates on ``kind``), the ``QrScanner``
event contract, the ``QrScanEvent`` boundary validation, and that the remaining
media widgets instantiate with valid defaults.
"""

from __future__ import annotations

from typing import Any

import pytest

from tempestroid import (
    ArcTo,
    BackdropFilter,
    Blur,
    CameraPreview,
    Canvas,
    ClipPath,
    ClipShape,
    Close,
    Container,
    DrawOval,
    DrawRect,
    DrawText,
    FillCmd,
    LineTo,
    MapView,
    MoveTo,
    QrScanEvent,
    QrScanner,
    StrokeCmd,
    Svg,
    Text,
    VideoPlayer,
    WebView,
    parse_event,
)


def _has_tuple(value: Any) -> bool:
    """Recursively detect any tuple inside a dumped command dict.

    Args:
        value: A value from a dumped draw command.

    Returns:
        ``True`` if a tuple appears anywhere in the structure.
    """
    if isinstance(value, tuple):
        return True
    if isinstance(value, dict):
        values: list[Any] = list(value.values())  # type: ignore[arg-type]
        return any(_has_tuple(item) for item in values)
    if isinstance(value, list):
        items: list[Any] = list(value)  # type: ignore[arg-type]
        return any(_has_tuple(item) for item in items)
    return False


def test_each_draw_command_serializes_without_tuples() -> None:
    commands = [
        MoveTo(x=1.0, y=2.0),
        LineTo(x=3.0, y=4.0),
        ArcTo(x=0.0, y=0.0, width=10.0, height=10.0, start_angle=0.0, sweep_angle=90.0),
        Close(),
        FillCmd(color=[1.0, 0.0, 0.0, 1.0]),
        StrokeCmd(color=[0.0, 1.0, 0.0, 0.5], width=3.0),
        DrawText(text="hi", x=1.0, y=2.0),
        DrawRect(x=1.0, y=2.0, width=3.0, height=4.0),
        DrawOval(x=5.0, y=6.0, width=7.0, height=8.0),
    ]
    for cmd in commands:
        dumped = cmd.model_dump()
        assert "kind" in dumped
        assert not _has_tuple(dumped), f"{cmd!r} dumped to a tuple"


def test_draw_command_colors_are_lists() -> None:
    assert FillCmd(color=[1.0, 0.0, 0.0, 1.0]).color == [1.0, 0.0, 0.0, 1.0]
    # Default color is a fresh list, not shared between instances.
    a = DrawText(text="a", x=0.0, y=0.0)
    b = DrawText(text="b", x=0.0, y=0.0)
    assert a.color == [0.0, 0.0, 0.0, 1.0]
    assert a.color is not b.color


def test_canvas_holds_all_nine_command_kinds() -> None:
    canvas = Canvas(
        width=100.0,
        height=50.0,
        commands=[
            MoveTo(x=0.0, y=0.0),
            LineTo(x=1.0, y=1.0),
            ArcTo(
                x=0.0, y=0.0, width=2.0, height=2.0,
                start_angle=0.0, sweep_angle=45.0,
            ),
            Close(),
            FillCmd(color=[0.0, 0.0, 0.0, 1.0]),
            StrokeCmd(color=[1.0, 1.0, 1.0, 1.0]),
            DrawText(text="x", x=0.0, y=0.0),
            DrawRect(x=0.0, y=0.0, width=1.0, height=1.0),
            DrawOval(x=0.0, y=0.0, width=1.0, height=1.0),
        ],
    )
    assert len(canvas.commands) == 9
    kinds = {cmd.kind for cmd in canvas.commands}
    assert kinds == {
        "move_to",
        "line_to",
        "arc_to",
        "close",
        "fill",
        "stroke",
        "draw_text",
        "draw_rect",
        "draw_oval",
    }


def test_canvas_default_commands_is_empty_list() -> None:
    assert Canvas().commands == []
    assert Canvas().width is None and Canvas().height is None


def test_canvas_command_discriminator_validates_from_dict() -> None:
    # Pydantic re-validates a command dict against the right union member by kind.
    canvas = Canvas.model_validate(
        {"commands": [{"kind": "fill", "color": [1.0, 0.0, 0.0, 1.0]}]}
    )
    assert isinstance(canvas.commands[0], FillCmd)
    assert canvas.commands[0].color == [1.0, 0.0, 0.0, 1.0]


def test_qr_scanner_declares_on_scan_event() -> None:
    assert "on_scan" in QrScanner.event_schemas
    assert QrScanner.event_schemas["on_scan"] is QrScanEvent

    def _on_scan() -> None:
        return None

    scanner = QrScanner(on_scan=_on_scan)
    assert scanner.on_scan is not None


def test_parse_qr_scan_event() -> None:
    event = parse_event(QrScanEvent, {"data": "https://example.com"})
    assert event.data == "https://example.com"
    assert event.format == "QR_CODE"
    explicit = parse_event(QrScanEvent, {"data": "123", "format": "EAN_13"})
    assert explicit.format == "EAN_13"


def test_remaining_media_widgets_instantiate_with_defaults() -> None:
    assert VideoPlayer(src="movie.mp4").autoplay is False
    assert VideoPlayer(src="movie.mp4").controls is True
    assert WebView(url="https://example.com").javascript_enabled is True
    assert Svg(src="logo.svg").fit.value == "contain"
    assert CameraPreview().facing == "back"
    assert MapView().zoom == 12.0
    assert MapView().markers == []
    assert Blur().radius == 8.0
    assert BackdropFilter().radius == 8.0
    assert ClipPath().shape is ClipShape.ROUNDED_RECT
    assert ClipPath().radius == 8.0


def test_blur_and_clip_path_expose_their_child() -> None:
    inner = Text(content="hi")
    assert Blur(child=inner).child_nodes() == [inner]
    assert BackdropFilter(child=inner).child_nodes() == [inner]
    assert ClipPath(child=inner).child_nodes() == [inner]
    assert Blur().child_nodes() == []
    # A clipped container nests correctly.
    clipped = ClipPath(shape=ClipShape.CIRCLE, child=Container(child=inner))
    assert len(clipped.child_nodes()) == 1


def test_parse_qr_scan_event_invalid_raises_event_validation_error() -> None:
    """An invalid payload raises ``EventValidationError`` with structured errors.

    ``parse_event`` is the boundary gate: the device side sends raw JSON; any
    structural mismatch must surface as a typed, JSON-serializable error rather
    than a raw Pydantic ``ValidationError``.
    """
    from tempestroid.widgets.events import EventValidationError

    # Missing required field 'data'.
    with pytest.raises(EventValidationError) as exc_info:
        parse_event(QrScanEvent, {})
    exc = exc_info.value
    assert exc.event_type is QrScanEvent
    assert isinstance(exc.errors, list)
    assert len(exc.errors) > 0, "errors list must not be empty"
    # Each error must be a dict (JSON-serializable).
    for err in exc.errors:
        assert isinstance(err, dict)

    # Wrong type for 'data'.
    with pytest.raises(EventValidationError) as exc_info2:
        parse_event(QrScanEvent, {"data": 42})
    assert exc_info2.value.event_type is QrScanEvent


def test_map_view_empty_markers_default_is_list() -> None:
    """``MapView().markers`` is an empty list, not ``None``.

    The convention is that collection fields default to ``[]`` so renderers can
    iterate unconditionally without a None-check.  This pins the contract against
    an accidental ``list[dict] | None = None`` regression.
    """
    mv = MapView()
    assert mv.markers == []
    assert isinstance(mv.markers, list)
    # Two separate instances must not share the same list object.
    mv2 = MapView()
    assert mv.markers is not mv2.markers


def test_canvas_commands_diff_detects_change() -> None:
    """The reconciler diffs a Canvas commands change as a prop ``Update``.

    The diff compares the ``commands`` list by equality (value-based), so
    replacing a command produces exactly one ``Update`` patch carrying the new
    list.  This exercises the end-to-end correctness of the ``DrawCommand``
    list as a diffable IR prop — the key invariant that lets both renderers just
    consume the updated list.
    """
    from tempestroid.core.ir import Update
    from tempestroid.core.reconciler import build, diff

    old_canvas = Canvas(commands=[MoveTo(x=0.0, y=0.0)])
    new_canvas = Canvas(commands=[MoveTo(x=1.0, y=1.0)])
    patches = diff(build(old_canvas), build(new_canvas))
    assert len(patches) == 1
    assert isinstance(patches[0], Update)
    updated_cmds: list[Any] = patches[0].set_props["commands"]
    assert len(updated_cmds) == 1
    assert updated_cmds[0].x == 1.0
    assert updated_cmds[0].y == 1.0


def test_canvas_commands_diff_no_op_when_equal() -> None:
    """The reconciler emits no patch when a Canvas's commands are unchanged."""
    from tempestroid.core.reconciler import build, diff

    cmd = MoveTo(x=5.0, y=5.0)
    old_canvas = Canvas(commands=[cmd])
    new_canvas = Canvas(commands=[MoveTo(x=5.0, y=5.0)])
    patches = diff(build(old_canvas), build(new_canvas))
    # FillCmd color lists compare by value — same values means no diff.
    assert patches == [], (
        "equal command lists must produce no patch; "
        "check that DrawCommand equality is value-based (frozen Pydantic model)"
    )


def test_draw_command_default_color_is_not_shared_between_draw_text_instances() -> None:
    """Each ``DrawText`` instance gets its own color list (no shared mutable default).

    If ``color`` defaulted to a module-level list literal the instances would
    share it; mutation of one would corrupt the other.  This pins the
    ``Field(default_factory=...)`` pattern used in the IR definition.
    """
    a = DrawText(text="a", x=0.0, y=0.0)
    b = DrawText(text="b", x=0.0, y=0.0)
    assert a.color == [0.0, 0.0, 0.0, 1.0]
    assert b.color == [0.0, 0.0, 0.0, 1.0]
    # Frozen models — identity check verifies they are not the same object.
    assert a.color is not b.color, (
        "DrawText.color default must use default_factory; "
        "two instances must not share the same list object"
    )


def test_qr_scanner_event_schemas_classvar_is_correct_type() -> None:
    """``QrScanner.event_schemas`` maps ``'on_scan'`` to the ``QrScanEvent`` class.

    Pins the classvar declaration against accidental dict-level type regressions
    (e.g. a string instead of the class object, or a missing key after a rename).
    The bridge's ``event_type_for`` relies on the value being the *class itself*.
    """
    schema = QrScanner.event_schemas
    assert isinstance(schema, dict)
    assert list(schema.keys()) == ["on_scan"], (
        "QrScanner.event_schemas must have exactly one key: 'on_scan'"
    )
    assert schema["on_scan"] is QrScanEvent, (
        "QrScanner.event_schemas['on_scan'] must be the QrScanEvent class, "
        "not a string or instance"
    )


def test_video_player_props_survive_serialization() -> None:
    """``VideoPlayer`` props cross the serializer to plain JSON-safe dicts.

    Verifies the four boolean props plus ``src`` survive ``serialize_node``
    unchanged so both renderers can read them from the serialized tree without
    casting.
    """
    import json

    from tempestroid.bridge import serialize_node
    from tempestroid.core.reconciler import build

    vp = VideoPlayer(src="https://example.com/clip.mp4",
                     autoplay=True, loop=True, controls=False, muted=True)
    payload = serialize_node(build(vp))
    json.dumps(payload)  # must not raise
    assert payload["type"] == "VideoPlayer"
    props = payload["props"]
    assert props["src"] == "https://example.com/clip.mp4"
    assert props["autoplay"] is True
    assert props["loop"] is True
    assert props["controls"] is False
    assert props["muted"] is True


def test_web_view_props_survive_serialization() -> None:
    """``WebView`` props cross the serializer correctly."""
    import json

    from tempestroid.bridge import serialize_node
    from tempestroid.core.reconciler import build

    wv = WebView(url="https://example.com", javascript_enabled=False)
    payload = serialize_node(build(wv))
    json.dumps(payload)
    assert payload["type"] == "WebView"
    assert payload["props"]["url"] == "https://example.com"
    assert payload["props"]["javascript_enabled"] is False


def test_svg_fit_prop_is_string_in_serialized_output() -> None:
    """``Svg.fit`` serializes as a plain string in the serialized node props.

    ``ImageFit`` is a ``StrEnum``; JSON serializers treat it as a string
    natively.  Pins that ``fit`` does not appear as an enum object in the
    serialized output (which would break ``json.dumps``).
    """
    import json

    from tempestroid import Svg
    from tempestroid.bridge import serialize_node
    from tempestroid.core.reconciler import build

    node = serialize_node(build(Svg(src="logo.svg")))
    json.dumps(node)  # must not raise
    fit = node["props"]["fit"]
    assert isinstance(fit, str), (
        f"Svg.fit must serialize as a str, got {type(fit).__name__!r}"
    )
    assert fit == "contain"


def test_clip_path_all_shapes_round_trip_through_serializer() -> None:
    """Each ``ClipShape`` value serializes to a plain string in node props."""
    import json

    from tempestroid.bridge import serialize_node
    from tempestroid.core.reconciler import build

    for shape in ClipShape:
        node = serialize_node(build(ClipPath(shape=shape)))
        json.dumps(node)
        assert node["props"]["shape"] == shape.value, (
            f"ClipPath.shape={shape!r} must serialize to {shape.value!r}"
        )


def test_blur_radius_prop_survives_serialization() -> None:
    """``Blur.radius`` and ``BackdropFilter.radius`` serialize as floats."""
    import json

    from tempestroid.bridge import serialize_node
    from tempestroid.core.reconciler import build

    for widget in (Blur(radius=12.5), BackdropFilter(radius=4.0)):
        node = serialize_node(build(widget))
        json.dumps(node)
        assert node["props"]["radius"] == pytest.approx(  # type: ignore[attr-defined]
            widget.radius, abs=1e-9
        )

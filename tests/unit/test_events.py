import pytest

from tempestroid import (
    DateChangeEvent,
    DismissEvent,
    EventValidationError,
    FileSelectEvent,
    MenuSelectEvent,
    TapEvent,
    TextChangeEvent,
    ToggleEvent,
    parse_event,
)


def test_tap_event_round_trip():
    event = TapEvent(x=12.0, y=4.0)
    raw = event.model_dump()
    restored = parse_event(TapEvent, raw)
    assert restored == event


def test_text_change_round_trip():
    event = TextChangeEvent(value="hello")
    restored = parse_event(TextChangeEvent, event.model_dump())
    assert restored.value == "hello"


def test_toggle_event_round_trip():
    event = ToggleEvent(checked=True)
    restored = parse_event(ToggleEvent, event.model_dump())
    assert restored.checked is True


def test_date_change_round_trip():
    event = DateChangeEvent(value="2026-05-31")
    restored = parse_event(DateChangeEvent, event.model_dump())
    assert restored.value == "2026-05-31"


def test_file_select_round_trip():
    event = FileSelectEvent(uri="content://docs/1", name="report.pdf")
    restored = parse_event(FileSelectEvent, event.model_dump())
    assert restored.uri == "content://docs/1"
    assert restored.name == "report.pdf"


def test_file_select_name_optional():
    event = parse_event(FileSelectEvent, {"uri": "file:///tmp/x"})
    assert event.uri == "file:///tmp/x"
    assert event.name is None


def test_toggle_event_requires_checked():
    with pytest.raises(EventValidationError) as exc:
        parse_event(ToggleEvent, {})
    assert exc.value.errors[0]["loc"] == ("checked",)


def test_tap_event_defaults_when_empty_payload():
    event = parse_event(TapEvent, {})
    assert event.x is None and event.y is None


def test_invalid_payload_raises_structured_error():
    with pytest.raises(EventValidationError) as exc:
        parse_event(TextChangeEvent, {})  # missing required `value`
    err = exc.value
    assert err.event_type is TextChangeEvent
    assert isinstance(err.errors, list) and err.errors
    first = err.errors[0]
    assert first["loc"] == ("value",)
    assert first["type"] == "missing"


def test_wrong_type_raises_structured_error():
    with pytest.raises(EventValidationError) as exc:
        parse_event(TapEvent, {"x": "not-a-number"})
    assert exc.value.errors[0]["loc"] == ("x",)


def test_events_are_frozen():
    event = TapEvent(x=1.0)
    with pytest.raises(Exception):  # noqa: B017 — frozen model rejects mutation
        event.x = 2.0  # type: ignore[misc]


# --- DismissEvent (E2) -------------------------------------------------------


def test_dismiss_event_round_trip_no_id():
    """DismissEvent with no overlay_id round-trips via parse_event."""
    event = DismissEvent()
    restored = parse_event(DismissEvent, event.model_dump())
    assert restored == event
    assert restored.overlay_id is None


def test_dismiss_event_round_trip_with_id():
    """DismissEvent with an explicit overlay_id survives round-trip."""
    event = DismissEvent(overlay_id="dlg-abc-123")
    restored = parse_event(DismissEvent, event.model_dump())
    assert restored.overlay_id == "dlg-abc-123"


def test_dismiss_event_accepts_empty_payload():
    """DismissEvent accepts an empty payload; overlay_id defaults to None."""
    event = parse_event(DismissEvent, {})
    assert event.overlay_id is None


def test_dismiss_event_rejects_wrong_id_type():
    """A non-string overlay_id raises EventValidationError with a loc on overlay_id."""
    with pytest.raises(EventValidationError) as exc:
        parse_event(DismissEvent, {"overlay_id": 999})
    assert exc.value.event_type is DismissEvent
    assert exc.value.errors[0]["loc"] == ("overlay_id",)


def test_dismiss_event_is_frozen():
    """DismissEvent is immutable (Pydantic frozen model)."""
    event = DismissEvent(overlay_id="x")
    with pytest.raises(Exception):  # noqa: B017
        event.overlay_id = "y"  # type: ignore[misc]


# --- MenuSelectEvent (E2) ----------------------------------------------------


def test_menu_select_event_round_trip():
    """MenuSelectEvent round-trips via parse_event."""
    event = MenuSelectEvent(value="copy", label="Copy")
    restored = parse_event(MenuSelectEvent, event.model_dump())
    assert restored == event
    assert restored.value == "copy"
    assert restored.label == "Copy"


def test_menu_select_event_requires_value():
    """MenuSelectEvent without `value` raises EventValidationError on `value`."""
    with pytest.raises(EventValidationError) as exc:
        parse_event(MenuSelectEvent, {"label": "Copy"})
    errors = exc.value.errors
    locs = [e["loc"] for e in errors]
    assert ("value",) in locs


def test_menu_select_event_requires_label():
    """MenuSelectEvent without `label` raises EventValidationError on `label`."""
    with pytest.raises(EventValidationError) as exc:
        parse_event(MenuSelectEvent, {"value": "copy"})
    errors = exc.value.errors
    locs = [e["loc"] for e in errors]
    assert ("label",) in locs


def test_menu_select_event_missing_both_fields():
    """An empty MenuSelectEvent payload fails with structured errors for both fields."""
    with pytest.raises(EventValidationError) as exc:
        parse_event(MenuSelectEvent, {})
    assert exc.value.event_type is MenuSelectEvent
    locs = {e["loc"] for e in exc.value.errors}
    assert ("value",) in locs
    assert ("label",) in locs


def test_menu_select_event_is_frozen():
    """MenuSelectEvent is immutable (Pydantic frozen model)."""
    event = MenuSelectEvent(value="x", label="X")
    with pytest.raises(Exception):  # noqa: B017
        event.value = "y"  # type: ignore[misc]

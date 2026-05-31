import pytest

from tempestroid import (
    DateChangeEvent,
    EventValidationError,
    FileSelectEvent,
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

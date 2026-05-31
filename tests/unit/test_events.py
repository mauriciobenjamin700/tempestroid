import pytest

from tempestroid import (
    EventValidationError,
    TapEvent,
    TextChangeEvent,
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

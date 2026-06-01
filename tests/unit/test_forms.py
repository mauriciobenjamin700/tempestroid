"""Tests for the form aggregation, typed validation and submit gating (E5b).

``Form.validate`` is the boundary gate for a form — it runs every field's typed
validators purely in Python and produces a structured, JSON-serializable
``FormState`` (a flat ``dict[str, str]`` of per-field errors plus a ``valid``
flag). The application decides, from that state, whether to dispatch the form's
``SubmitEvent``. These tests pin that contract: validation blocks an invalid
submit with a per-field error, a valid submit dispatches the event, and the
state serializes to plain JSON.
"""

import asyncio
import json
from typing import Any

from tempestroid import (
    App,
    Column,
    Dropdown,
    Form,
    FormField,
    FormState,
    Input,
    SubmitEvent,
    Validator,
    Widget,
    build,
    introspect,
    parse_event,
)
from tempestroid.bridge import DeviceApp, EventMessage, LoopbackBridge, serialize_node


def _require_at() -> Validator:
    """Build an ``@``-presence validator (returns an error str or None)."""

    def rule(value: Any) -> str | None:  # noqa: ANN401 — opaque field value
        return None if "@" in str(value) else "E-mail inválido"

    return rule


def _required(value: Any) -> str | None:  # noqa: ANN401 — opaque field value
    """Reject an empty value."""
    return "Campo obrigatório" if not str(value).strip() else None


# --- Form.validate ----------------------------------------------------------


def test_validate_passes_when_every_field_valid():
    form = Form(
        fields=[
            FormField(name="email", validators=[_require_at()], child=Input()),
            FormField(name="name", validators=[_required], child=Input()),
        ]
    )
    state = form.validate({"email": "a@b.com", "name": "Ana"})
    assert isinstance(state, FormState)
    assert state.valid is True
    assert state.errors == {}


def test_validate_blocks_with_per_field_error():
    form = Form(
        fields=[
            FormField(name="email", validators=[_require_at()], child=Input()),
            FormField(name="name", validators=[_required], child=Input()),
        ]
    )
    state = form.validate({"email": "nope", "name": ""})
    assert state.valid is False
    assert state.errors == {
        "email": "E-mail inválido",
        "name": "Campo obrigatório",
    }


def test_validate_missing_value_treated_as_empty():
    form = Form(fields=[FormField(name="name", validators=[_required], child=Input())])
    state = form.validate({})  # no value supplied for "name"
    assert state.valid is False
    assert state.errors == {"name": "Campo obrigatório"}


def test_field_validate_returns_first_error():
    def passes(_v: Any) -> str | None:
        return None

    def second(_v: Any) -> str | None:
        return "second"

    def third(_v: Any) -> str | None:
        return "third"

    field = FormField(name="x", validators=[passes, second, third], child=Input())
    assert field.run_validators("anything") == "second"


# --- FormState JSON-serializability -----------------------------------------


def test_form_state_is_json_serializable_flat_dict():
    state = FormState(errors={"email": "bad"}, valid=False)
    dumped = state.model_dump()
    assert dumped == {"errors": {"email": "bad"}, "valid": False}
    # Round-trips through plain JSON without nested models.
    assert json.loads(json.dumps(dumped)) == dumped


def test_form_state_is_frozen():
    state = FormState()
    try:
        state.valid = False  # type: ignore[misc]
    except Exception:  # noqa: BLE001 — frozen model rejects mutation
        pass
    else:  # pragma: no cover
        raise AssertionError("FormState should be frozen")


# --- introspection ----------------------------------------------------------


def test_form_and_field_in_introspection():
    spec = introspect()
    assert "Form" in spec["widgets"]
    assert "FormField" in spec["widgets"]
    assert spec["widgets"]["Form"]["events"] == {"on_submit": "SubmitEvent"}
    assert spec["widgets"]["FormField"]["events"] == {"on_validate": "ValidationEvent"}


# --- submit event parsing ---------------------------------------------------


def test_submit_event_round_trip_via_parse_event():
    event = parse_event(SubmitEvent, {"values": {"email": "a@b", "name": "x"}})
    assert event.values == {"email": "a@b", "name": "x"}


# --- serialization: fields cross as children, validators are dropped --------


def test_serialize_form_fields_become_children_without_validators():
    form = Form(
        fields=[
            FormField(
                name="email",
                validators=[_require_at()],
                label="E-mail",
                child=Input(value="x"),
            )
        ],
        on_submit=lambda _e: None,
    )
    payload = serialize_node(build(form))
    assert payload["props"]["on_submit"]["event"] == "SubmitEvent"
    # The field crosses as a child node, never as a prop holding nested models.
    assert "fields" not in payload["props"]
    field_node = payload["children"][0]
    assert field_node["type"] == "FormField"
    assert field_node["props"]["label"] == "E-mail"
    assert "validators" not in field_node["props"]  # callables dropped
    # The field's input crosses as its own child.
    assert field_node["children"][0]["type"] == "Input"


# --- bridge round-trip: valid submit dispatches, invalid does not -----------


class _SubmitState:
    """State for the bridge round-trip test."""

    email: str = ""
    submitted: bool = False


def _run_submit(email: str) -> _SubmitState:
    """Mount a form via the loopback bridge, submit it, return the final state."""
    state = _SubmitState()

    def view(app: App[_SubmitState]) -> Widget:
        def on_submit(event: SubmitEvent) -> None:
            form = Form(
                fields=[
                    FormField(
                        name="email",
                        validators=[_require_at()],
                        child=Input(value=app.state.email),
                    )
                ]
            )
            result = form.validate(event.values)
            if result.valid:
                app.set_state(lambda s: setattr(s, "submitted", True))

        return Column(
            children=[
                Form(
                    fields=[
                        FormField(
                            name="email",
                            validators=[_require_at()],
                            child=Input(value=app.state.email, key="email"),
                            key="email-field",
                        )
                    ],
                    on_submit=on_submit,
                    key="form",
                )
            ]
        )

    async def run() -> None:
        bridge = LoopbackBridge()
        device = DeviceApp(state, view, bridge)
        await device.start()
        scene = device.app.current_tree
        assert scene is not None
        form_node = serialize_node(scene.root)["children"][0]
        token = form_node["props"]["on_submit"]["$handler"]
        await device.handle_event(
            EventMessage(
                token=token, payload={"values": {"email": email}}
            ).model_dump()
        )

    asyncio.run(run())
    return state


def test_bridge_valid_submit_dispatches():
    state = _run_submit("a@b.com")
    assert state.submitted is True


def test_bridge_invalid_submit_does_not_dispatch():
    state = _run_submit("nope")
    assert state.submitted is False


# --- a Form may hold non-FormField siblings via composition -----------------


def test_dropdown_inside_field_serializes():
    form = Form(
        fields=[
            FormField(
                name="country",
                child=Dropdown(options=["BR", "US"], on_select=lambda _e: None),
            )
        ]
    )
    payload = serialize_node(build(form))
    field = payload["children"][0]
    assert field["children"][0]["type"] == "Dropdown"
    assert field["children"][0]["props"]["options"] == ["BR", "US"]

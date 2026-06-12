"""Forms — gallery example exercising the E5 form aggregation and validation.

Showcases the validating form path and the new selection / segmented inputs:

* a ``Form`` of ``FormField``s with typed validators — an e-mail field
  (``lambda v: None if "@" in v else "E-mail inválido"``) and a required name;
  submit is **blocked** while any field is invalid and each failing field shows
  its error string inline;
* a ``Dropdown`` of countries (``SelectEvent``);
* a ``PinInput`` OTP (``TextChangeEvent`` per cell + ``SubmitEvent`` once full).

Validation runs entirely in Python: on submit the form's ``validate`` builds a
``FormState`` and each field's ``error`` is mirrored back into the tree, so both
renderers receive an already-validated tree (no validation logic on the device).

Runs in the Qt simulator::

    uv run python examples/forms/app.py
    uv run tempest dev examples/forms/app.py     # + hot restart on save

Exposes ``view(app) -> Widget`` and ``make_state() -> S`` for ``tempest dev``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempestroid import (
    App,
    Color,
    Column,
    Dropdown,
    Edge,
    FontWeight,
    Form,
    FormField,
    FormState,
    Input,
    PinInput,
    SelectEvent,
    Style,
    SubmitEvent,
    Text,
    TextChangeEvent,
    Widget,
)

#: The countries offered by the dropdown.
_COUNTRIES: list[str] = ["Brazil", "Portugal", "United States", "Japan"]


@dataclass
class FormsState:
    """The screen's mutable state.

    Attributes:
        email: The text typed into the e-mail field.
        name: The text typed into the name field.
        country: The selected country, or ``""`` when none is chosen.
        otp: The one-time-password digits entered so far.
        form_state: The latest validation result (errors + validity).
        submitted: Whether a valid submit has gone through.
    """

    email: str = ""
    name: str = ""
    country: str = ""
    otp: str = ""
    form_state: FormState = field(default_factory=FormState)
    submitted: bool = False


def make_state() -> FormsState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new, empty forms state.
    """
    return FormsState()


def _email_rule(value: object) -> str | None:
    """Validate that the value looks like an e-mail address.

    Args:
        value: The field's raw value.

    Returns:
        An error message, or ``None`` when valid.
    """
    return None if "@" in str(value) else "E-mail inválido"


def _required_rule(value: object) -> str | None:
    """Validate that the value is not empty.

    Args:
        value: The field's raw value.

    Returns:
        An error message, or ``None`` when valid.
    """
    return "Campo obrigatório" if not str(value).strip() else None


def view(app: App[FormsState]) -> Widget:
    """Build the forms UI for the current state.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget of the forms screen.
    """
    state = app.state

    def on_email(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "email", event.value))

    def on_name(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "name", event.value))

    def on_country(event: SelectEvent) -> None:
        app.set_state(lambda s: setattr(s, "country", event.value))

    def on_otp(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "otp", event.value))

    def _build_form() -> Form:
        # Build the validating form against the *current* state values, mirroring
        # each field's error from the latest FormState.
        return Form(
            fields=[
                FormField(
                    name="email",
                    label="E-mail",
                    validators=[_email_rule],
                    error=state.form_state.errors.get("email", ""),
                    child=Input(
                        value=state.email,
                        placeholder="you@example.com",
                        on_change=on_email,
                        key="email-input",
                    ),
                    key="email-field",
                ),
                FormField(
                    name="name",
                    label="Name",
                    validators=[_required_rule],
                    error=state.form_state.errors.get("name", ""),
                    child=Input(
                        value=state.name,
                        placeholder="Your name",
                        on_change=on_name,
                        key="name-input",
                    ),
                    key="name-field",
                ),
            ],
            on_submit=on_submit,
            key="signup-form",
        )

    def on_submit(event: SubmitEvent) -> None:
        # Validation runs purely in Python: the submitted values are validated and
        # the resulting FormState (errors + validity) is folded back into state.
        result = _build_form().validate({"email": state.email, "name": state.name})

        def apply(s: FormsState) -> None:
            s.form_state = result
            s.submitted = result.valid

        app.set_state(apply)

    summary = (
        "Submitted!"
        if state.submitted
        else "Fill the form and submit (invalid fields block it)."
    )

    return Column(
        style=Style(
            gap=14.0,
            padding=Edge.all(24.0),
            background=Color.from_hex("#0b0f14"),
        ),
        children=[
            Text(
                content="Create account",
                style=Style(
                    color=Color.from_hex("#ffffff"),
                    font_size=24.0,
                    font_weight=FontWeight.BOLD,
                ),
                key="title",
            ),
            _build_form(),
            Dropdown(
                options=_COUNTRIES,
                value=state.country or None,
                placeholder="Select a country…",
                on_select=on_country,
                key="country",
            ),
            PinInput(
                length=6,
                value=state.otp,
                on_change=on_otp,
                key="otp",
            ),
            Text(
                content=summary,
                style=Style(
                    color=Color.from_hex("#22c55e")
                    if state.submitted
                    else Color.from_hex("#9ca3af"),
                    font_size=14.0,
                ),
                key="summary",
            ),
        ],
    )


if __name__ == "__main__":
    from tempestroid.renderers.qt import run_qt

    raise SystemExit(
        run_qt(make_state(), view, title="tempestroid — forms", size=(400, 560))
    )

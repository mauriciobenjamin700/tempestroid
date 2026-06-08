"""Brazilian form components + media pickers — device-verification app.

Run it in the Qt simulator with the ``qt`` extra installed::

    uv run python examples/brforms/app.py

It exercises the composite form components (which lower to the value-input
primitives, so they render on both the Qt simulator and the Compose device):

* :class:`~tempestroid.EmailInput`, :class:`~tempestroid.PhoneInput`,
  :class:`~tempestroid.CPFInput`, :class:`~tempestroid.CNPJInput` and
  :class:`~tempestroid.PasswordInput`, each wired into a
  :class:`~tempestroid.Form` of :class:`~tempestroid.FormField`\\s with the
  matching validator from :mod:`tempestroid.validators`;
* :class:`~tempestroid.ImagePicker` for a photo.

Submitting validates every field in Python and only flips ``submitted`` when the
whole form is valid.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempestroid import (
    AlignItems,
    App,
    Button,
    Color,
    Column,
    CPFInput,
    Edge,
    EmailInput,
    Form,
    FormField,
    ImagePicker,
    PasswordInput,
    PhoneInput,
    ScrollView,
    Style,
    Text,
    Widget,
    validate_cpf,
    validate_email,
    validate_phone,
)


@dataclass
class State:
    """The form's mutable state.

    Attributes:
        email: The current e-mail value.
        phone: The current phone value (masked).
        cpf: The current CPF value (masked).
        password: The current password value.
        photo: The picked photo uri.
        errors: Per-field error messages from the last submit.
        submitted: Whether a valid submit has happened.
    """

    email: str = ""
    phone: str = ""
    cpf: str = ""
    password: str = ""
    photo: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    submitted: bool = False


def make_state() -> State:
    """Build a fresh initial state.

    Returns:
        A new empty form state.
    """
    return State()


def view(app: App[State]) -> Widget:
    """Build the Brazilian sign-up form.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget.
    """
    s = app.state

    def on_field(name: str) -> object:
        def handler(value: str) -> None:
            app.set_state(lambda st: setattr(st, name, value))

        return handler

    def on_photo(uri: str) -> None:
        app.set_state(lambda st: setattr(st, "photo", uri))

    def on_submit() -> None:
        form = Form(
            fields=[
                FormField(name="email", validators=[validate_email]),
                FormField(name="phone", validators=[validate_phone]),
                FormField(name="cpf", validators=[validate_cpf]),
            ]
        )
        result = form.validate(
            {"email": s.email, "phone": s.phone, "cpf": s.cpf}
        )

        def apply(st: State) -> None:
            st.errors = dict(result.errors)
            st.submitted = result.valid

        app.set_state(apply)

    return ScrollView(
        child=Column(
            style=Style(
                align=AlignItems.STRETCH,
                gap=12.0,
                padding=Edge.all(20.0),
                background=Color.from_hex("#0b0f14"),
            ),
            children=[
                Text(
                    content="Cadastro",
                    style=Style(color=Color.from_hex("#ffffff"), font_size=22.0),
                    key="title",
                ),
                ImagePicker(value=s.photo, label="Foto", on_pick=on_photo, key="photo"),
                FormField(
                    name="email",
                    error=s.errors.get("email", ""),
                    child=EmailInput(value=s.email, on_change=on_field("email")),
                    key="f-email",
                ),
                FormField(
                    name="phone",
                    error=s.errors.get("phone", ""),
                    child=PhoneInput(value=s.phone, on_change=on_field("phone")),
                    key="f-phone",
                ),
                FormField(
                    name="cpf",
                    error=s.errors.get("cpf", ""),
                    child=CPFInput(value=s.cpf, on_change=on_field("cpf")),
                    key="f-cpf",
                ),
                FormField(
                    name="password",
                    child=PasswordInput(
                        value=s.password, on_change=on_field("password")
                    ),
                    key="f-pwd",
                ),
                Button(label="Enviar", on_click=on_submit, key="submit"),
                Text(
                    content="Enviado!" if s.submitted else "Preencha e envie",
                    style=Style(
                        color=Color.from_hex("#22c55e" if s.submitted else "#9ca3af")
                    ),
                    key="status",
                ),
            ],
        ),
        key="scroll",
    )

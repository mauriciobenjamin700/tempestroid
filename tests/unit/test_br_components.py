"""Tests for the Brazilian form-input and media-picker components.

Each component is a :class:`~tempestroid.widgets.Component` that lowers to
primitives via ``render``/``build``: these tests assert the produced primitive
tree (input types, masks, keyboards, icons) and that wiring the child handler
fires the component's own callable with the unwrapped value/URI.
"""

from __future__ import annotations

from tempestroid import (
    AddressInput,
    CNPJInput,
    CPFInput,
    DocumentPicker,
    EmailInput,
    FileSelectEvent,
    ImagePicker,
    ImagePicture,
    Node,
    PasswordInput,
    PhoneInput,
    TextChangeEvent,
    build,
)


def _find(node: Node, node_type: str) -> Node:
    """Return the first descendant node of the given widget type.

    Args:
        node: The root node to search.
        node_type: The ``type`` tag to match.

    Returns:
        The first matching node (depth-first, root included).

    Raises:
        AssertionError: If no matching node exists.
    """
    stack: list[Node] = [node]
    while stack:
        current = stack.pop(0)
        if current.type == node_type:
            return current
        stack.extend(current.children)
    raise AssertionError(f"no {node_type} node found")


# --- BR form inputs ---------------------------------------------------------


def test_email_input_lowers_to_email_field() -> None:
    node = build(EmailInput(value="a@b.com", on_change=lambda _v: None))
    field = _find(node, "Input")
    assert field.props["keyboard"] == "email"
    assert field.props["leading_icon"] == "mail"
    assert field.props["pattern"]
    assert field.props["value"] == "a@b.com"


def test_email_input_handler_unwraps_value() -> None:
    seen: list[str] = []
    node = build(EmailInput(on_change=seen.append))
    field = _find(node, "Input")
    field.props["on_change"](TextChangeEvent(value="x@y.com"))
    assert seen == ["x@y.com"]


def test_password_input_is_secure_with_lock_icon() -> None:
    node = build(PasswordInput(on_change=lambda _v: None))
    field = _find(node, "Input")
    assert field.props["secure"] is True
    assert field.props["leading_icon"] == "lock"
    assert field.props["placeholder"] == "Senha"


def test_phone_input_uses_phone_mask_and_keyboard() -> None:
    seen: list[str] = []
    node = build(PhoneInput(on_change=seen.append))
    field = _find(node, "MaskedInput")
    assert field.props["mask"] == "(99) 99999-9999"
    assert field.props["keyboard"] == "phone"
    field.props["on_change"](TextChangeEvent(value="11987654321"))
    assert seen == ["11987654321"]


def test_cpf_input_uses_cpf_mask() -> None:
    node = build(CPFInput(on_change=lambda _v: None))
    field = _find(node, "MaskedInput")
    assert field.props["mask"] == "999.999.999-99"
    assert field.props["keyboard"] == "number"


def test_cnpj_input_uses_cnpj_mask() -> None:
    node = build(CNPJInput(on_change=lambda _v: None))
    field = _find(node, "MaskedInput")
    assert field.props["mask"] == "99.999.999/9999-99"
    assert field.props["keyboard"] == "number"


def test_labelled_field_shows_error_when_set() -> None:
    node = build(EmailInput(error="E-mail inválido", on_change=lambda _v: None))
    texts = [c.props.get("content") for c in node.children if c.type == "Text"]
    assert "E-mail inválido" in texts


def test_labelled_field_hides_error_when_empty() -> None:
    node = build(EmailInput(on_change=lambda _v: None))
    texts = [c.props.get("content") for c in node.children if c.type == "Text"]
    assert "" not in texts


def test_address_input_builds_all_fields() -> None:
    node = build(AddressInput(on_change=lambda _f, _v: None))
    cep = _find(node, "MaskedInput")
    assert cep.props["mask"] == "99999-999"
    inputs = sum(1 for c in node.children if c.type == "Input")
    assert inputs == 6  # street, number, complement, neighborhood, city, state


def test_address_input_handler_reports_field_name() -> None:
    seen: list[tuple[str, str]] = []

    def on_change(field: str, value: str) -> None:
        seen.append((field, value))

    node = build(AddressInput(on_change=on_change))
    # CEP (the MaskedInput) and the city Input both report their field name.
    cep = _find(node, "MaskedInput")
    cep.props["on_change"](TextChangeEvent(value="01001000"))
    city = next(
        c for c in node.children if c.type == "Input" and c.key == "address-city"
    )
    city.props["on_change"](TextChangeEvent(value="São Paulo"))
    assert ("cep", "01001000") in seen
    assert ("city", "São Paulo") in seen


# --- media pickers ----------------------------------------------------------


def test_image_picker_shows_preview_only_when_set() -> None:
    empty = build(ImagePicker(on_pick=lambda _u: None))
    assert all(c.type != "Image" for c in empty.children)
    filled = build(ImagePicker(value="content://x.jpg", on_pick=lambda _u: None))
    assert any(c.type == "Image" for c in filled.children)


def test_image_picker_handler_unwraps_uri() -> None:
    seen: list[str] = []
    node = build(ImagePicker(on_pick=seen.append))
    picker = _find(node, "FilePicker")
    picker.props["on_select"](FileSelectEvent(uri="content://pic.jpg"))
    assert seen == ["content://pic.jpg"]


def test_document_picker_lowers_to_file_picker() -> None:
    seen: list[str] = []
    node = build(DocumentPicker(label="Doc", on_pick=seen.append))
    picker = _find(node, "FilePicker")
    assert picker.props["label"] == "Choose document"
    picker.props["on_select"](FileSelectEvent(uri="content://doc.pdf"))
    assert seen == ["content://doc.pdf"]


def test_image_picture_placeholder_without_src() -> None:
    node = build(ImagePicture(on_pick=lambda _u: None))
    icon = _find(node, "Icon")
    assert icon.props["name"] == "user"


def test_image_picture_clips_image_when_src_set() -> None:
    node = build(ImagePicture(src="content://me.jpg", on_pick=lambda _u: None))
    clip = _find(node, "ClipPath")
    assert clip.props["shape"] == "circle"
    image = _find(node, "Image")
    assert image.props["src"] == "content://me.jpg"


def test_image_picture_handler_unwraps_uri() -> None:
    seen: list[str] = []
    node = build(ImagePicture(on_pick=seen.append))
    picker = _find(node, "FilePicker")
    picker.props["on_select"](FileSelectEvent(uri="content://avatar.jpg"))
    assert seen == ["content://avatar.jpg"]

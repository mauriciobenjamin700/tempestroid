"""Render a specimen of every tempestroid widget/component to a PNG.

This tool drives the Qt renderer in offscreen mode to grab a screenshot of a
representative instance ("specimen") of every exported ``Widget``/``Component``
subclass, writing each to ``docs/assets/components/<snake_case_name>.png``. The
images are embedded next to the code in the docs tutorial pages so users see
what each widget looks like.

Run it with::

    QT_QPA_PLATFORM=offscreen uv run python tools/shoot_docs.py

It builds and mounts each specimen, reports any that fail, and exits non-zero if
any specimen could not be rendered.
"""

from __future__ import annotations

import inspect
import os
import re
from pathlib import Path

# Qt must run headless; set the platform before importing PySide6.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402
from tempest_core.core.reconciler import build  # noqa: E402

import tempestroid as T  # noqa: E402
from tempestroid import (  # noqa: E402
    Accordion,
    AddressInput,
    Animated,
    AnimatedList,
    AppBar,
    AspectRatio,
    Autocomplete,
    Avatar,
    BackdropFilter,
    Badge,
    Banner,
    Blur,
    BottomSheet,
    Breadcrumb,
    Burger,
    Button,
    Calendar,
    CameraPreview,
    Canvas,
    Card,
    Checkbox,
    Chip,
    ClipPath,
    Clock,
    CNPJInput,
    CollapsingAppBar,
    Color,
    Column,
    Container,
    CPFInput,
    DataTable,
    DatePicker,
    Dialog,
    Dismissible,
    DocumentPicker,
    DoubleTapHandler,
    Draggable,
    DragTarget,
    Drawer,
    Dropdown,
    Edge,
    EmailInput,
    EmptyState,
    FilePicker,
    Footer,
    Form,
    FormField,
    GestureDetector,
    Grid,
    Header,
    Hero,
    Icon,
    IconButton,
    Image,
    ImagePicker,
    ImagePicture,
    Input,
    InteractiveViewer,
    KeyboardAvoidingView,
    LazyColumn,
    LazyGrid,
    LazyRow,
    LineTo,
    ListTile,
    MaskedInput,
    Menu,
    MenuItem,
    MoveTo,
    NavBar,
    Navigator,
    PageView,
    PanHandler,
    PasswordInput,
    PhoneInput,
    PinInput,
    Popover,
    ProgressBar,
    QrScanner,
    RadioGroup,
    RangeSlider,
    Rating,
    RefreshControl,
    ReorderableList,
    RouteDrawer,
    Row,
    SafeArea,
    Scaffold,
    ScaleHandler,
    ScrollView,
    SearchBar,
    SectionHeader,
    SectionList,
    SegmentedControl,
    Shimmer,
    Sidebar,
    Skeleton,
    Slider,
    Spinner,
    Stack,
    Stepper,
    StrokeCmd,
    Style,
    Svg,
    Switch,
    TabBar,
    Table,
    TableCell,
    TableRow,
    TabView,
    Text,
    TextArea,
    TimePicker,
    Toast,
    Tooltip,
    VideoPlayer,
    WebView,
    Widget,
    Wrap,
)
from tempestroid.renderers.qt.renderer import QtRenderer  # noqa: E402

# Repo root → docs/assets/components.
REPO_ROOT: Path = Path(__file__).resolve().parent.parent
ASSETS_DIR: Path = REPO_ROOT / "docs" / "assets" / "components"

# A readable dark surface so light glyphs are visible on the docs page.
FRAME_STYLE: Style = Style(
    background=Color.from_hex("#11161c"),
    padding=Edge.all(16.0),
)


def _noop(*_args: object, **_kwargs: object) -> None:
    """Discard any positional/keyword arguments (dummy event handler).

    Args:
        *_args: Ignored positional arguments.
        **_kwargs: Ignored keyword arguments.
    """
    return None


def _demo_item(index: int) -> Widget:
    """Build a single demo row for a virtualized list specimen.

    Args:
        index: The item index supplied by the list's window.

    Returns:
        A ``Text`` widget labelled with the index.
    """
    return Text(content=f"Item {index}", key=f"row-{index}")


def _snake_case(name: str) -> str:
    """Convert a ``PascalCase`` class name to ``snake_case``.

    Acronym runs (e.g. ``CPF``, ``CNPJ``) collapse into a single token so
    ``CPFInput`` becomes ``cpf_input`` and ``DataTable`` becomes ``data_table``.

    Args:
        name: The class name to convert.

    Returns:
        The ``snake_case`` form of ``name``.
    """
    step = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    step = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", step)
    return step.lower()


# Classes that are non-visual / abstract / not sensibly standalone — skipped on
# purpose. Each maps to a short reason for the log.
SKIP: dict[str, str] = {
    "Widget": "abstract base class",
    "Component": "abstract base class",
}


def _build_specimens() -> dict[str, Widget]:
    """Build one representative specimen per exported Widget/Component.

    Returns:
        A mapping of class name to a ready-to-render specimen instance. Every
        specimen is wrapped where needed so ``build()`` + ``mount`` succeed.
    """
    specimens: dict[str, Widget] = {
        # --- basics ---------------------------------------------------------
        "Text": Text(content="Olá, mundo", key="t"),
        "Button": Button(label="Entrar", on_click=_noop, key="b"),
        "ProgressBar": ProgressBar(value=0.6, key="pb"),
        "Spinner": Spinner(key="sp"),
        # --- layout ---------------------------------------------------------
        "Column": Column(
            children=[
                Text(content="Linha 1", key="a"),
                Text(content="Linha 2", key="b"),
            ],
            key="col",
        ),
        "Row": Row(
            children=[
                Text(content="Esq.", key="a"),
                Text(content="Dir.", key="b"),
            ],
            key="row",
        ),
        "Container": Container(
            child=Text(content="Conteúdo", key="t"),
            style=Style(
                background=Color.from_hex("#2563eb"),
                padding=Edge.all(12.0),
            ),
            key="ct",
        ),
        "ScrollView": ScrollView(
            children=[Text(content=f"Item {i}", key=f"i{i}") for i in range(4)],
            key="sv",
        ),
        "SafeArea": SafeArea(
            child=Text(content="Dentro da área segura", key="t"),
            key="sa",
        ),
        "Stack": Stack(
            children=[
                Container(
                    style=Style(background=Color.from_hex("#1e293b")),
                    key="bg",
                ),
                Text(content="Sobreposto", key="t"),
            ],
            key="st",
        ),
        "Wrap": Wrap(
            children=[Chip(label=f"tag {i}", key=f"c{i}") for i in range(4)],
            key="wr",
        ),
        "PageView": PageView(
            children=[
                Text(content="Página 1", key="p1"),
                Text(content="Página 2", key="p2"),
            ],
            page=0,
            key="pv",
        ),
        "AspectRatio": AspectRatio(
            ratio=16 / 9,
            child=Container(
                style=Style(background=Color.from_hex("#0ea5e9")),
                key="c",
            ),
            key="ar",
        ),
        "KeyboardAvoidingView": KeyboardAvoidingView(
            children=[Input(value="Texto", placeholder="Digite…", key="in")],
            key="kav",
        ),
        # --- animation ------------------------------------------------------
        "Animated": Animated(
            child=Text(content="Animado", key="t"),
            key="an",
        ),
        "AnimatedList": AnimatedList(
            children=[Text(content=f"Linha {i}", key=f"l{i}") for i in range(3)],
            key="al",
        ),
        "Hero": Hero(
            hero_tag="photo",
            child=Avatar(initials="MS", key="av"),
            key="hero",
        ),
        "Shimmer": Shimmer(
            child=Container(
                style=Style(background=Color.from_hex("#334155")),
                key="c",
            ),
            key="shimmer",
        ),
        "Skeleton": Skeleton(key="sk"),
        # --- gestures -------------------------------------------------------
        "GestureDetector": GestureDetector(
            child=Text(content="Toque aqui", key="t"),
            on_tap=_noop,
            key="gd",
        ),
        "PanHandler": PanHandler(
            child=Text(content="Arraste", key="t"),
            on_pan=_noop,
            key="ph",
        ),
        "ScaleHandler": ScaleHandler(
            child=Text(content="Pince", key="t"),
            on_scale=_noop,
            key="sh",
        ),
        "DoubleTapHandler": DoubleTapHandler(
            child=Text(content="Toque duplo", key="t"),
            on_double_tap=_noop,
            key="dt",
        ),
        "Draggable": Draggable(
            child=Text(content="Pegue-me", key="t"),
            key="dg",
        ),
        "DragTarget": DragTarget(
            child=Text(content="Solte aqui", key="t"),
            key="dgt",
        ),
        "Dismissible": Dismissible(
            child=ListTile(title="Deslize p/ remover", key="lt"),
            key="dm",
        ),
        "ReorderableList": ReorderableList(
            children=[ListTile(title=f"Linha {i}", key=f"r{i}") for i in range(3)],
            key="ro",
        ),
        "InteractiveViewer": InteractiveViewer(
            child=Text(content="Zoom & pan", key="t"),
            key="iv",
        ),
        # --- navigation -----------------------------------------------------
        "Navigator": Navigator(
            child=Text(content="Tela atual", key="t"),
            key="nv",
        ),
        "TabView": TabView(
            tabs=["Início", "Perfil"],
            active=0,
            child=Text(content="Conteúdo da aba", key="t"),
            key="tv",
        ),
        "TabBar": TabBar(tabs=["Início", "Perfil", "Ajustes"], active=0, key="tb"),
        "RouteDrawer": RouteDrawer(
            child=Text(content="Conteúdo", key="t"),
            drawer=Column(
                children=[Text(content="Menu", key="m")],
                key="dr",
            ),
            key="rd",
        ),
        # --- inputs ---------------------------------------------------------
        "Input": Input(value="Maria", placeholder="Nome", on_change=_noop, key="in"),
        "TextArea": TextArea(
            value="Linha 1\nLinha 2",
            placeholder="Mensagem",
            on_change=_noop,
            key="ta",
        ),
        "Checkbox": Checkbox(checked=True, label="Aceito", on_change=_noop, key="cb"),
        "Switch": Switch(checked=True, on_change=_noop, key="sw"),
        "Slider": Slider(value=0.5, on_change=_noop, key="sl"),
        "RangeSlider": RangeSlider(low=0.2, high=0.7, on_change=_noop, key="rs"),
        "Dropdown": Dropdown(
            options=["Opção A", "Opção B"],
            value="Opção A",
            on_select=_noop,
            key="dd",
        ),
        "DatePicker": DatePicker(value="2026-06-08", on_change=_noop, key="dp"),
        "TimePicker": TimePicker(value="14:30", on_change=_noop, key="tp"),
        "FilePicker": FilePicker(label="Escolher arquivo", on_select=_noop, key="fp"),
        "PinInput": PinInput(length=4, value="12", on_change=_noop, key="pin"),
        "MaskedInput": MaskedInput(
            value="123",
            mask="999.999.999-99",
            on_change=_noop,
            key="mi",
        ),
        "Autocomplete": Autocomplete(
            value="Ma",
            options=["Maria", "Marina", "Mário"],
            on_change=_noop,
            key="ac",
        ),
        "Form": Form(
            fields=[
                FormField(
                    name="email",
                    label="E-mail",
                    child=Input(value="", placeholder="voce@exemplo.com", key="e"),
                    key="ff-e",
                ),
            ],
            key="form",
        ),
        "FormField": FormField(
            name="email",
            label="E-mail",
            error="E-mail inválido",
            child=Input(value="abc", placeholder="voce@exemplo.com", key="e"),
            key="ff",
        ),
        # --- media ----------------------------------------------------------
        "Image": Image(src="https://example.com/foto.png", alt="Foto", key="img"),
        "Icon": Icon(name="star", size=32.0, key="ic"),
        "IconButton": IconButton(
            icon="settings", label="Settings", on_click=_noop, key="ib"
        ),
        "Svg": Svg(src="https://example.com/logo.svg", key="svg"),
        "Canvas": Canvas(
            commands=[
                MoveTo(x=8.0, y=8.0),
                LineTo(x=120.0, y=80.0),
                StrokeCmd(color=[0.13, 0.83, 0.93, 1.0], width=3.0),
            ],
            width=160.0,
            height=100.0,
            key="cv",
        ),
        "VideoPlayer": VideoPlayer(
            src="https://example.com/video.mp4",
            controls=True,
            key="vp",
        ),
        "WebView": WebView(url="https://example.com", key="wv"),
        "Blur": Blur(
            radius=8.0,
            child=Text(content="Desfocado", key="t"),
            key="bl",
        ),
        "BackdropFilter": BackdropFilter(
            radius=8.0,
            child=Text(content="Fundo desfocado", key="t"),
            key="bf",
        ),
        "ClipPath": ClipPath(
            radius=16.0,
            child=Container(
                style=Style(background=Color.from_hex("#a855f7")),
                key="c",
            ),
            key="cp",
        ),
        "CameraPreview": CameraPreview(key="cam"),
        "QrScanner": QrScanner(on_scan=_noop, key="qr"),
        "MapView": T.MapView(latitude=-23.55, longitude=-46.63, key="mv"),
        # --- lists ----------------------------------------------------------
        "LazyColumn": LazyColumn(
            item_count=1000,
            item_builder=_demo_item,
            window=(0, 6),
            key="lc",
        ),
        "LazyRow": LazyRow(
            item_count=1000,
            item_builder=_demo_item,
            window=(0, 4),
            key="lr",
        ),
        "LazyGrid": LazyGrid(
            item_count=1000,
            item_builder=_demo_item,
            columns=3,
            window=(0, 9),
            key="lg",
        ),
        "SectionList": SectionList(
            sections=[
                SectionHeader(
                    title="A",
                    item_count=3,
                    item_builder=_demo_item,
                    header_builder=lambda: Text(content="Seção A", key="h"),
                    window=(0, 3),
                ),
            ],
            key="sl-list",
        ),
        "RefreshControl": RefreshControl(refreshing=True, on_refresh=_noop, key="rc"),
        # --- overlays -------------------------------------------------------
        "Dialog": Dialog(
            title="Confirmar",
            children=[
                Text(content="Deseja continuar?", key="t"),
                Button(label="OK", on_click=_noop, key="ok"),
            ],
            key="dlg",
        ),
        "BottomSheet": BottomSheet(
            children=[
                Text(content="Compartilhar via", key="t"),
                Button(label="WhatsApp", on_click=_noop, key="wa"),
            ],
            key="bs",
        ),
        "Menu": Menu(
            items=[
                MenuItem(label="Editar", value="edit"),
                MenuItem(label="Excluir", value="delete"),
            ],
            on_select=_noop,
            key="menu",
        ),
        "Popover": Popover(
            child=Text(content="Conteúdo do popover", key="t"),
            key="pop",
        ),
        "Toast": Toast(message="Salvo com sucesso", key="toast"),
        "Tooltip": Tooltip(
            message="Mais informações",
            child=Icon(name="info", key="i"),
            key="tt",
        ),
        "ActionSheet": T.ActionSheet(
            title="Opções",
            items=[
                MenuItem(label="Compartilhar", value="share"),
                MenuItem(label="Apagar", value="delete"),
            ],
            on_select=_noop,
            key="as",
        ),
        # --- components -----------------------------------------------------
        "AppBar": AppBar(title="Minha App", key="ab"),
        "Header": Header(title="Configurações", subtitle="Conta", key="hd"),
        "Footer": Footer(
            children=[Text(content="© 2026 Tempestroid", key="t")],
            key="ft",
        ),
        "CollapsingAppBar": CollapsingAppBar(title="Galeria", key="cab"),
        "NavBar": NavBar(
            items=["Início", "Buscar", "Perfil"],
            active=0,
            on_select=_noop,
            key="navbar",
        ),
        "Breadcrumb": Breadcrumb(
            items=["Início", "Loja", "Camisetas"],
            on_select=_noop,
            key="bc",
        ),
        "Burger": Burger(on_click=_noop, key="bg-burger"),
        "Drawer": Drawer(
            open=True,
            children=[
                ListTile(title="Início", key="d1"),
                ListTile(title="Perfil", key="d2"),
            ],
            key="drawer",
        ),
        "Scaffold": Scaffold(
            app_bar=AppBar(title="Painel", key="ab"),
            body=Text(content="Corpo da tela", key="body"),
            key="scaffold",
        ),
        "Sidebar": Sidebar(
            children=[
                ListTile(title="Dashboard", key="s1"),
                ListTile(title="Relatórios", key="s2"),
            ],
            key="sidebar",
        ),
        "Grid": Grid(
            children=[Chip(label=f"item {i}", key=f"g{i}") for i in range(6)],
            columns=3,
            key="grid",
        ),
        "SegmentedControl": SegmentedControl(
            options=["Dia", "Semana", "Mês"],
            selected=0,
            on_select=_noop,
            key="seg",
        ),
        "RadioGroup": RadioGroup(
            options=["Cartão", "Pix", "Boleto"],
            selected=1,
            on_select=_noop,
            key="radio",
        ),
        "Calendar": Calendar(
            month="2026-06",
            selected="2026-06-08",
            on_select=_noop,
            key="cal",
        ),
        "Clock": Clock(time="14:30", label="Agora", key="clock"),
        "Card": Card(
            children=[
                Text(content="Bem-vindo!", key="t"),
                Button(label="Entrar", on_click=_noop, key="btn"),
            ],
            key="card",
        ),
        "ListTile": ListTile(
            title="Maria Silva",
            subtitle="maria@example.com",
            leading=Avatar(initials="MS", key="av"),
            key="tile",
        ),
        "Avatar": Avatar(initials="MS", size=48.0, key="avatar"),
        "Divider": T.Divider(key="div"),
        "Chip": Chip(label="Tecnologia", selected=True, key="chip"),
        "Rating": Rating(value=4, max_stars=5, key="rating"),
        "Stepper": Stepper(value=2, on_change=_noop, key="stepper"),
        "SearchBar": SearchBar(
            value="café",
            placeholder="Buscar…",
            on_change=_noop,
            key="search",
        ),
        "Accordion": Accordion(
            title="Detalhes do pedido",
            open=True,
            children=[Text(content="Entrega em 3 dias", key="t")],
            on_toggle=_noop,
            key="acc",
        ),
        "Banner": Banner(
            message="Atualização disponível",
            tone="info",
            key="banner",
        ),
        "EmptyState": EmptyState(
            title="Nada por aqui",
            subtitle="Adicione seu primeiro item",
            glyph="📭",
            key="empty",
        ),
        "Badge": Badge(label="Novo", tone="success", key="badge"),
        "Table": Table(
            headers=["Nome", "Idade"],
            rows=[
                TableRow(cells=[TableCell(content="Ana"), TableCell(content="29")]),
                TableRow(cells=[TableCell(content="Bia"), TableCell(content="34")]),
            ],
            key="table",
        ),
        "DataTable": DataTable(
            columns=["Produto", "Preço"],
            rows=[["Café", "R$ 12"], ["Chá", "R$ 9"]],
            sortable=True,
            key="datatable",
        ),
        # --- BR components --------------------------------------------------
        "EmailInput": EmailInput(
            value="maria@exemplo.com",
            label="E-mail",
            on_change=_noop,
            key="email",
        ),
        "PasswordInput": PasswordInput(
            value="senha123",
            label="Senha",
            on_change=_noop,
            key="pw",
        ),
        "PhoneInput": PhoneInput(
            value="(11) 91234-5678",
            label="Telefone",
            on_change=_noop,
            key="phone",
        ),
        "CPFInput": CPFInput(
            value="123.456.789-09",
            label="CPF",
            on_change=_noop,
            key="cpf",
        ),
        "CNPJInput": CNPJInput(
            value="12.345.678/0001-95",
            label="CNPJ",
            on_change=_noop,
            key="cnpj",
        ),
        "AddressInput": AddressInput(
            cep="01001-000",
            street="Praça da Sé",
            number="100",
            city="São Paulo",
            state="SP",
            label="Endereço",
            on_change=_noop,
            key="addr",
        ),
        "ImagePicker": ImagePicker(label="Selecionar imagem", on_pick=_noop, key="ip"),
        "DocumentPicker": DocumentPicker(
            label="Selecionar documento",
            on_pick=_noop,
            key="docp",
        ),
        "ImagePicture": ImagePicture(src="", size=96.0, on_pick=_noop, key="ipic"),
    }
    return specimens


def _all_target_classes() -> list[str]:
    """Collect every exported Widget/Component subclass name.

    Returns:
        Sorted list of class names that are concrete ``Widget``/``Component``
        subclasses (excluding the abstract bases).
    """
    names: list[str] = []
    for name in T.__all__:
        obj = getattr(T, name, None)
        if (
            inspect.isclass(obj)
            and issubclass(obj, Widget)
            and name not in ("Widget", "Component")
        ):
            names.append(name)
    return sorted(names)


def _shoot(name: str, specimen: Widget) -> tuple[bool, str]:
    """Render one specimen to a PNG file.

    Args:
        name: The class name (used to derive the output filename).
        specimen: The widget instance to render.

    Returns:
        A ``(ok, detail)`` tuple — ``ok`` is ``True`` on success, ``detail`` is
        the output path on success or the error message on failure.
    """
    out_path = ASSETS_DIR / f"{_snake_case(name)}.png"
    try:
        renderer = QtRenderer()
        framed = Container(child=specimen, style=FRAME_STYLE, key="frame")
        renderer.mount(build(framed))
        host = renderer.host
        host.adjustSize()
        width = max(320, min(host.sizeHint().width(), 640))
        height = max(80, min(host.sizeHint().height(), 640))
        host.resize(width, height)
        host.grab().save(str(out_path))
    except Exception as exc:  # noqa: BLE001 — report every failure, keep going.
        return False, f"{type(exc).__name__}: {exc}"
    if not out_path.exists() or out_path.stat().st_size == 0:
        return False, "no PNG written or zero bytes"
    return True, str(out_path)


def main() -> int:
    """Render every specimen and report results.

    Returns:
        ``0`` if every non-skipped specimen rendered, ``1`` otherwise.
    """
    _app = QApplication.instance() or QApplication([])
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    specimens = _build_specimens()
    targets = _all_target_classes()

    missing = [n for n in targets if n not in specimens and n not in SKIP]
    if missing:
        print(
            f"WARNING: {len(missing)} exported class(es) have no specimen and "
            f"are not skipped: {', '.join(missing)}"
        )

    rendered: list[str] = []
    failed: list[tuple[str, str]] = []
    for name in sorted(specimens):
        ok, detail = _shoot(name, specimens[name])
        if ok:
            rendered.append(name)
        else:
            failed.append((name, detail))
            print(f"FAIL {name}: {detail}")

    print()
    print(f"Rendered {len(rendered)} PNG(s) to {ASSETS_DIR}")
    if SKIP:
        print(
            f"Skipped {len(SKIP)}: "
            + ", ".join(f"{n} ({why})" for n, why in SKIP.items())
        )
    if failed:
        print(f"FAILED {len(failed)}: " + ", ".join(n for n, _ in failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

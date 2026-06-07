# Overlays

Overlays são widgets que flutuam em uma **camada z-ordenada acima da árvore
principal**. Eles não são filhos diretos do `view` — vivem numa camada separada
que o framework mescla à cena antes de cada renderização. Você os abre por meio
dos métodos imperativos de `App` (`show_dialog`, `show_sheet`, `show_menu`,
`toast`) e os fecha chamando `dismiss` com o id retornado, ou deixa o usuário
dispensar tocando na barreira (scrim).

!!! info "Dois renderizadores, mesmos payloads"
    Qt usa `QDialog` / `QMenu` / overlays flutuantes; Compose usa
    `AlertDialog` / `ModalBottomSheet` / `DropdownMenu` do Material3.
    Os payloads dos eventos (`DismissEvent`, `MenuSelectEvent`) são idênticos
    nos dois renderizadores.

---

## Dialog

Um diálogo modal flutuado acima da tela, com título opcional e conteúdo
arbitrário.

```python
from dataclasses import dataclass
from tempestroid import Button, Column, Dialog, Text
from tempestroid.widgets.events import DismissEvent


@dataclass
class State:
    open: bool = False


def view(app):
    state = app.state

    def open_dialog():
        dialog_id = app.show_dialog(
            Dialog(
                title="Confirmar",
                children=[
                    Text(content="Deseja continuar?", key="msg"),
                    Button(
                        label="Fechar",
                        on_click=lambda: app.dismiss(dialog_id),
                        key="close",
                    ),
                ],
                on_dismiss=on_dismiss,
            )
        )

    def on_dismiss(event: DismissEvent) -> None:
        app.set_state(lambda s: setattr(s, "open", False))

    return Column(
        children=[
            Button(label="Abrir diálogo", on_click=open_dialog, key="btn"),
        ]
    )


def make_state() -> State:
    return State()
```

!!! warning "Barreira (scrim)"
    `app.show_dialog(widget, barrier=True)` (padrão) coloca um scrim
    semitransparente atrás do diálogo. Tocar no scrim dispensa o overlay
    e aciona `on_dismiss`. Passe `barrier=False` para desabilitar.

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `title` | `str \| None` | `None` | Título exibido no cabeçalho do diálogo. |
| `children` | `list[Widget]` | `[]` | Conteúdo do corpo do diálogo. |
| `on_dismiss` → `DismissEvent` | handler | `None` | Chamado quando o diálogo é dispensado (pelo usuário ou por `dismiss`). |

---

## BottomSheet

Uma folha que desliza a partir da borda inferior da tela.

```python
from dataclasses import dataclass
from tempestroid import BottomSheet, Button, Column, Text
from tempestroid.widgets.events import DismissEvent


@dataclass
class State:
    pass


def view(app):
    def open_sheet():
        sheet_id = app.show_sheet(
            BottomSheet(
                children=[
                    Text(content="Opções rápidas", key="title"),
                    Button(
                        label="Cancelar",
                        on_click=lambda: app.dismiss(sheet_id),
                        key="cancel",
                    ),
                ],
                on_dismiss=on_dismiss,
            )
        )

    def on_dismiss(event: DismissEvent) -> None:
        pass

    return Column(
        children=[
            Button(label="Abrir sheet", on_click=open_sheet, key="btn"),
        ]
    )


def make_state() -> State:
    return State()
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `children` | `list[Widget]` | `[]` | Conteúdo exibido dentro da folha. |
| `on_dismiss` → `DismissEvent` | handler | `None` | Chamado quando a folha é dispensada. |

---

## Menu

Uma lista de itens selecionáveis ancorada a um widget da árvore.

```python
from dataclasses import dataclass
from tempestroid import Button, Column, Menu, MenuItem
from tempestroid.widgets.events import MenuSelectEvent


@dataclass
class State:
    chosen: str = ""


def view(app):
    state = app.state

    def open_menu():
        app.show_menu(
            Menu(
                items=[
                    MenuItem(label="Editar", value="edit"),
                    MenuItem(label="Excluir", value="delete"),
                ],
                on_select=on_select,
            ),
            anchor="menu-btn",
        )

    def on_select(event: MenuSelectEvent) -> None:
        app.set_state(lambda s: setattr(s, "chosen", event.value))

    return Column(
        children=[
            Button(
                label="Menu",
                on_click=open_menu,
                key="menu-btn",
            ),
        ]
    )


def make_state() -> State:
    return State()
```

!!! tip "Âncora"
    Passe o `key` do widget de referência em `anchor` para que o
    renderizador posicione o menu próximo a ele. O parâmetro `barrier`
    de `show_menu` é `False` por padrão (menus geralmente não bloqueiam a
    tela inteira).

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `items` | `list[MenuItem]` | `[]` | Itens do menu. Cada `MenuItem` tem `label` e `value`. |
| `anchor` | `str \| None` | `None` | `key` do widget ao qual o menu é ancorado. |
| `on_select` → `MenuSelectEvent` | handler | `None` | Chamado com o item selecionado (`event.value`, `event.index`). |

---

## Popover

Um painel flutuante ancorado próximo a um widget, dispensável tocando fora.

```python
from dataclasses import dataclass
from tempestroid import Button, Column, Popover, Text
from tempestroid.widgets.events import DismissEvent


@dataclass
class State:
    pass


def view(app):
    def open_popover():
        pop_id = app.show_menu(
            Popover(
                child=Text(content="Dica: use ⌘K para buscar.", key="tip"),
                anchor="info-btn",
                on_dismiss=lambda e: None,
            ),
            anchor="info-btn",
        )

    return Column(
        children=[
            Button(label="?", on_click=open_popover, key="info-btn"),
        ]
    )


def make_state() -> State:
    return State()
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `child` | `Widget \| None` | `None` | Conteúdo do painel flutuante. |
| `anchor` | `str \| None` | `None` | `key` do widget de referência para posicionamento. |
| `on_dismiss` → `DismissEvent` | handler | `None` | Chamado quando o popover é dispensado. |

---

## Toast

Uma mensagem transitória que aparece brevemente e se auto-dispensa.

```python
from dataclasses import dataclass
from tempestroid import Button, Column, Toast


@dataclass
class State:
    pass


def view(app):
    def show_toast():
        app.toast(
            Toast(message="Salvo com sucesso!", duration_s=3.0),
        )

    return Column(
        children=[
            Button(label="Salvar", on_click=show_toast, key="save"),
        ]
    )


def make_state() -> State:
    return State()
```

!!! info "Auto-dispensa"
    `app.toast(widget)` agenda `dismiss` no loop de eventos após
    `duration_s` segundos (padrão `2.5`). O id retornado permite
    dispensar o toast antes do prazo via `app.dismiss(toast_id)`.
    Toasts não têm barreira — eles não bloqueiam interação com o fundo.

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `message` | `str` | obrigatório | Texto da mensagem exibida. |
| `duration_s` | `float` | `2.5` | Duração em segundos antes da auto-dispensa. |

---

## Tooltip

Um rótulo de dica pequeno exibido ao lado de um filho ancorado.

```python
from dataclasses import dataclass
from tempestroid import Button, Column, Icon, Tooltip


@dataclass
class State:
    pass


def view(app):
    def open_tooltip():
        app.show_menu(
            Tooltip(
                message="Clique para confirmar",
                child=Icon(name="info", key="icon"),
            ),
        )

    return Column(
        children=[
            Button(label="Info", on_click=open_tooltip, key="btn"),
        ]
    )


def make_state() -> State:
    return State()
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `message` | `str` | obrigatório | Texto da dica exibida. |
| `child` | `Widget \| None` | `None` | Widget ao lado do qual a dica é ancorada. |

---

## ActionSheet

Uma lista de ações ancorada na parte inferior da tela, com título opcional.

```python
from dataclasses import dataclass
from tempestroid import ActionSheet, Button, Column, MenuItem
from tempestroid.widgets.events import MenuSelectEvent


@dataclass
class State:
    action: str = ""


def view(app):
    state = app.state

    def open_actions():
        sheet_id = app.show_sheet(
            ActionSheet(
                title="O que deseja fazer?",
                items=[
                    MenuItem(label="Compartilhar", value="share"),
                    MenuItem(label="Arquivar", value="archive"),
                    MenuItem(label="Excluir", value="delete"),
                ],
                on_select=on_select,
            )
        )

    def on_select(event: MenuSelectEvent) -> None:
        app.set_state(lambda s: setattr(s, "action", event.value))

    return Column(
        children=[
            Button(label="Ações", on_click=open_actions, key="btn"),
        ]
    )


def make_state() -> State:
    return State()
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `title` | `str \| None` | `None` | Título opcional exibido acima dos itens. |
| `items` | `list[MenuItem]` | `[]` | Ações disponíveis. Cada `MenuItem` tem `label` e `value`. |
| `on_select` → `MenuSelectEvent` | handler | `None` | Chamado com a ação escolhida (`event.value`, `event.index`). |

---

## Recapitulando

- Overlays vivem em uma **camada z-ordenada separada** — não são filhos do `view`.
- Abra com `app.show_dialog` / `app.show_sheet` / `app.show_menu` / `app.toast`;
  feche com `app.dismiss(overlay_id)`.
- `barrier=True` (padrão em diálogos e sheets) exibe um scrim semitransparente;
  tocar nele dispensa o overlay e aciona `on_dismiss`.
- Toasts se auto-dispensam após `duration_s` segundos — sem barreira, sem bloquear
  a tela.
- Os payloads (`DismissEvent`, `MenuSelectEvent`) são idênticos no Qt e no
  Compose.

## Próximos passos

➡️ Veja como estilizar overlays com **[Estilos](../estilos.md)**, entenda os
eventos tipados em **[Eventos](../eventos.md)**, ou explore apps completos na
**[Galeria de exemplos](../exemplos.md)**.

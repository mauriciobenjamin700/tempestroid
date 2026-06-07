# Texto, ação e indicadores

Os widgets desta família são os blocos mais usados em qualquer tela: um rótulo
de texto estático, um botão tocável e dois indicadores de progresso —
`ProgressBar` para mostrar avanço determinado ou indeterminado, e `Spinner`
para sinalizar que algo está carregando em segundo plano. Combinados com os
widgets de layout, esses quatro elementos cobrem a grande maioria das telas de
um app típico.

Todos os widgets desta família são suportados pelos **dois renderizadores** —
simulador Qt (desktop) e Compose no dispositivo Android.

---

## Text

Exibe uma sequência de caracteres sem interação.

```python
from tempestroid import Column, Style, Text

Column(
    style=Style(padding=16.0, gap=8.0),
    children=[
        Text(content="Bem-vindo ao tempestroid!", key="title"),
        Text(content="Construa apps Android em Python tipado.", key="sub"),
    ],
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `content` | `str` | *(obrigatório)* | Texto a ser exibido. |

!!! tip "Estile com `Style`"
    `Text` herda `style` de `Widget`. Use `Style(font_size=20.0, color="#333333")`
    para tamanho e cor, `Style(font_weight="bold")` para negrito, etc.

---

## Button

Um botão tocável com rótulo textual. Quando tocado dispara um `TapEvent` para
o handler `on_click`.

```python
from tempestroid import Button, Column, Style, TapEvent, Text
from dataclasses import dataclass

@dataclass
class State:
    count: int = 0

def make_state() -> State:
    return State()

async def on_increment(e: TapEvent) -> None:
    app.set_state(lambda s: setattr(s, "count", s.count + 1))

def view(app) -> Column:
    return Column(
        style=Style(padding=24.0, gap=12.0),
        children=[
            Text(content=f"Contagem: {app.state.count}", key="label"),
            Button(label="Incrementar", on_click=on_increment, key="btn"),
        ],
    )
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `label` | `str` | *(obrigatório)* | Texto exibido no botão. |
| `on_click` | `handler → TapEvent` | `None` | Chamado ao tocar no botão. O handler pode ser zero-argumento ou receber um `TapEvent`. |

!!! note "Handler zero-argumento vs TapEvent"
    O `on_click` aceita qualquer das duas assinaturas abaixo — use a que for
    mais conveniente:

    ```python
    # com evento
    async def on_click(e: TapEvent) -> None:
        app.set_state(lambda s: setattr(s, "count", s.count + 1))

    # sem argumento
    async def on_click() -> None:
        app.set_state(lambda s: setattr(s, "count", s.count + 1))
    ```

---

## ProgressBar

Uma barra de progresso horizontal. Pode operar em modo determinado (0.0–1.0)
ou em modo indeterminado (animação contínua).

```python
from tempestroid import Button, Column, ProgressBar, Style, TapEvent, Text
from dataclasses import dataclass

@dataclass
class State:
    progress: float = 0.0
    loading: bool = False

def make_state() -> State:
    return State()

async def on_start(e: TapEvent) -> None:
    app.set_state(lambda s: setattr(s, "loading", True))

def view(app) -> Column:
    return Column(
        style=Style(padding=24.0, gap=16.0),
        children=[
            Text(content="Download em andamento", key="label"),
            # modo determinado: 60 % concluído
            ProgressBar(value=0.6, key="det"),
            # modo indeterminado: progresso desconhecido
            ProgressBar(indeterminate=app.state.loading, key="indet"),
            Button(label="Iniciar", on_click=on_start, key="btn"),
        ],
    )
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `value` | `float` | `0.0` | Progresso de `0.0` (vazio) a `1.0` (completo). Ignorado quando `indeterminate=True`. |
| `indeterminate` | `bool` | `False` | `True` exibe uma animação contínua em vez de um valor fixo. |

---

## Spinner

Um indicador circular de atividade — sempre indeterminado. Use-o para
sinalizar que o app está processando algo em segundo plano.

```python
from tempestroid import Column, Spinner, Style, Text
from dataclasses import dataclass

@dataclass
class State:
    loading: bool = True

def make_state() -> State:
    return State()

def view(app) -> Column:
    return Column(
        style=Style(padding=24.0, gap=16.0),
        children=[
            Spinner(size=40.0, key="spin") if app.state.loading
            else Text(content="Carregado!", key="done"),
        ],
    )
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `size` | `float \| None` | `None` | Diâmetro em pixels lógicos. `None` usa o tamanho padrão do renderizador. |

---

## Recapitulando

- **`Text`** — rótulo estático; exige apenas `content`. Estilize via `Style`.
- **`Button`** — botão tocável com `label` obrigatório; `on_click` recebe um
  `TapEvent` (ou pode ser zero-argumento). Use `app.set_state` dentro do
  handler para atualizar a UI.
- **`ProgressBar`** — modo determinado (`value` de `0.0` a `1.0`) ou
  indeterminado (`indeterminate=True`).
- **`Spinner`** — indicador circular sempre em animação; tamanho opcional via
  `size`.

Próximos passos: estilize os widgets com **[Estilos](../estilos.md)**, veja
como entradas de texto funcionam em **[Inputs](inputs.md)**, ou explore apps
completos na **[Galeria de exemplos](../exemplos.md)**.

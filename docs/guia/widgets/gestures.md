# Widgets de gestos

Os widgets de gestos são invólucros de filho único (ou lista de filhos, no caso
de `ReorderableList`) que detectam interações táteis — pan, arrastar, pinçar,
toque duplo, deslize lateral e reordenação — e emitem um evento tipado que o
handler converte em mudança de estado. Eles são compostos sobre os primitivos
de layout: basta embrulhar qualquer widget existente para adicionar
comportamento gestual sem alterar sua aparência.

Todos os widgets desta família são suportados pelos **dois renderizadores** —
simulador Qt (desktop) e Compose no dispositivo — sem diferença de API;
swipe-to-delete e reordenação foram verificados em ambos, e o pinch-zoom foi
verificado no dispositivo.

---

## GestureDetector

Invólucro de filho único que reporta toque simples, duplo, pressão longa e
deslize diretamente sobre a área do filho.

```python
from tempestroid import (
    Container,
    GestureDetector,
    LongPressEvent,
    Style,
    SwipeEvent,
    TapEvent,
    Text,
)


async def on_tap(e: TapEvent) -> None:
    app.set_state(lambda s: setattr(s, "msg", "tocado"))


async def on_long(e: LongPressEvent) -> None:
    app.set_state(lambda s: setattr(s, "msg", "pressão longa"))


async def on_swipe(e: SwipeEvent) -> None:
    app.set_state(lambda s: setattr(s, "msg", f"deslize {e.direction}"))


GestureDetector(
    on_tap=on_tap,
    on_long_press=on_long,
    on_swipe=on_swipe,
    child=Container(
        style=Style(padding=24.0, background="#E3F2FD", border_radius=12.0),
        child=Text(content="Toque ou deslize aqui", key="label"),
    ),
    key="detector",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `child` | `Widget \| None` | `None` | Filho único sobre o qual os gestos são detectados. |
| `on_tap` | `handler → TapEvent` | `None` | Toque simples. `TapEvent` tem os campos `x: float \| None` e `y: float \| None` com a posição do toque. |
| `on_double_tap` | `handler → TapEvent` | `None` | Toque duplo rápido. Emite o mesmo `TapEvent`. |
| `on_long_press` | `handler → LongPressEvent` | `None` | Pressão sustentada. `LongPressEvent` tem `x: float \| None` e `y: float \| None`. |
| `on_swipe` | `handler → SwipeEvent` | `None` | Deslize em qualquer direção. `SwipeEvent` tem `direction: str` (`"left"`, `"right"`, `"up"`, `"down"`). |

---

## PanHandler

Invólucro de filho único que reporta um gesto de pan (arrastar sem largar),
útil para mover objetos na tela ou implementar scroll personalizado.

```python
from tempestroid import Container, PanEvent, PanHandler, Style, Text


async def on_pan(e: PanEvent) -> None:
    app.set_state(
        lambda s: setattr(s, "offset", (s.offset[0] + e.delta_x, s.offset[1] + e.delta_y))
    )


PanHandler(
    on_pan=on_pan,
    child=Container(
        style=Style(padding=20.0, background="#FFF9C4", border_radius=8.0),
        child=Text(content="Arraste-me", key="lbl"),
    ),
    key="pan",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `child` | `Widget \| None` | `None` | Filho único monitorado. |
| `on_pan` | `handler → PanEvent` | `None` | Chamado continuamente durante o pan. `PanEvent` tem `delta_x: float`, `delta_y: float` (deslocamento desde o último evento) e `state: str` (`"start"`, `"update"`, `"end"`). |

---

## ScaleHandler

Invólucro de filho único que reporta pinch-to-zoom e rotação, além de toque
duplo como atalho de zoom.

```python
from tempestroid import Container, ScaleEvent, ScaleHandler, Style, TapEvent, Text


async def on_scale(e: ScaleEvent) -> None:
    app.set_state(lambda s: setattr(s, "zoom", s.zoom * e.scale))


async def on_double_tap(e: TapEvent) -> None:
    app.set_state(lambda s: setattr(s, "zoom", 1.0))


ScaleHandler(
    on_scale=on_scale,
    on_double_tap=on_double_tap,
    child=Container(
        style=Style(padding=32.0, background="#F3E5F5", border_radius=8.0),
        child=Text(content="Pinche para ampliar", key="lbl"),
    ),
    key="scale",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `child` | `Widget \| None` | `None` | Filho único monitorado. |
| `on_scale` | `handler → ScaleEvent` | `None` | Chamado durante o gesto de pinça. `ScaleEvent` tem `scale: float` (fator acumulado), `rotation: float` (graus) e `state: str` (`"start"`, `"update"`, `"end"`). |
| `on_double_tap` | `handler → TapEvent` | `None` | Toque duplo sobre a área do filho (conveniente para resetar zoom). |

---

## DoubleTapHandler

Invólucro de filho único focado exclusivamente em toque duplo — mais leve que
`GestureDetector` quando as demais gestos não são necessários.

```python
from tempestroid import Container, DoubleTapHandler, Style, TapEvent, Text


async def on_double(e: TapEvent) -> None:
    app.set_state(lambda s: setattr(s, "liked", not s.liked))


DoubleTapHandler(
    on_double_tap=on_double,
    child=Container(
        style=Style(padding=16.0, background="#FCE4EC", border_radius=8.0),
        child=Text(content="Toque duplo para curtir", key="lbl"),
    ),
    key="dtap",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `child` | `Widget \| None` | `None` | Filho único monitorado. |
| `on_double_tap` | `handler → TapEvent` | `None` | Toque duplo rápido. `TapEvent` tem `x: float \| None` e `y: float \| None`. |

---

## Draggable

Torna o filho arrastável. Ao iniciar o drag, o runtime carrega `drag_data`
que será entregue ao `DragTarget` ao soltar.

```python
from tempestroid import Container, DragEvent, Draggable, Style, Text


async def on_drag(e: DragEvent) -> None:
    app.set_state(lambda s: setattr(s, "dragging", e.state == "start"))


Draggable(
    drag_data="card-1",
    on_drag=on_drag,
    child=Container(
        style=Style(padding=16.0, background="#E8F5E9", border_radius=8.0),
        child=Text(content="Arraste-me até o alvo", key="lbl"),
    ),
    key="drag",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `child` | `Widget \| None` | `None` | Filho único que será arrastado. |
| `drag_data` | `str` | `""` | Dado opaco entregue ao `DragTarget.on_drop` como `DragEvent.data`. |
| `on_drag` | `handler → DragEvent` | `None` | Chamado em mudanças de estado do drag. `DragEvent` tem `data: str` e `state: str` (`"start"`, `"update"`, `"end"`). |

---

## DragTarget

Área receptora que aceita um `Draggable` soltado sobre ela.

```python
from tempestroid import Container, DragEvent, DragTarget, Style, Text


async def on_drop(e: DragEvent) -> None:
    app.set_state(lambda s: s.items.append(e.data))


DragTarget(
    on_drop=on_drop,
    child=Container(
        style=Style(
            padding=24.0,
            background="#FFF3E0",
            border_radius=8.0,
        ),
        child=Text(content="Solte aqui", key="lbl"),
    ),
    key="target",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `child` | `Widget \| None` | `None` | Filho único que representa a área de destino. |
| `on_drop` | `handler → DragEvent` | `None` | Chamado quando um `Draggable` é solto sobre esta área. `DragEvent` tem `data: str` (o `drag_data` do `Draggable`) e `state: str` (`"end"`). |

!!! tip "Combinando Draggable e DragTarget"
    Use `drag_data` para identificar qual item foi solto. O `on_drop` recebe
    `DragEvent.data` com esse valor, assim você pode atualizar o estado sem
    precisar de variáveis globais.

---

## Dismissible

Torna o filho dispensável com um deslize lateral (swipe-to-delete). O handler
`on_dismiss` é chamado quando o deslize é completado; remova o item do estado
para que o reconciliador o descarte da árvore.

```python
from tempestroid import Column, DismissEvent, Dismissible, Style, SwipeDirection, Text


async def on_dismiss(e: DismissEvent) -> None:
    app.set_state(lambda s: s.items.remove(item_id))


Dismissible(
    direction=SwipeDirection.LEFT,
    on_dismiss=on_dismiss,
    child=Column(
        style=Style(padding=12.0, background="#FAFAFA"),
        children=[
            Text(content="Deslize para remover", key="lbl"),
        ],
    ),
    key=f"item-{item_id}",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `child` | `Widget \| None` | `None` | Filho único que pode ser dispensado. |
| `direction` | `SwipeDirection` | `SwipeDirection.LEFT` | Direção do deslize que dispara a dispensa. Valores: `LEFT`, `RIGHT`. |
| `on_dismiss` | `handler → DismissEvent` | `None` | Chamado ao completar o deslize. `DismissEvent` tem `direction: str`. Remova o item do estado para que o reconciliador o retire da árvore. |

!!! warning "Remova o item do estado"
    `Dismissible` **não** remove o widget da árvore por conta própria — ele
    apenas notifica. Chame `app.set_state` no `on_dismiss` para remover o item
    da lista; o reconciliador emitirá o patch `Remove` correspondente.

---

## ReorderableList

Lista vertical cujos itens podem ser reordenados por arrastar e soltar.
`on_reorder` entrega os índices de origem e destino; o app reorganiza a lista
no estado e reconstrói a árvore.

```python
from tempestroid import ReorderEvent, ReorderableList, Text


async def on_reorder(e: ReorderEvent) -> None:
    def move(s: State) -> None:
        item = s.items.pop(e.old_index)
        s.items.insert(e.new_index, item)

    app.set_state(move)


ReorderableList(
    on_reorder=on_reorder,
    children=[
        Text(content=item, key=item_id)
        for item_id, item in enumerate(app.state.items)
    ],
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `children` | `list[Widget]` | `[]` | Itens da lista; use `key` estável em cada filho para que o reconciliador emita `Reorder` em vez de recriar os widgets. |
| `on_reorder` | `handler → ReorderEvent` | `None` | Chamado ao soltar um item na nova posição. `ReorderEvent` tem `old_index: int` e `new_index: int`. |

!!! tip "Chaves estáveis são essenciais"
    Dê um `key` único e estável a cada filho de `ReorderableList`. Sem chaves,
    o reconciliador não consegue emitir um patch `Reorder` eficiente e acaba
    recriando os itens desnecessariamente.

---

## InteractiveViewer

Container de filho único que permite ao usuário fazer pan e zoom (pinça + arraste)
sobre o conteúdo, com limites de escala configuráveis.

```python
from tempestroid import Container, Image, InteractiveViewer, ScaleEvent, Style


async def on_interaction(e: ScaleEvent) -> None:
    app.set_state(lambda s: setattr(s, "zoom", e.scale))


InteractiveViewer(
    min_scale=0.5,
    max_scale=4.0,
    on_interaction=on_interaction,
    child=Image(
        src="https://example.com/mapa.jpg",
        alt="Mapa interativo",
        key="map",
    ),
    key="viewer",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `child` | `Widget \| None` | `None` | Filho único sobre o qual pan e zoom são aplicados. |
| `min_scale` | `float` | `0.5` | Fator mínimo de escala permitido. |
| `max_scale` | `float` | `4.0` | Fator máximo de escala permitido. |
| `on_interaction` | `handler → ScaleEvent` | `None` | Chamado durante pan e zoom. `ScaleEvent` tem `scale: float`, `rotation: float` e `state: str`. |

!!! info "Pinch-zoom verificado no dispositivo"
    O gesto de pinça real foi verificado em um dispositivo arm64 (Xiaomi
    23053RN02A, Android 15). No simulador Qt o zoom é simulado com scroll do
    mouse + `Ctrl`.

---

## Recapitulando

- **`GestureDetector`** — invólucro multigestos: tap, duplo tap, pressão longa e
  deslize em qualquer direção.
- **`PanHandler`** — pan contínuo com `delta_x`/`delta_y` em cada frame do
  gesto.
- **`ScaleHandler`** — pinch-to-zoom e rotação via `ScaleEvent`; toque duplo
  como atalho de zoom.
- **`DoubleTapHandler`** — toque duplo isolado, mais leve que `GestureDetector`
  quando só esse gesto importa.
- **`Draggable`** / **`DragTarget`** — par para drag-and-drop: `drag_data`
  identifica o item; `DragEvent.data` o entrega ao alvo.
- **`Dismissible`** — swipe-to-delete; sempre remova o item do estado no
  `on_dismiss` para que o reconciliador gere o `Remove`.
- **`ReorderableList`** — reordenação por arrastar; `ReorderEvent` fornece
  `old_index` e `new_index`; use `key` estável em cada filho.
- **`InteractiveViewer`** — pan + zoom num filho único com limites `min_scale` /
  `max_scale`; pinch-zoom verificado no dispositivo.

Próximos passos: explore overlays e feedback na página de
**[Overlays](overlays.md)**, veja inputs avançados em **[Inputs](inputs.md)**,
ou confira apps completos na **[Galeria de exemplos](../exemplos.md)**.

# Animação

O framework de animação do tempestroid vive no núcleo renderer-agnóstico: um
`AnimationController` avança um valor normalizado (0.0–1.0) no relógio de
quadros do `App`, um `Tween` interpola um valor tipado a partir desse progresso,
e o `view` lê o resultado interpolado para montar a árvore com os estilos já no
alvo do quadro atual. Os widgets desta página — `Animated`, `AnimatedList`,
`Hero`, `Shimmer` e `Skeleton` — são a superfície declarativa que consome esses
drivers.

!!! tip "Controlador determinístico nos testes"
    O `AnimationController` aceita um `time_source` injetável, então os testes
    passam um relógio determinístico e avançam quadros manualmente — sem
    `sleep`, sem flakiness. O mesmo relógio cruza o bridge via `FRAME_TOKEN`
    para que as animações no dispositivo sejam reais.

!!! info "Dois renderizadores, um núcleo"
    A interpolação acontece aqui, não nos renderizadores — o Qt e o Compose
    recebem apenas props finais por quadro. O Qt aplica o valor interpolado
    diretamente; o Compose aciona seu mecanismo nativo de animação com o
    mesmo valor de `Curve`, mantendo paridade visual.

---

## `Animated`

Embrulha um filho e interpola o `Style` dele a cada quadro, entre `style_begin`
e `style_end`, guiado por um `AnimationController`.

```python
from tempestroid import (
    Animated,
    AnimationController,
    Button,
    Column,
    Color,
    Curve,
    Style,
    Text,
    Tween,
)


def make_state():
    return {"expanded": False}


ctrl = AnimationController(duration_s=0.4, curve=Curve.EASE_IN_OUT)
opacity_tween = Tween(begin=0.0, end=1.0)


def view(app):
    state = app.state

    def on_toggle():
        if state["expanded"]:
            ctrl.reverse()
        else:
            ctrl.forward()
        app.set_state(lambda s: {**s, "expanded": not s["expanded"]})

    current_opacity = opacity_tween.at(ctrl.value)

    return Column(
        children=[
            Button(label="Alternar", on_click=on_toggle, key="btn"),
            Animated(
                controller=ctrl,
                style_begin=Style(opacity=0.0, background=Color.from_hex("#e0e0e0")),
                style_end=Style(opacity=1.0, background=Color.from_hex("#4caf50")),
                child=Text(
                    content=f"Opacidade: {current_opacity:.2f}",
                    key="label",
                ),
                key="box",
            ),
        ],
        key="root",
    )
```

### Props

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `child` | `Widget` | — (obrigatório) | O widget filho que recebe o estilo interpolado. |
| `controller` | `AnimationController \| None` | `None` | O controlador que avança o progresso de 0.0 a 1.0. |
| `style_begin` | `Style \| None` | `None` | Estilo aplicado quando `controller.value == 0.0`. |
| `style_end` | `Style \| None` | `None` | Estilo aplicado quando `controller.value == 1.0`. |

!!! note "Sem `controller`"
    Quando `controller` é `None` o filho é renderizado com `style_begin` (ou
    sem estilo extra, se também for `None`) — útil para desativar a animação
    condicionalmente sem remover o widget da árvore.

---

## `AnimatedList`

Contêiner flex que anima filhos à medida que entram e saem da lista. Ao
adicionar ou remover um item, o widget desliza e esvanece automaticamente.

```python
from tempestroid import AnimatedList, Button, Column, Curve, FlexDirection, Text


def make_state():
    return {"items": ["Maçã", "Banana", "Cereja"]}


def view(app):
    state = app.state

    def add_item():
        app.set_state(
            lambda s: {**s, "items": [*s["items"], f"Item {len(s['items']) + 1}"]}
        )

    def remove_last():
        app.set_state(lambda s: {**s, "items": s["items"][:-1]})

    return Column(
        children=[
            Button(label="Adicionar", on_click=add_item, key="add"),
            Button(label="Remover último", on_click=remove_last, key="rm"),
            AnimatedList(
                direction=FlexDirection.COLUMN,
                enter_duration_ms=350,
                exit_duration_ms=250,
                enter_curve=Curve.EASE_OUT,
                exit_curve=Curve.EASE_IN,
                children=[
                    Text(content=item, key=item) for item in state["items"]
                ],
                key="list",
            ),
        ],
        key="root",
    )
```

### Props

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `children` | `list[Widget]` | `[]` | Filhos da lista; use `key` estável para que o reconciliador identifique entradas e saídas. |
| `direction` | `FlexDirection` | `COLUMN` | Eixo do contêiner (`COLUMN` ou `ROW`). |
| `enter_duration_ms` | `int` | `300` | Duração da animação de entrada em milissegundos. |
| `exit_duration_ms` | `int` | `300` | Duração da animação de saída em milissegundos. |
| `enter_curve` | `Curve` | `EASE_OUT` | Curva de easing para a entrada. |
| `exit_curve` | `Curve` | `EASE_IN` | Curva de easing para a saída. |

!!! tip "Chaves estáveis são obrigatórias"
    O reconciliador identifica entradas/saídas pelo `key` de cada filho.
    Sem `key`, qualquer mudança na lista parece uma substituição total — sem
    animação de entrada/saída.

---

## `Hero`

Marca um único filho com uma tag de transição compartilhada. Quando o
`Navigator` navega entre duas telas que possuem um `Hero` com o mesmo
`hero_tag`, o framework interpola a posição e o tamanho do elemento entre as
duas rotas — o chamado *shared-element transition*.

```python
from tempestroid import Button, Column, Hero, Image, Navigator, Route, Text


def home_view(app):
    def go_detail():
        app.push("detail")

    return Column(
        children=[
            Hero(
                hero_tag="cover-art",
                child=Image(src="https://example.com/cover.jpg", key="img"),
                key="hero-home",
            ),
            Button(label="Ver detalhes", on_click=go_detail, key="btn"),
        ],
        key="root",
    )


def detail_view(app):
    return Column(
        children=[
            Hero(
                hero_tag="cover-art",
                child=Image(src="https://example.com/cover.jpg", key="img"),
                key="hero-detail",
            ),
            Text(content="Detalhes do álbum", key="title"),
        ],
        key="root",
    )


def make_state():
    return {}


def view(app):
    return Navigator(
        routes={
            "home": Route(builder=home_view),
            "detail": Route(builder=detail_view),
        },
        initial_route="home",
        key="nav",
    )
```

### Props

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `hero_tag` | `str` | — (obrigatório) | Identificador único compartilhado entre as duas telas. |
| `child` | `Widget` | — (obrigatório) | O widget que será "voado" entre as rotas. |

!!! info "Disponibilidade no dispositivo"
    No simulador Qt, o `Hero` aplica uma animação `QPropertyAnimation` de
    posição/tamanho. No Compose (dispositivo), o par de `Hero` aciona o
    `SharedTransitionLayout` nativo do Material3.

---

## `Shimmer`

Placeholder de carregamento que varre um destaque gradiente sobre um filho
enquanto o conteúdo real ainda não chegou. Use para indicar que dados estão
sendo buscados sem um spinner intrusivo.

```python
from tempestroid import Color, Column, Container, Shimmer, Style, Text


def make_state():
    return {"loading": True, "name": ""}


def view(app):
    state = app.state

    if state["loading"]:
        return Shimmer(
            base_color=Color.from_hex("#e0e0e0"),
            highlight_color=Color.from_hex("#f5f5f5"),
            duration_ms=1400,
            child=Container(
                style=Style(width=200.0, height=24.0),
                key="placeholder",
            ),
            key="shimmer",
        )

    return Column(
        children=[Text(content=state["name"], key="name")],
        key="root",
    )
```

### Props

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `child` | `Widget` | — (obrigatório) | O widget sobre o qual o efeito shimmer é aplicado. |
| `base_color` | `Color` | cinza claro | Cor de fundo da área de shimmer. |
| `highlight_color` | `Color` | branco | Cor do destaque que varre a área. |
| `duration_ms` | `int` | `1200` | Duração de um ciclo completo de varredura em milissegundos. |

---

## `Skeleton`

Placeholder retangular sem filho — a forma mais simples de shimmer para
blocos de texto ou imagens ainda não carregados. É essencialmente um
`Shimmer` sem filho explícito, com bordas arredondadas configuráveis.

```python
from tempestroid import Column, Skeleton, Text


def make_state():
    return {"loaded": False, "title": "", "subtitle": ""}


def view(app):
    state = app.state

    if not state["loaded"]:
        return Column(
            children=[
                Skeleton(width=240.0, height=20.0, radius=4.0, key="sk-title"),
                Skeleton(width=160.0, height=16.0, radius=4.0, key="sk-sub"),
            ],
            key="root",
        )

    return Column(
        children=[
            Text(content=state["title"], key="title"),
            Text(content=state["subtitle"], key="sub"),
        ],
        key="root",
    )
```

### Props

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `width` | `float \| None` | `None` | Largura fixa do bloco em dp; `None` expande no eixo principal. |
| `height` | `float \| None` | `None` | Altura fixa do bloco em dp; `None` expande no eixo transversal. |
| `radius` | `float` | `4.0` | Raio dos cantos arredondados em dp. |
| `base_color` | `Color` | cinza claro | Cor de fundo do bloco. |
| `highlight_color` | `Color` | branco | Cor do destaque que varre o bloco. |
| `duration_ms` | `int` | `1200` | Duração de um ciclo completo de varredura em milissegundos. |

---

## Recapitulando

- O driver (`AnimationController` + `Tween` + `Spring`) vive no núcleo e é
  **renderer-agnóstico** — interpola valores antes de montar a árvore.
- `Animated` consome um controlador e dois estilos para criar transições de
  propriedades quadro a quadro.
- `AnimatedList` anima entradas e saídas de filhos automaticamente — dê
  `key` estável a cada filho.
- `Hero` marca um elemento para transição compartilhada entre rotas do
  `Navigator`.
- `Shimmer` e `Skeleton` são placeholders de carregamento; `Skeleton` é
  mais simples (sem filho), `Shimmer` envolve qualquer widget.
- Ambos os renderizadores animam esses widgets — o Qt interpola no núcleo;
  o Compose aciona o mecanismo nativo com os mesmos parâmetros de curva.

## Próximos passos

➡️ Veja como compor widgets com **[Layout](../widgets.md)**, entenda os
**[Eventos](../eventos.md)** tipados, ou explore apps completos na
**[Galeria de exemplos](../exemplos.md)**.

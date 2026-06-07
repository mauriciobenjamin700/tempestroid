# Widgets de layout

Os widgets de layout são os blocos estruturais de toda tela tempestroid.
Eles organizam filhos no espaço — empilhando na vertical, na horizontal,
sobrepondo em camadas, rolando conteúdo longo ou respeitando as bordas seguras
do sistema. Você os combina livremente para montar qualquer estrutura de UI.

Todos os widgets desta família são suportados pelos **dois renderizadores** —
simulador Qt (desktop) e Compose no dispositivo — sem diferença de API.

---

## Column

Empilha filhos na vertical (eixo principal = cima para baixo).

```python
from tempestroid import Column, Style, Text

Column(
    style=Style(gap=8.0, padding=16.0),
    children=[
        Text(content="Título", key="title"),
        Text(content="Subtítulo", key="sub"),
    ],
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `children` | `list[Widget]` | `[]` | Filhos empilhados de cima para baixo. |

!!! tip "Chaves em listas"
    Sempre dê um `key` estável a cada filho de `Column` quando a lista puder
    mudar de tamanho — o reconciliador usa a chave para emitir `Reorder` em
    vez de recriar o widget.

---

## Row

Posiciona filhos na horizontal (eixo principal = esquerda para direita).

```python
from tempestroid import Button, Row, TapEvent

async def on_dec(e: TapEvent) -> None:
    app.set_state(lambda s: setattr(s, "count", s.count - 1))

async def on_inc(e: TapEvent) -> None:
    app.set_state(lambda s: setattr(s, "count", s.count + 1))

Row(
    children=[
        Button(label="-", on_click=on_dec, key="dec"),
        Button(label="+", on_click=on_inc, key="inc"),
    ],
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `children` | `list[Widget]` | `[]` | Filhos posicionados da esquerda para a direita. |

---

## Container

Uma caixa de filho único usada para aplicar padding, cor de fundo, bordas e
tamanho fixo via `Style`.

```python
from tempestroid import Container, Style, Text

Container(
    style=Style(padding=16.0, background="#1E90FF", border_radius=8.0),
    child=Text(content="Olá!"),
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `child` | `Widget \| None` | `None` | Filho único a ser embrulhado. |

!!! note "Estilo é a API principal do Container"
    `Container` por si só não define tamanho, cor ou espaçamento — use
    `style=Style(...)` para isso. Sem `Style`, ele age como um `Column`
    transparente de um único filho.

---

## Stack

Um container de sobreposição: os filhos compartilham a mesma caixa, em
camadas ordenadas pelo índice (último = mais à frente).

```python
from tempestroid import Container, Stack, Style, Text

Stack(
    children=[
        Container(
            style=Style(width=200.0, height=200.0, background="#E0E0E0"),
            key="bg",
        ),
        Text(content="Sobreposto", key="label"),
    ],
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `children` | `list[Widget]` | `[]` | Filhos sobrepostos em ordem de z. |

---

## Wrap

Um container de fluxo: os filhos quebram para a linha seguinte quando a
linha corrente enche (equivalente a `flex-wrap: wrap`).

```python
from tempestroid import Chip, Wrap

Wrap(
    children=[
        Chip(label="Python", key="py"),
        Chip(label="Android", key="android"),
        Chip(label="Kotlin", key="kt"),
        Chip(label="Compose", key="compose"),
    ],
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `children` | `list[Widget]` | `[]` | Filhos que quebram de linha ao atingir a largura máxima. |

---

## ScrollView

Um container rolável que acomoda filhos que ultrapassam o espaço visível.
Por padrão rola na vertical; `horizontal=True` inverte o eixo.

```python
from tempestroid import Column, ScrollView, Style, Text

ScrollView(
    children=[
        Text(content=f"Item {i}", key=str(i))
        for i in range(50)
    ],
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `horizontal` | `bool` | `False` | `True` ativa rolagem horizontal. |
| `children` | `list[Widget]` | `[]` | Conteúdo rolável. |

!!! tip "Listas longas com muitos itens"
    Para listas de centenas ou milhares de itens prefira `LazyColumn` /
    `LazyRow` (família **lists**), que virtualizam o conteúdo e só
    materializam a janela visível.

---

## SafeArea

Uma caixa de filho único que inseta o conteúdo para longe das intrusões do
sistema (notch, barra de status, barra de navegação gestual).

```python
from tempestroid import Column, SafeArea, Text

SafeArea(
    child=Column(
        children=[
            Text(content="Conteúdo seguro", key="body"),
        ],
    ),
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `child` | `Widget \| None` | `None` | Filho a ser inserido nas bordas seguras. |
| `edges` | `list[SafeAreaEdge]` | `[]` | Bordas a respeitar. Lista vazia = todas as bordas. |

!!! info "Bordas seguras"
    `SafeAreaEdge` é um enum com os valores `TOP`, `BOTTOM`, `LEFT` e
    `RIGHT`. Passe uma lista vazia (padrão) para proteger todas as bordas,
    ou escolha apenas as que fazem sentido para o contexto da tela.

---

## AspectRatio

Uma caixa de filho único que restringe o filho a uma proporção largura/altura
fixa.

```python
from tempestroid import AspectRatio, Image

AspectRatio(
    ratio=16 / 9,
    child=Image(src="https://example.com/banner.jpg", alt="Banner"),
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `ratio` | `float` | *(obrigatório)* | Proporção largura ÷ altura (ex.: `16/9 ≈ 1.77`). |
| `child` | `Widget \| None` | `None` | Filho a ser constrangido. |

---

## PageView

Um carrossel horizontal paginado: uma página de largura total por vez, com
suporte a troca programática via `page` e reporte de mudança via
`on_page_change`.

```python
from tempestroid import Container, PageView, PageChangeEvent, Style, Text

async def on_page(e: PageChangeEvent) -> None:
    app.set_state(lambda s: setattr(s, "page", e.index))

PageView(
    page=app.state.page,
    on_page_change=on_page,
    children=[
        Container(
            style=Style(background="#FF6B6B", padding=32.0),
            child=Text(content="Página 1"),
            key="p0",
        ),
        Container(
            style=Style(background="#4ECDC4", padding=32.0),
            child=Text(content="Página 2"),
            key="p1",
        ),
        Container(
            style=Style(background="#45B7D1", padding=32.0),
            child=Text(content="Página 3"),
            key="p2",
        ),
    ],
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `children` | `list[Widget]` | `[]` | Páginas do carrossel; cada uma ocupa a largura total. |
| `page` | `int` | `0` | Índice da página visível (controlado pelo app). |
| `on_page_change` | `handler → PageChangeEvent` | `None` | Chamado quando o usuário desliza para outra página. O handler recebe um `PageChangeEvent` com o campo `index`. |

---

## KeyboardAvoidingView

Um container vertical que recua o conteúdo quando o teclado virtual aparece,
evitando que campos de entrada fiquem ocultos sob o teclado.

```python
from tempestroid import Column, Input, KeyboardAvoidingView, TextChangeEvent

async def on_change(e: TextChangeEvent) -> None:
    app.set_state(lambda s: setattr(s, "text", e.value))

KeyboardAvoidingView(
    children=[
        Input(
            value=app.state.text,
            placeholder="Digite aqui...",
            on_change=on_change,
            key="field",
        ),
    ],
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `children` | `list[Widget]` | `[]` | Filhos empilhados na vertical; recuam quando o teclado abre. |

!!! info "Comportamento no simulador Qt"
    No simulador desktop o teclado físico não aciona o recuo — o widget
    age como um `Column` normal. O comportamento de recuo só é visível no
    dispositivo Android, onde o teclado virtual pode cobrir parte da tela.

---

## Recapitulando

- **`Column` / `Row`** — empilham filhos na vertical e horizontal. Sempre use
  `key` em listas dinâmicas.
- **`Container`** — embrulha um único filho; todo o visual vem do `Style`.
- **`Stack`** — sobrepõe filhos em camadas (z-order = índice na lista).
- **`Wrap`** — fluxo com quebra de linha automática, ideal para chips e tags.
- **`ScrollView`** — rola conteúdo que ultrapassa o espaço visível; prefira
  `LazyColumn`/`LazyRow` para listas muito longas.
- **`SafeArea`** — inseta o conteúdo das bordas seguras do sistema (notch,
  barras).
- **`AspectRatio`** — força uma proporção fixa no filho.
- **`PageView`** — carrossel de páginas de largura total; `page` é controlado
  pelo app.
- **`KeyboardAvoidingView`** — recua o conteúdo quando o teclado virtual abre
  (efeito visível apenas no dispositivo).

Próximos passos: estilize os widgets com **[Estilos](../estilos.md)**, explore
inputs na página de **[Inputs](inputs.md)**, ou veja apps completos na
**[Galeria de exemplos](../exemplos.md)**.

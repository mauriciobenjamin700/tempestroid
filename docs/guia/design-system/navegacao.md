# Navegação

Você já tem ação ([variantes](variantes.md), [kit](kit.md)), moldura
([superfície](superficie.md)) e conversa ([feedback](feedback.md)). Falta a
**casca de navegação**: a barra do topo, a barra de abas, a navegação inferior, a
busca, o caminho de páginas. Esta página estiliza essa camada — todos os
componentes resolvem as **superfícies M3** e o **acento do item ativo** a partir
do `color_scheme`/`theme`, sem nenhuma cor escrita à mão.

![A galeria H5 no simulador Qt](../../assets/examples/h5gallery.png){ width=300 }

*O exemplo `examples/h5gallery` no simulador Qt: `AppBar`, `Header`,
`Breadcrumb`, `SearchBar`, `Tabs` e `NavBar` — todos tingidos pelo tema.*

!!! info "Onde os nomes moram"
    Tudo desta página é importado de **`tempestroid`**: os componentes de
    navegação (`AppBar`, `CollapsingAppBar`, `NavBar`, `Drawer`, `Sidebar`,
    `Breadcrumb`, `Burger`, `Footer`, `Header`, `Scaffold`, `SearchBar`, `Tabs`)
    e o `Theme`.

## A `AppBar` e o `Header`

A `AppBar` é a barra do topo — uma **superfície elevada** M3 com título, um
widget `leading` (botão de voltar/menu) e uma lista de `actions` à direita. O
`color_scheme` define o papel da superfície e do conteúdo:

```python
from tempestroid import AppBar, Button, Variant, Widget


def barra(theme) -> Widget:  # theme: Theme
    return AppBar(
        title="Tempestroid",
        color_scheme="primary",
        actions=[
            Button(label="Sair", variant=Variant.GHOST, theme=theme, key="out"),
        ],
        theme=theme,
    )
```

O `Header` é o cabeçalho de conteúdo (não a barra do sistema): título grande +
subtítulo, sobre a superfície da página.

```python
from tempestroid import Header, Widget


def cabecalho(theme) -> Widget:  # theme: Theme
    return Header(
        title="Painel",
        subtitle="Visão geral do projeto",
        theme=theme,
    )
```

!!! tip "Barra que colapsa ao rolar"
    `CollapsingAppBar` é a `AppBar` que encolhe conforme a tela rola: passe o
    `scroll_offset` (do `ScrollEvent`) e ela interpola entre `expanded_height` e
    `collapsed_height`. É o casamento da [app bar colapsável do E6](../widgets/layout.md)
    com os tokens do tema.

## `Tabs` — a faixa de abas M3

`Tabs` é a faixa de abas estilizada: uma lista de rótulos (`tabs`), o índice
ativo (`active`) e um handler `on_select(index)`. A aba ativa ganha o **acento do
`color_scheme`** mais um sublinhado:

```python
from tempestroid import Tabs, Widget


def abas(theme, ativa: int) -> Widget:  # theme: Theme
    return Tabs(
        tabs=["Visão geral", "Atividade", "Ajustes"],
        active=ativa,
        on_select=lambda i: None,  # troque o índice no seu estado
        color_scheme="primary",
        theme=theme,
    )
```

!!! note "`Tabs` é a faixa; as telas são suas"
    `Tabs` só desenha e emite a seleção — ele não troca conteúdo sozinho. Guarde
    o índice no estado, renderize o corpo da aba ativa e atualize via
    `app.set_state`. Para uma pilha de telas com transição animada, use o
    [`TabView`/`Navigator` da navegação](../navegacao.md).

## `NavBar` — a navegação inferior

`NavBar` é a barra de destinos (estilo "bottom navigation" do M3): rótulos via
`items`, o destino ativo via `active`, e `on_select(index)`. O item ativo recebe
a **pílula de acento** do `color_scheme`:

```python
from tempestroid import NavBar, Widget


def navegacao(theme, ativo: int) -> Widget:  # theme: Theme
    return NavBar(
        items=["Início", "Buscar", "Perfil"],
        active=ativo,
        on_select=lambda i: None,
        color_scheme="primary",
        theme=theme,
    )
```

## `SearchBar` e `Breadcrumb`

A `SearchBar` é o campo de busca M3 — um `field_variant` sobre a superfície, com
`value`, `placeholder`, `on_change(texto)` e um `on_clear` opcional. O
`Breadcrumb` é o caminho de páginas: uma lista de rótulos (`items`) com um
`separator` e `on_select(index)`.

```python
from tempestroid import Breadcrumb, SearchBar, VStack, Widget


def busca_e_caminho(theme, consulta: str) -> Widget:  # theme: Theme
    return VStack(
        gap="md",
        theme=theme,
        children=[
            SearchBar(
                value=consulta,
                placeholder="Buscar…",
                on_change=lambda q: None,  # guarde no estado
                color_scheme="primary",
                theme=theme,
            ),
            Breadcrumb(
                items=["Início", "Projetos", "Tempestroid"],
                on_select=lambda i: None,
                theme=theme,
            ),
        ],
    )
```

!!! tip "O resto da casca"
    A mesma camada traz `Drawer`/`Sidebar` (gaveta lateral), `Burger` (o botão
    de menu), `Footer`, e o `Scaffold` (o esqueleto barra-superior + corpo +
    barra-inferior que junta tudo). Todos seguem o tema e aceitam
    `color_scheme`. Veja o catálogo completo na
    [visão geral de widgets](../widgets.md) e na
    [API pública](../../referencia/api.md).

## Exemplo completo: a galeria de navegação

`examples/h5gallery/app.py` desenha a casca inteira — `AppBar`, `Header`,
`Breadcrumb`, `SearchBar` (digite e o estado atualiza), `Tabs` (toque troca a aba
ativa) e `NavBar` (toque troca o destino), todos tingidos pelo tema:

```bash
uv run python examples/h5gallery/app.py
# ou: make run APP=examples/h5gallery/app.py
```

O fonte completo está no
[`examples/h5gallery/app.py`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/h5gallery/app.py).
No aparelho, o mesmo `view`/`make_state` carrega no host Compose: como toda a
camada é de **componentes compostos** (descem a primitivos via
`Component.render`), eles renderizam pelos filhos primitivos nos **dois
renderizadores**, sobre as superfícies e o acento resolvidos do tema.

## Recapitulando

- A `AppBar` é a barra do topo (superfície elevada + `leading`/`actions`); o
  `Header` é o cabeçalho de conteúdo; `CollapsingAppBar` encolhe ao rolar via
  `scroll_offset`.
- `Tabs` é a faixa de abas M3 (`tabs`/`active`/`on_select`), com acento +
  sublinhado na aba ativa — você guarda o índice e renderiza o corpo.
- `NavBar` é a navegação inferior (`items`/`active`/`on_select`) com pílula de
  acento no destino ativo.
- `SearchBar` é o campo de busca (`value`/`on_change`/`on_clear`); `Breadcrumb`
  é o caminho de páginas (`items`/`on_select`).
- `Drawer`/`Sidebar`/`Burger`/`Footer`/`Scaffold` completam a casca — tudo segue
  o tema e o `color_scheme`.

A seguir: os [componentes de pesquisa](pesquisa.md) — métricas, gráficos e a
ponte com o `ort-vision-sdk`.

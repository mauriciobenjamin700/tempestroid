# Componentes compostos

Componentes compostos são blocos de interface de alto nível prontos para uso.
Cada um herda de `Component` e implementa um método `render()` que retorna uma
subárvore de widgets primitivos — `Column`, `Row`, `Container`, `Text`,
`Button`, etc. O reconciliador e os renderizadores os tratam de forma idêntica
às primitivas: sem código especial, sem casos extras no Qt ou no Compose.

!!! info "Dois renderizadores, zero código extra"
    Como os componentes baixam para primitivas via `render()`, eles funcionam
    identicamente no **simulador Qt** (desktop) e no **Compose no dispositivo**
    sem nenhuma alteração nos renderizadores.

Importe sempre do nível do pacote — cada componente abaixo mostra os imports de
que precisa:

```python
from tempestroid import AppBar, Card, NavBar, Scaffold
```

---

## Cartões e listas

### Card

Superfície elevada que agrupa filhos verticalmente num contêiner arredondado
com sombra.

```python
from tempestroid import Button, Card, Text

Card(
    children=[
        Text(content="Bem-vindo!", key="t"),
        Button(label="Entrar", on_click=on_enter, key="btn"),
    ],
    key="welcome-card",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `children` | `list[Widget]` | `[]` | Widgets empilhados verticalmente dentro do cartão. |

---

### ListTile

Linha de lista com texto principal, texto secundário opcional e slots para
widget inicial e final.

```python
from tempestroid import Avatar, Button, ListTile, TapEvent

async def on_delete(e: TapEvent) -> None:
    app.set_state(lambda s: s.remove_item(item_id))

ListTile(
    title="Maria Silva",
    subtitle="maria@example.com",
    leading=Avatar(initials="MS", key="av"),
    trailing=Button(label="✕", on_click=on_delete, key="del"),
    key="tile-1",
)
```

!!! note "Toque na linha inteira"
    `ListTile` é apresentacional (sem `on_click` próprio). Para ações use um
    `Button` no slot `trailing`, ou envolva o tile num `Button` sem rótulo.

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `title` | `str` | `""` | Texto principal da linha. |
| `subtitle` | `str \| None` | `None` | Texto secundário, mostrado em tom reduzido abaixo do título. |
| `leading` | `Widget \| None` | `None` | Widget posicionado antes do texto (ex.: `Avatar`). |
| `trailing` | `Widget \| None` | `None` | Widget posicionado após o texto (ex.: `Button`). |

---

### Avatar

Círculo com iniciais — ótimo para ícones de perfil ou marcadores.

```python
from tempestroid import Avatar

Avatar(initials="MB", size=48.0, key="profile-av")
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `initials` | `str` | `""` | Texto curto mostrado dentro do círculo (ex.: `"MB"`). |
| `size` | `float` | `40.0` | Diâmetro do círculo em pixels lógicos. |

---

### Divider

Linha horizontal fina para separar seções.

```python
from tempestroid import Column, Divider, Text

Column(
    children=[
        Text(content="Seção A", key="a"),
        Divider(thickness=1.0, key="div"),
        Text(content="Seção B", key="b"),
    ],
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `thickness` | `float` | `1.0` | Altura da linha em pixels lógicos. |

---

## Barras e navegação

### AppBar

Barra de aplicativo superior com widget inicial, título e ações ao final.

```python
from tempestroid import AppBar, Button, TapEvent

async def on_menu(e: TapEvent) -> None:
    app.set_state(lambda s: setattr(s, "drawer_open", True))

AppBar(
    title="Meu App",
    leading=Button(label="☰", on_click=on_menu, key="menu"),
    actions=[Button(label="⚙", on_click=on_settings, key="cfg")],
    key="appbar",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `title` | `str` | `""` | Texto do título. |
| `leading` | `Widget \| None` | `None` | Widget antes do título (ex.: botão voltar ou `Burger`). |
| `actions` | `list[Widget]` | `[]` | Widgets de ação ao final da barra. |

---

### Header

Cabeçalho de página com título e subtítulo opcional, com fundo distinto.

```python
from tempestroid import Header

Header(title="Dashboard", subtitle="Visão geral do dia", key="page-header")
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `title` | `str` | `""` | Texto principal do cabeçalho. |
| `subtitle` | `str \| None` | `None` | Linha secundária muda abaixo do título. |

---

### Footer

Barra inferior centralizando filhos arbitrários (links, rótulos, ações).

```python
from tempestroid import Footer, Text

Footer(
    children=[
        Text(content="© 2026 Minha Empresa", key="copy"),
    ],
    key="footer",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `children` | `list[Widget]` | `[]` | Widgets exibidos na barra inferior. |

---

### CollapsingAppBar

Barra de aplicativo que encolhe conforme o usuário rola o conteúdo. A altura
é derivada de `scroll_offset` — o app lê o evento de scroll da lista e
repassa o valor como estado, sem nenhuma lógica no renderizador.

```python
from tempestroid import CollapsingAppBar, LazyColumn, ScrollEvent

async def on_scroll(e: ScrollEvent) -> None:
    app.set_state(lambda s: setattr(s, "offset", e.offset))

def view(app):
    return Column(children=[
        CollapsingAppBar(
            title="Notícias",
            scroll_offset=app.state.offset,
            expanded_height=200.0,
            collapsed_height=56.0,
            key="cbar",
        ),
        LazyColumn(
            item_count=100,
            item_builder=build_item,
            on_scroll=on_scroll,
            key="list",
        ),
    ])
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `title` | `str` | `""` | Texto do título. |
| `expanded_height` | `float` | `200.0` | Altura da barra quando `scroll_offset == 0`. |
| `collapsed_height` | `float` | `56.0` | Altura mínima após colapso total. |
| `scroll_offset` | `float` | `0.0` | Offset atual de scroll em pixels lógicos (vem do estado do app). |
| `background` | `Color \| None` | `None` | Cor de fundo (padrão: token `SURFACE`). |

---

### NavBar

Barra de navegação/abas horizontal com item ativo destacado. Cada item é um
botão; tocar chama `on_select(index)`.

```python
from tempestroid import NavBar

NavBar(
    items=["Início", "Explorar", "Perfil"],
    active=app.state.tab,
    on_select=lambda i: app.set_state(lambda s: setattr(s, "tab", i)),
    key="navbar",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `items` | `list[str]` | `[]` | Rótulos dos itens, em ordem. |
| `active` | `int` | `0` | Índice do item ativo. |
| `on_select` | `handler → int` | — | Chamado com o índice do item tocado. **Obrigatório.** |

---

### Breadcrumb

Trilha de navegação com separador configurável. Itens não-finais são tocáveis
quando `on_select` é fornecido; o item final é sempre apresentacional.

```python
from tempestroid import Breadcrumb

Breadcrumb(
    items=["Início", "Produtos", "Detalhes"],
    separator="/",
    on_select=lambda i: app.navigate_to(i),
    key="bc",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `items` | `list[str]` | `[]` | Rótulos da raiz até a página atual. |
| `separator` | `str` | `"/"` | Caractere exibido entre itens. |
| `on_select` | `handler → int` | `None` | Chamado com o índice do item tocado (exceto o último). |

---

### Burger

Botão de menu hambúrguer — normalmente abre um `Drawer`.

```python
from tempestroid import AppBar, Burger

AppBar(
    title="App",
    leading=Burger(
        on_click=lambda: app.set_state(lambda s: setattr(s, "open", True)),
        key="burger",
    ),
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `on_click` | `handler` | — | Invocado ao tocar o botão. **Obrigatório.** |
| `glyph` | `str` | `"☰"` | Caractere do ícone exibido. |

---

### Drawer

Painel lateral controlado. Quando `open=False` colapsa para uma caixa vazia;
quando `open=True` exibe os filhos na largura configurada.

```python
from tempestroid import Burger, Column, Drawer, Row, Text

Row(
    children=[
        Drawer(
            open=app.state.open,
            width=260.0,
            children=[
                Text(content="Menu", key="menu-title"),
                # itens de navegação...
            ],
            key="drawer",
        ),
        main_content,
    ],
)
```

!!! warning "Posicionamento do Drawer"
    O `Drawer` usa o modelo flex: quando aberto ele ocupa espaço na linha/coluna
    pai (não flutua sobre o conteúdo). Use `Row` com `Drawer` + conteúdo para
    o padrão clássico de gaveta lateral.

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `open` | `bool` | `False` | Controla se o painel está expandido. |
| `children` | `list[Widget]` | `[]` | Widgets dentro do painel aberto. |
| `width` | `float` | `260.0` | Largura do painel em pixels lógicos. |

---

## Layout

### Scaffold

Estrutura de página: barra superior, corpo crescente e barra inferior opcional.
É o ponto de partida de quase toda tela.

```python
from tempestroid import AppBar, NavBar, Scaffold

Scaffold(
    app_bar=AppBar(title="Home", key="ab"),
    body=my_content,
    bottom_bar=NavBar(items=["A", "B", "C"], active=0, on_select=on_tab, key="nb"),
    scroll=True,
    key="scaffold",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `app_bar` | `Widget \| None` | `None` | Widget da barra superior (normalmente `AppBar`). |
| `body` | `Widget \| None` | `None` | Conteúdo principal (ocupa todo o espaço restante). |
| `bottom_bar` | `Widget \| None` | `None` | Barra inferior (ex.: `NavBar` ou `Footer`). |
| `scroll` | `bool` | `False` | Se `True`, envolve o corpo num `ScrollView`. |

---

### Sidebar

Coluna lateral de largura fixa para navegação ou conteúdo secundário.

```python
from tempestroid import Button, Row, Sidebar, TapEvent

Row(
    children=[
        Sidebar(
            width=240.0,
            children=[
                Button(label="Painel", on_click=on_dash, key="dash"),
                Button(label="Configurações", on_click=on_cfg, key="cfg"),
            ],
            key="sidebar",
        ),
        main_content,
    ],
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `children` | `list[Widget]` | `[]` | Widgets empilhados de cima para baixo na barra lateral. |
| `width` | `float` | `240.0` | Largura fixa em pixels lógicos. |

---

### Grid

Grade de colunas fixas: preenche as células da esquerda para a direita e de
cima para baixo. Células da última linha incompleta são preenchidas com espaço
vazio para manter o alinhamento.

```python
from tempestroid import Card, Grid, Text

Grid(
    columns=3,
    gap=12.0,
    children=[
        Card(children=[Text(content=f"Item {i}", key=f"t{i}")], key=f"c{i}")
        for i in range(9)
    ],
    key="grid",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `children` | `list[Widget]` | `[]` | Células preenchidas da esquerda para a direita. |
| `columns` | `int` | `2` | Número de colunas por linha (mínimo 1). |
| `gap` | `float` | `8.0` | Espaçamento entre células, horizontal e vertical. |

---

## Seleção e entrada

### SegmentedControl

Grupo de segmentos em pílula para escolha única compacta.

```python
from tempestroid import SegmentedControl

SegmentedControl(
    options=["Dia", "Semana", "Mês"],
    selected=app.state.period,
    on_select=lambda i: app.set_state(lambda s: setattr(s, "period", i)),
    key="period-ctrl",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `options` | `list[str]` | `[]` | Rótulos dos segmentos, em ordem. |
| `selected` | `int` | `0` | Índice do segmento ativo. |
| `on_select` | `handler → int` | — | Chamado com o índice do segmento tocado. **Obrigatório.** |

---

### RadioGroup

Lista vertical de opções com marcador de seleção (◉ / ○).

```python
from tempestroid import RadioGroup

RadioGroup(
    options=["Cartão", "Boleto", "Pix"],
    selected=app.state.payment,
    on_select=lambda i: app.set_state(lambda s: setattr(s, "payment", i)),
    key="payment",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `options` | `list[str]` | `[]` | Rótulos das opções, em ordem. |
| `selected` | `int` | `0` | Índice da opção escolhida. |
| `on_select` | `handler → int` | — | Chamado com o índice da opção tocada. **Obrigatório.** |

---

### Chip

Pílula pequena e arredondada; pode ser selecionável ou puramente visual.
Quando `on_click` é `None`, o chip é apresentacional.

```python
from tempestroid import Chip, Row

Row(
    children=[
        Chip(
            label="Python",
            selected=True,
            on_click=lambda: app.toggle_tag("Python"),
            key="chip-py",
        ),
        Chip(label="Kotlin", key="chip-kt"),
    ],
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `label` | `str` | `""` | Texto exibido no chip. |
| `selected` | `bool` | `False` | Se `True`, aplica cor de destaque (útil com `on_click`). |
| `on_click` | `handler` | `None` | Chamado ao tocar; quando `None` o chip é estático. |

---

### Rating

Fileira de estrelas mostrando (e opcionalmente ajustando) uma avaliação.
Quando `on_rate` é `None`, exibe a avaliação sem interação.

```python
from tempestroid import Rating

Rating(
    value=app.state.stars,
    max_stars=5,
    on_rate=lambda v: app.set_state(lambda s: setattr(s, "stars", v)),
    key="rating",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `value` | `int` | `0` | Número de estrelas preenchidas. |
| `max_stars` | `int` | `5` | Total de estrelas exibidas. |
| `on_rate` | `handler → int` | `None` | Chamado com o valor 1-based da estrela tocada. |

---

### Stepper

Controle numérico com botões − e + e valor central. Respeita limites opcionais.

```python
from tempestroid import Stepper

Stepper(
    value=app.state.qty,
    step=1,
    min_value=1,
    max_value=99,
    on_change=lambda v: app.set_state(lambda s: setattr(s, "qty", v)),
    key="qty-stepper",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `value` | `int` | `0` | Valor atual. |
| `step` | `int` | `1` | Incremento/decremento por toque. |
| `min_value` | `int \| None` | `None` | Limite inferior (sem limite quando `None`). |
| `max_value` | `int \| None` | `None` | Limite superior (sem limite quando `None`). |
| `on_change` | `handler → int` | — | Chamado com o novo valor (já limitado). **Obrigatório.** |

---

### SearchBar

Campo de busca controlado com botão de limpar opcional. O botão de limpar
aparece apenas quando `on_clear` é fornecido e o campo não está vazio.

```python
from tempestroid import SearchBar, TextChangeEvent

async def on_change(e: TextChangeEvent) -> None:
    app.set_state(lambda s: setattr(s, "query", e.value))

SearchBar(
    value=app.state.query,
    placeholder="Buscar produtos...",
    on_change=on_change,
    on_clear=lambda: app.set_state(lambda s: setattr(s, "query", "")),
    key="search",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `value` | `str` | `""` | Texto atual do campo (controlado). |
| `placeholder` | `str` | `"Search"` | Dica exibida quando o campo está vazio. |
| `on_change` | `handler → TextChangeEvent` | — | Chamado a cada edição com o evento validado. **Obrigatório.** |
| `on_clear` | `handler` | `None` | Chamado ao tocar o botão ✕; o botão só aparece quando este handler é fornecido e o campo tem texto. |

---

## Feedback

### Banner

Barra de status inline com mensagem e ação opcional ao final.
Tom aceito: `"info"`, `"success"`, `"warning"`, `"error"`.

```python
from tempestroid import Banner, Button, TapEvent

async def on_dismiss(e: TapEvent) -> None:
    app.set_state(lambda s: setattr(s, "show_banner", False))

Banner(
    message="Conexão restaurada.",
    tone="success",
    action=Button(label="OK", on_click=on_dismiss, key="ok"),
    key="banner",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `message` | `str` | `""` | Texto da mensagem. |
| `tone` | `str` | `"info"` | Cor de fundo: `"info"` / `"success"` / `"warning"` / `"error"`. |
| `action` | `Widget \| None` | `None` | Widget de ação ao final (ex.: `Button` "Fechar"). |

---

### EmptyState

Tela de estado vazio centralizada: glifo, título, subtítulo e ação opcionais.

```python
from tempestroid import Button, EmptyState, TapEvent

EmptyState(
    glyph="📭",
    title="Sem resultados",
    subtitle="Tente refinar a busca.",
    action=Button(label="Limpar filtros", on_click=on_clear, key="clear"),
    key="empty",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `title` | `str` | `""` | Mensagem principal. |
| `subtitle` | `str \| None` | `None` | Linha secundária. |
| `glyph` | `str` | `"○"` | Caractere grande exibido acima do título. |
| `action` | `Widget \| None` | `None` | Widget de call-to-action (ex.: `Button`). |

---

### Badge

Pílula de status inline para contagem ou rótulo curto.

```python
from tempestroid import Badge, Row, Text

Row(
    children=[
        Text(content="Notificações", key="lbl"),
        Badge(label="3", tone="error", key="badge"),
    ],
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `label` | `str` | `""` | Texto do badge (ex.: `"3"`, `"NOVO"`). |
| `tone` | `str` | `"error"` | Cor de fundo: `"info"` / `"success"` / `"warning"` / `"error"`. |

---

### Accordion

Seção expansível controlada. O estado `open` vive no estado do app; tocar o
cabeçalho chama `on_toggle` para alternância.

```python
from tempestroid import Accordion, Text

Accordion(
    title="Detalhes técnicos",
    open=app.state.details_open,
    on_toggle=lambda: app.set_state(lambda s: setattr(s, "details_open", not s.details_open)),
    children=[
        Text(content="Versão: 1.0.0", key="ver"),
        Text(content="Plataforma: Android 15", key="plat"),
    ],
    key="acc",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `title` | `str` | `""` | Texto do cabeçalho. |
| `open` | `bool` | `False` | Controla se o corpo está expandido. |
| `children` | `list[Widget]` | `[]` | Widgets revelados quando aberto. |
| `on_toggle` | `handler` | — | Chamado ao tocar o cabeçalho. **Obrigatório.** |

---

## Data e hora

### Calendar

Grade mensal de dias selecionáveis. O mês é fornecido como `"AAAA-MM"`;
o dia selecionado como `"AAAA-MM-DD"`. Omitir `month` exibe o mês atual.

```python
from tempestroid import Calendar

Calendar(
    month="2026-06",
    selected=app.state.date,
    on_select=lambda d: app.set_state(lambda s: setattr(s, "date", d)),
    key="cal",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `month` | `str` | `""` | Mês exibido no formato `"AAAA-MM"` (vazio = mês atual). |
| `selected` | `str` | `""` | Dia selecionado em `"AAAA-MM-DD"` (vazio = sem seleção). |
| `on_select` | `handler → str` | — | Chamado com a data ISO do dia tocado. **Obrigatório.** |

---

### Clock

Relógio digital que exibe uma string de tempo pré-formatada. O app formata e
avança o relógio pelo estado (veja o exemplo `stopwatch`).

```python
from tempestroid import Clock

Clock(
    time=app.state.time_str,   # ex.: "12:34:56"
    label="UTC-3",
    key="clock",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `time` | `str` | `""` | String de tempo a exibir (ex.: `"12:34:56"`). |
| `label` | `str \| None` | `None` | Legenda opcional em tom reduzido abaixo do tempo. |

---

## Tabelas

### Table

Tabela estática de linhas tipadas. Cada linha é um `TableRow` com células
`TableCell`. Cabeçalhos opcionais são renderizados em negrito na primeira
linha.

```python
from tempestroid import Table, TableCell, TableRow

Table(
    headers=["Nome", "Função", "Status"],
    rows=[
        TableRow(cells=[
            TableCell(content="Alice"),
            TableCell(content="Engenheira"),
            TableCell(content="Ativo"),
        ]),
        TableRow(cells=[
            TableCell(content="Bob"),
            TableCell(content="Designer"),
            TableCell(content="Férias"),
        ]),
    ],
    key="team-table",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `rows` | `list[TableRow]` | `[]` | Linhas do corpo, cada uma com células `TableCell`. |
| `headers` | `list[str]` | `[]` | Rótulos da linha de cabeçalho (negrito). |

---

### DataTable

Tabela de conveniência baseada em matriz de strings. Informe `columns` e
`rows` como listas de strings; use `sortable=True` para adicionar o glifo ▾
nos cabeçalhos (a ordenação efetiva é feita pelo app reordenando `rows`).

```python
from tempestroid import DataTable

DataTable(
    columns=["Produto", "Preço", "Estoque"],
    rows=[
        ["Notebook Pro", "R$ 4.999", "12"],
        ["Mouse Ergonômico", "R$ 299", "87"],
    ],
    sortable=True,
    key="products-dt",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `columns` | `list[str]` | `[]` | Rótulos das colunas. |
| `rows` | `list[list[str]]` | `[]` | Linhas do corpo como matriz de strings. |
| `sortable` | `bool` | `False` | Se `True`, adiciona ▾ nos cabeçalhos para indicar ordenação. |

---

## Formulários brasileiros

Estes componentes baixam para as primitivas `Input` / `MaskedInput` envolvidas
num `Column` rotulado (rótulo opcional acima, o campo, e uma linha de erro
vermelha opcional abaixo). Cada um expõe um `on_change` que recebe o **novo
valor em string** — você nunca toca no objeto de evento. Combine cada campo com
a função de validação correspondente em `tempestroid.validators` para validação
por campo dentro de um `Form`: passe o componente como `child` de um `FormField`
com a lista `validators` apropriada, e o `Form` agrega os erros e bloqueia o
submit inválido antes de qualquer patch.

!!! info "Validadores prontos"
    `tempestroid.validators` traz `validate_cpf`, `validate_cnpj`,
    `validate_email` e `validate_phone` — funções puras
    `Callable[[Any], str | None]` que devolvem uma mensagem PT-BR quando o valor
    é inválido ou `None` quando válido. Elas removem máscara (pontos, traços,
    parênteses) antes de validar, então `"123.456.789-09"` valida igual aos
    dígitos puros.

### EmailInput

Campo de e-mail rotulado com teclado de e-mail, ícone `mail` e `pattern`
embutido (`EMAIL_PATTERN`).

```python
from tempestroid import EmailInput, FormField, validate_email

FormField(
    name="email",
    validators=[validate_email],
    child=EmailInput(
        value=app.state.email,
        on_change=lambda v: app.set_state(lambda s: setattr(s, "email", v)),
        key="email",
    ),
    key="email-field",
)
```

Teclado `EMAIL`; valida com `validate_email`.

### PasswordInput

Campo de senha seguro (oculto, com o botão de olho embutido) e ícone `lock`.

```python
from tempestroid import FormField, PasswordInput

FormField(
    name="password",
    child=PasswordInput(
        value=app.state.password,
        on_change=lambda v: app.set_state(lambda s: setattr(s, "password", v)),
        key="password",
    ),
    key="password-field",
)
```

Campo seguro (`secure=True`); sem máscara — combine com seu próprio validador
de força, se quiser.

### PhoneInput

Telefone brasileiro mascarado `(99) 99999-9999`.

```python
from tempestroid import FormField, PhoneInput, validate_phone

FormField(
    name="phone",
    validators=[validate_phone],
    child=PhoneInput(
        value=app.state.phone,
        on_change=lambda v: app.set_state(lambda s: setattr(s, "phone", v)),
        key="phone",
    ),
    key="phone-field",
)
```

Máscara `(99) 99999-9999`, teclado `PHONE`; valida com `validate_phone`
(aceita 10 ou 11 dígitos).

### CPFInput

Campo de CPF mascarado `999.999.999-99`.

```python
from tempestroid import CPFInput, FormField, validate_cpf

FormField(
    name="cpf",
    validators=[validate_cpf],
    child=CPFInput(
        value=app.state.cpf,
        on_change=lambda v: app.set_state(lambda s: setattr(s, "cpf", v)),
        key="cpf",
    ),
    key="cpf-field",
)
```

Máscara `999.999.999-99`, teclado `NUMBER`; valida com `validate_cpf`
(11 dígitos + dígitos verificadores).

### CNPJInput

Campo de CNPJ mascarado `99.999.999/9999-99`.

```python
from tempestroid import CNPJInput, FormField, validate_cnpj

FormField(
    name="cnpj",
    validators=[validate_cnpj],
    child=CNPJInput(
        value=app.state.cnpj,
        on_change=lambda v: app.set_state(lambda s: setattr(s, "cnpj", v)),
        key="cnpj",
    ),
    key="cnpj-field",
)
```

Máscara `99.999.999/9999-99`, teclado `NUMBER`; valida com `validate_cnpj`
(14 dígitos + dígitos verificadores).

### AddressInput

Bloco de endereço brasileiro agrupado: CEP (mascarado `99999-999`), rua, número,
complemento, bairro, cidade e UF. Um único `on_change(field_name, new_value)` é
chamado para o campo alterado, onde `field_name` é `"cep"`, `"street"`,
`"number"`, `"complement"`, `"neighborhood"`, `"city"` ou `"state"`.

```python
from tempestroid import AddressInput

AddressInput(
    cep=app.state.cep,
    street=app.state.street,
    city=app.state.city,
    state=app.state.uf,
    on_change=lambda field, value: app.set_state(
        lambda s: setattr(s, field, value)
    ),
    key="address",
)
```

CEP mascarado `99999-999` (teclado `NUMBER`); os demais campos são `Input`
livres. Sem validador embutido — valide cada campo no app conforme necessário.

---

## Entrada de mídia

Estes componentes baixam para as primitivas `FilePicker` e `Image`. Cada um
expõe um `on_pick` que recebe a **URI** do arquivo escolhido (de
`FileSelectEvent.uri`) — você nunca toca no objeto de evento.

### ImagePicker

Seletor de imagem com prévia inline da imagem escolhida (um `FilePicker` mais um
`Image` de prévia quando há URI).

```python
from tempestroid import ImagePicker

ImagePicker(
    value=app.state.image_uri,
    label="Foto do produto",
    on_pick=lambda uri: app.set_state(lambda s: setattr(s, "image_uri", uri)),
    key="image-picker",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `value` | `str` | `""` | URI da imagem escolhida (vazio = sem prévia). |
| `label` | `str` | `""` | Título opcional acima do seletor. |
| `on_pick` | `handler → str` | — | Chamado com a URI escolhida. **Obrigatório.** |

### DocumentPicker

Seletor de documento rotulado (apenas o `FilePicker`, sem prévia).

```python
from tempestroid import DocumentPicker

DocumentPicker(
    value=app.state.doc_uri,
    label="Comprovante",
    on_pick=lambda uri: app.set_state(lambda s: setattr(s, "doc_uri", uri)),
    key="doc-picker",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `value` | `str` | `""` | URI do documento escolhido. |
| `label` | `str` | `""` | Título opcional acima do seletor. |
| `on_pick` | `handler → str` | — | Chamado com a URI escolhida. **Obrigatório.** |

### ImagePicture

Foto de perfil circular: a foto escolhida recortada em círculo (ou um ícone
`user` como placeholder) sobre um botão de troca. Diferente de `Avatar`, que
mostra iniciais.

```python
from tempestroid import ImagePicture

ImagePicture(
    src=app.state.photo_uri,
    size=120.0,
    on_pick=lambda uri: app.set_state(lambda s: setattr(s, "photo_uri", uri)),
    key="profile-photo",
)
```

| Prop | Tipo | Padrão | Descrição |
|---|---|---|---|
| `src` | `str` | `""` | URI da foto atual (vazio mostra o placeholder). |
| `size` | `float` | `96.0` | Diâmetro do círculo em pixels lógicos. |
| `on_pick` | `handler → str` | — | Chamado com a URI escolhida. **Obrigatório.** |

---

## Recapitulando

- Componentes herdam de `Component` e implementam `render()`, que devolve uma
  subárvore de primitivas — sem código extra nos renderizadores.
- Importe sempre de `from tempestroid import ...` — nunca de submódulos.
- `Scaffold` é o ponto de partida de uma tela: junte `AppBar` + conteúdo +
  `NavBar` com um único widget.
- Componentes **controlados** (`Drawer`, `Accordion`, `NavBar`, `Calendar`…)
  expõem `open`/`active`/`selected` como props — o estado vive no app.
- Para tabelas simples use `DataTable`; para células com estilo próprio use
  `Table` + `TableRow` + `TableCell`.
- `Badge`, `Banner` e `EmptyState` usam os tons `"info"`, `"success"`,
  `"warning"` e `"error"` para colorização semântica.

## Próximos passos

➡️ Veja como combinar esses componentes em apps completos na
**[Galeria de exemplos](../exemplos.md)**, ou explore os
**[Estilos](../estilos.md)** para personalizar a aparência de qualquer
componente via a prop `style`.

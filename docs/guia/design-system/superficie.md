# Superfície e layout

O [kit de ação e entrada](kit.md) deu ergonomia aos controles. Agora falta a
**moldura**: os cartões, as superfícies e os espaçadores que organizam a tela. O
tempestroid traz essa camada com a **mesma** API de variantes que você já
conhece — só que aqui o eixo é a *elevação* Material 3, não a ênfase do botão.

![A galeria H3 no simulador Qt](../../assets/examples/h3gallery.png){ width=300 }

*O exemplo `examples/h3gallery` no simulador Qt: as três variantes de `Card`, um
painel tingido com `ListTile` + `Divider`, e uma `Surface` crua.*

!!! info "Onde os nomes moram"
    Tudo desta página é importado de **`tempestroid`**: os widgets (`Card`,
    `Surface`, `HStack`, `VStack`, `Spacer`, `Divider`, `ListTile`), o enum
    `CardVariant` e o `Theme`/`Color`. `tempest_core` é só o motor por baixo —
    você não importa ele.

## `Card` e as três variantes Material 3

Um `Card` agrupa conteúdo numa superfície com cantos arredondados e *padding*
interno. A prop `variant` (enum `CardVariant`) escolhe o tratamento M3 — e, como
no `Button`, o motor resolve o `Style` a partir do `theme`, sem você fixar cor
nenhuma:

| `CardVariant` | Tratamento |
|---|---|
| `ELEVATED` | superfície + **sombra** (a elevação vira um `Shadow`) — o padrão |
| `FILLED` | preenchimento tonal (`surface_variant`), sem sombra |
| `OUTLINED` | borda fina na cor `outline`, fundo da superfície |

```python
from tempestroid import Card, CardVariant, Text, Widget


def cards(theme) -> Widget:  # theme: Theme
    return Card(
        variant=CardVariant.ELEVATED,
        theme=theme,
        children=[
            Text(content="Título"),
            Text(content="Conteúdo do cartão"),
        ],
    )
```

!!! tip "Os passos de espaçamento vêm do tema"
    `Card` carrega `padding_step` / `radius_step` / `gap_step` (padrão `"md"` /
    `"md"` / `"sm"`) — passos da escala 4dp do tema, não pixels soltos. Troque
    para `"sm"` ou `"lg"` e o cartão respira de acordo com o resto do app.

### Tingindo um cartão com `color_scheme`

Um `Card` aceita `color_scheme` para tingir a superfície num
[papel de cor](tokens.md#os-papeis-de-cor-color-schemes) (o padrão é `"neutral"`).
Útil para destacar um painel sem sair do tema:

```python
from tempestroid import Card, CardVariant, Text, Widget


def painel(theme) -> Widget:  # theme: Theme
    return Card(
        variant=CardVariant.ELEVATED,
        color_scheme="primary",  # superfície tingida no acento
        theme=theme,
        children=[Text(content="Painel em destaque")],
    )
```

## `Surface` — a primitiva crua

`Card` é uma conveniência sobre `Surface`: a `Surface` aplica a **mesma**
resolução de variante (`ELEVATED`/`FILLED`/`OUTLINED` + `color_scheme` +
`radius_step`), mas **sem o padding interno** e segurando **um único** filho
(`child`, não `children`). Use quando você quer controlar o espaçamento por conta
própria:

```python
from tempestroid import CardVariant, Surface, Text, Widget


def superficie(theme) -> Widget:  # theme: Theme
    return Surface(
        variant=CardVariant.FILLED,
        theme=theme,
        child=Text(content="Superfície preenchida, sem padding interno"),
    )
```

!!! note "Card constrói sobre Surface"
    Pense no `Card` como `Surface` + padding + um `Column` dos seus `children`.
    Quando o padding embutido do `Card` não serve, desça para a `Surface` e monte
    o miolo você mesmo.

## Helpers de pilha: `HStack`, `VStack`, `Spacer`

Para o arranjo do dia a dia, os helpers de pilha são `Row`/`Column` com **gaps
nomeados do tema** em vez de um número de pixels. `HStack` empilha na horizontal,
`VStack` na vertical; o `gap` aceita um passo da escala de espaçamento
(`"xs"`/`"sm"`/`"md"`/`"lg"`/`"xl"`):

```python
from tempestroid import HStack, Spacer, Text, VStack, Widget


def barra(theme) -> Widget:  # theme: Theme
    return HStack(
        gap="md",
        theme=theme,
        children=[
            Text(content="Início"),
            Spacer(),  # empurra o que vem depois para a borda oposta
            Text(content="Configurações"),
        ],
    )


def coluna(theme) -> Widget:  # theme: Theme
    return VStack(
        gap="sm",
        theme=theme,
        children=[Text(content="Linha 1"), Text(content="Linha 2")],
    )
```

`Spacer` é o espaço elástico: ele cresce para preencher o eixo principal, então
um `Spacer` entre dois filhos de um `HStack` joga o segundo para a borda
contrária. Controle a proporção com `flex` (padrão `1.0`).

## `Divider` e `ListTile` temáticos

`Divider` é uma régua fina que segue a cor `outline` do tema (ou um
`color_scheme` que você passe); `ListTile` é a linha clássica de lista — `title`
+ `subtitle` + slots `leading`/`trailing` (que aceitam qualquer widget, como um
`Avatar`):

```python
from tempestroid import Avatar, Divider, ListTile, VStack, Widget


def lista(theme) -> Widget:  # theme: Theme
    return VStack(
        gap="xs",
        theme=theme,
        children=[
            ListTile(
                title="Maria Silva",
                subtitle="maria@example.com",
                leading=Avatar(label="MS"),
                theme=theme,
            ),
            Divider(theme=theme),
            ListTile(title="João Souza", subtitle="joao@example.com", theme=theme),
        ],
    )
```

## Exemplo completo: a galeria de superfície

`examples/h3gallery/app.py` junta tudo — as três variantes de `Card` lado a lado,
um cartão tingido com `ListTile` + `Divider` + uma linha de ação que usa `Spacer`
para empurrar o botão à borda, e uma `Surface` crua:

```bash
uv run python examples/h3gallery/app.py
# ou: make run APP=examples/h3gallery/app.py
```

No aparelho, o mesmo `view`/`make_state` carrega no host Compose: como `Card`,
`Surface`, `HStack`, `VStack`, `Divider` e `ListTile` são **componentes
compostos** (descem a primitivos via `Component.render`), eles renderizam pelos
seus filhos primitivos nos **dois renderizadores** — sem um ramo Kotlin dedicado.

!!! check "Divergência de superfície"
    A sombra do `ELEVATED` vira um `Shadow` resolvido pela elevação M3 e segue os
    dois tradutores `Style`. A geometria (raio, padding) sai dos passos do tema —
    idêntica nos dois renderizadores. Veja a
    [cobertura de renderizadores](../../referencia/cobertura.md) para a tabela
    completa.

## Recapitulando

- `Card` agrupa conteúdo numa superfície M3; `variant` escolhe `ELEVATED`
  (sombra) / `FILLED` (tonal) / `OUTLINED` (borda) e o motor resolve o `Style` do
  tema.
- `padding_step`/`radius_step`/`gap_step` vêm da **escala 4dp** do tema, não de
  pixels soltos; `color_scheme` tinge a superfície num papel de cor.
- `Surface` é a primitiva crua que o `Card` usa — mesma resolução de variante,
  **sem padding** e com **um** `child`.
- `HStack`/`VStack` são `Row`/`Column` com **gap nomeado do tema**; `Spacer`
  cresce para empurrar os vizinhos.
- `Divider`/`ListTile` seguem o tema (linha + a clássica linha de lista com
  `leading`/`trailing`).
- Tudo é **componente composto** → renderiza pelos primitivos nos dois
  renderizadores.

A seguir: [data display e feedback](feedback.md) — `Alert`/`Banner`, a família
`Badge`/`Chip`/`Tag`, `Stat`, `ProgressStepper` e os `color_scheme`s de status.

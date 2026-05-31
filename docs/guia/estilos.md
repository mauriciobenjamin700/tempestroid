# Estilos

O estilo é descrito por objetos de valor Pydantic **frozen**, diferenciados por
valor — é o que permite ao reconciliador fazer o *diff* do estilo de forma
barata. Toda divergência entre Qt e Compose fica confinada aos dois tradutores de
`Style`.

```python
from tempestroid import (
    AlignItems, Color, Column, Edge, FlexDirection, FontWeight, Style, Text,
)

Column(
    style=Style(
        direction=FlexDirection.COLUMN,
        align=AlignItems.CENTER,
        gap=16.0,
        padding=Edge.all(24.0),
        background=Color.from_hex("#101418"),
    ),
    children=[
        Text(
            content="Título",
            style=Style(
                color=Color.from_hex("#ffffff"),
                font_size=24.0,
                font_weight=FontWeight.BOLD,
            ),
            key="t",
        ),
    ],
)
```

## Campos do `Style`, por grupo

`Style` é um modelo único; abaixo os campos agrupados por intenção.

| Grupo | Campos |
|---|---|
| **Layout** | `direction`, `justify`, `align`, `align_self`, `grow`, `gap` |
| **Caixa** | `padding`, `margin`, `border`, `radius` |
| **Pintura** | `background`, `color`, `opacity`, `shadow` |
| **Tipografia** | `font_family`, `font_size`, `font_weight`, `font_style`, `text_align`, `text_decoration`, `letter_spacing`, `line_height`, `max_lines`, `text_overflow` |
| **Dimensão** | `width`, `height`, `min_width`, `max_width`, `min_height`, `max_height`, `aspect_ratio` |
| **Animação** | `transition` |

## Objetos de valor

| Tipo | Uso |
|---|---|
| `Color` | Cor; `Color.from_hex("#101418")`. |
| `Edge` | Insets; `Edge.all(24.0)` ou `Edge.symmetric(vertical=8.0, horizontal=16.0)`. |
| `Border` | Borda uniforme (largura, cor). |
| `SideBorder` | Borda por lado (`top`/`right`/`bottom`/`left`) — ex.: um divisor inferior. |
| `Corners` | Raios por canto para `Style.radius` (`top_left`/`top_right`/`bottom_right`/`bottom_left`) — ex.: folhas arredondadas só no topo. |
| `Shadow` | `box-shadow`/elevação (`color`/`blur`/`offset_x`/`offset_y`). Compose mapeia para elevação; Qt para `QGraphicsDropShadowEffect`. |
| `Gradient` + `GradientStop` | Gradiente linear usável onde um `background` `Color` é (QSS `qlineargradient` / Compose `Brush`). |
| `Transition` | Animação implícita (`duration_ms`/`curve`/`delay_ms`). |

```python
from tempestroid import (
    Color, Corners, Gradient, GradientDirection, GradientStop, Shadow, Style,
)

Style(
    background=Gradient(
        stops=[GradientStop(color=Color.from_hex("#3b82f6"), position=0.0),
               GradientStop(color=Color.from_hex("#9333ea"), position=1.0)],
        direction=GradientDirection.LEFT_RIGHT,
    ),
    radius=Corners(top_left=16.0, top_right=16.0),
    shadow=Shadow(color=Color.from_hex("#00000040"), blur=12.0, offset_y=4.0),
    opacity=0.95,
)
```

## Enums

| Enum | Valores |
|---|---|
| `FlexDirection` | `ROW`, `COLUMN`. |
| `JustifyContent` | `START`, `CENTER`, `END`, `SPACE_BETWEEN`, `SPACE_AROUND`, `SPACE_EVENLY`. |
| `AlignItems` | `START`, `CENTER`, `END`, `STRETCH`. |
| `TextAlign` | `LEFT`, `CENTER`, `RIGHT`, `JUSTIFY`. |
| `FontWeight` | `NORMAL`, `BOLD` (e pesos numéricos). |
| `FontStyle` | `NORMAL`, `ITALIC`. |
| `TextDecoration` | `NONE`, `UNDERLINE`, `LINE_THROUGH`. |
| `TextOverflow` | `CLIP`, `ELLIPSIS`. |
| `GradientDirection` | `TOP_BOTTOM`, `BOTTOM_TOP`, `LEFT_RIGHT`, `RIGHT_LEFT`. |
| `Curve` | `LINEAR`, `EASE_IN`, `EASE_OUT`, `EASE_IN_OUT` (easing de `Transition`). |
| `ImageFit` | `CONTAIN`, `COVER`, `FILL`, `NONE` (usado por `Image`). |
| `KeyboardType` | `TEXT`, `NUMBER`, `EMAIL`, `PHONE`, `URL`, `PASSWORD` (usado por `Input`). |

## Transições animadas

`Style.transition` aceita um objeto `Transition` que descreve uma animação
implícita — modelado em `transition` do CSS / nos *implicitly-animated widgets* do
Flutter: quando uma prop estilizada muda entre rebuilds, o renderizador interpola
até o novo valor (Compose mapeia para `animate*AsState`; no Qt a animação é
imperativa no renderizador).

```python
from tempestroid import Curve, Style, Transition

Style(
    background=Color.from_hex("#3b82f6"),
    transition=Transition(duration_ms=200, curve=Curve.EASE_IN_OUT, delay_ms=0),
)
```

| Campo | Tipo | Significado |
|---|---|---|
| `duration_ms` | `int` | Duração da animação em milissegundos. |
| `curve` | `Curve` | Curva de easing. |
| `delay_ms` | `int` | Atraso antes de iniciar, em milissegundos. |

## Como cada renderizador traduz

O mesmo `Style` alimenta os dois tradutores; a **suíte de conformidade** (fase D)
fixa ambos com *golden snapshots* para impedir divergência silenciosa.

- **Qt** (`Style → Qt`): *padding* vira QSS nos *leaves* e `contentsMargins` nos
  containers (sem dupla contagem); `margin` vira regra QSS de box-model;
  `justify`/`align` `START/CENTER/END` viram flags de alinhamento Qt, enquanto
  `SPACE_BETWEEN/AROUND/EVENLY` são realizados no renderizador com *spacers* de
  *stretch* e `STRETCH` é o preenchimento padrão do eixo cruzado; `grow` vira
  fator de *stretch*. `width`/`height`/`aspect_ratio` fixos viram
  `setFixedWidth`/`setFixedHeight`; `text_align`, `max_lines`, `text_overflow` e
  `line_height` são honrados por um `QLabel` customizado (layout de texto via
  `QTextLayout`).
- **Compose** (`to_compose(style)`): emite uma *spec* serializável que o host
  Kotlin transforma em `Modifier` / `Arrangement` / `Alignment`.

!!! note "Divergências conhecidas"
    Nem todo campo é honrado igualmente nos dois lados ainda. A suíte de
    conformidade documenta as divergências e falha se um tradutor passar a tratar
    (ou parar de tratar) um campo sem atualizar a tabela.

## Imutabilidade

`Style` e seus objetos de valor são frozen. Para "mudar" um estilo, construa um
novo objeto — é o que a `view` faz a cada rebuild, e o que permite o *diff* por
valor.

## Recapitulando

- `Style` é um modelo único, frozen, diferenciado por valor.
- Campos agrupados por intenção: layout, caixa, pintura, tipografia, dimensão,
  animação.
- Objetos de valor (`Color`, `Edge`, `Border`, `Shadow`, `Gradient`,
  `Transition`) montam os campos.
- Um mesmo `Style` alimenta Qt e Compose; divergências ficam documentadas pela
  suíte de conformidade.

## Próximos passos

➡️ Ligue interação com **[Eventos](eventos.md)**, ou veja os estilos aplicados em
apps completos na **[Galeria de exemplos](exemplos.md)**.

# Kit de ação e entrada

A [API de variantes](variantes.md) que você viu no `Button` é a **mesma** em
todo o kit estilizado: botões de ícone, a família de campos de texto, os
controles de seleção e os sliders. Cada um carrega `size` / `color_scheme` (a
família de campos adiciona `field_variant`) e resolve seu `Style` Material 3
contra o `theme` que você passa. Esta página percorre o kit.

![O kit H2 no simulador Qt, tema claro](../../assets/design-system/kit-light.png){ width=300 }
![O mesmo kit em dark mode](../../assets/design-system/kit-dark.png){ width=300 }

*O exemplo `examples/h2gallery` no simulador Qt: o mesmo código segue o tema do
app — claro à esquerda, escuro à direita.*

!!! info "Onde os nomes moram"
    Os widgets (`Input`, `Checkbox`, `Switch`, `Slider`, `RadioGroup`, os inputs
    BR) e `Theme`/`Color` vêm de **`tempestroid`**. Os enums `Size`/`Variant`/
    `FieldVariant` e o `IconButton` vêm de **`tempest_core`**. Cada bloco mostra
    o import certo.

## O padrão `theme=app.theme`

A regra de ouro do kit: **passe sempre o tema vivo do app para cada
componente.** Como cada componente resolve sua aparência contra o `theme` que
recebe, entregar `theme=app.theme` faz o kit inteiro seguir o tema do app —
inclusive o dark mode trocado em runtime via `App.set_theme`.

```python
from tempest_core import Variant

from tempestroid import App, Button, Widget


def view(app: App) -> Widget:
    return Button(
        label="Salvar",
        variant=Variant.SOLID,
        color_scheme="primary",
        theme=app.theme,  # ← segue o tema do app, dark mode incluído
    )
```

A vitrine `examples/h2gallery/app.py` faz exatamente isso em todo componente — é
por isso que a galeria escurece junto quando o app entra em dark mode.

## `IconButton`

Um botão só de ícone, com a mesma API de variantes do `Button` — só que quadrado
e circular, com o alvo de toque de 48dp. O padrão é `GHOST` (o tratamento de
menor ênfase, focado no ícone). O `label` carrega o **nome acessível**
(`contentDescription`), já que não há texto visível.

```python
from tempest_core import IconButton, Variant

from tempestroid import Color, Theme

theme = Theme.from_seed(Color.from_hex("#2563eb"))

adicionar = IconButton(
    icon="add",
    label="Adicionar item",  # nome acessível (a11y)
    variant=Variant.SOLID,
    color_scheme="primary",
    theme=theme,
    on_click=lambda: print("clicou"),
)
```

!!! tip "Ícones curados + apelidos Material"
    O `icon` aceita um valor curado de `Icons` (ou sua string) — `"add"`,
    `"search"`, `"eye"`, `"trash"`, `"settings"`… — ou um nome de ícone
    arbitrário da plataforma. O simulador Qt mapeia nomes Material comuns
    (`photo_camera`, `history`, `person`…) para os glifos curados; o aparelho
    usa os ícones nativos.

## A família de campos

Os campos de texto compartilham a prop `field_variant` (enum `FieldVariant`) —
um tratamento de baixa ênfase no repouso, em que o `color_scheme` só tinge o
foco/cursor/borda:

| `FieldVariant` | Repouso |
|---|---|
| `OUTLINE` | borda completa na cor `outline` (o padrão) |
| `FILLED` | preenchimento tonal (`surface_variant`), sem borda |
| `FLUSHED` | apenas uma régua inferior |

```python
from tempest_core import FieldVariant, Size

from tempestroid import Color, Column, Input, Style, Theme, Widget
from tempestroid.widgets import TextChangeEvent

theme = Theme.from_seed(Color.from_hex("#2563eb"))


def inputs(on_change) -> Widget:  # on_change: callable recebendo TextChangeEvent
    return Column(
        style=Style(gap=8.0),
        children=[
            Input(
                value="",
                placeholder=f"{fv.value} field",
                on_change=on_change,
                field_variant=fv,
                size=Size.MD,
                color_scheme="primary",
                theme=theme,
                key=fv.value,
            )
            for fv in FieldVariant  # OUTLINE, FILLED, FLUSHED
        ],
    )
```

Toda a família de campos compartilha essas props: `Input`, `TextArea`,
`Dropdown`, `Autocomplete`, `MaskedInput`, `PinInput`, `DatePicker`,
`TimePicker`, `FilePicker`.

!!! check "Estado inválido = papel `error`"
    Passe um `error="mensagem"` num `Input` e o campo resolve a borda/label no
    papel `error` em qualquer estado — o foco ainda engrossa a borda para 2px,
    de modo que o campo ativo leia como "focado e errado". O estado de foco tinge
    a borda no acento do `color_scheme`.

## Controles de seleção

`Checkbox`, `Switch` e `RadioGroup` carregam o acento via `color_scheme` (sem
`variant` — o Material 3 dá a cada controle de seleção uma única *affordance*):

```python
from tempest_core import Size

from tempestroid import (
    Checkbox, Color, Column, RadioGroup, Style, Switch, Theme, Widget,
)
from tempestroid.widgets import ToggleEvent

theme = Theme.from_seed(Color.from_hex("#2563eb"))


def selections(on_toggle, on_pick) -> Widget:
    return Column(
        style=Style(gap=8.0),
        children=[
            Checkbox(
                label="Aceito os termos",
                checked=True,
                on_change=on_toggle,   # recebe um ToggleEvent
                color_scheme="primary",
                theme=theme,
                key="chk",
            ),
            Switch(
                label="Notificações",
                checked=False,
                on_change=on_toggle,
                color_scheme="secondary",
                theme=theme,
                key="sw",
            ),
            RadioGroup(
                options=["Free", "Pro", "Team"],
                selected=0,
                on_select=on_pick,     # recebe o índice (int)
                color_scheme="primary",
                theme=theme,
                key="radio",
            ),
        ],
    )
```

## `Slider`

O slider pinta a faixa ativa + o thumb no acento do `color_scheme`; `size`
controla a espessura da faixa:

```python
from tempest_core import Size

from tempestroid import Color, Slider, Theme
from tempestroid.widgets import SlideEvent

theme = Theme.from_seed(Color.from_hex("#2563eb"))

volume = Slider(
    value=40.0,
    min_value=0.0,
    max_value=100.0,
    on_change=lambda e: print(e.value),  # SlideEvent
    size=Size.MD,
    color_scheme="primary",
    theme=theme,
)
```

!!! note "Divergência Qt × Compose documentada"
    Para seleção e slider, o `color_scheme` controla **só a cor** — a geometria
    é fixa pelo Material 3 (a forma do checkbox, o trilho do switch, o thumb do
    slider). Os dois renderizadores casam na cor resolvida; a *affordance*
    nativa de cada plataforma fica idêntica em forma. Veja a
    [cobertura de renderizadores](../../referencia/cobertura.md) para a tabela
    completa de divergências.

## Inputs brasileiros

Sobre a família de campos, o tempestroid oferece campos rotulados prontos para
formulários BR — cada um lança ao seu `on_change` o **valor string** já
mascarado/validado, sem você tocar no objeto de evento:

```python
from tempestroid import (
    CNPJInput, CPFInput, Column, EmailInput, PasswordInput, PhoneInput,
    Style, Theme, Widget,
)


def br_form(theme: Theme, on_change) -> Widget:  # on_change: callable(str)
    return Column(
        style=Style(gap=12.0),
        children=[
            EmailInput(value="", on_change=on_change, theme=theme, key="email"),
            PasswordInput(value="", on_change=on_change, theme=theme, key="pwd"),
            PhoneInput(value="", on_change=on_change, theme=theme, key="phone"),
            CPFInput(value="", on_change=on_change, theme=theme, key="cpf"),
            CNPJInput(value="", on_change=on_change, theme=theme, key="cnpj"),
        ],
    )
```

| Input BR | Faz |
|---|---|
| `EmailInput` | teclado de e-mail + ícone de correio + validação de padrão |
| `PasswordInput` | campo seguro com o toggle de "olho" embutido |
| `PhoneInput` | máscara brasileira `(99) 99999-9999` |
| `CPFInput` | máscara `999.999.999-99` |
| `CNPJInput` | máscara `99.999.999/9999-99` |

!!! tip "Validadores prontos"
    Combine cada campo BR com o validador correspondente em
    `tempestroid.validators` (`validate_email`, `validate_phone`, `validate_cpf`,
    `validate_cnpj`) para preencher o `error` e bloquear o submit inválido.

## Exemplo completo: a galeria do kit

`examples/h2gallery/app.py` desenha o kit inteiro — Buttons + IconButtons, os
três `field_variant`, checkbox, switch, radio e slider — todos passando
`theme=app.theme`, dentro de um `ScrollView` para caber no celular:

```bash
uv run python examples/h2gallery/app.py
# ou: make run APP=examples/h2gallery/app.py
```

No aparelho, o mesmo `view`/`make_state` é carregado pelo host Compose; cada
componente mapeia para sua *affordance* Material 3 (`OutlinedTextField` /
`TextField` preenchido / `Checkbox` / `Switch` / `Slider` / `FilledIconButton` …)
sobre as cores resolvidas.

## Recapitulando

- O kit estilizado compartilha a API de variantes: `size` / `color_scheme` em
  todos, `field_variant` na família de campos.
- **Passe `theme=app.theme` em cada componente** — é o que faz o kit seguir o
  tema do app, dark mode incluído.
- `IconButton` é botão só de ícone (padrão `GHOST`); o `label` é o nome
  acessível; o `icon` aceita os ícones curados ou um nome de plataforma.
- A família de campos resolve com `field_variant` (`OUTLINE`/`FILLED`/
  `FLUSHED`), é *focus-led*, e um `error` força o papel `error`.
- Seleção (`Checkbox`/`Switch`/`RadioGroup`) e `Slider` acentuam pelo
  `color_scheme` — **cor apenas**; a geometria M3 é fixa (divergência Qt×Compose
  documentada).
- Os inputs BR (`EmailInput`/`PasswordInput`/`PhoneInput`/`CPFInput`/`CNPJInput`)
  entregam o valor string mascarado/validado direto ao `on_change`.

Você completou o tour do design system: [tokens](tokens.md) →
[variantes](variantes.md) → kit. Para o catálogo completo de widgets e a
referência de API, veja a [visão geral de widgets](../widgets.md) e a
[API pública](../../referencia/api.md).

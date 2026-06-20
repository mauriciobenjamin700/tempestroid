# Tema e tokens

Até aqui você estilizou cada widget na mão: `Color.from_hex("#2563eb")` aqui, um
raio `12.0` ali, um padding `Edge.all(16.0)` acolá. Funciona, mas espalha
decisões de marca por todo o app — e na hora do **dark mode** você reescreve cada
cor. O **design system** do tempestroid resolve isso: um `Theme` carrega um
conjunto de **tokens Material 3** (cores, espaçamento, raio, tipografia,
elevação, movimento), e os componentes leem esses tokens em vez de valores
crus.

!!! info "De onde vêm os tokens"
    O motor de design (`Theme`, `TokenSet`, variantes) mora no pacote
    **`tempest-core`**, instalado junto com o tempestroid. Por isso alguns nomes
    desta página importam de `tempest_core` e outros de `tempestroid` — cada
    bloco de código mostra o caminho correto. `Theme` está disponível nos dois.

## Um `Theme` em uma linha

A porta de entrada é `Theme.from_seed(...)`: você dá **uma** cor de marca e
recebe uma paleta Material 3 completa — claro e escuro, com todos os papéis de
cor preenchidos e contraste garantido.

```python
from tempestroid import Color, Theme

theme = Theme.from_seed(Color.from_hex("#2563eb"))

# A semente vira um esquema tonal M3 inteiro:
print(theme.color("primary").to_hex())     # papel primário do esquema claro
print(theme.color("on_primary").to_hex())  # conteúdo legível sobre o primário
print(theme.space("md"))                    # 16.0 — gutter padrão (grade de 4dp)
print(theme.radius("lg"))                   # 16.0 — raio de cantos grande
print(theme.elevation(2))                   # 3.0 — elevação nível 2, em dp
```

!!! tip "Não tem cor de marca ainda?"
    Construa `Theme()` sem argumentos: você ganha o tema baseline do Material 3
    (o roxo de referência `#6750A4`). Tudo nesta página funciona igual.

## Os papéis de cor (color schemes)

O Material 3 não pinta com cores cruas — pinta com **papéis semânticos**. Cada
papel tem um par `on_*` que é o conteúdo legível desenhado sobre ele (gerado
para atingir contraste WCAG-AA). O tempestroid expõe cinco famílias de papéis,
que os componentes escolhem pelo `color_scheme`:

| `color_scheme` | Papel base | Conteúdo (`on_*`) | Uso típico |
|---|---|---|---|
| `"primary"` | `primary` | `on_primary` | ação principal, estado ativo |
| `"secondary"` | `secondary` | `on_secondary` | acento complementar |
| `"tertiary"` | `tertiary` | `on_tertiary` | acento contrastante |
| `"error"` | `error` | `on_error` | erro / ação destrutiva |
| `"neutral"` | `on_surface` | `surface` | tratamento neutro, baixa ênfase |

Além desses, o esquema completo carrega os papéis de superfície que o app usa
para o "chrome" da página — `surface` / `on_surface`, `background` /
`on_background`, `outline`, `surface_variant` e seus `on_*`. Leia qualquer um
deles pelo `ColorRole` ou pela string:

```python
from tempest_core import ColorRole

from tempestroid import Color, Theme

theme = Theme.from_seed(Color.from_hex("#2563eb"))

surface = theme.color(ColorRole.SURFACE)
on_surface = theme.color(ColorRole.ON_SURFACE)
outline = theme.color("outline")  # string também resolve
```

!!! note "Sementes de acento à mão"
    `from_seed` deriva secundário/terciário girando o tom da semente. Quer
    escolher cada acento? Passe `secondary_seed` / `tertiary_seed` /
    `error_seed`, todos `Color`.

## Claro e escuro com `ThemeMode`

O modo do tema decide qual esquema (claro ou escuro) os papéis resolvem. São
três opções:

=== "Forçar claro/escuro"

    ```python
    from tempest_core import ThemeMode

    from tempestroid import Color, Theme

    light = Theme.from_seed(Color.from_hex("#2563eb"), mode=ThemeMode.LIGHT)
    dark = Theme.from_seed(Color.from_hex("#2563eb"), mode=ThemeMode.DARK)

    print(light.color("background").to_hex())  # superfície clara
    print(dark.color("background").to_hex())    # superfície escura
    ```

=== "Seguir o sistema"

    ```python
    from tempest_core import ThemeMode

    from tempestroid import Color, Theme

    # SYSTEM resolve contra o dark mode da plataforma em tempo de build.
    theme = Theme.from_seed(Color.from_hex("#2563eb"), mode=ThemeMode.SYSTEM)
    print(theme.is_dark(platform_dark_mode=True))  # True quando o SO está escuro
    ```

`ThemeMode.SYSTEM` é o padrão: o app acompanha a configuração do aparelho. Para
trocar o tema em tempo de execução (um botão "dark mode" no app), use
`App.set_theme(...)` — veja o exemplo `examples/theming/app.py`.

## As escalas sistemáticas

Além das cores, o `TokenSet` traz escalas Material 3 nomeadas — você pede
`"md"` em vez de decorar `16.0`:

| Escala | Acesso | Passos |
|---|---|---|
| **Espaçamento** (grade 4dp) | `theme.space(name)` | `none` `xs` `sm` `md` `lg` `xl` `xxl` |
| **Forma** (raio) | `theme.radius(name)` | `none` `xs` `sm` `md` `lg` `xl` `full` |
| **Tipografia** | `theme.typography(role)` | `display_*` `headline_*` `title_*` `body_*` `label_*` |
| **Elevação** | `theme.elevation(level)` | níveis `0`–`5`, em dp |
| **Movimento** | `theme.tokens.motion` | durações + curvas de easing |

```python
from tempestroid import Color, Edge, Style, Theme

theme = Theme.from_seed(Color.from_hex("#2563eb"))

# Componha um Style a partir de tokens, não de números mágicos:
title = theme.typography("title_large")
card = Style(
    background=theme.color("surface_variant"),
    padding=Edge.all(theme.space("md")),
    radius=theme.radius("lg"),
    font_size=title.font_size,
    font_weight=title.font_weight,
)
```

!!! tip "`radius('full')` é a pílula"
    O passo `full` usa o sentinela `999.0`; o renderizador o interpreta como um
    formato totalmente arredondado (pílula/círculo) e faz o *clamp* ao tamanho
    real da caixa.

## Como um componente lê o tema

A parte importante: **um componente resolve seu `Style` contra o `theme` que
você entrega a ele.** Os componentes estilizados (`Button`, `Input`, `Checkbox`,
…) aceitam um parâmetro `theme`. Passe sempre o tema vivo do app e o componente
adapta a aparência — incluindo o dark mode — sem você reescrever uma cor:

```python
from tempest_core import Variant

from tempestroid import Button, Color, Theme

theme = Theme.from_seed(Color.from_hex("#2563eb"))

# O Button resolve background/color/raio a partir do tema dado:
salvar = Button(
    label="Salvar",
    variant=Variant.SOLID,
    color_scheme="primary",
    theme=theme,
)
print(salvar.style.background)  # já é a cor do papel "primary" do tema
```

Trocou o `theme` por um escuro? O mesmo `Button` resolve cores escuras. É por
isso que a galeria de exemplo (`examples/h2gallery/app.py`) passa
`theme=app.theme` para cada componente: o app inteiro segue um único tema.

!!! info "Tokens são aditivos — `Style` cru continua valendo"
    Nada disso quebra o que você já tem. Um `Style(background=Color.from_hex(...))`
    escrito à mão continua funcionando. O tema é uma fonte **alternativa e
    opcional** de valores. Você pode até carregar um `TokenRef` dentro de um
    `Style` (`Style(background=TokenRef.color("primary"))`) e deixar o tema
    resolvê-lo na hora do build via `theme.resolve_style(...)`.

## Recapitulando

- Um **`Theme`** carrega um **`TokenSet`** Material 3: esquemas de cor +
  escalas de espaçamento/forma/tipografia/elevação/movimento.
- **`Theme.from_seed("#rrggbb")`** transforma uma cor de marca em uma paleta M3
  completa (claro + escuro), com contraste garantido.
- As cores são **papéis semânticos** (`primary`/`secondary`/`tertiary`/`error`/
  `neutral` + seus `on_*` e os papéis de superfície), não cores cruas.
- **`ThemeMode`** (`LIGHT`/`DARK`/`SYSTEM`) decide qual esquema resolve; troque
  em runtime com `App.set_theme`.
- Peça escalas por nome — `theme.space("md")`, `theme.radius("lg")`,
  `theme.typography("title_large")` — em vez de números mágicos.
- **Um componente resolve contra o `theme` que você passa**: entregue
  `theme=app.theme` e tudo segue o tema do app, dark mode incluído.

A seguir: a [API de variantes ao estilo Chakra](variantes.md), onde
`variant`/`size`/`color_scheme` viram o jeito ergonômico de pedir um `Style`
resolvido pelo tema.

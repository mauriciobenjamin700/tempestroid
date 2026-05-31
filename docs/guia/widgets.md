# Widgets

Widgets são as primitivas declarativas da IR — uma árvore de modelos Pydantic que
o reconciliador faz o *diff* e os renderizadores aplicam. Importe sempre do nível
do pacote: `from tempestroid import Text, Button, ...`.

## Layout e conteúdo

| Widget | Papel | Props principais |
|---|---|---|
| `Text` | Rótulo de texto. | `content: str` |
| `Button` | Botão tocável. | `label: str`, `on_click` |
| `Column` | Empilha filhos na vertical. | `children: list[Widget]` |
| `Row` | Empilha filhos na horizontal. | `children: list[Widget]` |
| `Container` | Embrulha um único filho. | `child: Widget \| None` |
| `ScrollView` | Área rolável. | `horizontal: bool`, `child` |
| `SafeArea` | Afasta o filho das barras do sistema + notch. | `child`, `edges: list[SafeAreaEdge]` (padrão todos) |

```python
from tempestroid import Button, Column, Row, ScrollView, Style, Text

ScrollView(
    child=Column(
        style=Style(gap=8.0),
        children=[
            Text(content="Olá", key="hi"),
            Row(children=[
                Button(label="-", on_click=dec, key="dec"),
                Button(label="+", on_click=inc, key="inc"),
            ]),
        ],
    ),
)
```

## Inputs com valor

Os *leaves* que carregam um valor e emitem um evento de mudança tipado. Cada um
declara seu *handler* de mudança em `event_schemas`, então a fronteira valida o
*payload*.

| Widget | Valor / props | Handler | Evento |
|---|---|---|---|
| `Input` | `value`, `placeholder`, `secure`, `pattern`, `error`, `keyboard`, `max_length` | `on_change` | `TextChangeEvent` |
| `TextArea` | `value`, `placeholder`, `rows`, `max_length` | `on_change` | `TextChangeEvent` |
| `Checkbox` | `label`, `checked` | `on_change` | `ToggleEvent` |
| `Switch` | `label`, `checked` | `on_change` | `ToggleEvent` |
| `Slider` | `value`, `min_value`, `max_value`, `step` | `on_change` | `SlideEvent` |
| `DatePicker` | `value` (ISO `yyyy-mm-dd`), `label` | `on_change` | `DateChangeEvent` |
| `FilePicker` | `label`, `value` | `on_select` | `FileSelectEvent` |

```python
from tempestroid import Checkbox, DatePicker, Input, Slider, Switch, TextArea

Input(value=state.name, placeholder="Seu nome", on_change=on_name, key="name")
Input(value=state.pwd, secure=True, keyboard=KeyboardType.PASSWORD, on_change=on_pwd, key="pwd")
TextArea(value=state.bio, rows=4, max_length=280, on_change=on_bio, key="bio")
Switch(label="Notificações", checked=state.notify, on_change=on_notify, key="sw")
Slider(value=state.volume, min_value=0.0, max_value=100.0, step=1.0, on_change=on_vol, key="vol")
```

O *handler* recebe o evento tipado (ou pode ser declarado sem argumentos quando o
valor não importa):

```python
def on_name(event: TextChangeEvent) -> None:
    app.set_state(lambda s: setattr(s, "name", event.value))
```

### Validação de `Input`

`Input` carrega validação no próprio widget: `secure` mascara o texto, `pattern`
é uma regex que o renderizador pode usar para validar, `error` exibe uma mensagem
de erro, e `keyboard` (enum `KeyboardType`: `TEXT`, `NUMBER`, `EMAIL`, `PHONE`,
`URL`, `PASSWORD`) sugere o teclado no dispositivo.

## Mídia

| Widget | Papel | Props |
|---|---|---|
| `Image` | Imagem por URL/URI. | `src`, `fit` (`ImageFit`), `alt` |
| `Icon` | Ícone nomeado. | `name`, `size` |

`ImageFit` aceita `CONTAIN`, `COVER`, `FILL`, `NONE`.

## Indicadores

| Widget | Papel | Props |
|---|---|---|
| `ProgressBar` | Barra de progresso. | `value`, `indeterminate` |
| `Spinner` | Indicador de carregamento. | `size` |

## Chaves (`key`)

Dê um `key` estável a cada filho de uma lista. O reconciliador usa chaves para
emitir `Reorder` em vez de recriar widgets, e para casar nós entre rebuilds.

## Percorrendo a árvore

Todo widget expõe `child_nodes()` — use-o para caminhar a árvore de forma
genérica, sem alcançar o armazenamento interno de cada tipo. *Leaves* (`Text`,
`Image`, inputs) devolvem `[]`.

!!! warning "Suporte no dispositivo"
    O framework e o **simulador Qt** suportam o conjunto completo de widgets. O
    **renderizador do dispositivo (Compose)** acompanha o conjunto-base (`Text` /
    `Button` / `Column` / `Row` / `Container` + `on_click`); widgets mais novos
    podem cair para um *fallback* até o host Kotlin crescer os casos
    correspondentes (continuação do Trilho B). Veja o [roadmap](../roadmap.md).

## Contrato de eventos por widget

Cada widget declara o evento que cada *handler* emite via a classvar
`event_schemas` (ex.: `Button.event_schemas == {"on_click": TapEvent}`). Esse
contrato é publicado por [`introspect()`](../referencia/api.md#introspeccao) e
consumido pela fronteira do dispositivo. Veja [Eventos](eventos.md).

## Recapitulando

- Widgets são modelos Pydantic; importe sempre do nível do pacote
  (`from tempestroid import ...`).
- Layout: `Column`/`Row`/`Container`/`ScrollView`/`SafeArea`; conteúdo: `Text`,
  `Button`, mídia e indicadores.
- *Inputs* com valor emitem um evento de mudança tipado (`on_change` /
  `on_select`).
- Dê um `key` estável a filhos de listas — é o que deixa o *diff* reordenar em
  vez de recriar.

## Próximos passos

➡️ Deixe os widgets bonitos com **[Estilos](estilos.md)**, entenda os
**[Eventos](eventos.md)** tipados, ou veja apps completos na
**[Galeria de exemplos](exemplos.md)**.

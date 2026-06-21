# Eventos

Eventos são o contrato tipado da fronteira Python↔Kotlin. Quando o lado nativo
reporta um toque ou uma mudança de valor, o *payload* chega cru e é **validado
antes** de entrar em um *handler* — como o FastAPI valida um corpo de requisição.

## Tipos de evento

Todos herdam de `Event` (Pydantic frozen).

| Evento | Campos | Emitido por |
|---|---|---|
| `TapEvent` | `x: float \| None`, `y: float \| None` | `Button.on_click` |
| `TextChangeEvent` | `value: str`, `valid: bool` (contra o `pattern` do input) | `Input.on_change`, `TextArea.on_change` |
| `ToggleEvent` | `checked: bool` | `Checkbox.on_change`, `Switch.on_change` |
| `SlideEvent` | `value: float` | `Slider.on_change` |
| `DateChangeEvent` | `value: str` (ISO `yyyy-mm-dd`) | `DatePicker.on_change` |
| `FileSelectEvent` | `uri: str`, `name: str \| None` | `FilePicker.on_select` |

!!! info "Estes são os eventos de núcleo — há 31 no total"
    A tabela acima mostra os mais comuns. O Trilho E acrescentou muitos outros —
    navegação (`RouteChangeEvent`/`PageChangeEvent`), listas (`ScrollEvent`/
    `EndReachedEvent`/`RefreshEvent`), gestos (`PanEvent`/`ScaleEvent`/
    `SwipeEvent`/`ReorderEvent`/`LongPressEvent`/`DragEvent`), formulários
    (`SubmitEvent`/`ValidationEvent`/`RangeChangeEvent`/`TimeChangeEvent`/
    `SelectEvent`), overlays
    (`DismissEvent`/`MenuSelectEvent`) e plataforma (`SensorEvent`/
    `LifecycleEvent`/`ConnectivityEvent`/`DeepLinkEvent`/`QrScanEvent`/
    `ThemeChangeEvent`/`LocaleChangeEvent`). Liste o contrato completo com
    `tempest spec` ou veja a [referência de API](../referencia/api.md).

## O portão de validação: `parse_event`

`parse_event(event_type, raw)` transforma um *payload* cru (um *mapping*) em um
evento tipado, ou levanta `EventValidationError` com os erros estruturados por
campo (JSON-serializável):

```python
from tempestroid import EventValidationError, TextChangeEvent, parse_event

event = parse_event(TextChangeEvent, {"value": "olá"})   # -> TextChangeEvent(value="olá")

try:
    parse_event(TextChangeEvent, {})                      # falta o campo obrigatório
except EventValidationError as exc:
    print(exc.errors)   # [{"loc": ("value",), "type": "missing", ...}]
```

## Handlers

Um *handler* pode receber o evento tipado **ou** ser zero-argumento quando o valor
não importa. O runtime detecta a aridade e passa (ou não) o evento:

```python
# Recebe o evento tipado:
def on_name(event: TextChangeEvent) -> None:
    app.set_state(lambda s: setattr(s, "name", event.value))

# Zero-argumento (ignora o payload):
Button(label="+", on_click=lambda: app.set_state(...))
```

*Handlers* podem ser síncronos ou `async` — o runtime agenda corrotinas no loop
asyncio sem travar a UI.

## Aliases de handler tipados

Para anotar props de *handler*, o pacote exporta **`EventHandler`** — o wrapper
tipado genérico de prop de *handler* (ex.: `on_click`, `on_change`). Ele carrega
uma anotação `WithJsonSchema` para que widgets com *handler* não quebrem a geração
de esquema JSON.

## O contrato como dado

Cada widget declara o evento que cada *handler* emite via a classvar
`event_schemas`. A função [`introspect()`](../referencia/api.md#introspeccao)
publica tudo isso como JSON — esquemas de prop dos widgets, o evento de cada
*handler* e o esquema de *payload* de cada evento. É o que alimenta `tempest
spec` e a fronteira do dispositivo.

## Recapitulando

- Eventos são modelos Pydantic frozen (`TapEvent`, `TextChangeEvent`, …).
- `parse_event` é o portão que valida o *payload* cru antes do *handler* — como
  o FastAPI valida um corpo de requisição.
- *Handlers* podem receber o evento tipado ou ser zero-argumento; síncronos ou
  `async`.
- O contrato (`event_schemas` + `introspect()`) é publicado como JSON por
  `tempest spec`.

## Próximos passos

➡️ Inspecione o contrato com a **[CLI (`tempest spec`)](cli.md)**, ou veja
*handlers* reais na **[Galeria de exemplos](exemplos.md)**.

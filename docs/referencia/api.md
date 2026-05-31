# API pública

Tudo abaixo é importável do nível do pacote `tempestroid`. Importe sempre do nível
do pacote, nunca de submódulos.

## Estilo (`tempestroid.style`)

Objetos de valor Pydantic frozen, diferenciados por valor.

- **`Style`** — o modelo de estilo (layout, caixa, pintura, tipografia, dimensão,
  animação). Veja os campos agrupados no [guia de estilos](../guia/estilos.md).
- **`Color`** — `Color.from_hex("#101418")`.
- **`Edge`** — insets; `Edge.all(24.0)`.
- **`Border`** (uniforme) / **`SideBorder`** (por lado).
- **`Corners`** — raios por canto para `Style.radius`.
- **`Shadow`** — `box-shadow`/elevação.
- **`Gradient`** + **`GradientStop`** — gradiente linear.
- **`Transition`** — animação implícita (`duration_ms`, `curve`, `delay_ms`).
- Enums: **`FlexDirection`**, **`JustifyContent`**, **`AlignItems`**,
  **`TextAlign`**, **`FontWeight`**, **`FontStyle`**, **`TextDecoration`**,
  **`TextOverflow`**, **`GradientDirection`**, **`Curve`**, **`ImageFit`**,
  **`KeyboardType`**.

Veja o [guia de estilos](../guia/estilos.md).

## Widgets (`tempestroid.widgets`)

A IR declarativa — widgets como substantivos.

- Layout/conteúdo: **`Widget`** (base), **`Text`**, **`Button`**, **`Column`**,
  **`Row`**, **`Container`**, **`ScrollView`**.
- Inputs com valor: **`Input`** (texto), **`TextArea`** (multilinha),
  **`Checkbox`**, **`Switch`** (booleanos), **`Slider`** (float), **`DatePicker`**
  (data ISO), **`FilePicker`** (seleção de arquivo).
- Mídia: **`Image`**, **`Icon`**.
- Indicadores: **`ProgressBar`**, **`Spinner`**.
- **`EventHandler`** — wrapper tipado de prop de *handler*.

Veja o [guia de widgets](../guia/widgets.md).

## Eventos (`tempestroid.widgets`) — contrato de fronteira tipado

- **`Event`** (base), **`TapEvent`**, **`TextChangeEvent`**, **`ToggleEvent`**,
  **`SlideEvent`**, **`DateChangeEvent`**, **`FileSelectEvent`**.
- **`parse_event(event_type, raw)`** — portão de fronteira: valida um *payload*
  cru em um evento tipado ou levanta **`EventValidationError`** com os erros
  estruturados por campo. É o contrato Python↔Kotlin para a ponte do dispositivo.

Veja o [guia de eventos](../guia/eventos.md).

## Núcleo — IR + reconciliador (`tempestroid.core`)

- **`Node`**, **`Path`** — a IR rebaixada.
- Patches: **`Insert`**, **`Remove`**, **`Update`**, **`Reorder`**, **`Replace`**,
  e a união **`Patch`**.
- **`build(widget) -> Node`**, **`diff(old, new) -> list[Patch]`**.
- **`App[S]`** — container de estado agnóstico de renderizador: guarda o estado,
  constrói via `view(app)`, faz o *diff* e entrega *patches* a um callback
  `apply_patches`.

## Introspecção (`tempestroid.core`) {#introspeccao}

- **`introspect()`** — contrato JSON completo `{"widgets": {...}, "events":
  {...}}` (alimenta `tempest spec`).
- **`widget_catalog()`**, **`event_catalog()`**.

## Renderizador Qt (`tempestroid.renderers.qt`, precisa do extra `qt`)

- **`run_qt(state, view, *, title, size)`** — roda um app no simulador Qt.
- **`run_dev(app_path)`** — o cockpit do `tempest dev`.

## Lado do dispositivo

Compose, ponte JNI, dev server e capacidades nativas — veja a página
[Lado do dispositivo (ponte)](dispositivo.md).

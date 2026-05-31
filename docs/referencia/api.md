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
- **`Component`** (base) — widget composto que se reduz a uma árvore de
  primitivos via `render()`; o reconciliador o expande antes do *diff*.
- Inputs com valor: **`Input`** (texto), **`TextArea`** (multilinha),
  **`Checkbox`**, **`Switch`** (booleanos), **`Slider`** (float), **`DatePicker`**
  (data ISO), **`FilePicker`** (seleção de arquivo).
- Mídia: **`Image`**, **`Icon`**.
- Indicadores: **`ProgressBar`**, **`Spinner`**.
- **`EventHandler`** — wrapper tipado de prop de *handler*.

Veja o [guia de widgets](../guia/widgets.md).

## Componentes (`tempestroid.components`)

Blocos de construção reutilizáveis — cada um um **`Component`** que se reduz a
widgets primitivos, então funcionam nos dois renderizadores (Qt e Compose) sem
mudança alguma de renderizador e são prontos para o dispositivo. Todo componente
aceita um `style` opcional mesclado sobre o padrão via **`merge_style`**.

- **`AppBar`** — barra superior: `leading` opcional, `title` e `actions` à direita.
- **`Header`** / **`Footer`** — faixa de cabeçalho (título + subtítulo opcional) e
  barra inferior centralizada com `children` arbitrários.
- **`Sidebar`** — coluna lateral de largura fixa (`width`) com `children`.
- **`Scaffold`** — moldura de página empilhando `app_bar`, um `body` que cresce e
  um `bottom_bar` opcional (`scroll=True` embrulha o corpo num `ScrollView`).
- **`NavBar`** — barra de navegação/abas selecionável: rótulos `items`, índice
  `active` e *callback* `on_select(index)` (generaliza o exemplo `tabs`).
- **`Burger`** / **`Drawer`** — botão de menu (☰, `on_click`) e painel lateral
  controlado (`open` vive no estado do app; alterne pelo burger).
- **`Calendar`** — grade do mês com dias selecionáveis: `month` (`"AAAA-MM"`),
  `selected` (`"AAAA-MM-DD"`) e `on_select(data_iso)`.
- **`Clock`** — relógio digital que renderiza um `time` já formatado (o app
  dirige o tick pelo estado, como o `stopwatch`).
- **`Card`** — superfície elevada (sombra + raio) agrupando `children`.
- **`ListTile`** — linha de lista: `leading` / `trailing` em volta de `title` +
  `subtitle` opcional.
- **`Avatar`** — emblema redondo de `initials`; **`Divider`** — linha fina.

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

# Widgets

Widgets são as primitivas declarativas da IR — uma árvore de modelos Pydantic que
o reconciliador faz o *diff* e os renderizadores aplicam. Importe sempre do nível
do pacote: `from tempestroid import Text, Button, ...`.

O framework exporta **~100 widgets**, todos suportados pelos **dois
renderizadores** (simulador Qt no desktop + Compose no dispositivo). Este guia é o
índice; cada família tem sua própria página tutorial com exemplos completos e a
tabela de props de cada widget.

## Catálogo por família

| Família | O que cobre |
|---|---|
| [Texto, ação e indicadores](widgets/basics.md) | `Text` / `Button` / `ProgressBar` / `Spinner` |
| [Layout](widgets/layout.md) | `Column` / `Row` / `Container` / `Stack` / `Wrap` / `ScrollView` / `SafeArea` / `AspectRatio` / `PageView` / `KeyboardAvoidingView` |
| [Inputs com valor](widgets/inputs.md) | `Input` / `TextArea` / `Checkbox` / `Switch` / `Slider` / `RangeSlider` / `Dropdown` / `DatePicker` / `TimePicker` / `FilePicker` / `PinInput` / `MaskedInput` / `Autocomplete` / `Form` / `FormField` |
| [Listas virtualizadas](widgets/lists.md) | `LazyColumn` / `LazyRow` / `LazyGrid` / `SectionList` / `RefreshControl` |
| [Navegação](widgets/navigation.md) | `Navigator` / `TabView` / `TabBar` / `RouteDrawer` |
| [Overlays e feedback](widgets/overlays.md) | `Dialog` / `BottomSheet` / `Menu` / `Popover` / `Toast` / `Tooltip` / `ActionSheet` |
| [Animação](widgets/animation.md) | `Animated` / `AnimatedList` / `Hero` / `Shimmer` / `Skeleton` |
| [Gestos](widgets/gestures.md) | `GestureDetector` / `PanHandler` / `ScaleHandler` / `DoubleTapHandler` / `Draggable` / `DragTarget` / `Dismissible` / `ReorderableList` / `InteractiveViewer` |
| [Mídia e gráficos](widgets/media.md) | `Image` / `Icon` / `Canvas` / `Svg` / `VideoPlayer` / `WebView` / `Blur` / `BackdropFilter` / `ClipPath` / `CameraPreview` / `QrScanner` / `MapView` |
| [Componentes compostos](widgets/components.md) | `Card` / `ListTile` / `Scaffold` / `AppBar` / `NavBar` / `SegmentedControl` / `Rating` / `Table` … (29) |

!!! tip "Por onde começar"
    Se você está chegando agora, siga na ordem: **[Texto, ação e
    indicadores](widgets/basics.md)** → **[Layout](widgets/layout.md)** →
    **[Inputs com valor](widgets/inputs.md)**. O resto pode ser lido por demanda.

## Conceitos transversais

Estes valem para qualquer widget — vale ler antes de mergulhar nas famílias.

### Chaves (`key`)

Dê um `key` estável a cada filho de uma lista. O reconciliador usa chaves para
emitir `Reorder` em vez de recriar widgets, e para casar nós entre rebuilds.

### Percorrendo a árvore

Todo widget expõe `child_nodes()` — use-o para caminhar a árvore de forma
genérica, sem alcançar o armazenamento interno de cada tipo. *Leaves* (`Text`,
`Image`, inputs) devolvem `[]`.

### Estilo, semântica e foco

Toda subclasse de `Widget` aceita `style` (um [`Style`](estilos.md)),
`semantics`/`focusable`/`focus_order` (acessibilidade) e `key`. Por isso essas
props não aparecem nas tabelas de cada família — são universais.

### Contrato de eventos por widget

Cada widget declara o evento que cada *handler* emite via a classvar
`event_schemas` (ex.: `Button.event_schemas == {"on_click": TapEvent}`). Esse
contrato é publicado por [`introspect()`](../referencia/api.md) e consumido pela
fronteira do dispositivo. Veja [Eventos](eventos.md).

!!! info "Paridade dos dois renderizadores"
    O conjunto completo renderiza tanto no **simulador Qt** quanto no
    **dispositivo (Compose)** — a paridade é fixada pela suíte de conformância
    (*golden snapshots* dos dois tradutores `Style`). A única exceção são alguns
    widgets de hardware (`CameraPreview` / `QrScanner` / `MapView`), que são
    **device-only** e aparecem como *placeholder* sinalizado no Qt.

## Recapitulando

- Widgets são modelos Pydantic; importe sempre do nível do pacote
  (`from tempestroid import ...`).
- São ~100 widgets em 10 famílias — use o catálogo acima.
- *Inputs* com valor emitem um evento de mudança tipado (`on_change` /
  `on_select`); dê um `key` estável a filhos de listas.
- `style`/`semantics`/`focusable`/`key` são universais a todo widget.

## Próximos passos

➡️ Deixe os widgets bonitos com **[Estilos](estilos.md)**, entenda os
**[Eventos](eventos.md)** tipados, ou veja apps completos na
**[Galeria de exemplos](exemplos.md)**.

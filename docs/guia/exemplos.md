# Galeria de exemplos

Um conjunto de apps de exemplo executáveis vive em `examples/`. Cada um expõe o
mesmo contrato `make_state()` + `view(app)`, então roda no simulador Qt **e** no
dispositivo via code-push, sem mudanças.

```bash
# Simulador Qt no desktop (precisa do extra `qt`; instalado por `uv sync`)
uv run python examples/<nome>/app.py
uv run tempest dev examples/<nome>/app.py     # + hot reload ao salvar

# Em um dispositivo Android, via code-push por LAN (fase B5)
adb reverse tcp:8765 tcp:8765                 # via USB; pule se na mesma Wi-Fi
uv run tempest serve examples/<nome>/app.py
```

## Apps

| App | O que mostra | Widgets / patches exercitados |
|---|---|---|
| `counter` | O básico: handlers síncronos **e** `async`. | `Text`, `Button`, `Row`/`Column`; `update`. |
| `shell` | Os componentes compostos: um `Scaffold` com `AppBar` no topo e `NavBar` embaixo, corpo por aba. | `tempestroid.components` (`AppBar`/`Scaffold`/`NavBar`/`Header`) reduzidos a primitivos via `Component.render`. |
| `todo` | Lista dirigida por toque (sem entrada de texto — itens vêm de um pool fixo). | Lista com chave estável; `insert` / `remove` / `update`. |
| `calculator` | Grade densa de botões como única entrada. | `Row`/`Column` aninhados, 16 botões com chave; `update` no display. |
| `stopwatch` | Loop async-first: um handler corrotina conta via `asyncio.sleep` sem travar a UI. | Rebuilds coalescidos a partir do loop; `update`. |
| `colorpicker` | `Style` dinâmico: swatches recolorem um preview vivo; toggles re-estilizam o texto. | Atualizações de `background` / `font_size` / `font_weight` pelo diff. |
| `form` | Os inputs com valor, cada um dobrando seu evento tipado de volta no estado. | `Input` / `Checkbox` / `DatePicker` / `FilePicker`; `TextChangeEvent` / `ToggleEvent` / `DateChangeEvent` / `FileSelectEvent`. |
| `gallery` | O conjunto expandido de componentes + estilização de input + uma transição implícita de `Style`. | `Slider` / `Switch` / `ProgressBar` / `Spinner` / `Image` / `Icon` / `ScrollView` / `TextArea`; `Input` seguro + regex; `SlideEvent`; `Style.transition`. |
| `device_counter` | Contador mínimo só de dispositivo (sem import de Qt) para o caminho de code-push. | Mesmo contrato, livre de Qt. |

## Conjunto de widgets atual

Os **dois renderizadores** — simulador Qt (desktop) e Compose (dispositivo) —
suportam o conjunto completo do Trilho E. Não há mais o gap antigo de "o Compose
só renderiza cinco widgets": os inputs com valor (`Input` / `TextArea` /
`Checkbox` / `Switch` / `Slider` / `Select` / `DatePicker` / `FilePicker` / …)
renderizam **nativamente no aparelho** via Jetpack Compose e dobram seus eventos
tipados de volta no estado. A paridade é fixada pela suíte de conformância
(*golden snapshots* dos dois tradutores `Style → Qt` e `Style → Compose`) e foi
verificada em device ao longo de E0–E9.

Cobertura (ambos os renderizadores, salvo nota):

| Categoria | Widgets |
|---|---|
| Layout | `Column` / `Row` / `Container` / `Stack` / `Wrap` / `ScrollView` / `SafeArea` / `AspectRatio` / `PageView` / `KeyboardAvoidingView` |
| Texto e ação | `Text` / `Button` / `Icon` / `Image` (`on_click`) |
| Inputs com valor | `Input` / `TextArea` / `Checkbox` / `Switch` / `Slider` / `RangeSlider` / `Select` / `DatePicker` / `TimePicker` / `FilePicker` / `PinInput` / `MaskedInput` / `Autocomplete` / `Form` / `FormField` |
| Listas virtualizadas | `LazyColumn` / `LazyRow` / `LazyGrid` / `SectionList` (+ pull-to-refresh, scroll infinito) |
| Navegação | `Navigator` / `TabView` / `TabBar` / `RouteDrawer` |
| Overlays | `Dialog` / `BottomSheet` / `Menu` / `Popover` / `Toast` / `Tooltip` / `ActionSheet` |
| Animação | `Animated` / `AnimatedList` / `Hero` / `Shimmer` / `Skeleton` |
| Gestos | `GestureDetector` / `PanHandler` / `ScaleHandler` / `DoubleTapHandler` / `Draggable` / `DragTarget` / `Dismissible` / `ReorderableList` / `InteractiveViewer` |
| Mídia e gráficos | `Canvas` / `Svg` / `VideoPlayer` / `WebView` / `Blur` / `BackdropFilter` / `ClipPath` |
| Indicadores | `ProgressBar` / `Spinner` |

!!! note "Divergência de mídia/câmera (device-only)"
    Alguns widgets de hardware — `CameraPreview` / `QrScanner` / `MapView` —
    renderizam só no aparelho (Compose) e aparecem como **placeholder sinalizado
    no Qt**, não o contrário. As divergências por campo entre os dois tradutores
    estão documentadas na suíte de conformância (`tests/conformance/`).

Os exemplos `form` e `gallery` exercitam os inputs com valor de verdade — no
simulador **e** no aparelho. Exemplos como `calculator` continuam dirigidos por
teclado numérico por *design* do app, não por limite do renderizador.

!!! tip "Handlers estáveis"
    Rebuilds comparam props de *handler* por identidade, então um `lambda` novo a
    cada build lê como mudança de prop (limitação conhecida). Os exemplos ainda
    emitem *patches* corretos — apenas mais que o mínimo estrito. Prefira
    referências de *handler* estáveis em apps de produção.

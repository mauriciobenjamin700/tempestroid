# Cobertura de renderizadores (Qt vs Compose)

O tempestroid tem **um reconciliador e dois renderizadores-folha**: o **Qt**
(simulador desktop) e o **Compose** (dispositivo Android, Kotlin). Esta página é a
matriz de **qual widget cada renderizador trata** — a referência para saber o que
roda no aparelho além do simulador.

!!! info "O que cada coluna significa"
    - **Qt (simulador)** — o widget tem um caminho de render no renderizador Qt
      (`tempestroid/renderers/qt/`).
    - **Compose (device)** — o renderizador Kotlin
      (`android-host/.../TempestRenderer.kt`) tem um **case explícito** que monta um
      Composable real para o `type` do nó (não cai no fallback `Box`/`Popup`).
    - Esta matriz reflete **cobertura no nível de código** (existe um tratador).
      A verificação **on-device por widget** (screenshot de cada um no aparelho) é
      feita nas rodadas de *device-verify* das fases E e segue como trabalho
      contínuo — onde não foi exercida, está sinalizado.

!!! check "Resumo"
    **Todo widget primitivo exportado tem um tratador nos dois renderizadores.** O
    renderizador Compose tem **62 cases primitivos + 7 de overlay**; qualquer
    `type` sem case cai num `Box`/`Popup` forward-compat (nunca quebra). Os
    **componentes compostos** (`tempestroid/components/`) são rebaixados a
    primitivos no Python (`Component.render`) antes da serialização — então **nunca
    chegam ao Kotlin**: renderizam via seus filhos primitivos nos dois lados.

## Layout

| Widget | Qt (simulador) | Compose (device) | Notas |
|---|:---:|:---:|---|
| `Column` | ✅ | ✅ | |
| `Row` | ✅ | ✅ | |
| `Container` | ✅ | ✅ | No Compose cai no `Box` forward-compat (estilo + filhos). |
| `Stack` | ✅ | ✅ | Z-order; `position=ABSOLUTE` ancora por insets. |
| `SafeArea` | ✅ | ✅ | Compose inseta contra `WindowInsets.safeDrawing`. |
| `Wrap` | ✅ | ✅ | Quebra de linha fixada na conformância (`flex_wrap`). |
| `AspectRatio` | ✅ | ✅ | |
| `PageView` | ✅ | ✅ | Emite `PageChangeEvent`. |
| `ScrollView` | ✅ | ✅ | |
| `KeyboardAvoidingView` | ✅ | ✅ | |

## Texto, ação e indicadores

| Widget | Qt (simulador) | Compose (device) | Notas |
|---|:---:|:---:|---|
| `Text` | ✅ | ✅ | |
| `Button` | ✅ | ✅ | |
| `Icon` | ✅ | ✅ | Ícones Material nomeados. |
| `Image` | ✅ | ✅ | Compose via Coil. |
| `ProgressBar` | ✅ | ✅ | |
| `Spinner` | ✅ | ✅ | |

## Inputs e formulários

| Widget | Qt (simulador) | Compose (device) | Notas |
|---|:---:|:---:|---|
| `Input` | ✅ | ✅ | |
| `TextArea` | ✅ | ✅ | |
| `Checkbox` | ✅ | ✅ | |
| `Switch` | ✅ | ✅ | |
| `Slider` | ✅ | ✅ | |
| `RangeSlider` | ✅ | ✅ | Qt: dois `QSlider`; Compose: M3 `RangeSlider`. |
| `Dropdown` / `Select` | ✅ | ✅ | |
| `TimePicker` | ✅ | ✅ | Qt: spinner inline; Compose: dialog M3. |
| `DatePicker` | ✅ | ✅ | |
| `FilePicker` | ✅ | ✅ | |
| `Autocomplete` | ✅ | ✅ | |
| `PinInput` | ✅ | ✅ | |
| `MaskedInput` | ✅ | ✅ | |
| `FormField` | ✅ | ✅ | Validação roda no Python; renderer só desenha o erro. |
| `Form` | ✅ | ✅ | |

## Listas virtualizadas

| Widget | Qt (simulador) | Compose (device) | Notas |
|---|:---:|:---:|---|
| `LazyColumn` | ✅ | ✅ | Janela materializada pela app; veja [divergências](#divergencias). |
| `LazyRow` | ✅ | ✅ | |
| `LazyGrid` | ✅ | ✅ | |
| `SectionList` | ✅ | ✅ | Cabeçalho fixo: `QLabel` flutuante (Qt) vs `stickyHeader` (Compose). |
| `RefreshControl` | ✅ | ✅ | Qt: prop `refreshing` (sem gesto de puxar); Compose: `PullToRefreshBox`. |

## Navegação

| Widget | Qt (simulador) | Compose (device) | Notas |
|---|:---:|:---:|---|
| `Navigator` | ✅ | ✅ | Qt: `QStackedWidget` + `QPropertyAnimation`; Compose: `AnimatedContent`. |
| `TabView` | ✅ | ✅ | |
| `TabBar` | ✅ | ✅ | |
| `RouteDrawer` | ✅ | ✅ | Compose: `ModalDrawer`. |

## Overlays e feedback

| Widget | Qt (simulador) | Compose (device) | Notas |
|---|:---:|:---:|---|
| `Dialog` | ✅ | ✅ | Compose: `AlertDialog` M3. |
| `BottomSheet` | ✅ | ✅ | Compose: `ModalBottomSheet`. |
| `ActionSheet` | ✅ | ✅ | |
| `Toast` | ✅ | ✅ | |
| `Menu` | ✅ | ✅ | Compose: `DropdownMenu`. |
| `Popover` | ✅ | ✅ | |
| `Tooltip` | ✅ | ✅ | |

## Animação

| Widget | Qt (simulador) | Compose (device) | Notas |
|---|:---:|:---:|---|
| `Animated` | ✅ | ✅ | Clock de frames cruza a ponte (`FRAME_TOKEN`). |
| `AnimatedList` | ✅ | ✅ | |
| `Shimmer` | ✅ | ✅ | |
| `Skeleton` | ✅ | ✅ | |
| `Hero` | ✅ | ✅ | Transição compartilhada entre telas. |

## Gestos

| Widget | Qt (simulador) | Compose (device) | Notas |
|---|:---:|:---:|---|
| `GestureDetector` | ✅ | ✅ | `on_tap` / `on_double_tap` / `on_long_press` / `on_swipe`. |
| `PanHandler` | ✅ | ✅ | |
| `ScaleHandler` | ✅ | ✅ | Pinça/zoom. |
| `DoubleTapHandler` | ✅ | ✅ | |
| `Draggable` | ✅ | ✅ | |
| `DragTarget` | ✅ | ✅ | |
| `Dismissible` | ✅ | ✅ | Swipe-to-delete. |
| `ReorderableList` | ✅ | ✅ | |
| `InteractiveViewer` | ✅ | ✅ | |

## Mídia e gráficos

| Widget | Qt (simulador) | Compose (device) | Notas |
|---|:---:|:---:|---|
| `Canvas` | ✅ | ✅ | Lista de comandos JSON idêntica (conformância). |
| `Svg` | ✅ | ✅ | |
| `Blur` / `BackdropFilter` | ✅ | ✅ | |
| `ClipPath` | ✅ | ✅ | |
| `VideoPlayer` | ✅ | ✅ | Compose via `AndroidView`. |
| `WebView` | ✅ | ✅ | Compose via `AndroidView`. |
| `CameraPreview` | ⚠️ placeholder | ✅ device | Qt mostra placeholder sinalizado; câmera real só no device. |
| `QrScanner` | ⚠️ placeholder | ✅ device | idem — leitura de QR só no device. |
| `MapView` | ⚠️ placeholder | ✅ device | idem — mapa real só no device. |

## Componentes compostos

Tudo em `tempestroid/components/` (`AppBar`, `Scaffold`, `NavBar`, `Sidebar`,
`Footer`, `Header`, `Card`, `Drawer`, `Calendar`, `Clock`, componentes BR de
formulário, etc.) é **rebaixado a primitivos no Python** por `Component.render`
antes do diff. O reconciliador nunca serializa um tipo `Component` para o
aparelho — o Kotlin só vê os filhos primitivos. Logo os componentes herdam a
cobertura dos primitivos que emitem, idêntica nos dois renderizadores.

## Divergências documentadas {#divergencias}

Os dois renderizadores casam em **comportamento e payload de evento**, mas usam
mecanismos nativos distintos. As divergências fixadas pela
[suíte de conformidade](../roadmap.md) (fase D) e descritas no `CLAUDE.md`:

- **Listas:** a área de scroll Qt cobre só a janela materializada (sem extensão
  virtual reservada); o `LazyColumn` do Compose reporta `layoutInfo` contra o
  `itemCount` total.
- **Overlays:** Qt usa `QDialog`/`QMenu`/`QTimer`; Compose usa Material3
  (`AlertDialog`/`ModalBottomSheet`/`DropdownMenu`) que gerenciam o próprio scrim
  e `WindowInsets.safeDrawing`.
- **Navegação:** Qt anima com `QPropertyAnimation`; Compose com
  `AnimatedContent`/`ModalDrawer`. O botão *voltar* do Android é o caminho
  device (vs `Esc` no simulador).
- **Mídia device-only:** câmera, QR e mapa são placeholders sinalizados no Qt e
  reais só no aparelho.

!!! note "Fonte da verdade"
    A coluna **Compose (device)** é derivada diretamente do `when (node.type)` em
    `android-host/app/src/main/java/.../TempestRenderer.kt` (dispatch primário +
    de overlay). Ao adicionar um widget novo, garanta um case lá **e** uma entrada
    nesta matriz.

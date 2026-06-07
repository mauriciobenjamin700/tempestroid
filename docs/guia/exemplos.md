# Galeria de exemplos

Um conjunto de apps de exemplo executáveis vive em
[`examples/`](https://github.com/mauriciobenjamin700/tempestroid/tree/main/examples).
Cada um expõe o mesmo contrato `make_state()` + `view(app)`, então roda no
simulador Qt **e** no dispositivo via code-push, sem mudanças. **Clique no nome
de qualquer app abaixo para ver o código-fonte** — todo `app.py` abre com um
*docstring* explicando o que demonstra.

```bash
# Simulador Qt no desktop (precisa do extra `qt`; instalado por `uv sync`)
uv run python examples/<nome>/app.py
uv run tempest dev examples/<nome>/app.py     # + hot reload ao salvar

# Em um dispositivo Android, via code-push por LAN (fase B5)
adb reverse tcp:8765 tcp:8765                 # via USB; pule se na mesma Wi-Fi
uv run tempest serve examples/<nome>/app.py
```

## Fundamentos

| App | O que mostra | Exercita |
|---|---|---|
| [`counter`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/counter/app.py) | O básico: handlers síncronos **e** `async` mutam estado e disparam um rebuild coalescido. | `Text`, `Button`, `Row`/`Column`; `update`. |
| [`stopwatch`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/stopwatch/app.py) | Loop async-first: um handler corrotina conta via `asyncio.sleep` sem travar a UI (stop/reset seguem tocáveis). | Rebuilds coalescidos a partir do loop; `update`. |
| [`todo`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/todo/app.py) | Digite uma tarefa no `Input` e toque "add"; tocar alterna concluída; "clear done" remove as feitas. | `Input` + chave estável; **todos** os child patches: `insert` / `remove` / `update`. |
| [`calculator`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/calculator/app.py) | A grade de botões **é** a entrada (sem widget de texto) — vitrine de layout denso. | `Row`/`Column` aninhados, botões com chave; `update` no display. |
| [`colorpicker`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/colorpicker/app.py) | `Style` dinâmico: *swatches* recolorem um preview vivo; toggles re-estilizam o texto. | `background` / `font_size` / `font_weight` pelo diff. |

## Componentes e shell

| App | O que mostra | Exercita |
|---|---|---|
| [`shell`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/shell/app.py) | Tela inteira montada dos componentes compostos: `Scaffold` + `AppBar` (com `Burger`/`Drawer`) no topo, `NavBar` embaixo. | `tempestroid.components` reduzidos a primitivos via `Component.render`. |
| [`gallery`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/gallery/app.py) | Widgets utilitários + estilização de input + transição implícita de `Style`. | `Slider`/`Switch`/`ProgressBar`/`Spinner`/`Image`/`Icon`/`ScrollView`/`TextArea`; `Input` seguro + regex; `Style.transition`. |

## Trilho E — paridade Flutter/RN

| App | O que mostra | Exercita |
|---|---|---|
| [`navigation`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/navigation/app.py) | Os três hosts de navegação: pilha push/pop animada, abas e gaveta. | `Navigator` / `TabView` / `RouteDrawer` (E0). |
| [`tabs`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/tabs/app.py) | Tab bar persistente troca o corpo entre 3 painéis; o estado compartilhado sobrevive à troca. | Padrão canônico de navegação por abas. |
| [`lists`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/lists/app.py) | `LazyColumn` de 10k itens + paginação + pull-to-refresh, e `SectionList` com cabeçalho fixo. | Virtualização por janela (E1). |
| [`overlays`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/overlays/app.py) | Dialog, bottom sheet, menu e toast pela API imperativa de overlay do `App`. | Camada de overlay z-ordenada (E2). |
| [`animation`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/animation/app.py) | Caixa que faz *ease* de cor/opacidade, lista animada, `Hero` e `Shimmer`. | `AnimationController` + `Tween` no clock de frames (E3). |
| [`gestures`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/gestures/app.py) | Swipe-to-delete (`Dismissible`), arrastar p/ reordenar e pinça-zoom. | Gestos avançados (E4). |
| [`forms`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/forms/app.py) | `Form` de `FormField`s com validators tipados (bloqueia submit inválido) + inputs de seleção/segmento. | Validação em Python antes dos patches (E5). |
| [`form`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/form/app.py) | Os inputs com valor básicos, cada um dobrando seu evento tipado de volta no estado. | `Input` / `Checkbox` / `DatePicker` / `FilePicker` + eventos tipados. |
| [`layout`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/layout/app.py) | Chips com `Wrap`, `PageView` paginado e `CollapsingAppBar` que encolhe ao rolar. | Layout refinado (E6). |
| [`media`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/media/app.py) | Desenho com `Canvas`, `Svg`, blur e clip. | Mídia e gráficos (E7). |
| [`platform`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/platform/app.py) | Haptics, preferências reais, stream de lifecycle e `KeyboardAvoidingView`. | Plataforma/sistema (E8) — roda no Qt e no device. |
| [`theming`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/theming/app.py) | Toggle dark/light (`App.set_theme`), locale PT↔árabe/RTL (`App.set_locale`) e `Semantics`. | Transversais: tema/i18n/acessibilidade (E9). |

## Dispositivo e multi-arquivo

| App | O que mostra | Exercita |
|---|---|---|
| [`device_counter`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/device_counter/app.py) | Contador mínimo **sem import de Qt** — o alvo do code-push no aparelho. | Mesmo contrato, livre de Qt (B5). |
| [`native_caps`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/native_caps/app.py) | Capacidades nativas sem config extra, cada uma um round-trip request/response tipado. | `clipboard` / `storage` / `database` (SQLite) / `secure_storage` / `system` (device-verificado). |
| [`sysverify`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/sysverify/app.py) | Harness de verificação on-device das capacidades que exigem hardware real. | Sensores / biometria / push (device-only). |
| [`multifile`](https://github.com/mauriciobenjamin700/tempestroid/tree/main/examples/multifile) | Projeto **multi-arquivo** (`main.py` + pacote `widgets/`) — o que `tempest new --template multi` gera. | Bundle do projeto inteiro no `sys.path` (Trilho C). |

## Conjunto de widgets atual

Os **dois renderizadores** — simulador Qt (desktop) e Compose (dispositivo) —
suportam o conjunto completo do Trilho E. Não há mais o gap antigo de "o Compose
só renderiza cinco widgets": os inputs com valor (`Input` / `TextArea` /
`Checkbox` / `Switch` / `Slider` / `Dropdown` / `DatePicker` / `FilePicker` / …)
renderizam **nativamente no aparelho** via Jetpack Compose e dobram seus eventos
tipados de volta no estado. A paridade é fixada pela suíte de conformância
(*golden snapshots* dos dois tradutores `Style → Qt` e `Style → Compose`) e foi
verificada em device ao longo de E0–E9.

Cobertura (ambos os renderizadores, salvo nota):

| Categoria | Widgets |
|---|---|
| Layout | `Column` / `Row` / `Container` / `Stack` / `Wrap` / `ScrollView` / `SafeArea` / `AspectRatio` / `PageView` / `KeyboardAvoidingView` |
| Texto e ação | `Text` / `Button` / `Icon` / `Image` (`on_click`) |
| Inputs com valor | `Input` / `TextArea` / `Checkbox` / `Switch` / `Slider` / `RangeSlider` / `Dropdown` / `DatePicker` / `TimePicker` / `FilePicker` / `PinInput` / `MaskedInput` / `Autocomplete` / `Form` / `FormField` |
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

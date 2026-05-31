# tempestroid — Plano de paridade (Flutter / React Native)

> **Trilho E — Paridade.** Roadmap fase-a-fase para fechar o gap entre o
> tempestroid e o que Flutter + React Native oferecem de fábrica. Continuação
> natural de [`plan.md`](plan.md): Trilhos A–D já entregaram a fundação (IR,
> reconciliador, dois renderizadores, dev loop, capacidades nativas básicas).
> Este documento cobre **o que falta** para o framework ser de uso geral.
>
> **Nível de detalhe.** Cada fase traz `Arquivos` (paths reais a tocar),
> `Contrato` (assinaturas + pontos de plug no código existente) e `Sub-tarefas`
> (recortes do tamanho de um agente). É spec de implementação, não só roadmap —
> um agente por sub-tarefa consegue codar sem redescobrir a base.

---

## 0. Premissas e regras do trilho

Todo o trilho respeita as invariantes já consolidadas:

- **Um reconciliador, dois renderizadores.** Toda fase entrega a superfície em
  **três camadas casadas**: (1) a IR/widget Pydantic + diff agnóstico, (2) o
  renderizador **Qt** (simulador desktop), (3) o renderizador **Compose/Kotlin**
  (device). Uma fase só fecha quando os **dois** renderizadores estão verdes.
- **Tradutores de estilo espelhados.** Qualquer campo de `Style` novo entra em
  `Style → Qt` (`renderers/qt/style_translator.py`) **e** `Style → Compose`
  (`renderers/compose/style_translator.py`), com entrada na suíte de conformância
  (`tests/conformance/`).
- **Contrato tipado na fronteira.** Eventos novos viram modelos `Event` frozen em
  `widgets/events.py`, registrados no `event_schemas` (ClassVar) do widget e
  validados por `parse_event` antes do dispatch. Vão para `introspect()`
  automaticamente.
- **Bridge sem mudança de C quando possível.** Capacidades nativas seguem o
  padrão B6: envelope `{"kind": "native"}` + `NativeModules`/módulo Kotlin, e
  request/response pelo token reservado `__native_result__:<id>` — **sem tocar no
  JNI/C**. Só fases que exigem um canal novo (ex.: stream de sensores) abrem
  exceção, sinalizada no "feito quando" como **token reservado novo** (não C).
- **Tudo dentro do projeto atual — sem projetos extras.** Toda implementação mora
  **dentro do repositório `tempestroid`** (Python no pacote `tempestroid/`,
  Kotlin/Compose em `android-host/`). **Não** criar repositório, pacote PyPI,
  plugin ou app separado. Limite permitido: (1) **um módulo dedicado novo** por
  área para organizar imports (sempre re-exportado pelo `__init__.py`, nunca
  ilha) e (2) **uma seção de documentação extra** (README/MkDocs). Preferir DIY
  sobre `androidx`/Compose/Qt já presentes; dependência externa nova só com
  justificativa forte registrada no PR.
- **Verificação dual obrigatória.** Com device conectado, toda fase é exercida no
  **Qt** e no **Compose físico** (screenshot). Sem device, valida no Qt e declara
  explícito que a metade device não foi exercida.
- **`feito quando` é testável e honesto** — sempre lastreado por testes verdes
  (unitários + conformância) e, quando há device, por evidência on-device.

### 0.1 Mapa de arquivos (âncoras reais)

Os blocos `Arquivos` de cada fase referenciam estes paths. **Confirmados na
árvore atual** — usar exatamente estes (não `translate.py`, que não existe):

| Camada | Arquivo | Papel |
|---|---|---|
| IR | `tempestroid/core/ir.py` | `Node(type, key, props, children)`; patches `Replace`/`Update`/`Insert`/`Remove`/`Reorder`; `Path = tuple[int,...]` |
| Reconciliador | `tempestroid/core/reconciler.py` | `build(widget)->Node`, `diff(old,new)->list[Patch]`, `_reconcile*`, `_diff_props`, `_reconcile_keyed` |
| Estado/loop | `tempestroid/core/state.py` | `App(state, view, apply_patches)`: `.start()->Node`, `.current_tree`, `.swap_view`, `.set_state`, `.request_rebuild` (coalesce via `loop.call_soon(_rebuild)`) |
| Introspecção | `tempestroid/core/introspection.py` | `introspect()`, `widget_catalog`, `event_catalog` |
| Widget base | `tempestroid/widgets/base.py` | `Widget(BaseModel)` + `event_schemas: ClassVar`, `.widget_type`, `.child_nodes()`; `Component.render()->Widget`; `EventHandler` |
| Eventos | `tempestroid/widgets/events.py` | `Event` frozen base, `parse_event(event_type, raw)`, `EventValidationError` |
| Widgets folha | `tempestroid/widgets/{layout,inputs,media,indicators,button,text,gestures}.py` | primitivos; exemplo `button.py` |
| Componentes | `tempestroid/components/*.py` | compostos que baixam para primitivos via `Component.render` |
| Qt renderer | `tempestroid/renderers/qt/renderer.py` | aplica patches em `QWidget`s |
| Qt translator | `tempestroid/renderers/qt/style_translator.py` | `to_qss(style,*,with_padding)->str`, `layout_alignment`, `self_alignment` |
| Qt runner | `tempestroid/renderers/qt/app_runner.py` | `run_qt` (qasync) |
| Compose translator | `tempestroid/renderers/compose/style_translator.py` | `to_compose(style)->dict` (spec JSON-able) |
| Bridge protocolo | `tempestroid/bridge/protocol.py` | `handler_token(path,prop)`, `event_type_for`, `MountMessage`/`PatchMessage`/`EventMessage` |
| Bridge serializer | `tempestroid/bridge/serializer.py` | `serialize_node(node,path=())->dict`, `serialize_patch(patch)->dict` |
| Bridge handlers | `tempestroid/bridge/handlers.py` | `HandlerRegistry.refresh/dispatch/tokens` |
| Bridge device | `tempestroid/bridge/device.py` | `Bridge` ABC, `LoopbackBridge`, `DeviceApp.start/reload/handle_event/_on_patches` |
| Bridge JNI | `tempestroid/bridge/jni.py` | `JniBridge`, `run_device`, `_on_event` (roteia `__native_result__`) |
| Nativo | `tempestroid/native/*.py` | `dispatch.py` (`send_native`/`send_native_request`/`resolve_native_result`) + um módulo por capacidade |
| Kotlin árvore | `android-host/app/src/main/java/org/tempestroid/host/TempestTree.kt` | `TempestNode(type,props,children)` snapshot; `apply(msg)` switch `mount`/`patch`; `parseNode`, `applyPatch` ops |
| Kotlin renderer | `android-host/.../host/TempestRenderer.kt` | árvore → `@Composable`; spec de `Style` → `Modifier`/`Arrangement` |
| Kotlin nativo | `android-host/.../host/NativeModules.kt` | por-activity; `ActivityResultLauncher`s; roteia comandos `native` |
| Kotlin runtime | `android-host/.../host/PythonRuntime.kt` | `dispatchEvent`, `onMessageFromPython`, `messageSink` |
| Kotlin activity | `android-host/.../host/MainActivity.kt` | `ComponentActivity`; alimenta a árvore; modo dev por intent |
| Testes | `tests/unit/test_*.py`, `tests/conformance/test_conformance.py` (+ `golden/`) | unit por área; golden Qt vs Compose |

**Padrão de widget novo (template, fiel a `button.py`):**

```python
class Dropdown(Widget):
    """..."""
    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_select": SelectEvent}
    options: list[str]
    value: str | None = None
    on_select: EventHandler | None = None
```

Depois: re-exportar em `widgets/__init__.py` (+ `__all__`), em `tempestroid/__init__.py` (+ `__all__`), o evento em `widgets/events.py` (+ `__all__`), mapear no `event_type_for` se o token cruzar a ponte, e adicionar testes em `tests/unit/`.

**Convenção de fases.** `E<n>`, sub-tarefas `E<n>a/b/c…`. Sequenciais por
dependência: E0 (navegação) destrava multi-tela e é pré-requisito de quase tudo;
E1 (listas) e E2 (overlays) são a base de UX; E3 (animação) é consumida por
E0/E2 nas transições; daí em diante o acoplamento afrouxa. Cada fase tem:
**Descrição → Superfície nova → Arquivos → Contrato → Sub-tarefas → Metas →
Feito quando.**

---

## E0 — Navegação e rotas

### Descrição

Hoje o framework renderiza **uma tela única**. Falta o recurso mais estrutural de
qualquer app mobile: uma **pilha de navegação** (push/pop), abas, gaveta como
rota, integração com o **botão voltar do Android** e **deep links**. Equivalentes:
`Navigator`/`go_router` (Flutter), React Navigation (RN).

### Superfície nova

- Módulo dedicado `tempestroid/navigation.py`: `Route`, `Router`, `NavStack`.
- API no `App`: `push`/`pop`/`replace`/`reset`; a pilha vive no `App.state`.
- Widgets: `Navigator` (host de pilha), `TabView` + `TabBar`, `RouteDrawer`.
- Evento: `RouteChangeEvent`.

### Arquivos

- **Novo:** `tempestroid/navigation.py`; `widgets/navigation_widgets.py` (`Navigator`/`TabView`/`TabBar`/`RouteDrawer`).
- **Edita:** `core/state.py` (helpers de navegação no `App`), `widgets/events.py` (`RouteChangeEvent`), `widgets/__init__.py` + `tempestroid/__init__.py` (re-export), `renderers/qt/renderer.py` (transição de pilha), `bridge/protocol.py` (token reservado `__back__`), `android-host/.../MainActivity.kt` (`onBackPressed`→evento), `TempestRenderer.kt` (render do `Navigator`/abas com `AnimatedContent`).
- **Testes:** `tests/unit/test_navigation.py`, `tests/conformance/` (transições).

### Contrato

```python
# navigation.py
class Route(BaseModel):           # frozen
    name: str
    params: dict[str, Any] = {}

class NavStack(BaseModel):        # parte do App.state do usuário, ou embutida
    stack: list[Route] = [Route(name="/")]
    @property
    def top(self) -> Route: ...

# A pilha NÃO é um Node novo: o view(app) lê app.nav.top e monta a tela.
# push/pop só mutam o NavStack + request_rebuild — reaproveita o loop coalescido.
class App(Generic[S]):
    nav: NavStack
    def push(self, route: Route) -> None: ...   # nav.stack.append; request_rebuild
    def pop(self) -> bool: ...                   # pop se len>1; request_rebuild; False se raiz
    def replace(self, route: Route) -> None: ...
    def reset(self, stack: list[Route]) -> None: ...
```

- **Plug no diff:** trocar de rota é o `view` montando outra subtree → o `diff`
  existente emite um `Replace` no nó do `Navigator`. **Nenhuma mudança no
  reconciliador** — só um hint de transição em `props` (`{"transition": "slide"}`).
- **Botão voltar:** `MainActivity.onBackPressed()` → `PythonRuntime.dispatchEvent("__back__:")` → `bridge/jni.py:_on_event` reconhece o token reservado → `App.pop()`. Se `pop` retorna `False` (raiz), o host faz o back padrão (fecha app).
- **Qt:** `Esc`/botão simulado → `App.pop()`.

### Sub-tarefas

- **E0a (core):** `navigation.py` + helpers no `App` + `RouteChangeEvent`. Testes de pilha (push/pop/replace/reset, params tipados). *Não toca renderizador.*
- **E0b (Qt):** `Navigator`/`TabView`/`RouteDrawer` no `renderer.py` com `QStackedWidget` + transição `QPropertyAnimation`; `Esc`→`pop`.
- **E0c (Compose):** mesmos widgets em `TempestRenderer.kt` com `AnimatedContent`; abas e gaveta.
- **E0d (back/deep link):** token `__back__` (protocol + jni + MainActivity); deep link = intent extra → `reset(stack inicial)`.

### Metas

Multi-tela com histórico, voltar do Android funcionando, abas e gaveta como
rotas reais, deep link resolvendo para uma pilha inicial.

### Feito quando

App de exemplo com 3 telas navega push/pop; botão voltar do Android faz `pop`
(verificado no device por screenshot); abas trocam de tela; `tempest spec` lista
`RouteChangeEvent`; conformância das transições verde.

---

## E1 — Listas virtualizadas e scroll avançado

### Descrição

`ScrollView` + `Grid` renderizam **tudo** — inviável para listas grandes. Falta
**virtualização** (só renderiza o visível), seções com cabeçalho fixo,
**pull-to-refresh** e **scroll infinito**. Equivalentes: `ListView.builder`,
`GridView.builder`, Slivers (Flutter); `FlatList`, `SectionList` (RN).

### Superfície nova

- Widgets: `LazyColumn`/`LazyRow`, `LazyGrid`, `SectionList`, `RefreshControl`.
- API: `on_end_reached` + `end_reached_threshold`.
- Eventos: `ScrollEvent`, `RefreshEvent`, `EndReachedEvent`.

### Arquivos

- **Novo:** `widgets/lists.py` (`LazyColumn`/`LazyRow`/`LazyGrid`/`SectionList`/`RefreshControl`).
- **Edita:** `core/ir.py` (suporte a nó com `item_count` + sem filhos materializados), `core/reconciler.py` (diff por janela visível — ver Contrato), `widgets/events.py` (3 eventos), `bridge/serializer.py` (serializar o builder-range), `renderers/qt/renderer.py`, `TempestTree.kt`/`TempestRenderer.kt` (`LazyColumn` nativo), re-exports.
- **Testes:** `tests/unit/test_lists.py`, `tests/unit/test_reconciler.py` (janela).

### Contrato

```python
class LazyColumn(Widget):
    event_schemas: ClassVar[...] = {"on_end_reached": EndReachedEvent, "on_scroll": ScrollEvent}
    item_count: int
    item_builder: Callable[[int], Widget]   # NÃO serializável direto
    on_end_reached: EventHandler | None = None
```

- **Janela visível:** o nó da lista **não materializa filhos**. O renderizador
  reporta o range visível `[start, end)` (via `ScrollEvent`); o core chama
  `item_builder(i)` só nesse range e diffa **apenas a janela** contra a anterior,
  por **chave de item** (reaproveita `_reconcile_keyed` do A2). O `Node` da lista
  guarda `props={"item_count": n, "window": [start,end]}` e `children` = só os
  itens da janela. Mudança de scroll → novo `ScrollEvent` → rebuild da janela.
- **Decisão de divergência:** Compose (`LazyColumn`) já virtualiza nativo — pode
  receber só o `item_count` + um canal de "me dê o item i" (event request, padrão
  `__native_result__`). Qt monta a janela no Python. Documentar na conformância.

### Sub-tarefas

- **E1a (core):** modelo de nó virtual + diff por janela + 3 eventos. Teste "monta só a janela".
- **E1b (Qt):** `QListView`/viewport custom + sinal de scroll + overlay de refresh.
- **E1c (Compose):** `LazyColumn`/`LazyVerticalGrid`/`stickyHeader`/`PullRefreshIndicator`; `EndReachedEvent` via `derivedStateOf(LazyListState)`.
- **E1d:** `SectionList` (seções + header fixo) sobre E1a–c.

### Metas

Rolar 10k itens sem travar nos dois renderizadores; seção com cabeçalho fixo;
puxar-para-atualizar; carregar mais ao chegar no fim.

### Feito quando

Exemplo de lista de 10k itens rola fluido no Qt e no device; pull-to-refresh
dispara handler e atualiza; `on_end_reached` pagina; cabeçalho de seção gruda no
topo (screenshot device).

---

## E2 — Overlays e feedback

### Descrição

Faltam os overlays canônicos de mobile: **diálogo modal**, **bottom sheet**,
**toast/snackbar** transitório, **tooltip**, **menu suspenso/popover** e
**action sheet**. Equivalentes: `showDialog`/`showModalBottomSheet`/`SnackBar`/
`PopupMenuButton` (Flutter); `Modal`/`ActionSheetIOS` + libs (RN).

### Superfície nova

- API imperativa no `App`: `show_dialog`/`show_sheet`/`toast`/`show_menu`/`dismiss`.
- Widgets: `Dialog`, `BottomSheet`, `Toast`, `Tooltip`, `Menu`/`MenuItem`, `Popover`, `ActionSheet`.
- Camada de **overlay** no estado do `App`.

### Arquivos

- **Novo:** `widgets/overlays.py`.
- **Edita (núcleo — alto risco):** `core/ir.py` (raiz vira `{root, overlays}` — ver Contrato), `core/reconciler.py` (`build`/`diff` cientes da camada), `core/state.py` (`App` guarda `overlays` + API imperativa), `bridge/protocol.py` (`MountMessage`/`PatchMessage` ganham campo `overlays`), `bridge/serializer.py`, `renderers/qt/renderer.py` (z-order + barrier), `TempestTree.kt` (parsear `overlays`), `TempestRenderer.kt` (`Dialog`/`ModalBottomSheet`/`Popup`/`SnackbarHost`).
- **Testes:** `tests/unit/test_overlays.py`, `tests/unit/test_reconciler.py` (camada), `tests/conformance/`.

### Contrato — **mudança de núcleo detalhada**

A árvore deixa de ser um único `Node`. Introduzir um **documento de UI**:

```python
# core/ir.py  — NÃO mexe em Node; envolve a raiz
class Scene(_IRModel):
    root: Node
    overlays: list[Node] = []     # z-order crescente, acima da root

# core/reconciler.py
def build_scene(widget: Widget, overlays: list[Widget]) -> Scene: ...
def diff_scene(old: Scene, new: Scene) -> list[Patch]:
    # diffa root como hoje (paths começam em ()).
    # overlays diffam por CHAVE (cada overlay tem id estável) — reusa _reconcile_keyed.
    # path do overlay i = ("overlay", i, ...) — Path passa a aceitar um tag inicial.
```

- **`Path` ganha namespace:** hoje `tuple[int,...]`. Passa a `tuple[int|str,...]`
  onde o primeiro elemento pode ser `"overlay"`. Renderizadores roteiam por esse
  prefixo. **Compatível** com paths atuais (sem prefixo = root).
- **`App`:** `self._overlays: list[OverlayEntry]`. `show_dialog(node, *, barrier=True)`
  empurra um overlay com id, agenda `request_rebuild`; `dismiss(id)` remove.
  `toast(...)` agenda remoção por `loop.call_later`. O `_rebuild` passa a montar
  `Scene` e chamar `diff_scene`.
- **Protocolo:** `MountMessage.overlays: list[dict]`, `PatchMessage` carrega
  patches com path namespaced. Kotlin: `TempestTree` guarda `root` + `overlays[]`,
  `MainActivity` renderiza root e, por cima, cada overlay no composable certo.
- **Barrier/dismiss:** `DismissEvent` (token reservado por overlay id) sobe pela
  ponte normal.

### Sub-tarefas

- **E2a (núcleo):** `Scene` + `build_scene`/`diff_scene` + `Path` namespaced + `App` overlay API. **Só core, sem renderizador.** Testes de camada (empilhar/dismiss/ordem). *Esta sub-tarefa é a de maior risco — fechar e revisar antes das demais.*
- **E2b (protocolo/bridge):** estender `MountMessage`/`PatchMessage`/serializer; `DeviceApp` envia `Scene`.
- **E2c (Qt):** overlays como `QWidget` z-order + máscara (barrier); `QMenu`; toast com timer+fade.
- **E2d (Compose):** `Dialog`/`ModalBottomSheet`/`DropdownMenu`/`Popup`/`SnackbarHost` em `TempestRenderer`/`MainActivity`.

### Metas

Diálogo modal com barrier e foco; bottom sheet arrastável; toast some sozinho;
menu/popover ancorado; action sheet.

### Feito quando

Cada overlay abre e fecha por handler no Qt e no device; barrier bloqueia toques
atrás; toast expira; menu abre no anchor (screenshot device); testes da camada
`Scene` verdes.

---

## E3 — Framework de animação

### Descrição

Só existe `Transition` (estilo CSS declarativo). Falta um **motor de animação**
real: controladores, curvas/tweens, animações **implícitas**, **dirigidas por
gesto**, **transição de elemento compartilhado** (Hero) e **skeleton/shimmer**.
Equivalentes: `AnimationController`/`AnimatedContainer`/`Hero` (Flutter);
`Animated`/Reanimated (RN).

### Superfície nova

- Módulo dedicado `tempestroid/animation.py`: `AnimationController`, `Tween`, `Spring`, ampliar o enum `Curve`.
- Widgets: `Animated`, `AnimatedList`, `Hero`, `Shimmer`/`Skeleton`.
- Clock de frames no `App`.

### Arquivos

- **Novo:** `tempestroid/animation.py`; `widgets/animated.py`.
- **Edita:** `core/state.py` (clock de frames + `request_rebuild` por tick — ver Contrato), `style.py` (ampliar `Curve`, talvez `Spring`), `renderers/qt/app_runner.py` (ticker `QTimer`/qasync), `renderers/compose/style_translator.py` (spec carrega curva/duração), `TempestRenderer.kt` (`animate*AsState`/`AnimatedVisibility`/`SharedTransitionLayout`), re-exports.
- **Testes:** `tests/unit/test_animation.py` (clock injetável), `tests/conformance/`.

### Contrato — **clock de frames detalhado**

```python
# animation.py
class AnimationController:
    def __init__(self, duration_s: float, curve: Curve = Curve.EASE) -> None: ...
    value: float                      # 0..1, lido pelo view
    def forward(self) -> None: ...     # registra-se no clock do App
    def reverse(self) -> None: ...
    def stop(self) -> None: ...

class Tween(Generic[T]):
    begin: T; end: T
    def at(self, t: float) -> T: ...   # interpola (cor/num/edge)
```

- **Clock no `App`:** novo registro `self._animations: set[AnimationController]`.
  Enquanto não-vazio, o `App` agenda um **tick por frame** (`loop.call_later(1/60)`
  no Qt; no device o host chama via `withFrameNanos` → evento `__frame__`). Cada
  tick: avança cada controller, e chama `request_rebuild` (coalescido). Controller
  que chega a `value==1` se desregistra → clock para (sem busy-loop).
- **Determinismo de teste:** o clock aceita um `time_source` injetável; o teste
  avança manualmente e verifica frames-chave. **Sem `Date.now`** (proibido nos
  scripts/loop) — usar o relógio do loop.
- **`Animated` widget:** guarda `target` + `controller`. A **interpolação roda no
  core** → os renderizadores recebem só props finais por frame (reconciliador
  permanece agnóstico). 
- **Divergência Qt × Compose (documentar na conformância):** para animação
  **declarativa** (mudou o `Style` alvo), Compose pode delegar ao motor nativo
  (`animateColorAsState` etc.) lendo `duration`/`curve` do spec — mais fluido. Qt
  interpola no core. `Hero` = Qt anima geometria no `Replace` de rota; Compose usa
  `SharedTransitionLayout`. Registrar essa divergência na tabela do Trilho D.

### Sub-tarefas

- **E3a (core):** `animation.py` (`AnimationController`/`Tween`/`Curve`) + clock no `App` com `time_source` injetável. Testes determinísticos. *Sem renderizador.*
- **E3b (Qt):** ticker no `app_runner`; `Animated`/`AnimatedList` interpolando no core; `Shimmer`.
- **E3c (Compose):** spec de animação no translator + `animate*AsState`/`AnimatedVisibility`; evento `__frame__` opcional.
- **E3d (Hero):** transição de elemento compartilhado integrada à E0 (rotas).

### Metas

Animar tamanho/cor/opacidade ao mudar estado; lista com itens entrando/saindo;
Hero entre telas; shimmer de loading; animação dirigida por arrasto.

### Feito quando

`AnimatedContainer`-equivalente anima ao mudar estado nos dois renderizadores;
`AnimatedList` anima insert/remove; `Hero` faz transição entre rotas no device
(screenshot/gravação); testes do controlador verdes com clock determinístico.

---

## E4 — Gestos avançados

### Descrição

Hoje só `tap`/`long-press`/`swipe` (em `widgets/gestures.py`). Faltam
**pan/drag-and-drop**, **pinça/zoom/escala**, **toque duplo**, **dismissible**,
**lista reordenável** e **viewer interativo**. Equivalentes: `Draggable`/
`DragTarget`/`Dismissible`/`ReorderableListView`/`InteractiveViewer` (Flutter).

### Superfície nova

- Widgets/handlers (em `widgets/gestures.py`): `PanHandler`, `ScaleHandler`, `DoubleTapHandler`, `Draggable`+`DragTarget`, `Dismissible`, `ReorderableList`, `InteractiveViewer`.
- Eventos: `PanEvent`, `ScaleEvent`, `DragEvent`, `DismissEvent`, `ReorderEvent`.

### Arquivos

- **Edita:** `widgets/gestures.py` (novos handlers, seguindo `TapHandler`/`SwipeHandler` existentes), `widgets/events.py` (5 eventos), `bridge/protocol.py` (`event_type_for` mapeia os novos tokens), `renderers/qt/renderer.py`, `TempestRenderer.kt` (`pointerInput`), re-exports.
- **Testes:** `tests/unit/test_overlay_gestures.py` (já existe — estender), `tests/conformance/`.

### Contrato

- **Padrão já existe:** seguir `SwipeHandler`/`SwipeEvent` em `gestures.py`/
  `events.py`. Cada novo evento é frozen, registrado no `event_schemas` do handler,
  validado por `parse_event`, mapeado em `event_type_for`.
- **Reorder usa o diff existente:** `ReorderEvent(from_index, to_index)` → handler
  reordena a lista no estado → o `diff` emite `Reorder` (A2). Zero mudança de core.
- **Qt:** `QGestureRecognizer`/eventos de mouse; pinça `QPinchGesture`; DnD `QDrag`/`dropEvent`; `InteractiveViewer` = `QGraphicsView` com transform.
- **Compose:** `pointerInput` + `detectDragGestures`/`detectTransformGestures`/`detectTapGestures(onDoubleTap)`; `SwipeToDismiss`; reorder via `detectDragGesturesAfterLongPress`; viewer = `graphicsLayer`.

### Sub-tarefas

- **E4a:** eventos + handlers (Python) + `event_type_for`. Testes de parse/validação.
- **E4b (Qt):** reconhecedores no `renderer.py`.
- **E4c (Compose):** `pointerInput` no `TempestRenderer`.
- **E4d:** `Dismissible` + `ReorderableList` (compõem E4a–c + diff `Reorder`).

### Metas

Arrastar e soltar entre alvos; pinça-zoom de imagem; swipe-to-delete em lista;
reordenar por arrasto; duplo-toque.

### Feito quando

Cada gesto dispara o evento tipado correto e muda o estado nos dois renderizadores;
swipe-to-delete remove item; reorder reordena (diff `Reorder`); pinça-zoom no
device (screenshot).

---

## E5 — Inputs e formulários

### Descrição

Faltam controles de formulário centrais: **dropdown/select**, **time picker**,
**range slider**, um **framework de formulário/validação**, **autocomplete**,
**OTP/pin** e **input mascarado**. Equivalentes: `DropdownButton`/`showTimePicker`/
`RangeSlider`/`Form`+`TextFormField` (Flutter).

### Superfície nova

- Widgets (em `widgets/inputs.py`): `Dropdown`/`Select`, `TimePicker`, `RangeSlider`, `Autocomplete`, `PinInput`, `MaskedInput`.
- Módulo dedicado `widgets/forms.py`: `Form`, `FormField`, `Validator`, `FormState`.
- Eventos: `SelectEvent`, `TimeChangeEvent`, `RangeChangeEvent`, `SubmitEvent`, `ValidationEvent`.

### Arquivos

- **Novo:** `tempestroid/widgets/forms.py`.
- **Edita:** `widgets/inputs.py` (novos controles, seguindo `Input`/`Slider`/`DatePicker` existentes), `widgets/events.py` (5 eventos), `bridge/protocol.py`, `renderers/qt/renderer.py`, `TempestRenderer.kt`, re-exports.
- **Testes:** `tests/unit/test_input_widgets.py` (estender), `tests/unit/test_forms.py`.

### Contrato

- **Validação espelha `parse_event`:** `Validator` é função tipada
  `(value) -> str | None` (erro ou `None`); `FormState` agrega erros por campo +
  validade. `Form` guarda o estado dos campos no `App.state`; submit roda todos os
  validadores e bloqueia se houver erro — **erro estruturado JSON-serializável**,
  mesma filosofia do `EventValidationError`.
- Novos inputs seguem o padrão de `Input` (valor + `on_change` tipado).
- **Qt:** `QComboBox`/`QTimeEdit`/slider duplo custom/`QCompleter`/`setInputMask`.
- **Compose:** `ExposedDropdownMenuBox`/`TimePicker` M3/`RangeSlider`/`VisualTransformation`.

### Sub-tarefas

- **E5a:** controles isolados (`Dropdown`/`TimePicker`/`RangeSlider`/`PinInput`/`MaskedInput`) + eventos, nos dois renderizadores.
- **E5b:** `forms.py` (`Form`/`FormField`/`Validator`/`FormState`) + `Autocomplete`. Testes de validação.

### Metas

Select com opções; escolher hora; faixa min–max; formulário que valida e mostra
erro por campo; autocomplete filtrando; pin/OTP; máscara (CPF/telefone/etc.).

### Feito quando

Formulário de exemplo valida e bloqueia submit inválido com erro por campo nos
dois renderizadores; cada novo input dispara seu evento tipado; conformância dos
controles verde.

---

## E6 — Layout refinado

### Descrição

Refinos de layout: **flex-wrap**, **PageView/carousel**, **slivers** (app bar
colapsável/parallax), **tabela/DataTable** e **AspectRatio**.

### Superfície nova

- `Style`: campo `flex_wrap`.
- Widgets: `Wrap`, `PageView`, `CollapsingAppBar`, `Table`/`DataTable`, `AspectRatio`.
- Evento: `PageChangeEvent`.

### Arquivos

- **Edita:** `style.py` (`flex_wrap`), `renderers/qt/style_translator.py` + `renderers/compose/style_translator.py` (traduzir `flex_wrap` — **espelhar**), `widgets/layout.py` (`Wrap`/`PageView`/`AspectRatio`), `components/` (`CollapsingAppBar`/`Table`), `widgets/events.py` (`PageChangeEvent`), renderers, re-exports.
- **Testes:** `tests/conformance/` (`flex_wrap`), `tests/unit/test_widgets.py`.

### Contrato

- `Wrap` é **só estilo** (`flex_wrap`): entra nos dois translators + conformância,
  como qualquer campo de `Style`. `PageView` guarda página ativa no estado;
  `CollapsingAppBar` coordena com o scroll da E1 (nested scroll).
- **Qt:** flow layout custom (`Wrap`); `QStackedWidget`+swipe (`PageView`); header colapsável por sinal de scroll; `QTableView`.
- **Compose:** `FlowRow`/`FlowColumn`; `HorizontalPager`; `TopAppBar` + `nestedScroll`; `Modifier.aspectRatio`.

### Sub-tarefas

- **E6a:** `flex_wrap` + `Wrap` + `AspectRatio` (puro estilo/layout). Conformância.
- **E6b:** `PageView` + `PageChangeEvent`.
- **E6c:** `CollapsingAppBar` (depende de E1) + `Table`/`DataTable`.

### Metas

Chips/tags que quebram linha; carousel paginado com indicador; app bar que
encolhe ao rolar; tabela de dados; razão de aspecto fixa.

### Feito quando

`Wrap` quebra linha igual nos dois renderizadores (conformância); `PageView`
pagina e emite `PageChangeEvent`; app bar colapsa ao rolar (screenshot device).

---

## E7 — Mídia e gráficos

### Descrição

Lacuna de mídia/gráficos: **player de vídeo**, **WebView**, **canvas/desenho
vetorial**, **SVG**, **preview de câmera ao vivo**, **leitor de QR**, **mapa**,
**blur/backdrop**, **clip de forma**. Equivalentes: `VideoPlayer`/`webview_flutter`/
`CustomPaint`/`CameraPreview`/`google_maps_flutter` (Flutter).

### Superfície nova

- Widgets (em `widgets/media.py`): `VideoPlayer`, `WebView`, `Canvas`, `Svg`, `CameraPreview`, `QrScanner`, `MapView`, `Blur`/`BackdropFilter`, `ClipPath`.

### Arquivos

- **Edita:** `widgets/media.py` (novas folhas; `Image`/`Icon` já estão aí), `style.py` (talvez `blur`/`clip`), os dois `style_translator.py` (blur/clip — espelhar), `bridge/serializer.py` (spec de comandos do `Canvas`), `renderers/qt/renderer.py`, `TempestRenderer.kt`, `NativeModules.kt` (QR scanner → resultado por `__native_result__`), manifest (permissões câmera).
- **Testes:** `tests/unit/test_media.py`, `tests/unit/test_serializer.py` (canvas), `tests/conformance/` (blur/clip).

### Contrato

- **`Canvas` = lista de comandos serializável** (o único item com IR nova):
  `Canvas(commands: list[DrawCommand])` onde `DrawCommand` é union frozen
  (`Path`/`Fill`/`Stroke`/`Text`). `serialize_node` baixa para JSON-able; o diff
  compara a lista (reusa `_diff_props`). Qt interpreta com `QPainter`; Compose com
  `drawIntoCanvas`. Entra na conformância dos comandos.
- **Folhas com host nativo:** `VideoPlayer`/`WebView`/`CameraPreview`/`MapView`
  são `AndroidView` no Compose (sem mudança de C); QR devolve resultado pelo canal
  de evento (padrão B6). Qt: `QMediaPlayer`/`QWebEngineView`/`QCamera`; mapa e QR
  no sim = **placeholder com aviso explícito** (sem equivalente desktop fiel).

### Sub-tarefas

- **E7a:** `Canvas` (IR de comandos + diff + ambos renderizadores). Conformância.
- **E7b:** `VideoPlayer` + `WebView` (folhas `AndroidView`).
- **E7c:** `CameraPreview` + `QrScanner` (CameraX + `__native_result__`).
- **E7d:** `MapView` + `Blur`/`ClipPath` (estilo) + `Svg`.

### Metas

Tocar vídeo; embutir página web; desenhar formas/charts em canvas; renderizar SVG;
ver câmera ao vivo; ler QR; mostrar mapa; aplicar blur/clip.

### Feito quando

Vídeo toca e WebView carrega no device; `Canvas` desenha um chart simples idêntico
nos dois renderizadores (conformância dos comandos); SVG renderiza; preview de
câmera e leitura de QR funcionam no device (screenshot). Itens sem equivalente Qt
(mapa, scanner) declaram placeholder explícito no sim.

---

## E8 — Plataforma e sistema nativo

### Descrição

Capacidades de sistema: **haptics/vibração**, **sensores**, **StatusBar**,
**teclado** (avoiding/dismiss), **lifecycle** (bg/fg), **deep linking**,
**permissões**, **biometria**, **secure storage/keychain**, **prefs**, **SQLite**,
**connectivity**, **push (FCM) + notificação agendada**, **background tasks**.

### Superfície nova

- `native/`: `haptics.py`, `sensors.py`, `system.py`, `lifecycle.py`, `permissions.py`, `biometrics.py`, `secure_storage.py`, `prefs.py`, `database.py`, `connectivity.py`, `push.py`, `background.py`.
- Widget: `KeyboardAvoidingView` (em `widgets/layout.py`).
- Eventos: `LifecycleEvent`, `SensorEvent`, `ConnectivityEvent`, `DeepLinkEvent`.

### Arquivos

- **Novo:** os módulos `native/*.py` acima (seguir `native/camera.py`/`geolocation.py` existentes).
- **Edita:** `native/__init__.py` + `native/dispatch.py` (re-export; padrão `send_native`/`send_native_request`/`resolve_native_result`), `bridge/jni.py` (token reservado novo `__sensor__`/`__lifecycle__` para streams), `android-host/.../NativeModules.kt` (um módulo Kotlin por capacidade — estender o router B6), `MainActivity.kt` (lifecycle/permissões `ActivityResultContracts`), manifest (permissões + FCM service), `tempestroid/__init__.py`.
- **Testes:** `tests/unit/test_native.py` (estender — já cobre o padrão request/response).

### Contrato

- **Maioria = padrão B6 sem mudança de C:** `send_native_request(envelope)` →
  `await Future` → host responde por `__native_result__:<id>`. Resultados tipados
  (frozen) + `NativeError(code)` em falha. Espelha `native/camera.py`.
- **Exceção — streams (sensores) e lifecycle:** eventos **contínuos** do host.
  Entram pelo canal de evento existente como `EventMessage` com **token reservado
  novo** (`__sensor__:<type>`, `__lifecycle__`), roteado em `bridge/jni.py:_on_event`
  como o `__native_result__` já é. **Token novo, não mudança de C.**
- **Simulador Qt:** o que não tem hardware (sensores, biometria, FCM, WorkManager)
  = **stub/mock com aviso explícito** ("device-only"); o que dá pra simular (prefs
  em arquivo, SQLite via `sqlite3` stdlib, clipboard, lifecycle por foco da janela)
  roda de verdade.

### Sub-tarefas

(cada uma é um módulo + módulo Kotlin + teste; independentes entre si)

- **E8a:** haptics + system (statusbar/brilho/wakelock) + KeyboardAvoidingView.
- **E8b:** sensores (stream, token reservado) + lifecycle + connectivity + deep link.
- **E8c:** permissões (API explícita) + biometria.
- **E8d:** secure storage + prefs + SQLite (parte simulável no Qt).
- **E8e:** push (FCM) + notificação agendada + background/WorkManager.

### Metas

Vibrar; sensores em stream; controlar status bar; teclado não cobre o input;
reagir a bg/fg; deep link; pedir/checar permissão; biometria; segredo cifrado;
prefs + SQLite; estado de rede; push + agendamento; tarefa em background.

### Feito quando

Cada capacidade tem a metade Python unit-testada off-device; no device, haptics
vibra, sensor faz stream, teclado recua a tela, permissão é pedida/concedida,
biometria autentica, prefs/SQLite persistem, push chega e notificação agenda
(evidência on-device). Stubs do simulador avisam explicitamente o que é
device-only.

---

## E9 — Transversais (tema, i18n, acessibilidade)

### Descrição

Bases transversais: **tema/dark mode + MediaQuery**, **i18n/l10n + RTL**,
**acessibilidade** (semantics, leitor de tela, foco) e **fontes custom + escala de
texto**. Equivalentes: `Theme`/`MediaQuery`/`Directionality`/`Semantics` (Flutter).

### Superfície nova

- Módulos dedicados `tempestroid/theme.py` (`Theme`, `ThemeMode`, `MediaQueryData`) e `tempestroid/i18n.py` (`Locale`, `translate`/`t`, direção).
- `Style`/widgets: campo `semantics` (label/role/hint), `focusable`; `Style` ganha `text_scale`/fonte.
- Eventos: `ThemeChangeEvent`, `LocaleChangeEvent`.

### Arquivos

- **Novo:** `tempestroid/theme.py`, `tempestroid/i18n.py`.
- **Edita:** `core/state.py` (`App` expõe `theme`/`media`/`locale` para o `view` ler — **contexto, não Node**), `widgets/base.py` (`semantics`/`focusable` no `Widget`), `style.py` (`text_scale`/fonte; RTL inverte `start/end`), os dois `style_translator.py` (RTL espelhado + fonte — **conformância**), `core/introspection.py` (expor `semantics`), `renderers/qt/renderer.py`, `TempestRenderer.kt`/`MainActivity.kt`, re-exports.
- **Testes:** `tests/conformance/` (RTL start/end espelhados; light/dark), `tests/unit/test_introspection.py` (semantics), `tests/unit/test_theme.py`.

### Contrato

- **Tema/MediaQuery/Locale = contexto de entrada do `build`**, não nó da árvore: o
  `view(app)` lê `app.theme`/`app.media`/`app.locale` e monta de acordo. Trocar
  tema/locale = mutar esse contexto + `request_rebuild`. **Mantém "árvore é IR".**
- **RTL** inverte semântica `start/end` nos **dois** translators (espelhar +
  conformância). `semantics` é campo do `Widget`, propagado a ambos os
  renderizadores e ao `introspect()`.
- **Qt:** paleta QSS trocável; `MediaQuery` lê tamanho da janela/preset `Device`
  (já existe); `setLayoutDirection`; `QAccessible`; `QFontDatabase`.
- **Compose:** `MaterialTheme`/`isSystemInDarkTheme`; `LocalConfiguration`;
  `LocalLayoutDirection`; `Modifier.semantics`; `FontFamily` custom + `LocalDensity`.

### Sub-tarefas

- **E9a:** `theme.py` + dark mode + `MediaQueryData` (contexto no `App`). Snapshot light/dark.
- **E9b:** `i18n.py` + RTL (translators + conformância espelhada).
- **E9c:** acessibilidade (`semantics`/`focusable` + introspect) + fontes custom/escala.

### Metas

Trocar light/dark (e seguir o sistema); responsivo por breakpoint/orientação;
traduzir + espelhar RTL; rótulos lidos pelo TalkBack; fontes custom + respeitar
escala do sistema.

### Feito quando

Dark mode aplica nos dois renderizadores (snapshot light/dark); RTL espelha
`start/end` (conformância); TalkBack lê os rótulos no device; troca de locale
re-renderiza; fonte custom carrega e a escala de texto do sistema é respeitada.

---

## Resumo de fases

| Fase | Escopo | Sub-tarefas | Risco núcleo | Destrava |
|---|---|---|---|---|
| **E0** | Navegação e rotas | a(core) b(Qt) c(Compose) d(back/deeplink) | baixo (reusa diff) | multi-tela — pré-req de quase tudo |
| **E1** | Listas virtualizadas + scroll | a(core/janela) b(Qt) c(Compose) d(section) | **médio** (diff por janela) | performance de listas |
| **E2** | Overlays e feedback | a(núcleo Scene) b(bridge) c(Qt) d(Compose) | **ALTO** (`Scene` + `Path` namespaced) | UX básica de mobile |
| **E3** | Framework de animação | a(core/clock) b(Qt) c(Compose) d(Hero) | **ALTO** (clock de frames + divergência) | movimento/transições |
| **E4** | Gestos avançados | a(eventos) b(Qt) c(Compose) d(dismiss/reorder) | baixo (padrão pronto) | interação rica |
| **E5** | Inputs e formulários | a(controles) b(forms/validação) | baixo | formulários sérios |
| **E6** | Layout refinado | a(wrap/aspect) b(pager) c(collapsing/table) | baixo | layouts ricos |
| **E7** | Mídia e gráficos | a(canvas) b(vídeo/web) c(câmera/QR) d(mapa/blur/svg) | médio (IR de canvas) | mídia/gráficos |
| **E8** | Plataforma/sistema | a..e (um módulo cada) | baixo (padrão B6 + token p/ stream) | integração com o SO |
| **E9** | Transversais | a(tema) b(i18n/RTL) c(a11y/fontes) | médio (contexto + RTL) | base transversal |

**Ordem de delegação.** E0 → E1 → E2 → E3 primeiro (E2a e E3a, as sub-tarefas de
núcleo, **fecham e passam por review antes** das sub-tarefas de renderizador).
E4–E9 acoplam menos e reordenam por demanda — exceto E6c (depende de E1) e E3d
(depende de E0). Como nos outros trilhos: **uma sub-tarefa por agente, fechando no
"feito quando", com os dois renderizadores verdes e — havendo device —
verificação dual obrigatória.**

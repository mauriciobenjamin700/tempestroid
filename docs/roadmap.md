# Roadmap e fases

O desenvolvimento segue duas trilhas-base e uma trilha de expansão. **Trilho A**
é o framework em Python puro (desktop/CPython). **Trilho B** é o runtime Android
(CPython 3.14 + host Kotlin + ponte JNI + renderizador Compose). **Trilho E** é a
paridade com Flutter/React Native (**concluído** — E0–E9). O plano completo está em
[Plano de design (EN)](plan.md) e, para o Trilho E, em
[Plano de paridade](plan-parity.md).

## Trilho A — framework (Python puro)

| Fase | Escopo | Status |
|---|---|---|
| A0 | Fundação: pacote, ferramental, `tempest --help` | ✅ |
| A1 | Modelo de estilo + primitivas de widget tipadas | ✅ |
| A2 | Reconciliador: `build → diff → patch` | ✅ |
| A3 | Renderizador Qt: patches → `QWidget`s, `Style → Qt` | ✅ |
| A4 | Loop de eventos async: asyncio ⨉ Qt (`qasync`) | ✅ |
| A5 | `tempest dev`: watcher, hot restart, loop de comandos | ✅ |
| A6 | Contrato de eventos tipado + introspecção | ✅ |

## Trilho B — runtime Android

Todo o Trilho B (B0–B6) está **implementado e verificado num device arm64 real**
(Xiaomi `23053RN02A`, Android 15).

| Fase | Escopo | Status |
|---|---|---|
| B0 | CPython 3.14 para arm64 | ✅ |
| B1 | Wheels nativas (pydantic-core) + site-packages do dispositivo | ✅ |
| B2 | Host Kotlin: embute CPython, boota o interpretador fora da thread de UI via JNI | ✅ |
| B3 | Ponte JNI (nativa): transporte bidirecional Python↔Kotlin | ✅ |
| B4 | Renderizador Compose (nativo): renderiza a árvore serializada, aplica patches, roteia toques | ✅ |
| B5 | Dev server + QR (code-push por LAN + relay de logs) | ✅ |
| B6 | Capacidades nativas (notificações) | ✅ |

## Polimento e conformidade

| Fase | Escopo | Status |
|---|---|---|
| C | Polimento: `new`/`build`/`run` + hot reload com estado | ✅ |
| D | *Golden snapshots* de conformidade (Qt vs Compose) | ✅ |

!!! note "Suíte de conformidade (fase D)"
    `tests/conformance/` fixa os dois tradutores de `Style`: *golden snapshots* de
    `to_compose` + `to_qss`/`layout_alignment` para estilos canônicos
    (regenere com `UPDATE_GOLDEN=1`), além de uma tabela de paridade de cobertura
    por campo que falha se um tradutor passar a tratar (ou parar de tratar) um
    campo sem atualizar as divergências documentadas.

## Capacidades nativas — conjunto expandido (pós-B6)

Além de `notify`, o pacote `native/` já expõe geolocalização (`get_position`),
compartilhamento (`share`/`share_to_whatsapp`/`open_url`), câmera (`take_photo`),
armazenamento (`read_file`/`write_file`/`delete_file`/`list_files`), área de
transferência (`get_text`/`set_text`) e bluetooth (`scan`).

Isso adicionou um formato **request/response** à ponte (antes só *fire-and-forget*):
`send_native_request` envia um envelope com `request_id` e dá `await` num
`asyncio.Future`; o host responde pelo **mesmo** canal de evento sob o token
reservado `__native_result__:<id>` — **sem mudança de C/JNI**. Falhas levantam
`NativeError(code)`.

!!! warning "Validação no device pendente"
    A metade Python (envelopes, resolução de *future*, resultados tipados) está
    **toda coberta por testes off-device** (`tests/unit/test_native.py`). Os
    módulos Kotlin de capacidade + permissões/`FileProvider` no manifest estão
    **escritos mas ainda não validados num device** — precisam do toolchain
    Android SDK/NDK.

## Trilho E — Paridade Flutter / React Native (concluído)

Fechou o gap com o que Flutter + RN oferecem de fábrica. Toda fase
entrega as **três camadas casadas** (IR/diff + renderizador Qt + renderizador
Compose) e só fecha com os **dois renderizadores verdes** + (havendo device)
verificação dual. Spec fase-a-fase em [Plano de paridade](plan-parity.md).

**Sequência.** E0 (navegação) destrava multi-tela e é pré-requisito de quase
tudo; E1–E2 são a base de UX; E3 (animação) é consumida por E0/E2 nas transições;
E4–E9 acoplam menos e reordenam por demanda (exceto E6c←E1 e E3d←E0).

| Fase | Escopo | Risco núcleo | Status |
|---|---|---|---|
| E0 | Navegação e rotas (pilha push/pop, abas, gaveta, botão voltar, deep link) | baixo (reusa diff) | ✅ |
| E1 | Listas virtualizadas + scroll (lazy, seção sticky, pull-to-refresh, scroll infinito) | médio (diff por janela) | ✅ |
| E2 | Overlays e feedback (dialog, bottom sheet, toast, tooltip, menu, action sheet) | **alto** (`Scene` + `Path` namespaced) | ✅ |
| E3 | Framework de animação (controller, tween/curva, implícita, gesto, Hero, shimmer) | **alto** (clock de frames) | ✅ |
| E4 | Gestos avançados (pan/drag-drop, pinça/zoom, double-tap, dismissible, reorder) | baixo (padrão pronto) | ✅ |
| E5 | Inputs e formulários (dropdown, time, range, form/validação, autocomplete, OTP, máscara) | baixo | ✅ |
| E6 | Layout refinado (flex-wrap, pager/carousel, app bar colapsável, tabela, aspect ratio) | baixo | ✅ |
| E7 | Mídia e gráficos (vídeo, webview, canvas, svg, câmera live, QR, mapa, blur, clip) | médio (IR de canvas) | ✅ |
| E8 | Plataforma/sistema (haptics, sensores, lifecycle, permissões, biometria, storage, SQLite, push) | baixo (padrão B6 + token p/ stream) | ✅ |
| E9 | Transversais (tema/dark + MediaQuery, i18n/RTL, acessibilidade, fontes custom + escala) | médio (contexto + RTL) | ✅ |

!!! info "Tudo dentro do projeto — sem projetos extras"
    Toda implementação do Trilho E mora **dentro do repositório `tempestroid`**:
    metade Python no pacote `tempestroid/`, metade Kotlin/Compose em
    `android-host/`. Nunca criar repositório, pacote PyPI, plugin ou app separado.
    O único movimento permitido é um **módulo dedicado novo** por área (ex.:
    `navigation.py`, `animation.py`), sempre re-exportado pelo `__init__.py`.

## Trilho H — design system: componentes estilizados (M3 + API Chakra)

Elevar o catálogo de **46 componentes** já existentes (no engine `tempest-core`)
a um **design system bonito e coeso**, ancorado visualmente em **Material 3** com
a **ergonomia de API do Chakra UI** (`variant`/`size`/`color_scheme` + tokens de
tema). Alvo de produto: **pesquisadores acadêmicos** montam apps Android de
validação de resultados (junto com o Trilho G de
inferência ONNX) com pouco esforço e visual profissional. Plano fase-a-fase em
[`docs/plan-design-system.md`](plan-design-system.md).

| Fase | Escopo | Risco | Status |
|---|---|---|---|
| H0 | Sistema de tokens: paleta tonal M3 + `color_scheme`s, escalas de espaçamento/raio/tipografia/elevação/motion; `Theme` resolve, `Style` referencia | **alto** | ✅ done (tempest-core 0.2.0, #109) |
| H1 | API de variantes (Chakra): `variant`/`size`/`color_scheme` → `Style` via tema + estados (hover/press/disabled/focus); `Button` piloto | **alto** | ✅ done (tempest-core 0.3.0 + Qt #112 + Compose #113 + conformância #114) |
| H2 | Kit base ação/entrada estilizado: Button/IconButton (+ sistema de ícones)/Input/Checkbox/RadioGroup/Switch/Select/Slider + inputs BR | médio | ✅ done (tempest-core 0.4.0 + Qt/Compose #116, device-verificado) |
| H3 | Superfície & layout estilizado: Card (elevated/filled/outlined), Surface, Divider, Stack helpers, Container, Grid, ListTile, Accordion | baixo | ✅ done (tempest-core 0.5.0 + Qt + Compose + conformância) |
| H4 | Data display & feedback estilizado: Badge/Tag/Chip/Avatar, Alert/Banner, Progress/Spinner, Skeleton, Tooltip, Stat, Rating, EmptyState, SegmentedControl, Stepper | baixo | ✅ done (tempest-core 0.6.0 + Qt + Compose + conformância) |
| H5 | Navegação estilizada: AppBar/CollapsingAppBar, NavBar, Drawer/Sidebar, Breadcrumb, Burger, Footer, Header, Scaffold, SearchBar, Tabs (skins M3 sobre os hosts do E0) | médio | ✅ done (tempest-core 0.7.0 + skin pass + conformância) |
| H6 | Componentes de pesquisa (liga ao G): MetricCard/StatCard, wrappers de gráfico (canvas E7), DataTable estilizada, ConfidenceBadge, DetectionOverlay (ort-vision-sdk), ImagePicker→ResultView | médio | ✅ done (tempest-core 0.8.1 + Qt + conformância) |
| H7 | Galeria (storybook) + docs tutorial-first bilíngues + dark/RTL verificados + conformância (matriz representativa) de tokens/variants | baixo | ✅ done (storybook + docs + dark/RTL Qt + matriz H1–H6) |

!!! warning "Trilho cross-repo — três camadas, dois repositórios"
    Diferente do Trilho E (tudo em `tempestroid`), o Trilho H atravessa **dois
    repos** porque o engine foi extraído (v0.13.0): camada IR/tokens/componentes
    → **`tempest-core`**; renderer Qt → **`tempestroid`**; renderer Compose →
    **`android-host`**. Cada fase só fecha com as **três camadas casadas** +
    conformância nos dois tradutores `Style`. Tokens/variantes são **aditivos** —
    `Style` cru continua aceito, apps existentes não quebram. Nenhum pacote PyPI
    novo: tudo dentro do ecossistema `tempest-core` + `tempestroid`.

## Trilho G — inferência ONNX + stack científica no device (investigação)

Rodar inferência de modelos `.onnx` **dentro do app Android nativo** usando o
[`ort-vision-sdk`](https://github.com/mauriciobenjamin700/ort-vision-sdk), com
`numpy` / `pandas` / `scikit-learn` funcionando no aparelho. **Investigação
primeiro** — a viabilidade (qual caminho, quais wheels fecham) é o entregável
inicial. Pesquisa fundamentada em
[`docs/research/onnx-ml-stack.md`](research/onnx-ml-stack.md).

| Fase | Escopo | Risco | Status |
|---|---|---|---|
| G0 | Spike de viabilidade: deps reais do SDK, decidir caminho CPython-puro vs inferência-nativa, levantar EPs do device-alvo, provar `numpy`+`onnxruntime` no device | médio | ✅ done ([g0-feasibility.md](research/g0-feasibility.md)) — deps/A-B/EPs fechados; **`import numpy` roda no emulador** (wheel `android_24_x86_64` via cibuildwheel 4.1; o `$(BLDLIBRARY)` era bug da 3.4.1). `examples/onnxspike` + `toolchain/build_numpy_x86.sh` |
| G1 | Wheel do `onnxruntime` (ou AAR Maven) + 1 modelo `.onnx` real ponta-a-ponta no device, fora da UI thread/loop + escolha de EP (NNAPI/XNNPACK/QNN, fallback CPU, latência medida) | **alto** | ✅ done (emulador) — caminho **(B) AAR**: `ort-vision-sdk` 0.4.0 (backend plugável) + `AarBackend` (Python) + `OnnxModule` Kotlin feature-gated (`onnxruntime-android:1.26.0`). Um `Classifier` real (squeezenet1.1) roda no emulador via AAR fora da UI thread (top-1 matchstick, 569ms). EP caiu pra **CPU** (NNAPI/XNNPACK fallback no emulador); **EP real + arm64 físico + decode de imagem (Pillow android, G2)** = follow-ups |
| G2 | Caminho de imagem sem OpenCV (Pillow / `BitmapFactory`; cv2 → SDK nativo, não wheel) + pré/pós em `numpy` | médio | ✅ done (emulador) — `decode_image` (Python) bridge → módulo Kotlin `image` (`BitmapFactory`, `src/main`, sem dep pesada): arquivo/bytes → RGB HWC uint8 → ndarray → SDK. **Device-verificado:** `banana.jpg` real → decode nativo → squeezenet → top-1 **banana (83.9%)**, 963ms, **sem opencv-python nem wheel Pillow** na APK (resize fica no shim numpy). Pillow android wheel = futuro só se precisar de ops puro-Python |
| G3 | Otimização de execução: pipeline `.onnx`→`.ort` + quantização (INT8/fp16); avaliar `onnxruntime-extensions` (pré/pós no grafo) | médio | ✅ done (emulador) — `tempest optimize model.onnx -q int8` (host): INT8 dynamic quant + conversão `.ort` (`cli/onnx_optimize.py`). squeezenet1.1 → `.int8.ort` **72% menor** (4840→1337 KiB). **Device-verificado:** o `.ort` quantizado roda via AAR no emulador — banana 81.5% (vs 83.9% fp32), 925ms (vs 819ms fp32: INT8 ganha **tamanho**, não latência no CPU EP do emulador). fp16 via onnxconverter-common (opcional). `onnxruntime-extensions` (pré/pós no grafo) = follow-up |
| G4 | Entrega e storage do modelo: embutido vs download+cache, `mmap` no load, Play Asset Delivery p/ modelos grandes | médio | ✅ done (emulador) — **ambas as estratégias provadas no device:** **embutido** (asset no bundle, G1-G3) + **download+cache+verify** (`native/model_store.py` `ensure_model`: cache-first, sha256, off-loop, stdlib). Device-verificado: app baixa squeezenet de localhost (adb-reverse) → cache `…/cache/tempest_models/` → classifica banana (`source=download`, 921ms). `mmap` implícito no load-by-path da AAR. (Fix de host de brinde: TMPDIR não chegava no interpretador embarcado — quebrava todo `tempest serve` — + passthrough de env por intent com allowlist `VISIONSPIKE_`/`TEMPEST_`.) Play Asset Delivery = futuro p/ modelos grandes |
| G5 | (opcional) `pandas` no device — feature-engineering tabular | médio | ⏳ planejado |
| G6 | (opcional) `scipy` + `scikit-learn` + `scikit-image` no device — ML clássico + img (skimage gated atrás do scipy) | **alto** | 🔬 spike de viabilidade feito ([g6-sklearn-feasibility.md](research/g6-sklearn-feasibility.md)) — **scipy 1.18.0 + scikit-learn 1.9.0 cross-compilam para `android_26_x86_64` com clang puro, ZERO Fortran**: o "calcanhar" sumiu upstream (scipy fortran-free via `-D_without-fortran` + scipy#18566 fechado; OpenBLAS `NOFORTRAN=1 C_LAPACK=1` = LAPACK em C/f2c). Wheels buildadas (`build_openblas_x86.sh`/`build_scipy_x86.sh`/`build_sklearn_x86.sh`), OpenMP via NDK `libomp`. Pendente: `import` on-device + rebuild arm64 |
| G7 | Encolher APK: custom onnxruntime build + modelo quantizado + ABI splits + trim | médio | 🚧 em progresso — **lever 1 (foreign-ABI dead-weight) landado:** `assets/python` empacotava `.so` das DUAS ABIs mas o APK roda em uma só (`abiFilters`); o generated-assets dir acumulava entre trocas de ABI no mesmo checkout. Fix no `build.gradle.kts` (limpa outputDir + exclui `*-<abi-não-alvo>-linux-android.so`) + **lever 2:** trim numpy runtime-dead (`tests` 7.7M/`f2py`/`_pyinstaller`/`*.pyi`, pure-python). **APK x86_64 73M→57M (−16MB, −22%), device-verificado** (counter tap 0→3 + numpy import/sum/dot). R8 OFF (interpretador chama Kotlin por-nome via JNI → quebra sem keep-rules; ganho dex-only). Falta: custom onnxruntime reduced-op + (talvez) R8 com keep-rules |

!!! warning "Dois caminhos, decisão em G0"
    **(A) CPython puro** cross-compila `onnxruntime`+`numpy`(+`pandas`/`sklearn`)
    como wheels Android (padrão B1 = `pydantic-core`) e o SDK roda no
    interpretador embarcado. **(B) Inferência nativa** usa o AAR
    `onnxruntime-android` (Kotlin/C++) com um shim sobre a ponte JNI, evitando a
    wheel C++ mais pesada. `scipy`/`sklearn` são o calcanhar (Fortran/LAPACK +
    OpenMP) — por isso G5/G6 são opcionais e não bloqueiam o caminho de visão
    (G0→G4, que inclui aceleração por EP, formato `.ort`/quantização e entrega do
    modelo). Tudo **dentro do repositório**: metade Python em `tempestroid/`,
    metade Kotlin em `android-host/`; o `ort-vision-sdk` segue dependência
    externa (não re-implementado aqui).

## Manutenção — skills de qualidade (`.claude/skills/`)

Guardas de saúde do framework, encadeadas pelos *gates*:

| Skill | Comando | Papel |
|---|---|---|
| `framework-guard` | `make gate` (`check.sh [--quick]`) | ruff + pyright (strict) + pytest + `mkdocs build --strict` + heurísticas de convenção |
| `docs-sync-check` | `make docs-sync` | README ↔ exports vivos ↔ comandos CLI ↔ tabelas de fase |
| `phase-closer` | `close.sh <fase>` | valida o "feito quando" de uma fase A–D antes de marcar ✅ |
| `android-doctor` | `make doctor` (`check.sh [--quick]`) | valida o toolchain B: SDK/NDK, Gradle wrapper 8.11.1, JDK, device arm64 + gotcha MIUI, runtime staged |
| `dual-verify` | `make dual-verify` (`verify.sh [APP]`) | verificação dual obrigatória: *gate* Qt + (havendo device) build/fluxo/screenshot no Compose |
| `parity-phase` | `make parity PHASE=…` (`plan.sh <E-id>`) | conta-parte do `phase-closer` para o Trilho E: spec da fase + invariante das três camadas + *gate* |

## Próximos passos abertos

Trilhos A–D, B (B0–B6) e E (E0–E9) estão **concluídos** e verificados em device:
os **dois renderizadores** (Qt + Compose) suportam o conjunto completo de
widgets, incluindo os inputs com valor no aparelho. O que resta é estabilização
para distribuição (Trilho F — ver [`docs/plan-stable.md`](plan-stable.md)):

- **F2 — validar as capacidades nativas restantes no device** (1 PR por grupo):
  geolocation, câmera+áudio, share, bluetooth, connectivity+permissões,
  biometria plena (digital cadastrada) e push FCM real (precisa
  `google-services.json`). A metade Python já é testada off-device; falta o
  exercício em hardware (`make doctor` → `make apk-install` → `dual-verify`).
- **F4 — distribuição profissional:** APK release-assinado standalone (keystore
  própria), ícone adaptativo (`tempest icon --adaptive`) e matriz de cobertura
  device dos widgets/nativas restantes.
- **F7 — alvo de device sem hardware:** emulador headless x86_64 (provado E2E),
  falta empacotar em `make emulator-verify` + camada B (testes JVM do Compose).
- **F8 — emulação estável + visualização nativa:** camada de confiabilidade
  sobre o F7 — AVD reprodutível, boot por snapshot, auto-recuperação, **pool de N
  emuladores isolados** (sharding da suíte), screenshot/regressão visual e
  `scrcpy` (espelhamento ao vivo no WSLg). Tira a dor recorrente do emulador.
  **Boot-proven (2026-06-14)** + **pool sharded PROVADO em paralelo (2026-06-20):**
  `make emulator-pool N=2` bootou 2 instâncias isoladas (`-read-only` do snapshot
  `golden`, portas próprias) → shardou counter+forms → ambos PASS → teardown limpo.
  Destravou no caminho a causa-raiz crônica do code-push: `resolve_project` subia
  pro `pyproject.toml` do framework ao servir um example → `tree_signature` no repo
  inteiro (~6.8s) → timeout; agora pula o pyproject do framework → signature 0ms,
  app monta. `provision_avd.sh`/`emulator_snapshot.sh`/`emulator_pool.sh`/
  `visual_regression.py`/`emulator_verify.sh` + alvos `make` + runbook bilíngue.
  Pendente menor: N>2 em hardware maior, screen-record mp4, android-doctor checks.
- **F9 — driver de testes nativo estilo Playwright:** ✅ **construído** —
  `tempestroid/testing/` (`Page`/`Locator`/auto-wait + `HeadlessBackend` +
  `EmulatorBackend` + `EmulatorPool`) + `tempest uitest <file> --target
  headless|emulator [-j N]` + `examples/*/test_*.py`. API de automação de UI
  **cross-renderer** (mesmo script no backend in-process **e** no Compose real do
  emulador), com **auto-wait** (sem `sleep`), locators por Semantics/texto/key,
  rodando em paralelo/sharded sobre o pool do F8. O "Playwright do nativo".
  **Alvo `headless` PROVADO verde** (2026-06-20: counter 3/3 PASS — key→tap→
  auto-wait→assert `0→1` + handler async); **alvo `emulator` provado no caminho
  do pool** (F8: `make emulator-pool N=2` shardou counter+forms no Compose real →
  PASS). O pool agora **fixa em `ANDROID_SERIAL`** p/ hosts compartilhados.
  `qt`/`device` reservados (`NotImplementedError`).

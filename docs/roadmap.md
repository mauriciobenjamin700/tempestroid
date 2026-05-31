# Roadmap e fases

O desenvolvimento segue duas trilhas-base e uma trilha de expansão. **Trilho A**
é o framework em Python puro (desktop/CPython). **Trilho B** é o runtime Android
(CPython 3.14 + host Kotlin + ponte JNI + renderizador Compose). **Trilho E** é a
paridade com Flutter/React Native (planejado). O plano completo está em
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

## Trilho E — Paridade Flutter / React Native (planejado)

Roadmap para fechar o gap com o que Flutter + RN oferecem de fábrica. Toda fase
entrega as **três camadas casadas** (IR/diff + renderizador Qt + renderizador
Compose) e só fecha com os **dois renderizadores verdes** + (havendo device)
verificação dual. Spec fase-a-fase em [Plano de paridade](plan-parity.md).

**Sequência.** E0 (navegação) destrava multi-tela e é pré-requisito de quase
tudo; E1–E2 são a base de UX; E3 (animação) é consumida por E0/E2 nas transições;
E4–E9 acoplam menos e reordenam por demanda (exceto E6c←E1 e E3d←E0).

| Fase | Escopo | Risco núcleo | Status |
|---|---|---|---|
| E0 | Navegação e rotas (pilha push/pop, abas, gaveta, botão voltar, deep link) | baixo (reusa diff) | 🔜 |
| E1 | Listas virtualizadas + scroll (lazy, seção sticky, pull-to-refresh, scroll infinito) | médio (diff por janela) | 🔜 |
| E2 | Overlays e feedback (dialog, bottom sheet, toast, tooltip, menu, action sheet) | **alto** (`Scene` + `Path` namespaced) | 🔜 |
| E3 | Framework de animação (controller, tween/curva, implícita, gesto, Hero, shimmer) | **alto** (clock de frames) | 🔜 |
| E4 | Gestos avançados (pan/drag-drop, pinça/zoom, double-tap, dismissible, reorder) | baixo (padrão pronto) | 🔜 |
| E5 | Inputs e formulários (dropdown, time, range, form/validação, autocomplete, OTP, máscara) | baixo | 🔜 |
| E6 | Layout refinado (flex-wrap, pager/carousel, app bar colapsável, tabela, aspect ratio) | baixo | 🔜 |
| E7 | Mídia e gráficos (vídeo, webview, canvas, svg, câmera live, QR, mapa, blur, clip) | médio (IR de canvas) | 🔜 |
| E8 | Plataforma/sistema (haptics, sensores, lifecycle, permissões, biometria, storage, SQLite, push) | baixo (padrão B6 + token p/ stream) | 🔜 |
| E9 | Transversais (tema/dark + MediaQuery, i18n/RTL, acessibilidade, fontes custom + escala) | médio (contexto + RTL) | 🔜 |

!!! info "Tudo dentro do projeto — sem projetos extras"
    Toda implementação do Trilho E mora **dentro do repositório `tempestroid`**:
    metade Python no pacote `tempestroid/`, metade Kotlin/Compose em
    `android-host/`. Nunca criar repositório, pacote PyPI, plugin ou app separado.
    O único movimento permitido é um **módulo dedicado novo** por área (ex.:
    `navigation.py`, `animation.py`), sempre re-exportado pelo `__init__.py`.

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

- **Validar as capacidades nativas expandidas no device:** os módulos Kotlin de
  geo/share/câmera/storage/clipboard/bluetooth precisam ser exercitados num
  device real (rodar `make doctor` → `make apk-install` → `dual-verify`).
- **Inputs no dispositivo (Compose):** o renderizador Kotlin ainda cai para uma
  caixa vazia em alguns widgets de entrada; falta crescer os casos no host. No
  simulador Qt esses widgets já funcionam.
- **Iniciar o Trilho E por E0 (navegação):** pré-requisito de quase tudo;
  começar pela sub-tarefa de núcleo (`E0a`) com `make parity PHASE=E0`.

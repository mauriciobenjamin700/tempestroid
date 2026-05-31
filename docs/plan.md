# tempestroid — Plano do projeto

> Framework pessoal para construir apps **Android nativos** escrevendo **Python tipado**, com um simulador desktop (Qt) e dev loop por QR code estilo Expo/Flutter.

---

## 1. Visão

Poder construir apps Android usando conhecimento e bibliotecas pythônicas (HTTPX, Pydantic e cia.), com:

- **UI nativa** (Jetpack Compose), sem WebView.
- **Estilização "web-like"** declarada por objetos Pydantic tipados (vocabulário do CSS, sem a cascata).
- **Tipagem como referência**, no espírito do FastAPI: você define o tipo uma vez e ele vira validação em runtime + autocomplete no editor.
- **Dev loop instantâneo**: simulador Qt no desktop + celular físico via QR code, ambos com hot reload, controlados por um terminal interativo único.
- **Async-first**: o runtime roda sobre um event loop (asyncio); handlers, hooks de ciclo de vida e chamadas nativas podem ser `async def`. Rodar código assíncrono — HTTPX, I/O, tarefas concorrentes — é o caminho padrão, não a exceção.

É, em essência, um runtime Python embarcado no Android com uma camada de UI declarativa por cima — um "Flutter de Python", focado só em Android.

---

## 2. Escopo e não-objetivos

**É:**

- Android-only.
- Foco em APK sideloaded (instalar direto no aparelho).
- Controle total da toolchain (runtime, ponte, UI, empacotamento).
- Suporte a wheels nativas (Rust/C), com o `pydantic-core` como teste de fogo.

**Não é (decisões conscientes):**

- Não é cross-platform (sem iOS, sem desktop como alvo de produção — o Qt é só simulador de dev).
- Não mira lojas de aplicativo, não precisa de assinatura/distribuição formal.
- Não é um motor de CSS: o estilo é inline tipado, não há seletores, specificity nem cascata.
- Não mira jogos/120fps; é ótimo para apps de dados, formulários e ferramentas.

---

## 3. Arquitetura

### 3.1 A ideia central: uma árvore, múltiplos renderizadores

Você não descreve a UI em widgets nativos diretamente. Descreve uma **árvore de widgets declarativa e tipada** (a IR — representação intermediária, modelos Pydantic). Um **reconciliador** faz o diff entre a árvore nova e a anterior e gera uma lista de **patches**. Cada renderizador sabe aplicar patches do seu jeito:

```
Código Python tipado
        │
        ▼
Árvore de widgets (IR, Pydantic)  ──diff──►  patches
        │
        ├──► Renderizador Qt        (simulador desktop, sem device)
        ├──► Renderizador Compose   (celular: dev via QR e APK final)
        └──► (eventos sobem pela mesma ponte: toque/input → handler → estado → rebuild)
```

O **reconciliador é o mesmo código Python** no desktop e no device. Só muda o renderizador-folha. Toda a divergência entre plataformas fica trancada em dois tradutores de estilo (`Style → Qt`, `Style → Compose`).

### 3.2 Quatro camadas ortogonais

| Camada | Responsabilidade | Origem |
|---|---|---|
| Runtime | Interpretar Python no Android | CPython 3.13+ oficial (PEP 738, `Android/android.py`) |
| Wheels nativas | Cross-compilar dependências com Rust/C | Android NDK + maturin + cibuildwheel/crossenv |
| Ponte | Python ↔ Kotlin (APIs nativas) | pyjnius (ou JNI próprio) |
| Empacotamento | Gerar o APK | Gradle + host Kotlin mínimo |

### 3.3 Onde a tipagem "vaza" (o contrato)

Sem WebView, não há fronteira JS↔Python. O contrato tipado mora na fronteira **Python ↔ Kotlin**, e o Pydantic valida os três pontos de cruzamento, análogo ao request/response do FastAPI:

1. **IR → renderizador**: a árvore serializada que o Compose interpreta.
2. **Eventos → handlers**: payloads que voltam do Kotlin (toque, texto) validados antes de entrar na função Python.
3. **Chamadas nativas**: wrappers tipados sobre os módulos de capacidade (câmera, notificações), expostos como awaitables (ver §3.5).

### 3.4 Regra de ouro de execução

O Python roda **numa thread de fundo** que hospeda um **event loop asyncio**, nunca na UI thread (senão dá ANR). A ponte marshala dados entre a thread do Python e a thread de UI do Compose. O Python roda **no device** (não no laptop): casa com produção e deixa o acesso nativo local, sem proxy de rede.

### 3.5 Async-first

O loop asyncio da thread de fundo é cidadão de primeira classe, não um add-on:

- **Handlers e hooks são `async`-friendly**: `on_click`, hooks de ciclo de vida (`on_mount`/`on_unmount`) e tarefas de fundo podem ser `async def`; o framework agenda no loop em vez de bloquear. Handlers síncronos continuam funcionando.
- **HTTPX e I/O sem medo**: o cliente async do HTTPX, leitura de arquivos, timers e tarefas concorrentes rodam direto. `await` no meio de um handler é o caminho padrão.
- **Estado e rebuild via loop**: quando uma tarefa async termina (ex.: a resposta HTTP chega), ela atualiza o estado e dispara um rebuild. Os rebuilds são **coalescidos no loop** — vários `set_state` no mesmo tick viram um único diff — evitando flicker e trabalho redundante.
- **Chamadas nativas viram awaitables**: APIs Android baseadas em callback (câmera, permissões) são embrulhadas em `Future`/awaitable na ponte, então do lado Python você escreve `photo = await camera.capture()` em vez de gerenciar callback.
- **Cancelamento no unmount**: tarefas async ligadas a um widget são canceladas quando ele sai da árvore (concorrência estruturada), evitando tarefas órfãs.

---

## 4. Sistema de estilo "web-like" tipado

### 4.1 Princípio

Não é uma folha de estilo, é um **objeto de estilo inline tipado** (mais perto do `style` prop do React / CSS-in-JS). Herda o *vocabulário* do CSS como campos Pydantic; descarta a *máquina* (seletores, specificity, herança implícita). Todo estilo é explícito, validado e previsível.

### 4.2 Layout padronizado em flexbox

Flexbox é o denominador comum que os dois backends replicam bem:

- **Compose**: `Row`/`Column` + `Arrangement` + `Alignment` + `weight` ≈ `flex-direction` + `justify-content` + `align-items` + `flex-grow`.
- **Qt**: `QBoxLayout` é flex-like, e o **QSS (Qt Style Sheets) já é uma linguagem tipo CSS** — padding/border/background/radius caem quase direto.

### 4.3 O que mapeia x o que não mapeia

**Mapeia limpo (v1):** flex (direction, justify, align, grow), box model (padding, margin), border + radius, background, cor, tipografia (família, tamanho, peso, alinhamento), dimensões (width/height/min/max).

**Não mapeia bem (limites conscientes / pós-v1):** `:hover` (não existe em toque), grid (possível, mas diverge mais — depois do flex), z-index complexo, `backdrop-filter`, gradientes elaborados, transições/animações (precisam de suporte explícito).

### 4.4 Defesa contra divergência

Os dois tradutores **têm que concordar**. A garantia é um **suite de conformância com golden snapshots**: renderiza o mesmo `Style` no Qt e no Compose e compara. É o que mantém o simulador honesto em relação ao device.

---

## 5. Dev loop: terminal interativo (cockpit único)

`tempest dev` controla os dois alvos ao mesmo tempo: sobe o simulador Qt, sobe o dev server na LAN com o QR, e fica num loop interativo estilo `flutter run`:

```
tempest dev

  ┌──────────────────────┐
  │ ▄▄▄▄▄ ▄ ▄▄ ▄▄▄▄▄      │   Escaneie com o app host
  │ █   █ ▀█▄  █   █      │   na mesma rede Wi-Fi
  │ █▄▄▄█ ▄▀▄  █▄▄▄█      │
  └──────────────────────┘

  Dev server   ws://192.168.0.42:8765   (WSL mirrored)
  Simulador    Qt        ● rodando
  Dispositivo  Pixel 7   ● conectado

  Comandos:
    r  hot reload      (v1: reinicia preservando nada — ver abaixo)
    R  hot restart     (estado limpo)
    s  abrir/recarregar simulador Qt
    d  listar dispositivos
    q  sair
```

### 5.1 v1 = só hot restart

Existe **hot reload** (re-roda o build, faz diff, aplica patch, **preserva estado**) e **hot restart** (re-roda do zero, **perde estado**). Preservar estado é a parte difícil.

**Decisão v1:** começar **só com hot restart** — robusto e simples. O reload com preservação de estado fica como refinamento pós-v1. É a ordem que o próprio Flutter seguiu.

### 5.2 Modelo de conexão (estilo Expo Go)

Um app **host** prebuildado no celular embarca o CPython + o renderizador Compose. O `tempest dev` sobe um dev server na LAN e imprime o QR. Você escaneia, o host puxa o código Python pela rede, roda localmente no celular, e edições disparam restart no simulador **e** no celular ao mesmo tempo. O dev server só faz duas coisas: mandar o código pro host e relayar logs de volta pro terminal.

### 5.3 WSL

Pro celular alcançar o dev server na LAN, usar `networkingMode=mirrored` no `.wslconfig` (compartilha o IP com o Windows). Sem isso, configurar port proxy. ADB via Wireless Debugging (TCP) ou `usbipd-win`.

---

## 6. Estratégia: dois trilhos

O caminho do simulador Qt **não precisa de nada da toolchain Android**. Isso permite paralelizar e ter retorno rápido.

### Trilho A — DX (CPython desktop puro, zero Android)

Reconciliador, IR, modelo de estilo, API tipada de widgets, renderizador Qt, terminal interativo, hot restart no sim. Prova que o framework é gostoso de usar **antes** de encarar Android. Retorno em dias.

### Trilho B — Runtime Android (infra pesada)

Cross-compile do `pydantic-core` arm64, host com CPython embarcado, renderizador Compose, ponte JNI, dev server + QR. Pesado, mas desacoplado: não bloqueia a validação da experiência.

**Convergência:** o host no celular carrega o **mesmo reconciliador do Trilho A**, trocando só o renderizador Qt pelo Compose. O terminal do A5 ganha o alvo "device".

---

## 7. Fases e marcos

Cada fase tem um "feito quando" testável. A ordem dentro de cada trilho é sequencial; os trilhos correm em paralelo após A1.

### Trilho A

- **A0 — Fundação.** Layout do pacote, `pyproject.toml`, `CLAUDE.md`, ferramentas (ruff, pyright/mypy, pytest), `tempest --help`.
  *Feito quando:* `pip install -e .` e a CLI respondem; lint/type-check rodam.
- **A1 — Modelo de estilo + widgets.** `Style` (Pydantic) e primitivos tipados: `Widget` base, `Text`, `Button`, `Column`, `Row`, `Container`.
  *Feito quando:* dá pra montar uma árvore, ela valida, e o type-checker passa limpo.
- **A2 — Reconciliador.** `build → diff → patch`. Dados puros, agnóstico de renderizador (insert/remove/update/reorder).
  *Feito quando:* testes unitários do diff produzem a lista de patches correta.
- **A3 — Renderizador Qt.** Aplica patches em `QWidget`s; tradutor `Style → Qt` (QBoxLayout + QSS).
  *Feito quando:* uma app de exemplo renderiza numa janela Qt a partir da árvore.
- **A4 — Loop de eventos (async).** Integrar asyncio ao loop do Qt (ex.: `qasync`); evento → handler (sync ou `async`) → estado → rebuild coalescido → diff → patch.
  *Feito quando:* um handler `async` que faz `await` (ex.: sleep ou HTTPX) atualiza a tela ao concluir, sem travar a UI.
- **A5 — `tempest dev` (sim).** File watcher, hot restart, loop de comandos (r/R/s/q).
  *Feito quando:* editar `app.py` + `R` reinicia o sim com a UI nova.
- **A6 — Contrato tipado + introspecção.** Handlers tipados e validação Pydantic na fronteira; modo de introspecção (lista de widgets/handlers com schemas, análogo ao `/docs`).
  *Feito quando:* round-trip tipado com validação e erro estruturado.

### Trilho B

- **B0 — CPython Android.** Build do CPython 3.13 para `aarch64-linux-android` (PEP 738).
  *Feito quando:* binário do interpretador para arm64.
- **B1 — Wheels nativas (DERISK CRÍTICO).** Pipeline de cross-compile; `import pydantic` (`pydantic-core` Rust) num Python arm64.
  *Feito quando:* `import pydantic` funciona num celular físico arm64.
- **B2 — Host Kotlin mínimo.** Activity, boot do CPython em thread de fundo, "hello from python".
  *Feito quando:* APK imprime saída do Python no logcat/tela.
- **B3 — Ponte JNI.** pyjnius (ou própria) — chamadas Python ↔ Kotlin nos dois sentidos.
  *Feito quando:* Python dispara um toast/log nativo.
- **B4 — Renderizador Compose.** Composable data-driven que interpreta a IR; tradutor `Style → Compose Modifier`.
  *Feito quando:* a mesma árvore de exemplo do Trilho A renderiza nativa.
- **B5 — Dev server + QR.** Host puxa código pela LAN; hot restart no device.
  *Feito quando:* escanear o QR carrega o app por Wi-Fi e `R` reinicia no celular.
- **B6 — Capacidades nativas.** Notificações (`NotificationManager`, canal obrigatório no Android 8+, permissão `POST_NOTIFICATIONS` no 13+); câmera (via `Intent` primeiro, módulo CameraX depois).
  *Feito quando:* notificação disparada do Python; foto capturada.

### Pós-convergência

- **C — Polimento.** ✅ `tempest new` (scaffold de projeto rodável), `tempest build` (empacota o app como asset + dirige o Gradle do `android-host`), `tempest run` (build + `adb install` + logcat). Hot reload com preservação de estado via `App.swap_view`: no cockpit Qt `r` (e o save) reaplica por diff preservando o estado e cai para restart limpo se incompatível; `R` reinicia do zero; no device o code-push faz `DeviceApp.reload` preservando o estado on-device. (`build`/`run` no device exigem SDK/NDK Android.)
- **D — Conformância.** Suite de golden snapshots Qt vs Compose, no CI.

---

## 8. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Cross-compile de crates Rust mais chato que o esperado | É a fase B1, atacada cedo; pesquisar wheels Android prontas antes de buildar do zero |
| pyjnius assume setup do p4a (pode não casar com CPython oficial) | Validar na B3; ter um JNI próprio como plano B; usar o Chaquopy como referência |
| Os dois tradutores de `Style` divergirem | Suite de conformância com golden snapshots (fase D) |
| tkinter/Qt nunca baterem pixel-a-pixel com o Compose | Sim é para velocidade de iteração; o celular via QR é o teste de verdade |
| Ecossistema de wheels Android se moveu pós jan/2026 | Ligar busca web antes de cravar a B1 — pode poupar semanas |
| Casar o loop asyncio (thread Python) com a threading do Android (UI thread, callbacks) | Uma única fronteira de marshalling na ponte: `call_soon_threadsafe` para entrar no loop, `runOnUiThread` para sair; callbacks nativos resolvem um `Future` no loop |

> **Atenção:** o estado das wheels nativas para Android (suporte do `cibuildwheel`, repositórios de wheels prontas, facilidade do maturin para o target Android) evolui rápido e parte é recente. Verificar o estado atual antes de iniciar a B1.

---

## 9. Estrutura de repositório (proposta)

```
tempestroid/
├── pyproject.toml
├── CLAUDE.md
├── README.md
├── tempestroid-plano.md          # este documento
├── tempestroid/
│   ├── __init__.py
│   ├── style.py                  # Style, Color, Spacing, Edge... (Pydantic)
│   ├── widgets/                  # Text, Button, Column, Row, Container...
│   │   └── __init__.py
│   ├── core/
│   │   ├── ir.py                 # nós da IR (Pydantic)
│   │   ├── reconciler.py         # build / diff / patch
│   │   └── state.py              # estado + loop de rebuild
│   ├── renderers/
│   │   ├── qt/                   # renderizador Qt + Style→Qt
│   │   └── compose/              # bindings do lado Python (renderer em Kotlin)
│   ├── bridge/                   # wrappers JNI (pyjnius)
│   ├── native/                   # módulos de capacidade: notifications, camera
│   ├── devserver/                # servidor LAN, envio de código, relay de logs
│   └── cli/                      # tempest dev/build/run/new + terminal + QR
├── android-host/                 # app host Kotlin (Gradle), renderer Compose, JNI
├── toolchain/                    # scripts CPython Android + cross-compile de wheels
├── examples/
│   └── counter/app.py
└── tests/
    ├── unit/
    └── conformance/              # golden snapshots Qt vs Compose
```

---

## 10. Convenções de código (para o `CLAUDE.md`)

Manter o estilo já consolidado nos outros projetos:

- **Strings:** aspas duplas em tudo.
- **Tipagem:** obrigatória e completa (incluindo `Any` quando necessário); type-checker no CI.
- **Docstrings:** estilo Google, em inglês.
- **Imports:** de nível de módulo via `__init__.py`, mantendo `__all__`.
- **Stack do projeto:** Pydantic (núcleo do modelo), PySide6/Qt (simulador), pyjnius (ponte, fase B). Sem FastAPI/SQLAlchemy/Redis aqui — é um framework, não um serviço web.
- **Async-first:** o core assume um event loop asyncio; preferir APIs async, embrulhar callbacks em awaitables e usar concorrência estruturada para o ciclo de vida das tarefas. No Qt, integrar via `qasync`.
- **Linguagem:** identificadores e docstrings em inglês; comentários explicativos podem ser PT-BR.

Sugestão de fluxo com o Claude Code:

- Trabalhar **uma fase por vez**, sempre fechando no "feito quando".
- Usar o slash command `review-pr` antes de mergear cada fase.
- Manter os testes da fase verdes antes de avançar — especialmente A2 (diff) e D (conformância), que são a espinha dorsal da corretude.

---

## 11. Glossário

- **IR** — Intermediate Representation: a árvore de widgets serializável (Pydantic) que os renderizadores interpretam.
- **Reconciliador** — compara a árvore nova com a anterior e emite patches.
- **Patch** — operação mínima sobre a UI (insert/remove/update/reorder).
- **Renderizador-folha** — quem aplica os patches numa tecnologia concreta (Qt no desktop, Compose no Android).
- **Tradutor de estilo** — converte `Style` (Pydantic) para o vocabulário do backend (QSS/QBoxLayout ou Compose Modifier).
- **Host** — app Android prebuildado que embarca o CPython e roda o código Python (em dev puxa pela LAN; em produção embute).
- **Hot restart** — recarrega do zero, estado limpo (v1).
- **Hot reload** — recarrega preservando estado (pós-v1).

---

## 12. Próximo passo imediato

Começar pelo **Trilho A, fase A0 → A1**: fundação do repo + `Style` Pydantic + os primeiros widgets tipados (`Column`, `Row`, `Text`, `Button`, `Container`). É puro CPython desktop, dá pra ver a árvore de widgets ganhando forma sem tocar em NDK.

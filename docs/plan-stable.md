# tempestroid — Plano de estabilização para uso pelo time (Trilho F)

> **Trilho F — Adoção.** Roadmap fase-a-fase para o time usar o tempestroid em
> projetos reais, de forma **simples e prática, no estilo pythônico**.
> Continuação de [`plan.md`](plan.md) (A–D) e [`plan-parity.md`](plan-parity.md)
> (E0–E9, paridade Flutter/RN, já fechado). Os Trilhos A–E entregaram o
> framework; este Trilho fecha as **três lacunas operacionais** que separam
> "funciona no meu device" de "o time empacota, valida e distribui sem atrito".
>
> **Nível de detalhe.** Cada fase traz `Estado atual` (o que já existe na árvore),
> `Arquivos` (paths reais), `Sub-tarefas` (recorte do tamanho de um agente) e
> `Feito quando` (testável e honesto). É spec de implementação, não só roadmap.

---

## 0. Premissas do trilho

Herda as invariantes consolidadas (um reconciliador / dois renderizadores;
tradutores de estilo espelhados; contrato tipado na fronteira; bridge sem mudança
de C quando possível; **tudo dentro do repositório `tempestroid`** — sem projetos
extras; verificação dual obrigatória com device; `feito quando` lastreado por
testes verdes). Acrescenta uma regra própria:

- **Pythônico acima de tudo.** A superfície de uso é Python puro tipado: o app é
  um módulo com `make_state() -> S` + `view(app) -> Widget`. Toda DX nova
  (templates, exemplos, build) deve reforçar esse contrato, nunca pedir que o
  time escreva Gradle/Kotlin/XML à mão.
- **Regra de ouro do app:** o arquivo do app é **renderer-agnostic** — importa só
  `tempestroid` no topo; `run_qt` entra preguiçoso dentro de `__main__`. (Era a
  causa raiz da tela branca; ver [PR #39].)

| Fase | Escopo | Status | Feito quando |
|---|---|---|---|
| F1 | `tempest build` Gradle por-app: `applicationId` único → apps do time instalam lado a lado | ✅ done (v0.7.0, PR #41) | dois apps tempestroid distintos instalam e rodam simultâneos no mesmo device; `--fast` repackage preservado |
| F2 | Validação on-device das capacidades nativas Kotlin (uma PR de verificação por capacidade/grupo) | 🅿️ adiada (futuro) — grupo no-config ✅ (clipboard/storage/database/secure_storage/system); resto parkeado | cada capacidade exercida no device com evidência (screenshot/dumpsys/log) e resultado tipado; matriz de status verde |
| F3 | `tempest new --template` multi-arquivo + exemplos de chamadas nativas | ✅ done (v0.7.0, PR #43) | `tempest new --template <nome>` gera projeto multi-arquivo rodável (Qt + device) com exemplo nativo; coberto por teste de scaffold |
| F-branding | Ícone + splash no `tempest build` + `tempest icon` (gera de uma imagem) | ✅ done (v0.8.0, PR #47) | ícone default + splash de assets cobrem o boot; `--icon/--splash/--splash-bg` + `tempest icon` device-verificados |
| F4 | Distribuição profissional: APK release-signed standalone (keystore própria) + ícone adaptativo + cobertura device dos widgets/nativas restantes | 🚧 em progresso — **(1) APK release-signed ✅** (`tempest build release-apk`); **(2) ícone adaptativo ✅** (`tempest icon --adaptive` + `tempest build --adaptive-icon/--icon-bg`); **(3) matriz de cobertura de widgets publicada ✅** (`docs/referencia/cobertura.md`, PT+EN); (4) fechar F2 + (5) trim pendentes (device/investigação) | `tempest build release-apk --keystore` produz APK release-assinado instalável fora da Play; `tempest icon --adaptive` gera ícone adaptativo (fg/bg); matriz de widgets/nativas device-verificada |
| F5 | **Harness de device confiável** — loop de validação on-device à prova de queda de USB (timeout por adb, detecção de drop, checkpoint/resume), base única do `dual-verify` | ✅ implementada (off-device) — **gate de toda device-verify futura** (bloqueia F2, device-verify do release-apk/ícone e os leftovers E8/E9); falta o teste de drop com device conectado | rodar os 24 examples no device sem hang (cada app ≤40s); desconectar o USB no meio aborta limpo com `ABORT … usb-drop` — detecção ≤20s no drop mid-run (~38s no pior caso de adb-server morto no start), sem adb wedged — e a re-execução **retoma** dos faltantes; `dual-verify` nunca reporta verde falso |
| F6 | **Trim de tamanho do APK** — enxugar o CPython 3.14 embutido. **Fase-1 (off-device):** pruning seguro de stdlib morta. **Fase-2 (host-side, device-gated):** stdlib-archive/codecs/compressão | 🚧 fase-1 ✅ (PR #74) — baseline real **~39MB** (não ~50MB; já cortado por #70/#71), fase-1 rende ~1MB → **~38MB**; **~20MB exige fase-2 host-side** (Kotlin/C + device, não offline) | **fase-1:** excludes seguros (import trace verde) + APK rebuilda + tamanho documentado + gate verde; **fase-2 (futuro):** APK materialmente menor que boota e roda os examples (Qt + device via F5), custo de 1º boot medido |

---

## F1 — `tempest build` por-app (instalar vários apps lado a lado)

### Objetivo
Cada app empacotado carrega seu próprio `applicationId`, então dois apps do time
(`com.time.vendas`, `com.time.estoque`) instalam **simultâneos** no mesmo
aparelho em vez de um sobrescrever o outro (hoje ambos viram `org.tempestroid.host`).

### Estado atual (já no working tree — falta fechar)
Trabalho em voo (não commitado) em `cli/release_build.py` + `cli/main.py` +
`tests/unit/test_cli.py`:
- `derive_app_id(project_name)` → `applicationId` default a partir do nome.
- `build_apk(app, *, app_id, ...)` → `gradlew assembleDebug -Ptempest.applicationId=<id>`.
- `build_aab(...)` → `gradlew bundleRelease` (loja).
- `build_cmd`/`_run_build`/`_run_run` já despacham com `--app-id`.
- O host Gradle **já** lê `-Ptempest.applicationId` (`android-host/app/build.gradle.kts:42`).
- Testes: `test_build_dispatches_to_apk`, `test_build_uses_given_app_id`,
  `test_build_reports_gradle_failure`.

### ⚠️ Tensão de design a resolver (decisão da fase)
O em-voo **troca o default** de `tempest build` do caminho **repackage sem-Gradle**
(introduzido na v0.6.1: "roda de install PyPI, sem SDK/NDK") para **Gradle
`assembleDebug`** (exige SDK/NDK + checkout `android-host`). É regressão de
portabilidade. Motivo técnico legítimo: o repackage **não reescreve** o package do
manifesto binário, então não dá `applicationId` distinto; só o Gradle dá.

**Resolução recomendada (manter os dois caminhos):**
- `tempest build` → **repackage sem-Gradle** (default, portátil; mantém
  `org.tempestroid.host` — bom para "rodar rápido", um app por vez).
- `tempest build --app-id com.time.x` (ou `--gradle`) → caminho **Gradle**
  (lado-a-lado; exige toolchain). `--release` (AAB) já implica Gradle.
- `derive_app_id` continua, mas só dispara o caminho Gradle quando `--app-id` é
  dado/derivado **explicitamente** para lado-a-lado.

### Arquivos
- `tempestroid/cli/release_build.py` — manter `build_apk`/`build_aab`/`derive_app_id`;
  **não remover** `package_app_apk`/`apk_repack.repackage_host_apk` (caminho repackage).
- `tempestroid/cli/main.py` — `build_cmd`/`_run_build`/`_run_run` despacham
  repackage **vs** Gradle conforme a flag.
- `tempestroid/cli/apk_repack.py` — preservado.
- `android-host/app/build.gradle.kts` — `-Ptempest.applicationId` (já existe).
- `tests/unit/test_cli.py` — manter os 3 testes + 1 que prova o default repackage.

### Sub-tarefas
1. **Decidir + reintroduzir o default repackage** (resolver a tensão acima); manter
   Gradle atrás de `--app-id`/`--gradle`/`--release`. Atualizar docstrings/CHANGELOG.
2. **Commitar o em-voo** numa branch `feat/tempest-build-per-app` + gate verde.
3. **README/CLI table**: documentar os dois caminhos e quando cada um aplica.

### Feito quando
- Dois projetos (`tempest new vendas`, `tempest new estoque`) → dois APKs com ids
  distintos → ambos instalam e abrem no **mesmo device** sem se sobrescrever
  (verificado por `pm list packages | grep time` + screenshot dos dois apps).
- `tempest build` sem `--app-id` continua funcionando **de um install PyPI sem
  SDK/NDK** (caminho repackage preservado).
- `framework-guard` + `docs-sync` verdes.

---

## F2 — Validar as capacidades nativas Kotlin no device

!!! note "Adiada — fazer no futuro"
    O grupo **sem-config** (clipboard/storage/database/secure_storage/system) já
    foi device-verificado (`examples/native_caps/app.py`). Os grupos restantes
    (geolocation, camera+audio, share, bluetooth, connectivity+permissions,
    biometria plena, push FCM) ficam **parkeados para o futuro** — o foco atual é
    o **APK básico e funcional**. Quando retomar, siga "uma PR por grupo" abaixo.

### Objetivo
Sair de "metade Python testada off-device" para **cada capacidade exercida no
aparelho** com evidência, fechando a ressalva registrada no `CLAUDE.md`.

### Estado atual
`NativeModules.kt` (router `handle()`) já tem **todas** as ~20 capacidades fiadas,
com a metade Python unit-testada (`tests/unit/test_native.py`) e re-exportada por
`tempestroid/native/__init__.py`. O bridge usa o envelope `{"kind":"native"}` +
request/response no token `__native_result__:<id>` (sem mudança de C).

**Já device-validado** (CLAUDE.md, 2026-06-04): `haptics`, `lifecycle`, `prefs`,
`sensors`, `background` (enqueue), `biometrics` (alcança o prompt), `push` (local).

**Falta validar no device** (alvo desta fase):

| Capacidade | Módulo Python | Precisa no device |
|---|---|---|
| geolocation | `native/geolocation.py` (`get_position`) | permissão de localização + GPS |
| share | `native/share.py` (`share`/`whatsapp`/`open_url`) | intent chooser + WhatsApp instalado |
| camera | `native/camera.py` (`take_photo`/`record_video`) | permissão câmera + FileProvider |
| audio | `native/audio.py` (`record_audio`/`play_sound`) | permissão microfone |
| storage | `native/storage.py` (`read/write/delete/list_files`) | escopo de arquivos do app |
| clipboard | `native/clipboard.py` (`get_text`/`set_text`) | — |
| bluetooth | `native/bluetooth.py` (`scan`) | permissões BT + hardware |
| system | `native/system.py` (status bar/brilho) | — |
| secure_storage | `native/secure_storage.py` | Keystore |
| database | `native/database.py` (SQLite) | — |
| connectivity | `native/connectivity.py` | toggles de rede |
| permissions | `native/permissions.py` | fluxo de grant |
| biometrics (sucesso pleno) | `native/biometrics.py` | digital cadastrada |
| push (FCM real) | `native/push.py` | `google-services.json` + servidor |

### Arquivos
- `examples/native/<cap>/app.py` — um app mínimo por capacidade (ou um app
  "galeria nativa" com botões por capacidade).
- `android-host/.../NativeModules.kt` — só corrige o que falhar no device
  (handlers já existem); manifesto/`FileProvider` conforme a permissão.
- `tests/unit/test_native.py` — mantém a metade Python; device é evidência manual.

### Sub-tarefas (uma PR por linha, ou agrupando as sem-hardware)
1. **Grupo sem hardware/config** (clipboard, system, database, secure_storage,
   storage) — um app galeria + verificação device numa PR.
2. **geolocation** (permissão + GPS).
3. **camera + audio** (permissões + FileProvider).
4. **share** (chooser + WhatsApp).
5. **bluetooth** (permissões + scan).
6. **connectivity + permissions** (fluxos de grant/toggle).
7. **biometrics pleno** (device com digital) — depende de hardware.
8. **push FCM real** — depende de `google-services.json` + backend (registrar como
   bloqueado por config externa).

### Feito quando
- Cada capacidade do grupo tem evidência on-device (screenshot / `dumpsys` / log)
  e devolve **resultado tipado** (ou `NativeError(code)` previsível).
- Matriz de status no `CLAUDE.md`/README vira verde por capacidade; as bloqueadas
  por config externa ficam explicitamente marcadas, não silenciadas.

---

## F3 — `tempest new --template` multi-arquivo + exemplos nativos

### Objetivo
O time começa um projeto real (multi-arquivo, com chamada nativa) em um comando,
sem copiar exemplo na mão. Reforça o contrato pythônico.

### Estado atual
- `tempest new <nome>` (`cli/scaffold.py`) gera **um** `app.py` (single-file) +
  `pyproject` (`[tool.tempest] app`) + README + `.gitignore`. **Sem** `--template`.
- A infra **multi-arquivo já existe**: `cli/bundle.py`
  (`resolve_project`/`build_bundle`/`extract_bundle`/`tree_signature`) e
  `spec_from_project` já bundlam a árvore inteira para o device (Trilho C).
- Exemplos que tocam nativo hoje: `examples/sysverify`, `examples/platform`.

### Arquivos
- `tempestroid/cli/scaffold.py` — adicionar `--template`; extrair os templates
  para um registro (`TEMPLATES: dict[str, Callable[..., ScaffoldResult]]`),
  mantendo `DEFAULT_APP_TEMPLATE` como `--template default`.
- `tempestroid/cli/main.py` — `new_cmd` ganha `--template/-t` (Typer Option).
- `tempestroid/cli/templates/` (novo pacote, re-exportado) — um módulo por
  template com os arquivos-fonte como strings (sem dependência externa).
- `tests/unit/test_scaffold.py` (ou `test_cli.py`) — cada template scaffolda e o
  resultado **importa + casa o contrato** (`make_state`/`view` presentes).

### Templates propostos (mínimo viável)
1. **`default`** — o single-file atual (compatível).
2. **`multi`** — estrutura multi-arquivo pythônica:
   ```
   meu_app/
   ├── pyproject.toml          # [tool.tempest] app = "app.py"
   ├── app.py                  # make_state() + view(app) — só compõe telas
   ├── state.py                # @dataclass AppState (tipado)
   ├── screens/                # uma função view por tela (Home, Detalhe…)
   │   ├── __init__.py         # re-exporta as telas
   │   └── home.py
   └── components/             # widgets compostos reutilizáveis (Component)
   ```
   Demonstra `Navigator`/`Route` (E0) entre telas e o padrão de imports do projeto.
3. **`native`** — o `multi` + uma tela que usa uma capacidade (`notify()` num
   handler, e um `await get_position()` com `try/except NativeError`), mostrando o
   padrão async + fire-and-forget vs request/response.

### Sub-tarefas
1. **Registro de templates** em `scaffold.py` + `--template` no `new_cmd` (default
   inalterado → sem breaking change).
2. **Template `multi`** (state/screens/components + Navigator) + teste de scaffold.
3. **Template `native`** (notify + get_position com NativeError) + teste.
4. **Docs**: página de tutorial "começando um projeto do time" (padrão tiangolo,
   PT-BR + EN), ligando os três estágios de uso.

### Feito quando
- `tempest new x --template multi` gera projeto multi-arquivo que **roda no Qt**
  (`tempest dev`) e **no device** (`tempest serve`) sem edição.
- `tempest new x --template native` idem, com a chamada nativa funcionando (device).
- Cada template tem teste verde provando o contrato; README/docs atualizados.

---

## F4 — Distribuição profissional (em progresso)

### Objetivo
Sair de "APK pra amigos sideloarem" (debug-signed) para **distribuível de
verdade**: APK release-assinado com keystore própria, ícone adaptativo, e a
cobertura device fechada. Hoje (v0.8.0) já dá pra mandar um APK pros amigos
(`tempest build` → debug-signed, id/ícone/splash próprios, instala por
sideload); F4 cobre o salto para "profissional".

### Sub-tarefas
1. ✅ **APK release-signed standalone** — `tempest build release-apk --keystore
   minha.jks --app-id … --app-version …`: antes só existia APK **debug-signed**
   (`tempest build`) ou **AAB** de loja (`prd`); agora há um **APK** assinado
   com a keystore do publisher para distribuir **fora da Play** (site, loja
   alternativa, link direto) com identidade real. Gradle `assembleRelease` +
   signing config (reaproveita `ensure_release_keystore`/`ReleaseConfig`/
   `_signing_props`; `build_release_apk` em `cli/release_build.py`, target
   `release-apk` em `cli/main.py` → `_run_release_apk`). Saída
   `dist/<project>-release.apk`; verificável por `apksigner verify`.
   **Não cai no fallback `--fast`** — um APK release exige o build real.
   Device-verificação (instalar + abrir) pendente do toolchain Android.
2. ✅ **Ícone adaptativo** — `tempest icon <src> --adaptive` grava o
   `ic_launcher_foreground.png`; `tempest build --adaptive-icon <fg.png>
   --icon-bg <#rrggbb>` emite o adaptive icon real (foreground/background +
   `mipmap-anydpi-v26/ic_launcher{,_round}.xml`), com o PNG quadrado como
   fallback pré-API-26. Lê `adaptive_icon`/`icon_bg` de `[tool.tempest]`;
   Gradle-only (`--fast` avisa). Device-verificação (máscara do launcher)
   pendente do toolchain Android.
3. ✅ **Cobertura device dos widgets** — matriz publicada em
   `docs/referencia/cobertura.md` (PT+EN, na nav MkDocs): todo widget primitivo
   exportado tem case nos DOIS renderizadores (Compose: 62 cases primitivos + 7
   de overlay; sem case → `Box`/`Popup` forward-compat); componentes são lowered
   no Python e nunca chegam ao Kotlin. Gaps de wiring = zero; o que resta é
   device-verificação por widget (rodadas de device-verify das fases E, contínuo)
   e os placeholders device-only sinalizados (`CameraPreview`/`QrScanner`/`MapView`).
   Coluna Compose derivada do `when (node.type)` em `TempestRenderer.kt`.
4. **Fechar a F2** (capacidades nativas restantes no device) — pré-requisito para
   um app "profissional" que use câmera/geo/etc.
5. **Trim de tamanho** — promovido à fase própria **F6**; ver a seção F6. Saiu de
   "opcional" porque o peso do APK é o maior atrito de adoção. Achado ao medir
   (PR #74): baseline real ~39MB (não ~50MB), fase-1 off-device rende ~1MB; ~20MB
   exige fase-2 host-side device-gated.

### Feito quando
- `tempest build --release-apk --keystore …` produz um `.apk` release-assinado
  que instala num device e abre, assinado com a chave do publisher (verificável
  por `apksigner verify`).
- `tempest icon --adaptive` gera um adaptive icon que o launcher mascara.
- A matriz de widgets/nativas device-verificada está publicada e verde nos itens
  prioritários.

---

## F5 — Harness de device confiável (gate de toda device-verify futura)

### Motivação (incidente 2026-06-13)
A validação on-device é o **gargalo real** do trilho de estabilização: F2, o
device-verify do `release-apk`/ícone adaptativo e os leftovers E8/E9 todos
dependem de um loop de aparelho que funcione de ponta a ponta. Hoje ele **não é
confiável**. Rodando `toolchain/validate_gallery.sh` (24 examples via code-push),
o aparelho **desanexou do USB do WSL** no 2º app (`brforms`): nenhuma chamada
`adb` tem `timeout`, então `cap_md5`/`screencap` **travaram indefinidamente**, o
harness ficou 25 min preso, perdeu 23/24 apps (só `animation` chegou a `PASS`),
deixou o `adb server` wedged (`adb devices` → rc=124) e `lsusb` parou de ver o
device. Conclusão: antes de gastar device-verify em F2/E, o **loop precisa ser à
prova de queda**.

### Objetivo
Um loop de device que: **(1)** nunca trava — toda chamada `adb` com `timeout`;
**(2)** detecta queda de USB/`adb` e **aborta limpo** com diagnóstico (sem deixar
`adb` wedged); **(3)** faz **checkpoint por-app** e é **re-rodável** (retoma sem
refazer os já-verdes); **(4)** é a **base única** que `dual-verify` e o agente
`device-verifier` chamam — nunca um script ad-hoc por fase.

### Estado atual
- `toolchain/validate_gallery.sh` existe mas está **untracked** (não commitado) e
  **frágil**: chamadas `adb` cruas, sem detecção de drop, sem resume, mata só o
  grupo do `serve` no caminho feliz.
- `toolchain/_diag_hotreload.sh` (untracked) — diagnóstico de hot-reload, mesma
  fragilidade.
- `.claude/skills/dual-verify/verify.sh` e `.claude/skills/android-doctor/check.sh`
  existem mas não detectam um device que **cai no meio** (só checam no início).

### Arquivos
- `toolchain/device_loop.sh` (novo) — helper compartilhado: `adbq() { timeout
  "${ADB_TIMEOUT:-20}" adb "$@"; }`, `device_alive()` (cruza `adb get-state` +
  `lsusb`), `abort_clean()` (mata serve group + `adb kill-server`), sourced pelos
  harnesses. Sem dependência externa (estilo do resto da toolchain).
- `toolchain/validate_gallery.sh` — **commitar** + endurecer: trocar todo `adb`
  por `adbq`; pré-checar `device_alive` antes de cada app (drop → grava
  `ABORT <app> usb-drop` no RESULTS e sai com código distinto); **resume** (lê o
  RESULTS no início e pula apps já `PASS`); cleanup sempre mata o serve group.
- `toolchain/_diag_hotreload.sh` — commitar + mesmo wrapper `adbq`.
- `.claude/skills/dual-verify/verify.sh` — chamar o harness endurecido; ao detectar
  `ABORT … usb-drop`, reportar honestamente "device half abortou em `<app>`" e
  **falhar** (nunca verde falso), com o passo de recuperação `usbipd attach`.
- `.claude/skills/android-doctor/check.sh` — novo check "device estável" (2
  leituras de `adb get-state` espaçadas + `lsusb` Android visível) e registrar o
  gotcha usbipd-WSL nas instruções de recuperação.

### Sub-tarefas
1. **`device_loop.sh`** (helper `adbq`/`device_alive`/`abort_clean`) + commitar os
   dois harnesses untracked migrados pra ele.
2. **Resume + drop-detect** no `validate_gallery.sh` (checkpoint por-app; abort em
   ≤20s; sem adb wedged) — testar desconectando o USB no meio.
3. **`dual-verify`/`android-doctor`** consomem o helper e reportam drop sem fingir
   verde; documentar a recuperação `usbipd attach --wsl --busid <id>` (Windows).
4. **README/CLAUDE.md**: a regra "device-verify passa pelo harness F5" + a nota do
   gotcha USB-WSL.

### Feito quando
- Com o device conectado, o harness valida os 24 examples (screenshots + tabela
  PASS/FAIL) **sem nenhum hang** — cada app limitado a ~40s.
- Desconectar o USB no meio → aborta em ≤20s com `ABORT … usb-drop`, mata o
  `serve`, **não** deixa `adb` wedged; a **re-execução retoma** dos apps faltantes
  (não refaz os `PASS`).
- `dual-verify` reporta honestamente "device half abortou" quando cai — nunca
  verde falso — e `android-doctor` pega o device instável antes do build.
- `framework-guard` verde (os scripts em `toolchain/` ficam fora dos gates Python,
  mas o `dual-verify`/`android-doctor` rodam limpos).

---

## F6 — Trim de tamanho do APK (baseline real ~39MB)

### Por que isso importa (alavanca direta de adoção)
O peso do APK é o **maior atrito prático** para o time adotar o tempestroid: cada
app que mandam pros colegas é um download/sideload, cada `tempest build`/`install`
move os bytes pro device, e numa loja alternativa/link direto o tamanho afasta
instalação. Um app "olá mundo" deveria ser o mais leve possível.

### ⚠️ Correção do alvo (medido em 2026-06-13, PR #74)
A meta inicial "~50MB → ~20MB" foi calibrada contra um **baseline velho**. Medido
de verdade, o APK lean (debug, arm64, sem features extras) já pesa **~39MB**, não
~50MB — o grosso já tinha sido cortado por **#71** (`material-icons-core`) e **#70**
(feature-gating de camera/qr/push/video). O **piso é alto e em boa parte
irredutível** sem mexer no host:

| Componente | Tamanho | Redutível? |
|---|---|---|
| nativos (`libpython` 5.8MB + `libcrypto` 3.7MB + …) | ~11MB | **não** — já totalmente stripados (`llvm-strip` = 0 bytes) |
| `pydantic_core` (wheel nativo) | ~4.6MB | não (dependência core) |
| `pydantic` (puro-py) | ~2.0MB | não |
| stdlib necessária + tempest_core + framework | resto | pouco |
| stdlib morta (test/REPL/wsgiref/lib-dynload de teste) | ~1-2MB | **sim** (off-device, seguro) |

**Conclusão honesta:** o único lever seguro off-device (excludes no
`build.gradle.kts`) rende **~1MB**. Chegar a ~20MB **não é possível** só com
pruning seguro off-device — exigiria mudança no host (stdlib como arquivo único
montado em runtime, ou dropar codecs CJK) que é **Kotlin/C + device-gated**, fora
do escopo de uma fase offline. O alvo realista off-device é **~37-38MB**; ~20MB
vira um esforço host-side separado (F6-fase-2), device-gated.

### Estado / entregue
- **F6-fase-1 (PR #74, ✅ off-device):** excludes seguros no `CopyPythonStdlibTask`
  (`build.gradle.kts`, source-mode, só assets — prefixo de dev intacto): `_pyrepl/`,
  `wsgiref/`, `doctest.py`, `pydoc.py` + lib-dynload de teste (`_test*.so`,
  `_xxtestfuzz*`, `xxsubtype*`, `xxlimited*`). Todos provados ausentes do grafo de
  import (framework + pydantic + tempest_core) por trace off-device. **39MB → ~38MB**
  (lib-dynload 67 → 54 `.so`). Doc bilíngue "Tamanho do APK" em `docs/guia/build.md`
  (+ `.en`). Caveat conhecido: os excludes vivem no `@TaskAction`, não num `@Input`
  → editar a lista exige `--rerun-tasks`/clean (build limpo aplica certo; só afeta
  re-medição em dev) — documentado nos deploy notes do PR.

### F6-fase-2 (host-side, device-gated — NÃO offline)
Para ir materialmente abaixo de ~38MB, os levers restantes precisam do host +
validação no device (depende do F5):
- **stdlib como arquivo único** (zip/`.pyc` em um `.zip` no `sys.path`) montado em
  runtime em vez de ~1500 arquivos soltos — corta overhead de filesystem + permite
  compressão; precisa de mudança no `extractAssets`/boot (Kotlin/C) e medição de
  custo de 1º boot (o splash cobre).
- **dropar codecs CJK** da stdlib (`encodings/`) se nenhum app precisar — economia
  média, risco médio (validar locale/i18n no device, cruza com E9).
- **compressão dos assets** com descompressão no boot.

### Arquivos
- `android-host/app/build.gradle.kts` — `CopyPythonStdlibTask` (excludes; fase-1 ✓).
- `toolchain/02_stage_deps.sh` / `00_fetch_cpython.sh` — se a allow/deny-list migrar
  pra etapa de staging.
- `MainActivity` (`extractAssets`) — fase-2: stdlib-archive/compressão no boot.
- `docs/guia/build.md` (+ `.en`) — tabela antes/depois + piso documentado (fase-1 ✓).

### Feito quando
- **Fase-1 (✅):** `build.gradle.kts` dropa a stdlib morta com segurança (import
  trace verde), APK rebuilda limpo, tamanho medido/documentado, gate verde.
- **Fase-2 (futuro, device-gated):** se perseguida, `tempest build` produz um APK
  materialmente menor que ainda boota o interpretador e roda os examples nos dois
  renderizadores (Qt + device via F5), sem `ImportError`, com custo de 1º boot
  medido — e o ganho real vs a complexidade do host registrado antes de seguir.
- A redução está medida e documentada (antes/depois por componente).
- Nenhum módulo necessário em runtime foi removido (provado pela galeria F5 verde).

---

## Ordem sugerida e dependências

```
F1 (build por-app) ──► desbloqueia distribuir vários apps do time         ✅
F3 (templates)     ──► acelera começar projetos; usa F1 para empacotar     ✅
F4 (1)(2)(3)       ──► distribuição profissional (release-apk/ícone/matriz) ✅
F5 (device loop)   ──► GATE: harness de device à prova de drop             ⬜
   └─► F2 (native device) ─┐
   └─► device-verify       ├─► só confiáveis DEPOIS do F5
   └─► leftovers E8/E9 ────┘
F6 (trim APK)      ──► fase-1 ✅ ~39→~38MB (off-device); fase-2 ~20MB = host  🚧
```

F1/F3/F4(1-3) já entregaram criar + distribuir. **F5 é o novo gate**: a validação
on-device era o gargalo frágil (queda de USB trava o loop), então F2, os
device-verify pendentes e os leftovers E8/E9 só são confiáveis depois que o
harness de device existir. **F6 (trim do APK):** a fase-1 off-device já cortou a
stdlib morta com segurança (~39MB → ~38MB, PR #74); o ganho grande (alvo ~20MB) é
**fase-2 host-side device-gated**, não off-device — então passou a depender do F5
como qualquer outro device-verify. Fechar F5 → device-verify deixa de ser aposta
e destrava a fase-2 do F6.

### Próximos passos (pós-v0.13.0)

v0.13.0 publicada: o engine compartilhado foi extraído para **`tempest-core`** (na
PyPI) e o `tempestroid` agora o adota como dependência (cópia vendada dropada;
`tempestroid/_adopt.py` aliasa `tempest_core.*` sob o path histórico). F4 (1)(2)(3)
já entregues (v0.12.0).

**F5 é o gate.** A queda de USB de 2026-06-13 mostrou que device-verify sem um
harness à prova de drop é tempo perdido — então **F5 vem primeiro** e desbloqueia
todo o resto. Ordem de alavanca:

1. **F5 — harness de device confiável** (pré-requisito formal; ver seção F5):
   `adbq`/timeout em toda chamada adb, detecção de queda de USB com abort limpo,
   checkpoint/resume por-app, `dual-verify`/`android-doctor` consumindo o helper.
   Sem isso, F2 e os device-verify abaixo não são confiáveis.
2. **Device-verify do já-mergeado** (barato — código pronto, só rodar **via F5**):
   adoção do `tempest-core` no device (rodar a galeria pelo harness novo);
   `release-apk` instala/abre + `apksigner verify`; `--adaptive-icon` mascarado
   pelo launcher (screenshot).
3. **F6 — trim de tamanho.** Fase-1 off-device **já entregue** (PR #74): pruning
   seguro da stdlib morta, **~39MB → ~38MB**. O alvo grande (~20MB) é **fase-2
   host-side device-gated** (stdlib-archive/codecs/compressão — Kotlin/C + device),
   então depende do F5. Baseline real é ~39MB (não ~50MB; já cortado por #70/#71).
   Ver seção F6.
4. **F2 — native device** (1 PR por grupo, **via F5**): geolocation, camera+audio,
   share, bluetooth, connectivity+permissions, biometria plena (digital
   cadastrada), push FCM real (`google-services.json` + envio server).
5. **Leftovers E8/E9 no device** (via F5): TalkBack audível (E9), corpo real do
   WorkManager worker (E8), sucesso pleno da biometria (E8).

[PR #39]: https://github.com/mauriciobenjamin700/tempestroid/pull/39

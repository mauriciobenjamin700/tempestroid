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
| F4 | Distribuição profissional: APK release-signed standalone (keystore própria) + ícone adaptativo + cobertura device dos widgets/nativas restantes | 🚧 em progresso — **(2) ícone adaptativo ✅** (`tempest icon --adaptive` + `tempest build --adaptive-icon/--icon-bg`); (1) APK release-signed em PR separado; (3) matriz device, (4) fechar F2, (5) trim pendentes | `tempest build release-apk --keystore` produz APK release-assinado instalável fora da Play; `tempest icon --adaptive` gera ícone adaptativo (fg/bg); matriz de widgets/nativas device-verificada |

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

## F4 — Distribuição profissional (planejado)

### Objetivo
Sair de "APK pra amigos sideloarem" (debug-signed) para **distribuível de
verdade**: APK release-assinado com keystore própria, ícone adaptativo, e a
cobertura device fechada. Hoje (v0.8.0) já dá pra mandar um APK pros amigos
(`tempest build` → debug-signed, id/ícone/splash próprios, instala por
sideload); F4 cobre o salto para "profissional".

### Sub-tarefas
1. **APK release-signed standalone** — `tempest build --release-apk --keystore
   minha.jks --app-id … --app-version …`: hoje só existe APK **debug-signed**
   (`tempest build`) ou **AAB** de loja (`--release`); falta um **APK** assinado
   com a keystore do publisher para distribuir **fora da Play** (site, loja
   alternativa, link direto) com identidade real. Gradle `assembleRelease` +
   signing config (reaproveitar `ensure_release_keystore`).
2. **Ícone adaptativo** — `tempest icon --adaptive` gera as camadas
   foreground/background + o `mipmap-anydpi-v26/ic_launcher.xml` (adaptive icon),
   para o launcher aplicar a máscara (arredondado/squircle) como um app nativo.
   Hoje o ícone é um PNG quadrado simples (sem máscara do launcher).
3. **Cobertura device dos widgets** — matriz de quais widgets do Trilho E
   renderizam no Compose vs. só no Qt; fechar os gaps prioritários.
4. **Fechar a F2** (capacidades nativas restantes no device) — pré-requisito para
   um app "profissional" que use câmera/geo/etc.
5. **Trim de tamanho** (opcional) — investigar reduzir o ~58MB do CPython
   embutido (stdlib pruning, compressão) para apps pequenos.

### Feito quando
- `tempest build --release-apk --keystore …` produz um `.apk` release-assinado
  que instala num device e abre, assinado com a chave do publisher (verificável
  por `apksigner verify`).
- `tempest icon --adaptive` gera um adaptive icon que o launcher mascara.
- A matriz de widgets/nativas device-verificada está publicada e verde nos itens
  prioritários.

---

## Ordem sugerida e dependências

```
F1 (build por-app) ──► desbloqueia distribuir vários apps do time
F3 (templates)     ──► acelera começar projetos; usa F1 para empacotar
F2 (native device) ──► transversal; pode correr em paralelo, PR por capacidade
```

F1 e F3 são as de maior alavanca para o time (criar + distribuir). F2 é
incremental e paraleliza bem (uma capacidade por PR). Fechar as três → tempestroid
"estável para uso em produção interna" no estilo pythônico que o time já escreve.

[PR #39]: https://github.com/mauriciobenjamin700/tempestroid/pull/39

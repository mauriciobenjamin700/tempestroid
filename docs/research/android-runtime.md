# Pesquisa — rodar CPython recente no Android (Trilho B)

> Levantamento web (2025–2026) para fundamentar as fases B0–B6 do `docs/plan.md`.
> Fontes primárias citadas. Datas/versões verificadas em maio/2026.
> **Atenção:** o ecossistema muda rápido — reconfirmar versões antes de cravar a B1.

---

## TL;DR — caminho recomendado

| Fase | Decisão fundamentada | Por quê |
|---|---|---|
| **B0** runtime | **CPython 3.14 binary release oficial** (PEP 738, Tier 3). Fallback: `Android/android.py` para build custom. | 3.14 (out/2025) **passou a publicar binários Android oficiais** — elimina a B0 do "buildar do zero". |
| **B1** wheels nativas | **cibuildwheel ≥ 3.1** para cross-compilar `pydantic-core` arm64. | Suporte Android oficial no cibuildwheel desde 3.1.0 (jul/2025); caminho recomendado para Py 3.13+. Sem wheel oficial de pydantic-core. |
| **B2** embedding | Copiar o modelo do **CPython `Platforms/Android/testbed/`** (`PyConfig`/`Py_InitializeFromConfig`). Rodar o interpretador em **thread de fundo** (padrão python-for-android). | É o blueprint oficial de embedding; testbed roda na UI thread só por ser teste. |
| **B3** ponte | **DECIDIDO: (Y) CPython oficial 3.14 + JNI próprio.** Confirmado por cross-check: a testbed oficial do CPython usa JNI hand-rolled (`external fun runPython`), não pyjnius/Chaquopy. `rubicon-java` morto; pyjnius/p4a usam forks patcheados. | Alinha ao "controle total da toolchain / CPython oficial" do plano. Ver §4 e runbook. |
| **B4** renderer | **Compose data-driven DIY** (`@Composable` recursivo `when(node.type)` + `Modifier` em runtime). **Remote Compose** só como referência (alpha, sem binding Python). | Flexbox→Compose mapeia limpo. Nenhum OSS faz Python→Compose ainda. |
| **B5** dev server | LAN HTTP/WS + QR (modelo Expo). WSL: `networkingMode=mirrored`. | Confirmado oficialmente. |

---

## 1. CPython oficial no Android — PEP 738 (Tier 3)

- **PEP 738 Final.** Android virou plataforma suportada **Tier 3 no CPython 3.13** (não 3.14). Autor/implementador: **Malcolm Smith** (Chaquopy); contato de ABI: Petr Viktorin / Russell Keith-Magee. — <https://peps.python.org/pep-0738/>, <https://peps.python.org/pep-0011/>
- **Triples (64-bit only):** `aarch64-linux-android` (arm64-v8a) e `x86_64-linux-android`. 32-bit excluído do Tier 3.
- **CPython 3.14 (lançado 7/out/2025): "Binary releases for Android are now provided".** Grande melhoria sobre 3.13 (que exigia buildar você mesmo). — <https://docs.python.org/3.14/whatsnew/3.14.html#build-changes>
- **Min API level:** 3.13 = API 21 (Android 5.0); **3.14 = API 24 (Android 7.0)** (de `Android/android-env.sh`).
- **NDK fixado:** `ndk_version=27.3.13750724` (NDK r27) nos branches 3.13 e 3.14.
- **`Android/android.py`** (em `main` → `Platforms/Android/testbed/`): `configure-build` / `make-build` / `configure-host HOST` / `make-host HOST`; atalho `build HOST`; `package HOST` gera tarball em `cross-build/HOST/dist`; `test --connected|--managed` roda a testbed APK (`org.python.testbed`). Build host POSIX (Linux/macOS); precisa `ANDROID_HOME`, `curl`, `java`. — <https://github.com/python/cpython/blob/main/Android/android.py>, doc: <https://docs.python.org/3.13/using/android.html>

**Decisão B0:** usar **3.14 binary release oficial**; só cair pro `android.py` se precisar de build custom (debug, flags). Economiza a fase inteira de cross-compile do interpretador.

---

## 2. Wheels nativas — pydantic-core arm64 (DERISK CRÍTICO)

- **cibuildwheel 3.1.0 (23/jul/2025) adicionou Android oficialmente** (`platform = "android"`, `CIBW_PLATFORM=android`, archs via `CIBW_ARCHS_ANDROID`). Atual **3.4.1 (abr/2026)**. **Caminho recomendado para Py 3.13+** (a própria doc do Chaquopy aponta pra ele). Host Linux x86_64/macOS, precisa Android SDK, frontend `build`/`uv` (pip **não** suportado pra Android). — <https://cibuildwheel.pypa.io/en/stable/platforms/>, changelog <https://cibuildwheel.pypa.io/en/stable/changelog/>, issue <https://github.com/pypa/cibuildwheel/issues/1960>
- **maturin** cross-compila `aarch64-linux-android` **na prática** (NDK + `cargo-ndk` ou linker explícito), mas **não é target oficialmente listado/testado**. Bug recente #2945 (jan/2026, "not planned") na detecção `platform.system()=="android"` no port nativo — cibuildwheel contorna; maturin "pelado" pode precisar de patch. — <https://www.maturin.rs/platform_support.html>, <https://github.com/PyO3/maturin/issues/2945>
- **pydantic-core: SEM wheels Android oficiais** (PyPI 2.47.0 só tem manylinux/musllinux/macOS/Win). **Não está** no repo Chaquopy nem no BeeWare mobile-wheels. → **buildar você mesmo com cibuildwheel 3.1+.** O repo `Eutalix/android-pydantic-core` (fresco, v2.46.3 mai/2026, Py 3.9–3.13) é **só Termux** (tag `linux_aarch64`, não PEP 738 `android_*`). — <https://github.com/Eutalix/android-pydantic-core>, <https://github.com/pydantic/pydantic-core/issues/1474>
- **Tag PEP 738:** `android_<api>_<abi>` (ex.: `android_24_arm64_v8a`). **PyPI já aceita upload de wheels Android** (warehouse PR #17559). — <https://peps.python.org/pep-0738/>
- **Repos prontos** (não têm pydantic-core, mas têm o pesado): Chaquopy `pypi-13.1` (numpy/pandas/scipy/cryptography/pillow/tensorflow...) e **BeeWare mobile-wheels** (~40 pacotes, `android_24_arm64`/`android_24_x86_64`; binários Android hospedados no índice do Chaquopy). — <https://chaquo.com/pypi-13.1/>, <https://beeware.org/mobile-wheels/>
- **crossenv**: engana pip/setuptools a cross-compilar (só path setuptools, **não** Rust; host Linux; versões build/host iguais). Mecanismo legado, parcialmente superado pelo cibuildwheel. — <https://github.com/benfogle/crossenv>

**Decisão B1:** pipeline `cibuildwheel ≥ 3.4` (host Linux x86_64) cross-compilando `pydantic-core` → wheel `android_24_arm64_v8a`. É a prova de fogo do plano §2.

---

## 3. Embedding do interpretador

- **Modelo oficial (PEP 738):** Android só roda Python **embarcado** — carrega `libpython3.x.so` via JNI e dirige pela C-API. Sem Python de sistema, sem subprocess. — <https://docs.python.org/3/using/android.html>
- **Blueprint = CPython `Platforms/Android/testbed/`:**
  - `MainActivity.kt`: `setenv TMPDIR`; `extractAssets()` copia `python/` (assets) → `filesDir/python` (vira PYTHONHOME); `System.loadLibrary("main_activity")` (o shim JNI do app, linkado contra `libpython`); `redirectStdioToLogcat()`; `runPython(home, argv)`.
  - `c/main_activity.c`: `PyConfig_InitPythonConfig` → `PyConfig_SetBytesArgv` → **`config.home = home`** (é assim que se seta PYTHONHOME, não env var) → `Py_InitializeFromConfig` → `Py_RunMain`. Desbloqueia `SIGUSR1` (Signal Catcher do Android bloqueia). stdout/stderr → pipes → `__android_log_write`.
  - `app/build.gradle.kts`: jniLibs = `libpython*.so` + `lib*_python.so`; assets = stdlib em `assets/python/lib/pythonX.Y/` + seu código em `site-packages`. **Trick `.gz`→`.gz-`**: AAPT auto-descomprime assets `.gz` e corromperia dados da stdlib; renomeia e `MainActivity` desfaz na extração.
  - — <https://github.com/python/cpython/tree/main/Platforms/Android/testbed>
- **Off-UI-thread (anti-ANR):** o testbed roda na UI thread só por ser harness de teste. O padrão real de thread de fundo é o do **python-for-android**: `PythonService`/`PythonActivity` faz `new Thread(this).start()` cujo `run()` chama o `native nativeStart` que roda o interpretador (na thread do SDL). `run_on_ui_thread` volta pra UI. — <https://github.com/kivy/python-for-android> (`bootstraps/.../PythonActivity.java`, `PythonService.java`)
- **Trick `.so`-in-`lib/`** (Chaquopy): nativos têm que morar em `lib/<abi>/` com nome `lib*.so` + `android:extractNativeLibs="false"` → armazenados descomprimidos, alinhados e `mmap`ados direto do APK. — <https://medium.com/androiddevelopers/smallerapk-part-8-native-libraries-open-from-apk-fc22713861ff>

**Decisão B2:** clonar a estrutura do testbed (PyConfig embedding) + **rodar `Py_RunMain`/loop asyncio numa background thread própria** (padrão p4a) para casar com a "regra de ouro" do plano §3.4.

---

## 4. Ponte Python↔Kotlin — a encruzilhada

| | rubicon-java | pyjnius | Chaquopy | JNI próprio |
|---|---|---|---|---|
| Status 2025–26 | **arquivado 2022** ☠️ | ativo 1.7.0 (set/2025) | ativo **17.0.0 (dez/2025)** | — |
| Mecanismo | JNI + C-API | JNI reflection (Cython) | JNI + CPython + Gradle plugin | C-API via shim JNI |
| Embute CPython próprio? | não | não | **sim** | não |
| Fit com CPython oficial | era o ideal (morto) | possível via `PYJNIUS_JNIENV_SYMBOL` (sem exemplo documentado) | **não** — adota o interpretador dele | **melhor fit** (é o modelo PEP 738) |
| Esforço | — | médio (caminho não trilhado) | **baixo** | alto |
| Licença | BSD (morto) | MIT | **MIT, grátis desde 12.0.1** | — |
| Python | — | genérico | **3.10–3.14** | qualquer |

- **`rubicon-java` MORTO** (arquivado 12/out/2022). Era o bridge "CPython oficial + JNI + C-API". **Não usar.** BeeWare migrou pra Chaquopy. `rubicon-objc` vive (só iOS). — <https://github.com/beeware/rubicon-java>
- **Chaquopy** é o bridge mais completo e documentado: `from java import …`, `dynamic_proxy`/`static_proxy`, `Python.getInstance().getModule().callAttr()`, conversão automática de tipos. **MIT/grátis desde 12.0.1**, **17.0.0 suporta Py 3.10–3.14** (3.13+ exigido pro requisito de 16 KB page do Android 15, vigente 1/nov/2025). **Mas embute o próprio build de CPython** — você adota o interpretador do Chaquopy, não aponta pra um CPython oficial externo. Não pode rodar na main thread. — <https://chaquo.com/chaquopy/doc/current/>, <https://github.com/chaquo/chaquopy>
- **pyjnius**: independente do Kivy; no Android pega o JVM existente. Hook **`PYJNIUS_JNIENV_SYMBOL`** permite plugar seu próprio getter de `JNIEnv*` → **em tese** roda com CPython oficial embarcado, mas **não há exemplo standalone documentado** (gap de evidência). `run_on_ui_thread` é do p4a, não do pyjnius. — <https://pyjnius.readthedocs.io/>, <https://gist.github.com/tito/63d3bbb424364a74499a>
- **Threading/asyncio:** Java callback dispara em thread do JVM ≠ thread do loop asyncio → usar **`loop.call_soon_threadsafe(...)`** (ou `run_coroutine_threadsafe`) resolvendo um `Future` para transformar callback nativo (câmera/permissão) em awaitable. UI: `runOnUiThread`. (Composição é prática estabelecida, sem fonte única canônica.)

**Encruzilhada B3 (decisão do usuário — muda semanas de trabalho):**
- **Opção Y — CPython oficial 3.14 + JNI próprio.** Alinha 100% ao plano ("controle total da toolchain", "CPython oficial", §3.2/§6). Mais trabalho: reimplementar marshalling, GIL/`AttachCurrentThread`, refs JNI, tradução de exceções. É reconstruir o que o `rubicon-java` automatizava.
- **Opção X — Chaquopy.** Caminho mais curto: resolve embedding + ponte + Gradle + repo de wheels de uma vez, grátis, suporta 3.14. **Custo:** cede o controle da toolchain (usa o CPython empacotado por ele) — contradiz a premissa do plano. `pydantic-core` ainda precisa de cibuildwheel de qualquer forma (não está no repo deles).
- **Híbrido sugerido:** **spike rápido com Chaquopy** para provar o conceito ponta-a-ponta (APK rodando Python + host Compose) e validar `pydantic-core`; manter a porta aberta para migrar pra Y se o controle limitar.

---

## 5. Renderer Compose data-driven + dev loop

- **Remote Compose (`androidx.compose.remote`)** — server-driven UI oficial do Google: árvore Compose serializada em binário, device renderiza nativo. **ALPHA (1.0.0-alpha11, mai/2026)** — API instável, cobertura de primitivos incompleta. Authoring `remote-creation-jvm` **sem dependência de Android SDK**, mas **sem binding Python** (emitir o formato binário seria trabalho novo). → **referência futura, não dependência.** — <https://developer.android.com/jetpack/androidx/releases/compose-remote>
- **DIY (recomendado v1):** `@Composable` recursivo com `when(node.type) { is TextNode -> ...; is ColumnNode -> RenderChildren(...) }`; `Modifier` montado em runtime a partir do `Style`. OSS de referência: `skydoves/server-driven-compose`, `jesusdmedinac/json-to-compose`.
- **Flexbox → Compose (API atual confirmada):** `flex-direction`→`Row`/`Column`; `justify-content`→`horizontalArrangement`/`verticalArrangement` (`Arrangement.Start/Center/SpaceBetween/spacedBy`); `align-items`→`verticalAlignment`/`horizontalAlignment` (`Alignment.*`); `flex-grow`→`Modifier.weight()`; wrap→`FlowRow`/`FlowColumn`. Box model→`Modifier.padding/background/border/clip/size`. **Nosso `Style` mapeia direto** — confirma plano §4.2. — <https://developer.android.com/develop/ui/compose/layouts/flow>, <https://developer.android.com/develop/ui/compose/modifiers>
- **Prior art "Python define UI → nativo renderiza":** **Flet** (→ Flutter, protocolo JSON) e **BeeWare/Toga** (→ native Views). **Nenhum OSS faz Python→Compose** — tempestroid seria novidade nesse nicho. — <https://flet.dev/>
- **Dev loop:** Expo = QR codifica URL do dev server; app container baixa o bundle via HTTP na LAN. Flutter hot reload = push de kernel `.dill` via VM Service Protocol. — <https://docs.expo.dev/more/expo-cli/>, <https://docs.flutter.dev/tools/hot-reload>
- **WSL2 → celular na mesma Wi-Fi:** `[wsl2] networkingMode=mirrored` no `.wslconfig` + `wsl --shutdown`; liberar Hy-V firewall inbound (`Set-NetFirewallHyperVVMSetting ... -DefaultInboundAction Allow`); bind do dev server em `0.0.0.0`. Alternativa NAT: `netsh interface portproxy`. ADB wireless: `adb pair`/`adb connect` (Android 11+). **usbipd-win instável com Android** (issues #232/#248) — preferir Wireless Debugging. — <https://learn.microsoft.com/en-us/windows/wsl/networking>, <https://developer.android.com/tools/adb>

**Decisão B4/B5:** renderer Compose DIY (`when(type)` + Modifier runtime); dev server LAN HTTP/WS + QR; WSL mirrored.

---

## Pontos de atenção (gaps de evidência)

1. Versões mudam rápido — **reconfirmar cibuildwheel/maturin/Chaquopy/CPython antes da B1.**
2. **Sem caminho documentado de pyjnius standalone** com CPython oficial (só o hook de código).
3. Provenance exata do CPython do Chaquopy (vanilla vs patched) não documentada.
4. Remote Compose é **alpha** — não shippar.
5. `pydantic-core` **tem que ser buildado** (cibuildwheel) em qualquer caminho — não há atalho de wheel pronto PEP 738.

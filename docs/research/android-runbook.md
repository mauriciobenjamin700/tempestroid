# Runbook executável — Trilho B (runtime Android)

> Passo a passo para rodar numa máquina com toolchain Android (Linux x86_64 ou
> macOS). **Não roda neste ambiente WSL sem SDK/NDK.** Fundamentado em
> [`android-runtime.md`](./android-runtime.md) (fontes primárias, mai/2026).
>
> **Decisões fixadas:**
> - Runtime: **CPython 3.14 oficial** (PEP 738 Tier 3; binários Android oficiais).
> - Wheels nativas: **cibuildwheel ≥ 3.4**.
> - Ponte: **JNI próprio** sobre a C-API (modelo da testbed oficial), **sem**
>   pyjnius/Chaquopy/p4a — controle total, CPython não-patcheado.
> - Renderer device: **Jetpack Compose data-driven** (DIY, `when(type)` + `Modifier`).
> - Reconciliador/IR/Style/eventos: **reutilizar o Trilho A** sem mudança.

---

## Pré-requisitos (host de build)

| Ferramenta | Versão alvo | Notas |
|---|---|---|
| SO host | Linux x86_64 **ou** macOS | cross-build do CPython e cibuildwheel exigem POSIX. WSL2 conta como Linux. |
| Android SDK | command-line tools em `cmdline-tools/latest`; `ANDROID_HOME` setado | `sdkmanager` instala o resto. |
| Android NDK | **r27 (27.3.13750724)** | versão fixada por `Android/android-env.sh` do CPython 3.14. |
| JDK | 17+ | Gradle/AGP. |
| Rust | stable + `rustup target add aarch64-linux-android` | para `pydantic-core`. |
| `cargo-ndk` | recente | linker NDK para crates Rust. |
| uv | ≥ 0.7 | frontend de build (`pip` não suporta Android). |
| Dispositivo | Android 7.0+ (API 24), arm64-v8a | + Wireless Debugging para B5. |

Variáveis: `export ANDROID_HOME=...`, `export ANDROID_NDK_HOME=$ANDROID_HOME/ndk/27.3.13750724`.

---

## B0 — CPython 3.14 para arm64

**Caminho rápido (recomendado):** baixar o release Android oficial.
```bash
# https://www.python.org/downloads/android/  (3.14.x, aarch64)
# Resultado: prefix/ com lib/libpython3.14.so + lib/python3.14/ (stdlib)
```

**Caminho custom (se precisar de flags/debug):** cross-build com o helper oficial.
```bash
git clone --branch v3.14.x --depth 1 https://github.com/python/cpython
cd cpython
./android.py build aarch64-linux-android        # configure/make build+host
./android.py package aarch64-linux-android       # tarball em cross-build/.../dist
# (em main/3.15: python3 Platforms/Android build aarch64-linux-android)
```

**Feito quando:** existe `libpython3.14.so` arm64 + stdlib empacotada (`prefix/`).
**Validação:** `file libpython3.14.so` → `ELF 64-bit ... ARM aarch64`.

---

## B1 — Wheels nativas (DERISK CRÍTICO): `pydantic-core` arm64

Não há wheel Android pronta de `pydantic-core` → cross-compilar com cibuildwheel.
```bash
uv tool install cibuildwheel        # ≥ 3.4
git clone --depth 1 https://github.com/pydantic/pydantic-core && cd pydantic-core
export CIBW_PLATFORM=android
export CIBW_ARCHS_ANDROID=arm64_v8a          # + x86_64 p/ emulador, se quiser
export CIBW_BUILD="cp314-*"
cibuildwheel --platform android --output-dir wheelhouse
# host Linux x86_64/macOS; precisa ANDROID_HOME, NDK r27, Rust + target android,
# cargo-ndk no PATH. Frontend de build = build/uv (NÃO pip).
```

**Feito quando:** `wheelhouse/pydantic_core-*-cp314-cp314-android_24_arm64_v8a.whl`
existe e `import pydantic` roda num Python arm64 (testbed/emulador).
**Riscos conhecidos:** detecção `platform.system()=="android"` no maturin (issue #2945)
— cibuildwheel contorna; se buildar maturin "pelado", aplicar o patch. Reconfirmar
versões de cibuildwheel/maturin antes de começar (muda rápido).
**Atalho p/ deps pesadas** (numpy/cryptography/...): índice Chaquopy `pypi-13.1`
ou BeeWare mobile-wheels (mas **não** têm pydantic-core).

---

## B2 — Host Kotlin mínimo + boot do CPython em thread de fundo

Espelhar `Platforms/Android/testbed/` do CPython, com uma diferença: rodar o
interpretador numa **thread de fundo** (não na UI thread — testbed só usa UI por
ser teste). Estrutura em `android-host/` (Gradle):

- `app/src/main/java/.../MainActivity.kt`
  - `setenv("TMPDIR", cacheDir)`; `extractAssets()` copia `python/` → `filesDir/python` (= PYTHONHOME); desfaz o rename `.gz-`.
  - `System.loadLibrary("tempest_host")` (shim JNI linkado contra `libpython3.14`).
  - **start em background:** `Thread { runPython(pythonHome, argv) }.start()` (a UI fica livre; sem ANR).
  - `redirectStdioToLogcat()`.
- `app/src/main/c/tempest_host.c` (JNI):
  - `PyConfig_InitPythonConfig` → `PyConfig_SetBytesString(&config, &config.home, home)` → `Py_InitializeFromConfig` → roda o entrypoint (`Py_RunMain` ou `PyImport_ImportModule`). Desbloquear `SIGUSR1`.
- `app/src/main/c/CMakeLists.txt`: `link_libraries(log python3.14)`, include de `python3.14`.
- `app/build.gradle.kts`: jniLibs ← `libpython*.so`/`lib*_python.so`; assets ← stdlib em `assets/python/lib/python3.14/` + nosso pacote em `site-packages`; **rename `.gz`→`.gz-`** (AAPT); `android:extractNativeLibs="false"` + `.so` em `lib/<abi>/`.

**Feito quando:** APK builda, instala e imprime "hello from python" no logcat,
com o interpretador rodando fora da UI thread.

---

## B3 — Ponte JNI própria (Python ↔ Kotlin), bidirecional

Sobre a C-API, sem framework de ponte. Casar com o loop asyncio do Trilho A.

- **Kotlin → Python:** o shim JNI mantém `JavaVM*`/`JNIEnv*` (cacheados em
  `JNI_OnLoad`); chama Python via `PyGILState_Ensure` + `PyObject_CallObject`.
- **Python → Kotlin:** `ctypes`/CFFI sobre funções C exportadas, ou um C-ext que
  faz `AttachCurrentThread` + `CallObjectMethod`. Toast/log nativo como smoke.
- **Marshalling de threads (a única fronteira, plano §8):**
  - entrar no loop Python a partir de callback Java → `loop.call_soon_threadsafe(...)`;
  - sair para a UI Android → `runOnUiThread(...)`;
  - callback nativo (câmera/permissão) resolve um `asyncio.Future` → vira `await`.
- Reutilizar `parse_event` (A6) para validar payloads de evento na entrada.

**Feito quando:** Python dispara um toast/log nativo **e** um toque no device
chega a um handler Python (round-trip), com o payload validado por Pydantic.

---

## B4 — Renderer Compose data-driven (`Style → Compose`)

Host Compose interpreta a **mesma IR** do Trilho A (serializada via a ponte) —
trocar só o renderer-folha. Composable recursivo:
```kotlin
@Composable fun RenderNode(node: Node) = when (node.type) {
    "Text"   -> Text(node.props["content"], modifier = node.style.toModifier())
    "Button" -> Button(onClick = { emitTap(node.key) }) { Text(node.props["label"]) }
    "Column" -> Column(node.style.arrangement(), node.style.alignment()) { node.children.forEach { RenderNode(it) } }
    "Row"    -> Row(...) { ... }
    "Container" -> Box(node.style.toModifier()) { node.child?.let { RenderNode(it) } }
}
```
Tradutor `Style → Compose` (espelha `Style → Qt`, plano §4.4):
- `direction`→`Row`/`Column`; `justify`→`Arrangement` (`Start/Center/SpaceBetween/spacedBy`);
  `align`→`Alignment`; `grow`→`Modifier.weight`; wrap→`FlowRow`/`FlowColumn`.
- box model→`Modifier.padding/background(color,shape)/border/clip/size`.
- Aplicar **patches** do reconciliador (insert/remove/update/reorder/replace) ao
  estado Compose (lista observável de nós) — não rebuildar a árvore inteira.
- **Remote Compose** (`androidx.compose.remote`) é referência futura (alpha, sem
  binding Python) — **não** dependência v1.

**Feito quando:** a árvore de exemplo do Trilho A (counter) renderiza nativa no
device e o botão incrementa via rebuild→diff→patch.

---

## B5 — Dev server + QR (estilo Expo)

- `tempest dev` (estender o cockpit do A5) sobe um server LAN (HTTP/WS) que:
  1. serve o código Python do app; 2. relaya logs de volta ao terminal.
- Imprime QR codificando `ws://<lan-ip>:<porta>`. App host escaneia, puxa o
  código, roda local, e salvar → restart no sim **e** no device.
- **WSL:** `[wsl2] networkingMode=mirrored` no `%UserProfile%\.wslconfig` +
  `wsl --shutdown`; liberar Hyper-V firewall inbound; bind do server em `0.0.0.0`.
  ADB: `adb pair`/`adb connect` (Wireless Debugging). Evitar usbipd-win com
  Android (instável).

**Feito quando:** escanear o QR carrega o app por Wi-Fi e salvar reinicia no celular.

---

## B6 — Capacidades nativas

- **Notificações:** `NotificationManager` + canal obrigatório (Android 8+),
  permissão `POST_NOTIFICATIONS` (Android 13+). Wrapper Python em `native/`.
- **Câmera:** via `Intent` primeiro (simples), módulo CameraX depois. Callback
  nativo → `Future` → `await camera.capture()` (padrão B3).

**Feito quando:** notificação disparada do Python; foto capturada e devolvida ao Python.

---

## Ordem e convergência

1. **B0 → B1 em paralelo** (B1 é o derisk; atacar cedo, plano §8).
2. **B2 → B3** (host + ponte) depois de ter `libpython` arm64.
3. **B4** reusa reconciliador/IR/Style/eventos do Trilho A — só o renderer muda.
4. **B5/B6** por último.
5. **Convergência:** o host no celular carrega o **mesmo reconciliador** do
   Trilho A; `tempest dev` ganha o alvo "device" ao lado do "sim".
6. **D (conformância):** golden snapshots `Style→Qt` vs `Style→Compose` no CI —
   é o que mantém o simulador honesto contra o device.

## Reconfirmar antes de executar (muda rápido)
- Versões: CPython 3.14.x, cibuildwheel, maturin, NDK, AGP/Compose BOM.
- Estado das wheels Android de `pydantic-core` (pode surgir wheel pronta).
- Status do Remote Compose (se sair de alpha, reavaliar para o renderer).

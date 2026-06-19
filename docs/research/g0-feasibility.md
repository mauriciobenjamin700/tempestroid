# G0 — spike de viabilidade (Trilho G): resultados

> Execução do **G0** definido em [`onnx-ml-stack.md`](onnx-ml-stack.md) §6.
> Data: 2026-06-18. Host: WSL Ubuntu, NDK r27 (`/usr/lib/android-sdk/ndk/27.3.13750724`),
> CPython 3.14 android oficial, cibuildwheel **3.4.1**.
> Alvo exercitado: **emulador x86_64** (`emulator-5556`, ranchu, API 34).

## Done-when do G0 (§6) — placar

| Item | Estado |
|---|---|
| Árvore de deps do `ort-vision-sdk` classificada | ✅ feito (§1) |
| Decisão (A) CPython-puro vs (B) inferência-nativa registrada | ✅ feito (§2) |
| EPs do device-alvo listados | ✅ feito (§3) |
| `import numpy` no aparelho | ✅ **FEITO** (2026-06-18, emulator-5556) — 3 blockers vencidos (§4) |

**Atualização (2026-06-18):** o item 4 **fechou**. O blocker do sysconfig
(`$(BLDLIBRARY)`) era **bug do cibuildwheel 3.4.1**; subir para **4.1.0** o
resolveu. A wheel `numpy-2.4.6-cp314-cp314-android_24_x86_64.whl` (9 MB) buildou,
foi staged no site-packages do device e **`import numpy` + cálculo rodam no
emulador** (`examples/onnxspike`, screenshot: `numpy 2.4.6 sum=55 mean=5.5
dot=385`). Receita reprodutível em `toolchain/build_numpy_x86.sh`.

---

## 1. Árvore de dependências do `ort-vision-sdk` (real, do PyPI)

`ort-vision-sdk` **0.3.2** (`requires_dist`):

| Pacote | Tipo | Balde | Notas |
|---|---|---|---|
| `numpy>=1.24.0` | nativo (C/Cython, Meson) | **wheel difícil** | I/O de tensores; **caminho crítico** (ver §2). BLAS + run-checks de cross. |
| `onnxruntime>=1.17.0` | nativo (C++ pesado) | **wheel difícil** | sem wheel android no PyPI; buildar ou usar AAR (§2). |
| `pillow>=10.0.0` | nativo (C) | wheel média | decode/resize sem cv2 (caminho de visão preferido). |
| `opencv-python>=4.8.0` | nativo (C++ enorme) | **difícil**, só extra `[opencv]` | **evitar** no device — usar OpenCV Android SDK nativo ou Pillow/`BitmapFactory`. |
| `onnxruntime-gpu` | nativo | só extra `[gpu]` | irrelevante no device (sem CUDA). |

`pandas`/`scikit-learn`/`scikit-image` **não** são deps do SDK de visão (camada
opcional, G5/G6). **Núcleo de visão = numpy + onnxruntime + pillow.**

Confirma a §1 da pesquisa: nada de novo no balde "difícil"; opencv/gpu são extras
descartáveis no caminho de visão.

---

## 2. Decisão (A) vs (B)

**Constatação que decide:** **ambos os caminhos precisam de `numpy` no device.**
- (A) CPython-puro roda o SDK inteiro no interpretador → numpy obrigatório.
- (B) inferência-nativa (AAR `onnxruntime-android`) tira só a wheel do
  `onnxruntime`, mas o **pré/pós-processamento** (resize, normalize, NMS, tensor
  I/O) continua em `numpy` no Python — a menos que tudo vá pra dentro do grafo
  (`onnxruntime-extensions`) ou pro Kotlin.

Logo o cross-compile do `numpy` está no **caminho crítico independente de A/B** —
e é exatamente onde o G0 travou (§4). Resolver numpy destrava os dois.

**Decisão registrada:** seguir **(A) parcial** — numpy + onnxruntime como wheels —
**condicionado a fechar o blocker de sysconfig (§4)**. Manter **(B)** como fallback
para a inferência (`onnxruntime` AAR) caso a wheel do onnxruntime não feche; mas
(B) **não** elimina a necessidade do numpy. Reavaliar `onnxruntime-extensions`
para mover pré/pós ao grafo e encolher a dependência de numpy (G3).

---

## 3. Execution Providers no device-alvo

| EP | Emulador x86_64 (`emulator-5556`) | Xiaomi arm64 (Snapdragon) | Fonte |
|---|---|---|---|
| **NNAPI** | ✅ presente — `nnapi_native.current_feature_level = 7`, HAL `neuralnetworks_*_sample_*` rodando (drivers de amostra, backed por CPU) | ✅ (NNAPI varia por OEM/versão) | `adb shell getprop` |
| **XNNPACK** | ✅ via AAR Maven do ORT (kernels CPU float ARM/x86) | ✅ | AAR |
| **QNN** (Hexagon/NPU) | ❌ (x86, sem Hexagon) | ✅ (Snapdragon) — maior ganho | — |
| **CPU** (fallback) | ✅ sempre | ✅ sempre | — |

No emulador o NNAPI é HAL de amostra (não acelera de verdade, cai em CPU). Para
medir ganho real de EP é preciso o **device físico** (a medição de latência por EP
é entregável do **G1**, §4.1 da pesquisa). Cadeia provável: `QNN→NNAPI→XNNPACK→CPU`
(Snapdragon) / `NNAPI→XNNPACK→CPU` (genérico) / `XNNPACK→CPU` (emulador).

---

## 4. `import numpy` no device — blockers do cross-compile

Tentativa: `cibuildwheel --platform android --archs x86_64` sobre numpy **2.4.6**
(sdist), CPython 3.14 android, NDK r27. Três blockers em sequência:

### Blocker 1 — `before-build` do numpy provisiona OpenBLAS (host-only) ✅ resolvido
A config `[tool.cibuildwheel]` do numpy roda `tools/wheels/cibw_before_build.sh`
(instala `scipy-openblas64`, **sem variante android**); além disso o script **nem
existe no sdist**. numpy **não tem** seção `[tool.cibuildwheel.android]`.
**Fix:** `CIBW_BEFORE_BUILD=""` + build BLAS-less via `-Dallow-noblas=true`
(numpy 2.x). Para uma prova de *import* (não de velocidade), noblas serve.

### Blocker 2 — run-check de `longdouble` no ambiente cross ✅ resolvido
`numpy/_core/meson.build:444` faz `cc.run(...)` para detectar o formato de
`long double` — impossível em cross (binário android não roda no host). numpy lê
`meson.get_external_property('longdouble_format', ...)`.
**Fix:** cross-file extra com
```ini
[properties]
longdouble_format = 'INTEL_EXTENDED_16_BYTES_LE'   # x86_64 = 80-bit estendido, 16 bytes
```
passado via `setup-args=--cross-file=<arquivo>` (meson mescla múltiplos cross-files).
Destravou o configure; compilou até **[66/479] objetos**.

### Blocker 3 — sysconfig do CPython android vaza `$(BLDLIBRARY)` no link ✅ resolvido (cibuildwheel ≥4.0)

No link de cada C-extension, com **cibuildwheel 3.4.1**:

```text
clang: error: no such file or directory: '$(BLDLIBRARY)'
```

O CPython 3.14 android x86_64 que o cibuildwheel 3.4.1 baixava expunha
`$(BLDLIBRARY)` **não-expandido** no `LDSHARED`/flags que o meson repassava
literalmente ao clang. Afetava **qualquer C-extension** (numpy, onnxruntime-wheel,
pillow); o `pydantic-core` (B1) escapava por ser **Rust/maturin**.

**Resolvido subindo cibuildwheel → 4.1.0** (lead nº1, menor esforço). A 4.x
amadureceu o Android e não vaza mais a variável; o link passou e a wheel buildou.
Dois ajustes a mais que a 4.x exigiu: numpy lista o enable-group
`cpython-freethreading` que a 4.x removeu (retirar do `pyproject`), e a fase de
teste do numpy tenta `pip install` no target (`CIBW_TEST_SKIP="*"`). Tudo
capturado em `toolchain/build_numpy_x86.sh`.

(Leads alternativos, não mais necessários: sanear o `_sysconfigdata` do python
android; estudar as receitas do Chaquopy `server/pypi` — ★ da pesquisa.)

---

## 5. Conclusão do G0

- **Investigação fechada** (deps, A/B, EPs): núcleo de visão = numpy + onnxruntime
  + pillow; numpy é caminho crítico para A **e** B; EPs do emulador = NNAPI(sample)
  /XNNPACK/CPU, QNN só no Snapdragon físico.
- **numpy no device: FEITO.** Os 3 blockers de cross-compile resolvidos
  (OpenBLAS→noblas; longdouble→cross-prop; `$(BLDLIBRARY)`→cibuildwheel 4.1).
  Wheel `numpy-2.4.6-cp314-cp314-android_24_x86_64.whl` staged no device e
  `import numpy` + cálculo rodam no emulador (`examples/onnxspike`). A correção do
  3º blocker (subir a cibuildwheel) **destrava todas as wheels C** — vale para
  onnxruntime e pillow também.
- **G0 fechado nos 4 done-when.** O que era o gargalo virou receita reprodutível.

> **G1 continua por:** wheel/AAR do `onnxruntime` + 1 modelo `.onnx` ponta-a-ponta
> no device (fora da UI thread/loop) + escolha de EP (latência medida). Para o
> onnxruntime, **buildar a wheel** (`build.py --build_wheel --android`) reusando o
> mesmo destravamento (cibuildwheel ≥4.0) **ou** o AAR `onnxruntime-android` (path
> B). numpy já provado; pillow pelo mesmo caminho quando o decode de imagem entrar
> (G2).

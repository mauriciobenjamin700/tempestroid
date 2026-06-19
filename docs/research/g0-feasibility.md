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
| `import numpy` no aparelho | ⚠️ **bloqueado** — 3 blockers achados, 2 resolvidos, 1 preciso (§4) |

O item 4 não fechou: o cross-compile do numpy esbarra num **vazamento de
variável Makefile no sysconfig do CPython 3.14 android** que o cibuildwheel
baixa. O blocker está **pinçado e reproduzível** (§4) — é trabalho de toolchain
nível G1, não mais de spike.

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

### Blocker 3 — sysconfig do CPython android vaza `$(BLDLIBRARY)` no link ✗ aberto
No link de cada C-extension:
```
clang: error: no such file or directory: '$(BLDLIBRARY)'
```
O **CPython 3.14 android x86_64 que o cibuildwheel baixa** expõe `$(BLDLIBRARY)`
**não-expandido** no `LDSHARED`/flags de link que o meson repassa literalmente ao
clang. (O prefixo arm64 oficial que staguei no Trilho B tem
`BLDLIBRARY='-L. -lpython3.14'` corretamente expandido — então é específico do
build x86_64 do cibuildwheel / da introspecção meson.)

Afeta **qualquer C-extension** (numpy, onnxruntime-wheel, pillow), **não** só o
numpy. O `pydantic-core` (B1) escapa porque é **Rust/maturin**, que linka de outro
jeito — por isso o Trilho B nunca bateu nisso.

**Leads para fechar (G1):**
1. **Subir cibuildwheel 3.4.1 → ≥4.0** — a 4.0 "amadureceu Android" (auditwheel,
   pkg-config, Fortran); o vazamento de sysconfig pode já estar corrigido lá.
   Tentar **primeiro**, é o de menor esforço.
2. Sanear o `_sysconfigdata` do python android usado no build (expandir
   `BLDLIBRARY`/`LDSHARED`) antes de invocar o meson.
3. Estudar as **receitas do Chaquopy** (`server/pypi`, numpy+OpenBLAS android) — a
   referência ★ da pesquisa; eles já resolveram isto.

---

## 5. Conclusão do G0

- **Investigação fechada** (deps, A/B, EPs): núcleo de visão = numpy + onnxruntime
  + pillow; numpy é caminho crítico para A **e** B; EPs do emulador = NNAPI(sample)
  /XNNPACK/CPU, QNN só no Snapdragon físico.
- **Derisk do numpy:** 2 dos 3 blockers de cross-compile resolvidos com fixes
  documentados; o 3º (`$(BLDLIBRARY)`) pinçado e com 3 leads. **É o gargalo que
  G1 tem que atacar primeiro — e destrava todas as wheels C.**
- **Prova de `import numpy` no device: não atingida nesta rodada** (bloqueada pelo
  item acima). Honestamente fora do escopo de spike — vira a primeira tarefa do G1.

> **G1 abre por:** resolver o `$(BLDLIBRARY)` (lead 1: cibuildwheel ≥4.0) →
> fechar a wheel do numpy x86_64 → `import numpy` no emulador → então a wheel/AAR
> do onnxruntime + 1 modelo `.onnx` ponta-a-ponta.

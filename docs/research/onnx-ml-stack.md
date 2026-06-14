# Pesquisa — inferência ONNX + stack científica no device (Trilho G)

> Levantamento para fundamentar o **Trilho G**: rodar inferência de modelos
> `.onnx` **dentro do app Android nativo** usando o
> [`ort-vision-sdk`](https://github.com/mauriciobenjamin700/ort-vision-sdk) do
> time, com `numpy` / `pandas` / `scikit-learn` funcionando no aparelho.
> Fontes primárias citadas; versões verificadas em jun/2026.
> **Atenção:** o ecossistema muda rápido — reconfirmar versões antes de cravar
> qualquer fase G.

---

## TL;DR — duas arquiteturas possíveis

O problema tem **dois caminhos**, e a decisão de qual seguir é o primeiro
entregável da investigação (G0):

| Caminho | Como | Prós | Contras |
|---|---|---|---|
| **(A) CPython puro** | Cross-compilar `onnxruntime` + `numpy`/`pandas`/`scikit-learn` como wheels Android e empacotar no site-packages do device (padrão **B1** = `pydantic-core`). `ort-vision-sdk` roda no interpretador embarcado. | Reusa todo o runtime do Trilho B; código Python idêntico ao desktop; SDK roda sem mudança. | Wheels pesadas; `scipy`/`sklearn` são o calcanhar (Fortran/LAPACK + OpenMP); APK cresce muito. |
| **(B) Inferência nativa + ponte** | Usar o **`onnxruntime-android` (AAR Maven, Kotlin/C++)** para a inferência no host; Python só orquestra (pré/pós-processamento leve). Tensores cruzam a ponte JNI existente. | Evita a wheel mais pesada (`onnxruntime` C++); AAR oficial mantido pela Microsoft; menor APK. | `ort-vision-sdk` (Python) **não** roda a inferência — precisaria de um shim Kotlin espelhando a API; pré/pós em `numpy` ainda exige a wheel. |

**Recomendação inicial (a confirmar em G0):** começar por **(A) parcial** —
cross-compilar `numpy` + `onnxruntime` (as duas que o `ort-vision-sdk` realmente
exige no caminho de detecção/classificação) e **adiar `pandas`/`scikit-learn`**
para um sub-trilho separado, porque são ordens de grandeza mais difíceis (ver
§3). Manter **(B)** como fallback se a wheel do `onnxruntime` não fechar.

---

## 1. O que o `ort-vision-sdk` realmente importa

Antes de cross-compilar qualquer coisa, mapear a árvore de dependências **real**
do SDK no device — não a do dev desktop:

- **Núcleo obrigatório:** `onnxruntime` (C++ pesado) + `numpy` (tensores I/O).
- **Backend de imagem:** o extra `[opencv]` puxa `opencv-python` (enorme; outra
  wheel nativa). Avaliar usar **Pillow** ou o decoder de imagem do próprio host
  (Android `BitmapFactory`) em vez de OpenCV no device.
- **`pandas`/`scikit-learn` NÃO são dependências do SDK de visão** — entram só se
  o app do usuário fizer feature-engineering tabular ou pós-processamento ML
  clássico. Por isso o Trilho G os trata como **camada opcional**, não núcleo.

> **G0 done-when:** árvore de deps do `ort-vision-sdk[opencv]` resolvida para
> `aarch64`/`x86_64`-android, com cada pacote marcado: pure-python (trivial),
> wheel nativa "fácil" (numpy), wheel nativa "difícil" (onnxruntime, opencv,
> scipy, sklearn).

---

## 2. Cross-compilar wheels nativas — estado da arte (jun/2026)

O Trilho B já provou o padrão com `pydantic-core` via **cibuildwheel** (B1). O
ecossistema avançou desde então:

- **cibuildwheel ganhou Android na 3.1** (jul/2025) e **amadureceu na 4.0**:
  suporte a **auditwheel**, **pkg-config** e **configuração de Fortran**, além de
  `xbuild-files` (listar arquivos do host seguros durante o cross-build). Isso é
  exatamente o que `scipy`/`sklearn` precisam. —
  <https://iscinumpy.dev/post/cibuildwheel-4-0-0/>,
  <https://cibuildwheel.pypa.io/>
- **`numpy`** já usa cibuildwheel para suas wheels multi-plataforma → caminho de
  cross-compile arm64-android é o mais maduro da stack científica. Risco: baixo.
- **`scipy`** migrou de multibuild para cibuildwheel (config no próprio repo) —
  mas depende de **BLAS/LAPACK + Fortran (gfortran)**, o ponto mais frágil no
  NDK. Risco: **alto**. —
  <https://github.com/scikit-learn/scikit-learn/issues/30284>
- **`scikit-learn`** usa cibuildwheel com **Cython + C++ + OpenMP**; no Android o
  OpenMP exige **`libomp` do NDK** linkado corretamente, e ele depende de
  `scipy`. Risco: **alto** (herda o risco do scipy + OpenMP).
- **`pandas`** = `numpy` + extensões Cython/C próprias; sem Fortran. Risco:
  **médio**.

**Build host:** cibuildwheel para Android exige runner **Linux x86_64 / macOS
arm64 / macOS x86_64** + Android SDK/NDK — igual ao Trilho B (NDK r27,
`ANDROID_SDK_ROOT=/usr/lib/android-sdk` neste host; não roda em WSL sem o
toolchain).

---

## 3. `onnxruntime` no Android — wheel vs AAR

Duas formas de ter ONNX Runtime no aparelho:

### (A) Wheel Python via `build.py`

O build oficial suporta Android + wheel num único comando:

```bash
python tools/ci_build/build.py \
  --build_wheel --android \
  --android_home <SDK> --android_ndk_path <NDK> \
  --android_abi arm64-v8a --config Release
```

→ produz `.whl` em `<config>/dist`. Cross-compile arm também suportado via
**QEMU user-mode** quando não há device. —
<https://onnxruntime.ai/docs/build/inferencing.html>,
<https://onnxruntime.ai/docs/build/custom.html>

> Não há wheel oficial android de `onnxruntime` no PyPI — **temos que buildar**,
> igual fizemos com `pydantic-core`. Avaliar um **custom build** (só os
> operadores que os modelos do time usam) para encolher o binário —
> `--include_ops_by_config` reduz drasticamente o tamanho.

### (B) AAR nativo (`onnxruntime-android` via Maven)

A Microsoft publica o AAR oficial (`com.microsoft.onnxruntime:onnxruntime-android`)
consumido pelo Gradle do `android-host/`. A inferência roda em C++/Kotlin; um
shim Kotlin exporia `run(modelPath, inputs)` à ponte JNI, e o Python mandaria só
tensores serializados. Espelha o padrão **B6/E8** (`native` envelope +
module-router). Evita a wheel C++ mais pesada — mas duplica a API do SDK em
Kotlin.

---

## 4. Tamanho do APK — restrição dura

Empilhar CPython 3.14 + stdlib (Trilho B já ~39 MB) + `numpy` + `onnxruntime` +
modelo `.onnx` + (eventual) `opencv`/`scipy`/`sklearn` estoura fácil **>150 MB**.
Mitigações a investigar em G:

- **ABI splits / App Bundle** (já é caminho do Trilho F4) — uma ABI por device.
- **onnxruntime custom build** (só operadores usados) + **modelo quantizado**
  (`.ort` / INT8).
- **Trim do site-packages** (padrão F6: remover testes/`__pycache__`/headers das
  wheels).
- Reaproveitar o `numpy` para o pré/pós e **evitar `opencv`** no device.

---

## 5. Fases propostas (investigação-primeiro)

| Fase | Escopo | Risco | Feito quando |
|---|---|---|---|
| **G0** | Spike de viabilidade: mapear deps reais do `ort-vision-sdk`, decidir caminho (A)/(B), provar `import numpy` + `onnxruntime` no device | médio | árvore de deps classificada; decisão A/B registrada; `numpy` importa no aparelho |
| **G1** | Wheel do `onnxruntime` (ou AAR) + inferência de 1 modelo `.onnx` real ponta-a-ponta no device | **alto** | um `Detector`/`Classifier` do SDK roda no aparelho e devolve resultado tipado (verificado por screenshot) |
| **G2** | Caminho de imagem sem OpenCV (Pillow ou `BitmapFactory` do host) + pré/pós em `numpy` | médio | imagem da câmera/galeria → tensor → inferência sem `opencv-python` na APK |
| **G3** | (opcional) `pandas` no device — feature-engineering tabular | médio | `import pandas` + um pipeline tabular roda no aparelho |
| **G4** | (opcional) `scipy` + `scikit-learn` no device — ML clássico | **alto** | `import sklearn`; um modelo sklearn faz `predict` no aparelho |
| **G5** | Encolher APK: custom onnxruntime build + modelo quantizado + ABI splits + trim | médio | APK com inferência cabe num orçamento de tamanho acordado, medido |

`G3`/`G4` ficam **gated** por demanda real de app — não bloqueiam o caminho de
visão (`G0→G2`), que é o que o `ort-vision-sdk` exercita.

---

## 6. Riscos e perguntas em aberto

- **`scipy`/`sklearn` podem simplesmente não fechar** no NDK sem esforço grande
  de Fortran/LAPACK — por isso G4 é o último e opcional. Confirmar se a
  comunidade já publica wheels android (improvável em jun/2026).
- **Threading do onnxruntime** vs a regra do Trilho B ("Python fora da UI
  thread") — a inferência é CPU-pesada; precisa rodar no executor de fundo, não
  bloquear o loop asyncio nem a UI.
- **Aceleração:** NNAPI / XNNPACK / GPU como execution providers do onnxruntime
  no Android — ganho grande, mas cada EP é uma flag de build a validar.
- **Tudo dentro do projeto:** seguindo a regra do `CLAUDE.md`, a metade Python
  do Trilho G mora no pacote `tempestroid/` (ex.: `native/inference.py` se o
  caminho (B) precisar de um envelope) e a metade Kotlin em `android-host/` —
  **sem repositório/pacote separado**. O `ort-vision-sdk` continua dependência
  externa (não é re-implementado aqui).

---

## Fontes

- cibuildwheel 4.0 (Android: auditwheel, pkg-config, Fortran) — <https://iscinumpy.dev/post/cibuildwheel-4-0-0/>
- cibuildwheel 3.0 (Android desde 3.1) — <https://iscinumpy.dev/post/cibuildwheel-3-0-0/>
- cibuildwheel docs — <https://cibuildwheel.pypa.io/>
- scikit-learn — release de wheels via CI (cibuildwheel) — <https://github.com/scikit-learn/scikit-learn/issues/30284>
- ONNX Runtime — build for inferencing (Android, `--build_wheel`, `--android_abi`) — <https://onnxruntime.ai/docs/build/inferencing.html>
- ONNX Runtime — custom build (reduzir operadores) — <https://onnxruntime.ai/docs/build/custom.html>
- `ort-vision-sdk` — <https://github.com/mauriciobenjamin700/ort-vision-sdk>

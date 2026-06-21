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
  (Android `BitmapFactory`) em vez de OpenCV no device — ver §3.5.
- **`pandas`/`scikit-learn`/`scikit-image` NÃO são dependências do SDK de
  visão** — entram só se o app do usuário fizer feature-engineering tabular,
  pós-processamento ML clássico ou processamento de imagem avançado. Por isso o
  Trilho G os trata como **camada opcional**, não núcleo.

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

> **Prova de viabilidade — Chaquopy.** O SDK Chaquopy já mantém um **repositório
> público de wheels android pré-buildadas** (`numpy` com OpenBLAS, `scipy`,
> `opencv`, `scikit-learn`, `tensorflow`) em <https://chaquo.com/pypi-13.1/>,
> com os **scripts de build abertos** em `chaquo/chaquopy` (`server/pypi`). Não
> usamos o runtime Chaquopy (decisão B = JNI próprio + CPython oficial), **mas
> as receitas de cross-compile dele são a melhor referência existente** para
> fechar `scipy`/`sklearn`/`opencv` no NDK — exatamente o nosso calcanhar. G0
> deve estudá-las antes de buildar do zero. Ver §Referências.

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

### 3.5 `opencv` e `scikit-image` — backends de imagem/visão pesados

Duas libs que o app pode querer, ambas no balde **difícil**:

**`opencv-python` (cv2)**

- **Sem wheel android no PyPI.** O PyPI só publica desktop
  (manylinux/win/mac); o `piwheels` cobre **ARM-Linux** (Raspberry Pi), **não**
  Android. → buildar do NDK = pesado (binário ~50–90 MB, dezenas de deps C++).
- Caminhos melhores no device:
  - **(a) OpenCV Android SDK nativo** (`.so`/Kotlin oficial) + ponte JNI — a
    inferência/processamento roda em C++, o Python só orquestra (espelha o
    caminho **(B)** da §TL;DR). Evita a wheel cv2.
  - **(b) Evitar cv2** — decode/resize via `BitmapFactory` do host + `numpy`, e
    `Pillow` para o resto. Cobre a maioria dos pré-processos de visão.
- Se cv2-em-Python for inevitável: usar **`opencv-python-headless`** (sem GUI,
  menor) + custom build. Risco **alto**, tamanho **muito alto**.

**`scikit-image` (skimage)**

- Quase puro-Python no topo, **mas depende de `scipy`** (`scipy.ndimage`,
  `scipy.fft`, …) → **herda o pior risco da stack** (Fortran/LAPACK + OpenMP).
  As outras deps (`imageio`, `tifffile`, `networkx`, `pillow`, `lazy_loader`,
  `packaging`) são leves.
- Logo: **skimage fica gated atrás do `scipy` (G4)**. Se o `scipy` fechar,
  skimage adiciona pouco; se não fechar, skimage não roda.

> **Regra prática:** para *visão* (decode, resize, normalize, tensor I/O), ficar
> em `numpy` + `Pillow`/`BitmapFactory` cobre o caminho de visão sem cv2 nem skimage. `cv2`
> (SDK nativo) e `skimage` (pós-`scipy`) são camadas opcionais, só sob demanda
> real de app.

## 4. Ecossistema de execução nativa (só inferência — treino fora de escopo)

> **Escopo fixado:** a lib só **executa** modelos; **treino está fora** — sem
> torch/TF-train, autograd, datasets, otimizadores, augmentation pesada. Isso
> reduz muito a superfície de deps. O que resta é o ecossistema de *runtime de
> inferência*, mapeado abaixo (era o ponto cego das §§1–3).

### 4.1 Execution Providers (aceleração de hardware)

A inferência no CPU puro é o piso; o ganho real (ordem de grandeza) vem dos EPs.
Cada EP é uma **flag de build** do `onnxruntime` + **registro em runtime** ao
criar a sessão, com **fallback p/ CPU** quando o device não suporta:

- **NNAPI** — interface unificada CPU/GPU/DSP/NPU do Android (API 27+; ideal 9+).
- **XNNPACK** — kernels CPU float otimizados (ARM); publicado no AAR Maven.
- **QNN** — Qualcomm Hexagon/NPU (Snapdragon); maior ganho onde existe.
- **GPU/Vulkan** — conforme device.

> Decisão de quais EPs habilitar entra no **G1** (não é nota de rodapé): medir
> latência por EP no device-alvo e escolher a cadeia (ex.: QNN→NNAPI→XNNPACK→CPU).

### 4.2 `onnxruntime-extensions` (pré/pós dentro do grafo)

Operadores custom (tokenização, decode/resize de imagem, NMS, etc.) **embutidos
no grafo ONNX** em vez de em Python. Para visão: pode mover resize/normalize/NMS
para dentro do modelo → **menos `numpy`/`opencv` no device** e APK menor. Forte
candidato a encolher o caminho (A). Confirmar suporte Android + tamanho em G0/G1.

### 4.3 Formato e otimização do modelo

- **`.onnx` → `.ort`** — formato mobile do ONNX Runtime (carrega mais rápido,
  casa com *minimal build*).
- **Quantização** — INT8 dinâmica/estática, float16; corta tamanho e acelera.
- **Otimização de grafo** — níveis (basic/extended/all), fusão de operadores.
- **Opset** — garantir compatibilidade do opset do modelo com o runtime buildado.

Um **pipeline de conversão** (onnx→ort + quantize) roda no host, não no device.

### 4.4 Entrega e armazenamento do modelo

Onde o `.onnx`/`.ort` vive em produção:

- **Embutido no APK** (asset) — simples, mas infla o APK (ver §5).
- **Baixado em runtime** — APK enxuto; precisa de cache local + verificação.
- **Play Asset Delivery** — para modelos grandes, fora do APK base.
- **`mmap` no load** — não estoura a RAM com modelos grandes; respeitar limites
  de memória mobile.

### 4.5 Threading da inferência

Inferência é CPU-pesada: roda **fora da UI thread** *e* **fora do loop asyncio**
(thread pool / executor), casando com o `async_predict` (`asyncio.to_thread`) e o
`ort_async_predict` (`run_async` nativo do ORT) do `ort-vision-sdk` e com o
invariante do Trilho B (Python já roda fora da UI thread). O resultado volta ao
loop via `call_soon_threadsafe`.

### 4.6 Amplitude de domínio (hoje fora de escopo — flag)

Visão é o foco (o que o `ort-vision-sdk` exercita). **Se** um dia entrar NLP/áudio:
tokenizers (HF Rust — tem wheels; sentencepiece), áudio (`librosa` puxa
`scipy`/`numba` = difícil). Registrado como **out-of-scope** explícito para não
inflar o caminho de visão.

---

## 5. Tamanho do APK — restrição dura

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

## 6. Fases propostas (investigação-primeiro)

| Fase | Escopo | Risco | Feito quando |
|---|---|---|---|
| **G0** | Spike de viabilidade: mapear deps reais do `ort-vision-sdk`, decidir caminho (A)/(B), levantar EPs disponíveis no device-alvo, provar `import numpy` + `onnxruntime` no device | médio | árvore de deps classificada; decisão A/B registrada; EPs do device listados; `numpy` importa no aparelho |
| **G1** | Wheel do `onnxruntime` (ou AAR) + inferência de 1 modelo `.onnx` real ponta-a-ponta no device, **rodando fora da UI thread/loop** (§4.5) + **escolha de EP** (§4.1: medir latência, fallback CPU) | **alto** | um `Detector`/`Classifier` do SDK roda no aparelho, devolve resultado tipado sem travar a UI, com EP escolhido (verificado por screenshot + latência medida) |
| **G2** | Caminho de imagem sem OpenCV (Pillow ou `BitmapFactory` do host) + pré/pós em `numpy`; se cv2 for exigido, OpenCV Android SDK nativo + ponte (não a wheel) | médio | imagem da câmera/galeria → tensor → inferência sem `opencv-python` na APK |
| **G3** | Otimização de execução (§4.2/§4.3): pipeline `.onnx`→`.ort` + quantização (INT8/fp16) no host; avaliar `onnxruntime-extensions` (pré/pós no grafo) | médio | modelo `.ort` quantizado roda no device; pré/pós movido pro grafo onde valer (menos numpy/opencv) |
| **G4** | Entrega e storage do modelo (§4.4): embutido vs download em runtime + cache, `mmap` no load, Play Asset Delivery p/ modelos grandes | médio | um modelo carrega por cada estratégia escolhida sem estourar RAM; decisão de delivery registrada |
| **G5** | (opcional) `pandas` no device — feature-engineering tabular | médio | `import pandas` + um pipeline tabular roda no aparelho |
| **G6** | (opcional) `scipy` + `scikit-learn` + `scikit-image` no device — ML clássico + processamento de imagem (skimage gated atrás do scipy) | **alto** | `import sklearn`/`skimage`; um modelo sklearn faz `predict` no aparelho |
| **G7** | Encolher APK: custom onnxruntime build + modelo quantizado + ABI splits + trim | médio | APK com inferência cabe num orçamento de tamanho acordado, medido |

`G5`/`G6` ficam **gated** por demanda real de app — não bloqueiam o caminho de
visão (`G0→G4`), que é o que o `ort-vision-sdk` exercita.

---

## 7. Riscos e perguntas em aberto

- **`scipy`/`sklearn` podem simplesmente não fechar** no NDK sem esforço grande
  de Fortran/LAPACK — por isso G6 é o último e opcional. Confirmar se a
  comunidade já publica wheels android (improvável em jun/2026).
- **Fragmentação de EP entre devices** (§4.1) — QNN só em Snapdragon, NNAPI varia
  por OEM/versão; a cadeia precisa de **fallback p/ CPU** garantido e medição por
  device-alvo, não só no aparelho de bancada. Threading (§4.5) já promovido.
- **`onnxruntime-extensions` no Android** (§4.2) — confirmar suporte e custo de
  tamanho em G0/G1 antes de apostar nele para encolher o pré/pós.
- **Tudo dentro do projeto:** seguindo a regra do `CLAUDE.md`, a metade Python
  do Trilho G mora no pacote `tempestroid/` (ex.: `native/inference.py` se o
  caminho (B) precisar de um envelope) e a metade Kotlin em `android-host/` —
  **sem repositório/pacote separado**. O `ort-vision-sdk` continua dependência
  externa (não é re-implementado aqui).

---

## Referências para avançar a pesquisa

Material de leitura curado por tema. Os itens marcados **★** são leitura
obrigatória antes de iniciar a fase indicada.

### Receitas de wheels científicas para Android (a melhor referência)

- **★ Chaquopy — repositório de wheels android pré-buildadas** (numpy/OpenBLAS,
  scipy, opencv, scikit-learn, tensorflow): <https://chaquo.com/pypi-13.1/>
- **★ Chaquopy — scripts de build das wheels** (`server/pypi`; as receitas de
  cross-compile de cada pacote): <https://github.com/chaquo/chaquopy>
- Chaquopy — "More data science packages now available" (notas de OpenBLAS,
  versões): <https://chaquo.com/chaquopy/more-data-science-packages-now-available/>

### Cross-compilar wheels nativas (toolchain)

- **★ cibuildwheel — docs** (target Android, opções de build): <https://cibuildwheel.pypa.io/>
- cibuildwheel 4.0 — Android maduro (auditwheel, pkg-config, Fortran, `xbuild-files`): <https://iscinumpy.dev/post/cibuildwheel-4-0-0/>
- cibuildwheel 3.0 — Android desde a 3.1: <https://iscinumpy.dev/post/cibuildwheel-3-0-0/>
- NumPy — guia de build/cross-compile (Meson): <https://numpy.org/doc/stable/building/>
- SciPy — guia de build (BLAS/LAPACK, Fortran): <https://docs.scipy.org/doc/scipy/building/>
- scikit-learn — release de wheels via CI (cibuildwheel + OpenMP): <https://github.com/scikit-learn/scikit-learn/issues/30284>
- maturin — build de extensões Rust (referência do `pydantic-core`, Trilho B1): <https://www.maturin.rs/>

### Runtime CPython no Android (base do Trilho B)

- **★ PEP 738 — Android como plataforma suportada**: <https://peps.python.org/pep-0738/>
- CPython — using Python on Android (3.14, binários oficiais): <https://docs.python.org/3.14/using/android.html>
- Pesquisa interna do runtime (B0–B6): [`android-runtime.md`](android-runtime.md) · runbook executável: [`android-runbook.md`](android-runbook.md)

### ONNX Runtime no Android

- **★ ONNX Runtime — deploy on mobile** (visão geral, formato ORT, EPs): <https://onnxruntime.ai/docs/tutorials/mobile/>
- ONNX Runtime — build for inferencing (Android, `--build_wheel`, `--android_abi`): <https://onnxruntime.ai/docs/build/inferencing.html>
- ONNX Runtime — custom build (reduzir operadores, `--include_ops_by_config`): <https://onnxruntime.ai/docs/build/custom.html>
- ONNX Runtime — NNAPI Execution Provider (aceleração CPU/GPU/NPU, API 27+): <https://onnxruntime.ai/docs/execution-providers/NNAPI-ExecutionProvider.html>
- ONNX Runtime — XNNPACK Execution Provider (AAR no Maven): <https://onnxruntime.ai/docs/execution-providers/Xnnpack-ExecutionProvider.html>
- ONNX Runtime — QNN Execution Provider (Qualcomm Hexagon/NPU): <https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html>
- ONNX Runtime — catálogo de Execution Providers: <https://onnxruntime.ai/docs/execution-providers/>

### Execução: formato, otimização e pré/pós

- **★ ONNX Runtime — ORT format model** (`.ort`, minimal build): <https://onnxruntime.ai/docs/reference/ort-format-models.html>
- ONNX Runtime — quantização (INT8/fp16): <https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html>
- ONNX Runtime — otimizações de grafo (níveis/fusão): <https://onnxruntime.ai/docs/performance/model-optimizations/graph-optimizations.html>
- **★ onnxruntime-extensions** (pré/pós no grafo: tokenização, imagem, NMS): <https://github.com/microsoft/onnxruntime-extensions>

### Entrega e storage do modelo

- Play Asset Delivery (modelos grandes fora do APK base): <https://developer.android.com/guide/playcore/asset-delivery>

### OpenCV / processamento de imagem no Android

- OpenCV — Android (SDK nativo, alternativa à wheel cv2): <https://opencv.org/android/>
- Pillow — docs (decode/resize puro-Python, sem cv2): <https://pillow.readthedocs.io/>

### Projetos comparáveis (Python embarcado no Android)

- Chaquopy — SDK Python para Android (Gradle plugin, embedding): <https://chaquo.com/chaquopy/>
- BeeWare Briefcase — empacotar apps Python (inclui Android): <https://briefcase.readthedocs.io/>
- python-for-android (Kivy) — toolchain p4a: <https://python-for-android.readthedocs.io/>

### O SDK do time

- **★ `ort-vision-sdk`** (a API de inferência que o Trilho G precisa rodar no device): <https://github.com/mauriciobenjamin700/ort-vision-sdk>

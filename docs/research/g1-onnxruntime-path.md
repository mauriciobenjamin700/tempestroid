# G1 — onnxruntime no device: caminho (A) wheel vs (B) AAR

> Spike de decisão da fase **G1** (após o marco numpy de
> [`g0-feasibility.md`](g0-feasibility.md)). Data: 2026-06-18.
> Objetivo do G1: **um `Detector`/`Classifier` do `ort-vision-sdk` rodando no
> device**, fora da UI thread, com EP escolhido e latência medida.

## Os dois caminhos, com números reais

| | (A) Wheel Python | (B) AAR nativo |
|---|---|---|
| Como obter | `tools/ci_build/build.py --build_wheel --android --android_abi x86_64` (cmake C++) | Maven `com.microsoft.onnxruntime:onnxruntime-android` |
| Disponível pronto? | **Não** — onnxruntime **não publica sdist no PyPI** (só wheels desktop); cibuildwheel **não serve** (sem PEP517). Build do source obrigatório. | **Sim** — 1.26.0 = **43,6 MB** (4 ABIs: arm64-v8a/armeabi-v7a/x86/x86_64; ~11 MB/ABI com split). |
| Roda o `ort-vision-sdk`? | **Sim** — o SDK faz `import onnxruntime` (Python); só a wheel expõe esse módulo. | **Não** — o AAR é Java/C++; **não existe módulo Python `onnxruntime`** nele. Inferência iria pra um shim Kotlin, **sem** usar o `Detector`/`Classifier` do SDK. |
| Pré/pós em numpy (já provado) | Sim, no Python | Sim, no Python (tensores cruzam a ponte) |
| Custo de build | Alto (cmake + submódulos, ~45–90 min, host-tools + cross) | Nenhum (artefato pronto) |
| Tamanho no APK | wheel C++ pesada (~10–30 MB/ABI; encolhível com custom build, G7) | ~11 MB/ABI (com split) |
| Manutenção | nós buildamos a wheel | MS mantém o AAR |

## Decisão

**O done-when do G1 — "o `Detector`/`Classifier` do SDK roda no device" — só é
satisfeito por (A).** O AAR não tem binding Python; com (B) o SDK não roda a
inferência (só seus helpers de pré/pós em numpy rodariam), e seria preciso
reimplementar o despacho de inferência em Kotlin espelhando a API do SDK. Isso
contraria o objetivo do Trilho G (rodar o `ort-vision-sdk` no app).

→ **Seguir (A): buildar a wheel do onnxruntime via `build.py --android`.** É o
caminho pesado, mas é o único que honra o objetivo. (B) fica como **fallback
explícito** só se a wheel se provar inviável — e nesse caso o G1 seria
re-escopado (inferência em Kotlin, SDK só no desktop).

Notas:
- O destravamento de C-ext do numpy (cibuildwheel 4.x, `$(BLDLIBRARY)`) **não se
  aplica** ao onnxruntime: ele usa o próprio `build.py`/cmake com o NDK, toolchain
  diferente — pode ou não bater em problemas próprios (a verificar no build).
- Começar pelo **x86_64** (emulador, mesma bancada do numpy); arm64 depois.
- Encolher (custom build com `--include_ops_by_config`, `.ort`/quantização) é o
  **G7**, não bloqueia o primeiro ponta-a-ponta.

## Resultado do spike de build (A) — 2026-06-18

Tentativa de buildar a wheel via `tools/ci_build/build.py --android --android_abi
x86_64 --build_wheel` (onnxruntime **v1.26.0**, NDK r27, cmake 3.28). Vencidos:

- tag real é `v1.26.0` (não `v1.27.0` — esse só existe no PyPI, sem tag git);
- `build.py` força `USE_KLEIDIAI=ON`/`USE_SVE=ON` (features **ARM**) num build
  x86_64 → desligar com `--no_kleidiai --no_sve`;
- o cmake precisa de `numpy` no **python do host** (`find_package(Python …
  NumPy)`) → rodar o `build.py` com o venv do projeto (tem numpy), não o
  `/usr/bin/python3`.

**Blocker que não cedeu:** no *generate step*, `CMakeLists.txt:1775` referencia o
target importado **`Python::NumPy`** que **não é criado sob o toolchain cross do
Android** (`-- Generating done` → `target was not found` → *CMake Generate step
failed*). O `find_package(Python COMPONENTS … NumPy)` não materializa o
`Python::NumPy` em modo cross.

**Leitura:** **`onnxruntime` não suporta wheel Python no Android.** O artefato
Android oficial da Microsoft é o **AAR nativo** (C++/Java); **não há wheel python
android no PyPI** e o caminho `ENABLE_PYTHON + build_wheel + --android` é território
não-trilhado (daí o `Python::NumPy` faltando no cross). Buildar (A) exigiria
**patchar o CMake do onnxruntime** para prover o `Python::NumPy` cross — alto risco,
esforço aberto.

## Decisão revisada → pivô para (B) AAR + ponte

O caminho (A) "rodar o `ort-vision-sdk` em Python fazendo inferência no device"
depende de uma wheel python android do onnxruntime que **upstream não suporta**.
Logo:

- **Inferência via (B) AAR `onnxruntime-android`** (Gradle no `android-host/`) +
  um **shim JNI** (`run(model, inputs)` → tensores pela ponte), espelhando o padrão
  `native` do B6/E8.
- **Pré/pós em Python com `numpy`** (já provado no device, G0/G1) — recebe/entrega
  tensores pela ponte.
- **Re-escopo do done-when do G1:** "um modelo `.onnx` roda ponta-a-ponta no device
  pela AAR, dirigido do Python (tensores cruzam a ponte), fora da UI thread, EP
  escolhido + latência" — em vez de `Detector.predict()` literalmente em Python.
  Os *helpers de pré/pós* do `ort-vision-sdk` (numpy) ainda rodam em Python; o
  despacho de inferência passa pela AAR.

> **Alternativa (só se rodar o SDK em Python verbatim for requisito duro):**
> investir em (A) patchando o CMake do onnxruntime para o `Python::NumPy` cross —
> registrar como sub-tarefa de alto risco antes de começar.

## Próximo passo (B)

1. Adicionar `com.microsoft.onnxruntime:onnxruntime-android` ao Gradle do
   `android-host/` (ABI split p/ caber no orçamento de tamanho — §5 da pesquisa).
2. Shim Kotlin (`OnnxModule`) sobre `OrtEnvironment`/`OrtSession` + envelope
   `native` (`infer`) roteado pelo `NativeModules` (padrão B6/E8).
3. Lado Python (`native/inference.py`): serializa tensor de entrada (numpy →
   bytes/shape/dtype), `send_native_request("infer", …)`, recebe o tensor de saída.
4. Modelo `.onnx` pequeno ponta-a-ponta no emulador, fora da UI thread, EP
   CPU→XNNPACK (NNAPI/QNN no device físico), latência medida.

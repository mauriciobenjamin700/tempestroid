# Dados e ML no dispositivo

O tempestroid roda **CPython de verdade** no aparelho (não um subset). Isso abre
uma porta que apps Android normais não têm: rodar a stack científica de Python —
`numpy`, `scikit-learn`, **`polars`**, inferência ONNX — **dentro do app**, no
mesmo interpretador que constrói a UI.

Esta página mostra o que já roda, como você habilita cada peça, e onde estão os
limites. É o **Trilho G** do roadmap.

!!! info "Onde isso foi provado"
    Tudo aqui é **device-verificado num emulador x86_64** (a stack de teste
    hardware-free; veja [Rodar no dispositivo](dispositivo-wsl.md)). O alvo de
    *ship* é arm64 — o caminho é o mesmo (as receitas são por-ABI), mas as wheels
    arm64 das libs pesadas ainda estão pendentes. O status de cada peça está na
    tabela no fim.

## Dois caminhos

Há duas formas de uma lib nativa rodar no device, e o tempestroid usa as duas:

1. **Wheel CPython cross-compilada** — a lib é compilada como uma *wheel Android*
   (mesmo padrão do `pydantic-core`) e roda no interpretador embarcado. É o
   caminho de `numpy`, `scipy`, `scikit-learn` e `polars`.
2. **Biblioteca nativa + ponte** — a lib roda como código nativo (AAR Kotlin/C++)
   e o Python fala com ela pela ponte JNI. É o caminho da **inferência ONNX**
   (`onnxruntime-android`), que evita compilar a wheel C++ pesada.

!!! note "Por que isso importa"
    Cross-compilar uma wheel resolve `import x` puro; a ponte nativa evita o peso
    de compilar engines C++ gigantes. A decisão é por-lib, registrada em
    `docs/research/`.

## numpy

`numpy` é o caminho crítico — quase toda a stack depende dele. A wheel Android é
cross-compilada com `cibuildwheel` (receita `toolchain/build_numpy_x86.sh`).

```python
import numpy as np

arr = np.arange(1, 11, dtype=np.float64)
total = float(arr.sum())     # 55
dot = float(np.dot(arr, arr))  # 385
```

Rode no emulador com o exemplo pronto:

```bash
make stage-x86          # estaga o CPython x86_64 + base (numpy incluso)
make apk-x86            # builda o APK do emulador
tempest serve examples/onnxspike/app.py   # mostra "numpy OK" no device
```

## Polars — o DataFrame do device

Para dados tabulares, **use Polars, não pandas**. Polars é um core em **Rust**
(classe `pydantic-core`), cross-compila para uma wheel **abi3** (uma wheel serve
todo CPython ≥3.10), tem **core sem dependências** e lê/escreve **CSV/JSON/Parquet
nativamente** — sem `numpy`/`pyarrow` obrigatórios.

```python
import io
import polars as pl

frame = pl.DataFrame({"team": ["a", "b", "a"], "points": [10, 7, 3]})
totals = frame.group_by("team").agg(pl.col("points").sum())

# Reading/writing: round-trip por CSV, tudo em memória
csv_text = frame.write_csv()
restored = pl.read_csv(io.StringIO(csv_text))
```

Habilite (opt-in — o core Rust é grande):

```bash
make stage-polars       # estaga a wheel polars-runtime-32 (abi3) + o wrapper
make apk-x86
tempest serve examples/polarsspike/app.py
```

!!! warning "pandas é desencorajado"
    Se o seu app importa `pandas`, o loader emite um aviso orientando a usar
    Polars (`tempestroid/cli/advisories.py`). pandas arrasta extensões Cython/C
    pesadas + deps científicas pro APK e é chato de cross-compilar; Polars é a
    escolha que cabe no device. O import ainda roda no simulador — é um **aviso**,
    não um erro.

!!! info "Receita do build"
    `toolchain/build_polars_x86.sh` cross-compila o `polars-runtime-32` via
    `maturin`. Os detalhes (features Android-safe, strip, o blocker do clipboard)
    estão em [`docs/research/g-polars-feasibility.md`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/docs/research/g-polars-feasibility.md).

## scikit-learn + scipy

ML clássico roda no device. `scipy` e `scikit-learn` cross-compilam **só com
clang, zero Fortran** (o "calcanhar" histórico sumiu upstream: OpenBLAS em C +
scipy fortran-free), com OpenMP via a `libomp` do NDK.

```python
import numpy as np
from sklearn.linear_model import LogisticRegression

x = np.arange(0, 10, dtype=np.float64).reshape(-1, 1)
y = (x.ravel() >= 5).astype(np.int64)
model = LogisticRegression().fit(x, y)
preds = model.predict(np.array([[2.0], [8.0]]))  # [0, 1]
```

Habilite (opt-in — scipy + sklearn + deps são pesados):

```bash
make stage-science      # scipy + scikit-learn + joblib/threadpoolctl/narwhals
make apk-x86
tempest serve examples/sklearnspike/app.py
```

## Inferência ONNX (visão)

!!! check "O emulador valida inferência real — sem device físico"
    **`make vision-verify`** roda `examples/visionspike/app.py` num emulador
    x86_64 headless (KVM): builda a APK com `--feature vision`, empurra via
    `tempest serve`, e a APK roda **squeezenet1.1 na `banana.jpg`** pelo AAR
    `onnxruntime-android` (decode nativo → pré/pós em `numpy` → inferência). O
    harness **afirma o resultado no logcat** — `VISIONSPIKE_RESULT ok=1
    top1=banana` (não só que o app subiu). Assim o porting de um modelo de visão
    é validável ponta-a-ponta no emulador. Roda **na CI** (job
    `emulator-vision`, `.github/workflows/android-emulator.yml`).

    Smoke mais leve (só imports + compute): `examples/visionsmoke/app.py` →
    "VISION OK — numpy … ort_vision_sdk …".

Para rodar modelos `.onnx` (classificação, detecção, segmentação) use o
[`ort-vision-sdk`](https://github.com/mauriciobenjamin700/ort-vision-sdk) com o
backend nativo do tempestroid: o SDK roda a inferência pelo **AAR
`onnxruntime-android`** pela ponte (caminho 2), com o pré/pós em `numpy` no
Python.

```python
from ort_vision_sdk import Classifier
from tempestroid.native.inference import AarBackend

clf = Classifier("squeezenet1.1.onnx", backend=AarBackend())
result = clf.predict("banana.jpg")[0]   # top-1 no device
```

O caminho de imagem não precisa de OpenCV: `tempestroid.native.image.decode_image`
decodifica via `BitmapFactory` do host → `ndarray`. Modelos podem ser **embutidos**
ou **baixados+cacheados** (`tempestroid.native.model_store.ensure_model`, com
verificação sha256, fora da UI thread). `tempest optimize model.onnx -q int8`
quantiza + converte pra `.ort` no host (build time).

!!! warning "Como shippar um app de visão (senão dá `no module named ort_vision_sdk`)"
    O `ort_vision_sdk` é **opt-in**: um `tempest build`/`run`/`deploy` padrão
    monta o APK a partir do host **enxuto** (sem a stack de visão), então
    `import ort_vision_sdk` estoura no device. Para embarcá-lo:

    1. **Host (build-time):** `pip install "tempestroid[vision]"` — traz o
       `ort-vision-sdk` + `onnx` para o tooling do host (`tempest optimize`).
    2. **Feature `vision` no build** — no `pyproject.toml`:

        ```toml
        [tool.tempest]
        app = "app.py"
        features = ["vision"]
        ```

        ou por flag: `tempest build app.py --feature vision`. Isso (a) força um
        **build from-source** (SDK/NDK), (b) empacota o AAR `onnxruntime-android`
        e (c) seta `TEMPEST_VISION=1` no staging, que copia o `ort_vision_sdk`
        (+ shim PIL) para o `site-packages` do device. `tempest run` também lê
        `[tool.tempest] features`.
    3. **numpy para a ABI alvo** — o `ort_vision_sdk` importa `numpy`, então a
       wheel Android de numpy precisa estar staged. Emulador: `make stage-x86`.
       Device arm64: `make numpy-arm64` (cross-compila `wheels-arm64-v8a/`, que o
       staging inclui). Sem ela o staging avisa e o `import` falha no `numpy`,
       não no SDK. Ambas as receitas precisam de host com Android NDK +
       `cibuildwheel >= 4.0` (não rodam no WSL puro).

## Receitas de staging (resumo)

As libs pesadas são **opt-in** — o build padrão não carrega nenhuma. Cada uma tem
uma receita por-ABI:

| Lib | Habilitar | Wheel/recipe |
|---|---|---|
| numpy (x86_64) | `make stage-x86` (base) | `toolchain/build_numpy_x86.sh` |
| numpy (arm64-v8a) | `make numpy-arm64` | `toolchain/build_numpy_arm64.sh` (`build_numpy.sh arm64-v8a`) |
| polars | `make stage-polars` | `toolchain/build_polars_x86.sh` |
| scipy + sklearn | `make stage-science` | `toolchain/build_{openblas,scipy,sklearn}_x86.sh` |
| onnxruntime | feature `vision` no build | AAR `onnxruntime-android` (sem wheel) |

## Tamanho do APK

A stack científica é pesada. O **Trilho G7** corta o que dá com segurança:

- **`noCompress("so")`** — as `.so` de assets não são comprimidas (o compressor do
  AGP crasha em `.so` grande; elas são extraídas em runtime de qualquer forma).
- **strip** — as `.so` Rust/C saem stripadas (a do polars cai de ~2.4 GB pra
  ~200 MB).
- **ABI única** — só a `.so` da ABI alvo entra (o build não vaza a outra ABI).
- **trim do numpy** — `numpy/tests`, `f2py`, stubs `*.pyi` (runtime-dead) saem.

## Status por peça

| Peça | x86_64 (emulador) | arm64 (ship) |
|---|---|---|
| numpy | ✅ import + compute | 🚧 wheel builda (`make numpy-arm64`, `.so` aarch64), run no device físico pendente |
| scipy + scikit-learn | ✅ import + `fit`/`predict` | ⏳ rebuild |
| Polars | ✅ build + `import` (op-path `PySeries` pendente) | ⏳ rebuild |
| ONNX (ort-vision-sdk via AAR) | ✅ `Classifier` real (squeezenet) | ⏳ device físico |
| pandas | 🚫 desencorajado → Polars | 🚫 |

## Recap

- O tempestroid roda CPython real no device → a stack científica de Python roda
  **dentro do app**.
- **Polars** é o DataFrame do device (Rust, abi3, leve); **pandas é
  desencorajado** (aviso automático).
- `numpy`, `scipy`/`scikit-learn` e a **inferência ONNX** (via AAR) rodam no
  emulador hoje; cada lib pesada é **opt-in** por uma receita `make stage-*`.
- O Trilho G7 corta o APK (noCompress/strip/ABI-única/trim).
- Tudo provado no emulador x86_64; arm64 (o ship real) é o próximo passo.

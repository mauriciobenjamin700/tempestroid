# Data & ML on device

tempestroid runs **real CPython** on the device (not a subset). That opens a door
ordinary Android apps don't have: running Python's scientific stack — `numpy`,
`scikit-learn`, **`polars`**, ONNX inference — **inside the app**, in the same
interpreter that builds the UI.

This page shows what already runs, how you enable each piece, and where the limits
are. It is the roadmap's **Trilho G**.

!!! info "Where this was proven"
    Everything here is **device-verified on an x86_64 emulator** (the
    hardware-free test stack; see [Running on a device](dispositivo-wsl.md)). The
    *ship* target is arm64 — the path is identical (recipes are per-ABI), but the
    arm64 wheels for the heavy libs are still pending. Per-piece status is in the
    table at the end.

## Two paths

A native lib can reach the device in two ways, and tempestroid uses both:

1. **Cross-compiled CPython wheel** — the lib is compiled as an *Android wheel*
   (the same pattern as `pydantic-core`) and runs in the embedded interpreter.
   This is the path for `numpy`, `scipy`, `scikit-learn` and `polars`.
2. **Native library + bridge** — the lib runs as native code (a Kotlin/C++ AAR)
   and Python talks to it over the JNI bridge. This is the path for **ONNX
   inference** (`onnxruntime-android`), avoiding the heavy C++ wheel build.

!!! note "Why it matters"
    Cross-compiling a wheel solves plain `import x`; the native bridge avoids the
    weight of compiling giant C++ engines. The choice is per-lib, recorded under
    `docs/research/`.

## numpy

`numpy` is the critical path — almost the whole stack depends on it. The Android
wheel is cross-compiled with `cibuildwheel` (recipe
`toolchain/build_numpy_x86.sh`).

```python
import numpy as np

arr = np.arange(1, 11, dtype=np.float64)
total = float(arr.sum())       # 55
dot = float(np.dot(arr, arr))  # 385
```

Run it on the emulator with the ready-made example:

```bash
make stage-x86          # stage the x86_64 CPython + base (numpy included)
make apk-x86            # build the emulator APK
tempest serve examples/onnxspike/app.py   # shows "numpy OK" on device
```

## Polars — the device DataFrame

For tabular data, **use Polars, not pandas**. Polars is a **Rust** core (the
`pydantic-core` class), cross-compiles to an **abi3** wheel (one wheel for all
CPython ≥3.10), has a **dependency-free core**, and reads/writes
**CSV/JSON/Parquet natively** — no `numpy`/`pyarrow` required.

```python
import io
import polars as pl

frame = pl.DataFrame({"team": ["a", "b", "a"], "points": [10, 7, 3]})
totals = frame.group_by("team").agg(pl.col("points").sum())

# Reading/writing: a CSV round-trip, entirely in memory
csv_text = frame.write_csv()
restored = pl.read_csv(io.StringIO(csv_text))
```

Enable it (opt-in — the Rust core is large):

```bash
make stage-polars       # stage the polars-runtime-32 wheel (abi3) + the wrapper
make apk-x86
tempest serve examples/polarsspike/app.py
```

!!! warning "pandas is discouraged"
    If your app imports `pandas`, the loader emits a warning steering you to
    Polars (`tempestroid/cli/advisories.py`). pandas drags heavy Cython/C
    extensions + scientific deps into the APK and is awkward to cross-compile;
    Polars is the choice that fits the device. The import still runs in the
    simulator — it's a **warning**, not an error.

!!! info "Build recipe"
    `toolchain/build_polars_x86.sh` cross-compiles `polars-runtime-32` via
    `maturin`. The details (Android-safe features, strip, the clipboard blocker)
    are in [`docs/research/g-polars-feasibility.md`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/docs/research/g-polars-feasibility.md).

## scikit-learn + scipy

Classic ML runs on the device. `scipy` and `scikit-learn` cross-compile with
**clang only, zero Fortran** (the historical "Achilles' heel" is gone upstream:
OpenBLAS in C + a Fortran-free scipy), with OpenMP via the NDK's `libomp`.

```python
import numpy as np
from sklearn.linear_model import LogisticRegression

x = np.arange(0, 10, dtype=np.float64).reshape(-1, 1)
y = (x.ravel() >= 5).astype(np.int64)
model = LogisticRegression().fit(x, y)
preds = model.predict(np.array([[2.0], [8.0]]))  # [0, 1]
```

Enable it (opt-in — scipy + sklearn + deps are heavy):

```bash
make stage-science      # scipy + scikit-learn + joblib/threadpoolctl/narwhals
make apk-x86
tempest serve examples/sklearnspike/app.py
```

## ONNX inference (vision)

To run `.onnx` models (classification, detection, segmentation) use the
[`ort-vision-sdk`](https://github.com/mauriciobenjamin700/ort-vision-sdk) with
tempestroid's native backend: the SDK runs inference through the **`onnxruntime-android`
AAR** over the bridge (path 2), with `numpy` pre/post in Python.

```python
from ort_vision_sdk import Classifier
from tempestroid.native.inference import AarBackend

clf = Classifier("squeezenet1.1.onnx", backend=AarBackend())
result = clf.predict("banana.jpg")[0]   # top-1 on device
```

The image path needs no OpenCV: `tempestroid.native.image.decode_image` decodes
via the host's `BitmapFactory` → `ndarray`. Models can be **embedded** or
**downloaded+cached** (`tempestroid.native.model_store.ensure_model`, with sha256
verification, off the UI thread). `tempest optimize model.onnx -q int8` quantizes
+ converts to `.ort` on the host (build time).

!!! warning "Shipping a vision app (else you get `no module named ort_vision_sdk`)"
    `ort_vision_sdk` is **opt-in**: a default `tempest build`/`run`/`deploy`
    assembles the APK from the **lean** host (no vision stack), so
    `import ort_vision_sdk` crashes on device. To bundle it:

    1. **Host (build-time):** `pip install "tempestroid[vision]"` — brings
       `ort-vision-sdk` + `onnx` for the host tooling (`tempest optimize`).
    2. **The `vision` feature** — in `pyproject.toml`:

        ```toml
        [tool.tempest]
        app = "app.py"
        features = ["vision"]
        ```

        or via flag: `tempest build app.py --feature vision`. This (a) forces a
        **from-source build** (SDK/NDK), (b) bundles the `onnxruntime-android`
        AAR, and (c) sets `TEMPEST_VISION=1` for staging, which copies
        `ort_vision_sdk` (+ a PIL shim) into the device `site-packages`.
        `tempest run` reads `[tool.tempest] features` too.
    3. **numpy for the target ABI** — `ort_vision_sdk` imports `numpy`, so the
       Android numpy wheel must be staged (`make stage-x86` on the emulator; the
       arm64 wheel is still pending — see the staging table below). Without it
       the staging warns and the `import` fails on `numpy`, not on the SDK.

## Staging recipes (summary)

The heavy libs are **opt-in** — the default build carries none. Each has a
per-ABI recipe:

| Lib | Enable | Wheel/recipe |
|---|---|---|
| numpy | `make stage-x86` (base) | `toolchain/build_numpy_x86.sh` |
| polars | `make stage-polars` | `toolchain/build_polars_x86.sh` |
| scipy + sklearn | `make stage-science` | `toolchain/build_{openblas,scipy,sklearn}_x86.sh` |
| onnxruntime | the `vision` build feature | `onnxruntime-android` AAR (no wheel) |

## APK size

The scientific stack is heavy. **Trilho G7** trims what it safely can:

- **`noCompress("so")`** — asset `.so` are not compressed (AGP's compressor
  crashes on a large `.so`; they're extracted at runtime anyway).
- **strip** — Rust/C `.so` ship stripped (polars' drops from ~2.4 GB to ~200 MB).
- **single ABI** — only the target ABI's `.so` is packaged (the build doesn't
  leak the other ABI).
- **numpy trim** — `numpy/tests`, `f2py`, `*.pyi` stubs (runtime-dead) are dropped.

## Per-piece status

| Piece | x86_64 (emulator) | arm64 (ship) |
|---|---|---|
| numpy | ✅ import + compute | ⏳ rebuild |
| scipy + scikit-learn | ✅ import + `fit`/`predict` | ⏳ rebuild |
| Polars | ✅ build + `import` (op-path `PySeries` pending) | ⏳ rebuild |
| ONNX (ort-vision-sdk via AAR) | ✅ real `Classifier` (squeezenet) | ⏳ physical device |
| pandas | 🚫 discouraged → Polars | 🚫 |

## Recap

- tempestroid runs real CPython on device → Python's scientific stack runs
  **inside the app**.
- **Polars** is the device DataFrame (Rust, abi3, light); **pandas is
  discouraged** (automatic warning).
- `numpy`, `scipy`/`scikit-learn` and **ONNX inference** (via the AAR) run on the
  emulator today; each heavy lib is **opt-in** via a `make stage-*` recipe.
- Trilho G7 trims the APK (noCompress/strip/single-ABI/trim).
- All proven on the x86_64 emulator; arm64 (the real ship target) is next.

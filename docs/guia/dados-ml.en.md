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

!!! check "The emulator validates real inference — no physical device"
    **`make vision-verify`** runs `examples/visionspike/app.py` on a headless
    x86_64 emulator (KVM): it builds the APK with `--feature vision`, pushes it
    via `tempest serve`, and the APK runs **squeezenet1.1 on `banana.jpg`**
    through the `onnxruntime-android` AAR (native decode → `numpy` pre/post →
    inference). The harness **asserts the result in logcat** —
    `VISIONSPIKE_RESULT ok=1 top1=banana` (not just that the app mounted). So a
    vision model's port is validated end-to-end on the emulator. Runs **in CI**
    (job `emulator-vision`, `.github/workflows/android-emulator.yml`).

    Lighter smoke (imports + compute only): `examples/visionsmoke/app.py` →
    "VISION OK — numpy … ort_vision_sdk …".

!!! check "Also verified on real arm64 hardware"
    The **standalone APK flow** (`tempest build examples/visionspike/app.py
    --feature vision --from-source` → install → launch, **no** `tempest serve`)
    runs inference on the physical phone (Redmi 12, arm64): **top-1 banana
    (81.5%), provider=AAR, 886 ms**. Evidence under `docs/assets/device/`.

The vision API lives in **`tempestroid.vision`** — a *platform-aware* wrapper over
[`ort-vision-sdk`](https://github.com/mauriciobenjamin700/ort-vision-sdk). An app
expresses only its **domain** (which models, thresholds, crop/label logic) and
**never branches on platform**: the same code runs on device (`onnxruntime-android`
AAR + `BitmapFactory`) and on the desktop / Qt simulator (in-process `onnxruntime`
+ Pillow). `numpy` is imported lazily, so a lean install stays NumPy-free.

### Classify an image

```python
from tempestroid.vision import Classifier

clf = await Classifier.create("squeezenet1.1.onnx")
result = (await clf.predict("banana.jpg"))[0]   # bytes/path decoded on device
print(result)                                    # top-k with label + confidence
```

`create` is async (loads the right per-platform backend) and `predict` runs
inference **off the UI thread**. Pass **bytes, a path, or an HWC uint8 RGB
`ndarray`** — on device the first two are decoded through `decode_image` first (the
SDK's own decode needs Pillow/cv2, absent on device).

### Detection (boxes) and segmentation (masks)

`Detector` and `Segmenter` share the `Classifier` shape:

```python
from tempestroid.vision import Detector

det = await Detector.create("yolo.onnx", labels="coco")
for r in (await det.predict(image_bytes))[0]:
    print(r.class_name, r.confidence, r.box.xyxy)
```

`Segmenter` returns boxes **plus one mask per instance** (`.masks`).

### Overlays — bake the result onto a frame

`draw_boxes` / `overlay_masks` are **numpy-in / numpy-out** (they run on device):

```python
from tempestroid.vision import draw_boxes, encode_image

boxes = [r.box.xyxy for r in results]
annotated = draw_boxes(frame, boxes)            # outlines (cycles a palette)
data, mime = encode_image(annotated)            # → data: URI for an Image widget
```

!!! tip "Boxes with captions = the `DetectionOverlay` widget"
    `draw_boxes` strokes outlines only (text needs a font rasteriser the device
    lacks). For crisp vector boxes **with labels**, use the `tempest_core`
    `DetectionOverlay` widget (a `Canvas` over an `Image`, on both renderers).

### Live camera-stream detection

`CameraPreview(on_frame=…, frame_interval_ms=…)` delivers a `CameraFrameEvent` per
throttled frame. `frame_array(event)` rebuilds the `ndarray` to feed a
`Detector`/`Segmenter` live:

```python
from tempestroid.vision import Detector, frame_array

async def on_frame(event):
    results = (await detector.predict(frame_array(event)))[0]
    ...  # update state with results (draw back with draw_boxes/overlay_masks)

CameraPreview(on_frame=lambda e: on_frame(e), frame_interval_ms=400)
```

### Domain helpers + low-level session

- `crop_box(image, x, y, w, h)` — clamped ROI crop (falls back to the whole image on a degenerate box).
- `mean_luminance(image)` — BT.709 mean luma in `[0, 255]` (gate a too-dark capture).
- `top_class(scores, labels=None, *, apply_softmax=False)` → `(index, label, conf)`.
- `OrtSession` — the raw ONNX session when you build pre/post by hand:
  `session = await OrtSession.create("m.onnx")` → `await session.run({session.input_name: tensor})`.

The low-level escape hatch is `tempestroid.native.inference.AarBackend` (what the
wrappers use underneath), but prefer `tempestroid.vision` — it runs **identically on
both targets**.

The image path needs no OpenCV: `decode_image` decodes via the host's
`BitmapFactory` → `ndarray`. Models can be **embedded** or **downloaded+cached**
(`tempestroid.native.model_store.ensure_model`, with sha256 verification, off the
UI thread). `tempest optimize model.onnx -q int8` quantizes + converts to `.ort` on
the host (build time).

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
       Android numpy wheel must be staged. Emulator: `make stage-x86`. arm64
       device: `make numpy-arm64` (cross-compiles `wheels-arm64-v8a/`, which the
       staging then bundles). Without it the staging warns and the `import` fails
       on `numpy`, not on the SDK. Both recipes need an Android-NDK host +
       `cibuildwheel >= 4.0` (they do not run under plain WSL).

## Staging recipes (summary)

The heavy libs are **opt-in** — the default build carries none. Each has a
per-ABI recipe:

| Lib | Enable | Wheel/recipe |
|---|---|---|
| numpy (x86_64) | `make stage-x86` (base) | `toolchain/build_numpy_x86.sh` |
| numpy (arm64-v8a) | `make numpy-arm64` | `toolchain/build_numpy_arm64.sh` (`build_numpy.sh arm64-v8a`) |
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
| numpy | ✅ import + compute | 🚧 wheel builds (`make numpy-arm64`, aarch64 `.so`), physical-device run pending |
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

"""ONNX inference on the device via the native ``onnxruntime-android`` AAR.

This is the Trilho G bridge: it lets the [`ort-vision-sdk`](https://pypi.org/project/ort-vision-sdk/)
run a real model on an Android device even though there is **no** ``onnxruntime``
Python wheel for Android. ONNX Runtime ships for Android only as a native AAR, so
the inference runs in Kotlin/C++ on the host; Python keeps doing the SDK's
preprocessing/postprocessing in NumPy.

The seam is the SDK's ``InferenceBackend`` protocol (ort-vision-sdk ≥ 0.4.0):
:class:`AarBackend` implements it, marshalling the input tensor to the host over
the **existing** request/response native channel (no new C/JNI entry point) under
the ``onnx`` module:

* ``load`` — open a model on the host; the reply carries the model's input/output
  names and shapes, so the SDK can read metadata (``num_classes`` etc.)
  synchronously after the backend is constructed.
* ``infer`` — run one inference; the reply carries the output tensors.

Tensors cross the bridge as JSON-able dicts ``{"dtype", "shape", "data"}`` where
``data`` is base64 of the raw little-endian buffer (the bridge speaks JSON, so raw
bytes are base64-encoded).

Usage on device (async-first, off the UI thread)::

    from ort_vision_sdk import Detector
    from tempestroid.native.inference import AarBackend

    backend = await AarBackend.create("model.onnx")   # host loadModel + metadata
    det = Detector("model.onnx", backend=backend)      # sync; reads metadata
    results = await det.ort_async_predict(image)       # inference over the bridge
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tempestroid.native.dispatch import send_native_request

if TYPE_CHECKING:
    import numpy as np

__all__ = ["AarBackend", "encode_tensor", "decode_tensor"]

#: Native module name routed by the host's ``NativeModules`` to the ONNX module.
_MODULE = "onnx"


def encode_tensor(array: np.ndarray) -> dict[str, Any]:
    """Encode a NumPy array as a JSON-able tensor envelope.

    Args:
        array: The array to encode (any dtype/shape).

    Returns:
        A dict ``{"dtype", "shape", "data"}`` where ``data`` is base64 of the
        contiguous little-endian raw buffer.
    """
    import numpy as np

    contiguous = np.ascontiguousarray(array)
    return {
        "dtype": str(contiguous.dtype),
        "shape": list(contiguous.shape),
        "data": base64.b64encode(contiguous.tobytes()).decode("ascii"),
    }


def decode_tensor(envelope: dict[str, Any]) -> np.ndarray:
    """Decode a tensor envelope produced by :func:`encode_tensor` (or the host).

    Args:
        envelope: A dict ``{"dtype", "shape", "data"}`` (``data`` base64).

    Returns:
        The reconstructed NumPy array.
    """
    import numpy as np

    raw = base64.b64decode(envelope["data"])
    dtype = np.dtype(str(envelope["dtype"]))
    shape = tuple(int(d) for d in envelope["shape"])
    return np.frombuffer(raw, dtype=dtype).reshape(shape)


def _to_shape_tuples(
    shapes: list[list[int | str]],
) -> list[tuple[int | str, ...]]:
    """Normalize JSON shape lists to tuples (dynamic dims stay strings).

    Args:
        shapes: Shapes as JSON lists (ints or strings for dynamic dims).

    Returns:
        The shapes as tuples.
    """
    return [tuple(s) for s in shapes]


class AarBackend:
    """An ``InferenceBackend`` that runs inference on the native ONNX AAR.

    Construct it with :meth:`create` (an async factory that loads the model on
    the host and fetches its metadata), then hand it to any ort-vision-sdk task
    via ``backend=``. The model metadata is available synchronously afterwards,
    so the task's constructor (which reads ``output_shapes`` to infer
    ``num_classes``) works without awaiting.

    Inference is async: prefer ``await task.ort_async_predict(image)``. The sync
    :meth:`run` is supported only when called off the app's event loop (e.g. via
    ``task.async_predict``, which runs the sync ``predict`` in a worker thread);
    calling it on the loop thread raises, since it cannot block the loop on the
    bridge round-trip.

    Methods:
        create: Async factory — load a model on the host and capture metadata.
        run: Synchronous inference (worker-thread only; bridges to the host).
        async_run: Async inference over the bridge.
        ort_async_run: Async inference over the bridge (alias of async_run).
    """

    def __init__(
        self,
        session_id: str,
        *,
        input_names: list[str],
        input_shapes: list[tuple[int | str, ...]],
        output_names: list[str],
        output_shapes: list[tuple[int | str, ...]],
        loop: asyncio.AbstractEventLoop | None = None,
        provider: str = "",
    ) -> None:
        """Initialize the backend around an already-loaded host session.

        Prefer :meth:`create`; this constructor is for tests and advanced use.

        Args:
            session_id: The host-side session id returned by ``load``.
            input_names: The model's input names.
            input_shapes: The model's input shapes (dynamic dims as strings).
            output_names: The model's output names.
            output_shapes: The model's output shapes (dynamic dims as strings).
            loop: The event loop the device app runs on, used to bridge the sync
                :meth:`run` from a worker thread. Defaults to the running loop.
            provider: The execution provider the host opened the session with
                (``"CPU"`` / ``"NNAPI"`` / ``"XNNPACK"``); empty when unknown.
        """
        self._session_id = session_id
        self._provider = provider
        self._input_names = list(input_names)
        self._input_shapes = list(input_shapes)
        self._output_names = list(output_names)
        self._output_shapes = list(output_shapes)
        try:
            self._loop = loop if loop is not None else asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

    @classmethod
    async def create(
        cls,
        model_path: str | Path,
        *,
        providers: list[str] | None = None,
    ) -> AarBackend:
        """Load ``model_path`` on the host and return a ready backend.

        Sends the ``load`` command over the bridge and captures the model's
        input/output metadata so the SDK can read it synchronously.

        Args:
            model_path: Path to the ``.onnx`` model on the device filesystem.
            providers: Optional execution-provider hint for the host (the AAR
                chooses the Android EP chain, e.g. NNAPI → XNNPACK → CPU). The
                ORT-Python provider names are not used here.

        Returns:
            A backend bound to the loaded host session.

        Raises:
            NativeError: If the host fails to load the model.
        """
        data = await send_native_request(
            _MODULE,
            "load",
            {"path": str(model_path), "providers": list(providers or [])},
        )
        return cls(
            str(data["session_id"]),
            input_names=[str(n) for n in data.get("input_names", [])],
            input_shapes=_to_shape_tuples(data.get("input_shapes", [])),
            output_names=[str(n) for n in data.get("output_names", [])],
            output_shapes=_to_shape_tuples(data.get("output_shapes", [])),
            provider=str(data.get("provider", "")),
        )

    @property
    def session_id(self) -> str:
        """The host-side session id this backend drives."""
        return self._session_id

    @property
    def provider(self) -> str:
        """The execution provider the host opened this session with (diagnostics)."""
        return self._provider

    @property
    def input_names(self) -> list[str]:
        """Names of the model's inputs, in declaration order."""
        return list(self._input_names)

    @property
    def input_name(self) -> str:
        """Name of the first (and usually only) input."""
        return self._input_names[0]

    @property
    def input_shapes(self) -> list[tuple[int | str, ...]]:
        """Declared shapes of the inputs (dynamic dims appear as strings)."""
        return list(self._input_shapes)

    @property
    def input_shape(self) -> tuple[int | str, ...]:
        """Declared shape of the first input."""
        return self._input_shapes[0]

    @property
    def output_names(self) -> list[str]:
        """Names of the model's outputs, in declaration order."""
        return list(self._output_names)

    @property
    def output_shapes(self) -> list[tuple[int | str, ...]]:
        """Declared shapes of the outputs (dynamic dims appear as strings)."""
        return list(self._output_shapes)

    async def _infer(
        self,
        feeds: dict[str, np.ndarray],
        output_names: list[str] | None,
    ) -> list[np.ndarray]:
        """Run one inference on the host and decode its output tensors.

        Args:
            feeds: Mapping of input name to NumPy array.
            output_names: Outputs to fetch; ``None`` fetches all in order.

        Returns:
            One NumPy array per output, in the host's returned order.

        Raises:
            NativeError: If the host reports the inference failed.
        """
        encoded = {name: encode_tensor(arr) for name, arr in feeds.items()}
        data = await send_native_request(
            _MODULE,
            "infer",
            {
                "session_id": self._session_id,
                "inputs": encoded,
                "output_names": list(output_names) if output_names else [],
            },
        )
        outputs = data.get("outputs", [])
        return [decode_tensor(o) for o in outputs]

    def run(
        self,
        feeds: dict[str, np.ndarray],
        *,
        output_names: list[str] | None = None,
    ) -> list[np.ndarray]:
        """Run inference synchronously (worker-thread only).

        The device app loop is async; this sync method must be driven from a
        worker thread (as ``task.async_predict`` does via ``asyncio.to_thread``),
        scheduling the bridge round-trip on the app loop and blocking the worker
        for the result. Calling it on the loop thread raises (it cannot block the
        loop) — use ``await task.ort_async_predict(...)`` there instead.

        Args:
            feeds: Mapping of input name to NumPy array.
            output_names: Outputs to fetch; ``None`` fetches all in order.

        Returns:
            One NumPy array per output, in order.

        Raises:
            RuntimeError: If no app loop is bound, or if called on the loop
                thread (where blocking is impossible).
            NativeError: If the host reports the inference failed.
        """
        if self._loop is None:
            raise RuntimeError(
                "AarBackend.run needs the app event loop; construct via "
                "AarBackend.create on the running loop."
            )
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._loop:
            raise RuntimeError(
                "AarBackend.run cannot block the app loop; use "
                "await task.ort_async_predict(...) (or task.async_predict) instead."
            )
        future = asyncio.run_coroutine_threadsafe(
            self._infer(feeds, output_names), self._loop
        )
        return future.result()

    async def async_run(
        self,
        feeds: dict[str, np.ndarray],
        *,
        output_names: list[str] | None = None,
    ) -> list[np.ndarray]:
        """Run inference asynchronously over the bridge.

        Args:
            feeds: Mapping of input name to NumPy array.
            output_names: Outputs to fetch; ``None`` fetches all in order.

        Returns:
            One NumPy array per output, in order.
        """
        return await self._infer(feeds, output_names)

    async def ort_async_run(
        self,
        feeds: dict[str, np.ndarray],
        *,
        output_names: list[str] | None = None,
    ) -> list[np.ndarray]:
        """Run inference asynchronously over the bridge (alias of :meth:`async_run`).

        The AAR has no separate ORT thread-pool path exposed here, so this simply
        bridges to the host like :meth:`async_run`.

        Args:
            feeds: Mapping of input name to NumPy array.
            output_names: Outputs to fetch; ``None`` fetches all in order.

        Returns:
            One NumPy array per output, in order.
        """
        return await self._infer(feeds, output_names)

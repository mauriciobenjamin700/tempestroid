"""Native biometric-authentication capability (phase E8).

:func:`authenticate` is request/response: the Kotlin ``BiometricsModule`` drives
``androidx.biometric.BiometricPrompt`` and replies with the
:class:`BiometricResult`. The Qt simulator has no biometric hardware, so it
raises :class:`~tempestroid.native.dispatch.NativeError` with the
``device_only`` code.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from tempestroid.native.dispatch import NativeError, on_device, send_native_request

__all__ = ["BiometricResult", "authenticate"]


class BiometricResult(BaseModel):
    """The outcome of a biometric authentication prompt.

    Attributes:
        authenticated: Whether the user authenticated successfully.
        error: A short error code when authentication failed/was cancelled, or
            ``None`` on success.
    """

    model_config = ConfigDict(frozen=True)

    authenticated: bool
    error: str | None = None


async def authenticate(reason: str = "") -> BiometricResult:
    """Prompt the user to authenticate with a biometric (fingerprint/face).

    Args:
        reason: The prompt subtitle explaining why authentication is requested.

    Returns:
        The :class:`BiometricResult` reported by the host.

    Raises:
        NativeError: On the Qt simulator (``device_only``) — biometrics need
            real hardware.
    """
    if not on_device():
        raise NativeError(
            "device_only", "biometrics not supported on Qt simulator"
        )
    data = await send_native_request("biometrics", "authenticate", {"reason": reason})
    return BiometricResult.model_validate(data)

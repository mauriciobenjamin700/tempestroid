"""Native runtime-permissions capability (phase E8).

:func:`request_permission` and :func:`check_permission` are request/response: the
Kotlin ``PermissionsModule`` drives ``ActivityResultContracts.RequestPermission``
and replies with the resulting :class:`PermissionResult`. On the Qt simulator
there is no permission model — a desktop has every capability — so both return
:data:`PermissionStatus.GRANTED` immediately.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from tempestroid.native.dispatch import on_device, send_native_request

__all__ = [
    "PermissionStatus",
    "PermissionResult",
    "request_permission",
    "check_permission",
]


class PermissionStatus(StrEnum):
    """The outcome of a runtime-permission request/check.

    Attributes:
        GRANTED: The app holds the permission and may use the capability now.
        DENIED: The user declined the permission, but the system will still
            prompt again on a future request (a soft, retryable refusal).
        PERMANENTLY_DENIED: The user refused and selected "don't ask again"
            (or denied twice on newer Android), so the system will no longer
            show the prompt — the app must direct the user to the settings
            screen to grant it manually.
    """

    GRANTED = "granted"
    DENIED = "denied"
    PERMANENTLY_DENIED = "permanently_denied"


class PermissionResult(BaseModel):
    """The result of a permission request or check.

    Attributes:
        permission: The Android permission string (e.g.
            ``"android.permission.CAMERA"``).
        status: The resulting grant status.
    """

    model_config = ConfigDict(frozen=True)

    permission: str
    status: PermissionStatus


async def request_permission(permission: str) -> PermissionResult:
    """Request a runtime permission, prompting the user if needed.

    Args:
        permission: The Android permission string to request.

    Returns:
        The :class:`PermissionResult` reported by the host (always granted on
        the Qt simulator).
    """
    if not on_device():
        return PermissionResult(permission=permission, status=PermissionStatus.GRANTED)
    data = await send_native_request(
        "permissions", "request", {"permission": permission}
    )
    return PermissionResult.model_validate({"permission": permission, **data})


async def check_permission(permission: str) -> PermissionResult:
    """Check whether a runtime permission is already granted.

    Args:
        permission: The Android permission string to check.

    Returns:
        The :class:`PermissionResult` reported by the host (always granted on
        the Qt simulator).
    """
    if not on_device():
        return PermissionResult(permission=permission, status=PermissionStatus.GRANTED)
    data = await send_native_request("permissions", "check", {"permission": permission})
    return PermissionResult.model_validate({"permission": permission, **data})

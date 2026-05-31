"""Unit tests for the Android device-size presets."""

from __future__ import annotations

import pytest

from tempestroid import DEFAULT_DEVICE, Device


def test_size_property() -> None:
    """``Device.size`` returns the ``(width, height)`` tuple."""
    assert Device.PIXEL_7.size == (412, 915)
    assert Device.PIXEL_7.size == (Device.PIXEL_7.width, Device.PIXEL_7.height)


def test_label_carried_per_member() -> None:
    """Each member exposes a human-readable label."""
    assert Device.REDMI_NOTE_12.label == "Xiaomi Redmi Note 12"


def test_same_size_members_are_not_aliased() -> None:
    """Phones sharing a viewport stay distinct members (value is the label)."""
    assert Device.REDMI_NOTE_12 is not Device.REDMI_NOTE_11
    assert Device.REDMI_NOTE_12.size == Device.REDMI_NOTE_11.size
    assert len(Device) == len(Device.__members__)  # no collapsed aliases


def test_all_sizes_are_positive() -> None:
    """Every preset has a sane positive viewport (phones taller than wide)."""
    for device in Device:
        assert device.width > 0
        assert device.height > 0
        assert device.height > device.width


def test_default_device_is_a_member() -> None:
    """``DEFAULT_DEVICE`` is one of the enum members."""
    assert DEFAULT_DEVICE in Device
    assert DEFAULT_DEVICE is Device.REDMI_NOTE_12


def test_lookup_by_name() -> None:
    """Members are reachable by their identifier via ``Device[...]``."""
    assert Device["GALAXY_S23"] is Device.GALAXY_S23


@pytest.mark.parametrize(
    "name",
    ["REDMI_11", "REDMI_12", "REDMI_NOTE_11", "REDMI_NOTE_12", "GALAXY_S23", "PIXEL_7"],
)
def test_common_devices_present(name: str) -> None:
    """The devices called out in the request are registered."""
    assert name in Device.__members__

"""Fictional enhancement control device management.

Devices only adjust simulation parameters. They never represent real
chemical dosing or physical hardware control.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.database import get_db

DEVICE_TYPES = ("Bio-Monitor", "Nebula Regulator", "Stabilizer")

DEVICE_COMMANDS = ("start", "pause", "stop", "stabilize", "emergency_shutdown", "reset")

_COMMAND_PERMISSIONS = {
    "Bio-Monitor": {"start", "pause", "stop", "emergency_shutdown"},
    "Nebula Regulator": {"start", "pause", "stop", "stabilize"},
    "Stabilizer": {"stabilize", "reset"},
}


class DeviceError(Exception):
    """Raised when a device operation cannot be completed."""


class DeviceNotFoundError(DeviceError):
    """Raised when a control device does not exist."""


class DuplicateDeviceError(DeviceError):
    """Raised when a device code is already in use."""


class CommandNotAllowedError(DeviceError):
    """Raised when the device type cannot issue the requested command."""


class DeviceCreate(BaseModel):
    """Input model for registering a control device."""

    model_config = ConfigDict(extra="forbid")

    device_code: str = Field(min_length=3, max_length=32)
    device_name: str = Field(min_length=1, max_length=120)
    device_type: str

    @field_validator("device_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        code = value.strip().upper()
        if not all(char.isalnum() or char in "-_" for char in code):
            raise ValueError("device_code may contain only letters, numbers, '-' and '_'")
        return code

    @field_validator("device_type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        for device_type in DEVICE_TYPES:
            if value.strip().lower() == device_type.lower():
                return device_type
        raise ValueError(f"device_type must be one of {DEVICE_TYPES}")


class DeviceConfigurationUpdate(BaseModel):
    """Input model for updating device parameters on a 0-100 scale."""

    model_config = ConfigDict(extra="forbid")

    device_integrity: float | None = Field(default=None, ge=0, le=100)
    monitoring_accuracy: float | None = Field(default=None, ge=0, le=100)
    control_efficiency: float | None = Field(default=None, ge=0, le=100)
    stability_support: float | None = Field(default=None, ge=0, le=100)
    emergency_shutdown_status: bool | None = None


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _device_row(conn: sqlite3.Connection, device_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM control_devices WHERE id = ?", (device_id,)).fetchone()
    if row is None:
        raise DeviceNotFoundError(f"Control device {device_id} does not exist")
    return row


def _config_row(conn: sqlite3.Connection, device_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM device_configurations WHERE device_id = ? ORDER BY id DESC LIMIT 1",
        (device_id,),
    ).fetchone()
    if row is None:
        raise DeviceError(f"Device {device_id} has no configuration record")
    return row


def create_device(payload: DeviceCreate) -> dict[str, Any]:
    """Register a device together with its default configuration."""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM control_devices WHERE device_code = ?", (payload.device_code,)
        ).fetchone()
        if existing:
            raise DuplicateDeviceError(f"Device code '{payload.device_code}' is already in use")

        device_id = int(
            conn.execute(
                """INSERT INTO control_devices (device_code, device_name, device_type, is_active)
                VALUES (?, ?, ?, 1)""",
                (payload.device_code, payload.device_name, payload.device_type),
            ).lastrowid
        )

        conn.execute(
            """INSERT INTO device_configurations
            (device_id, device_integrity, monitoring_accuracy,
                control_efficiency, stability_support, emergency_shutdown_status)
            VALUES (?, 100.0, 95.0, 90.0, 85.0, 0)""",
            (device_id,),
        )

    return get_device(device_id)


def get_device(device_id: int) -> dict[str, Any]:
    """Return one device with metadata, configuration and derived state."""
    with get_db() as conn:
        device = dict(_device_row(conn, device_id))
        configuration = dict(_config_row(conn, device_id))

    device["is_active"] = bool(device["is_active"])
    configuration["emergency_shutdown_status"] = bool(configuration["emergency_shutdown_status"])
    device["configuration"] = configuration
    device["operational"] = is_operational(device)
    return device


def list_devices() -> list[dict[str, Any]]:
    """Return every registered device with its current configuration."""
    with get_db() as conn:
        rows = conn.execute("SELECT id FROM control_devices ORDER BY id").fetchall()
    return [get_device(int(row["id"])) for row in rows]


def update_configuration(device_id: int, payload: DeviceConfigurationUpdate) -> dict[str, Any]:
    """Update the parameter record of a device."""
    updates = payload.model_dump(exclude_unset=True)
    updates = {key: value for key, value in updates.items() if value is not None}

    with get_db() as conn:
        _device_row(conn, device_id)
        config = _config_row(conn, device_id)

        if updates:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            values = [
                int(value) if key == "emergency_shutdown_status" else value
                for key, value in updates.items()
            ]
            conn.execute(
                f"UPDATE device_configurations SET {assignments} WHERE id = ?",
                (*values, int(config["id"])),
            )

    return get_device(device_id)


def is_operational(device: dict[str, Any]) -> bool:
    """A device operates only while active, intact and not shut down."""
    configuration = device["configuration"]
    return bool(
        device["is_active"]
        and configuration["device_integrity"] > 0
        and not configuration["emergency_shutdown_status"]
    )


def effective_control(device_id: int) -> dict[str, Any]:
    """Return 0-1 influence factors consumed by the simulation engine."""
    device = get_device(device_id)

    if not is_operational(device):
        return {
            "integrity": 0.0, "monitoring": 0.0, "control": 0.0,
            "support": 0.0, "operational": False,
        }

    configuration = device["configuration"]
    return {
        "integrity": configuration["device_integrity"] / 100.0,
        "monitoring": configuration["monitoring_accuracy"] / 100.0,
        "control": configuration["control_efficiency"] / 100.0,
        "support": configuration["stability_support"] / 100.0,
        "operational": True,
    }


def send_command(device_id: int, command: str) -> dict[str, Any]:
    """Apply a control command. Commands only change simulation parameters."""
    normalized = command.strip().lower()
    if normalized not in DEVICE_COMMANDS:
        raise DeviceError(f"command must be one of {list(DEVICE_COMMANDS)}, got '{command}'")

    device = get_device(device_id)
    allowed = _COMMAND_PERMISSIONS[device["device_type"]]
    if normalized not in allowed:
        raise CommandNotAllowedError(
            f"{device['device_type']} cannot issue '{normalized}'; allowed: {sorted(allowed)}"
        )

    configuration = device["configuration"]

    if normalized == "emergency_shutdown":
        update_configuration(
            device_id, DeviceConfigurationUpdate(emergency_shutdown_status=True)
        )
        return {
            "device_id": device_id, "command": normalized, "applied": True,
            "message": "Emergency shutdown engaged. Simulation control is frozen.",
        }

    if normalized == "reset":
        update_configuration(
            device_id, DeviceConfigurationUpdate(emergency_shutdown_status=False)
        )
        return {
            "device_id": device_id, "command": normalized, "applied": True,
            "message": "Shutdown flag cleared. Device is available again.",
        }

    if normalized == "stabilize":
        boosted = _clamp(configuration["stability_support"] + 8.0)
        update_configuration(
            device_id,
            DeviceConfigurationUpdate(
                stability_support=boosted,
                control_efficiency=_clamp(configuration["control_efficiency"] + 3.0),
            ),
        )
        return {
            "device_id": device_id, "command": normalized, "applied": True,
            "message": f"Stabilization mode engaged. Stability support at {boosted}.",
        }

    return {
        "device_id": device_id, "command": normalized, "applied": True,
        "message": f"Device acknowledges '{normalized}'. Session state is set by the engine.",
    }


def device_status(device_id: int) -> dict[str, Any]:
    """Compact status block for the Device Control dashboard section."""
    device = get_device(device_id)
    configuration = device["configuration"]

    if not device["is_active"]:
        state = "Offline"
    elif configuration["emergency_shutdown_status"]:
        state = "Emergency Shutdown"
    elif configuration["device_integrity"] < 40:
        state = "Degraded"
    else:
        state = "Operational"

    return {
        "device_id": device_id,
        "device_code": device["device_code"],
        "device_name": device["device_name"],
        "device_type": device["device_type"],
        "state": state,
        "device_integrity": configuration["device_integrity"],
        "monitoring_accuracy": configuration["monitoring_accuracy"],
        "control_efficiency": configuration["control_efficiency"],
        "stability_support": configuration["stability_support"],
        "emergency_shutdown_status": configuration["emergency_shutdown_status"],
        "effective_control": effective_control(device_id),
    }


def devices_summary() -> dict[str, Any]:
    """Aggregate device health for the dashboard header."""
    devices = list_devices()
    return {
        "total": len(devices),
        "operational": sum(1 for device in devices if device["operational"]),
        "by_type": {
            device_type: sum(1 for d in devices if d["device_type"] == device_type)
            for device_type in DEVICE_TYPES
        },
        "average_integrity": (
            round(sum(d["configuration"]["device_integrity"] for d in devices) / len(devices), 2)
            if devices else None
        ),
    }
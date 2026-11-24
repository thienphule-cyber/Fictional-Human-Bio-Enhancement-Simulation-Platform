"""Biological enhancement simulation engine.

Drives one simulation tick through six fictional stages:

    Absorption -> Digestion -> Adaptation -> Enhancement -> Mutation -> Stability

The engine is deterministic: the same session inputs and seed always produce
the same trajectory. It only adjusts software parameters and never models a
real substance dose.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.compatibility import calculate_compatibility
from backend.database import get_db
from backend.devices import effective_control
from backend.human import (
    PARAMETER_FIELDS,
    BiologicalParameters,
    add_biological_parameters,
    derive_physical_class,
    get_latest_parameters,
    get_profile,
    resolve_biological_status,
)
from backend.mutation import calculate_mutation, record_mutation
from backend.nebula import get_gas

SESSION_STATUSES = (
    "Created", "Running", "Paused", "Stopped", "Completed", "Emergency Shutdown"
)

_FOCUS_TARGETS = {
    "muscle": ("muscle_density", "bone_density"),
    "skeletal": ("bone_density", "muscle_density"),
    "cardiovascular": ("cardiovascular_capacity", "metabolic_efficiency"),
    "neural": ("neural_activity", "regeneration_index"),
    "metabolic": ("metabolic_efficiency", "regeneration_index"),
    "regenerative": ("regeneration_index", "cellular_stability"),
}

_MAX_TICK_GAIN = 2.4
_STABILITY_DRAG = 0.45


class EnhancementError(Exception):
    """Raised when a simulation step cannot be performed."""


class SessionNotFoundError(EnhancementError):
    """Raised when a simulation session does not exist."""


class SessionStateError(EnhancementError):
    """Raised when an operation is invalid for the current session state."""


class SessionCreate(BaseModel):
    """Input model for opening a simulation session."""

    model_config = ConfigDict(extra="forbid")

    profile_id: int = Field(ge=1)
    gas_id: int = Field(ge=1)
    device_id: int = Field(ge=1)


class StepRequest(BaseModel):
    """Input model for advancing one simulation tick."""

    model_config = ConfigDict(extra="forbid")

    intensity: float = Field(default=50, ge=0, le=100)
    focus: str = "muscle"
    seed: int | None = Field(default=None, ge=0)

    def resolved_focus(self) -> str:
        key = self.focus.strip().lower()
        if key not in _FOCUS_TARGETS:
            raise EnhancementError(
                f"focus must be one of {sorted(_FOCUS_TARGETS)}, got '{self.focus}'"
            )
        return key


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(max(low, min(high, value)), 2)


def _session_row(conn: sqlite3.Connection, session_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM simulation_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if row is None:
        raise SessionNotFoundError(f"Simulation session {session_id} does not exist")
    return row


def create_session(payload: SessionCreate) -> dict[str, Any]:
    """Open a session pairing one profile, one gas and one control device."""
    get_profile(payload.profile_id)
    get_gas(payload.gas_id)

    with get_db() as conn:
        device = conn.execute(
            "SELECT id FROM control_devices WHERE id = ?", (payload.device_id,)
        ).fetchone()
        if device is None:
            raise EnhancementError(f"Control device {payload.device_id} does not exist")

        total = conn.execute(
            "SELECT COUNT(*) AS total FROM simulation_sessions"
        ).fetchone()
        session_code = f"SIM-{int(total['total']) + 1:04d}"

        session_id = int(
            conn.execute(
                """INSERT INTO simulation_sessions
                (session_code, profile_id, gas_id, device_id, status, current_tick)
                VALUES (?, ?, ?, ?, 'Created', 0)""",
                (session_code, payload.profile_id, payload.gas_id, payload.device_id),
            ).lastrowid
        )

    return get_session(session_id)


def get_session(session_id: int) -> dict[str, Any]:
    """Return a session with its profile and gas resolved."""
    with get_db() as conn:
        session = dict(_session_row(conn, session_id))

    profile = get_profile(session["profile_id"])
    gas = get_gas(session["gas_id"])

    session["profile"] = {
        "subject_code": profile["subject_code"],
        "full_name": profile["full_name"],
        "physical_class": profile["physical_class"],
        "physical_class_name": profile["physical_class_name"],
        "biological_status": profile["biological_status"],
    }
    session["gas"] = {
        "gas_code": gas["gas_id"],
        "gas_name": gas["gas_name"],
        "hazard_level": gas["hazard_level"],
        "hazard_name": gas["hazard_name"],
    }
    return session


def list_sessions(profile_id: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Return recent sessions, optionally restricted to one profile."""
    if not 1 <= limit <= 200:
        raise EnhancementError("limit must be between 1 and 200")

    with get_db() as conn:
        if profile_id is None:
            rows = conn.execute(
                "SELECT id FROM simulation_sessions ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id FROM simulation_sessions
                WHERE profile_id = ? ORDER BY id DESC LIMIT ?""",
                (profile_id, limit),
            ).fetchall()

    return [get_session(int(row["id"])) for row in rows]


def _set_status(
    session_id: int, status: str, allowed_from: tuple[str, ...]
) -> dict[str, Any]:
    if status not in SESSION_STATUSES:
        raise EnhancementError(f"status must be one of {SESSION_STATUSES}")

    with get_db() as conn:
        session = _session_row(conn, session_id)
        if session["status"] not in allowed_from:
            raise SessionStateError(
                f"cannot move session from '{session['status']}' to '{status}'"
            )
        conn.execute(
            """UPDATE simulation_sessions
            SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (status, session_id),
        )

    return get_session(session_id)


def start_session(session_id: int) -> dict[str, Any]:
    """Start or resume a session. The assigned device must be operational."""
    session = get_session(session_id)
    if not effective_control(session["device_id"])["operational"]:
        raise SessionStateError(
            "the assigned control device is not operational; clear the emergency "
            "shutdown or restore device integrity first"
        )
    return _set_status(session_id, "Running", ("Created", "Paused", "Stopped"))


def pause_session(session_id: int) -> dict[str, Any]:
    """Pause a running session."""
    return _set_status(session_id, "Paused", ("Running",))


def stop_session(session_id: int) -> dict[str, Any]:
    """Stop a session while keeping its recorded history."""
    return _set_status(session_id, "Stopped", ("Running", "Paused", "Created"))


def complete_session(session_id: int) -> dict[str, Any]:
    """Mark a stopped session as completed."""
    return _set_status(session_id, "Completed", ("Stopped", "Running"))


def emergency_shutdown(session_id: int) -> dict[str, Any]:
    """Force a session into the emergency shutdown state."""
    with get_db() as conn:
        _session_row(conn, session_id)
        conn.execute(
            """UPDATE simulation_sessions
               SET status = 'Emergency Shutdown', updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (session_id,),
        )
    return get_session(session_id)


def absorption_rate(purity: float, intensity: float, monitoring: float, hazard_level: int) -> float:
    """How much of the gas is taken in during one tick."""
    return _clamp(
        purity * 0.45 + intensity * 0.40 + monitoring * 10.0 - hazard_level * 3.5,
        5.0, 95.0,
    )


def digestion_efficiency(
    compatibility_digest: float, metabolic_efficiency: float, purity: float,
    absorption: float,
) -> float:
    """How much of the absorbed gas becomes usable enhancement energy."""
    return _clamp(
        compatibility_digest * 0.40 + metabolic_efficiency * 0.30
        + purity * 0.15 + absorption * 0.15,
        0.0, 92.0,
    )


def adaptation_rate(
    adaptation_stability: float, cellular_stability: float, control: float,
    hazard_level: int,
) -> float:
    """How smoothly the simulated body accepts the converted gas."""
    return _clamp(
        adaptation_stability * 0.45 + cellular_stability * 0.30
        + control * 15.0 - hazard_level * 3.0,
        0.0, 90.0,
    )


def enhancement_gain(
    digestion: float, adaptation: float, energy_potential: float,
    intensity: float, hazard_level: int,
) -> float:
    """Enhancement applied to the focus parameters during one tick."""
    gain = (
        digestion * 0.010 + adaptation * 0.010 + energy_potential * 0.008
        + intensity * 0.004 - hazard_level * 0.010
    )
    return round(max(0.0, min(_MAX_TICK_GAIN, gain)), 4)


def stability_score(
    cellular_stability: float, adaptation: float, support: float,
    hazard_level: int, mutation_level: int,
) -> float:
    """Overall fictional biological stability after the tick."""
    return _clamp(
        cellular_stability * 0.50 + adaptation * 0.25 + support * 20.0
        - hazard_level * 3.0 - mutation_level * 5.0
    )


def _apply_gain(
    parameters: dict[str, Any], focus: str, gain: float,
    mutation_level: int, hazard_level: int,
) -> dict[str, float]:
    """Distribute the enhancement gain; mutation converts gain into wear."""
    primary, secondary = _FOCUS_TARGETS[focus]
    updated = {field: float(parameters.get(field, 50.0)) for field in PARAMETER_FIELDS}
    damage = mutation_level * 0.6 + max(0, hazard_level - 2) * 0.2

    updated[primary] = _clamp(updated[primary] + gain)
    updated[secondary] = _clamp(updated[secondary] + gain * 0.55)
    updated["neural_activity"] = _clamp(updated["neural_activity"] + gain * 0.20)
    updated["cellular_stability"] = _clamp(
        updated["cellular_stability"] + gain * 0.20 - _STABILITY_DRAG - damage
    )
    updated["mutation_resistance"] = _clamp(
        updated["mutation_resistance"] + gain * 0.15 - damage * 0.8
    )
    updated["regeneration_index"] = _clamp(
        updated["regeneration_index"] + gain * 0.25 - damage * 0.3
    )
    return updated


def run_step(session_id: int, request: StepRequest | None = None) -> dict[str, Any]:
    """Advance the session by one tick across all six simulated stages."""
    payload = request or StepRequest()
    focus = payload.resolved_focus()

    session = get_session(session_id)
    if session["status"] != "Running":
        raise SessionStateError(
            f"session is '{session['status']}'; call start_session() before stepping"
        )

    profile = get_profile(session["profile_id"])
    gas = get_gas(session["gas_id"])
    parameters = get_latest_parameters(session["profile_id"])
    if parameters is None:
        raise EnhancementError(
            f"profile {session['profile_id']} has no biological parameters"
        )

    control = effective_control(session["device_id"])
    if not control["operational"]:
        emergency_shutdown(session_id)
        raise SessionStateError(
            "control device went offline during the simulation; session was shut down"
        )

    compatibility = calculate_compatibility(profile["physical_class"], parameters, gas)
    tick = int(session["current_tick"]) + 1

    absorbed = absorption_rate(
        gas["gas_purity"], payload.intensity, control["monitoring"], gas["hazard_level"]
    )
    digested = digestion_efficiency(
        compatibility["digest_efficiency"],
        float(parameters["metabolic_efficiency"]),
        gas["gas_purity"],
        absorbed,
    )
    adapted = adaptation_rate(
        compatibility["adaptation_stability"],
        float(parameters["cellular_stability"]),
        control["control"],
        gas["hazard_level"],
    )
    gain = enhancement_gain(
        digested, adapted, gas["energy_potential"], payload.intensity, gas["hazard_level"]
    )
    mutation = calculate_mutation(
        mutation_risk=compatibility["mutation_risk"],
        mutation_potential=gas["mutation_potential"],
        cellular_stability=float(parameters["cellular_stability"]),
        hazard_level=gas["hazard_level"],
        mutation_resistance=float(parameters["mutation_resistance"]),
        seed=payload.seed if payload.seed is not None else session_id * 1000 + tick,
    )
    stability = stability_score(
        float(parameters["cellular_stability"]),
        adapted,
        control["support"],
        gas["hazard_level"],
        mutation.mutation_level,
    )
    updated = _apply_gain(
        parameters, focus, gain, mutation.mutation_level, gas["hazard_level"]
    )

    physical_class = derive_physical_class(updated)
    biological_status = resolve_biological_status(updated, physical_class)
    risk_level = max(
        mutation.mutation_level,
        min(5, int(round((100.0 - stability) / 20.0))),
    )

    with get_db() as conn:
        enhancement_id = int(
            conn.execute(
                """INSERT INTO enhancement_records
                (session_id, tick, absorption_rate, digestion_efficiency,
                    adaptation_rate, enhancement_gain, stability_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, tick, absorbed, digested, adapted, gain, stability),
            ).lastrowid
        )

        conn.execute(
            """INSERT INTO simulation_metrics
            (session_id, tick, muscle_density, bone_density,
                cardiovascular_capacity, neural_activity, cellular_stability,
                metabolic_efficiency, regeneration_index, mutation_resistance,
                biological_status, risk_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id, tick,
                updated["muscle_density"], updated["bone_density"],
                updated["cardiovascular_capacity"], updated["neural_activity"],
                updated["cellular_stability"], updated["metabolic_efficiency"],
                updated["regeneration_index"], updated["mutation_resistance"],
                biological_status, risk_level,
            ),
        )

        conn.execute(
            """UPDATE simulation_sessions
            SET current_tick = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (tick, session_id),
        )

    add_biological_parameters(
        session["profile_id"], BiologicalParameters(**updated)
    )

    mutation_record = None
    if mutation.occurred:
        mutation_record = record_mutation(session_id, tick, mutation)

    return {
        "session_id": session_id,
        "tick": tick,
        "stages": {
            "absorption": absorbed,
            "digestion": digested,
            "adaptation": adapted,
            "enhancement_gain": gain,
            "mutation_level": mutation.mutation_level,
            "stability": stability,
        },
        "compatibility": {
            "score": compatibility["compatibility_score"],
            "mutation_risk": compatibility["mutation_risk"],
            "result_status": compatibility["result_status"],
        },
        "mutation": mutation.model_dump(),
        "mutation_record_id": mutation_record["id"] if mutation_record else None,
        "parameters": updated,
        "physical_class": physical_class,
        "biological_status": biological_status,
        "risk_level": risk_level,
        "enhancement_record_id": enhancement_id,
    }


def get_enhancement_history(session_id: int, limit: int = 200) -> list[dict[str, Any]]:
    """Return the enhancement stage history of a session."""
    if not 1 <= limit <= 1000:
        raise EnhancementError("limit must be between 1 and 1000")

    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM enhancement_records
            WHERE session_id = ? ORDER BY tick, id LIMIT ?""",
            (session_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_metrics(session_id: int, limit: int = 200) -> list[dict[str, Any]]:
    """Return the time-series biological metrics of a session."""
    if not 1 <= limit <= 1000:
        raise EnhancementError("limit must be between 1 and 1000")

    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM simulation_metrics
            WHERE session_id = ? ORDER BY tick, id LIMIT ?""",
            (session_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def session_summary(session_id: int) -> dict[str, Any]:
    """Aggregate a session for the Enhancement Monitor panel."""
    session = get_session(session_id)
    metrics = get_metrics(session_id)

    if not metrics:
        return {
            "session_id": session_id,
            "session_code": session["session_code"],
            "status": session["status"],
            "ticks": 0,
            "first": None,
            "last": None,
            "delta": None,
            "peak_risk_level": 0,
            "final_status": None,
        }

    first = {field: float(metrics[0][field]) for field in PARAMETER_FIELDS}
    last = {field: float(metrics[-1][field]) for field in PARAMETER_FIELDS}

    return {
        "session_id": session_id,
        "session_code": session["session_code"],
        "status": session["status"],
        "ticks": len(metrics),
        "first": first,
        "last": last,
        "delta": {field: round(last[field] - first[field], 2) for field in PARAMETER_FIELDS},
        "peak_risk_level": max(int(row["risk_level"]) for row in metrics),
        "final_status": metrics[-1]["biological_status"],
    }
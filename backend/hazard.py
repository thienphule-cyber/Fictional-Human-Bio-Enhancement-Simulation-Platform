"""Fictional hazard and biological stability assessment for Nebula.

This module evaluates simulation state only. Hazard levels are internal labels
for the fictional model and do not represent real chemical exposure.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.database import get_db
from backend.nebula import HAZARD_CLASSIFICATIONS

RISK_STATUSES = {
    0: "Safe Simulation State",
    1: "Low Risk",
    2: "Moderate Risk",
    3: "High Risk",
    4: "Critical Risk",
    5: "Biological Collapse",
}


class HazardError(Exception):
    """Raised when a hazard assessment cannot be completed."""


class HazardAssessmentInput(BaseModel):
    """Input model for evaluating one simulation state."""

    model_config = ConfigDict(extra="forbid")

    gas_hazard_level: int = Field(ge=0, le=5)
    physical_class: int = Field(ge=0, le=5)
    compatibility_score: float = Field(ge=0, le=100)
    mutation_risk: float = Field(ge=0, le=100)
    biological_stability: float = Field(ge=0, le=100)
    device_integrity: float = Field(ge=0, le=100)
    device_operational: bool = True


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    """Keep a value within a defined range."""
    return round(max(low, min(high, value)), 2)


def risk_status(risk_level: int) -> str:
    """Return the human-readable label for a risk level."""
    if risk_level not in RISK_STATUSES:
        raise HazardError("risk_level must be between 0 and 5")
    return RISK_STATUSES[risk_level]


def assess_values(data: HazardAssessmentInput) -> dict[str, Any]:
    """Calculate hazard score, risk level, stability and shutdown recommendation."""
    hazard = data.gas_hazard_level
    class_gap = max(0, hazard - data.physical_class)
    device_penalty = 15.0 if not data.device_operational else (100.0 - data.device_integrity) * 0.25

    hazard_score = _clamp(
        hazard * 11.0
        + class_gap * 10.0
        + (100.0 - data.compatibility_score) * 0.18
        + data.mutation_risk * 0.28
        + (100.0 - data.biological_stability) * 0.22
        + device_penalty
    )

    # Map the continuous score to an integer level from 0 to 5.
    risk_level = min(5, int(hazard_score // 20))

    if class_gap >= 2 or data.mutation_risk >= 90 or data.biological_stability < 15:
        risk_level = 5
    elif class_gap == 1 or data.mutation_risk >= 75 or data.biological_stability < 30:
        risk_level = max(risk_level, 4)
    elif not data.device_operational or data.device_integrity < 20:
        risk_level = max(risk_level, 4)

    shutdown_recommended = (
        risk_level >= 4
        or data.mutation_risk >= 80
        or data.biological_stability < 25
        or not data.device_operational
    )

    stability_status = (
        "Stable" if data.biological_stability >= 70
        else "Strained" if data.biological_stability >= 45
        else "Unstable" if data.biological_stability >= 25
        else "Critical"
    )

    summary = (
        f"{RISK_STATUSES[risk_level]}: simulation hazard score {hazard_score:.1f}; "
        f"biological stability is {stability_status.lower()}."
    )
    if shutdown_recommended:
        summary += " Emergency shutdown is recommended."

    return {
        "hazard_score": hazard_score,
        "risk_level": risk_level,
        "risk_status": RISK_STATUSES[risk_level],
        "stability_status": stability_status,
        "shutdown_recommended": shutdown_recommended,
        "assessment_summary": summary,
        "class_gap": class_gap,
    }


def assess_session(session_id: int, persist: bool = True) -> dict[str, Any]:
    """Assess the latest state of a stored simulation session."""
    with get_db() as conn:
        session = conn.execute(
            "SELECT * FROM simulation_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if session is None:
            raise HazardError(f"Simulation session {session_id} does not exist")

        profile = conn.execute(
            "SELECT * FROM human_profiles WHERE id = ?", (session["profile_id"],)
        ).fetchone()
        gas = conn.execute(
            "SELECT * FROM nebula_gases WHERE id = ?", (session["gas_id"],)
        ).fetchone()
        device = conn.execute(
            "SELECT * FROM control_devices WHERE id = ?", (session["device_id"],)
        ).fetchone()
        device_config = conn.execute(
            "SELECT * FROM device_configurations WHERE device_id = ? ORDER BY id DESC LIMIT 1",
            (session["device_id"],),
        ).fetchone()
        metrics = conn.execute(
            "SELECT * FROM simulation_metrics WHERE session_id = ? ORDER BY tick DESC, id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        compatibility = conn.execute(
            "SELECT * FROM compatibility_records WHERE profile_id = ? AND gas_id = ? ORDER BY id DESC LIMIT 1",
            (session["profile_id"], session["gas_id"]),
        ).fetchone()
        latest_parameters = conn.execute(
            "SELECT * FROM biological_parameters WHERE profile_id = ? ORDER BY id DESC LIMIT 1",
            (session["profile_id"],),
        ).fetchone()

        if profile is None or gas is None or device is None or device_config is None:
            raise HazardError("Session references missing profile, gas, or device data")

        biological_stability = (
            float(metrics["cellular_stability"])
            if metrics is not None
            else float(latest_parameters["cellular_stability"])
            if latest_parameters is not None
            else 50.0
        )
        mutation_risk = (
            float(compatibility["mutation_risk"])
            if compatibility is not None
            else float(gas["mutation_potential"])
        )
        compatibility_score = (
            float(compatibility["compatibility_score"])
            if compatibility is not None
            else max(0.0, 100.0 - float(gas["hazard_level"]) * 12.0)
        )

        operational = bool(device["is_active"]) and float(device_config["device_integrity"]) > 0
        operational = operational and not bool(device_config["emergency_shutdown_status"])

        inputs = HazardAssessmentInput(
            gas_hazard_level=int(gas["hazard_level"]),
            physical_class=int(profile["physical_class"]),
            compatibility_score=compatibility_score,
            mutation_risk=mutation_risk,
            biological_stability=biological_stability,
            device_integrity=float(device_config["device_integrity"]),
            device_operational=operational,
        )
        result = assess_values(inputs)
        tick = int(session["current_tick"])

        if persist:
            cursor = conn.execute(
                """INSERT INTO hazard_assessments
                (session_id, tick, risk_level, stability_status,
                    assessment_summary, shutdown_triggered)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    tick,
                    result["risk_level"],
                    result["stability_status"],
                    result["assessment_summary"],
                    int(result["shutdown_recommended"]),
                ),
            )
            result["assessment_id"] = int(cursor.lastrowid)

    result.update(
        {
            "session_id": session_id,
            "tick": tick,
            "gas_hazard_level": int(gas["hazard_level"]),
            "hazard_classification": HAZARD_CLASSIFICATIONS[int(gas["hazard_level"])],
            "physical_class": int(profile["physical_class"]),
            "compatibility_score": round(compatibility_score, 2),
            "mutation_risk": round(mutation_risk, 2),
            "biological_stability": round(biological_stability, 2),
            "device_integrity": round(float(device_config["device_integrity"]), 2),
            "device_operational": operational,
        }
    )

    if result["shutdown_recommended"] and persist:
        _set_session_shutdown(session_id)

    return result


def _set_session_shutdown(session_id: int) -> None:
    """Set the simulation session to Emergency Shutdown."""
    with get_db() as conn:
        conn.execute(
            """UPDATE simulation_sessions
            SET status = 'Emergency Shutdown', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?""",
            (session_id,),
        )


def get_assessment_history(session_id: int, limit: int = 100) -> list[dict[str, Any]]:
    """Return risk-assessment history for a session."""
    if not 1 <= limit <= 1000:
        raise HazardError("limit must be between 1 and 1000")

    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM hazard_assessments
            WHERE session_id = ? ORDER BY tick, id LIMIT ?""",
            (session_id, limit),
        ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["risk_status"] = RISK_STATUSES[item["risk_level"]]
        item["shutdown_triggered"] = bool(item["shutdown_triggered"])
        result.append(item)
    return result


def risk_summary(session_id: int) -> dict[str, Any]:
    """Summarize assessment history for the Hazard Monitor dashboard."""
    history = get_assessment_history(session_id)
    if not history:
        return {
            "session_id": session_id,
            "assessments": 0,
            "current_risk_level": None,
            "peak_risk_level": None,
            "shutdown_count": 0,
            "risk_trend": [],
        }

    return {
        "session_id": session_id,
        "assessments": len(history),
        "current_risk_level": history[-1]["risk_level"],
        "current_risk_status": history[-1]["risk_status"],
        "peak_risk_level": max(item["risk_level"] for item in history),
        "shutdown_count": sum(bool(item["shutdown_triggered"]) for item in history),
        "risk_trend": [
            {"tick": item["tick"], "risk_level": item["risk_level"]}
            for item in history
        ],
    }
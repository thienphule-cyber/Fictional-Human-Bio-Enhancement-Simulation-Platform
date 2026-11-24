"""Simulation history, statistics and reporting for the Nebula platform.

All figures are computed from stored simulation data. Nothing here produces
real-world medical or chemical conclusions.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.database import get_db
from backend.human import PARAMETER_FIELDS


class AnalyticsError(Exception):
    """Raised when analytics data cannot be produced."""


class ComparisonRequest(BaseModel):
    """Input model for comparing two or more simulation sessions."""

    model_config = ConfigDict(extra="forbid")

    session_ids: list[int] = Field(min_length=2, max_length=10)

    def validated(self) -> list[int]:
        unique: list[int] = []
        for session_id in self.session_ids:
            if session_id < 1:
                raise AnalyticsError("session ids must be positive integers")
            if session_id not in unique:
                unique.append(session_id)
        if len(unique) < 2:
            raise AnalyticsError("at least two distinct session ids are required")
        return unique


def _fetch_session(conn: sqlite3.Connection, session_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM simulation_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if row is None:
        raise AnalyticsError(f"Simulation session {session_id} does not exist")
    return row


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(float(value), digits)


# --------------------------------------------------------------------------- #
# Parameter trends
# --------------------------------------------------------------------------- #


def parameter_trends(session_id: int, limit: int = 500) -> dict[str, Any]:
    """
    Return chart-ready series for every biological parameter.

    The shape matches what Chart.js expects: one shared label array plus one
    dataset per parameter, so the frontend does not have to reshape anything.
    """
    if not 1 <= limit <= 2000:
        raise AnalyticsError("limit must be between 1 and 2000")

    with get_db() as conn:
        _fetch_session(conn, session_id)
        rows = conn.execute(
            """SELECT * FROM simulation_metrics
            WHERE session_id = ? ORDER BY tick, id LIMIT ?""",
            (session_id, limit),
        ).fetchall()

    if not rows:
        return {
            "session_id": session_id,
            "ticks": 0,
            "labels": [],
            "datasets": {field: [] for field in PARAMETER_FIELDS},
            "risk_levels": [],
            "statuses": [],
        }

    return {
        "session_id": session_id,
        "ticks": len(rows),
        "labels": [int(row["tick"]) for row in rows],
        "datasets": {
            field: [round(float(row[field]), 2) for row in rows]
            for field in PARAMETER_FIELDS
        },
        "risk_levels": [int(row["risk_level"]) for row in rows],
        "statuses": [row["biological_status"] for row in rows],
    }


def parameter_deltas(session_id: int) -> dict[str, Any]:
    """Return first, last and delta for every parameter across a session."""
    trends = parameter_trends(session_id)
    if trends["ticks"] == 0:
        return {"session_id": session_id, "ticks": 0, "first": {}, "last": {}, "delta": {}}

    first = {field: values[0] for field, values in trends["datasets"].items()}
    last = {field: values[-1] for field, values in trends["datasets"].items()}
    return {
        "session_id": session_id,
        "ticks": trends["ticks"],
        "first": first,
        "last": last,
        "delta": {
            field: round(last[field] - first[field], 2) for field in PARAMETER_FIELDS
        },
    }


# --------------------------------------------------------------------------- #
# Histories
# --------------------------------------------------------------------------- #


def enhancement_history(profile_id: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Return enhancement stage rows, newest first, optionally per profile."""
    if not 1 <= limit <= 500:
        raise AnalyticsError("limit must be between 1 and 500")

    query = """
        SELECT e.*, s.session_code, s.profile_id
        FROM enhancement_records e
        JOIN simulation_sessions s ON s.id = e.session_id
    """
    params: tuple[Any, ...] = ()

    if profile_id is not None:
        query += " WHERE s.profile_id = ?"
        params = (profile_id,)

    query += " ORDER BY e.id DESC LIMIT ?"
    params = (*params, limit)

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [
        {
            "id": int(row["id"]),
            "session_id": int(row["session_id"]),
            "session_code": row["session_code"],
            "profile_id": int(row["profile_id"]),
            "tick": int(row["tick"]),
            "absorption_rate": _round(row["absorption_rate"]),
            "digestion_efficiency": _round(row["digestion_efficiency"]),
            "adaptation_rate": _round(row["adaptation_rate"]),
            "enhancement_gain": _round(row["enhancement_gain"], 4),
            "stability_score": _round(row["stability_score"]),
            "recorded_at": row["recorded_at"],
        }
        for row in rows
    ]


def mutation_history(profile_id: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Return mutation rows, newest first, optionally per profile."""
    if not 1 <= limit <= 500:
        raise AnalyticsError("limit must be between 1 and 500")

    from backend.mutation import MUTATION_LEVELS

    query = """
        SELECT m.*, s.session_code, s.profile_id
        FROM mutation_records m
        JOIN simulation_sessions s ON s.id = m.session_id
    """
    params: tuple[Any, ...] = ()

    if profile_id is not None:
        query += " WHERE s.profile_id = ?"
        params = (profile_id,)

    query += " ORDER BY m.id DESC LIMIT ?"
    params = (*params, limit)

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [
        {
            "id": int(row["id"]),
            "session_id": int(row["session_id"]),
            "session_code": row["session_code"],
            "profile_id": int(row["profile_id"]),
            "tick": int(row["tick"]),
            "mutation_type": row["mutation_type"],
            "mutation_level": int(row["mutation_level"]),
            "mutation_level_name": MUTATION_LEVELS[int(row["mutation_level"])],
            "mutation_stability": _round(row["mutation_stability"]),
            "mutation_risk": _round(row["mutation_risk"]),
            "description": row["description"],
            "recorded_at": row["recorded_at"],
        }
        for row in rows
    ]


def hazard_history(profile_id: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Return hazard assessment rows, newest first, optionally per profile."""
    if not 1 <= limit <= 500:
        raise AnalyticsError("limit must be between 1 and 500")

    from backend.hazard import RISK_STATUSES

    query = """
        SELECT h.*, s.session_code, s.profile_id
        FROM hazard_assessments h
        JOIN simulation_sessions s ON s.id = h.session_id
    """
    params: tuple[Any, ...] = ()

    if profile_id is not None:
        query += " WHERE s.profile_id = ?"
        params = (profile_id,)

    query += " ORDER BY h.id DESC LIMIT ?"
    params = (*params, limit)

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [
        {
            "id": int(row["id"]),
            "session_id": int(row["session_id"]),
            "session_code": row["session_code"],
            "profile_id": int(row["profile_id"]),
            "tick": int(row["tick"]),
            "risk_level": int(row["risk_level"]),
            "risk_status": RISK_STATUSES[int(row["risk_level"])],
            "stability_status": row["stability_status"],
            "assessment_summary": row["assessment_summary"],
            "shutdown_triggered": bool(row["shutdown_triggered"]),
            "assessed_at": row["assessed_at"],
        }
        for row in rows
    ]


# --------------------------------------------------------------------------- #
# Session comparison
# --------------------------------------------------------------------------- #


def _session_snapshot(conn: sqlite3.Connection, session_id: int) -> dict[str, Any]:
    session = _fetch_session(conn, session_id)

    profile = conn.execute(
        "SELECT subject_code, full_name, physical_class, biological_status"
        " FROM human_profiles WHERE id = ?",
        (session["profile_id"],),
    ).fetchone()
    gas = conn.execute(
        "SELECT gas_id, gas_name, hazard_level FROM nebula_gases WHERE id = ?",
        (session["gas_id"],),
    ).fetchone()
    metrics = conn.execute(
        "SELECT * FROM simulation_metrics WHERE session_id = ? ORDER BY tick, id",
        (session_id,),
    ).fetchall()
    mutation_peak = conn.execute(
        "SELECT MAX(mutation_level) AS peak FROM mutation_records WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    risk_peak = conn.execute(
        "SELECT MAX(risk_level) AS peak FROM hazard_assessments WHERE session_id = ?",
        (session_id,),
    ).fetchone()

    first = None
    last = None
    if metrics:
        first = {field: round(float(metrics[0][field]), 2) for field in PARAMETER_FIELDS}
        last = {field: round(float(metrics[-1][field]), 2) for field in PARAMETER_FIELDS}

    return {
        "session_id": session_id,
        "session_code": session["session_code"],
        "status": session["status"],
        "ticks": len(metrics),
        "subject_code": profile["subject_code"] if profile else None,
        "physical_class": int(profile["physical_class"]) if profile else None,
        "gas_code": gas["gas_id"] if gas else None,
        "gas_name": gas["gas_name"] if gas else None,
        "gas_hazard_level": int(gas["hazard_level"]) if gas else None,
        "first": first,
        "last": last,
        "delta": (
            {field: round(last[field] - first[field], 2) for field in PARAMETER_FIELDS}
            if first and last
            else None
        ),
        "peak_mutation_level": (
            int(mutation_peak["peak"]) if mutation_peak and mutation_peak["peak"] is not None else 0
        ),
        "peak_risk_level": (
            int(risk_peak["peak"]) if risk_peak and risk_peak["peak"] is not None else None
        ),
        "final_biological_status": metrics[-1]["biological_status"] if metrics else None,
    }


def compare_sessions(request: ComparisonRequest) -> dict[str, Any]:
    """Compare two to ten sessions side by side for the Analytics page."""
    session_ids = request.validated()

    with get_db() as conn:
        snapshots = [_session_snapshot(conn, session_id) for session_id in session_ids]

    def _best(key: str) -> dict[str, Any] | None:
        candidates = [
            item for item in snapshots if item.get(key) is not None
        ]
        if not candidates:
            return None
        winner = max(candidates, key=lambda item: item[key])  # type: ignore[arg-type]
        return {"session_id": winner["session_id"], "value": winner[key]}

    return {
        "sessions": snapshots,
        "count": len(snapshots),
        "highest_mutation": _best("peak_mutation_level"),
        "highest_risk": _best("peak_risk_level"),
        "most_ticks": _best("ticks"),
        "average_ticks": round(
            sum(item["ticks"] for item in snapshots) / len(snapshots), 2
        ),
    }


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #


def session_report(session_id: int) -> dict[str, Any]:
    """Build the full report shown on the simulation report screen."""
    with get_db() as conn:
        _fetch_session(conn, session_id)
        snapshot = _session_snapshot(conn, session_id)
        enhancement = conn.execute(
            """SELECT COUNT(*) AS rows_count,
                    AVG(absorption_rate) AS avg_absorption,
                    AVG(digestion_efficiency) AS avg_digestion,
                    AVG(adaptation_rate) AS avg_adaptation,
                    AVG(enhancement_gain) AS avg_gain,
                    AVG(stability_score) AS avg_stability
            FROM enhancement_records WHERE session_id = ?""",
            (session_id,),
        ).fetchone()
        mutations = conn.execute(
            """SELECT mutation_type, COUNT(*) AS total, MAX(mutation_level) AS peak
            FROM mutation_records
            WHERE session_id = ? AND mutation_type != 'None'
            GROUP BY mutation_type ORDER BY total DESC""",
            (session_id,),
        ).fetchall()
        assessments = conn.execute(
            "SELECT COUNT(*) AS total FROM hazard_assessments WHERE session_id = ?",
            (session_id,),
        ).fetchone()

    return {
        "session": snapshot,
        "enhancement": {
            "records": int(enhancement["rows_count"] or 0),
            "average_absorption": _round(enhancement["avg_absorption"]),
            "average_digestion": _round(enhancement["avg_digestion"]),
            "average_adaptation": _round(enhancement["avg_adaptation"]),
            "average_gain": _round(enhancement["avg_gain"], 4),
            "average_stability": _round(enhancement["avg_stability"]),
        },
        "mutations": [
            {
                "mutation_type": row["mutation_type"],
                "occurrences": int(row["total"]),
                "peak_level": int(row["peak"]),
            }
            for row in mutations
        ],
        "hazard_assessments": int(assessments["total"] or 0),
        "generated_from": "stored simulation data",
    }


def profile_report(profile_id: int) -> dict[str, Any]:
    """Aggregate every session belonging to one profile."""
    with get_db() as conn:
        profile = conn.execute(
            "SELECT * FROM human_profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        if profile is None:
            raise AnalyticsError(f"Human profile {profile_id} does not exist")

        sessions = conn.execute(
            "SELECT id FROM simulation_sessions WHERE profile_id = ? ORDER BY id",
            (profile_id,),
        ).fetchall()

        compatibility = conn.execute(
            """SELECT COUNT(*) AS total,
                    AVG(compatibility_score) AS avg_score,
                    AVG(mutation_risk) AS avg_risk,
                    AVG(enhancement_potential) AS avg_potential
            FROM compatibility_records WHERE profile_id = ?""",
            (profile_id,),
        ).fetchone()

    session_ids = [int(row["id"]) for row in sessions]

    with get_db() as conn:
        snapshots = [_session_snapshot(conn, session_id) for session_id in session_ids]

    return {
        "profile": {
            "id": int(profile["id"]),
            "subject_code": profile["subject_code"],
            "full_name": profile["full_name"],
            "physical_class": int(profile["physical_class"]),
            "biological_status": profile["biological_status"],
        },
        "sessions": snapshots,
        "session_count": len(snapshots),
        "compatibility": {
            "evaluations": int(compatibility["total"] or 0),
            "average_score": _round(compatibility["avg_score"]),
            "average_mutation_risk": _round(compatibility["avg_risk"]),
            "average_enhancement_potential": _round(compatibility["avg_potential"]),
        },
    }


def platform_statistics() -> dict[str, Any]:
    """High-level counters for the dashboard header and the Analytics overview."""
    with get_db() as conn:
        counts = conn.execute(
            """SELECT
                (SELECT COUNT(*) FROM human_profiles) AS profiles,
                (SELECT COUNT(*) FROM nebula_gases) AS gases,
                (SELECT COUNT(*) FROM control_devices) AS devices,
                (SELECT COUNT(*) FROM simulation_sessions) AS sessions,
                (SELECT COUNT(*) FROM compatibility_records) AS compatibility_records,
                (SELECT COUNT(*) FROM enhancement_records) AS enhancement_records,
                (SELECT COUNT(*) FROM mutation_records) AS mutation_records,
                (SELECT COUNT(*) FROM simulation_metrics) AS metric_rows,
                (SELECT COUNT(*) FROM hazard_assessments) AS hazard_assessments"""
        ).fetchone()

        statuses = conn.execute(
            "SELECT status, COUNT(*) AS total FROM simulation_sessions GROUP BY status"
        ).fetchall()

        class_rows = conn.execute(
            "SELECT physical_class, COUNT(*) AS total FROM human_profiles GROUP BY physical_class"
        ).fetchall()

        risk_rows = conn.execute(
            "SELECT risk_level, COUNT(*) AS total FROM hazard_assessments GROUP BY risk_level"
        ).fetchall()

    return {
        "counts": {key: int(counts[key]) for key in counts.keys()},
        "sessions_by_status": {row["status"]: int(row["total"]) for row in statuses},
        "profiles_by_physical_class": {
            str(row["physical_class"]): int(row["total"]) for row in class_rows
        },
        "assessments_by_risk_level": {
            str(row["risk_level"]): int(row["total"]) for row in risk_rows
        },
    }


def recent_activity(limit: int = 20) -> list[dict[str, Any]]:
    """Return the most recent sessions as a compact activity feed."""
    if not 1 <= limit <= 100:
        raise AnalyticsError("limit must be between 1 and 100")

    with get_db() as conn:
        rows = conn.execute(
            """SELECT s.id, s.session_code, s.status, s.current_tick, s.created_at,
                    p.subject_code, g.gas_id AS gas_code, g.hazard_level
            FROM simulation_sessions s
            JOIN human_profiles p ON p.id = s.profile_id
            JOIN nebula_gases g ON g.id = s.gas_id
            ORDER BY s.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()

    return [
        {
            "session_id": int(row["id"]),
            "session_code": row["session_code"],
            "status": row["status"],
            "current_tick": int(row["current_tick"]),
            "subject_code": row["subject_code"],
            "gas_code": row["gas_code"],
            "hazard_level": int(row["hazard_level"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
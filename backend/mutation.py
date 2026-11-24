"""Fictional mutation modeling and mutation-history persistence."""

from __future__ import annotations

import random
import sqlite3
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.database import get_db

MUTATION_TYPES = (
    "Muscle Transformation",
    "Skeletal Transformation",
    "Skin Transformation",
    "Neural Transformation",
    "Organ Transformation",
)
MUTATION_LEVELS = {
    0: "Stable", 1: "Latent", 2: "Minor", 3: "Manifest", 4: "Severe", 5: "Critical"
}


class MutationError(Exception):
    """Raised when a mutation result cannot be processed."""


class MutationResult(BaseModel):
    """Result of one fictional mutation calculation."""

    model_config = ConfigDict(extra="forbid")

    mutation_type: str
    mutation_level: int = Field(ge=0, le=5)
    mutation_level_name: str
    mutation_stability: float = Field(ge=0, le=100)
    mutation_risk: float = Field(ge=0, le=100)
    occurred: bool
    description: str


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def level_from_risk(risk: float) -> int:
    """Map a 0-100 mutation risk to a discrete level from 0 to 5."""
    if not 0 <= risk <= 100:
        raise MutationError("mutation risk must be between 0 and 100")
    if risk < 15: return 0
    if risk < 30: return 1
    if risk < 48: return 2
    if risk < 66: return 3
    if risk < 84: return 4
    return 5


def calculate_mutation(
    mutation_risk: float,
    mutation_potential: float,
    cellular_stability: float,
    hazard_level: int,
    mutation_resistance: float,
    seed: int = 0,
) -> MutationResult:
    """Calculate a reproducible fictional mutation outcome for one tick."""
    if not 0 <= hazard_level <= 5:
        raise MutationError("hazard_level must be between 0 and 5")

    risk = _clamp(
        mutation_risk * 0.55
        + mutation_potential * 0.25
        + hazard_level * 4.0
        + max(0.0, 55.0 - cellular_stability) * 0.45
        - mutation_resistance * 0.20
    )
    level = level_from_risk(risk)
    stability = _clamp(
        cellular_stability * 0.55
        + mutation_resistance * 0.30
        + (100.0 - mutation_potential) * 0.15
        - level * 6.0
    )

    rng = random.Random(seed)
    mutation_type = rng.choice(MUTATION_TYPES) if level else "None"
    descriptions = {
        0: "No deviation detected in the simulated tissue.",
        1: "Trace deviation detected in the simulation readout.",
        2: "Localised fictional transformation detected.",
        3: "Clear transformation detected in the simulated tissue.",
        4: "Extensive transformation with reduced structural coherence.",
        5: "Critical transformation level; simulated stability is severely compromised.",
    }

    return MutationResult(
        mutation_type=mutation_type,
        mutation_level=level,
        mutation_level_name=MUTATION_LEVELS[level],
        mutation_stability=stability,
        mutation_risk=risk,
        occurred=level > 0,
        description=descriptions[level],
    )


def _record_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["mutation_level_name"] = MUTATION_LEVELS[result["mutation_level"]]
    return result


def record_mutation(session_id: int, tick: int, result: MutationResult) -> dict[str, Any]:
    """Save one mutation result and return the stored row."""
    if tick < 0:
        raise MutationError("tick must not be negative")

    with get_db() as conn:
        exists = conn.execute(
            "SELECT id FROM simulation_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if exists is None:
            raise MutationError(f"Simulation session {session_id} does not exist")

        cursor = conn.execute(
            """INSERT INTO mutation_records
            (session_id, tick, mutation_type, mutation_level,
                mutation_stability, mutation_risk, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, tick, result.mutation_type, result.mutation_level,
            result.mutation_stability, result.mutation_risk, result.description),
        )
        row = conn.execute(
            "SELECT * FROM mutation_records WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return _record_dict(row)


def get_mutations(session_id: int, limit: int = 200) -> list[dict[str, Any]]:
    """Return mutation history in tick order."""
    if not 1 <= limit <= 1000:
        raise MutationError("limit must be between 1 and 1000")
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM mutation_records WHERE session_id = ? ORDER BY tick, id LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [_record_dict(row) for row in rows]


def mutation_summary(session_id: int) -> dict[str, Any]:
    """Summarize mutation levels and types for a session."""
    records = get_mutations(session_id)
    if not records:
        return {"session_id": session_id, "records": 0, "peak_level": 0,
                "peak_level_name": MUTATION_LEVELS[0], "average_risk": None,
                "average_stability": None, "type_counts": {}}

    types: dict[str, int] = {}
    for row in records:
        if row["mutation_type"] != "None":
            types[row["mutation_type"]] = types.get(row["mutation_type"], 0) + 1
    peak = max(row["mutation_level"] for row in records)
    return {
        "session_id": session_id,
        "records": len(records),
        "peak_level": peak,
        "peak_level_name": MUTATION_LEVELS[peak],
        "average_risk": round(sum(r["mutation_risk"] for r in records) / len(records), 2),
        "average_stability": round(sum(r["mutation_stability"] for r in records) / len(records), 2),
        "type_counts": types,
    }
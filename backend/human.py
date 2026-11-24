"""Human profiles and biological parameter history for Nebula."""

from __future__ import annotations

import sqlite3
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.database import get_db


PHYSICAL_CLASSES = {
    0: "Normal",
    1: "Adapted",
    2: "Enhanced",
    3: "Advanced",
    4: "Superior",
    5: "Apex",
}

BIOLOGICAL_STATUSES = (
    "Normal",
    "Adaptation",
    "Enhanced",
    "Unstable",
    "Mutated",
    "Critical",
)

PARAMETER_FIELDS = (
    "muscle_density",
    "bone_density",
    "cardiovascular_capacity",
    "neural_activity",
    "cellular_stability",
    "metabolic_efficiency",
    "regeneration_index",
    "mutation_resistance",
)


class ProfileNotFoundError(Exception):
    """Raised when a human profile does not exist."""


class DuplicateSubjectError(Exception):
    """Raised when a subject code is already in use."""


class BiologicalParameters(BaseModel):
    """Biological parameters represented on a fictional 0-100 scale."""

    model_config = ConfigDict(extra="forbid")

    muscle_density: float = Field(default=50, ge=0, le=100)
    bone_density: float = Field(default=50, ge=0, le=100)
    cardiovascular_capacity: float = Field(default=50, ge=0, le=100)
    neural_activity: float = Field(default=50, ge=0, le=100)
    cellular_stability: float = Field(default=50, ge=0, le=100)
    metabolic_efficiency: float = Field(default=50, ge=0, le=100)
    regeneration_index: float = Field(default=50, ge=0, le=100)
    mutation_resistance: float = Field(default=50, ge=0, le=100)


class HumanProfileCreate(BaseModel):
    """Input model for creating a human profile."""

    model_config = ConfigDict(extra="forbid")

    subject_code: str = Field(min_length=3, max_length=32)
    full_name: str = Field(min_length=1, max_length=120)
    physical_class: int = Field(default=0, ge=0, le=5)
    biological_status: str = "Normal"
    notes: str | None = Field(default=None, max_length=500)
    initial_parameters: BiologicalParameters | None = None

    @field_validator("subject_code")
    @classmethod
    def normalize_subject_code(cls, value: str) -> str:
        code = value.strip().upper()
        if not all(char.isalnum() or char in "-_" for char in code):
            raise ValueError("subject_code may contain only letters, numbers, '-' and '_'")
        return code

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        name = " ".join(value.split())
        if not name:
            raise ValueError("full_name must not be blank")
        return name

    @field_validator("biological_status")
    @classmethod
    def validate_biological_status(cls, value: str) -> str:
        for status in BIOLOGICAL_STATUSES:
            if value.strip().lower() == status.lower():
                return status
        raise ValueError(f"biological_status must be one of {BIOLOGICAL_STATUSES}")


class HumanProfileUpdate(BaseModel):
    """Input model for partially updating a human profile."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    physical_class: int | None = Field(default=None, ge=0, le=5)
    biological_status: str | None = None
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("biological_status")
    @classmethod
    def validate_biological_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        for status in BIOLOGICAL_STATUSES:
            if value.strip().lower() == status.lower():
                return status
        raise ValueError(f"biological_status must be one of {BIOLOGICAL_STATUSES}")


def _profile_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["physical_class_name"] = PHYSICAL_CLASSES[result["physical_class"]]
    return result


def _parameters_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _get_profile_row(conn: sqlite3.Connection, profile_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM human_profiles WHERE id = ?",
        (profile_id,),
    ).fetchone()

    if row is None:
        raise ProfileNotFoundError(f"Human profile {profile_id} does not exist")

    return row


def _insert_parameters(
    conn: sqlite3.Connection,
    profile_id: int,
    parameters: BiologicalParameters,
) -> int:
    columns = ", ".join(PARAMETER_FIELDS)
    placeholders = ", ".join("?" for _ in PARAMETER_FIELDS)
    values = [getattr(parameters, field) for field in PARAMETER_FIELDS]

    cursor = conn.execute(
        f"INSERT INTO biological_parameters (profile_id, {columns}) "
        f"VALUES (?, {placeholders})",
        (profile_id, *values),
    )
    return int(cursor.lastrowid)


def create_profile(payload: HumanProfileCreate) -> dict[str, Any]:
    """Create a profile and its initial biological parameter record."""

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM human_profiles WHERE subject_code = ?",
            (payload.subject_code,),
        ).fetchone()

        if existing:
            raise DuplicateSubjectError(
                f"Subject code '{payload.subject_code}' is already in use"
            )

        cursor = conn.execute(
            """
            INSERT INTO human_profiles
                (subject_code, full_name, physical_class, biological_status, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload.subject_code,
                payload.full_name,
                payload.physical_class,
                payload.biological_status,
                payload.notes,
            ),
        )

        profile_id = int(cursor.lastrowid)
        parameters = payload.initial_parameters or BiologicalParameters()
        _insert_parameters(conn, profile_id, parameters)

        return _profile_dict(_get_profile_row(conn, profile_id))


def list_profiles() -> list[dict[str, Any]]:
    """Return all profiles."""

    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM human_profiles ORDER BY id"
        ).fetchall()

    return [_profile_dict(row) for row in rows]


def get_profile(profile_id: int) -> dict[str, Any]:
    """Return one profile by its database ID."""

    with get_db() as conn:
        row = _get_profile_row(conn, profile_id)

    return _profile_dict(row)


def update_profile(
    profile_id: int,
    payload: HumanProfileUpdate,
) -> dict[str, Any]:
    """Update the provided profile fields."""

    updates = payload.model_dump(exclude_unset=True)

    with get_db() as conn:
        _get_profile_row(conn, profile_id)

        if updates:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(
                f"""
                UPDATE human_profiles
                SET {assignments}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (*updates.values(), profile_id),
            )

        return _profile_dict(_get_profile_row(conn, profile_id))


def delete_profile(profile_id: int) -> None:
    """Delete a profile if it is not referenced by a simulation session."""

    with get_db() as conn:
        _get_profile_row(conn, profile_id)

        try:
            conn.execute(
                "DELETE FROM human_profiles WHERE id = ?",
                (profile_id,),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                "The profile is referenced by a simulation session and cannot be deleted"
            ) from exc


def add_biological_parameters(
    profile_id: int,
    parameters: BiologicalParameters,
) -> dict[str, Any]:
    """Append a new biological parameter snapshot."""

    with get_db() as conn:
        _get_profile_row(conn, profile_id)
        record_id = _insert_parameters(conn, profile_id, parameters)

        row = conn.execute(
            "SELECT * FROM biological_parameters WHERE id = ?",
            (record_id,),
        ).fetchone()

    return _parameters_dict(row)


def get_latest_parameters(profile_id: int) -> dict[str, Any] | None:
    """Return the latest biological parameter snapshot for a profile."""

    with get_db() as conn:
        _get_profile_row(conn, profile_id)

        row = conn.execute(
            """
            SELECT * FROM biological_parameters
            WHERE profile_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (profile_id,),
        ).fetchone()

    return _parameters_dict(row) if row else None


def derive_physical_class(parameters: dict[str, Any]) -> int:
    """Calculate a suggested Physical Class from the parameter values."""

    score = sum(float(parameters.get(field, 50)) for field in PARAMETER_FIELDS)
    score /= len(PARAMETER_FIELDS)

    if score < 20:
        return 0
    if score < 32:
        return 1
    if score < 45:
        return 2
    if score < 58:
        return 3
    if score < 72:
        return 4
    return 5


def composite_index(parameters: dict[str, Any]) -> float:
    """Average of the eight biological parameters, on a 0-100 scale."""

    total = sum(float(parameters.get(field, 50)) for field in PARAMETER_FIELDS)
    return round(total / len(PARAMETER_FIELDS), 2)


def resolve_biological_status(parameters: dict[str, Any], physical_class: int) -> str:
    """Derive a Biological Status from stability and resistance readings."""

    stability = float(parameters.get("cellular_stability", 50))
    resistance = float(parameters.get("mutation_resistance", 50))
    if stability < 30:
        return "Critical"
    if stability < 45 and resistance < 40:
        return "Mutated"
    if stability < 55:
        return "Unstable"
    if physical_class >= 2:
        return "Enhanced"
    if physical_class == 1:
        return "Adaptation"
    return "Normal"
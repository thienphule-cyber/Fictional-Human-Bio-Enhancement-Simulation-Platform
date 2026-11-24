"""Nebula Gas catalogue and Hazard Level reference data."""

from __future__ import annotations

import sqlite3
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.database import get_db


HAZARD_CLASSIFICATIONS = {
    0: "Inert",
    1: "Low Hazard",
    2: "Moderate Hazard",
    3: "High Hazard",
    4: "Extreme Hazard",
    5: "Critical Hazard",
}

MAX_HAZARD_BY_PHYSICAL_CLASS = {
    0: 0,
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
}


class GasNotFoundError(Exception):
    """Raised when a Nebula Gas record does not exist."""


class DuplicateGasError(Exception):
    """Raised when a gas ID is already in use."""


class NebulaGasCreate(BaseModel):
    """Input model for creating a Nebula Gas record."""

    model_config = ConfigDict(extra="forbid")

    gas_id: str = Field(min_length=3, max_length=32)
    gas_name: str = Field(min_length=1, max_length=120)
    hazard_level: int = Field(ge=0, le=5)
    gas_purity: float = Field(ge=0, le=100)
    energy_potential: float = Field(ge=0, le=100)
    mutation_potential: float = Field(ge=0, le=100)
    stability_index: float = Field(ge=0, le=100)
    classification: str | None = None

    @field_validator("gas_id")
    @classmethod
    def normalize_gas_id(cls, value: str) -> str:
        code = value.strip().upper()
        if not all(char.isalnum() or char in "-_" for char in code):
            raise ValueError("gas_id may contain only letters, numbers, '-' and '_'")
        return code

    @field_validator("gas_name")
    @classmethod
    def normalize_gas_name(cls, value: str) -> str:
        name = " ".join(value.split())
        if not name:
            raise ValueError("gas_name must not be blank")
        return name


class NebulaGasUpdate(BaseModel):
    """Input model for partially updating a Nebula Gas record."""

    model_config = ConfigDict(extra="forbid")

    gas_name: str | None = Field(default=None, min_length=1, max_length=120)
    hazard_level: int | None = Field(default=None, ge=0, le=5)
    gas_purity: float | None = Field(default=None, ge=0, le=100)
    energy_potential: float | None = Field(default=None, ge=0, le=100)
    mutation_potential: float | None = Field(default=None, ge=0, le=100)
    stability_index: float | None = Field(default=None, ge=0, le=100)
    classification: str | None = Field(default=None, max_length=60)


def _gas_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["hazard_name"] = HAZARD_CLASSIFICATIONS[result["hazard_level"]]
    return result


def _get_gas_row(conn: sqlite3.Connection, gas_pk: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM nebula_gases WHERE id = ?",
        (gas_pk,),
    ).fetchone()

    if row is None:
        raise GasNotFoundError(f"Nebula Gas {gas_pk} does not exist")

    return row


def create_gas(payload: NebulaGasCreate) -> dict[str, Any]:
    """Create a Nebula Gas catalogue entry."""

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM nebula_gases WHERE gas_id = ?",
            (payload.gas_id,),
        ).fetchone()

        if existing:
            raise DuplicateGasError(f"Gas ID '{payload.gas_id}' is already in use")

        classification = (
            payload.classification.strip()
            if payload.classification
            else HAZARD_CLASSIFICATIONS[payload.hazard_level]
        )

        cursor = conn.execute(
            """
            INSERT INTO nebula_gases (
                gas_id, gas_name, hazard_level, gas_purity,
                energy_potential, mutation_potential, stability_index,
                classification
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.gas_id,
                payload.gas_name,
                payload.hazard_level,
                payload.gas_purity,
                payload.energy_potential,
                payload.mutation_potential,
                payload.stability_index,
                classification,
            ),
        )

        return _gas_dict(_get_gas_row(conn, int(cursor.lastrowid)))


def list_gases(hazard_level: int | None = None) -> list[dict[str, Any]]:
    """Return all gases, optionally filtered by Hazard Level."""

    with get_db() as conn:
        if hazard_level is None:
            rows = conn.execute(
                "SELECT * FROM nebula_gases ORDER BY hazard_level, id"
            ).fetchall()
        else:
            if not 0 <= hazard_level <= 5:
                raise ValueError("hazard_level must be between 0 and 5")

            rows = conn.execute(
                """
                SELECT * FROM nebula_gases
                WHERE hazard_level = ?
                ORDER BY id
                """,
                (hazard_level,),
            ).fetchall()

    return [_gas_dict(row) for row in rows]


def get_gas(gas_pk: int) -> dict[str, Any]:
    """Return one gas by its database ID."""

    with get_db() as conn:
        row = _get_gas_row(conn, gas_pk)

    return _gas_dict(row)


def update_gas(gas_pk: int, payload: NebulaGasUpdate) -> dict[str, Any]:
    """Update provided gas fields."""

    updates = payload.model_dump(exclude_unset=True)
    updates = {key: value for key, value in updates.items() if value is not None}

    with get_db() as conn:
        current = _get_gas_row(conn, gas_pk)

        if "hazard_level" in updates and "classification" not in updates:
            updates["classification"] = HAZARD_CLASSIFICATIONS[
                updates["hazard_level"]
            ]

        if updates:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(
                f"UPDATE nebula_gases SET {assignments} WHERE id = ?",
                (*updates.values(), gas_pk),
            )

        return _gas_dict(_get_gas_row(conn, gas_pk))


def delete_gas(gas_pk: int) -> None:
    """Delete a gas unless it is referenced by a simulation session."""

    with get_db() as conn:
        _get_gas_row(conn, gas_pk)

        try:
            conn.execute(
                "DELETE FROM nebula_gases WHERE id = ?",
                (gas_pk,),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                "The gas is referenced by a simulation session and cannot be deleted"
            ) from exc


def hazard_ceiling(physical_class: int) -> int:
    """Return the maximum Hazard Level assigned to a Physical Class."""

    if physical_class not in MAX_HAZARD_BY_PHYSICAL_CLASS:
        raise ValueError("physical_class must be between 0 and 5")

    return MAX_HAZARD_BY_PHYSICAL_CLASS[physical_class]
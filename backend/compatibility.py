"""Fictional compatibility scoring between human profiles and Nebula Gas."""

from __future__ import annotations

from typing import Any

from backend.database import get_db
from backend.human import get_latest_parameters, get_profile
from backend.nebula import (
    HAZARD_CLASSIFICATIONS,
    get_gas,
    hazard_ceiling,
)


STATUS_COMPATIBLE = "Compatible"
STATUS_PARTIAL = "Partially Compatible"
STATUS_INCOMPATIBLE = "Incompatible"


class CompatibilityError(Exception):
    """Raised when compatibility cannot be evaluated."""


def _clamp(value: float) -> float:
    """Keep a score within the fictional 0-100 range."""

    return round(max(0.0, min(100.0, value)), 2)


def calculate_compatibility(
    physical_class: int,
    parameters: dict[str, Any],
    gas: dict[str, Any],
) -> dict[str, Any]:
    """Calculate compatibility indicators without accessing the database."""

    if not 0 <= physical_class <= 5:
        raise ValueError("physical_class must be between 0 and 5")

    hazard_level = int(gas["hazard_level"])
    if not 0 <= hazard_level <= 5:
        raise ValueError("hazard_level must be between 0 and 5")

    ceiling = hazard_ceiling(physical_class)
    excess_levels = max(0, hazard_level - ceiling)
    within_limit = excess_levels == 0

    cellular_stability = float(parameters.get("cellular_stability", 50))
    mutation_resistance = float(parameters.get("mutation_resistance", 50))
    metabolic_efficiency = float(parameters.get("metabolic_efficiency", 50))

    purity = float(gas["gas_purity"])
    energy = float(gas["energy_potential"])
    mutation_potential = float(gas["mutation_potential"])
    gas_stability = float(gas["stability_index"])

    class_fit = _clamp(100 - (hazard_level * 10) - (excess_levels * 25))

    gas_fit = _clamp(
        purity * 0.25
        + gas_stability * 0.35
        + energy * 0.15
        + (100 - mutation_potential) * 0.25
    )

    biological_buffer = _clamp(
        cellular_stability * 0.45
        + mutation_resistance * 0.45
        + metabolic_efficiency * 0.10
    )

    compatibility_score = _clamp(
        class_fit * 0.40
        + gas_fit * 0.30
        + biological_buffer * 0.30
    )

    digest_efficiency = _clamp(
        compatibility_score * 0.45
        + metabolic_efficiency * 0.25
        + purity * 0.20
        + gas_stability * 0.10
        - hazard_level * 5
    )

    adaptation_stability = _clamp(
        cellular_stability * 0.45
        + gas_stability * 0.35
        + mutation_resistance * 0.20
        - hazard_level * 5
    )

    mutation_risk = _clamp(
        mutation_potential * 0.40
        + hazard_level * 9
        + max(0, 60 - cellular_stability) * 0.50
        - mutation_resistance * 0.25
    )

    enhancement_potential = _clamp(
        energy * 0.35
        + digest_efficiency * 0.35
        + metabolic_efficiency * 0.15
        + adaptation_stability * 0.15
        - mutation_risk * 0.20
    )

    if excess_levels >= 2:
        result_status = STATUS_INCOMPATIBLE
    elif excess_levels == 1 or compatibility_score < 45:
        result_status = STATUS_INCOMPATIBLE
    elif excess_levels == 0 and compatibility_score >= 65:
        result_status = STATUS_COMPATIBLE
    else:
        result_status = STATUS_PARTIAL

    return {
        "physical_class": physical_class,
        "hazard_level": hazard_level,
        "hazard_classification": HAZARD_CLASSIFICATIONS[hazard_level],
        "class_hazard_ceiling": ceiling,
        "within_class_limit": within_limit,
        "compatibility_score": compatibility_score,
        "digest_efficiency": digest_efficiency,
        "adaptation_stability": adaptation_stability,
        "mutation_risk": mutation_risk,
        "enhancement_potential": enhancement_potential,
        "result_status": result_status,
    }


def evaluate(
    profile_id: int,
    gas_pk: int,
    persist: bool = True,
) -> dict[str, Any]:
    """Evaluate a stored profile against a stored gas."""

    profile = get_profile(profile_id)
    gas = get_gas(gas_pk)
    parameters = get_latest_parameters(profile_id)

    if parameters is None:
        raise CompatibilityError(
            f"Profile {profile_id} has no biological parameter records"
        )

    result = calculate_compatibility(
        profile["physical_class"],
        parameters,
        gas,
    )

    response = {
        "profile_id": profile_id,
        "gas_id": gas_pk,
        "profile": profile,
        "gas": gas,
        **result,
    }

    if persist:
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO compatibility_records (
                    profile_id, gas_id, compatibility_score,
                    digest_efficiency, adaptation_stability, mutation_risk,
                    enhancement_potential, result_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_id,
                    gas_pk,
                    result["compatibility_score"],
                    result["digest_efficiency"],
                    result["adaptation_stability"],
                    result["mutation_risk"],
                    result["enhancement_potential"],
                    result["result_status"],
                ),
            )

            response["record_id"] = int(cursor.lastrowid)

    return response
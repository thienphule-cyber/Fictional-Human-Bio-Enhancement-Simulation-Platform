"""FastAPI entry point for the Nebula simulation platform.

macOS-friendly by default: the server binds to 127.0.0.1 and scans upward from
the preferred port until it finds a free one, so it never collides with other
local development servers that are already running.
"""

from __future__ import annotations

import argparse
import os
import socket
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from backend import analytics, compatibility, devices, enhancement, hazard, human, mutation, nebula
from backend.analytics import ComparisonRequest
from backend.config import settings
from backend.database import init_db
from backend.enhancement import SessionCreate, StepRequest
from backend.human import BiologicalParameters, HumanProfileCreate, HumanProfileUpdate
from backend.nebula import NebulaGasCreate


# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables and seed reference data before serving requests."""
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Error handling
# --------------------------------------------------------------------------- #


_ERROR_STATUS: dict[type[Exception], int] = {
    human.ProfileNotFoundError: 404,
    nebula.GasNotFoundError: 404,
    devices.DeviceNotFoundError: 404,
    enhancement.SessionNotFoundError: 404,
    human.DuplicateSubjectError: 409,
    nebula.DuplicateGasError: 409,
    devices.DuplicateDeviceError: 409,
    compatibility.CompatibilityError: 400,
    devices.CommandNotAllowedError: 400,
    devices.DeviceError: 400,
    enhancement.SessionStateError: 409,
    enhancement.EnhancementError: 400,
    mutation.MutationError: 400,
    hazard.HazardError: 400,
    analytics.AnalyticsError: 400,
    ValueError: 400,
}


def _make_error_handler(status_code: int):
    def handler(request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={"detail": str(exc), "error_type": type(exc).__name__},
        )

    return handler


for error_type, status_code in _ERROR_STATUS.items():
    app.add_exception_handler(error_type, _make_error_handler(status_code))


# --------------------------------------------------------------------------- #
# Request models used by the API
# --------------------------------------------------------------------------- #


class CompatibilityRequest(BaseModel):
    """Body for evaluating one stored profile against one stored gas."""

    model_config = ConfigDict(extra="forbid")

    profile_id: int
    gas_id: int
    persist: bool = True


class DeviceCommandRequest(BaseModel):
    """Body for sending one control command to a device."""

    model_config = ConfigDict(extra="forbid")

    command: str


# --------------------------------------------------------------------------- #
# Health and metadata
# --------------------------------------------------------------------------- #


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Liveness probe used by the dashboard before rendering data."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database_ready": os.path.exists(settings.DB_PATH),
    }


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    """Server metadata: app identity and active runtime settings."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "host": getattr(app.state, "runtime_host", settings.HOST),
        "port": getattr(app.state, "runtime_port", settings.PORT),
        "debug": settings.DEBUG,
        "device_types": list(devices.DEVICE_TYPES),
        "device_commands": list(devices.DEVICE_COMMANDS),
        "session_statuses": list(enhancement.SESSION_STATUSES),
        "mutation_levels": mutation.MUTATION_LEVELS,
        "risk_statuses": hazard.RISK_STATUSES,
        "focus_targets": sorted(enhancement._FOCUS_TARGETS),
    }


# --------------------------------------------------------------------------- #
# Human profiles
# --------------------------------------------------------------------------- #


@app.post("/api/humans", status_code=201)
def create_human_profile(payload: HumanProfileCreate) -> dict[str, Any]:
    return human.create_profile(payload)


@app.get("/api/humans")
def list_human_profiles() -> list[dict[str, Any]]:
    return human.list_profiles()


@app.get("/api/humans/{profile_id}")
def get_human_profile(profile_id: int) -> dict[str, Any]:
    return human.get_profile(profile_id)


@app.patch("/api/humans/{profile_id}")
def update_human_profile(
    profile_id: int,
    payload: HumanProfileUpdate,
) -> dict[str, Any]:
    return human.update_profile(profile_id, payload)


@app.post("/api/humans/{profile_id}/parameters", status_code=201)
def add_parameters(
    profile_id: int,
    payload: BiologicalParameters,
) -> dict[str, Any]:
    return human.add_biological_parameters(profile_id, payload)


@app.get("/api/humans/{profile_id}/parameters/latest")
def get_latest_parameters(profile_id: int) -> dict[str, Any]:
    parameters = human.get_latest_parameters(profile_id)
    if parameters is None:
        raise HTTPException(
            status_code=404,
            detail="No biological parameters recorded yet",
        )
    return parameters


# --------------------------------------------------------------------------- #
# Nebula Gas catalogue
# --------------------------------------------------------------------------- #


@app.post("/api/gases", status_code=201)
def create_gas(payload: NebulaGasCreate) -> dict[str, Any]:
    return nebula.create_gas(payload)


@app.get("/api/gases")
def list_gases() -> list[dict[str, Any]]:
    return nebula.list_gases()


@app.get("/api/gases/{gas_pk}")
def get_gas(gas_pk: int) -> dict[str, Any]:
    return nebula.get_gas(gas_pk)


# --------------------------------------------------------------------------- #
# Compatibility
# --------------------------------------------------------------------------- #


@app.post("/api/compatibility")
def evaluate_compatibility(payload: CompatibilityRequest) -> dict[str, Any]:
    return compatibility.evaluate(
        payload.profile_id,
        payload.gas_id,
        persist=payload.persist,
    )


@app.get("/api/humans/{profile_id}/compatibility")
def profile_compatibility_history(
    profile_id: int,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if not 1 <= limit <= 500:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 500",
        )

    from backend.database import get_db

    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM compatibility_records
               WHERE profile_id = ? ORDER BY id DESC LIMIT ?""",
            (profile_id, limit),
        ).fetchall()

    return [dict(row) for row in rows]


# --------------------------------------------------------------------------- #
# Control devices
# --------------------------------------------------------------------------- #


@app.post("/api/devices", status_code=201)
def create_device(payload: devices.DeviceCreate) -> dict[str, Any]:
    return devices.create_device(payload)


@app.get("/api/devices")
def list_devices() -> list[dict[str, Any]]:
    return devices.list_devices()


@app.get("/api/devices/summary")
def devices_summary() -> dict[str, Any]:
    return devices.devices_summary()


@app.get("/api/devices/{device_id}")
def get_device(device_id: int) -> dict[str, Any]:
    return devices.get_device(device_id)


@app.patch("/api/devices/{device_id}/configuration")
def update_device_configuration(
    device_id: int,
    payload: devices.DeviceConfigurationUpdate,
) -> dict[str, Any]:
    return devices.update_configuration(device_id, payload)


@app.post("/api/devices/{device_id}/command")
def send_device_command(
    device_id: int,
    payload: DeviceCommandRequest,
) -> dict[str, Any]:
    return devices.send_command(device_id, payload.command)


@app.get("/api/devices/{device_id}/status")
def device_status(device_id: int) -> dict[str, Any]:
    return devices.device_status(device_id)


@app.get("/api/devices/{device_id}/effective-control")
def device_effective_control(device_id: int) -> dict[str, Any]:
    return devices.effective_control(device_id)


# --------------------------------------------------------------------------- #
# Simulation sessions
# --------------------------------------------------------------------------- #


@app.post("/api/sessions", status_code=201)
def create_session(payload: SessionCreate) -> dict[str, Any]:
    return enhancement.create_session(payload)


@app.get("/api/sessions")
def list_sessions(
    profile_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    return enhancement.list_sessions(profile_id=profile_id, limit=limit)


@app.get("/api/sessions/{session_id}")
def get_session(session_id: int) -> dict[str, Any]:
    return enhancement.get_session(session_id)


@app.post("/api/sessions/{session_id}/start")
def start_session(session_id: int) -> dict[str, Any]:
    return enhancement.start_session(session_id)


@app.post("/api/sessions/{session_id}/pause")
def pause_session(session_id: int) -> dict[str, Any]:
    return enhancement.pause_session(session_id)


@app.post("/api/sessions/{session_id}/stop")
def stop_session(session_id: int) -> dict[str, Any]:
    return enhancement.stop_session(session_id)


@app.post("/api/sessions/{session_id}/complete")
def complete_session(session_id: int) -> dict[str, Any]:
    return enhancement.complete_session(session_id)


@app.post("/api/sessions/{session_id}/shutdown")
def shutdown_session(session_id: int) -> dict[str, Any]:
    return enhancement.emergency_shutdown(session_id)


@app.post("/api/sessions/{session_id}/step")
def run_simulation_step(
    session_id: int,
    payload: StepRequest,
) -> dict[str, Any]:
    return enhancement.run_step(session_id, payload)


@app.get("/api/sessions/{session_id}/metrics")
def get_session_metrics(
    session_id: int,
    limit: int = 200,
) -> list[dict[str, Any]]:
    return enhancement.get_metrics(session_id, limit=limit)


@app.get("/api/sessions/{session_id}/enhancements")
def get_session_enhancements(
    session_id: int,
    limit: int = 200,
) -> list[dict[str, Any]]:
    return enhancement.get_enhancement_history(session_id, limit=limit)


@app.get("/api/sessions/{session_id}/summary")
def get_session_summary(session_id: int) -> dict[str, Any]:
    return enhancement.session_summary(session_id)


@app.get("/api/sessions/{session_id}/mutations")
def get_session_mutations(
    session_id: int,
    limit: int = 200,
) -> list[dict[str, Any]]:
    return mutation.get_mutations(session_id, limit=limit)


@app.get("/api/sessions/{session_id}/mutations/summary")
def get_session_mutation_summary(session_id: int) -> dict[str, Any]:
    return mutation.mutation_summary(session_id)


# --------------------------------------------------------------------------- #
# Hazard assessment
# --------------------------------------------------------------------------- #


@app.post("/api/sessions/{session_id}/hazard/assess")
def assess_session_hazard(
    session_id: int,
    persist: bool = True,
) -> dict[str, Any]:
    return hazard.assess_session(session_id, persist=persist)


@app.get("/api/sessions/{session_id}/hazard")
def get_hazard_history(
    session_id: int,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return hazard.get_assessment_history(session_id, limit=limit)


@app.get("/api/sessions/{session_id}/hazard/summary")
def get_hazard_summary(session_id: int) -> dict[str, Any]:
    return hazard.risk_summary(session_id)


# --------------------------------------------------------------------------- #
# Analytics
# --------------------------------------------------------------------------- #


@app.get("/api/analytics/sessions/{session_id}/trends")
def get_parameter_trends(
    session_id: int,
    limit: int = 500,
) -> dict[str, Any]:
    return analytics.parameter_trends(session_id, limit=limit)


@app.get("/api/analytics/sessions/{session_id}/deltas")
def get_parameter_deltas(session_id: int) -> dict[str, Any]:
    return analytics.parameter_deltas(session_id)


@app.get("/api/analytics/enhancement-history")
def get_enhancement_history(
    profile_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    return analytics.enhancement_history(profile_id=profile_id, limit=limit)


@app.get("/api/analytics/mutation-history")
def get_mutation_history(
    profile_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    return analytics.mutation_history(profile_id=profile_id, limit=limit)


@app.get("/api/analytics/hazard-history")
def get_analytics_hazard_history(
    profile_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    return analytics.hazard_history(profile_id=profile_id, limit=limit)


@app.post("/api/analytics/compare")
def compare_sessions(payload: ComparisonRequest) -> dict[str, Any]:
    return analytics.compare_sessions(payload)


@app.get("/api/analytics/sessions/{session_id}/report")
def get_session_report(session_id: int) -> dict[str, Any]:
    return analytics.session_report(session_id)


@app.get("/api/analytics/profiles/{profile_id}/report")
def get_profile_report(profile_id: int) -> dict[str, Any]:
    return analytics.profile_report(profile_id)


@app.get("/api/analytics/statistics")
def get_platform_statistics() -> dict[str, Any]:
    return analytics.platform_statistics()


@app.get("/api/analytics/recent")
def get_recent_activity(limit: int = 20) -> list[dict[str, Any]]:
    return analytics.recent_activity(limit=limit)


# --------------------------------------------------------------------------- #
# Static frontend
# --------------------------------------------------------------------------- #


FRONTEND_DIR = settings.BASE_DIR / "frontend"

if FRONTEND_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend",
    )
else:
    print(
        f"WARNING: frontend directory not found at {FRONTEND_DIR}; "
        "the API still works but no dashboard is served."
    )


# --------------------------------------------------------------------------- #
# Port discovery and server startup
# --------------------------------------------------------------------------- #


def bind_available_socket(
    host: str,
    preferred_port: int,
    attempts: int = 50,
) -> socket.socket:
    """Bind and listen on the first available port, keeping it reserved.

    Returning the already-bound socket avoids a race where another application
    could claim the port between checking it and Uvicorn binding to it.
    """
    if not 0 <= preferred_port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    if preferred_port == 0:
        ports = [0]
    else:
        ports = range(
            preferred_port,
            min(preferred_port + attempts, 65536),
        )

    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    last_error: OSError | None = None

    for port in ports:
        server_socket = socket.socket(family, socket.SOCK_STREAM)
        try:
            address: Any = (
                (host, port, 0, 0)
                if family == socket.AF_INET6
                else (host, port)
            )
            server_socket.bind(address)
            server_socket.listen(socket.SOMAXCONN)
            return server_socket
        except OSError as exc:
            last_error = exc
            server_socket.close()

    if preferred_port == 0:
        raise RuntimeError(
            f"Could not bind to an available port on {host}"
        ) from last_error

    last_port = min(preferred_port + attempts - 1, 65535)
    raise RuntimeError(
        f"No free port found between {preferred_port} and {last_port} on {host}"
    ) from last_error


def main() -> None:
    """Parse runtime options, reserve an available port and start Uvicorn."""
    parser = argparse.ArgumentParser(
        description="Nebula simulation platform server",
    )
    parser.add_argument(
        "--host",
        default=settings.HOST,
        help="Bind address (default: %(default)s; localhost-only by default)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.PORT,
        help="Preferred port; if busy, scan upward (default: %(default)s)",
    )
    parser.add_argument(
        "--no-scan",
        action="store_true",
        help="Use only the requested port and exit if it is busy",
    )
    args = parser.parse_args()

    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")

    attempts = 1 if args.no_scan and args.port != 0 else 50
    server_socket = bind_available_socket(
        args.host,
        args.port,
        attempts=attempts,
    )
    actual_port = int(server_socket.getsockname()[1])

    app.state.runtime_host = args.host
    app.state.runtime_port = actual_port

    if args.port != 0 and actual_port != args.port:
        print(
            f"NOTE: preferred port {args.port} is busy on {args.host}; "
            f"using the next free port {actual_port}."
        )

    display_host = f"[{args.host}]" if ":" in args.host else args.host
    print(f"Nebula dashboard: http://{display_host}:{actual_port}")

    config = uvicorn.Config(
        app,
        host=args.host,
        port=actual_port,
        log_level="info" if settings.DEBUG else "warning",
    )
    server = uvicorn.Server(config)

    try:
        # Passing the reserved socket lets Uvicorn use exactly the port found.
        server.run(sockets=[server_socket])
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
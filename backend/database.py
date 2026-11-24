"""
SQLite database connection management and schema initialization for Nebula.
Provides database context managers and creates all required relational tables.
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from backend.config import settings


def get_connection() -> sqlite3.Connection:
    """
    Creates and returns a SQLite connection configured with Row factory
    and Foreign Key constraints enabled.
    """
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for database transactions.
    Automatically commits on success and rolls back on unhandled exceptions.
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """
    Initializes all 12 platform tables and seeds baseline classification data.
    """
    schema = """
    -- 1. Human Profiles
    CREATE TABLE IF NOT EXISTS human_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_code TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        physical_class INTEGER NOT NULL CHECK (physical_class BETWEEN 0 AND 5),
        biological_status TEXT NOT NULL DEFAULT 'Normal',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 2. Biological Parameters
    CREATE TABLE IF NOT EXISTS biological_parameters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        muscle_density REAL NOT NULL,
        bone_density REAL NOT NULL,
        cardiovascular_capacity REAL NOT NULL,
        neural_activity REAL NOT NULL,
        cellular_stability REAL NOT NULL,
        metabolic_efficiency REAL NOT NULL,
        regeneration_index REAL NOT NULL,
        mutation_resistance REAL NOT NULL,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (profile_id) REFERENCES human_profiles(id) ON DELETE CASCADE
    );

    -- 3. Nebula Gases
    CREATE TABLE IF NOT EXISTS nebula_gases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gas_id TEXT UNIQUE NOT NULL,
        gas_name TEXT NOT NULL,
        hazard_level INTEGER NOT NULL CHECK (hazard_level BETWEEN 0 AND 5),
        gas_purity REAL NOT NULL CHECK (gas_purity BETWEEN 0.0 AND 100.0),
        energy_potential REAL NOT NULL,
        mutation_potential REAL NOT NULL,
        stability_index REAL NOT NULL,
        classification TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 4. Hazard Classifications (Reference Table)
    CREATE TABLE IF NOT EXISTS hazard_classifications (
        level INTEGER PRIMARY KEY CHECK (level BETWEEN 0 AND 5),
        classification TEXT NOT NULL,
        description TEXT NOT NULL
    );

    -- 5. Digest Compatibility Records
    CREATE TABLE IF NOT EXISTS compatibility_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        gas_id INTEGER NOT NULL,
        compatibility_score REAL NOT NULL,
        digest_efficiency REAL NOT NULL,
        adaptation_stability REAL NOT NULL,
        mutation_risk REAL NOT NULL,
        enhancement_potential REAL NOT NULL,
        result_status TEXT NOT NULL,
        evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (profile_id) REFERENCES human_profiles(id) ON DELETE CASCADE,
        FOREIGN KEY (gas_id) REFERENCES nebula_gases(id) ON DELETE CASCADE
    );

    -- 6. Enhancement Control Devices
    CREATE TABLE IF NOT EXISTS control_devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_code TEXT UNIQUE NOT NULL,
        device_name TEXT NOT NULL,
        device_type TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 7. Device Configurations
    CREATE TABLE IF NOT EXISTS device_configurations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        device_integrity REAL NOT NULL DEFAULT 100.0,
        monitoring_accuracy REAL NOT NULL DEFAULT 95.0,
        control_efficiency REAL NOT NULL DEFAULT 90.0,
        stability_support REAL NOT NULL DEFAULT 85.0,
        emergency_shutdown_status INTEGER NOT NULL DEFAULT 0,
        configured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (device_id) REFERENCES control_devices(id) ON DELETE CASCADE
    );

    -- 8. Simulation Sessions
    CREATE TABLE IF NOT EXISTS simulation_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_code TEXT UNIQUE NOT NULL,
        profile_id INTEGER NOT NULL,
        gas_id INTEGER NOT NULL,
        device_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'Created',
        current_tick INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (profile_id) REFERENCES human_profiles(id) ON DELETE RESTRICT,
        FOREIGN KEY (gas_id) REFERENCES nebula_gases(id) ON DELETE RESTRICT,
        FOREIGN KEY (device_id) REFERENCES control_devices(id) ON DELETE RESTRICT
    );

    -- 9. Enhancement Simulation Records
    CREATE TABLE IF NOT EXISTS enhancement_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        tick INTEGER NOT NULL,
        absorption_rate REAL NOT NULL,
        digestion_efficiency REAL NOT NULL,
        adaptation_rate REAL NOT NULL,
        enhancement_gain REAL NOT NULL,
        stability_score REAL NOT NULL,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES simulation_sessions(id) ON DELETE CASCADE
    );

    -- 10. Mutation Records
    CREATE TABLE IF NOT EXISTS mutation_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        tick INTEGER NOT NULL,
        mutation_type TEXT NOT NULL,
        mutation_level INTEGER NOT NULL CHECK (mutation_level BETWEEN 0 AND 5),
        mutation_stability REAL NOT NULL,
        mutation_risk REAL NOT NULL,
        description TEXT,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES simulation_sessions(id) ON DELETE CASCADE
    );

    -- 11. Simulation Metrics (Time-Series Data)
    CREATE TABLE IF NOT EXISTS simulation_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        tick INTEGER NOT NULL,
        muscle_density REAL NOT NULL,
        bone_density REAL NOT NULL,
        cardiovascular_capacity REAL NOT NULL,
        neural_activity REAL NOT NULL,
        cellular_stability REAL NOT NULL,
        metabolic_efficiency REAL NOT NULL,
        regeneration_index REAL NOT NULL,
        mutation_resistance REAL NOT NULL,
        biological_status TEXT NOT NULL,
        risk_level INTEGER NOT NULL CHECK (risk_level BETWEEN 0 AND 5),
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES simulation_sessions(id) ON DELETE CASCADE
    );

    -- 12. Hazard Assessments
    CREATE TABLE IF NOT EXISTS hazard_assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        tick INTEGER NOT NULL,
        risk_level INTEGER NOT NULL CHECK (risk_level BETWEEN 0 AND 5),
        stability_status TEXT NOT NULL,
        assessment_summary TEXT NOT NULL,
        shutdown_triggered INTEGER NOT NULL DEFAULT 0,
        assessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES simulation_sessions(id) ON DELETE CASCADE
    );
    """

    seed_hazard_levels = """
    INSERT OR IGNORE INTO hazard_classifications (level, classification, description)
    VALUES
        (0, 'Inert', 'No biological hazard detected. Neutral physiological reaction.'),
        (1, 'Low Hazard', 'Minor cellular agitation. Safe for adapted profiles.'),
        (2, 'Moderate Hazard', 'Substantial energy output. Requires stable monitoring.'),
        (3, 'High Hazard', 'High cellular breakdown risk and aggressive mutation.'),
        (4, 'Extreme Hazard', 'Severe mutation hazard. Rapid biological instability.'),
        (5, 'Critical Hazard', 'Catastrophic biological collapse threshold.');
    """

    with get_db() as conn:
        conn.executescript(schema)
        conn.executescript(seed_hazard_levels)


if __name__ == "__main__":
    # Allows initializing the database directly via: python -m backend.database
    init_db()
    print(f"Database initialized successfully at: {settings.DB_PATH}")
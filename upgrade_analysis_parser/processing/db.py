import sqlite3
import json
import contextlib
from pathlib import Path
from typing import List

from ..models import ChangeRecord

from config import (
    DB_PATH
)

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@contextlib.contextmanager
def sqlite_db(version: float, clean: bool = False):
    db_path = Path(DB_PATH) / f"{version}.db"
    if clean and db_path.exists():
        db_path.unlink()
    logger.debug(f"Connecting to {db_path}")
    if not db_path.exists() and not clean:
        err_msg = 'Database %s does not exist' % db_path
        logger.error(err_msg)
        raise OSError(err_msg)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        yield cursor
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        conn.close()

def setup_database(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        schema_sql = """
            CREATE TABLE IF NOT EXISTS changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                module TEXT NOT NULL,
                change_category TEXT NOT NULL,
                change_type TEXT NOT NULL,
                model_name TEXT,
                field_name TEXT,
                record_model TEXT,
                xml_id TEXT,
                description TEXT,
                raw_line TEXT,
                details_json TEXT
            );
        """
        cursor.execute(schema_sql)
        conn.commit()


def clear_all_changes(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        logger.info(f"Clearing old data from {db_path.name}...")
        cursor.execute("DELETE FROM changes;")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='changes';")
        conn.commit()
        logger.info("Old data cleared.")


def insert_data(db_path: Path, data: List[ChangeRecord]) -> None:
    seen_raw_lines = set()
    unique_data = []
    for d in data:
        if d.raw_line not in seen_raw_lines:
            seen_raw_lines.add(d.raw_line)
            unique_data.append(d)

    if not unique_data:
        logger.info("No new unique records to insert.")
        return
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        insert_sql = """
            INSERT INTO changes (
                version,
                module,
                change_category,
                change_type,
                model_name,
                field_name,
                record_model,
                xml_id,
                description,
                raw_line,
                details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        rows_to_insert = [
            (
                d.version,
                d.module,
                d.change_category,
                d.change_type,
                d.model_name,
                d.field_name,
                d.record_model,
                d.xml_id,
                d.description,
                d.raw_line,
                json.dumps(d.details_json),
            )
            for d in unique_data
        ]
        cursor.executemany(insert_sql, rows_to_insert)
        conn.commit()
        logger.info(
            f"Successfully inserted {len(rows_to_insert)} new records into {db_path.name}."
        )

def db_path_for_version(major_version: float) -> Path:
    return Path(DB_PATH) / f"{major_version}.db"

def ensure_db_exists(db_path: Path, version: float) -> bool:
    if not db_path.exists():
        logger.error(f"Database for version {version} not found at {db_path}.")
        logger.error(f"Please run 'python manage.py parse --versions {version}' first.")
        return False
    return True

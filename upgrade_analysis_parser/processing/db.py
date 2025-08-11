import sqlite3
import json
from pathlib import Path
from typing import List

from ..models import ChangeRecord

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
            for d in data
        ]
        cursor.executemany(insert_sql, rows_to_insert)
        conn.commit()
        logger.info(
            f"Successfully inserted {len(rows_to_insert)} new records into {db_path.name}."
        )
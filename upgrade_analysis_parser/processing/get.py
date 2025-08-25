from pathlib import Path

from .db import db_path_for_version, ensure_db_exists

import logging
import sqlite3
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_removed_models(major_version: float, out_dir: Path) -> None:
    db_path = db_path_for_version(major_version)
    if not ensure_db_exists(db_path, major_version):
        return
    models = []
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT model_name
            FROM changes
            WHERE change_category='MODEL' AND change_type='OBSOLETE' AND model_name IS NOT NULL
            ORDER BY model_name
            """
        )
        models = [row[0] for row in cur.fetchall()]
    target_file = out_dir / "removed_models.yaml"
    with open(target_file, "w", encoding="utf-8") as f:
        for m in models:
            f.write(f"- ['{m}', '']\n")
    logger.info(f"Wrote {len(models)} removed models to {target_file}")


def generate_removed_fields(major_version: float, out_dir: Path) -> None:
    db_path = db_path_for_version(major_version)
    if not ensure_db_exists(db_path, major_version):
        return
    by_module = defaultdict(list)
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT module, model_name, field_name
            FROM changes
            WHERE change_category='FIELD' AND change_type='DEL'
                  AND model_name IS NOT NULL AND field_name IS NOT NULL
            ORDER BY module, model_name, field_name
            """
        )
        for module, model, field in cur.fetchall():
            by_module[module].append((model, field))
    count_files = 0
    total_entries = 0
    for module, items in by_module.items():
        target_file = out_dir / f"{module}.yaml"
        with open(target_file, "w", encoding="utf-8") as f:
            for model, field in items:
                f.write(f"- ['{model}', '{field}', '']\n")
        count_files += 1
        total_entries += len(items)
    logger.info(f"Wrote {total_entries} removed fields across {count_files} module files in {out_dir}")

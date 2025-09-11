# Copyright 2025 Trobz
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from pathlib import Path
import json
import re

from .db import db_path_for_version, ensure_db_exists
from .parser import parse_pre_migration_for_renamed_fields
from config import OPENUPGRADE_SCRIPTS_SOURCES_PATH

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


def generate_renamed_models(major_version: float, out_dir: Path) -> None:
    """Generate renamed models YAML combining both directions from parser output.

    Output file: renamed_models.yaml
    Each line: ["old.model", "new.model", None]
    """
    db_path = db_path_for_version(major_version)
    if not ensure_db_exists(db_path, major_version):
        return
    renamed_model_pairs = set()
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT model_name, details_json
            FROM changes
            WHERE change_category='MODEL' AND details_json IS NOT NULL AND model_name IS NOT NULL
            ORDER BY model_name
            """
        )
        rows = cur.fetchall()
    for model_name, details_json in rows:
        try:
            details = json.loads(details_json) if details_json else {}
        except json.JSONDecodeError:
            details = {}
        info = details.get("rename_info") if isinstance(details, dict) else None
        if not info:
            continue
        m_to = re.search(r"\brenamed\s+to\s+([\w\.]+)", info)
        m_from = re.search(r"\brenamed\s+from\s+([\w\.]+)", info)
        if m_to:
            old_model = model_name
            new_model = m_to.group(1)
            renamed_model_pairs.add((old_model, new_model))
        elif m_from:
            old_model = m_from.group(1)
            new_model = model_name
            renamed_model_pairs.add((old_model, new_model))
    target_file = out_dir / "renamed_models.yaml"
    with open(target_file, "w", encoding="utf-8") as f:
        for old, new in sorted(renamed_model_pairs):
            f.write(f"- [\"{old}\", \"{new}\", None]\n")
    logger.info(f"Wrote {len(renamed_model_pairs)} renamed models to {target_file}")

def generate_renamed_fields(major_version: float, out_dir: Path) -> None:
    """Generate renamed fields YAML by parsing pre-migration.py rename_fields calls.

    Output files: one per module, named {module}.yaml
    Each line: ['model', 'old_field', 'new_field', '']
    """
    base = Path(OPENUPGRADE_SCRIPTS_SOURCES_PATH) / str(major_version)
    if not base.exists():
        logger.error(f"Source directory not found for version {major_version} at {base}.")
        logger.error(f"Please run 'python manage.py sync --versions {major_version}' first.")
        return
    renamed_fields_by_module: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for pre_path in base.glob("**/*/pre-migration.py"):
        # .../<module>/<version>/pre-migration.py
        if pre_path.parent is None or pre_path.parent.parent is None:
            continue
        module_name = pre_path.parent.parent.name
        tuples = parse_pre_migration_for_renamed_fields(pre_path)
        if tuples:
            renamed_fields_by_module[module_name].extend(tuples)
    count_files = 0
    total_entries = 0
    for module, entries in sorted(renamed_fields_by_module.items()):
        # Ensure deterministic ordering within each file
        entries_sorted = sorted(entries)
        target_file = out_dir / f"{module}.yaml"
        with open(target_file, "w", encoding="utf-8") as f:
            for model, old_field, new_field in entries_sorted:
                f.write(f"- ['{model}', '{old_field}', '{new_field}', '']\n")
        count_files += 1
        total_entries += len(entries_sorted)
    logger.info(f"Wrote {total_entries} renamed fields across {count_files} module files in {out_dir}")
